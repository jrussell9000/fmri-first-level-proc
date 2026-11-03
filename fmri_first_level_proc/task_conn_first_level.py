#!/usr/bin/env python3

# ============================================================================
# TASK-BASED fMRI BETA-SERIES AND CONNECTIVITY ANALYSIS
# 1. Design matrix and beta series via AFNI's 3dDeconvolve (design only) and 3dLSS
# 2. (optional) Extract parcel-level beta series with a provided template
# 3. (optional) Compute functional connectivity (parcellated or seed-to-voxel)
#
# Author: Taylor J. Keding, Ph.D.
# ============================================================================
"""
Task connectivity (beta series) first-level pipeline.

INPUTS
------
Mode A (per-run files): paths.scan_paths, paths.task_timing_paths,
    paths.motion_paths, paths.CSF_paths (optional), paths.WM_paths (optional),
    aligned lists with run_labels.
Mode B (single concatenated file): paths.scan_path, paths.task_timing_path,
    paths.motion_path, paths.CSF_path (optional), paths.WM_path (optional),
    with run_lengths and run_labels describing run boundaries.

Other inputs: cond_beta_labels, hrf_model, custom_hrf, fd_threshold,
censor_prev_tr, include_motion_derivs, use_tissue_derivs, scale_to_psc,
average_type, roi_zero_handling, template_path (global), smoothing
(enabled, fwhm), extraction (extract_pbseries, extract_out_file_pre,
extract_raw_ptseries), connectivity (calc_conn, conn_out_file_pre,
pcorr, fishZ, contrasts).

FINAL OUTPUTS
-------------
{pre}_concat_LSS.nii.gz (frozen primary output)
{pre}_concat_LSS.1d
{pre}_concat_LSS_index.json (3dLSS sub-brick -> trial identity)
{pre}_concat_bseries_{cond}.nii.gz
{pre}_concat_bseries_{cond}_index.json (beta-series sub-brick -> trial identity)
{pre}_concat_bseries_dmat.x1D
{ext}_pbseries_{cond}.csv
Connectivity matrices/maps and contrasts
{ext}_raw_ptseries.csv, {ext}_raw_psc_ptseries.csv
Min-outlier EPI
_s{N}mm smoothed siblings of LSS, bseries, their index JSONs and seed maps
{pre}_qc_summary.json
{pre}_timing_errors.json (written only when onset timing validation fails)

INTERMEDIATE OUTPUTS
---------------------
{pre}_ledger.jsonl, mean/PSC volumes, concat_scan, run_intersect_mask,
resampled template, smoothing mask, smoothed model inputs, onset files
(nuisance and beta), the design-matrix REML_cmd, censor and side files,
prepared motion, tissue prepared/derivative files.

STEP ORDER
----------
Always-run: task-conn-events, task-conn-nuisance, task-conn-onsets.
Ledgered: task-conn-template (if template used), task-conn-prep,
task-conn-design-matrix, task-conn-estimability, task-conn-min-outlier-epi,
task-conn-raw-ptseries (if configured), task-conn-beta-series,
task-conn-pbseries (if configured), task-conn-smooth and
task-conn-beta-series-smooth (if smoothing enabled), task-conn-connectivity
(if configured), task-conn-roi-qc (if template used).
Final: task-conn-qc.
"""

import copy
import json
import os

import numpy as np

from . import names, events, nuisance, estimability, prep, roi, smoothing, connectivity
from .engine import RunContext, StageSpec, Outcome, Output, run_with_status
from .runsets import build_runsets
from .runtime import runtime_check
from .exceptions import GuardError, InputError, ModelError
from .first_level_config import FILENAME_TOKEN_RE
from .first_level_utils import (
    clear_warnings,
    graded_warning,
    setup_logging,
    run_afni_command,
    needs_married_timing,
    hrf_for_durations,
    build_decon_base_command,
    collect_reml_cmds,
    valid_contrast_functions,
    gen_min_outlier_epi,
    log_hrf_model,
    log_nuisance_model,
    sanitize_filename_label,
    write_tissue_derivative,
)


# ---------------------------------------------------------------------------
# Expected-path enumeration
# ---------------------------------------------------------------------------

def task_conn_expected(config, runsets, surviving_conditions, non_beta_conditions,
                       conn_listed=frozenset()):
    """Enumerate every final output and deterministic intermediate for task_conn.

    Connectivity outputs are taken from *conn_listed* (the relpaths the
    task-conn-connectivity stage listed in this invocation), so a condition
    or contrast that produced no output this time is not expected.

    Returns
    -------
    set of str
    """
    pre = config.out_file_pre
    expected = set()
    s_pre = runsets.s_pre
    s_final = runsets.s_final
    k_sup = runsets.k_supplied

    expected.add(names.ledger(pre))
    expected.add(names.qc_summary(pre))
    expected.add(names.lss(pre))
    expected.add(names.lss_1d(pre))
    expected.add(names.bseries_dmat(pre))
    expected.add(names.lss_index(pre))

    for cond in surviving_conditions:
        expected.add(names.bseries(pre, cond))
        expected.add(names.bseries_index(pre, cond))

    for lbl in s_final:
        expected.add(names.min_outlier_epi(pre, None if k_sup == 1 else lbl))

    if config.scale_to_psc:
        for lbl in s_pre:
            expected.add(names.run_mean(pre, None if k_sup == 1 else lbl))
            expected.add(names.run_psc(pre, None if k_sup == 1 else lbl))
        if k_sup > 1:
            expected.add(names.psc_concat(pre))

    if runsets.input_mode == "A" and k_sup > 1:
        expected.add(names.concat_scan(pre))

    if runsets.k_model > 1:
        expected.add(names.run_intersect_mask(pre))

    if config.template_path is not None:
        expected.add(names.template_resampled(pre, config.template_path))

    if config.extract_raw_ptseries and config.extract_out_file_pre:
        ext = config.extract_out_file_pre
        expected.add(names.raw_ptseries(ext, None))
        if config.scale_to_psc:
            expected.add(names.raw_psc_ptseries(ext, None))

    if config.extract_pbseries and config.extract_out_file_pre:
        ext = config.extract_out_file_pre
        for cond in surviving_conditions:
            expected.add(names.pbseries(ext, cond))

    # Onset files (nuisance + beta)
    for cond in non_beta_conditions:
        expected.add(names.onset_file(pre, cond))
    expected.add(names.beta_onsets(pre))

    expected.add(names.censor(pre, None))
    for sf in names.censor_side_files(pre, None):
        expected.add(sf)
    expected.add(names.motion_prepared(pre, None))
    for tissue in ("CSF", "WM"):
        path_attr = f"{tissue}_path" if runsets.input_mode == "B" else f"{tissue}_paths"
        if getattr(config, path_attr, None) is not None:
            expected.add(names.tissue_prepared(pre, tissue))
            if config.use_tissue_derivs:
                expected.add(names.tissue_deriv(pre, tissue, None))

    expected.add(names.estimability_dmat(pre))

    expected.update(conn_listed)

    if config.smoothing_enabled:
        token = names.smoothing_token(config.smoothing_fwhm)
        expected.add(names.smoothing_mask(pre))
        for lbl in s_pre:
            expected.add(names.blurred_run(pre, None if k_sup == 1 else lbl, token))
            if config.scale_to_psc:
                expected.add(names.blurred_psc_run(pre, None if k_sup == 1 else lbl, token))
        if k_sup > 1:
            expected.add(names.blurred_concat(pre, token, config.scale_to_psc))
        expected.add(names.lss(pre, token))
        expected.add(names.lss_index(pre, token))
        for cond in surviving_conditions:
            expected.add(names.bseries(pre, cond, token))
            expected.add(names.bseries_index(pre, cond, token))

    return expected


def _beta_column_order(event_table, beta_cond_order, s_pre):
    """Return (condition, run_label, onset) per trial in beta onset-file order.

    Built from events.onset_rows_labeled, the same source that writes the beta
    onset file, so position k is the k-th -stim_times_IM column and the k-th
    3dLSS sub-brick.
    """
    rows = events.onset_rows_labeled(event_table, beta_cond_order, list(s_pre))
    return [
        (cond, lbl, onset)
        for i, lbl in enumerate(s_pre)
        for (cond, onset, _) in rows[i]
    ]


def _check_lss_count(lss_path, n_expected, logger, cwd):
    """GuardError unless the 3dLSS output has one sub-brick per IM column."""
    nv = int(run_afni_command(
        ["3dinfo", "-nv", lss_path], capture_output=True,
        description="3dinfo -nv 3dLSS output", logger=logger, cwd=cwd,
    ).strip())
    if nv != n_expected:
        raise GuardError(
            f"3dLSS output '{lss_path}' has {nv} sub-bricks but the design "
            f"matrix has {n_expected} beta_stims IM columns; trial-to-sub-brick "
            "mapping would be invalid."
        )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run(config, logger=None):
    """Run the task connectivity (beta series) first-level pipeline.

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
        logger = setup_logging("task_conn_first_level")
    return run_with_status("task_conn", config, logger, _run)


def _run(config, logger, tracker):
    """Pipeline body; see run()."""

    config = copy.copy(config)
    clear_warnings()
    tracker.step = "task-conn-runtime-check"
    versions = runtime_check(logger)
    tracker.versions = versions

    tracker.step = "task-conn-contrast-validation"
    parsed_contrasts = None
    if config.calc_conn is not None and getattr(config, "contrast_functions", None):
        parsed_contrasts = valid_contrast_functions(
            config.contrast_functions, config.contrast_labels,
            config.cond_beta_labels, logger=logger,
        )

    tracker.step = "task-conn-run-sets"
    runsets = build_runsets(config, "task_conn", logger)
    ctx = RunContext(config, "task_conn", logger, versions, runsets.grid_ref, tracker=tracker)
    ctx.start()

    log_hrf_model(config.hrf_model, config.custom_hrf, logger)
    log_nuisance_model(config.CSF_path, config.WM_path, logger, config.use_tissue_derivs)

    pre = config.out_file_pre

    # Template checks
    template_used = config.template_path is not None and (
        (config.extract_pbseries and config.extract_out_file_pre)
        or config.extract_raw_ptseries
        or (config.calc_conn is not None)
    )
    conn_types = set()
    if config.extract_pbseries or config.extract_raw_ptseries:
        conn_types.add("extract")
    if config.calc_conn:
        conn_types.add(config.calc_conn)
    same_grid = None
    if template_used:
        tracker.step = "task-conn-template-check"
        same_grid = roi.check_template(
            config.template_path, runsets.grid_ref, config.force_diff_atlas,
            conn_types, logger,
        )

    # Step: task-conn-events (all conditions in the events files)
    def _events_step(io):
        event_table, check = events.build_event_table(
            config, runsets, config.cond_beta_labels,
        )
        if check.violations:
            record = events.timing_record("task_conn", runsets.input_mode, config.tr, check)
            text = json.dumps(record, indent=2) + "\n"
            rel = names.timing_errors(pre)
            with open(io.path(rel), "w", newline="") as f:
                f.write(text)
            msg = events.timing_error_message(record, rel)
            return Outcome(
                outputs=[Output(rel, "final", "py_text",
                               producer="timing error record",
                               expected_text=text)],
                deferred_error=InputError(msg, context=record),
            )
        ctx._event_table = event_table
        return Outcome(outputs=[])

    ctx.run_step("task-conn-events", _events_step)
    event_table = ctx._event_table

    # Step: task-conn-nuisance
    def _nuisance_step(io):
        outcome, state = nuisance.task_nuisance(io, config, runsets, logger)
        ctx._nuisance_state = state
        return outcome

    ctx.run_step("task-conn-nuisance", _nuisance_step)
    nuisance_state = ctx._nuisance_state
    s_pre = runsets.s_pre

    # Determine beta_cond_order: by first appearance (run acquisition order, onset)
    beta_df = event_table.for_runs(s_pre).df
    beta_mask = beta_df["condition"].isin(config.cond_beta_labels)
    beta_only = beta_df[beta_mask].sort_values(["run", "onset"])
    seen = []
    for cond in beta_only["condition"]:
        if cond not in seen:
            seen.append(cond)
    beta_cond_order = seen if seen else list(config.cond_beta_labels)

    model_conditions = event_table.for_runs(list(s_pre)).conditions()
    non_beta_conditions = sorted(
        c for c in model_conditions
        if c not in set(config.cond_beta_labels)
    )
    # Nuisance conditions name their onset files, so they must be file-name safe
    unsafe = [c for c in non_beta_conditions if not FILENAME_TOKEN_RE.match(c)]
    if unsafe:
        raise InputError(
            f"Events condition(s) {unsafe} cannot be modeled as nuisance regressors: "
            "nuisance conditions are written to onset files named by condition, so "
            "names must use letters, digits, '.', '_' or '-' and start with a letter "
            f"or digit. Rename them in the events files: "
            f"{sorted(set(event_table.for_runs(list(s_pre)).df['events_file']))}."
        )
    dropped_nuisance = sorted(
        c for c in event_table.conditions()
        if c not in set(config.cond_beta_labels) and c not in model_conditions
    )
    if dropped_nuisance:
        logger.warning(
            "Nuisance condition(s) %s occur only in runs excluded before "
            "modeling (%s); not modeled.",
            dropped_nuisance,
            sorted(set(runsets.supplied) - set(s_pre)),
        )

    # Step: task-conn-onsets
    def _onsets_step(io):
        outputs = []
        married = needs_married_timing(config.hrf_model, config.custom_hrf)

        for cond in non_beta_conditions:
            rows = events.onset_rows(event_table, [cond], list(s_pre))
            text = events.onset_file_text(rows, married)
            rel = names.onset_file(pre, cond)
            with open(io.path(rel), "w", newline="") as f:
                f.write(text)
            outputs.append(Output(rel, "intermediate", "py_text",
                                  producer="nuisance onset file", expected_text=text))

        beta_rows = events.onset_rows(event_table, beta_cond_order, list(s_pre))
        beta_text = events.onset_file_text(beta_rows, married)
        beta_rel = names.beta_onsets(pre)
        with open(io.path(beta_rel), "w", newline="") as f:
            f.write(beta_text)
        outputs.append(Output(beta_rel, "intermediate", "py_text",
                              producer="beta onset file", expected_text=beta_text))

        ctx._beta_cond_order = beta_cond_order
        return Outcome(outputs=outputs)

    ctx.run_step("task-conn-onsets", _onsets_step)

    # Ledgered stage: task-conn-template
    template_resolved = config.template_path
    if template_used:
        template_resolved = roi.template_stage(
            ctx, config, runsets, pre, same_grid, "task-conn", logger,
        )

    # Ledgered stage: task-conn-prep
    prep_spec = StageSpec(
        label="task-conn-prep",
        fields=("scan_path", "scan_paths", "run_lengths", "run_labels", "scale_to_psc"),
        derived_values={"s_pre": list(s_pre)},
    )

    def _prep_stage(io):
        return prep.task_prep(io, config, runsets, logger)

    ctx.run_stage(prep_spec, _prep_stage)

    # Ledgered stage: task-conn-design-matrix
    design_matrix_files = (
        [f"{config.out_dir}/{names.censor(pre, None)}",
         f"{config.out_dir}/{nuisance_state['motion_rel']}"]
        + [f"{config.out_dir}/{names.onset_file(pre, c)}" for c in non_beta_conditions]
        + [f"{config.out_dir}/{names.beta_onsets(pre)}"]
        + [f"{config.out_dir}/{nuisance_state['tissue_rel'][t]}"
           for t in ("CSF", "WM") if t in nuisance_state["tissue_rel"]]
    )

    design_spec = StageSpec(
        label="task-conn-design-matrix",
        fields=("scan_path", "scan_paths", "run_lengths", "run_labels", "tr",
                "hrf_model", "custom_hrf", "cond_beta_labels", "task_timing_path",
                "task_timing_paths", "motion_path", "motion_paths",
                "include_motion_derivs", "fd_threshold", "censor_prev_tr",
                "CSF_path", "CSF_paths", "WM_path", "WM_paths", "use_tissue_derivs"),
        derived_files=tuple(design_matrix_files),
        derived_values={"s_pre": list(s_pre), "beta_cond_order": beta_cond_order},
        upstream=("task-conn-prep",),
    )

    def _design_matrix_stage(io):
        model_input = prep.task_model_input(config, runsets, config.out_dir)
        mask_path = prep.task_mask_path(config, runsets, config.out_dir)
        censor_path = f"{config.out_dir}/{names.censor(pre, None)}"
        motion_path = f"{config.out_dir}/{nuisance_state['motion_rel']}"

        ortvecs = []
        outputs = []
        tissue_rel = nuisance_state["tissue_rel"]
        for tissue in ("CSF", "WM"):
            if tissue in tissue_rel:
                tissue_path = f"{config.out_dir}/{tissue_rel[tissue]}"
                ortvecs.append((tissue_path, f"{tissue}_regressor"))
                if config.use_tissue_derivs:
                    deriv_rel = names.tissue_deriv(pre, tissue, None)
                    deriv_text = write_tissue_derivative(
                        tissue_path, tissue, runsets.run_lengths(s_pre), io.path(deriv_rel),
                    )
                    outputs.append(Output(deriv_rel, "intermediate", "py_text",
                                          producer=f"{tissue} derivative",
                                          expected_text=deriv_text))
                    ortvecs.append((io.path(deriv_rel), f"{tissue}_deriv_regressor"))

        cmd = build_decon_base_command(
            model_input, censor_path, motion_path, ortvecs,
            runsets.run_starts(s_pre), mask_path, config.tr,
        )

        n_nuisance = len(non_beta_conditions)
        cmd.extend(["-num_stimts", str(n_nuisance + 1)])

        run_df = event_table.for_runs(s_pre).df
        married = needs_married_timing(config.hrf_model, config.custom_hrf)
        stim_flag = "-stim_times_AM1" if married else "-stim_times"
        for k, cond in enumerate(non_beta_conditions, 1):
            onset_path = f"{config.out_dir}/{names.onset_file(pre, cond)}"
            hrf = hrf_for_durations(
                config.hrf_model, config.custom_hrf,
                run_df.loc[run_df["condition"] == cond, "duration"],
            )
            cmd.extend([stim_flag, str(k), onset_path, hrf, "-stim_label", str(k), cond])

        beta_onsets_path = f"{config.out_dir}/{names.beta_onsets(pre)}"
        beta_hrf = hrf_for_durations(config.hrf_model, config.custom_hrf, beta_only["duration"])
        k_beta = n_nuisance + 1
        cmd.extend([
            "-stim_times_IM", str(k_beta), beta_onsets_path, beta_hrf,
            "-stim_label", str(k_beta), "beta_stims",
        ])

        dmat_rel = names.bseries_dmat(pre)
        cmd.extend([
            "-x1D", io.path(dmat_rel),
            "-x1D_stop", "-nobucket", "-jobs", str(config.num_cores),
        ])

        run_afni_command(cmd, description="3dDeconvolve design matrix",
                         logger=logger, cwd=io.staging)

        reml = collect_reml_cmds(io.staging, pre, "task-conn-design-matrix")
        outputs.append(Output(dmat_rel, "final", "x1d", producer="design matrix"))
        for rel, kind in reml:
            outputs.append(Output(rel, "intermediate", kind, producer="REML_cmd"))

        return Outcome(outputs=outputs)

    ctx.run_stage(design_spec, _design_matrix_stage)

    # Step: task-conn-estimability
    def _estimability_step(io):
        dmat_path = f"{config.out_dir}/{names.bseries_dmat(pre)}"
        dof = estimability.task_conn_lss_dof(dmat_path)

        beta_hrf = hrf_for_durations(config.hrf_model, config.custom_hrf, beta_only["duration"])
        onset_specs = [("beta_stims",
                        f"{config.out_dir}/{names.beta_onsets(pre)}",
                        beta_hrf)]

        matrix, header = estimability.estimability_dry_run(
            io, config, runsets, onset_specs, logger,
        )

        censor_path = f"{config.out_dir}/{names.censor(pre, None)}"
        censor_vec = np.loadtxt(censor_path, dtype=int).ravel()

        cols = estimability.im_columns(header, "beta_stims")

        # Trial list in beta onset-file order (same source as the file itself);
        # a trial's position here is its global IM column / 3dLSS sub-brick index.
        all_column_order = _beta_column_order(event_table, beta_cond_order, s_pre)
        fvals = estimability.trial_estimability(
            matrix, cols, censor_vec, len(all_column_order),
        )
        estimability.check_im_order(
            matrix, cols, all_column_order, ctx.versions.get("afni_version"),
        )
        ctx._beta_column_order = all_column_order

        trials = estimability.build_trials(
            event_table, beta_cond_order, s_pre, runsets.supplied,
            all_column_order, fvals, "task_conn",
        )
        trial_counts, surviving, run_counts = estimability.survival_summary(
            trials, beta_cond_order,
        )
        kept_conditions, kept_contrasts, kept_labels, _ = estimability.apply_floor(
            "task_conn", beta_cond_order, surviving,
            parsed_contrasts, config.contrast_labels, logger,
        )
        config.cond_beta_labels = kept_conditions
        config.contrast_labels = kept_labels
        ctx._kept_contrasts = kept_contrasts
        ctx._surviving_trials = trials

        reml = collect_reml_cmds(io.staging, pre, "task-conn-estimability")
        outputs = [Output(names.estimability_dmat(pre), "intermediate", "x1d",
                          producer="estimability dry run")]
        for rel, kind in reml:
            outputs.append(Output(rel, "intermediate", kind, producer="REML_cmd"))

        qc_frag = {
            "dof": dof,
            "trials": trials,
            "per_condition_trial_counts": trial_counts,
            "per_condition_surviving_trials": surviving,
            "per_condition_run_counts": run_counts,
        }
        return Outcome(outputs=outputs, qc=qc_frag)

    ctx.run_step("task-conn-estimability", _estimability_step)
    surviving_conditions = config.cond_beta_labels
    trials_list = ctx._surviving_trials

    runsets.set_s_final(s_pre)
    s_final = runsets.s_final

    # Ledgered stage: task-conn-min-outlier-epi
    moe_spec = StageSpec(
        label="task-conn-min-outlier-epi",
        fields=("scan_path", "scan_paths", "run_lengths", "run_labels"),
        derived_values={"s_final": list(s_final)},
    )

    def _moe_stage(io):
        outputs = []
        for lbl in s_final:
            ri = runsets.run(lbl)
            out_rel = names.min_outlier_epi(pre, None if runsets.k_supplied == 1 else lbl)
            gen_min_outlier_epi(ri.source_path, ri.start, ri.n_vols,
                                io.path(out_rel), logger, cwd=io.staging)
            outputs.append(Output(out_rel, "final", "nifti",
                                  producer="min-outlier EPI", expected_nvols=1))
        return Outcome(outputs=outputs)

    ctx.run_stage(moe_spec, _moe_stage)

    # Ledgered stage: task-conn-raw-ptseries
    if config.extract_raw_ptseries and template_used:
        raw_spec = StageSpec(
            label="task-conn-raw-ptseries",
            fields=("extract_raw_ptseries", "extract_out_file_pre", "template_path",
                    "average_type", "roi_zero_handling", "scan_path", "scan_paths",
                    "run_labels", "scale_to_psc"),
            derived_values={"s_pre": list(s_pre), "template_resolved": template_resolved},
            upstream=("task-conn-prep", "task-conn-template"),
        )

        def _raw_ptseries_stage(io):
            return prep.task_raw_ptseries(io, config, runsets, template_resolved, logger)

        ctx.run_stage(raw_spec, _raw_ptseries_stage)

    # Ledgered stage: task-conn-beta-series
    # Global 3dLSS sub-brick indices of each surviving condition's surviving
    # trials; the k-th index is the trial with beta_series_position k.
    beta_sel = estimability.beta_selection(trials_list, ctx._beta_column_order)
    beta_sel = {cond: beta_sel.get(cond, []) for cond in surviving_conditions}
    n_im_columns = len(ctx._beta_column_order)

    beta_series_spec = StageSpec(
        label="task-conn-beta-series",
        fields=("cond_beta_labels", "scan_path", "scan_paths", "run_labels"),
        derived_values={
            "s_pre": list(s_pre),
            "survival": beta_sel,
        },
        upstream=("task-conn-design-matrix",),
    )

    def _beta_series_stage(io):
        model_input = prep.task_model_input(config, runsets, config.out_dir)
        mask_path = prep.task_mask_path(config, runsets, config.out_dir)
        dmat_path = f"{config.out_dir}/{names.bseries_dmat(pre)}"

        lss_rel = names.lss(pre)
        lss_1d_rel = names.lss_1d(pre)

        cmd = ["3dLSS", "-matrix", dmat_path, "-input", model_input]
        if mask_path:
            cmd.extend(["-mask", mask_path])
        cmd.extend(["-save1D", io.path(lss_1d_rel), "-prefix", io.path(lss_rel)])

        run_afni_command(cmd, description="3dLSS beta series",
                         logger=logger, cwd=io.staging)

        outputs = [
            Output(lss_rel, "final", "nifti", producer="3dLSS"),
            Output(lss_1d_rel, "final", "afni_aux", producer="3dLSS 1D save"),
        ]

        _, header = estimability.parse_x1d(dmat_path)
        im_cols = estimability.im_columns(header, "beta_stims")
        if len(im_cols) != n_im_columns:
            raise GuardError(
                f"Design matrix has {len(im_cols)} beta_stims IM columns but the "
                f"beta onset file has {n_im_columns} trials."
            )
        _check_lss_count(io.path(lss_rel), len(im_cols), logger, io.staging)

        by_lss = {t["lss_index"]: t for t in trials_list if t.get("lss_index") is not None}
        lss_index_obj = [
            {
                "lss_index": i,
                "condition": by_lss[i]["condition"],
                "run": by_lss[i]["run"],
                "onset": by_lss[i]["onset"],
                "survived": by_lss[i]["survived"],
                "beta_series_position": by_lss[i]["beta_series_position"],
            }
            for i in range(len(ctx._beta_column_order))
        ]
        lss_index_text = json.dumps(lss_index_obj, indent=2) + "\n"
        lss_index_rel = names.lss_index(pre)
        with open(io.path(lss_index_rel), "w", newline="") as f:
            f.write(lss_index_text)
        outputs.append(Output(lss_index_rel, "final", "py_text",
                              producer="LSS index", expected_text=lss_index_text))

        for cond in surviving_conditions:
            indices = beta_sel[cond]
            if not indices:
                continue
            idx_str = ",".join(str(i) for i in indices)
            bseries_rel = names.bseries(pre, cond)
            run_afni_command(
                ["3dcalc", "-a", f"{io.path(lss_rel)}[{idx_str}]",
                 "-expr", "a", "-prefix", io.path(bseries_rel)],
                description=f"3dcalc extract beta series {cond}",
                logger=logger, cwd=io.staging,
            )

            # Non-finite check
            dminmax = run_afni_command(
                ["3dinfo", "-dmin", "-dmax", io.path(bseries_rel)],
                capture_output=True,
                description=f"3dinfo dmin/dmax {cond}",
                logger=logger, cwd=io.staging,
            )
            try:
                # 3dinfo -dmin -dmax terminates each value with a literal
                # '|' separator; strip it before parsing as float.
                vals = [float(v.rstrip("|")) for v in dminmax.split()]
                if any(not np.isfinite(v) for v in vals):
                    raise GuardError(
                        f"Beta series for condition '{cond}' contains "
                        f"non-finite values: {vals}"
                    )
            except ValueError:
                raise GuardError(
                    f"Could not parse dmin/dmax for beta series '{cond}': "
                    f"'{dminmax}'"
                )

            outputs.append(Output(bseries_rel, "final", "nifti",
                                  producer=f"beta series {cond}"))

            bseries_index_obj = [
                {
                    "beta_series_position": k,
                    "lss_index": idx,
                    "run": by_lss[idx]["run"],
                    "onset": by_lss[idx]["onset"],
                }
                for k, idx in enumerate(indices)
            ]
            bseries_index_text = json.dumps(bseries_index_obj, indent=2) + "\n"
            bseries_index_rel = names.bseries_index(pre, cond)
            with open(io.path(bseries_index_rel), "w", newline="") as f:
                f.write(bseries_index_text)
            outputs.append(Output(bseries_index_rel, "final", "py_text",
                                  producer=f"beta series {cond} index",
                                  expected_text=bseries_index_text))

        return Outcome(outputs=outputs)

    ctx.run_stage(beta_series_spec, _beta_series_stage)

    # Ledgered stage: task-conn-pbseries
    if config.extract_pbseries and template_used:
        pbseries_spec = StageSpec(
            label="task-conn-pbseries",
            fields=("extract_pbseries", "extract_out_file_pre", "average_type",
                    "roi_zero_handling", "template_path"),
            derived_values={"template_resolved": template_resolved,
                           "conditions": list(surviving_conditions)},
            upstream=("task-conn-beta-series", "task-conn-template"),
        )

        def _pbseries_stage(io):
            outputs = []
            ext = config.extract_out_file_pre
            for cond in surviving_conditions:
                bseries_path = f"{config.out_dir}/{names.bseries(pre, cond)}"
                if not os.path.exists(bseries_path):
                    continue
                df = roi.extract_roi_stats(
                    bseries_path, template_resolved, config.average_type,
                    config.roi_zero_handling, logger, cwd=io.staging,
                )
                csv_text = df.to_csv(index=False)
                rel = names.pbseries(ext, cond)
                with open(io.path(rel), "w", newline="") as f:
                    f.write(csv_text)
                outputs.append(Output(rel, "final", "py_text",
                                      producer=f"parcel beta series {cond}",
                                      expected_text=csv_text))
            return Outcome(outputs=outputs)

        ctx.run_stage(pbseries_spec, _pbseries_stage)

    # Smoothing branch
    if config.smoothing_enabled:
        token = names.smoothing_token(config.smoothing_fwhm)

        smooth_spec = StageSpec(
            label="task-conn-smooth",
            fields=("smoothing_enabled", "smoothing_fwhm", "scan_path", "scan_paths",
                    "run_lengths", "run_labels", "scale_to_psc"),
            derived_values={"s_pre": list(s_pre)},
            upstream=("task-conn-prep",),
        )

        def _smooth_stage(io):
            return smoothing.task_smooth(io, config, runsets, s_pre, pre, token, logger)

        ctx.run_stage(smooth_spec, _smooth_stage)

        beta_smooth_spec = StageSpec(
            label="task-conn-beta-series-smooth",
            fields=beta_series_spec.fields + ("smoothing_enabled", "smoothing_fwhm"),
            derived_values=beta_series_spec.derived_values,
            upstream=("task-conn-smooth", "task-conn-design-matrix"),
        )

        def _beta_series_smooth_stage(io):
            model_input = prep.task_model_input(config, runsets, config.out_dir, token)
            mask_path = prep.task_mask_path(config, runsets, config.out_dir)
            dmat_path = f"{config.out_dir}/{names.bseries_dmat(pre)}"

            lss_rel = names.lss(pre, token)
            cmd = ["3dLSS", "-matrix", dmat_path, "-input", model_input]
            if mask_path:
                cmd.extend(["-mask", mask_path])
            cmd.extend(["-prefix", io.path(lss_rel)])
            run_afni_command(cmd, description="3dLSS smoothed beta series",
                             logger=logger, cwd=io.staging)

            outputs = [Output(lss_rel, "final", "nifti", producer="smoothed 3dLSS")]
            _check_lss_count(io.path(lss_rel), n_im_columns, logger, io.staging)

            by_lss = {t["lss_index"]: t for t in trials_list if t.get("lss_index") is not None}
            lss_index_obj = [
                {
                    "lss_index": i,
                    "condition": by_lss[i]["condition"],
                    "run": by_lss[i]["run"],
                    "onset": by_lss[i]["onset"],
                    "survived": by_lss[i]["survived"],
                    "beta_series_position": by_lss[i]["beta_series_position"],
                }
                for i in range(len(ctx._beta_column_order))
            ]
            lss_index_text = json.dumps(lss_index_obj, indent=2) + "\n"
            lss_index_rel = names.lss_index(pre, token)
            with open(io.path(lss_index_rel), "w", newline="") as f:
                f.write(lss_index_text)
            outputs.append(Output(lss_index_rel, "final", "py_text",
                                  producer="LSS index", expected_text=lss_index_text))

            for cond in surviving_conditions:
                indices = beta_sel[cond]
                if not indices:
                    continue
                idx_str = ",".join(str(i) for i in indices)
                bseries_rel = names.bseries(pre, cond, token)
                run_afni_command(
                    ["3dcalc", "-a", f"{io.path(lss_rel)}[{idx_str}]",
                     "-expr", "a", "-prefix", io.path(bseries_rel)],
                    description=f"3dcalc smoothed beta series {cond}",
                    logger=logger, cwd=io.staging,
                )
                outputs.append(Output(bseries_rel, "final", "nifti",
                                      producer=f"smoothed beta series {cond}"))

                bseries_index_obj = [
                    {
                        "beta_series_position": k,
                        "lss_index": idx,
                        "run": by_lss[idx]["run"],
                        "onset": by_lss[idx]["onset"],
                    }
                    for k, idx in enumerate(indices)
                ]
                bseries_index_text = json.dumps(bseries_index_obj, indent=2) + "\n"
                bseries_index_rel = names.bseries_index(pre, cond, token)
                with open(io.path(bseries_index_rel), "w", newline="") as f:
                    f.write(bseries_index_text)
                outputs.append(Output(bseries_index_rel, "final", "py_text",
                                      producer=f"smoothed beta series {cond} index",
                                      expected_text=bseries_index_text))

            return Outcome(outputs=outputs)

        ctx.run_stage(beta_smooth_spec, _beta_series_smooth_stage)

    # Ledgered stage: task-conn-connectivity
    if config.calc_conn is not None and config.conn_out_file_pre:
        conn_upstream = ["task-conn-beta-series"]
        if template_used:
            conn_upstream.append("task-conn-template")
        if config.smoothing_enabled and config.calc_conn == "seed_to_voxel":
            conn_upstream.append("task-conn-beta-series-smooth")

        conn_spec = StageSpec(
            label="task-conn-connectivity",
            fields=("calc_conn", "conn_out_file_pre", "pcorr", "fishZ",
                    "template_path", "roi_zero_handling", "contrast_functions",
                    "contrast_labels", "average_type"),
            derived_values={"template_resolved": template_resolved,
                           "conditions": list(surviving_conditions)},
            upstream=tuple(conn_upstream),
        )

        def _connectivity_stage(io):
            outputs = []
            qc_frag = {}
            conn_pre = config.conn_out_file_pre
            produced_conditions = []
            produced_paths = {}
            produced_paths_smoothed = {}
            token = (names.smoothing_token(config.smoothing_fwhm)
                     if config.smoothing_enabled else "")

            for cond in surviving_conditions:
                bseries_path = f"{config.out_dir}/{names.bseries(pre, cond)}"
                if not os.path.exists(bseries_path):
                    continue

                if config.calc_conn == "parcellated":
                    out_rel = names.conn_output(conn_pre, cond, config.fishZ,
                                                config.pcorr, config.calc_conn)
                    output, frag = connectivity.parcellated(
                        io, bseries_path, template_resolved, config.average_type,
                        config.roi_zero_handling, config.fishZ, config.pcorr,
                        out_rel, cond, logger,
                    )
                    for k, v in frag.items():
                        qc_frag.setdefault(k, []).extend(v if isinstance(v, list) else [v])
                    if output is not None:
                        outputs.append(output)
                        produced_conditions.append(cond)
                        produced_paths[cond] = io.path(out_rel)
                else:
                    out_rel = names.conn_output(conn_pre, cond, config.fishZ,
                                                config.pcorr, config.calc_conn)
                    output, frag, is_null = connectivity.seed_to_voxel(
                        io, bseries_path, bseries_path, template_resolved,
                        config.average_type, config.roi_zero_handling,
                        config.fishZ, out_rel, cond, logger,
                    )
                    for k, v in frag.items():
                        qc_frag.setdefault(k, []).extend(v if isinstance(v, list) else [v])
                    if output is not None:
                        outputs.append(output)
                        produced_conditions.append(cond)
                        produced_paths[cond] = io.path(out_rel)

                    if config.smoothing_enabled and not is_null:
                        # Seed series from the unsmoothed beta series; only the
                        # target is smoothed.
                        smoothed_bseries = f"{config.out_dir}/{names.bseries(pre, cond, token)}"
                        out_rel_s = names.conn_output(
                            conn_pre, cond, config.fishZ, config.pcorr,
                            config.calc_conn, token,
                        )
                        output_s, frag_s, _ = connectivity.seed_to_voxel(
                            io, bseries_path, smoothed_bseries, template_resolved,
                            config.average_type, config.roi_zero_handling,
                            config.fishZ, out_rel_s, cond, logger,
                        )
                        for k, v in frag_s.items():
                            qc_frag.setdefault(k, []).extend(v if isinstance(v, list) else [v])
                        if output_s is not None:
                            outputs.append(output_s)
                            produced_paths_smoothed[cond] = io.path(out_rel_s)

            if not produced_conditions:
                raise ModelError(
                    "No condition yielded a connectivity output "
                    "(all conditions were null or rank-deficient)."
                )

            kept_contrasts = getattr(ctx, "_kept_contrasts", None)
            if kept_contrasts and config.contrast_labels:
                for contrast, label in zip(kept_contrasts, config.contrast_labels):
                    conds_in_contrast = contrast["CONDS"]
                    missing = [c for c in conds_in_contrast if c not in produced_conditions]
                    if missing:
                        graded_warning(
                            logger, "medium", "CONTRAST_DROPPED",
                            f"Connectivity contrast '{label}' skipped: condition(s) "
                            f"{sorted(set(missing))} produced no connectivity output.",
                            user_facing=True,
                        )
                        continue
                    coefs = [float(c) for c in contrast["COEFS"]]
                    safe_label = sanitize_filename_label(label)

                    if config.calc_conn == "parcellated":
                        paths = [produced_paths[c] for c in conds_in_contrast]
                        out_rel = names.conn_output(conn_pre, safe_label, config.fishZ,
                                                    config.pcorr, config.calc_conn)
                        output = connectivity.matrix_contrast(paths, coefs, out_rel, io)
                        outputs.append(output)
                    else:
                        paths = [produced_paths[c] for c in conds_in_contrast]
                        out_rel = names.conn_output(conn_pre, safe_label, config.fishZ,
                                                    config.pcorr, config.calc_conn)
                        output = connectivity.seed_contrast(
                            io, paths, coefs, out_rel, label, logger,
                        )
                        outputs.append(output)

                        # Smoothed sibling over the smoothed condition maps.
                        if config.smoothing_enabled and all(
                            c in produced_paths_smoothed for c in conds_in_contrast
                        ):
                            paths_s = [produced_paths_smoothed[c] for c in conds_in_contrast]
                            out_rel_s = names.conn_output(
                                conn_pre, safe_label, config.fishZ,
                                config.pcorr, config.calc_conn, token,
                            )
                            output_s = connectivity.seed_contrast(
                                io, paths_s, coefs, out_rel_s, label, logger,
                            )
                            outputs.append(output_s)

            return Outcome(outputs=outputs, qc=qc_frag)

        ctx.run_stage(conn_spec, _connectivity_stage)

    # Ledgered stage: task-conn-roi-qc
    if template_used:
        roiqc_spec = StageSpec(
            label="task-conn-roi-qc",
            fields=("template_path", "roi_zero_handling", "scan_path", "scan_paths",
                    "run_lengths", "run_labels", "scale_to_psc"),
            derived_values={"s_pre": list(s_pre), "template_resolved": template_resolved},
            upstream=("task-conn-template", "task-conn-prep"),
        )

        def _roiqc_stage(io):
            return roi.task_roi_qc(io, config, runsets, s_pre, template_resolved, pre, logger)

        ctx.run_stage(roiqc_spec, _roiqc_stage)

    # Final assembly
    conn_listed = frozenset(
        o.path for o in ctx.stage_outputs.get("task-conn-connectivity", [])
    )
    expected = task_conn_expected(config, runsets, surviving_conditions, non_beta_conditions,
                                  conn_listed)
    produced_contrast_labels = [
        label for label in (config.contrast_labels or [])
        if config.conn_out_file_pre and names.conn_output(
            config.conn_out_file_pre, sanitize_filename_label(label),
            config.fishZ, config.pcorr, config.calc_conn) in conn_listed
    ]

    def _qc_fragment(retired):
        frag = {
            "analysis_type": "task_conn",
            "hrf_model": config.hrf_model if config.hrf_model != "custom"
                        else f"custom ({config.custom_hrf})",
            "fd_threshold": config.fd_threshold,
            "censor_prev_tr": config.censor_prev_tr,
            "censor_metric": nuisance.CENSOR_METRIC,
            "fd_radius_mm": nuisance.FD_RADIUS_MM,
            "excluded_runs": nuisance_state["excluded"],
            "reused_stages": ctx.reused,
            "retired_outputs": retired,
            "provenance": versions,
        }
        if produced_contrast_labels:
            frag["contrast_labels"] = produced_contrast_labels
        return frag

    return ctx.finish(expected=expected, qc_step_fragment=_qc_fragment)
