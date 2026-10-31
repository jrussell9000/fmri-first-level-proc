#!/usr/bin/env python3

# ============================================================================
# TASK-BASED fMRI ACTIVATION ANALYSIS
# 1. First-level regression statistical dataset (including denoising and censoring) with AFNI's 3dDeconvolve
# 2. (optional) Creates condition/contrast- and stat-specific datasets with AFNI's 3dcalc
# 3. (optional) Extract parcel-level/ROI activation with a provided template with AFNI's 3dROIstats
#
# Author: Taylor J. Keding, Ph.D.
# Version: 3.0.0
# Last updated: 05/01/26
# ============================================================================
'''
REQUIREMENTS:
- AFNI
- numpy
- pandas

INPUTS:
(required)
-scan_path: global file path to the run-concatenated dense time series (preprocessed UP TO first-level analyses)
    format = string(path_to_nii) (volumetric)
--task_timing_path: global file path to the run-concatenated stimulus timing file (should have been stripped for dummy scans)
    format = string(path_to_csv); column 1 name = 'CONDITION', column 2 name = 'ONSET' (global times matching --scan_path scan length), column 3 name = 'DURATION'
--motion_path: global file path to the run-concatenated motion regressors (should have been stripped for dummy scans)
    format = string(path_to_txt) (tab-delimited) with no headers; rows = TR/frame, columns = motion regressors (6 base or 12 with derivatives, controlled by include_motion_derivs)
--fd_threshold: framewise displacement threshold (mm); TRs with FD above this value are censored (censor file is generated internally from --motion_path; it is NOT a user-provided input)
--cond_labels: string-list (comma-separated) of task conditions to use in first level analyses - labels should match the 'CONDITION' column from the timing file;
    Conditions in cond_labels will be the only ones used in the regression (more could be in task_timing_path file) and the only ones that can be used within contrast_functions (optional)
    format = string-list of conditions e.g. 'stimFear,stimSad,stimNeu'
--out_dir: global directory path for derivative intermediates and statistical datasets; will create if doesn't exist
--out_file_pre: prefix to be prepended to the statistical dataset outputs (should usually contain an ID, task name, time point, etc. but NOT the global file path; eg. 'subj001_nback_baseline')
--num_cores: number of CPU cores available for parallel processing (int)

(optional)
--hrf_model: HRF basis function model to use (default: 'GAM'). Options: 'GAM', 'BLOCK', 'dmBLOCK', 'SPMG1', 'custom'
--custom_hrf: custom AFNI HRF model string (only used when hrf_model='custom', e.g. 'TENT(0,14,8)')
--CSF_path: global file path to the run-concatenated cerebrospinal fluid BOLD signal time series
    format = string(path_to_txt); no headers; rows=TR/frame, single column = mean CSF signal
--WM_path: global file path to the run-concatenated white-matter BOLD signal time series
    format = string(path_to_txt); no headers; rows=TR/frame, single column = mean WM signal
--use_tissue_derivs: (no value) include this option to add first temporal derivatives of tissue signals (CSF/WM) as additional nuisance regressors; only computed for tissue paths that are provided
--remove_previous: (no value) include this option if "out_dir" should have all files removed before processing starts (including connectivity); if not included, will not overwrite pre-existing files
--contrast_functions: list of string formulas for linear contrasts using condition names in cond_labels
    format = list(string-equations) (e.g. if conditions "stimFear", "stimSad", and "stimNeu" exist in cond_labels, "1*stimFear-1*stimNeu,1*stimSad-1*stimNeu" would produce Fear-Neutral and Sad-Neutral constrasts)
--contrast_labels: list of string labels to give to each constrast in contrasts_functions
    format = list(string-labels) (for the example above, "Fear-Neutral,Sad-Neutral")
--extract: (no value) include this option if you want condition/contrast- and stat-specific maps
    If present and no template is provided to template_path, voxelwise whole-brain maps will be output; if present and template_path is valid, parcellated maps will be output
--extract_labels: if --extract is present, list of string labels to extract (each to their own file); MUST have corresponding matches in either --cond_labels or --constrast_labels
    format = list(string-labels) (e.g. "stimFear,stimSad,Fear-Neutral,Sad-Neutral" would save 4 maps specific to each condition/contrast and stat contained in --extract_stat)
--extract_stat: if --extract is present, statistic to extract from the 'bucket' statistical dataset from 3dDeconvolve; options: 'z', 't', 'r'
--extract_out_file_pre: if --extract, the prefix to attach to output files (should NOT include the file path, task condition/contrast, or stat; similar to --out_file_pre e.g. 'subj001_nback_baseline_Shen368')
--template_path: optional template file for --extract; if --extract is present and no template exists, voxelwise maps will be extracted, else parcel-level/ROI averages will be extracted based on the template and extract_stat
    Can be a binary mask (only a single parcel/ROI will be output) or a set of N ROIs/masks indicated by unique integers>0 (full parcel/ROI table will be output)
    format = string(path_to_nii) (volumetric and registered to the same atlas as input scan, unless --force_diff_atlas used; if there is a mismatch in grid spacing, will resample the template to the input scan grid)
--average_type: either "mean" or "median" - the type of averaging used when calculating average parcel activation with template
--extract_resids: (no value) if --extract is present and a valid template is provided, flag to indicate that parcel-level/ROI residuals should also be extracted.
--force_diff_atlas: (no value) include this option if you know the template and scan are in different standard spaces, but want to force connectivity analyses anyway (USE WITH CAUTION)

OUTPUTS:
(always)
{out_dir}/{out_file_pre}_concat_{condition}_onsets.txt: AFNI-safe version of timing onsets for task conditions (1D single column with no headers or row names)
{out_dir}/{out_file_pre}_concat_bucket_stats.nii.gz: first-level output statistical dataset for the entire task (subbrik = stim-stat combination)
{out_dir}/{out_file_pre}_concat_bucket_resids.nii.gz: residuals from the first-level output statistical dataset for the entire task

(optional)
--extract:
    If no template is provided: {out_dir}/{extract_out_file_pre}_{condition/constrast}_{stat}.nii.gz: condition- and stat-specific voxelwise map
    If a template is provided: {out_dir}/{extract_out_file_pre}_{condition/constrast}_{stat}.csv; rows correspond to each parcel/ROI in the template and columns are ["ROI", "ACT_{averageType}_{stat}"]
    If a template is provided and --extract_resids is present: {out_dir}/{extract_out_file_pre}_resids.csv; rows correspond to each parcel/ROI in the template and columns are ["ROI", "ACT_{averageType}_RESID"]
'''

# Imports
import copy
import json
import logging
import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from .exceptions import ConfigError, GuardError, InputError, ModelError, ToolExecutionError
from .first_level_config import ResolvedConfig
from .first_level_utils import (
    FirstLevelResult,
    graded_warning,
    get_warnings,
    clear_warnings,
    setup_logging,
    dir_path_exists,
    file_path_exists,
    valid_string_list,
    valid_ave_type,
    run_afni_command,
    validate_template,
    remove_files_from_dir,
    extract_roi_stats,
    build_hrf_string,
    needs_married_timing,
    read_and_validate_stim_data,
    write_onset_file,
    build_decon_base_command,
    clean_deconvolve_err,
    log_hrf_model,
    log_nuisance_model,
    prepare_motion_file,
    compute_tissue_derivative,
    create_censor_file,
    check_trial_survival,
    write_qc_summary,
    compute_dof,
    valid_contrast_functions,
    gen_min_outlier_epi,
    scale_to_psc,
    CENSOR_WARN_THRESHOLD,
    CENSOR_HIGH_THRESHOLD,
    HRF_DM_MODELS,
    HRF_IMPULSE_MODELS,
    HRF_DURATION_MODELS,
    VALID_HRF_MODELS,
)

# Surviving trial count below which TRIALS_FEW warning is emitted (condition still included)
_TRIALS_FEW_THRESHOLD = 10


def read_stim_data(config: ResolvedConfig, logger: logging.Logger) -> pd.DataFrame:
    """Read and validate stimulus timing data for the task activation pipeline.

    Reads and validates the timing CSV without writing any onset files. Separating
    the read phase from the write phase allows trial-survival filtering to be applied
    before onset files are written, maintaining architectural consistency with the
    task connectivity pipeline.

    Parameters
    ----------
    config : ResolvedConfig
        Must include: task_timing_path, cond_labels.
    logger : logging.Logger

    Returns
    -------
    pd.DataFrame
        Sorted timing data with trial_type, onset, duration columns (BIDS naming).
    """
    return read_and_validate_stim_data(config.task_timing_path, config.cond_labels, logger=logger)


def write_stim_onset_files(stim_data: pd.DataFrame, config: ResolvedConfig, logger: logging.Logger) -> None:
    """Write per-condition AFNI onset files for the task activation pipeline.

    Must be called after trial-survival filtering so that config.cond_labels reflects
    only surviving conditions. Writes one AFNI-format onset file per condition in
    config.cond_labels (used as -stim_times inputs to 3dDeconvolve). Conditions present
    in stim_data but not in config.cond_labels are silently ignored.

    Parameters
    ----------
    stim_data : pd.DataFrame
        Sorted timing data with trial_type, onset, duration columns (BIDS naming).
    config : ResolvedConfig
        Must include: cond_labels, out_dir, out_file_pre, hrf_model, custom_hrf.
    logger : logging.Logger
    """
    for cond in stim_data['trial_type'].unique():
        cond_df = stim_data[stim_data['trial_type'] == cond]
        if cond in config.cond_labels:
            onset_file = f"{config.out_dir}/{config.out_file_pre}_concat_{cond}_onsets.txt"
            write_onset_file(cond_df, onset_file, config.hrf_model, config.custom_hrf, logger=logger)

def run_first_level(stim_data: pd.DataFrame, config: ResolvedConfig, logger: logging.Logger) -> None:
    """Execute the 3dDeconvolve activation first-level regression.

    Builds the full 3dDeconvolve command including nuisance regressors
    (motion, optional CSF/WM/derivatives), per-condition HRF-convolved
    stimulus timing, optional linear contrasts (GLTs), and statistics output
    flags (-fout, -rout, -tout). Writes the bucket stats and residuals NIfTIs.
    Skips if the output bucket stats file already exists.

    Parameters
    ----------
    stim_data : pd.DataFrame
        Timing data from read_stim_data.
    config : ResolvedConfig
        Must include: scan_path, censor_path, motion_path, CSF_path, WM_path,
        out_dir, out_file_pre, cond_labels, hrf_model, custom_hrf,
        contrast_functions, contrast_labels, num_cores, tr.
    logger : logging.Logger

    Raises
    ------
    ToolExecutionError
        If 3dDeconvolve fails or does not produce the expected bucket stats file.
    """
    # Check if outputs exist
    if not os.path.exists(f"{config.out_dir}/{config.out_file_pre}_concat_bucket_stats.nii.gz"):

        # Compute tissue signal derivatives if requested
        CSF_deriv_path = None
        WM_deriv_path = None
        if config.use_tissue_derivs:
            if config.CSF_path is not None:
                CSF_deriv_path = compute_tissue_derivative(config.CSF_path, config.out_dir, config.out_file_pre, "CSF", logger)
            if config.WM_path is not None:
                WM_deriv_path = compute_tissue_derivative(config.WM_path, config.out_dir, config.out_file_pre, "WM", logger)

        # Set-up base command, including temporal detrending, frame censors, and motion regressors
        decon_command = build_decon_base_command(config.scan_path, config.censor_path, config.motion_path,
                                                 CSF_path=config.CSF_path, WM_path=config.WM_path,
                                                 CSF_deriv_path=CSF_deriv_path, WM_deriv_path=WM_deriv_path,
                                                 tr=config.tr)
        decon_command.extend(["-num_stimts", f"{len(config.cond_labels)}"])

        # Iteratively add stim timing for conditions
        for i, cond in enumerate(config.cond_labels):
            # Compute mean duration for models that need it
            mean_dur = None
            if config.hrf_model in HRF_DURATION_MODELS:
                mean_dur = np.mean(stim_data[stim_data['trial_type'] == cond]['duration'])
            hrf_string = build_hrf_string(config.hrf_model, mean_dur=mean_dur, custom_hrf=config.custom_hrf)

            # dmBLOCK-family models require -stim_times_AM1 for married timing
            stim_flag = "-stim_times_AM1" if needs_married_timing(config.hrf_model, config.custom_hrf) else "-stim_times"
            decon_command.extend([stim_flag, f"{i+1}", f"{config.out_dir}/{config.out_file_pre}_concat_{cond}_onsets.txt",
                                 hrf_string, "-stim_label", f"{i+1}", f"{cond}"])

        # Iteratively add contrasts
        if config.contrast_functions:
            decon_command.extend(["-num_glt", str(len(config.contrast_functions))])
            for ci, cont in enumerate(config.contrast_functions):
                sym_eq = "SYM: " + " ".join(
                    f"{coef}*{cond}" for coef, cond in zip(cont["COEFS"], cont["CONDS"])
                )
                decon_command.extend(["-gltsym", sym_eq,
                                      "-glt_label", f"{ci+1}", f"{config.contrast_labels[ci]}"])

        # Add statistics output
        decon_command.extend(["-errts", f"{config.out_dir}/{config.out_file_pre}_concat_bucket_resids.nii.gz",
                              "-fout", "-rout", "-tout",
                              "-bucket", f"{config.out_dir}/{config.out_file_pre}_concat_bucket_stats.nii.gz",
                              "-jobs", f"{config.num_cores}"])

        # Run command
        run_afni_command(decon_command, description="3dDeconvolve activation", logger=logger)

        if os.path.exists(f"{config.out_dir}/{config.out_file_pre}_concat_bucket_stats.nii.gz"):
            logger.info("Successfully created first level activation stats for %s", config.out_file_pre)
        else:
            raise ToolExecutionError(
                f"3dDeconvolve did not produce bucket stats for {config.out_file_pre}."
            )
    else:
        logger.info("First level activation stats for %s already exists.", config.out_file_pre)

    # Remove err file that always seems to be output
    clean_deconvolve_err(config.out_dir)

def _get_subbrik_stat_aux(bucket_path, subbrik_index, logger=None):
    """Get the statistical auxiliary parameters (e.g. DOF) for a sub-brick.

    Returns
    -------
    list of float
        The auxiliary parameter values (e.g. [DOF] for a T-stat sub-brick).
    """
    try:
        out = run_afni_command(
            ["3dAttribute", "BRICK_STATAUX", bucket_path],
            capture_output=True,
            description="3dAttribute BRICK_STATAUX",
            logger=logger,
        )
    except ToolExecutionError:
        return []

    # BRICK_STATAUX format: pairs of (subbrik_index stat_type n_params param1 param2 ...)
    # stat_type 3 = T-stat (params: DOF)
    tokens = out.split()
    i = 0
    while i < len(tokens):
        try:
            idx = int(tokens[i])
            stype = int(tokens[i + 1])
            npar = int(tokens[i + 2])
            params = [float(tokens[i + 3 + j]) for j in range(npar)]
            if idx == subbrik_index:
                return params
            i += 3 + npar
        except (ValueError, IndexError):
            break
    return []


def generate_bucket_stats_index(config: ResolvedConfig, logger: logging.Logger) -> str:
    """Generate a JSON index mapping every sub-brick label in the bucket stats output to its 0-based index.

    Parameters
    ----------
    config : ResolvedConfig
        Must include: out_dir, out_file_pre.
    logger : logging.Logger

    Returns
    -------
    str
        Path to the written index JSON file.
    """
    bucket_path = f"{config.out_dir}/{config.out_file_pre}_concat_bucket_stats.nii.gz"
    index_path = os.path.join(
        config.out_dir, f"{config.out_file_pre}_concat_bucket_stats_index.json")

    if os.path.exists(index_path):
        logger.info("Bucket stats index already exists: %s", index_path)
        return index_path

    info = run_afni_command(
        ['3dinfo', '-label', bucket_path],
        capture_output=True,
        description="3dinfo label for bucket stats index",
        logger=logger,
    )
    labels = [l.strip() for l in info.strip().split('|') if l.strip()]
    index_map = {label: i for i, label in enumerate(labels)}

    with open(index_path, "w") as f:
        json.dump(index_map, f, indent=2)
    logger.info("Wrote bucket stats index: %s", index_path)

    return index_path


def extract_stat_buckets(config: ResolvedConfig, logger: logging.Logger) -> list[str]:
    """Extract stat-type-based bucket outputs from the 3dDeconvolve bucket dataset.

    For each stat type in config.stat_buckets, this function:
    1. Discovers all sub-bricks matching that stat type via 3dinfo -subbrick_info.
    2. Extracts them into a single multi-sub-brick NIfTI via 3dbucket.
    3. Writes a JSON index mapping condition/contrast labels to sub-brick indices.
    4. When template_path is available and not 'WB', writes a parcellated CSV
       (rows = conditions/contrasts, columns = ROIs).

    For Zstat: finds Tstat sub-bricks, converts each to Z via 3dcalc fitt_t2z(),
    then assembles the Z volumes into the bucket.

    Parameters
    ----------
    config : ResolvedConfig
        Must include: out_dir, out_file_pre, stat_buckets, extract_out_file_pre,
        template_path, average_type, extract_resids.
    logger : logging.Logger

    Returns
    -------
    list[str]
        Paths of all output files created.
    """
    bucket_path = f"{config.out_dir}/{config.out_file_pre}_concat_bucket_stats.nii.gz"
    output_files = []

    bucket_info = run_afni_command(
        ['3dinfo', '-subbrick_info', bucket_path],
        capture_output=True,
        description="3dinfo subbrick_info for stat bucket extraction",
        logger=logger,
    )
    bucket_split = bucket_info.split()

    available_stats = set()
    for token in bucket_split:
        for st in ("Coef", "Tstat", "Fstat", "R^2"):
            if st in token:
                available_stats.add(st)
    if any("Tstat" in token for token in bucket_split):
        available_stats.add("Zstat")
    logger.info("Available stat types in bucket: %s", sorted(available_stats))

    for stat_type in config.stat_buckets:
        search_stat = "Tstat" if stat_type == "Zstat" else stat_type
        need_t2z = (stat_type == "Zstat")

        matched = []
        for i, token in enumerate(bucket_split):
            if search_stat in token and "#" in token:
                label_part = token.split("#")[0]
                try:
                    idx = int(bucket_split[i - 1][1:])
                    matched.append((label_part, idx))
                except (ValueError, IndexError):
                    continue

        if not matched:
            logger.warning(
                "No sub-bricks found for stat type '%s' in %s. Skipping.",
                stat_type, bucket_path)
            continue

        logger.info("Found %d sub-bricks for stat type '%s': %s",
                    len(matched), stat_type, [m[0] for m in matched])

        bucket_out = os.path.join(
            config.out_dir,
            f"{config.extract_out_file_pre}_{stat_type}_bucket.nii.gz")
        index_out = os.path.join(
            config.out_dir,
            f"{config.extract_out_file_pre}_{stat_type}_index.json")

        if not os.path.exists(bucket_out):
            if need_t2z:
                z_vols = []
                for label, idx in matched:
                    aux_params = _get_subbrik_stat_aux(bucket_path, idx, logger=logger)
                    if not aux_params:
                        raise GuardError(
                            f"Could not retrieve DOF for sub-brick {idx} ({label}) in "
                            f"{bucket_path}; cannot convert T to Z.")
                    dof = int(aux_params[0])
                    z_tmp = os.path.join(
                        config.out_dir,
                        f"{config.out_file_pre}_{label}_zconv_tmp.nii.gz")
                    run_afni_command(
                        ["3dcalc", "-a", f"{bucket_path}[{idx}]",
                         "-expr", f"fitt_t2z(a,{dof})",
                         "-prefix", z_tmp],
                        description=f"T-to-Z conversion for {label}",
                        logger=logger)
                    z_vols.append(z_tmp)

                bucket_cmd = ["3dbucket", "-prefix", bucket_out] + z_vols
                run_afni_command(bucket_cmd,
                    description=f"3dbucket assemble {stat_type} bucket",
                    logger=logger)

                for zv in z_vols:
                    if os.path.exists(zv):
                        os.remove(zv)
            else:
                sub_brik_selectors = [f"{bucket_path}[{idx}]" for _, idx in matched]
                bucket_cmd = ["3dbucket", "-prefix", bucket_out] + sub_brik_selectors
                run_afni_command(bucket_cmd,
                    description=f"3dbucket extract {stat_type} bucket",
                    logger=logger)

            if not os.path.exists(bucket_out):
                raise ToolExecutionError(
                    f"Failed to create {stat_type} bucket: {bucket_out}")
            logger.info("Created %s bucket: %s", stat_type, bucket_out)
        else:
            logger.info("%s bucket already exists: %s", stat_type, bucket_out)

        output_files.append(bucket_out)

        index_map = {label: i for i, (label, _) in enumerate(matched)}
        with open(index_out, "w") as f:
            json.dump(index_map, f, indent=2)
        output_files.append(index_out)
        logger.info("Wrote %s index: %s", stat_type, index_out)

        if config.template_path is not None and config.template_path != "WB":
            csv_out = os.path.join(
                config.out_dir,
                f"{config.extract_out_file_pre}_{stat_type}_parcellated.csv")
            if not os.path.exists(csv_out):
                rows = {}
                for new_idx, (label, _) in enumerate(matched):
                    roi_df = extract_roi_stats(
                        f"{bucket_out}[{new_idx}]",
                        config.template_path, config.average_type, logger=logger)
                    rows[label] = roi_df.iloc[0]
                parcellated_df = pd.DataFrame(rows).T
                parcellated_df.index.name = "condition"
                parcellated_df.to_csv(csv_out)
                logger.info("Wrote %s parcellated CSV: %s", stat_type, csv_out)
            else:
                logger.info("%s parcellated CSV already exists: %s", stat_type, csv_out)
            output_files.append(csv_out)

    if config.extract_resids:
        resid_path = f"{config.out_dir}/{config.out_file_pre}_concat_bucket_resids.nii.gz"
        resid_csv = f"{config.out_dir}/{config.extract_out_file_pre}_resids.csv"
        if not os.path.exists(resid_csv):
            resid_df = extract_roi_stats(
                resid_path, config.template_path, config.average_type, logger=logger)
            resid_df.to_csv(resid_csv)
            if os.path.exists(resid_csv):
                logger.info("Extracted residuals to %s", resid_csv)
            else:
                raise ToolExecutionError("Could not extract residuals using ROI template.")
        output_files.append(resid_csv)

    return output_files

def run(config: ResolvedConfig, logger: logging.Logger | None = None) -> FirstLevelResult:
    """Validate config and execute the task activation pipeline.

    Orchestrates the full task_act pipeline in the following order:
    1. Validate contrast and extraction arguments.
    2. Optionally clear out_dir (if remove_previous is set).
    3. Validate extraction and connectivity template options.
    4. Optionally extract pre-regression parcellated time series (extract_raw_ptseries).
    5. Extract minimum-outlier EPI frame (gen_min_outlier_epi; mandatory).
    6. Generate motion censor file from motion_path and fd_threshold.
    7. Prepare motion regressors (truncate to required columns).
    8. Read and validate stimulus timing data (read_stim_data).
    9. Check per-condition trial survival after censoring.
    10. Warn for conditions with few surviving trials (TRIALS_FEW).
    11. Filter conditions with fewer than 2 surviving trials (warn COND_DROPPED and drop).
    12. Drop contrasts/extractions that reference dropped conditions (warn CONTRAST_DROPPED / EXTRACT_DROPPED).
    13. Write per-condition AFNI onset files (write_stim_onset_files).
    14. Pre-flight DOF check.
    15. Warn if overall censoring rate exceeds CENSOR_HIGH_THRESHOLD (CENSOR_HIGH).
    16. Run 3dDeconvolve GLM (run_first_level).
    17. Optionally extract stat-type-based bucket outputs (extract_stat_buckets).
    18. Write QC summary JSON.
    19. Return FirstLevelResult with status, warnings, qc_summary, and output_files.

    Works from the config-driven dispatch runner
    (run_first_level.py / DISPATCH["task_act"]).

    Parameters
    ----------
    config : ResolvedConfig
        All pipeline parameters (see first_level_config.py ResolvedConfig for
        the full attribute list).
    logger : logging.Logger or None, optional
        Logger instance. A default logger is created if None is provided.

    Returns
    -------
    FirstLevelResult
        Structured result with status ('success' or 'warning'),
        output_dir, accumulated graded warnings, qc_summary dict, and
        list of output file paths.

    Raises
    ------
    ConfigError
        On invalid or incompatible configuration options.
    InputError
        If an expected output file is not found after a write step.
    ModelError
        If all conditions are dropped due to insufficient surviving trials.
    ToolExecutionError
        If an AFNI command fails or does not produce its expected output.
    GuardError
        If a pipeline invariant is violated (e.g. unexpected sub-brick state).
    """
    if logger is None:
        logger = setup_logging("task_act_first_level")

    config = copy.copy(config)
    clear_warnings()

    logger.info("First-level regression will use the following task conditions: %s", config.cond_labels)
    logger.info("All other task conditions will not be modeled.")
    log_hrf_model(config.hrf_model, config.custom_hrf, logger)
    log_nuisance_model(config.CSF_path, config.WM_path, logger, use_tissue_derivs=config.use_tissue_derivs)

    # Contrast-related checks
    if config.contrast_labels is not None:
        if config.contrast_functions is None:
            raise ConfigError("contrast_functions must exist if contrast_labels exist.")
    else:
        if config.contrast_functions is not None:
            raise ConfigError("contrast_labels must exist if contrast_functions exist.")
    if config.contrast_functions is not None and config.contrast_labels is not None:
        config.contrast_functions = valid_contrast_functions(
            config.contrast_functions, config.contrast_labels, config.cond_labels, logger=logger
        )

    # If remove_previous is provided, clear-out the output dir (before template
    # resampling or any other file creation in out_dir)
    if config.remove_previous:
        logger.info("Removing all files from previous analyses in %s (if they exist).", config.out_dir)
        remove_files_from_dir(config.out_dir, logger=logger)

    # Check if the user wants to extract stat buckets
    if config.stat_buckets:
        if config.extract_out_file_pre is None:
            raise ConfigError(
                "extract_out_file_pre must be set when stat_buckets is specified."
            )
        logger.info("Stat bucket extraction requested for types: %s", config.stat_buckets)

        if config.template_path is None:
            config.template_path = "WB"
            logger.info("No template was provided; stat buckets will be NIfTI-only (no parcellated CSV).")
            if config.extract_resids:
                raise ConfigError("extract_resids is only valid when template_path is provided and valid.")
        else:
            config.template_path = validate_template(
                config.scan_path, config.template_path, config.out_dir,
                config.force_diff_atlas, conn_type="extract", logger=logger
            )
            if config.average_type is None:
                raise ConfigError("average_type is required when stat_buckets is specified and template_path is valid.")
            logger.info("Parcellated CSVs will be extracted based on %s.", config.template_path)
    else:
        logger.info("No stat bucket extraction requested.")

    # Extract pre-regression parcellated time series if requested
    if getattr(config, 'extract_raw_ptseries', False):
        if config.extract_out_file_pre is None:
            raise ConfigError("extract_raw_ptseries requires extract_out_file_pre to be set.")
        raw_out = os.path.join(config.out_dir, f"{config.extract_out_file_pre}_raw_ptseries.csv")
        if not os.path.exists(raw_out):
            if config.template_path is None or config.template_path == "WB":
                raise ConfigError("extract_raw_ptseries requires a valid template_path (not whole-brain).")
            # Validate template if not already validated by the extract block above
            validated_tpl = validate_template(
                config.scan_path, config.template_path,
                config.out_dir, config.force_diff_atlas, conn_type="extract", logger=logger
            )
            raw_df = extract_roi_stats(config.scan_path, validated_tpl, config.average_type, logger=logger)
            raw_df.to_csv(raw_out)
            if os.path.exists(raw_out):
                logger.info("Extracted raw (pre-regression) ptseries to %s.", raw_out)
            else:
                raise InputError("Failed to extract raw ptseries.")
        else:
            logger.info("Raw ptseries already exists: %s", raw_out)

    # ---------------------------------

    # Extract minimum-outlier representative EPI frame (mandatory, before regression)
    gen_min_outlier_epi(config.scan_path, config.out_dir, config.out_file_pre, "", logger)

    # PSC scaling (after min-outlier EPI, before regression)
    if config.scale_to_psc:
        psc_path = scale_to_psc(
            config.scan_path, config.out_dir, config.out_file_pre, "", logger)
        config.scan_path = psc_path

    # Generate censor file from motion regressors (before prepare_motion_file overwrites path)
    config.censor_path = create_censor_file(
        config.motion_path, config.fd_threshold, config.censor_prev_tr,
        config.out_dir, config.out_file_pre, "concat", logger)

    # Validate and prepare motion regressors
    use_cols = 12 if config.include_motion_derivs else 6
    config.motion_path = prepare_motion_file(
        config.motion_path, use_cols, config.out_dir, config.out_file_pre, "concat", logger)

    # Read and validate stimulus timing data (no file I/O yet)
    stim_data = read_stim_data(config, logger)

    # Per-condition trial survival QC
    trial_survival = check_trial_survival(stim_data, config.cond_labels, config.censor_path, config.tr, logger)

    # Warn for conditions with few but sufficient surviving trials
    for cond, n_surv in trial_survival.items():
        if 2 <= n_surv < _TRIALS_FEW_THRESHOLD:
            graded_warning(
                logger, 'medium', 'TRIALS_FEW',
                f"Condition '{cond}' has only {n_surv} surviving trial(s) after censoring "
                f"(below advisory threshold of {_TRIALS_FEW_THRESHOLD}).",
                user_facing=True,
            )

    # Filter conditions by survival (minimum 2 trials required for AFNI estimation)
    original_conds = list(config.cond_labels)
    config.cond_labels = [c for c in original_conds if trial_survival.get(c, 0) >= 2]
    dropped_conds = [c for c in original_conds if c not in config.cond_labels]

    if dropped_conds:
        graded_warning(
            logger, 'medium', 'COND_DROPPED',
            f"Conditions with insufficient surviving trials (< 2) dropped: {dropped_conds}",
            user_facing=True,
        )

    if not config.cond_labels:
        raise ModelError("No task conditions have sufficient surviving trials. Analysis aborted.")

    # Update contrast functions if any conditions were dropped
    if config.contrast_functions and dropped_conds:
        valid_contrasts = []
        valid_labels = []
        for i, cont in enumerate(config.contrast_functions):
            if any(c in dropped_conds for c in cont["CONDS"]):
                graded_warning(
                    logger, 'medium', 'CONTRAST_DROPPED',
                    f"Contrast '{config.contrast_labels[i]}' depends on dropped conditions "
                    f"{[c for c in cont['CONDS'] if c in dropped_conds]} and will be skipped.",
                    user_facing=True,
                )
            else:
                valid_contrasts.append(cont)
                valid_labels.append(config.contrast_labels[i])
        config.contrast_functions = valid_contrasts
        config.contrast_labels = valid_labels

    # Write onset files now that cond_labels reflects only surviving conditions
    write_stim_onset_files(stim_data, config, logger)

    # Pre-flight DOF check
    n_regressors = use_cols + len(config.cond_labels)
    if config.CSF_path is not None:
        n_regressors += 1
    if config.WM_path is not None:
        n_regressors += 1
    if config.use_tissue_derivs:
        if config.CSF_path is not None:
            n_regressors += 1
        if config.WM_path is not None:
            n_regressors += 1
    dof = compute_dof(config.censor_path, n_regressors, logger, tr=config.tr)

    # Build QC summary data
    qc_data = {
        "analysis_type": "task_act",
        "hrf_model": config.hrf_model if config.hrf_model != "custom" else f"custom ({config.custom_hrf})",
        "fd_threshold": config.fd_threshold,
        "censor_prev_tr": config.censor_prev_tr,
    }
    try:
        censor_data = np.loadtxt(config.censor_path)
        qc_data["n_trs_total"] = len(censor_data)
        qc_data["n_trs_censored"] = int(np.sum(censor_data == 0))
        qc_data["pct_censored"] = round(100.0 * qc_data["n_trs_censored"] / qc_data["n_trs_total"], 2) if qc_data["n_trs_total"] > 0 else 0.0
    except Exception:
        pass
    qc_data["per_condition_trial_counts"] = {c: int(len(stim_data[stim_data['trial_type'] == c])) for c in config.cond_labels}
    qc_data["per_condition_surviving_trials"] = trial_survival
    qc_data["dof"] = dof

    # Warn if censoring rate exceeds the high threshold
    if qc_data.get("pct_censored", 0.0) > CENSOR_HIGH_THRESHOLD:
        graded_warning(
            logger, 'high', 'CENSOR_HIGH',
            f"Censoring rate ({qc_data['pct_censored']:.1f}%) exceeds the {CENSOR_HIGH_THRESHOLD}% threshold.",
            user_facing=True,
        )

    # Run activation first-level analysis
    run_first_level(stim_data, config, logger)

    # Generate bucket stats sub-brick index
    bucket_stats_index_path = generate_bucket_stats_index(config, logger)

    # Run stat bucket extraction if indicated
    extraction_files = []
    if config.stat_buckets:
        extraction_files = extract_stat_buckets(config, logger)

    # Write QC summary
    write_qc_summary(config.out_dir, config.out_file_pre, qc_data, logger)

    # Collect output file paths
    output_files: list[str] = []
    psc_out = os.path.join(config.out_dir, f"{config.out_file_pre}_psc.nii.gz")
    if os.path.exists(psc_out):
        output_files.append(psc_out)
    bucket_path = f"{config.out_dir}/{config.out_file_pre}_concat_bucket_stats.nii.gz"
    resids_path = f"{config.out_dir}/{config.out_file_pre}_concat_bucket_resids.nii.gz"
    if os.path.exists(bucket_path):
        output_files.append(bucket_path)
    if os.path.exists(resids_path):
        output_files.append(resids_path)
    if os.path.exists(bucket_stats_index_path):
        output_files.append(bucket_stats_index_path)
    output_files.extend(extraction_files)
    qc_path = os.path.join(config.out_dir, f"{config.out_file_pre}_qc_summary.json")
    if os.path.exists(qc_path):
        output_files.append(qc_path)

    # Determine overall result status
    status = "warning" if any(w.get("severity") == "high" for w in get_warnings()) else "success"

    return FirstLevelResult(
        status=status,
        output_dir=Path(config.out_dir),
        warnings=get_warnings(),
        qc_summary=qc_data,
        output_files=output_files,
    )
