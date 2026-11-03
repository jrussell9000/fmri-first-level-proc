#!/usr/bin/env python3

# ============================================================================
# RESTING-STATE fMRI FIRST-LEVEL AND FUNCTIONAL CONNECTIVITY ANALYSIS
# 1. First-level regression with AFNI's 3dTproject, creating residual dense time series
# 2. Note: Unlike task-based analyses, resting-state runs will NOT be concatenated
# 3. (optional) Extract parcel-level/ROI residual time series with a provided template
# 4. (optional) Runs functional connectivity analysis with AFNI's 3dNetCorr
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
-scan_paths: list of global file paths to the dense time series runs (preprocessed UP TO first-level analyses)
    format = list(string(path_to_nii)) (volumetric)
--motion_paths: list of global file paths of the run motion regressors (preprocessed UP TO first-level analyses)
    format = list(string(path_to_motion_txt)) (tab-delimited) with no headers; rows = TR/frame, columns = motion regressors (number of columns controlled by motion_deriv_degree: 6 * degree)
--censor_paths: list of global file paths of the motion/outlier censor files (should have been stripped for dummy scans)
    format = list(string(path_to_censor_txt)) (tab-delimited) with no headers; rows= TR/frame, single column = binary (1=include,0=exclude)
--CSF_paths: list of global file paths to the average cerebrospinal fluid BOLD signal time series
    format = list(string(path_to_CSF_TS_txt)); no headers; rows= TR/frame, single column = mean signal for frame
--WM_paths: list of global file paths to the average white-matter BOLD signal time series
    format = list(string(path_to_WM_TS_txt)); no headers; rows= TR/frame, single column = mean signal for frame
--out_dir: global directory path for derivative intermediates and task-condition beta series; will create if doesn't exist
--out_file_pre: prefix to be prepended to the files stored in out_dir (should usually contain an ID, task name, time point, etc. but NOT the global file path; eg. 'subj001_rest_baseline')
--num_cores: number of CPU cores available for parallel processing (int; defaults to 1)

(optional)
--GS_paths: list of global file paths to the average global BOLD signal time series (one per run); enables global signal regression (GSR)
    format = list(string(path_to_GS_TS_txt)); no headers; rows=TR/frame, single column = mean global signal for frame
    NOTE: GSR is controversial -- it can remove neural signal and introduce artifactual anti-correlations. Use with caution and report in methods.
--bandpass: bandpass filter frequencies [low high] in Hz (default: [0.01, 0.1]); set to null in YAML config to disable
--polort: 3dTproject -polort 2 when bandpass[0] > 0, else 1 + floor(run duration / 150 s), per run; sequenced backend: -polort -1, with 3dBandpass's quadratic detrend instead
--use_tissue_derivs: (no value) include this option to add first temporal derivatives of tissue signals (CSF/WM, and GS when enabled) as additional nuisance regressors
--remove_previous: (no value) include this option if "out_dir" should have all files removed before processing starts (including connectivity); if not included, will not overwrite pre-existing files
--extract_ptseries: include this option if you want residual time series extracted for parcels/ROIs (requires --template_path be provided)
--average_type: either "mean" or "median" - the type of averaging used when calculating average parcel residual time series
--extract_out_file_pre: if --extract_ptseries is included, the prefix to attach to the extracted ptseries (should NOT include the file path; similar to --out_file_pre e.g. 'subj001_rest_baseline_Shen368_WB')
--calc_conn: either 'seed_to_voxel' or 'parcellated'; included if functional connectivity should be calculated with the given approach
--conn_out_file_pre: if --calc_conn is included, the prefix to attach to connectivity output files (should NOT include the file path, task condition, or connectivity; similar to --out_file_pre e.g. 'subj001_rest_baseline_R_amyg_wholeBrain')
--template_path: template file for --extract_ptseries and/or the option specified in --calc_conn.
    For extract_ptseries, can be a binary mask (only a single ptseries will be output) or a set of N ROIs/masks indicated by unique integers>0 (N ptseries will be output)
    For calc_conn, if 'seed_to_voxel', should be a binary mask with a single ROI; if 'parcellated', should be a set of ROIs (at least 2 required, each labeled with a unique integer>0)
    format = .nii (volumetric and registered to the same atlas as task beta series, unless --force_diff_atlas used; if there is a mismatch in grid spacing, will resample the template to the beta series grid)
--force_diff_atlas: (no value) include this option if you know the template and scan are in different standard spaces, but want to force connectivity analyses anyway (USE WITH CAUTION)
--pcorr: (no value) include this option to use partial correlation instead of standard correlation for functional connectivity
--fishZ: (no value) include this option if correlation 'r' should be Fisher-transformed into z-scores
--keep_run_res_dtseries: (default True) keep per-run residual dtseries files after concatenation; use --no-keep_run_res_dtseries to remove them
--use_sequenced_bandpass: (no value) include this option to use the sequenced denoising path (interpolate censored TRs, bandpass-filter BOLD and nuisance separately, then regress nuisance) instead of the default simultaneous path. Reduces bandpass-implied regressor DOF cost.

OUTPUTS:
(always)
{out_dir}/{out_file_pre}_run{N}_residual_dtseries.nii.gz: first-level output residual dense time series by-run (removed if --no-keep_run_res_dtseries)
{out_dir}/{out_file_pre}_concat_residual_dtseries.nii.gz: first-level output concatenated residual dense time series

(optional)
--extract_ptseries:
    {out_dir}/{extract_out_file_pre}_residual_ptseries.csv: residual BOLD time series averaged by masks in --template_path;
        Rows correspond to the TR/frame (no column/header for TR/frame) and columns are unique masks/ROIs (e.g. "ROI_1" for mask_value == 1)
--calc_conn 'parcellated':
{out_dir}/{conn_out_file_pre}_{fishZ}_{pcorr}_mat.txt: Square, task condition-specific functional connectivity matrix for the ROIs contained in --template_path;
    Row/column numbers correspond to the ROI integers from the template (i.e. cell {1,2} is connectivity between ROI_label=1 and ROI_label=2)
--calc_conn 'seed_to_voxel':
{out_dir}/{conn_out_file_pre}_{fishZ}_{pcorr}.nii.gz: .nii file containing voxelwise functional connectivity from seed contained in --template_path
'''

# Imports
import copy
import logging
import shutil
from pathlib import Path

import numpy as np

from ..afni import parallel_map, run_afni_command, uses_num_cores
from ..manifest import manifested
from ..config import ResolvedConfig
from ..connectivity import parcellated_conn, seed_to_voxel_conn, seed_to_voxel_smoothed
from ..design import compute_dof
from ..exceptions import ConfigError, ModelError, ToolExecutionError
from ..fileutils import remove_files_from_dir, with_token
from ..inputs import check_inputs
from ..preprocessing import (
    CENSOR_METRIC,
    bandpass_filter_1d_afni,
    censor_interpolate_1d_afni,
    compute_tissue_derivative,
    create_censor_file,
    gen_min_outlier_epi,
    notch_filter_motion,
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
from ..smoothing import smooth_rest_runs, smoothing_token
from ..templates import (
    extract_roi_stats,
    validate_connectivity_options,
    validate_extract_options,
    validate_template,
)


def _run_residual_path(config, run_idx) -> Path:
    return Path(config.out_dir) / f"{config.out_file_pre}_run{run_idx+1}_residual_dtseries.nii.gz"


def _concat_residual_path(config) -> Path:
    return Path(config.out_dir) / f"{config.out_file_pre}_concat_residual_dtseries.nii.gz"


def _generate_run_residual_simultaneous(run_idx, run_scan, censor_path, prepared_motion, config, logger):
    """Generate per-run residual via simultaneous 3dTproject (regression + bandpass + censoring).

    Implements the default rest_conn denoising path: a single 3dTproject call with
    -ort regressors, -bandpass, -censor X.1D, -cenmode ZERO. Bandpass-implied
    sin/cos basis vectors are subsumed into the projection at the same step as
    nuisance regression.

    Parameters
    ----------
    run_idx : int
        Zero-based run index (used for logging and accessing per-run path lists).
    run_scan : str
        Path to the run's pre-residualisation dtseries.
    censor_path : str
        Path to the run's censor.1D file (binary 1=keep, 0=censor).
    prepared_motion : str
        Path to the run's prepared motion file (motion_deriv_degree*6 columns).
    config : ResolvedConfig
        Pipeline configuration. Must include CSF_paths, WM_paths, GS_paths,
        use_tissue_derivs, bandpass, out_dir,
        out_file_pre, tr.
    logger : logging.Logger

    Returns
    -------
    pathlib.Path or None
        Path to the run's residual dtseries, or None on 3dTproject failure.
    """
    run_out = _run_residual_path(config, run_idx)

    if run_out.exists():
        return run_out

    tproj_command = ["3dTproject", "-input", run_scan,
        "-dt", str(config.tr),
        "-censor", censor_path,
        "-cenmode", "ZERO",
        "-ort", prepared_motion,
        "-ort", config.CSF_paths[run_idx],
        "-ort", config.WM_paths[run_idx]]
    if config.GS_paths is not None:
        tproj_command.extend(["-ort", config.GS_paths[run_idx]])
    if config.use_tissue_derivs:
        csf_deriv = compute_tissue_derivative(config.CSF_paths[run_idx], config.out_dir, config.out_file_pre, f"run{run_idx+1}_CSF", logger)
        tproj_command.extend(["-ort", csf_deriv])
        wm_deriv = compute_tissue_derivative(config.WM_paths[run_idx], config.out_dir, config.out_file_pre, f"run{run_idx+1}_WM", logger)
        tproj_command.extend(["-ort", wm_deriv])
        if config.GS_paths is not None:
            gs_deriv = compute_tissue_derivative(config.GS_paths[run_idx], config.out_dir, config.out_file_pre, f"run{run_idx+1}_GS", logger)
            tproj_command.extend(["-ort", gs_deriv])
    n_trs = len(np.loadtxt(censor_path))
    tproj_command.extend(["-polort", str(_simultaneous_polort(n_trs, config))])
    if config.bandpass is not None:
        tproj_command.extend(["-bandpass", str(config.bandpass[0]), str(config.bandpass[1])])
    tproj_command.extend(["-prefix", run_out])

    try:
        run_afni_command(tproj_command, description=f"3dTproject run{run_idx+1}", logger=logger)
    except ToolExecutionError as e:
        logger.error("3dTproject failed for run %d: %s", run_idx+1, e)
        return None

    if run_out.exists():
        logger.info("Successfully created residual dtseries for %s_run%d.", config.out_file_pre, run_idx+1)
        return run_out
    else:
        logger.error("Failed to create residual dtseries for %s_run%d.", config.out_file_pre, run_idx+1)
        return None


def _simultaneous_polort(n_trs, config):
    """Polynomial degree for the simultaneous backend's 3dTproject call.

    Sinusoids don't span quadratic trends, and 3dTproject's help advises against
    -polort -1 when the data mean is non-zero. Degree 2 is the highest that makes
    sense once low frequencies are bandpassed out; without a low cut, use polort A's rule.
    """
    if config.bandpass is not None and config.bandpass[0] > 0:
        return 2
    return 1 + int(n_trs * config.tr / 150.0)


def _generate_run_residual_sequenced(run_idx, run_scan, censor_path, prepared_motion, config, logger):
    """Generate per-run residual via sequenced denoising (Ciric-inspired).

    Six-step flow:
      (1) Confounds already generated upstream (motion, censor, tissue signals).
      (2-3) 3dTproject -polort -1 -censor X.1D -cenmode NTRP on BOLD to interpolate
           censored TRs.
      (4) 3dBandpass on interpolated BOLD to detrend (quadratic) and band-limit the signal.
      (5) For each nuisance regressor file (motion, CSF, WM, optional GS, optional
          tissue derivatives), apply the same NTRP-interp + 3dBandpass pipeline
          using censor_interpolate_1d_afni and bandpass_filter_1d_afni.
      (6) 3dTproject -polort -1 -ort filtered_motion -ort filtered_CSF [...] (no
          -bandpass, no -censor) on filtered BOLD to produce raw residual.
      (post) 3dcalc -a residual.nii.gz -b censor.1D -expr 'a*b' to zero residuals
           at originally-censored TRs (preserves output convention).

    Tissue derivatives are computed on the RAW tissue signal (existing
    compute_tissue_derivative behavior) and then routed through the same
    NTRP-interp + bandpass pipeline as the base regressors so all -ort regressors
    are frequency-equivalent to the BOLD passband (Hallquist 2013 doctrine).

    Per-run intermediate files are written to
    {config.out_dir}/_sequenced_intermediates/run{N}/ and removed at the end of
    this function unless config.keep_run_res_dtseries is True. On step-6 or
    post-step failure, the directory is preserved regardless of flag value
    so the user can inspect the intermediate state.

    Parameters
    ----------
    run_idx : int
    run_scan : str
    censor_path : str
    prepared_motion : str
    config : ResolvedConfig
        Must include: CSF_paths, WM_paths, GS_paths, use_tissue_derivs,
        bandpass, keep_run_res_dtseries, out_dir, out_file_pre, tr.
    logger : logging.Logger

    Returns
    -------
    pathlib.Path or None
        Path to the run's residual dtseries, or None on failure.
    """
    run_out = _run_residual_path(config, run_idx)

    if run_out.exists():
        return run_out

    inter_dir = Path(config.out_dir) / "_sequenced_intermediates" / f"run{run_idx+1}"
    inter_dir.mkdir(parents=True, exist_ok=True)

    label = f"run{run_idx+1}"
    success = False
    try:
        # Step 2-3: NTRP interpolate BOLD
        bold_interp = inter_dir / f"{config.out_file_pre}_{label}_bold_interp.nii.gz"
        interp_cmd = ["3dTproject",
                      "-polort", "-1",
                      "-dt", str(config.tr),
                      "-input", run_scan,
                      "-censor", censor_path,
                      "-cenmode", "NTRP",
                      "-prefix", bold_interp]
        run_afni_command(interp_cmd, description=f"3dTproject NTRP BOLD {label}", logger=logger)
        if not bold_interp.exists():
            logger.error("Sequenced step 2-3 failed: BOLD interpolation missing for %s.", label)
            return None

        # Step 4: 3dBandpass BOLD
        bold_bp = inter_dir / f"{config.out_file_pre}_{label}_bold_bp.nii.gz"
        bp_cmd = ["3dBandpass",
                  "-dt", str(config.tr),
                  "-prefix", bold_bp,
                  str(config.bandpass[0]), str(config.bandpass[1]),
                  bold_interp]
        run_afni_command(bp_cmd, description=f"3dBandpass BOLD {label}", logger=logger)
        if not bold_bp.exists():
            logger.error("Sequenced step 4 failed: BOLD bandpass missing for %s.", label)
            return None

        # Step 5: filter each nuisance regressor (interp -> bandpass).
        # Tissue derivatives are computed on the RAW signal and then routed
        # through the same filter pipeline as base regressors.
        def _filter_1d(src_path, lbl):
            interp_path = censor_interpolate_1d_afni(
                src_path, config.tr, censor_path, inter_dir, config.out_file_pre, lbl, logger)
            bp_path = bandpass_filter_1d_afni(
                interp_path, config.tr, config.bandpass, inter_dir, config.out_file_pre, lbl, logger)
            return bp_path

        filtered_motion = _filter_1d(prepared_motion, f"{label}_motion")
        filtered_csf = _filter_1d(config.CSF_paths[run_idx], f"{label}_CSF")
        filtered_wm = _filter_1d(config.WM_paths[run_idx], f"{label}_WM")

        ort_args = ["-ort", filtered_motion, "-ort", filtered_csf, "-ort", filtered_wm]

        if config.GS_paths is not None:
            filtered_gs = _filter_1d(config.GS_paths[run_idx], f"{label}_GS")
            ort_args.extend(["-ort", filtered_gs])

        if config.use_tissue_derivs:
            csf_deriv_raw = compute_tissue_derivative(
                config.CSF_paths[run_idx], inter_dir, config.out_file_pre, f"{label}_CSF_deriv_raw", logger)
            filtered_csf_deriv = _filter_1d(csf_deriv_raw, f"{label}_CSF_deriv")
            ort_args.extend(["-ort", filtered_csf_deriv])
            wm_deriv_raw = compute_tissue_derivative(
                config.WM_paths[run_idx], inter_dir, config.out_file_pre, f"{label}_WM_deriv_raw", logger)
            filtered_wm_deriv = _filter_1d(wm_deriv_raw, f"{label}_WM_deriv")
            ort_args.extend(["-ort", filtered_wm_deriv])
            if config.GS_paths is not None:
                gs_deriv_raw = compute_tissue_derivative(
                    config.GS_paths[run_idx], inter_dir, config.out_file_pre, f"{label}_GS_deriv_raw", logger)
                filtered_gs_deriv = _filter_1d(gs_deriv_raw, f"{label}_GS_deriv")
                ort_args.extend(["-ort", filtered_gs_deriv])

        # Step 6: nuisance regression on filtered BOLD with filtered orts.
        # No -bandpass, no -censor; -polort -1 (rest_conn convention).
        residual_pre_mask = inter_dir / f"{config.out_file_pre}_{label}_residual_premask.nii.gz"
        reg_cmd = ["3dTproject",
                   "-polort", "-1",
                   "-dt", str(config.tr),
                   "-input", bold_bp] + ort_args + ["-prefix", residual_pre_mask]
        run_afni_command(reg_cmd, description=f"3dTproject sequenced regression {label}", logger=logger)
        if not residual_pre_mask.exists():
            logger.error("Sequenced step 6 failed: regression output missing for %s.", label)
            return None

        # Post-step: zero residuals at originally-censored TRs via 3dcalc
        # broadcasting the censor.1D file across the time axis.
        calc_cmd = ["3dcalc",
                    "-a", residual_pre_mask,
                    "-b", censor_path,
                    "-expr", "a*b",
                    "-prefix", run_out]
        run_afni_command(calc_cmd, description=f"3dcalc post-step zero censored TRs {label}", logger=logger)
        if not run_out.exists():
            logger.error("Sequenced post-step failed: censored-zero residual missing for %s.", label)
            return None

        logger.info("Successfully created sequenced residual dtseries for %s_run%d.", config.out_file_pre, run_idx+1)
        success = True
        return run_out

    except (ToolExecutionError, OSError) as e:
        logger.error("Sequenced denoising failed for run %d: %s", run_idx+1, e)
        return None

    finally:
        # Cleanup intermediates per S5b-ii. Preserve on failure regardless of flag.
        if success and not config.keep_run_res_dtseries:
            try:
                shutil.rmtree(inter_dir)
                logger.info("Removed sequenced intermediates for %s.", label)
            except Exception as e:
                logger.warning("Unable to remove sequenced intermediates for %s: %s", label, e)
        elif not success:
            logger.info("Preserving sequenced intermediates at %s for inspection (failure).", inter_dir)
        else:
            logger.info("Keeping sequenced intermediates at %s (keep_run_res_dtseries=True).", inter_dir)


def gen_residual_ts(config, logger, unscaled_scans=None):
    """Generate per-run residual dense time series and concatenate across runs.

    For each run: optionally notch-filters motion parameters, generates an FD-based
    censor file, runs a DOF check (emits RUN_SKIPPED graded_warning and skips runs
    where compute_dof raises ModelError), then calls 3dTproject to regress out
    motion, tissue signals, and optional bandpass filtering. Surviving runs are
    concatenated via 3dTcat.

    The per-run residual generation dispatches to one of two backends based on
    config.use_sequenced_bandpass: simultaneous (default; single 3dTproject call
    with -ort, -bandpass, -censor, -cenmode ZERO) or sequenced (Ciric-inspired
    six-step flow: NTRP-interpolate, 3dBandpass, filter nuisance, regress, mask
    censored TRs). Shared setup (motion preparation, censor generation, DOF
    check) and teardown (concatenation, cleanup) are identical across paths.

    Parameters
    ----------
    config : ResolvedConfig
        Pipeline configuration (scan_paths, motion_paths, CSF_paths, WM_paths,
        GS_paths, out_dir, out_file_pre, tr, fd_threshold, censor_prev_tr,
        notch_filter_band, bandpass, use_tissue_derivs, keep_run_res_dtseries).
    logger : logging.Logger
    unscaled_scans : list of str, optional
        The runs' scans before PSC scaling, for the smoothing mask. Defaults to
        config.scan_paths.

    Returns
    -------
    (list[int | None], list[dict])
        Per-run DOF estimates (None for runs where DOF could not be computed
        or where ModelError was raised), and smoothing_per_run records (empty
        without smoothing). Warnings are accumulated via the module-level
        warning accumulator (get_warnings).

    Raises
    ------
    ToolExecutionError
        If no runs were successfully processed, or if 3dTcat concatenation fails.
    """
    # Check if concatenated residual dtseries exists
    concat_path = _concat_residual_path(config)
    per_run_dof = []
    smoothing_records = []
    if not concat_path.exists():

        # Validate and prepare motion files, generate censor files per run
        use_cols = 6 * config.motion_deriv_degree
        prepared_motion = []
        censor_paths = []
        skip_run = []
        for i, mot_path in enumerate(config.motion_paths):
            # Optionally notch-filter motion for respiratory artifact removal
            censor_motion_src = mot_path
            if config.notch_filter_band is not None:
                censor_motion_src = notch_filter_motion(
                    mot_path, config.tr, config.notch_filter_band,
                    config.out_dir, config.out_file_pre, f"run{i+1}", logger)
            # Generate censor file from (possibly filtered) motion
            censor_path = create_censor_file(
                censor_motion_src, config.fd_threshold, config.censor_prev_tr,
                config.out_dir, config.out_file_pre, f"run{i+1}", logger)
            censor_paths.append(censor_path)
            # Prepare motion for regression (original, unfiltered)
            prepared = prepare_motion_file(
                mot_path, use_cols, config.out_dir, config.out_file_pre, f"run{i+1}", logger)
            prepared_motion.append(prepared)

            # Per-run DOF check
            n_regressors = use_cols
            if not config.use_sequenced_bandpass:
                # The sequenced backend detrends in 3dBandpass, before its regression
                n_regressors += _simultaneous_polort(len(np.loadtxt(censor_path)), config) + 1
            n_regressors += 2  # CSF + WM (always present)
            if config.GS_paths is not None:
                n_regressors += 1
            if config.use_tissue_derivs:
                n_regressors += 2  # CSF_deriv + WM_deriv
                if config.GS_paths is not None:
                    n_regressors += 1  # GS_deriv
            try:
                run_dof = compute_dof(censor_path, n_regressors, logger)
                per_run_dof.append(run_dof)
                skip_run.append(False)
            except ModelError as e:
                msg = f"Run {i+1}: {e}"
                graded_warning(logger, 'high', 'RUN_SKIPPED', msg, user_facing=True)
                per_run_dof.append(None)
                skip_run.append(True)

        # Dispatch to selected backend based on config.use_sequenced_bandpass
        backend = (_generate_run_residual_sequenced if config.use_sequenced_bandpass
                   else _generate_run_residual_simultaneous)

        def residual_for_run(i):
            if skip_run[i]:
                return None
            return backend(i, config.scan_paths[i], censor_paths[i], prepared_motion[i], config, logger)

        # Runs are independent; process them concurrently within the num_cores budget.
        # A None result means the backend logged a failure and the run is skipped.
        # parallel_map keeps run order, which 3dTcat relies on.
        residuals = parallel_map(residual_for_run, range(len(config.scan_paths)))
        completed_runs = [r for r in residuals if r is not None]

        if not completed_runs:
            raise ToolExecutionError(
                f"No runs were successfully processed for {config.out_file_pre}. "
                "All runs either failed AFNI processing or were skipped due to insufficient DOF."
            )

        # Concatenate residual time series runs
        cat_command = ["3dTcat", "-TR", str(config.tr), "-prefix", concat_path] + completed_runs
        run_afni_command(cat_command, description="3dTcat concat residuals", logger=logger)
        if concat_path.exists():
            logger.info("Successfully created concatenated residual dtseries for %s.", config.out_file_pre)
        else:
            raise ToolExecutionError(
                f"Failed to create concatenated residual dtseries for {config.out_file_pre}."
            )

        # Smooth from the per-run residuals, before they can be removed below
        if config.smoothing_enabled:
            scans = unscaled_scans or config.scan_paths
            completed = [i for i, r in enumerate(residuals) if r is not None]
            smoothing_records = smooth_rest_runs([(i + 1, residuals[i]) for i in completed],
                                                 [scans[i] for i in completed], concat_path, config, logger)

        # If keep_run_res_dtseries is False (default True), remove per-run residual files
        if not config.keep_run_res_dtseries:
            for comp_run in completed_runs:
                comp_run.unlink()
            all_removed = all(not cr.exists() for cr in completed_runs)
            if all_removed:
                logger.info("Successfully removed run-specific residual dtseries.")
            else:
                logger.warning("Unable to remove all run-specific residual dtseries (continuing, but check the output).")
    else:
        logger.info("%s already exists.", concat_path)

    return per_run_dof, smoothing_records

def gen_ptseries(config, logger):
    """Extract ROI-level residual parcel time series from the concatenated dtseries.

    Uses the concatenated residual dtseries and the provided template to extract
    mean or median BOLD signal per ROI via 3dROIstats. Output is written as a CSV.
    Skips if the output file already exists.

    Parameters
    ----------
    config : ResolvedConfig
        Must include: out_dir, out_file_pre, extract_out_file_pre, template_path,
        average_type.
    logger : logging.Logger

    Raises
    ------
    ToolExecutionError
        If ptseries CSV could not be written after extraction.
    """
    ptseries_path = Path(config.out_dir) / f"{config.extract_out_file_pre}_residual_ptseries.csv"

    # Check if output already exists
    if not ptseries_path.exists():

        new_df = extract_roi_stats(_concat_residual_path(config), config.template_path, config.average_type, logger=logger,
                                   roi_zero_handling=config.roi_zero_handling)

        # Save ptseries
        new_df.to_csv(ptseries_path)
        if ptseries_path.exists():
            logger.info("Successfully extracted ptseries using ROI template.")
        else:
            raise ToolExecutionError(
                f"Could not extract ptseries using ROI template for {config.out_file_pre}."
            )
    else:
        logger.info("%s already exists.", ptseries_path)

def gen_conn(config, logger):
    """Compute functional connectivity from the concatenated residual dtseries.

    Dispatches to either parcellated_conn (ROI-to-ROI matrix via 3dNetCorr) or
    seed_to_voxel_conn (whole-brain voxelwise map via 3dNetCorr) based on
    config.calc_conn. For resting-state, no condition label is used.

    Parameters
    ----------
    config : ResolvedConfig
        Must include: out_dir, out_file_pre, calc_conn, conn_out_file_pre,
        template_path, fishZ, pcorr.
    logger : logging.Logger
    """
    inset_path = _concat_residual_path(config)

    # Run connectivity analyses based on the specified flavor (no condition -- resting-state)
    if config.calc_conn == "parcellated":
        parcellated_conn(
            inset_path=inset_path,
            out_dir=config.out_dir,
            conn_out_file_pre=config.conn_out_file_pre,
            template_path=config.template_path,
            fishZ=config.fishZ,
            pcorr=config.pcorr,
            condition=None,
            logger=logger,
        )
    else:
        seed_to_voxel_conn(
            inset_path=inset_path,
            out_dir=config.out_dir,
            conn_out_file_pre=config.conn_out_file_pre,
            template_path=config.template_path,
            fishZ=config.fishZ,
            pcorr=config.pcorr,
            condition=None,
            logger=logger,
        )
        if config.smoothing_enabled:
            token = smoothing_token(config.smoothing_fwhm)
            seed_to_voxel_smoothed(inset_path, with_token(inset_path, token), config.out_dir,
                                   config.conn_out_file_pre, config.template_path, config.fishZ,
                                   config.pcorr, token, condition=None, logger=logger)

@manifested
@uses_num_cores
def run(config: ResolvedConfig, logger: logging.Logger | None = None) -> FirstLevelResult:
    """Validate config and execute the resting-state connectivity pipeline.

    Orchestrates the full rest_conn pipeline in the following order:
    1. Validate that all run-level path lists are the same length.
    2. Log GSR warning if GS_paths is provided; emit GS_MISSING graded_warning if not.
    3. Optionally clear out_dir (if remove_previous is set).
    4. Validate extraction and connectivity arguments.
    5. Extract minimum-outlier EPI frame per run (gen_min_outlier_epi; mandatory).
    6. Optionally extract pre-regression parcellated time series per run (extract_raw_ptseries).
    7. Generate per-run residual dense time series via 3dTproject (gen_residual_ts),
       which internally: optionally notch-filters motion, generates per-run censor
       files, runs per-run DOF checks (emits RUN_SKIPPED graded_warning and skips
       runs where ModelError is raised), and concatenates surviving runs via 3dTcat.
    8. Collect per-run censoring statistics for QC; emit CENSOR_HIGH graded_warning
       if aggregate censoring exceeds 50%.
    9. Optionally extract parcel time series from the concatenated residuals (gen_ptseries).
    10. Optionally compute functional connectivity from the concatenated residuals (gen_conn).
    11. Write QC summary JSON.
    12. Return FirstLevelResult with status, warnings, qc_summary, and output_files.

    Works from the config-driven dispatch runner
    (cli.py / DISPATCH["rest_conn"]).

    Parameters
    ----------
    config : ResolvedConfig
        All pipeline configuration (see config.py ResolvedConfig for
        the full attribute list).
    logger : logging.Logger or None
        If None, a default logger is created via setup_logging.

    Returns
    -------
    FirstLevelResult
        Pipeline result with status ('success' or 'warning'),
        output_dir, accumulated warnings, qc_summary, and output_files.

    Raises
    ------
    ConfigError
        For invalid option combinations or path list length mismatches.
    InputError
        For missing required input files.
    ToolExecutionError
        For AFNI command failures or missing expected output files.
    """
    if logger is None:
        logger = setup_logging("rest_conn_first_level")

    config = copy.copy(config)
    clear_warnings()

    # Validate all path lists are the same length (config-driven dispatch validates
    # this upstream, but guard here for direct programmatic callers)
    path_lengths = {"scan_paths": len(config.scan_paths), "motion_paths": len(config.motion_paths),
                    "CSF_paths": len(config.CSF_paths), "WM_paths": len(config.WM_paths)}
    if config.GS_paths is not None:
        path_lengths["GS_paths"] = len(config.GS_paths)
    if len(set(path_lengths.values())) > 1:
        raise ConfigError(
            f"All path lists must be the same length. Got: {path_lengths}"
        )
    check_inputs(config, logger)

    logger.info("Residual dense time series will be created for resting-state fMRI.")
    if config.use_tissue_derivs:
        tissue_parts = ["CSF", "WM"]
        if config.GS_paths is not None:
            tissue_parts.append("GS")
        logger.info("Tissue signal derivatives will be included as additional regressors: %s", ", ".join(tissue_parts))
    if config.GS_paths is not None:
        logger.warning("Global signal regression (GSR) is enabled. Note: GSR is controversial -- "
                       "it can remove neural signal and introduce artifactual anti-correlations. "
                       "Use with caution and report in methods.")
    else:
        graded_warning(logger, 'low', 'GS_MISSING',
                       "Global signal paths (GS_paths) not provided; global signal regression (GSR) disabled.",
                       user_facing=False)

    # If --remove_previous is provided, clear-out the output dir (before template
    # resampling or any other file creation in out_dir)
    if config.remove_previous:
        logger.info("Removing all files from previous analyses in %s (if they exist).", config.out_dir)
        remove_files_from_dir(config.out_dir, logger=logger)

    # Make sure optional args exist if --extract_ptseries is provided
    if config.extract_ptseries:
        config.template_path = validate_extract_options(
            "--extract_ptseries", config.average_type, config.extract_out_file_pre,
            config.template_path, config.scan_paths[0], config.out_dir, config.force_diff_atlas,
            logger=logger)

    # Make sure optional args exist if --calc_conn is provided
    if config.calc_conn is not None:
        config.template_path = validate_connectivity_options(
            config.calc_conn, config.conn_out_file_pre, config.template_path,
            config.scan_paths[0], config.out_dir, config.force_diff_atlas,
            data_label="residual time series", logger=logger)
    else:
        logger.info("Connectivity will not be output after generating residual time series.")

    # ---------------------------------

    # Per run (concurrently): extract the minimum-outlier representative EPI frame
    # (mandatory, before regression), then optionally PSC-scale the scan.
    def prepare_run_scan(i):
        scan = config.scan_paths[i]
        gen_min_outlier_epi(scan, config.out_dir, config.out_file_pre, f"run{i+1}", logger)
        if config.scale_to_psc:
            return str(scale_to_psc(scan, config.out_dir, config.out_file_pre, f"run{i+1}", logger,
                                    qc_records=psc_per_run, run=i + 1))
        return scan

    unscaled_scans = list(config.scan_paths)
    psc_per_run = []
    config.scan_paths = parallel_map(prepare_run_scan, range(len(config.scan_paths)))

    # Extract pre-regression parcellated time series per run if requested
    if getattr(config, 'extract_raw_ptseries', False):
        if config.extract_out_file_pre is None:
            raise ConfigError(
                "extract_raw_ptseries requires extract_out_file_pre to be set."
            )
        if config.template_path is None:
            raise ConfigError(
                "extract_raw_ptseries requires a valid template_path."
            )
        validated_tpl = validate_template(config.scan_paths[0], config.template_path,
            config.out_dir, config.force_diff_atlas, conn_type="extract", logger=logger)
        for i, scan in enumerate(config.scan_paths):
            raw_out = Path(config.out_dir) / f"{config.extract_out_file_pre}_run{i+1}_raw_ptseries.csv"
            if not raw_out.exists():
                raw_df = extract_roi_stats(scan, validated_tpl, config.average_type, logger=logger,
                                           roi_zero_handling=config.roi_zero_handling)
                raw_df.to_csv(raw_out)
                if raw_out.exists():
                    logger.info("Extracted raw ptseries for run %d to %s.", i+1, raw_out)
                else:
                    raise ToolExecutionError(
                        f"Failed to extract raw ptseries for run {i+1}."
                    )
            else:
                logger.info("Raw ptseries for run %d already exists: %s", i+1, raw_out)

    # Build QC summary data with per-run censoring stats
    qc_data = {
        "analysis_type": "rest_conn",
        "fd_threshold": config.fd_threshold,
        "censor_metric": CENSOR_METRIC,
        "censor_prev_tr": config.censor_prev_tr,
        "bandpass": config.bandpass,
        "per_run_censoring": [],
    }

    # Generate residual dense time series (regression for denoising, censoring, and temporal filtering)
    per_run_dof, smoothing_records = gen_residual_ts(config, logger, unscaled_scans)
    if per_run_dof:
        qc_data["per_run_dof"] = per_run_dof
    if config.scale_to_psc:
        qc_data["psc_per_run"] = sorted(psc_per_run, key=lambda record: record["run"])
    if smoothing_records:
        qc_data["smoothing_per_run"] = smoothing_records

    # Collect per-run censor stats (censor files were created inside gen_residual_ts)
    for i in range(len(config.scan_paths)):
        censor_path = Path(config.out_dir) / f"{config.out_file_pre}_run{i+1}_censor.1D"
        run_stats = {"run": i + 1}
        try:
            censor_data = np.loadtxt(censor_path)
            run_stats["n_trs_total"] = len(censor_data)
            run_stats["n_trs_censored"] = int(np.sum(censor_data == 0))
            run_stats["pct_censored"] = round(100.0 * run_stats["n_trs_censored"] / run_stats["n_trs_total"], 2) if run_stats["n_trs_total"] > 0 else 0.0
            logger.info("Run %d censoring: %d of %d TRs censored (%.1f%%).",
                        i + 1, run_stats["n_trs_censored"], run_stats["n_trs_total"], run_stats["pct_censored"])
        except Exception:
            pass
        qc_data["per_run_censoring"].append(run_stats)

    # Aggregate totals
    total_trs = sum(r.get("n_trs_total", 0) for r in qc_data["per_run_censoring"])
    total_censored = sum(r.get("n_trs_censored", 0) for r in qc_data["per_run_censoring"])
    qc_data["n_trs_total"] = total_trs
    qc_data["n_trs_censored"] = total_censored
    qc_data["pct_censored"] = round(100.0 * total_censored / total_trs, 2) if total_trs > 0 else 0.0

    # Emit CENSOR_HIGH graded_warning if aggregate censoring exceeds 50%
    if qc_data["pct_censored"] > 50.0:
        graded_warning(
            logger, 'high', 'CENSOR_HIGH',
            f"Aggregate censoring is {qc_data['pct_censored']:.1f}% (>{50.0}% threshold). "
            "Results may be unreliable; consider relaxing the FD threshold.",
            user_facing=True,
        )

    # Extract ptseries if user provided option
    if config.extract_ptseries:
        gen_ptseries(config, logger)

    # Generate connectivity from residual time series if user provided option
    if config.calc_conn is not None:
        gen_conn(config, logger)

    # Write QC summary
    write_qc_summary(config.out_dir, config.out_file_pre, qc_data, logger)

    # Collect output_files
    out_dir = Path(config.out_dir)
    n_runs = len(config.scan_paths)
    candidates = [out_dir / f"{config.out_file_pre}_run{i+1}_psc.nii.gz" for i in range(n_runs)]
    candidates.append(_concat_residual_path(config))
    if config.keep_run_res_dtseries:
        candidates.extend(_run_residual_path(config, i) for i in range(n_runs))
    if config.smoothing_enabled:
        token = smoothing_token(config.smoothing_fwhm)
        candidates.append(with_token(_concat_residual_path(config), token))
        if config.keep_run_res_dtseries:
            candidates.extend(with_token(_run_residual_path(config, i), token) for i in range(n_runs))
    if getattr(config, 'extract_raw_ptseries', False) and config.extract_out_file_pre is not None:
        candidates.extend(out_dir / f"{config.extract_out_file_pre}_run{i+1}_raw_ptseries.csv" for i in range(n_runs))
    if config.extract_ptseries and config.extract_out_file_pre is not None:
        candidates.append(out_dir / f"{config.extract_out_file_pre}_residual_ptseries.csv")
    candidates.append(out_dir / f"{config.out_file_pre}_qc_summary.json")
    output_files = [str(p) for p in candidates if p.exists()]

    # Determine result status
    status = "warning" if any(w.get("severity") == "high" for w in get_warnings()) else "success"

    return FirstLevelResult(
        status=status,
        output_dir=Path(config.out_dir),
        warnings=get_warnings(),
        qc_summary=qc_data,
        output_files=output_files,
    )
