#!/usr/bin/env python3

# ============================================================================
# TASK-BASED fMRI ACTIVATION ANALYSIS
# 1. First-level regression statistical dataset (including denoising and censoring) with AFNI's 3dDeconvolve
# 2. (optional) Creates condition/contrast- and stat-specific datasets with AFNI's 3dcalc
# 3. (optional) Extract parcel-level/ROI activation with a provided template with AFNI's 3dROIstats
#
# Author: Taylor J. Keding, Ph.D.
# ============================================================================
"""
Task activation first-level pipeline.

INPUTS
------
Mode A (per-run files): paths.scan_paths, paths.task_timing_paths,
    paths.motion_paths, paths.CSF_paths (optional), paths.WM_paths (optional),
    aligned lists with run_labels.
Mode B (single concatenated file): paths.scan_path, paths.task_timing_path,
    paths.motion_path, paths.CSF_path (optional), paths.WM_path (optional),
    with run_lengths and run_labels describing run boundaries.

Other inputs: cond_labels, hrf_model, custom_hrf, fd_threshold, censor_prev_tr,
include_motion_derivs, use_tissue_derivs, scale_to_psc, average_type,
roi_zero_handling, template_path (global), smoothing (enabled, fwhm),
contrasts (functions, labels), extraction (stat_buckets, extract_out_file_pre,
extract_resids, extract_raw_ptseries).

FINAL OUTPUTS
-------------
{pre}_concat_bucket_stats.nii.gz (frozen primary output)
{pre}_concat_bucket_resids.nii.gz
{pre}_concat_bucket_stats_index.json
{ext}_{stat}_bucket.nii.gz, {ext}_{stat}_index.json (sub-brick key is its exact
    3dinfo -label label, mapped to its 0-based position in the extracted
    bucket; a Zstat bucket reuses the matching Tstat label with "Zstat" in
    place of "Tstat"), {ext}_{stat}_parcellated.csv (same keys as row labels)
{ext}_resids.csv
{ext}_raw_ptseries.csv, {ext}_raw_psc_ptseries.csv
Min-outlier EPI (single or per-run labeled name)
_s{N}mm smoothed siblings of the bucket stats, residuals and each stat bucket
{pre}_qc_summary.json
{pre}_timing_errors.json (written only when onset timing validation fails)

INTERMEDIATE OUTPUTS
---------------------
{pre}_ledger.jsonl, mean/PSC volumes, concat_scan, run_intersect_mask,
resampled template, smoothing mask, smoothed model inputs, onset files,
preflight and estimability design matrices, REML_cmd files, censor and
side files, prepared motion, tissue prepared/derivative files.

STEP ORDER
----------
Always-run: task-act-events, task-act-nuisance, task-act-estimability,
task-act-onsets, task-act-preflight.
Ledgered: task-act-template (if template used), task-act-prep,
task-act-min-outlier-epi, task-act-raw-ptseries (if configured),
task-act-glm, task-act-extract (if configured), task-act-smooth and
task-act-glm-smooth (if smoothing enabled), task-act-roi-qc (if template used).
Final: task-act-qc.
"""

import copy
import json

import numpy as np
import pandas as pd

from . import names, events, nuisance, estimability, prep, roi, smoothing
from .engine import RunContext, StageSpec, Outcome, Output, run_with_status
from .runsets import build_runsets
from .runtime import runtime_check
from .exceptions import GuardError, InputError, ToolExecutionError
from .first_level_utils import (
    clear_warnings,
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
)


# ---------------------------------------------------------------------------
# Sub-brick statistics helper
# ---------------------------------------------------------------------------

def _get_stataux(bucket_path, logger=None):
    """Get the statistical auxiliary parameters (e.g. DOF) for every
    sub-brick via a single 3dAttribute BRICK_STATAUX call.

    Returns
    -------
    dict of int -> list of float
        {sub-brick index: auxiliary parameter values (e.g. [DOF] for a
        T-stat sub-brick)}. The first occurrence wins for a duplicated index.

    Raises
    ------
    GuardError
        If the 3dAttribute command fails.
    """
    try:
        out = run_afni_command(
            ["3dAttribute", "BRICK_STATAUX", bucket_path],
            capture_output=True,
            description="3dAttribute BRICK_STATAUX",
            logger=logger,
        )
    except ToolExecutionError as e:
        raise GuardError(
            f"Could not retrieve BRICK_STATAUX from {bucket_path}: {e}"
        ) from e

    tokens = out.split()
    stataux = {}
    i = 0
    while i < len(tokens):
        try:
            idx = int(tokens[i])
            _ = int(tokens[i + 1])
            npar = int(tokens[i + 2])
            params = [float(tokens[i + 3 + j]) for j in range(npar)]
            if idx not in stataux:
                stataux[idx] = params
            i += 3 + npar
        except (ValueError, IndexError):
            break
    return stataux


# ---------------------------------------------------------------------------
# GLT contrast argument builder
# ---------------------------------------------------------------------------

def gltsym_args(kept_contrasts, contrast_labels):
    """Build -num_glt/-gltsym/-glt_label arguments from the kept contrast list."""
    if not kept_contrasts or not contrast_labels:
        return ["-num_glt", "0"]
    args = ["-num_glt", str(len(kept_contrasts))]
    for k, (contrast, label) in enumerate(zip(kept_contrasts, contrast_labels), 1):
        gltstr = "".join(
            f"{c}*{cd} " for c, cd in zip(contrast["COEFS"], contrast["CONDS"])
        ).strip()
        args.extend(["-gltsym", f"SYM: {gltstr}", "-glt_label", str(k), label])
    return args


# ---------------------------------------------------------------------------
# Bucket stats index generation
# ---------------------------------------------------------------------------

def generate_bucket_stats_index(io, bucket_rel, index_rel, logger):
    """Generate a JSON index mapping bucket sub-brick labels to indices.

    Returns
    -------
    Output
    """
    bucket_path = io.path(bucket_rel)
    info = run_afni_command(
        ["3dinfo", "-label", bucket_path],
        capture_output=True,
        description="3dinfo label for bucket stats index",
        logger=logger,
        cwd=io.staging,
    )
    labels = [l.strip() for l in info.strip().split("|") if l.strip()]
    index_map = {label: i for i, label in enumerate(labels)}
    text = json.dumps(index_map, indent=2) + "\n"
    with open(io.path(index_rel), "w", newline="") as f:
        f.write(text)
    return Output(index_rel, "final", "py_text", producer="bucket stats index",
                 expected_text=text)


# ---------------------------------------------------------------------------
# Per-stat-type index writer
# ---------------------------------------------------------------------------

def write_stat_indexes(io, ext, matched, token=""):
    """Write per-stat-type JSON indexes and return their Outputs."""
    outputs = []
    for stat_type, items in matched.items():
        index_rel = names.stat_index(ext, stat_type, token)
        index_map = {label: i for i, (label, _) in enumerate(items)}
        index_text = json.dumps(index_map, indent=2) + "\n"
        with open(io.path(index_rel), "w", newline="") as f:
            f.write(index_text)
        outputs.append(Output(index_rel, "final", "py_text",
                              producer=f"{stat_type} index",
                              expected_text=index_text))
    return outputs


# ---------------------------------------------------------------------------
# Stat bucket extraction
# ---------------------------------------------------------------------------

def extract_stat_bucket_niftis(io, bucket_path, stat_types, ext, token, logger):
    """Extract stat-type-specific NIfTI buckets from the full bucket stats dataset.

    Each extracted sub-brick is keyed by its exact ``3dinfo -label`` label
    (e.g. ``"ave_negface_GLT#0_Coef"``, ``"Full_Fstat"``); a Zstat bucket
    reuses the matching Tstat label with the trailing "Tstat" replaced by
    "Zstat". A label belongs to stat type S when it ends with "_" + S.

    Parameters
    ----------
    io : StepIO
    bucket_path : str
        Absolute path to the source bucket stats NIfTI (in out_dir).
    stat_types : list of str
    ext : str
        extract_out_file_pre.
    token : str
        Smoothing token ("" for unsmoothed).
    logger : logging.Logger

    Returns
    -------
    (list of Output, dict)
        Outputs and a dict {stat: [(key, orig_idx)]} matched sub-bricks.
    """
    outputs = []
    matched_all = {}

    info = run_afni_command(
        ["3dinfo", "-label", bucket_path],
        capture_output=True,
        description="3dinfo label for stat bucket extraction",
        logger=logger, cwd=io.staging,
    )
    labels = [l.strip() for l in info.strip().split("|") if l.strip()]

    for stat_type in stat_types:
        search_stat = "Tstat" if stat_type == "Zstat" else stat_type
        need_t2z = (stat_type == "Zstat")
        suffix = f"_{search_stat}"

        matched = []
        for idx, label in enumerate(labels):
            if label.endswith(suffix):
                key = label[: -len(search_stat)] + "Zstat" if need_t2z else label
                matched.append((key, idx))

        if not matched:
            logger.warning(
                "No sub-bricks found for stat type '%s' in %s. Skipping.",
                stat_type, bucket_path,
            )
            continue

        bucket_out_rel = names.stat_bucket(ext, stat_type, token)

        if need_t2z:
            stataux = _get_stataux(bucket_path, logger=logger)
            z_vols = []
            for i, (key, idx) in enumerate(matched):
                aux_params = stataux.get(idx, [])
                if not aux_params:
                    raise GuardError(
                        f"Could not retrieve DOF for sub-brick {idx} ({key}) "
                        f"in {bucket_path}; cannot convert T to Z."
                    )
                dof = int(aux_params[0])
                z_tmp_rel = f"_zconv_tmp_{i}.nii.gz"
                run_afni_command(
                    ["3dcalc", "-a", f"{bucket_path}[{idx}]",
                     "-expr", f"fitt_t2z(a,{dof})",
                     "-prefix", io.path(z_tmp_rel)],
                    description=f"T-to-Z conversion for {key}",
                    logger=logger, cwd=io.staging,
                )
                z_vols.append(io.path(z_tmp_rel))

            run_afni_command(
                ["3dbucket", "-prefix", io.path(bucket_out_rel)] + z_vols,
                description=f"3dbucket assemble {stat_type} bucket",
                logger=logger, cwd=io.staging,
            )
        else:
            selectors = [f"{bucket_path}[{idx}]" for _, idx in matched]
            run_afni_command(
                ["3dbucket", "-prefix", io.path(bucket_out_rel)] + selectors,
                description=f"3dbucket extract {stat_type} bucket",
                logger=logger, cwd=io.staging,
            )

        outputs.append(Output(bucket_out_rel, "final", "nifti",
                              producer=f"{stat_type} bucket extraction",
                              expected_nvols=len(matched)))
        matched_all[stat_type] = matched

    return outputs, matched_all


def stat_bucket_parcellations(io, ext, matched, bucket_out_paths, template,
                               average_type, roi_zero_handling, logger):
    """Write parcellated CSVs for each extracted stat bucket.

    Parameters
    ----------
    io : StepIO
    ext : str
    matched : dict
        {stat: [(label, orig_idx)]}
    bucket_out_paths : dict
        {stat: absolute path to the extracted bucket NIfTI}
    template : str or None
    average_type, roi_zero_handling : str
    logger : logging.Logger

    Returns
    -------
    list of Output
    """
    outputs = []
    for stat_type, items in matched.items():
        if template is not None:
            csv_rel = names.stat_parcellated(ext, stat_type)
            bucket_path = bucket_out_paths[stat_type]
            rows = {}
            for new_idx, (label, _) in enumerate(items):
                roi_df = roi.extract_roi_stats(
                    f"{bucket_path}[{new_idx}]", template, average_type,
                    roi_zero_handling, logger, cwd=io.staging,
                )
                rows[label] = roi_df.iloc[0]
            parcellated_df = pd.DataFrame(rows).T
            parcellated_df.index.name = "condition"
            csv_text = parcellated_df.to_csv()
            with open(io.path(csv_rel), "w", newline="") as f:
                f.write(csv_text)
            outputs.append(Output(csv_rel, "final", "py_text",
                                  producer=f"{stat_type} parcellation",
                                  expected_text=csv_text))

    return outputs


# ---------------------------------------------------------------------------
# Expected-path enumeration
# ---------------------------------------------------------------------------

def task_act_expected(config, runsets, conditions):
    """Enumerate every final output and deterministic intermediate for task_act.

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
    expected.add(names.bucket_stats(pre))
    expected.add(names.bucket_resids(pre))
    expected.add(names.bucket_stats_index(pre))

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

    if config.stat_buckets and config.extract_out_file_pre:
        ext = config.extract_out_file_pre
        for stat in config.stat_buckets:
            expected.add(names.stat_bucket(ext, stat))
            expected.add(names.stat_index(ext, stat))
            if config.template_path is not None:
                expected.add(names.stat_parcellated(ext, stat))

    if config.extract_resids and config.extract_out_file_pre:
        expected.add(names.resids_csv(config.extract_out_file_pre))

    for cond in conditions:
        expected.add(names.onset_file(pre, cond))

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

    expected.add(names.preflight_dmat(pre))
    expected.add(names.estimability_dmat(pre))

    if config.smoothing_enabled:
        token = names.smoothing_token(config.smoothing_fwhm)
        expected.add(names.smoothing_mask(pre))
        for lbl in s_pre:
            expected.add(names.blurred_run(pre, None if k_sup == 1 else lbl, token))
            if config.scale_to_psc:
                expected.add(names.blurred_psc_run(pre, None if k_sup == 1 else lbl, token))
        if k_sup > 1:
            expected.add(names.blurred_concat(pre, token, config.scale_to_psc))
        expected.add(names.bucket_stats(pre, token))
        expected.add(names.bucket_resids(pre, token))
        expected.add(names.bucket_stats_index(pre, token))
        if config.stat_buckets and config.extract_out_file_pre:
            ext = config.extract_out_file_pre
            for stat in config.stat_buckets:
                expected.add(names.stat_bucket(ext, stat, token))
                expected.add(names.stat_index(ext, stat, token))

    return expected


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run(config, logger=None):
    """Run the task activation first-level pipeline.

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
        logger = setup_logging("task_act_first_level")
    return run_with_status("task_act", config, logger, _run)


def _run(config, logger, tracker):
    """Pipeline body; see run()."""

    config = copy.copy(config)
    clear_warnings()
    tracker.step = "task-act-runtime-check"
    versions = runtime_check(logger)
    tracker.versions = versions

    # Contrast checks
    tracker.step = "task-act-contrast-validation"
    if config.contrast_functions:
        parsed_contrasts = valid_contrast_functions(
            config.contrast_functions, config.contrast_labels,
            config.cond_labels, logger=logger,
        )
    else:
        parsed_contrasts = None

    tracker.step = "task-act-run-sets"
    runsets = build_runsets(config, "task_act", logger)
    ctx = RunContext(config, "task_act", logger, versions, runsets.grid_ref, tracker=tracker)
    ctx.start()

    log_hrf_model(config.hrf_model, config.custom_hrf, logger)
    log_nuisance_model(config.CSF_path, config.WM_path, logger, config.use_tissue_derivs)

    pre = config.out_file_pre

    # Template checks
    template_used = config.template_path is not None and (
        (config.stat_buckets and config.extract_out_file_pre)
        or config.extract_resids
        or config.extract_raw_ptseries
    )
    same_grid = None
    if template_used:
        tracker.step = "task-act-template-check"
        same_grid = roi.check_template(
            config.template_path, runsets.grid_ref, config.force_diff_atlas,
            {"extract"}, logger,
        )

    # Step: task-act-events
    def _events_step(io):
        event_table, check = events.build_event_table(
            config, runsets, config.cond_labels,
        )
        if check.violations:
            record = events.timing_record("task_act", runsets.input_mode, config.tr, check)
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

    ctx.run_step("task-act-events", _events_step)
    event_table = ctx._event_table

    # Step: task-act-nuisance
    def _nuisance_step(io):
        outcome, state = nuisance.task_nuisance(io, config, runsets, logger)
        ctx._nuisance_state = state
        return outcome

    ctx.run_step("task-act-nuisance", _nuisance_step)
    nuisance_state = ctx._nuisance_state
    s_pre = runsets.s_pre

    # Step: task-act-estimability
    def _estimability_step(io):
        onset_specs = []
        run_df = event_table.for_runs(s_pre).df
        married = needs_married_timing(config.hrf_model, config.custom_hrf)
        for cond in config.cond_labels:
            rows = events.onset_rows(event_table, [cond], list(s_pre))
            text = events.onset_file_text(rows, married)
            tmp_rel = f"_tmp_onset_{cond}.txt"
            with open(io.path(tmp_rel), "w", newline="") as f:
                f.write(text)

            hrf = hrf_for_durations(
                config.hrf_model, config.custom_hrf,
                run_df.loc[run_df["condition"] == cond, "duration"],
            )

            onset_specs.append((cond, io.path(tmp_rel), hrf))

        matrix, header = estimability.estimability_dry_run(
            io, config, runsets, onset_specs, logger,
        )

        # Load censor vector
        censor_path = f"{config.out_dir}/{names.censor(pre, None)}"
        censor_vec = np.loadtxt(censor_path, dtype=int).ravel()

        all_column_order = []
        all_fvalues = []
        afni_version = ctx.versions.get("afni_version")
        for cond in config.cond_labels:
            # Trials in this condition's onset-file order (same source as the file).
            cond_rows = events.onset_rows_labeled(event_table, [cond], list(s_pre))
            cond_order = [
                (c, lbl, onset)
                for i, lbl in enumerate(s_pre)
                for (c, onset, _) in cond_rows[i]
            ]
            if not cond_order:
                # No trials in the model runs: no IM columns may exist for it.
                try:
                    stray = estimability.im_columns(header, cond)
                except ToolExecutionError:
                    stray = []
                if stray:
                    raise GuardError(
                        f"Condition '{cond}' has no trials in the model runs but "
                        f"the design matrix has {len(stray)} IM column(s) for it."
                    )
                continue

            cols = estimability.im_columns(header, cond)
            # One (f, reason) per trial, pooled over the trial's basis columns
            # when the HRF has more than one column per trial.
            fvals = estimability.trial_estimability(
                matrix, cols, censor_vec, len(cond_order),
            )
            estimability.check_im_order(matrix, cols, cond_order, afni_version)

            all_column_order.extend(cond_order)
            all_fvalues.extend(fvals)

        trials = estimability.build_trials(
            event_table, config.cond_labels, s_pre, runsets.supplied,
            all_column_order, all_fvalues, "task_act",
        )
        trial_counts, surviving, run_counts = estimability.survival_summary(
            trials, config.cond_labels,
        )
        kept_conditions, kept_contrasts, kept_labels, _ = estimability.apply_floor(
            "task_act", config.cond_labels, surviving,
            parsed_contrasts, config.contrast_labels, logger,
        )
        config.cond_labels = kept_conditions
        config.contrast_functions = (
            [f"{'+'.join(f'{c}*{cd}' for c, cd in zip(con['COEFS'], con['CONDS']))}"
             for con in kept_contrasts] if kept_contrasts else None
        )
        config.contrast_labels = kept_labels
        ctx._kept_contrasts = kept_contrasts

        reml = collect_reml_cmds(io.staging, pre, "task-act-estimability")
        outputs = [Output(names.estimability_dmat(pre), "intermediate", "x1d",
                          producer="estimability dry run")]
        for rel, kind in reml:
            outputs.append(Output(rel, "intermediate", kind, producer="REML_cmd"))

        qc_frag = {
            "trials": trials,
            "per_condition_trial_counts": trial_counts,
            "per_condition_surviving_trials": surviving,
            "per_condition_run_counts": run_counts,
        }
        return Outcome(outputs=outputs, qc=qc_frag)

    ctx.run_step("task-act-estimability", _estimability_step)

    # Step: task-act-onsets
    def _onsets_step(io):
        outputs = []
        married = needs_married_timing(config.hrf_model, config.custom_hrf)
        for cond in config.cond_labels:
            rows = events.onset_rows(event_table, [cond], list(s_pre))
            text = events.onset_file_text(rows, married)
            rel = names.onset_file(pre, cond)
            with open(io.path(rel), "w", newline="") as f:
                f.write(text)
            outputs.append(Output(rel, "intermediate", "py_text",
                                  producer="onset file", expected_text=text))
        return Outcome(outputs=outputs)

    ctx.run_step("task-act-onsets", _onsets_step)

    # Step: task-act-preflight
    def _preflight_step(io):
        onset_files = [
            (cond, f"{config.out_dir}/{names.onset_file(pre, cond)}")
            for cond in config.cond_labels
        ]
        ortvecs = nuisance.task_ortvecs(nuisance_state, config.out_dir)

        censor_path = f"{config.out_dir}/{names.censor(pre, None)}"
        motion_path = f"{config.out_dir}/{nuisance_state['motion_rel']}"

        dof = estimability.task_act_preflight_dof(
            io, config, runsets, onset_files, censor_path, motion_path,
            ortvecs, event_table, logger,
        )

        reml = collect_reml_cmds(io.staging, pre, "task-act-preflight")
        outputs = [Output(names.preflight_dmat(pre), "intermediate", "x1d",
                          producer="preflight dry run")]
        for rel, kind in reml:
            outputs.append(Output(rel, "intermediate", kind, producer="REML_cmd"))

        return Outcome(outputs=outputs, qc={"dof": dof})

    ctx.run_step("task-act-preflight", _preflight_step)

    # Ledgered stage: task-act-template
    template_resolved = config.template_path
    if template_used:
        template_resolved = roi.template_stage(
            ctx, config, runsets, pre, same_grid, "task-act", logger,
        )

    # Ledgered stage: task-act-prep
    prep_spec = StageSpec(
        label="task-act-prep",
        fields=("scan_path", "scan_paths", "run_lengths", "run_labels", "scale_to_psc"),
        derived_values={"s_pre": list(s_pre)},
    )

    def _prep_stage(io):
        return prep.task_prep(io, config, runsets, logger)

    ctx.run_stage(prep_spec, _prep_stage)

    # Set S_final (= S_pre for task_act; no model-estimation failures per run)
    runsets.set_s_final(s_pre)
    s_final = runsets.s_final

    # Ledgered stage: task-act-min-outlier-epi
    moe_spec = StageSpec(
        label="task-act-min-outlier-epi",
        fields=("scan_path", "scan_paths", "run_lengths", "run_labels"),
        derived_values={"s_final": list(s_final)},
    )

    def _moe_stage(io):
        outputs = []
        for lbl in s_final:
            ri = runsets.run(lbl)
            out_rel = names.min_outlier_epi(pre, None if runsets.k_supplied == 1 else lbl)
            gen_min_outlier_epi(
                ri.source_path, ri.start, ri.n_vols, io.path(out_rel), logger,
                cwd=io.staging,
            )
            outputs.append(Output(out_rel, "final", "nifti",
                                  producer="min-outlier EPI", expected_nvols=1))
        return Outcome(outputs=outputs)

    ctx.run_stage(moe_spec, _moe_stage)

    # Ledgered stage: task-act-raw-ptseries
    if config.extract_raw_ptseries and template_used:
        raw_spec = StageSpec(
            label="task-act-raw-ptseries",
            fields=("extract_raw_ptseries", "extract_out_file_pre", "template_path",
                    "average_type", "roi_zero_handling", "scan_path", "scan_paths",
                    "run_labels", "scale_to_psc"),
            derived_values={"s_pre": list(s_pre), "template_resolved": template_resolved},
            upstream=("task-act-prep", "task-act-template"),
        )

        def _raw_ptseries_stage(io):
            return prep.task_raw_ptseries(io, config, runsets, template_resolved, logger)

        ctx.run_stage(raw_spec, _raw_ptseries_stage)

    def _run_glm(io, token, stage_label, description, producer):
        """Run the 3dDeconvolve GLM (unsmoothed when token is None) and
        return (outputs, bucket_stats_rel)."""
        model_input = prep.task_model_input(config, runsets, config.out_dir, token)
        mask_path = prep.task_mask_path(config, runsets, config.out_dir)
        censor_path = f"{config.out_dir}/{names.censor(pre, None)}"
        motion_path = f"{config.out_dir}/{nuisance_state['motion_rel']}"

        ortvecs = nuisance.task_ortvecs(nuisance_state, config.out_dir)

        cmd = build_decon_base_command(
            model_input, censor_path, motion_path, ortvecs,
            runsets.run_starts(s_pre), mask_path, config.tr,
        )
        cmd.extend(["-num_stimts", str(len(config.cond_labels))])

        run_df = event_table.for_runs(s_pre).df
        married = needs_married_timing(config.hrf_model, config.custom_hrf)
        stim_flag = "-stim_times_AM1" if married else "-stim_times"
        for k, cond in enumerate(config.cond_labels, 1):
            onset_path = f"{config.out_dir}/{names.onset_file(pre, cond)}"
            hrf = hrf_for_durations(
                config.hrf_model, config.custom_hrf,
                run_df.loc[run_df["condition"] == cond, "duration"],
            )
            cmd.extend([stim_flag, str(k), onset_path, hrf, "-stim_label", str(k), cond])

        cmd.extend(gltsym_args(getattr(ctx, "_kept_contrasts", None), config.contrast_labels))

        bucket_stats_rel = names.bucket_stats(pre, token)
        bucket_resids_rel = names.bucket_resids(pre, token)
        cmd.extend([
            "-errts", io.path(bucket_resids_rel),
            "-fout", "-rout", "-tout",
            "-bucket", io.path(bucket_stats_rel),
            "-jobs", str(config.num_cores),
        ])

        run_afni_command(cmd, description=description, logger=logger, cwd=io.staging)

        reml = collect_reml_cmds(io.staging, pre, stage_label)
        outputs = [
            Output(bucket_stats_rel, "final", "nifti", producer=producer),
            Output(bucket_resids_rel, "final", "nifti", producer=producer),
        ]
        for rel, kind in reml:
            outputs.append(Output(rel, "intermediate", kind, producer="REML_cmd"))

        index_out = generate_bucket_stats_index(
            io, bucket_stats_rel, names.bucket_stats_index(pre, token), logger,
        )
        outputs.append(index_out)

        return outputs, bucket_stats_rel

    # Files the GLM passes to AFNI (censor, motion, onsets, tissue regressors
    # and their derivatives); hashed so a content-only edit reruns the GLM.
    glm_files = (
        [f"{config.out_dir}/{names.censor(pre, None)}",
         f"{config.out_dir}/{nuisance_state['motion_rel']}"]
        + [f"{config.out_dir}/{names.onset_file(pre, c)}" for c in config.cond_labels]
        + [f"{config.out_dir}/{nuisance_state['tissue_rel'][t]}"
           for t in ("CSF", "WM") if t in nuisance_state["tissue_rel"]]
        + [f"{config.out_dir}/{d}"
           for t, d in sorted(nuisance_state.get("tissue_deriv_rel", {}).items())]
    )

    # Ledgered stage: task-act-glm
    glm_spec = StageSpec(
        label="task-act-glm",
        fields=("scan_path", "scan_paths", "run_lengths", "run_labels", "tr",
                "hrf_model", "custom_hrf", "cond_labels", "contrast_functions",
                "contrast_labels", "task_timing_path", "task_timing_paths",
                "motion_path", "motion_paths", "include_motion_derivs",
                "fd_threshold", "censor_prev_tr", "CSF_path", "CSF_paths",
                "WM_path", "WM_paths", "use_tissue_derivs"),
        derived_files=tuple(glm_files),
        derived_values={"s_pre": list(s_pre)},
        upstream=("task-act-prep",),
    )

    def _glm_stage(io):
        outputs, _ = _run_glm(io, None, "task-act-glm", "3dDeconvolve GLM", "3dDeconvolve GLM")
        return Outcome(outputs=outputs)

    ctx.run_stage(glm_spec, _glm_stage)

    # Ledgered stage: task-act-extract
    if config.stat_buckets or config.extract_resids:
        extract_upstream = ["task-act-glm"]
        if template_used:
            extract_upstream.append("task-act-template")
        extract_spec = StageSpec(
            label="task-act-extract",
            fields=("stat_buckets", "extract_resids", "extract_out_file_pre",
                    "average_type", "roi_zero_handling", "template_path"),
            derived_values={"template_resolved": template_resolved},
            upstream=tuple(extract_upstream),
        )

        def _extract_stage(io):
            outputs = []
            bucket_path = f"{config.out_dir}/{names.bucket_stats(pre)}"

            if config.stat_buckets:
                stat_outs, matched = extract_stat_bucket_niftis(
                    io, bucket_path, config.stat_buckets,
                    config.extract_out_file_pre, "", logger,
                )
                outputs.extend(stat_outs)

                idx_outs = write_stat_indexes(io, config.extract_out_file_pre, matched)
                outputs.extend(idx_outs)

                bucket_out_paths = {
                    stat: io.path(names.stat_bucket(config.extract_out_file_pre, stat))
                    for stat in matched
                }
                parcel_outs = stat_bucket_parcellations(
                    io, config.extract_out_file_pre, matched, bucket_out_paths,
                    template_resolved if config.template_path else None,
                    config.average_type, config.roi_zero_handling, logger,
                )
                outputs.extend(parcel_outs)

            if config.extract_resids:
                resid_path = f"{config.out_dir}/{names.bucket_resids(pre)}"
                resid_df = roi.extract_roi_stats(
                    resid_path, template_resolved, config.average_type,
                    config.roi_zero_handling, logger, cwd=io.staging,
                )
                csv_text = resid_df.to_csv()
                rel = names.resids_csv(config.extract_out_file_pre)
                with open(io.path(rel), "w", newline="") as f:
                    f.write(csv_text)
                outputs.append(Output(rel, "final", "py_text",
                                      producer="residuals extraction",
                                      expected_text=csv_text))

            return Outcome(outputs=outputs)

        ctx.run_stage(extract_spec, _extract_stage)

    # Smoothing branch
    if config.smoothing_enabled:
        token = names.smoothing_token(config.smoothing_fwhm)

        smooth_spec = StageSpec(
            label="task-act-smooth",
            fields=("smoothing_enabled", "smoothing_fwhm", "scan_path", "scan_paths",
                    "run_lengths", "run_labels", "scale_to_psc"),
            derived_values={"s_pre": list(s_pre)},
            upstream=("task-act-prep",),
        )

        def _smooth_stage(io):
            return smoothing.task_smooth(io, config, runsets, s_pre, pre, token, logger)

        ctx.run_stage(smooth_spec, _smooth_stage)

        glm_smooth_spec = StageSpec(
            label="task-act-glm-smooth",
            fields=glm_spec.fields + ("smoothing_enabled", "smoothing_fwhm",
                                      "stat_buckets", "extract_out_file_pre"),
            derived_files=tuple(glm_files),
            derived_values={"s_pre": list(s_pre)},
            upstream=("task-act-smooth",),
        )

        def _glm_smooth_stage(io):
            outputs, bucket_stats_rel = _run_glm(
                io, token, "task-act-glm-smooth", "3dDeconvolve smoothed GLM", "smoothed GLM",
            )

            if config.stat_buckets:
                stat_outs, matched = extract_stat_bucket_niftis(
                    io, io.path(bucket_stats_rel), config.stat_buckets,
                    config.extract_out_file_pre, token, logger,
                )
                outputs.extend(stat_outs)

                idx_outs = write_stat_indexes(io, config.extract_out_file_pre, matched, token)
                outputs.extend(idx_outs)

            return Outcome(outputs=outputs)

        ctx.run_stage(glm_smooth_spec, _glm_smooth_stage)

    # Ledgered stage: task-act-roi-qc
    if template_used:
        roiqc_spec = StageSpec(
            label="task-act-roi-qc",
            fields=("template_path", "roi_zero_handling", "scan_path", "scan_paths",
                    "run_lengths", "run_labels", "scale_to_psc"),
            derived_values={"s_pre": list(s_pre), "template_resolved": template_resolved},
            upstream=("task-act-template", "task-act-prep"),
        )

        def _roiqc_stage(io):
            return roi.task_roi_qc(io, config, runsets, s_pre, template_resolved, pre, logger)

        ctx.run_stage(roiqc_spec, _roiqc_stage)

    # Final assembly
    conditions_final = config.cond_labels
    expected = task_act_expected(config, runsets, conditions_final)

    def _qc_fragment(retired):
        return {
            "analysis_type": "task_act",
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

    return ctx.finish(expected=expected, qc_step_fragment=_qc_fragment)
