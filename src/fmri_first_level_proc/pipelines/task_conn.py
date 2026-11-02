#!/usr/bin/env python3

# ============================================================================
# TASK-BASED fMRI FIRST-LEVEL AND FUNCTIONAL CONNECTIVITY ANALYSIS
# 1. Creates task design matrix (including denoising and censoring) with AFNI's 3dDeconvolve
# 2. Creates full-task beta series with AFNI's 3dLSS
# 3. Creates task condition-specific beta series with AFNI's 3dcalc
# 4. (optional) Extract parcel-level/ROI condition beta series with a provided template
# 5. (optional) Runs functional connectivity analysis for available beta series with AFNI's 3dNetCorr
#
# Author: Taylor J. Keding, Ph.D.
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
--cond_beta_labels: list (comma-separated) of task conditions to generate beta series for - all labels should match to rows in the 'CONDITION' column from the timing file
    format = string-list of conditions e.g. 'stimFear,stimSad,stimNeu'
--out_dir: global directory path for derivative intermediates and task-condition beta series; will create if doesn't exist
--out_file_pre: prefix to be prepended to the files stored in out_dir (should usually contain an ID, task name, time point, etc. but NOT the global file path; eg. 'subj001_nback_baseline')
--num_cores: number of CPU cores available for parallel processing (int; defaults to 1)

(optional)
--hrf_model: HRF basis function model to use (default: 'GAM'). Options: 'GAM', 'BLOCK', 'dmBLOCK', 'SPMG1', 'custom'
--custom_hrf: custom AFNI HRF model string (only used when hrf_model='custom', e.g. 'TENT(0,14,8)')
--CSF_path: global file path to the run-concatenated cerebrospinal fluid BOLD signal time series
    format = string(path_to_txt); no headers; rows=TR/frame, single column = mean CSF signal
--WM_path: global file path to the run-concatenated white-matter BOLD signal time series
    format = string(path_to_txt); no headers; rows=TR/frame, single column = mean WM signal
--use_tissue_derivs: (no value) include this option to add first temporal derivatives of tissue signals (CSF/WM) as additional nuisance regressors; only computed for tissue paths that are provided
--remove_previous: (no value) include this option if "out_dir" should have all files removed before processing starts (including connectivity); if not included, will not overwrite pre-existing files
--extract_pbseries: include this option if you want condition-specific beta series extracted for parcels/ROIs (requires --template_path be provided)
--average_type: either "mean" or "median" - the type of averaging used when calculating average parcel beta series
--extract_out_file_pre: if --extract_pbseries is included, the prefix to attach to the extracted pbseries (should NOT include the file path or task condition; similar to --out_file_pre e.g. 'subj001_nback_baseline_Shen368_WB')
--calc_conn: either 'seed_to_voxel' or 'parcellated'; included if functional connectivity should be calculated with the given approach
--conn_out_file_pre: if --calc_conn is included with a valid option, the prefix to attach to connectivity output files (should NOT include the file path or task condition; similar to --out_file_pre e.g. 'subj001_nback_baseline_R_amyg_wholeBrain')
--template_path: template file for --extract_pbseries and/or the option specified in --calc_conn.
    For extract_pbseries, can be a binary mask (only a single pbseries will be output) or a set of N ROIs/masks indicated by unique integers>0 (N pbseries will be output per task condition)
    For calc_conn, if 'seed_to_voxel', should be a binary mask with a single ROI; if 'parcellated', should be a set of ROIs (at least 2 required, each labeled with a unique integer>0)
    format = string(path_to_nii) (volumetric and registered to the same atlas as task beta series, unless --force_diff_atlas used; if there is a mismatch in grid spacing, will resample the template to the beta series grid)
--force_diff_atlas: (no value) include this option if you know the template and scan are in different standard spaces, but want to force connectivity analyses anyway (USE WITH CAUTION)
--pcorr: (no value) include this option to use partial correlation instead of standard correlation for functional connectivity
--fishZ: (no value) include this option if correlation 'r' should be Fisher-transformed into z-scores

OUTPUTS:
(always)
{out_dir}/{out_file_pre}_concat_{condition}_onsets.txt: AFNI-safe version of timing onsets for task conditions NOT included in --cond_beta_labels (1D single column with no headers or row names)
{out_dir}/{out_file_pre}_concat_beta_onsets.txt: AFNI-safe version of timing onsets for task conditions to calculate beta series for (1D single column with no headers or row names)
{out_dir}/{out_file_pre}_concat_bseries_dmat.x1D: AFNI-safe design matrix for the task fMRI beta series first-level analysis
{out_dir}/{out_file_pre}_concat_LSS.nii.gz: first-level output beta series for the entire task (subbrik = stim, in the order they were presented in ..beta_onsets.txt)
{out_dir}/{out_file_pre}_concat_LSS.1d: same as "...concat_LSS.nii.gz", but in text file format (not much space and may be useful later)
{out_dir}/{out_file_pre}_concat_bseries_{condition}.nii.gz: first-level output task condition-specific beta series (in the order they were presented in ..beta_onsets.txt)

(optional)
--extract_pbseries:
    {out_dir}/{extract_out_file_pre}_pbseries_{condition}.csv: condition-specific beta series averaged by masks in --template_path;
        Rows correspond to the TR/frame (no column/header for TR/frame) and columns are unique masks/ROIs (e.g. "ROI_1" for mask_value == 1)
--calc_conn 'parcellated':
{out_dir}/{conn_out_file_pre}_{condition}_{fishZ}_{pcorr}_mat.txt: Square, task condition-specific functional connectivity matrix for the ROIs contained in --template_path;
    Row/column numbers correspond to the ROI integers from the template (i.e. cell {1,2} is connectivity between ROI_label=1 and ROI_label=2)
--calc_conn 'seed_to_voxel':
{out_dir}/{conn_out_file_pre}_{condition}_{fishZ}_{pcorr}.nii.gz: .nii file containing voxelwise, task condition-specific functional connectivity from seed contained in --template_path
'''

# Imports
import copy
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from ..afni import clean_deconvolve_err, run_afni_command
from ..config import ResolvedConfig
from ..connectivity import (
    build_conn_output_path,
    compute_matrix_contrast,
    parcellated_conn,
    seed_to_voxel_conn,
)
from ..design import (
    HRF_DURATION_MODELS,
    build_decon_base_command,
    build_hrf_string,
    check_trial_survival,
    compute_dof,
    log_hrf_model,
    log_nuisance_model,
    needs_married_timing,
    read_and_validate_stim_data,
    valid_contrast_functions,
    write_onset_file,
)
from ..exceptions import ConfigError, InputError, ModelError, ToolExecutionError
from ..fileutils import remove_files_from_dir, sanitize_filename_label
from ..preprocessing import (
    CENSOR_HIGH_THRESHOLD,
    compute_tissue_derivative,
    create_censor_file,
    gen_min_outlier_epi,
    prepare_motion_file,
    scale_to_psc,
)
from ..reporting import (
    FirstLevelResult,
    clear_warnings,
    get_warnings,
    graded_warning,
    setup_logging,
    write_qc_summary,
)
from ..templates import (
    extract_roi_stats,
    validate_connectivity_options,
    validate_extract_options,
    validate_template,
)

def read_stim_data(config: ResolvedConfig, logger):
    """Read and validate stimulus timing data for the task connectivity pipeline.

    Reads and validates the timing CSV without writing any onset files. Separating
    the read phase from the write phase allows trial-survival filtering to be applied
    before onset files are written, ensuring dropped conditions receive individual
    nuisance onset files rather than being silently omitted.

    Parameters
    ----------
    config : ResolvedConfig
        Must include: task_timing_path, cond_beta_labels.
    logger : logging.Logger

    Returns
    -------
    pd.DataFrame
        Sorted timing data with trial_type, onset, duration columns (BIDS naming).
    """
    return read_and_validate_stim_data(config.task_timing_path, config.cond_beta_labels, logger=logger)


def write_stim_onset_files(stim_data, config: ResolvedConfig, logger):
    """Write AFNI-format onset files for the task connectivity pipeline.

    Must be called after trial-survival filtering so that config.cond_beta_labels
    reflects only surviving conditions. Conditions present in stim_data but NOT
    in config.cond_beta_labels receive individual onset files (nuisance regressors
    in 3dDeconvolve). Conditions IN config.cond_beta_labels are accumulated into a
    single combined onset file for 3dLSS (-stim_times_IM).

    The combined beta onset file accumulates trials in first-appearance order
    (pandas .unique() traversal of stim_data). This order is returned as
    beta_cond_order and must be used in gen_beta_series() to correctly map
    sub-brick indices to conditions.

    Parameters
    ----------
    stim_data : pd.DataFrame
        Sorted timing data with trial_type, onset, duration columns (BIDS naming).
    config : ResolvedConfig
        Must include: cond_beta_labels, out_dir, out_file_pre, hrf_model, custom_hrf.
    logger : logging.Logger

    Returns
    -------
    list of str
        beta_cond_order: conditions whose onsets were appended to beta_onsets.txt,
        in the order they were appended (i.e., the order sub-bricks appear in the
        3dLSS output).
    """
    betas_onsets = None
    betas_durations = None
    beta_cond_order = []

    out_dir = Path(config.out_dir)

    # Iterate conditions in first-appearance order (matches 3dLSS sub-brick layout)
    for cond in stim_data['trial_type'].unique():
        cond_df = stim_data[stim_data['trial_type'] == cond]

        # Conditions not in cond_beta_labels become individual nuisance onset files
        if cond not in config.cond_beta_labels:
            onset_file = out_dir / f"{config.out_file_pre}_concat_{cond}_onsets.txt"
            write_onset_file(cond_df, onset_file, config.hrf_model, config.custom_hrf, logger=logger)
        # Beta conditions are accumulated into a single combined onset file
        else:
            if betas_onsets is None:
                betas_onsets = list(cond_df['onset'])
                betas_durations = list(cond_df['duration'])
            else:
                betas_onsets.extend(cond_df['onset'])
                betas_durations.extend(cond_df['duration'])
            beta_cond_order.append(cond)

    betas_df = pd.DataFrame({'onset': betas_onsets, 'duration': betas_durations})
    beta_onset_file = out_dir / f"{config.out_file_pre}_concat_beta_onsets.txt"
    write_onset_file(betas_df, beta_onset_file, config.hrf_model, config.custom_hrf, logger=logger)

    return beta_cond_order

def gen_design_matrix(stim_data, config: ResolvedConfig, logger):
    """Build the 3dDeconvolve design matrix for LSS beta series estimation.

    Creates nuisance regressors for non-beta conditions and a combined -stim_times_IM
    regressor for all beta conditions. The matrix is written to disk as an .x1D file
    using 3dDeconvolve -x1D_stop (no output statistics dataset). Skips if the design
    matrix file already exists.

    Parameters
    ----------
    stim_data : pd.DataFrame
        Timing data from read_stim_data.
    config : ResolvedConfig
        Must include: scan_path, censor_path, motion_path, CSF_path, WM_path,
        CSF_deriv_path (if use_tissue_derivs), out_dir, out_file_pre, hrf_model,
        custom_hrf, cond_beta_labels, num_cores, tr.
    logger : logging.Logger
    """
    out_dir = Path(config.out_dir)
    dmat_path = out_dir / f"{config.out_file_pre}_concat_bseries_dmat.x1D"

    # Check if output already exists
    if not dmat_path.exists():

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
        decon_command.extend(["-num_stimts", f"{1+len(stim_data['trial_type'].unique())-len(config.cond_beta_labels)}"])

        # Iteratively add stim timing for conditions NOT included in beta series
        stim_count = 1
        for cond in stim_data['trial_type'].unique():
            if cond not in config.cond_beta_labels:
                mean_dur = None
                if config.hrf_model in HRF_DURATION_MODELS:
                    mean_dur = np.mean(stim_data[stim_data['trial_type'] == cond]['duration'])
                hrf_string = build_hrf_string(config.hrf_model, mean_dur=mean_dur, custom_hrf=config.custom_hrf)
                stim_flag = "-stim_times_AM1" if needs_married_timing(config.hrf_model, config.custom_hrf) else "-stim_times"
                decon_command.extend([stim_flag, f"{stim_count}", out_dir / f"{config.out_file_pre}_concat_{cond}_onsets.txt",
                                     hrf_string, "-stim_label", f"{stim_count}", f"{cond}"])
                stim_count += 1

        # Add stimtimes IM for conditions included in beta series
        # 3dLSS requires -stim_times_IM; config validation rejects married-timing
        # HRFs (e.g. dmBLOCK) that would require -stim_times_AM1.
        mean_dur = None
        if config.hrf_model in HRF_DURATION_MODELS:
            mean_dur = np.mean(stim_data[stim_data['trial_type'].isin(config.cond_beta_labels)]['duration'])
        hrf_string = build_hrf_string(config.hrf_model, mean_dur=mean_dur, custom_hrf=config.custom_hrf)
        beta_stim_flag = "-stim_times_IM"
        decon_command.extend([beta_stim_flag, f"{stim_count}", out_dir / f"{config.out_file_pre}_concat_beta_onsets.txt",
                              hrf_string, "-stim_label", f"{stim_count}", "beta_stims",
                              "-x1D", dmat_path,
                              "-x1D_stop", "-nobucket", "-jobs", f"{config.num_cores}"])

        # Run command and be sure we have output
        run_afni_command(decon_command, description="3dDeconvolve design matrix", logger=logger)

        if dmat_path.exists():
            logger.info("Successfully created design matrix %s_concat_bseries_dmat.x1D", config.out_file_pre)
        else:
            logger.error("Failed to create design matrix %s_concat_bseries_dmat.x1D", config.out_file_pre)
            raise ToolExecutionError(
                f"Failed to create design matrix {config.out_file_pre}_concat_bseries_dmat.x1D"
            )
    else:
        logger.info("Design matrix for %s already exists.", config.out_file_pre)

    # Remove err file that always seems to be output
    clean_deconvolve_err(config.out_dir)

def gen_beta_series(stim_data, config: ResolvedConfig, beta_cond_order, logger):
    """Generate the full-task LSS beta series and condition-specific beta volumes.

    Runs 3dLSS on the design matrix to produce the full-task beta series NIfTI
    (one sub-brick per trial), then extracts condition-specific sub-bricks via 3dcalc
    for each condition in beta_cond_order.

    Sub-brick indices are computed by iterating beta_cond_order — the same order
    in which condition onsets were appended to beta_onsets.txt by
    write_stim_onset_files(). This guarantees that total_used correctly tracks
    cumulative trial counts regardless of alphabetical vs. first-appearance ordering.

    Parameters
    ----------
    stim_data : pd.DataFrame
        Timing data from read_stim_data.
    config : ResolvedConfig
        Must include: out_dir, out_file_pre, scan_path, cond_beta_labels.
    beta_cond_order : list of str
        Conditions in the order their onsets were written to beta_onsets.txt
        (returned by write_stim_onset_files). Determines sub-brick mapping.
    logger : logging.Logger

    Returns
    -------
    dict
        {'CONDITION': list of str, 'PATH': list of str} with successfully created
        condition-specific beta series.
    """
    out_dir = Path(config.out_dir)
    lss_path = out_dir / f"{config.out_file_pre}_concat_LSS.nii.gz"

    # Check if full-task beta series already exists
    if not lss_path.exists():

        # Build the 3dLSS command and create full-task beta series
        lss_command = ["3dLSS", "-matrix", out_dir / f"{config.out_file_pre}_concat_bseries_dmat.x1D",
                       "-input", config.scan_path,
                       "-save1D", out_dir / f"{config.out_file_pre}_concat_LSS.1d",
                       "-prefix", lss_path]
        run_afni_command(lss_command, description="3dLSS beta series", logger=logger)

        if lss_path.exists():
            logger.info("Successfully created full-task beta series for %s", config.out_file_pre)
        else:
            logger.error("Failed to create full-task beta series for %s", config.out_file_pre)
            raise ToolExecutionError(
                f"Failed to create full-task beta series for {config.out_file_pre}"
            )
    else:
        logger.info("%s already exists", lss_path)

    # Iterate beta conditions in the exact order onsets were written to beta_onsets.txt.
    # This ensures total_used correctly maps to 3dLSS sub-brick indices.
    bseries_out = {"CONDITION": [], "PATH": []}
    total_used = 0
    for curr_cond in beta_cond_order:

        # Get onset times for the condition
        cond = stim_data[stim_data['trial_type'] == curr_cond]['onset']
        bseries_path = out_dir / f"{config.out_file_pre}_concat_bseries_{curr_cond}.nii.gz"

        # Check if condition-specific beta series already exists
        if not bseries_path.exists():

            # Sub-brick selector for this condition's trials, e.g. "[6,7,8]"
            calc_indices_str = "[" + ",".join(str(total_used + n) for n in range(len(cond))) + "]"

            # Build the 3dcalc command and create task condition beta series
            calc_command = ["3dcalc", "-a", f"{lss_path}{calc_indices_str}",
                            "-expr", "a",
                            "-prefix", bseries_path]
            run_afni_command(calc_command, description=f"3dcalc beta series {curr_cond}", logger=logger)

            if bseries_path.exists():
                logger.info("Successfully created beta series %s", bseries_path.name)
                bseries_out['CONDITION'].append(curr_cond)
                bseries_out["PATH"].append(bseries_path)
            else:
                logger.warning("Failed to create beta series %s", bseries_path.name)
                logger.warning("Continuing to see if beta series can be created for other task conditions.")
        else:
            logger.info("Beta series %s already exists.", bseries_path.name)
            bseries_out['CONDITION'].append(curr_cond)
            bseries_out["PATH"].append(bseries_path)

        total_used += len(cond)

    # Something went wrong if our output is empty
    if len(bseries_out["CONDITION"]) == 0:
        logger.error("Could not find or create any beta series for %s.", config.out_file_pre)
        raise ToolExecutionError(
            f"Could not find or create any beta series for {config.out_file_pre}."
        )

    # Return dictionary with those conditions for which we've successfully created beta series
    return bseries_out

def gen_pbseries(bseries_info, config: ResolvedConfig, logger):
    """Extract ROI-level parcel beta series for each condition.

    For each condition with a beta series NIfTI, calls extract_roi_stats to
    average beta values per ROI/parcel using the provided template, and saves
    the result as a CSV. Skips conditions where the output already exists.

    Parameters
    ----------
    bseries_info : dict
        {'CONDITION': list of str, 'PATH': list of str} from gen_beta_series.
    config : ResolvedConfig
        Must include: out_dir, extract_out_file_pre, template_path, average_type.
    logger : logging.Logger
    """
    # Iterate available condition-specific beta series
    for i, cond in enumerate(bseries_info['CONDITION']):
        pbseries_path = Path(config.out_dir) / f"{config.extract_out_file_pre}_pbseries_{cond}.csv"

        # Check if output already exists
        if not pbseries_path.exists():

            new_df = extract_roi_stats(bseries_info['PATH'][i], config.template_path, config.average_type, logger=logger)

            # Save pbseries
            new_df.to_csv(pbseries_path)
            if pbseries_path.exists():
                logger.info("Successfully extracted pbseries from %s using ROI template.", bseries_info['PATH'][i])
            else:
                logger.error("Could not extract pbseries from %s using ROI template.", bseries_info['PATH'][i])
                raise InputError(
                    f"Could not extract pbseries from {bseries_info['PATH'][i]} using ROI template."
                )
        else:
            logger.info("%s already exists (skipping).", pbseries_path)

def gen_conn(bseries_info, config: ResolvedConfig, logger):
    """Compute condition-specific functional connectivity from task beta series.

    Iterates over each condition in bseries_info and dispatches to either
    parcellated_conn (ROI-to-ROI matrix) or seed_to_voxel_conn (whole-brain map)
    based on config.calc_conn.

    Parameters
    ----------
    bseries_info : dict
        {'CONDITION': list of str, 'PATH': list of str} from gen_beta_series.
    config : ResolvedConfig
        Must include: calc_conn, out_dir, conn_out_file_pre, template_path,
        fishZ, pcorr.
    logger : logging.Logger
    """
    # Iterate task conditions with beta series
    for i, cond in enumerate(bseries_info['CONDITION']):

        # Run connectivity analyses based on the specified flavor
        if config.calc_conn == "parcellated":
            parcellated_conn(
                inset_path=bseries_info['PATH'][i],
                out_dir=config.out_dir,
                conn_out_file_pre=config.conn_out_file_pre,
                template_path=config.template_path,
                fishZ=config.fishZ,
                pcorr=config.pcorr,
                condition=cond,
                logger=logger,
            )
        else:
            seed_to_voxel_conn(
                inset_path=bseries_info['PATH'][i],
                out_dir=config.out_dir,
                conn_out_file_pre=config.conn_out_file_pre,
                template_path=config.template_path,
                fishZ=config.fishZ,
                pcorr=config.pcorr,
                condition=cond,
                logger=logger,
            )

def gen_conn_contrasts(bseries_info, parsed_contrasts, contrast_labels, config: ResolvedConfig, logger):
    """Generate connectivity contrasts from condition-level connectivity outputs.

    For each contrast, validates that all referenced conditions have connectivity
    output files on disk, then computes the weighted linear combination for
    parcellated (matrix) and/or seed-to-voxel (NIfTI) connectivity outputs.

    Parameters
    ----------
    bseries_info : dict
        Dictionary with 'CONDITION' and 'PATH' lists from gen_beta_series.
    parsed_contrasts : list of dict
        Output of valid_contrast_functions — list of {'COEFS': [...], 'CONDS': [...]}.
    contrast_labels : list of str
        User-specified labels for each contrast.
    config : ResolvedConfig
        Pipeline config (must include calc_conn, conn_out_file_pre, fishZ, pcorr, out_dir).
    logger : logging.Logger
    """
    available_conds = set(bseries_info['CONDITION'])

    for ci, (contrast, label) in enumerate(zip(parsed_contrasts, contrast_labels)):
        safe_label = sanitize_filename_label(label)
        coefs = contrast['COEFS']
        conds = contrast['CONDS']

        # Validate all referenced conditions have connectivity output
        missing = []
        cond_conn_paths = []
        for cond in conds:
            if cond not in available_conds:
                missing.append(cond)
                cond_conn_paths.append(None)
                continue
            cond_path = build_conn_output_path(
                config.out_dir, config.conn_out_file_pre, cond,
                config.fishZ, config.pcorr, config.calc_conn)
            if not cond_path.exists():
                missing.append(cond)
            cond_conn_paths.append(cond_path)

        if missing:
            logger.error("Connectivity contrast '%s': missing connectivity output for "
                         "conditions %s. Skipping this contrast.", label, missing)
            continue

        # Build contrast output path
        contrast_conn_path = build_conn_output_path(
            config.out_dir, config.conn_out_file_pre, safe_label,
            config.fishZ, config.pcorr, config.calc_conn)

        if contrast_conn_path.exists():
            logger.info("Connectivity contrast '%s' already exists at %s.", label, contrast_conn_path)
            continue

        if config.calc_conn == "parcellated":
            compute_matrix_contrast(cond_conn_paths, coefs, contrast_conn_path, logger)
            logger.info("Parcellated connectivity contrast '%s' saved to %s.", label, contrast_conn_path)
        else:
            # seed_to_voxel: use 3dcalc with single-letter identifiers
            if len(conds) > 26:
                logger.error("Connectivity contrast '%s' references %d conditions, "
                             "but 3dcalc supports at most 26 single-letter identifiers.",
                             label, len(conds))
                continue

            letters = [chr(ord('a') + i) for i in range(len(conds))]

            calc_cmd = ["3dcalc"]
            for letter, path in zip(letters, cond_conn_paths):
                calc_cmd.extend([f"-{letter}", path])

            # Build expression: coef_a*a+coef_b*b+...
            expr_parts = []
            for coef_str, letter in zip(coefs, letters):
                expr_parts.append(f"{coef_str}*{letter}")
            # Join with implicit sign handling (coefs already contain signs)
            expr = expr_parts[0]
            for part in expr_parts[1:]:
                if part[0] in ('+', '-'):
                    expr += part
                else:
                    expr += '+' + part

            calc_cmd.extend(["-expr", expr, "-prefix", contrast_conn_path])
            run_afni_command(calc_cmd, description=f"3dcalc connectivity contrast {label}", logger=logger)

            if contrast_conn_path.exists():
                logger.info("Seed-to-voxel connectivity contrast '%s' saved to %s.", label, contrast_conn_path)
            else:
                logger.error("Failed to create seed-to-voxel connectivity contrast '%s'.", label)


def run(config: ResolvedConfig, logger: logging.Logger | None = None) -> FirstLevelResult:
    """Validate config and execute the task connectivity pipeline.

    Orchestrates the full task_conn pipeline in the following order:
    1. Validate extraction and connectivity arguments.
    2. Optionally clear out_dir (if remove_previous is set).
    3. Validate extraction and connectivity template options.
    4. Optionally extract pre-regression parcellated time series (extract_raw_ptseries).
    5. Extract minimum-outlier EPI frame (gen_min_outlier_epi; mandatory).
    6. Generate motion censor file from motion_path and fd_threshold.
    7. Prepare motion regressors (truncate to required columns).
    8. Read and validate stimulus timing data (read_stim_data).
    9. Parse contrast functions using the full original condition list
       (parse-then-drop: ensures contrast CONDS dict is valid before filtering).
    10. Check per-condition trial survival after censoring.
    11. Filter conditions with fewer than 2 surviving trials (warn and drop).
    12. Drop contrasts that reference dropped conditions.
    13. Write AFNI onset files (write_stim_onset_files); returns beta_cond_order
        (first-appearance order of conditions in beta_onsets.txt).
    14. Pre-flight DOF check.
    15. Build 3dDeconvolve design matrix (gen_design_matrix).
    16. Generate full-task and condition-specific beta series via 3dLSS (gen_beta_series),
        using beta_cond_order to correctly map sub-bricks to conditions.
    17. Optionally extract parcel beta series (gen_pbseries).
    18. Optionally compute functional connectivity (gen_conn).
    19. Optionally compute connectivity contrasts (gen_conn_contrasts).
    20. Write QC summary JSON.

    Works from the config-driven dispatch runner
    (cli.py / DISPATCH["task_conn"]).

    Parameters
    ----------
    config : ResolvedConfig
        All pipeline parameters (see config.py for the full attribute list).
    logger : logging.Logger or None
        If None, a default logger named 'task_conn_first_level' is created.

    Returns
    -------
    FirstLevelResult
        Structured result with status, output_dir, warnings, qc_summary, and
        output_files.
    """
    if logger is None:
        logger = setup_logging("task_conn_first_level")

    config = copy.copy(config)
    clear_warnings()

    logger.info("Beta series will be created for the following task conditions: %s", config.cond_beta_labels)
    logger.info("All other task conditions will be controlled for, but won't have betas modeled.")
    log_hrf_model(config.hrf_model, config.custom_hrf, logger)
    log_nuisance_model(config.CSF_path, config.WM_path, logger, use_tissue_derivs=config.use_tissue_derivs)

    # If --remove_previous is provided, clear-out the output dir (before template
    # resampling or any other file creation in out_dir)
    if config.remove_previous:
        logger.info("Removing all files from previous analyses in %s (if they exist).", config.out_dir)
        remove_files_from_dir(config.out_dir, logger=logger)

    # Make sure optional args exist if --extract_pbseries is provided
    if config.extract_pbseries:
        config.template_path = validate_extract_options(
            "--extract_pbseries", config.average_type, config.extract_out_file_pre,
            config.template_path, config.scan_path, config.out_dir, config.force_diff_atlas,
            logger=logger)

    # Make sure optional args exist if --calc_conn is provided
    if config.calc_conn is not None:
        config.template_path = validate_connectivity_options(
            config.calc_conn, config.conn_out_file_pre, config.template_path,
            config.scan_path, config.out_dir, config.force_diff_atlas,
            data_label="task beta series", logger=logger)
    else:
        logger.info("Connectivity will not be output after generating task beta series.")

    # Extract pre-regression parcellated time series if requested
    if getattr(config, 'extract_raw_ptseries', False):
        if config.extract_out_file_pre is None:
            logger.error("extract_raw_ptseries requires extract_out_file_pre to be set.")
            raise ConfigError("extract_raw_ptseries requires extract_out_file_pre to be set.")
        raw_out = Path(config.out_dir) / f"{config.extract_out_file_pre}_raw_ptseries.csv"
        if not raw_out.exists():
            if config.template_path is None:
                logger.error("extract_raw_ptseries requires a valid template_path.")
                raise ConfigError("extract_raw_ptseries requires a valid template_path.")
            validated_tpl = validate_template(config.scan_path, config.template_path,
                config.out_dir, config.force_diff_atlas, conn_type="extract", logger=logger)
            raw_df = extract_roi_stats(config.scan_path, validated_tpl, config.average_type, logger=logger)
            raw_df.to_csv(raw_out)
            if raw_out.exists():
                logger.info("Extracted raw (pre-regression) ptseries to %s.", raw_out)
            else:
                logger.error("Failed to extract raw ptseries.")
                raise ToolExecutionError("Failed to extract raw ptseries.")
        else:
            logger.info("Raw ptseries already exists: %s", raw_out)

    # ---------------------------------

    # Extract minimum-outlier representative EPI frame (mandatory, before regression)
    gen_min_outlier_epi(config.scan_path, config.out_dir, config.out_file_pre, "", logger)

    # PSC scaling (after min-outlier EPI, before regression)
    if config.scale_to_psc:
        psc_path = scale_to_psc(
            config.scan_path, config.out_dir, config.out_file_pre, "", logger)
        config.scan_path = str(psc_path)

    # Generate censor file from motion regressors (before prepare_motion_file overwrites path)
    config.censor_path = str(create_censor_file(
        config.motion_path, config.fd_threshold, config.censor_prev_tr,
        config.out_dir, config.out_file_pre, "concat", logger))

    # Validate and prepare motion regressors
    use_cols = 12 if config.include_motion_derivs else 6
    config.motion_path = str(prepare_motion_file(
        config.motion_path, use_cols, config.out_dir, config.out_file_pre, "concat", logger))



    # Read and validate stimulus timing data (no file I/O yet)
    stim_data = read_stim_data(config, logger)

    # Contrast-related checks
    if config.contrast_labels is not None:
        if config.contrast_functions is None:
            logger.error("--contrast_functions must exist if --contrast_labels exist.")
            raise ConfigError("--contrast_functions must exist if --contrast_labels exist.")
    else:
        if config.contrast_functions is not None:
            logger.error("--contrast_labels must exist if --contrast_functions exist.")
            raise ConfigError("--contrast_labels must exist if --contrast_functions exist.")

    # Per-condition trial survival QC
    trial_survival = check_trial_survival(stim_data, config.cond_beta_labels, config.censor_path, config.tr, logger)

    # Emit TRIALS_FEW warning for conditions with >=2 but <5 surviving trials
    for cond, n_surviving in trial_survival.items():
        if 2 <= n_surviving < 5:
            msg = (
                f"Condition '{cond}': only {n_surviving} trials survive censoring; "
                "estimates may be unreliable due to low trial count."
            )
            graded_warning(logger, 'medium', 'TRIALS_FEW', msg, user_facing=True)

    # Filter conditions by survival (minimum 2 trials required for AFNI estimation)
    original_conds = list(config.cond_beta_labels)

    # Parse contrast functions using the full original condition list before any filtering.
    # parse-then-drop ensures cont["CONDS"] is a valid dict when the drop block iterates.
    if config.contrast_functions is not None and config.contrast_labels is not None:
        config.contrast_functions = valid_contrast_functions(
            config.contrast_functions, config.contrast_labels,
            original_conds, logger=logger)

    config.cond_beta_labels = [c for c in original_conds if trial_survival.get(c, 0) >= 2]
    dropped_conds = [c for c in original_conds if c not in config.cond_beta_labels]

    if dropped_conds:
        for cond in dropped_conds:
            n = trial_survival.get(cond, 0)
            n_total = int(len(stim_data[stim_data['trial_type'] == cond]))
            msg = (
                f"Condition '{cond}' dropped: only {n} of {n_total} trials survive censoring "
                "(minimum 2 required for reliable estimation)."
            )
            graded_warning(logger, 'medium', 'COND_DROPPED', msg, user_facing=True)

    if not config.cond_beta_labels:
        logger.error("NO task conditions have sufficient surviving trials. Aborting analysis.")
        raise ModelError("NO task conditions have sufficient surviving trials. Aborting analysis.")

    # Update contrast functions if any conditions were dropped
    if config.contrast_functions and dropped_conds:
        valid_contrasts = []
        valid_labels = []
        for i, cont in enumerate(config.contrast_functions):
            if any(c in dropped_conds for c in cont["CONDS"]):
                dropped_in_contrast = [c for c in cont["CONDS"] if c in dropped_conds]
                msg = (
                    f"Contrast '{config.contrast_labels[i]}' depends on dropped conditions "
                    f"{dropped_in_contrast} and will be SKIPPED."
                )
                graded_warning(logger, 'medium', 'CONTRAST_DROPPED', msg, user_facing=True)
            else:
                valid_contrasts.append(cont)
                valid_labels.append(config.contrast_labels[i])
        config.contrast_functions = valid_contrasts
        config.contrast_labels = valid_labels

    # Write onset files now that cond_beta_labels reflects only surviving conditions.
    # Dropped conditions receive individual nuisance onset files; surviving conditions
    # are accumulated into beta_onsets.txt in first-appearance order.
    beta_cond_order = write_stim_onset_files(stim_data, config, logger)

    # Pre-flight DOF check (conservative lower bound — actual per-trial regressors are higher)
    n_regressors = use_cols + len(config.cond_beta_labels)
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
        "analysis_type": "task_conn",
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
    qc_data["per_condition_trial_counts"] = {c: int(len(stim_data[stim_data['trial_type'] == c])) for c in config.cond_beta_labels}
    qc_data["per_condition_surviving_trials"] = trial_survival
    qc_data["dof"] = dof

    # Emit CENSOR_HIGH warning if censoring exceeds threshold
    pct_censored = qc_data.get("pct_censored", 0.0)
    if pct_censored > CENSOR_HIGH_THRESHOLD:
        msg = (
            f"Censoring exceeds {CENSOR_HIGH_THRESHOLD}%: {pct_censored}% of TRs censored "
            f"({qc_data.get('n_trs_censored', 'N/A')} of {qc_data.get('n_trs_total', 'N/A')} TRs)."
        )
        graded_warning(logger, 'high', 'CENSOR_HIGH', msg, user_facing=True)

    # Generate task design matrix, including regressors for denoising, censoring, and stimulus timing
    gen_design_matrix(stim_data, config, logger)

    # Generate full task beta-series and condition-specific beta series
    bseries_out = gen_beta_series(stim_data, config, beta_cond_order, logger)

    # Extract pbseries if user provided option
    if config.extract_pbseries:
        gen_pbseries(bseries_out, config, logger)

    # Generate connectivity from task beta-series if user provided option
    if config.calc_conn is not None:
        gen_conn(bseries_out, config, logger)

    # Connectivity contrasts (config.contrast_functions already parsed above)
    if config.contrast_functions is not None and config.contrast_labels is not None:
        if config.calc_conn is not None:
            gen_conn_contrasts(bseries_out, config.contrast_functions, config.contrast_labels, config, logger)
            qc_data["contrast_labels"] = config.contrast_labels
        else:
            logger.warning("Contrasts specified but calc_conn is disabled — "
                           "connectivity contrasts require connectivity to be enabled. Skipping.")

    # Write QC summary
    write_qc_summary(config.out_dir, config.out_file_pre, qc_data, logger)

    # Collect deliverable output files
    out_dir = Path(config.out_dir)
    candidates = [
        out_dir / f"{config.out_file_pre}_psc.nii.gz",
        out_dir / f"{config.out_file_pre}_qc_summary.json",
        out_dir / f"{config.out_file_pre}_concat_LSS.nii.gz",
        out_dir / f"{config.out_file_pre}_concat_bseries_dmat.x1D",
        *bseries_out.get("PATH", []),
    ]
    output_files = [str(p) for p in candidates if p.exists()]

    # Determine final status
    status = "warning" if any(w.get("severity") == "high" for w in get_warnings()) else "success"

    return FirstLevelResult(
        status=status,
        output_dir=Path(config.out_dir),
        warnings=get_warnings(),
        qc_summary=qc_data,
        output_files=output_files,
    )
