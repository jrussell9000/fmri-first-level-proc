#!/usr/bin/env python3

# ============================================================================
# RESTING-STATE fMRI CONNECTIVITY ANALYSIS
# 1. Per-run nuisance regression and bandpass filtering via AFNI's 3dTproject
#    (simultaneous backend) or 3dBandpass + 3dTproject (sequenced backend),
#    then residuals are concatenated into one time series with 3dTcat
# 2. (optional) Extract parcel-level time series with a provided template
# 3. (optional) Compute functional connectivity (parcellated or seed-to-voxel)
#
# Author: Taylor J. Keding, Ph.D.
# ============================================================================
"""
Resting-state connectivity first-level pipeline.

INPUTS
------
Per-run lists (always Mode A): paths.scan_paths, paths.motion_paths,
paths.CSF_paths, paths.WM_paths, paths.GS_paths (optional), aligned with
run_labels.

Other inputs: fd_threshold, censor_prev_tr, bandpass, notch_filter_band,
motion_deriv_degree, use_tissue_derivs, use_sequenced_bandpass,
keep_run_res_dtseries, scale_to_psc, average_type, roi_zero_handling,
template_path (global), smoothing (enabled, fwhm), extraction
(extract_ptseries, extract_out_file_pre, extract_raw_ptseries),
connectivity (calc_conn, conn_out_file_pre, pcorr, fishZ).

The per-run polort for the simultaneous backend is 2 when bandpass[0] > 0,
else 1 + floor(n_vols * tr / 150). The sequenced backend always runs with
polort -1 in its NTRP-interpolation and final regression steps, relying on
3dBandpass's default quadratic detrend for polynomial removal.

FINAL OUTPUTS
-------------
{pre}_concat_residual_dtseries.nii.gz (frozen primary output)
{pre}_run{N}_residual_dtseries.nii.gz (when keep_run_res_dtseries is true)
{ext}_residual_ptseries.csv
{ext}_run{N}_raw_ptseries.csv, {ext}_run{N}_raw_psc_ptseries.csv
{pre}_run{N}_min_outlier_epi.nii.gz
Connectivity outputs
_s{N}mm smoothed siblings of residual dtseries
{pre}_qc_summary.json

INTERMEDIATE OUTPUTS
---------------------
{pre}_ledger.jsonl, run mean/PSC volumes, notch/censor/side/motion files,
prepared tissue regressors (first column of each CSF/WM/GS file),
tissue derivative files, resampled template, smoothing mask, sequenced
backend intermediates (kept only when keep_run_res_dtseries is true).

STEP ORDER
----------
Always-run: rest-conn-nuisance.
Ledgered: rest-conn-template (if template used), rest-conn-prep, then
either {rest-conn-residuals-run{N} for each S_pre run, rest-conn-concat}
(keep_run_res_dtseries true) or {rest-conn-residuals-concat}
(keep_run_res_dtseries false), rest-conn-raw-ptseries (if configured),
rest-conn-min-outlier-epi, rest-conn-smooth-residuals (if smoothing enabled),
rest-conn-ptseries (if configured), rest-conn-connectivity (if configured),
rest-conn-roi-qc (if template used).
Final: rest-conn-qc.
"""

import copy
import os

import numpy as np

from . import names, roi, smoothing, connectivity
from .engine import RunContext, StageSpec, Outcome, Output, run_with_status
from .runsets import build_runsets
from .runtime import runtime_check
from .exceptions import ConfigError, GuardError, ModelError, ToolExecutionError
from .first_level_utils import (
    clear_warnings,
    setup_logging,
    run_afni_command,
    graded_warning,
    gen_min_outlier_epi,
    write_tissue_derivative,
    censor_interpolate_1d_afni,
    bandpass_filter_1d_afni,
)
from . import nuisance as nuisance_mod
from . import prep


# ---------------------------------------------------------------------------
# Residual regression backends
# ---------------------------------------------------------------------------

def _residual_simultaneous(io, config, label, run_input, censor, motion,
                           tissue_paths, polort, out_rel, logger):
    """Compute residuals for one run via the simultaneous backend (3dTproject).

    Parameters
    ----------
    io : StepIO
    config : ResolvedConfig
    label : int
    run_input : str
        AFNI selector for the run's input time series.
    censor, motion : str
        Absolute paths.
    tissue_paths : dict
        {'CSF': path, 'WM': path, 'GS': path or None, 'derivs': {...}}
    polort : int
    out_rel : str
    logger : logging.Logger

    Returns
    -------
    Output
    """
    cmd = ["3dTproject", "-input", run_input, "-dt", str(config.tr),
           "-censor", censor, "-cenmode", "ZERO",
           "-ort", motion, "-ort", tissue_paths["CSF"], "-ort", tissue_paths["WM"]]
    if tissue_paths.get("GS"):
        cmd.extend(["-ort", tissue_paths["GS"]])
    for d in tissue_paths.get("derivs", {}).values():
        cmd.extend(["-ort", d])
    cmd.extend([
        "-polort", str(polort),
        "-bandpass", str(config.bandpass[0]), str(config.bandpass[1]),
        "-prefix", io.path(out_rel),
    ])

    run_afni_command(cmd, description=f"3dTproject residuals run {label}",
                     logger=logger, cwd=io.staging)

    return Output(out_rel, "final", "nifti", producer=f"3dTproject residuals run {label}")


def _residual_sequenced(io, config, label, run_input, censor, motion,
                        tissue_paths, out_rel, logger):
    """Compute residuals for one run via the sequenced backend: NTRP-interpolate
    censored TRs, 3dBandpass BOLD and nuisance regressors at the same passband,
    regress (no -bandpass), zero censored TRs. Interpolation before filtering
    and re-censoring follow Power et al. (2014), with linear rather than
    spectral interpolation; passband-matched regressors follow Hallquist et al.
    (2013), whose preferred single-step approach is the simultaneous backend.

    Parameters
    ----------
    io : StepIO
    config : ResolvedConfig
    label : int
    run_input : str
    censor, motion : str
    tissue_paths : dict
    out_rel : str
    logger : logging.Logger

    Returns
    -------
    (Output, list of Output)
        The final residual output and the list of kept intermediate outputs.
    """
    seq_dir = names.sequenced_dir(config.out_file_pre, label)
    extra_outputs = []

    def seq_path(name):
        return f"{seq_dir}/{name}"

    os.makedirs(io.path(seq_dir), exist_ok=True)

    # NTRP-interpolate the BOLD input
    bold_interp_rel = seq_path("bold_interp.nii.gz")
    run_afni_command(
        ["3dTproject", "-polort", "-1", "-dt", str(config.tr),
         "-input", run_input, "-censor", censor, "-cenmode", "NTRP",
         "-prefix", io.path(bold_interp_rel)],
        description=f"3dTproject NTRP interpolate BOLD run {label}",
        logger=logger, cwd=io.staging,
    )
    extra_outputs.append(Output(bold_interp_rel, "intermediate", "nifti",
                                producer=f"NTRP interpolated BOLD run {label}"))

    # 3dBandpass the interpolated BOLD
    bold_bp_rel = seq_path("bold_bp.nii.gz")
    run_afni_command(
        ["3dBandpass", "-dt", str(config.tr),
         "-prefix", io.path(bold_bp_rel),
         str(config.bandpass[0]), str(config.bandpass[1]),
         io.path(bold_interp_rel)],
        description=f"3dBandpass BOLD run {label}",
        logger=logger, cwd=io.staging,
    )
    extra_outputs.append(Output(bold_bp_rel, "intermediate", "nifti",
                                producer=f"bandpassed BOLD run {label}"))

    # Interpolate and bandpass nuisance regressors at the same passband.
    # AFNI opens a 1D file passed to -input with the transpose quote only
    # when it has a .1D/.1d extension (any extension works via -ort), so
    # user-supplied CSF/WM/GS paths are copied to a .1D name first.
    def _ensure_1d(path, tag):
        if path.endswith(".1D") or path.endswith(".1d"):
            return path
        rel = f"_seq_src_{tag}.1D"
        with open(path, "r") as fsrc:
            content = fsrc.read()
        with open(io.path(rel), "w", newline="") as fdst:
            fdst.write(content)
        return io.path(rel)

    nuisance_interp = {}
    for key, path in [("motion", motion), ("CSF", tissue_paths["CSF"]),
                      ("WM", tissue_paths["WM"])]:
        norm_path = _ensure_1d(path, f"{key}_run{label}")
        interp_path = censor_interpolate_1d_afni(
            norm_path, config.tr, censor, io.staging, config.out_file_pre,
            f"{key}_run{label}", logger, cwd=io.staging,
        )
        bp_path = bandpass_filter_1d_afni(
            interp_path, config.tr, config.bandpass, io.staging,
            config.out_file_pre, f"{key}_run{label}", logger, cwd=io.staging,
        )
        nuisance_interp[key] = bp_path

    if tissue_paths.get("GS"):
        gs_norm = _ensure_1d(tissue_paths["GS"], f"GS_run{label}")
        interp_gs = censor_interpolate_1d_afni(
            gs_norm, config.tr, censor, io.staging,
            config.out_file_pre, f"GS_run{label}", logger, cwd=io.staging,
        )
        nuisance_interp["GS"] = bandpass_filter_1d_afni(
            interp_gs, config.tr, config.bandpass, io.staging,
            config.out_file_pre, f"GS_run{label}", logger, cwd=io.staging,
        )

    for dname, dpath in tissue_paths.get("derivs", {}).items():
        dkey = f"{dname}_deriv"
        interp_d = censor_interpolate_1d_afni(
            dpath, config.tr, censor, io.staging, config.out_file_pre,
            f"{dname}_deriv_run{label}", logger, cwd=io.staging,
        )
        nuisance_interp[dkey] = bandpass_filter_1d_afni(
            interp_d, config.tr, config.bandpass, io.staging,
            config.out_file_pre, f"{dname}_deriv_run{label}", logger, cwd=io.staging,
        )

    # Final regression (polort -1, no -bandpass; frequency content already matched)
    reg_rel = seq_path("regressed.nii.gz")
    cmd = ["3dTproject", "-input", io.path(bold_bp_rel), "-dt", str(config.tr),
           "-polort", "-1",
           "-ort", nuisance_interp["motion"],
           "-ort", nuisance_interp["CSF"],
           "-ort", nuisance_interp["WM"]]
    if "GS" in nuisance_interp:
        cmd.extend(["-ort", nuisance_interp["GS"]])
    for key, path in nuisance_interp.items():
        if key not in ("motion", "CSF", "WM", "GS"):
            cmd.extend(["-ort", path])
    cmd.extend(["-prefix", io.path(reg_rel)])
    run_afni_command(cmd, description=f"3dTproject final regression run {label}",
                     logger=logger, cwd=io.staging)
    extra_outputs.append(Output(reg_rel, "intermediate", "nifti",
                                producer=f"regressed run {label}"))

    # Post-step: re-apply censor mask (zero out censored TRs)
    censor_vec = np.loadtxt(censor, dtype=int).ravel()
    run_afni_command(
        ["3dcalc", "-a", io.path(reg_rel),
         "-b", f"1D: {' '.join(str(int(c)) for c in censor_vec)}",
         "-expr", "a*b", "-prefix", io.path(out_rel)],
        description=f"3dcalc apply censor run {label}",
        logger=logger, cwd=io.staging,
    )

    final_output = Output(out_rel, "final", "nifti",
                          producer=f"sequenced residuals run {label}")
    return final_output, extra_outputs


# ---------------------------------------------------------------------------
# Expected-path enumeration
# ---------------------------------------------------------------------------

def rest_expected(config, runsets, excluded_runs):
    """Enumerate every final output and deterministic intermediate for rest_conn.

    Returns
    -------
    set of str
    """
    pre = config.out_file_pre
    expected = set()
    s_pre = runsets.s_pre

    expected.add(names.ledger(pre))
    expected.add(names.qc_summary(pre))
    expected.add(names.residual_concat(pre))

    try:
        s_final = runsets.s_final
    except GuardError:
        s_final = s_pre

    if config.keep_run_res_dtseries:
        for lbl in s_final:
            expected.add(names.residual_run(pre, lbl))

    for lbl in s_final:
        expected.add(names.min_outlier_epi(pre, lbl))

    if config.scale_to_psc:
        for lbl in s_pre:
            expected.add(names.run_mean(pre, lbl))
            expected.add(names.run_psc(pre, lbl))

    if config.template_path is not None:
        expected.add(names.template_resampled(pre, config.template_path))

    if config.extract_raw_ptseries and config.extract_out_file_pre:
        ext = config.extract_out_file_pre
        for lbl in s_final:
            expected.add(names.raw_ptseries(ext, lbl))
            if config.scale_to_psc:
                expected.add(names.raw_psc_ptseries(ext, lbl))

    if config.extract_ptseries and config.extract_out_file_pre:
        expected.add(names.residual_ptseries(config.extract_out_file_pre))

    if config.calc_conn is not None and config.conn_out_file_pre:
        expected.add(names.conn_output(config.conn_out_file_pre, None,
                                       config.fishZ, config.pcorr, config.calc_conn))

    for lbl in s_pre:
        if config.notch_filter_band is not None:
            expected.add(names.notch_motion(pre, lbl))
        expected.add(names.censor(pre, lbl))
        for sf in names.censor_side_files(pre, lbl):
            expected.add(sf)
        expected.add(names.motion_prepared(pre, lbl))
        for tissue in ("CSF", "WM") + (("GS",) if config.GS_paths else ()):
            expected.add(names.tissue_prepared(pre, tissue, lbl))

    if config.smoothing_enabled:
        token = names.smoothing_token(config.smoothing_fwhm)
        expected.add(names.smoothing_mask(pre))
        expected.add(names.residual_concat(pre, token))
        if config.keep_run_res_dtseries:
            for lbl in s_final:
                expected.add(names.residual_run(pre, lbl, token))
        if config.calc_conn == "seed_to_voxel" and config.conn_out_file_pre:
            expected.add(names.conn_output(config.conn_out_file_pre, None,
                                           config.fishZ, config.pcorr,
                                           config.calc_conn, token))

    return expected


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run(config, logger=None):
    """Run the resting-state connectivity first-level pipeline.

    On failure, the error is recorded in {pre}_qc_summary.json (run_status)
    and the exception is re-raised.

    Parameters
    ----------
    config : ResolvedConfig
    logger : logging.Logger, optional

    Returns
    -------
    FirstLevelResult
    """
    if logger is None:
        logger = setup_logging("rest_conn_first_level")
    return run_with_status("rest_conn", config, logger, _run)


def _run(config, logger, tracker):
    """Pipeline body; see run()."""

    config = copy.copy(config)
    clear_warnings()
    tracker.step = "rest-conn-runtime-check"
    versions = runtime_check(logger)
    tracker.versions = versions

    # Path-list length guard
    tracker.step = "rest-conn-path-checks"
    n_runs = len(config.scan_paths)
    for name_, lst in [("motion_paths", config.motion_paths),
                       ("CSF_paths", config.CSF_paths),
                       ("WM_paths", config.WM_paths)]:
        if len(lst) != n_runs:
            raise ConfigError(
                f"{name_} has {len(lst)} entries but scan_paths has {n_runs}."
            )
    if config.GS_paths is not None:
        if len(config.GS_paths) != n_runs:
            raise ConfigError(
                f"GS_paths has {len(config.GS_paths)} entries but "
                f"scan_paths has {n_runs}."
            )
        logger.info("Global signal regression enabled (%d runs).", n_runs)
    else:
        graded_warning(
            logger, "low", "GS_MISSING",
            "GS_paths not provided; global signal regression disabled.",
            user_facing=False,
        )

    tracker.step = "rest-conn-run-sets"
    runsets = build_runsets(config, "rest_conn", logger)
    ctx = RunContext(config, "rest_conn", logger, versions, runsets.grid_ref, tracker=tracker)
    ctx.start()

    pre = config.out_file_pre

    # Template checks
    template_used = config.template_path is not None and (
        config.extract_ptseries or config.extract_raw_ptseries
        or config.calc_conn is not None
    )
    conn_types = set()
    if config.extract_ptseries or config.extract_raw_ptseries:
        conn_types.add("extract")
    if config.calc_conn:
        conn_types.add(config.calc_conn)
    same_grid = None
    if template_used:
        tracker.step = "rest-conn-template-check"
        same_grid = roi.check_template(
            config.template_path, runsets.grid_ref, config.force_diff_atlas,
            conn_types, logger,
        )

    # Step: rest-conn-nuisance
    def _nuisance_step(io):
        outcome, state = nuisance_mod.rest_nuisance(io, config, runsets, logger)
        ctx._nuisance_state = state
        return outcome

    ctx.run_step("rest-conn-nuisance", _nuisance_step)
    nuisance_state = ctx._nuisance_state
    s_pre = runsets.s_pre

    # Ledgered stage: rest-conn-template
    template_resolved = config.template_path
    if template_used:
        template_resolved = roi.template_stage(
            ctx, config, runsets, pre, same_grid, "rest-conn", logger,
        )

    # Ledgered stage: rest-conn-prep
    prep_spec = StageSpec(
        label="rest-conn-prep",
        fields=("scan_paths", "scale_to_psc", "run_labels"),
        derived_values={"s_pre": list(s_pre)},
    )

    def _prep_stage(io):
        return prep.rest_prep(io, config, runsets, logger)

    ctx.run_stage(prep_spec, _prep_stage)

    def _tissue_paths_for(lbl):
        # Prepared single-column copies written by rest-conn-nuisance
        prepared = nuisance_state["tissue_prepared"][lbl]
        tp = {
            "CSF": f"{config.out_dir}/{prepared['CSF']}",
            "WM": f"{config.out_dir}/{prepared['WM']}",
            "GS": f"{config.out_dir}/{prepared['GS']}" if "GS" in prepared else None,
            "derivs": {},
        }
        return tp

    def _prepared_tissue_files(lbl):
        prepared = nuisance_state["tissue_prepared"][lbl]
        return [f"{config.out_dir}/{prepared[t]}" for t in ("CSF", "WM", "GS") if t in prepared]

    def _motion_prepared_path(lbl):
        return f"{config.out_dir}/{names.motion_prepared(pre, lbl)}"

    def _censor_path(lbl):
        return f"{config.out_dir}/{names.censor(pre, lbl)}"

    def _run_input(lbl):
        return prep.rest_run_input(config, runsets, config.out_dir, lbl)

    # One ledgered stage per run (keep_run_res_dtseries true) or one stage
    # covering all runs (false)
    failed_runs_record = []

    if config.keep_run_res_dtseries:
        s_final_candidates = []
        for lbl in s_pre:
            ri = runsets.run(lbl)
            polort = nuisance_state["polort"][lbl]
            label_str = f"rest-conn-residuals-run{lbl}"

            run_spec = StageSpec(
                label=label_str,
                fields=("tr", "bandpass", "notch_filter_band", "motion_deriv_degree",
                        "fd_threshold", "censor_prev_tr", "use_tissue_derivs",
                        "use_sequenced_bandpass", "keep_run_res_dtseries"),
                derived_files=(
                    [f"{config.out_dir}/{names.censor(pre, lbl)}",
                     f"{config.out_dir}/{names.motion_prepared(pre, lbl)}"]
                    + ([f"{config.out_dir}/{names.notch_motion(pre, lbl)}"]
                       if config.notch_filter_band else [])
                    + _prepared_tissue_files(lbl)
                ),
                derived_values={
                    "run_label": lbl,
                    "scan": config.scan_paths[ri.position],
                    "motion": config.motion_paths[ri.position],
                    "CSF": config.CSF_paths[ri.position],
                    "WM": config.WM_paths[ri.position],
                    "GS": config.GS_paths[ri.position] if config.GS_paths else None,
                    "polort": polort,
                    "scale_to_psc": config.scale_to_psc,
                },
                upstream=("rest-conn-prep",),
            )

            def _residual_run_stage(io, lbl=lbl, ri=ri, polort=polort):
                run_input = _run_input(lbl)
                censor = _censor_path(lbl)
                motion = _motion_prepared_path(lbl)
                tissue_paths = _tissue_paths_for(lbl)

                if config.use_tissue_derivs:
                    for tname, tpath in [("CSF", tissue_paths["CSF"]), ("WM", tissue_paths["WM"]),
                                         ("GS", tissue_paths.get("GS"))]:
                        if tname == "GS" and not tpath:
                            continue
                        drel = names.tissue_deriv(pre, tname, lbl)
                        write_tissue_derivative(tpath, tname, [ri.n_vols], io.path(drel))
                        tissue_paths["derivs"][tname] = io.path(drel)

                out_rel = names.residual_run(pre, lbl)

                if not config.use_sequenced_bandpass:
                    out = _residual_simultaneous(
                        io, config, lbl, run_input, censor, motion,
                        tissue_paths, polort, out_rel, logger,
                    )
                    outputs = [out]
                    for dname, dpath in tissue_paths.get("derivs", {}).items():
                        drel = os.path.relpath(dpath, io.staging)
                        outputs.append(Output(drel, "intermediate", "py_text",
                                              producer=f"{dname} derivative run {lbl}"))
                else:
                    final_out, extra = _residual_sequenced(
                        io, config, lbl, run_input, censor, motion,
                        tissue_paths, out_rel, logger,
                    )
                    outputs = [final_out] + extra
                    for dname, dpath in tissue_paths.get("derivs", {}).items():
                        drel = os.path.relpath(dpath, io.staging)
                        outputs.append(Output(drel, "intermediate", "py_text",
                                              producer=f"{dname} derivative run {lbl}"))

                return Outcome(outputs=outputs, qc={})

            try:
                ctx.run_stage(run_spec, _residual_run_stage)
                s_final_candidates.append(lbl)
            except ToolExecutionError as e:
                graded_warning(
                    logger, "high", "RUN_FAILED",
                    f"Run {lbl}: {e}",
                    user_facing=True,
                )
                ctx.record_stage_failure(label_str, {
                    "failed_runs": [{"run": lbl, "error": str(e)}],
                })
                failed_runs_record.append({"run": lbl, "error": str(e)})

        if not s_final_candidates:
            excluded_for_error = list(nuisance_state["excluded"]) + [
                {"run": r["run"], "reason": "run_failed"} for r in failed_runs_record
            ]
            raise ToolExecutionError(
                f"All runs failed regression; runs excluded: {excluded_for_error}",
                context={"excluded_runs": excluded_for_error},
            )

        runsets.set_s_final(s_final_candidates)
        s_final = runsets.s_final

        concat_spec = StageSpec(
            label="rest-conn-concat",
            fields=("tr", "keep_run_res_dtseries"),
            derived_values={"s_final": list(s_final)},
            upstream=tuple(f"rest-conn-residuals-run{lbl}" for lbl in s_final),
        )

        def _concat_stage(io):
            run_files = [f"{config.out_dir}/{names.residual_run(pre, lbl)}" for lbl in s_final]
            concat_rel = names.residual_concat(pre)
            cmd = ["3dTcat", "-TR", str(config.tr), "-prefix", io.path(concat_rel)] + run_files
            run_afni_command(cmd, description="3dTcat residual concat",
                             logger=logger, cwd=io.staging)
            return Outcome(outputs=[Output(concat_rel, "final", "nifti",
                                           producer="3dTcat residual concat")])

        ctx.run_stage(concat_spec, _concat_stage)

    else:
        # Single ledgered stage: per-run regressions, then 3dTcat concatenation
        all_fields = ("tr", "bandpass", "notch_filter_band", "motion_deriv_degree",
                     "fd_threshold", "censor_prev_tr", "use_tissue_derivs",
                     "use_sequenced_bandpass", "keep_run_res_dtseries")
        derived_files = []
        for lbl in s_pre:
            ri = runsets.run(lbl)
            derived_files.append(f"{config.out_dir}/{names.censor(pre, lbl)}")
            derived_files.append(f"{config.out_dir}/{names.motion_prepared(pre, lbl)}")
            if config.notch_filter_band:
                derived_files.append(f"{config.out_dir}/{names.notch_motion(pre, lbl)}")
            derived_files.extend(_prepared_tissue_files(lbl))

        concat_mode_spec = StageSpec(
            label="rest-conn-residuals-concat",
            fields=all_fields,
            derived_files=derived_files,
            derived_values={
                "s_pre": list(s_pre),
                "per_run": {lbl: nuisance_state["polort"][lbl] for lbl in s_pre},
            },
            upstream=("rest-conn-prep",),
        )

        def _concat_mode_stage(io):
            outputs = []
            successes = []
            failed = []

            for lbl in s_pre:
                ri = runsets.run(lbl)
                subdir = f"run{lbl}"
                os.makedirs(io.path(subdir), exist_ok=True)

                try:
                    run_input = _run_input(lbl)
                    censor = _censor_path(lbl)
                    motion = _motion_prepared_path(lbl)
                    tissue_paths = _tissue_paths_for(lbl)
                    polort = nuisance_state["polort"][lbl]

                    if config.use_tissue_derivs:
                        for tname, tpath in [("CSF", tissue_paths["CSF"]), ("WM", tissue_paths["WM"]),
                                             ("GS", tissue_paths.get("GS"))]:
                            if tname == "GS" and not tpath:
                                continue
                            drel = f"{subdir}/{tname}_deriv.1D"
                            write_tissue_derivative(tpath, tname, [ri.n_vols], io.path(drel))
                            tissue_paths["derivs"][tname] = io.path(drel)

                    # A temporary that only 3dTcat below reads, so uncompressed.
                    out_rel = f"{subdir}/residual.nii"

                    if not config.use_sequenced_bandpass:
                        _residual_simultaneous(
                            io, config, lbl, run_input, censor, motion,
                            tissue_paths, polort, out_rel, logger,
                        )
                    else:
                        _residual_sequenced(
                            io, config, lbl, run_input, censor, motion,
                            tissue_paths, out_rel, logger,
                        )

                    successes.append(lbl)
                except ToolExecutionError as e:
                    graded_warning(
                        logger, "high", "RUN_FAILED",
                        f"Run {lbl}: {e}",
                        user_facing=True,
                    )
                    failed.append({"run": lbl, "error": str(e)})

            if not successes:
                raise ToolExecutionError(
                    f"All runs failed regression inside rest-conn-residuals-concat: "
                    f"{failed}",
                )

            run_files = [io.path(f"run{lbl}/residual.nii") for lbl in successes]
            concat_rel = names.residual_concat(pre)
            cmd = ["3dTcat", "-TR", str(config.tr), "-prefix", io.path(concat_rel)] + run_files
            run_afni_command(cmd, description="3dTcat residual concat",
                             logger=logger, cwd=io.staging)
            outputs.append(Output(concat_rel, "final", "nifti",
                                  producer="3dTcat residual concat"))

            qc = {}
            if failed:
                qc["failed_runs"] = failed

            ctx._concat_mode_successes = successes
            return Outcome(outputs=outputs, qc=qc)

        ctx.run_stage(concat_mode_spec, _concat_mode_stage)

        latest_qc = None
        for label, frag in ctx.fragments:
            if label == "rest-conn-residuals-concat":
                latest_qc = frag
        for f in (latest_qc or {}).get("failed_runs", []):
            failed_runs_record.append({"run": f["run"], "error": f["error"]})
        s_final_labels = getattr(ctx, "_concat_mode_successes", None)
        if s_final_labels is None:
            # Stage was reused; derive from completion record qc
            failed_labels = {f["run"] for f in (latest_qc or {}).get("failed_runs", [])}
            s_final_labels = [lbl for lbl in s_pre if lbl not in failed_labels]
        runsets.set_s_final(s_final_labels)
        s_final = runsets.s_final

    # Ledgered stage: rest-conn-raw-ptseries
    if config.extract_raw_ptseries and template_used:
        raw_spec = StageSpec(
            label="rest-conn-raw-ptseries",
            fields=("extract_raw_ptseries", "extract_out_file_pre", "template_path",
                    "average_type", "roi_zero_handling", "scan_paths",
                    "run_labels", "scale_to_psc"),
            derived_values={"s_final": list(s_final), "template_resolved": template_resolved},
            upstream=("rest-conn-prep", "rest-conn-template"),
        )

        def _raw_ptseries_stage(io):
            outputs = []
            ext = config.extract_out_file_pre
            for lbl in s_final:
                ri = runsets.run(lbl)
                df = roi.extract_roi_stats(
                    ri.source_path, template_resolved, config.average_type,
                    config.roi_zero_handling, logger, cwd=io.staging,
                )
                csv_text = df.to_csv(index=False)
                rel = names.raw_ptseries(ext, lbl)
                with open(io.path(rel), "w", newline="") as f:
                    f.write(csv_text)
                outputs.append(Output(rel, "final", "py_text",
                                      producer=f"raw ptseries run {lbl}",
                                      expected_text=csv_text))

                if config.scale_to_psc:
                    psc_path = f"{config.out_dir}/{names.run_psc(pre, lbl)}"
                    df2 = roi.extract_roi_stats(
                        psc_path, template_resolved, config.average_type,
                        config.roi_zero_handling, logger, cwd=io.staging,
                    )
                    csv2 = df2.to_csv(index=False)
                    rel2 = names.raw_psc_ptseries(ext, lbl)
                    with open(io.path(rel2), "w", newline="") as f:
                        f.write(csv2)
                    outputs.append(Output(rel2, "final", "py_text",
                                          producer=f"raw PSC ptseries run {lbl}",
                                          expected_text=csv2))
            return Outcome(outputs=outputs)

        ctx.run_stage(raw_spec, _raw_ptseries_stage)

    # Ledgered stage: rest-conn-min-outlier-epi
    moe_spec = StageSpec(
        label="rest-conn-min-outlier-epi",
        fields=("scan_paths", "run_labels"),
        derived_values={"s_final": list(s_final)},
    )

    def _moe_stage(io):
        outputs = []
        for lbl in s_final:
            ri = runsets.run(lbl)
            out_rel = names.min_outlier_epi(pre, lbl)
            gen_min_outlier_epi(ri.source_path, ri.start, ri.n_vols,
                                io.path(out_rel), logger, cwd=io.staging)
            outputs.append(Output(out_rel, "final", "nifti",
                                  producer=f"min-outlier EPI run {lbl}",
                                  expected_nvols=1))
        return Outcome(outputs=outputs)

    ctx.run_stage(moe_spec, _moe_stage)

    residual_stage_label = "rest-conn-concat" if config.keep_run_res_dtseries else "rest-conn-residuals-concat"

    # Smoothing branch
    if config.smoothing_enabled:
        token = names.smoothing_token(config.smoothing_fwhm)

        smooth_spec = StageSpec(
            label="rest-conn-smooth-residuals",
            fields=("smoothing_enabled", "smoothing_fwhm", "scan_paths",
                    "run_lengths", "run_labels"),
            derived_values={"s_final": list(s_final)},
            upstream=(residual_stage_label,),
        )

        def _smooth_stage(io):
            outputs = []
            unscaled_specs = [runsets.run(lbl).source_path for lbl in s_final]
            mask_rel = names.smoothing_mask(pre)
            mask_out = smoothing.smoothing_mask(io, unscaled_specs, mask_rel, logger)
            outputs.append(mask_out)
            n_mask, fov = smoothing.mask_stats(io.path(mask_rel), logger)

            offsets = runsets.offsets(s_final)
            concat_path = f"{config.out_dir}/{names.residual_concat(pre)}"
            qc_records = []

            run_rels = []
            for lbl in s_final:
                ri = runsets.run(lbl)
                start = offsets[lbl]
                selector = f"{concat_path}[{start}..{start + ri.n_vols - 1}]"
                out_rel = names.residual_run(pre, lbl, token)
                smoothing.blur(io, selector, io.path(mask_rel),
                               config.smoothing_fwhm, out_rel, logger)
                cls = "final" if config.keep_run_res_dtseries else "intermediate"
                outputs.append(Output(out_rel, cls, "nifti", producer=f"smoothed residual run {lbl}"))
                run_rels.append(io.path(out_rel))

                fin = smoothing.acf_fwhm(io, selector, io.path(mask_rel), False, logger)
                fout = smoothing.acf_fwhm(io, io.path(out_rel), io.path(mask_rel), False, logger)
                qc_records.append(smoothing.qc_record(
                    lbl, config.smoothing_fwhm, fin, fout, n_mask, fov, logger,
                ))

            concat_rel = names.residual_concat(pre, token)
            run_afni_command(
                ["3dTcat", "-TR", str(config.tr), "-prefix", io.path(concat_rel)] + run_rels,
                description="3dTcat smoothed residual concat",
                logger=logger, cwd=io.staging,
            )
            outputs.append(Output(concat_rel, "final", "nifti",
                                  producer="smoothed residual concat"))

            return Outcome(outputs=outputs, qc={"smoothing_per_run": qc_records})

        ctx.run_stage(smooth_spec, _smooth_stage)

    # Ledgered stage: rest-conn-ptseries
    if config.extract_ptseries and template_used:
        ptseries_spec = StageSpec(
            label="rest-conn-ptseries",
            fields=("extract_ptseries", "extract_out_file_pre", "average_type",
                    "roi_zero_handling", "template_path"),
            derived_values={"template_resolved": template_resolved},
            upstream=(residual_stage_label, "rest-conn-template"),
        )

        def _ptseries_stage(io):
            concat_path = f"{config.out_dir}/{names.residual_concat(pre)}"
            df = roi.extract_roi_stats(
                concat_path, template_resolved, config.average_type,
                config.roi_zero_handling, logger, cwd=io.staging,
            )
            csv_text = df.to_csv(index=False)
            rel = names.residual_ptseries(config.extract_out_file_pre)
            with open(io.path(rel), "w", newline="") as f:
                f.write(csv_text)
            return Outcome(outputs=[Output(rel, "final", "py_text",
                                           producer="residual ptseries",
                                           expected_text=csv_text)])

        ctx.run_stage(ptseries_spec, _ptseries_stage)

    # Ledgered stage: rest-conn-connectivity
    if config.calc_conn is not None and config.conn_out_file_pre:
        conn_upstream = [residual_stage_label, "rest-conn-template"]
        if config.smoothing_enabled and config.calc_conn == "seed_to_voxel":
            conn_upstream.append("rest-conn-smooth-residuals")

        conn_spec = StageSpec(
            label="rest-conn-connectivity",
            fields=("calc_conn", "conn_out_file_pre", "pcorr", "fishZ",
                    "template_path", "roi_zero_handling", "average_type"),
            derived_values={"template_resolved": template_resolved},
            upstream=tuple(conn_upstream),
        )

        def _connectivity_stage(io):
            concat_path = f"{config.out_dir}/{names.residual_concat(pre)}"
            conn_pre = config.conn_out_file_pre
            qc_frag = {}

            if config.calc_conn == "parcellated":
                out_rel = names.conn_output(conn_pre, None, config.fishZ,
                                            config.pcorr, config.calc_conn)
                output, frag = connectivity.parcellated(
                    io, concat_path, template_resolved, config.average_type,
                    config.roi_zero_handling, config.fishZ, config.pcorr,
                    out_rel, None, logger,
                )
                qc_frag.update(frag)
                if output is None:
                    raise ModelError(
                        "Parcellated connectivity could not be computed "
                        "(rank-deficient partial correlation)."
                    )
                outputs = [output]
            else:
                out_rel = names.conn_output(conn_pre, None, config.fishZ,
                                            config.pcorr, config.calc_conn)
                output, frag, _ = connectivity.seed_to_voxel(
                    io, concat_path, concat_path, template_resolved,
                    config.average_type, config.roi_zero_handling,
                    config.fishZ, out_rel, None, logger,
                )
                qc_frag.update(frag)
                if output is None:
                    raise ModelError("Seed-to-voxel connectivity: seed is null.")
                outputs = [output]

                if config.smoothing_enabled:
                    token = names.smoothing_token(config.smoothing_fwhm)
                    smoothed_path = f"{config.out_dir}/{names.residual_concat(pre, token)}"
                    out_rel_s = names.conn_output(conn_pre, None, config.fishZ,
                                                  config.pcorr, config.calc_conn, token)
                    # Seed series from the unsmoothed residual; only the
                    # target is smoothed.
                    output_s, frag_s, _ = connectivity.seed_to_voxel(
                        io, concat_path, smoothed_path, template_resolved,
                        config.average_type, config.roi_zero_handling,
                        config.fishZ, out_rel_s, None, logger,
                    )
                    for k, v in frag_s.items():
                        qc_frag.setdefault(k, []).extend(v if isinstance(v, list) else [v])
                    if output_s is not None:
                        outputs.append(output_s)

            return Outcome(outputs=outputs, qc=qc_frag)

        ctx.run_stage(conn_spec, _connectivity_stage)

    # Ledgered stage: rest-conn-roi-qc
    if template_used:
        roiqc_spec = StageSpec(
            label="rest-conn-roi-qc",
            fields=("template_path", "roi_zero_handling", "scan_paths",
                    "run_lengths", "run_labels", "scale_to_psc"),
            derived_values={"s_final": list(s_final), "template_resolved": template_resolved},
            upstream=("rest-conn-template", "rest-conn-prep"),
        )

        def _roiqc_stage(io):
            def unscaled_spec(lbl):
                return runsets.run(lbl).source_path

            def model_series_spec(lbl):
                if config.scale_to_psc:
                    return f"{config.out_dir}/{names.run_psc(pre, lbl)}"
                return runsets.run(lbl).source_path

            def mean_volume(lbl):
                if config.scale_to_psc:
                    return f"{config.out_dir}/{names.run_mean(pre, lbl)}"
                return None

            qc_frag = roi.roi_qc(
                io, config, runsets, list(s_final), template_resolved,
                unscaled_spec, model_series_spec, mean_volume, logger,
            )
            return Outcome(outputs=[], qc=qc_frag)

        ctx.run_stage(roiqc_spec, _roiqc_stage)

    # Final assembly
    excluded_runs = list(nuisance_state["excluded"]) + [
        {"run": r["run"], "reason": "run_failed"} for r in failed_runs_record
    ]
    expected = rest_expected(config, runsets, excluded_runs)

    def _qc_fragment(retired):
        return {
            "analysis_type": "rest_conn",
            "fd_threshold": config.fd_threshold,
            "censor_prev_tr": config.censor_prev_tr,
            "censor_metric": nuisance_mod.CENSOR_METRIC,
            "fd_radius_mm": nuisance_mod.FD_RADIUS_MM,
            "bandpass": config.bandpass,
            "bandpass_backend": "sequenced" if config.use_sequenced_bandpass else "simultaneous",
            "excluded_runs": excluded_runs,
            "reused_stages": ctx.reused,
            "retired_outputs": retired,
            "provenance": versions,
        }

    return ctx.finish(expected=expected, qc_step_fragment=_qc_fragment)
