"""Motion/censor preparation, nuisance-regressor filtering, PSC scaling, and min-outlier EPI."""

import os

import numpy as np

from .afni import run_afni_command
from .exceptions import GuardError, InputError, ToolExecutionError


# ----------------------------------------------------------------------------
# Censoring QC thresholds (warn only — never abort based on percentage)
# ----------------------------------------------------------------------------
CENSOR_WARN_THRESHOLD = 30.0    # % censored → warning


CENSOR_HIGH_THRESHOLD = 50.0    # % censored → strong warning


def prepare_motion_file(motion_path, use_columns, out_dir, out_prefix, label, logger):
    """
    Validate and prepare a motion regressor file for AFNI.

    Reads the motion file, validates it has >= use_columns columns, and writes
    a truncated version (first use_columns columns only) to out_dir. Returns
    the path to the prepared file.

    Parameters
    ----------
    motion_path : str
        Path to the original motion file.
    use_columns : int
        Number of columns to keep (6 for base, 12 for +derivs, etc.).
    out_dir : str
        Directory for the prepared file.
    out_prefix : str
        Filename prefix for the prepared file.
    label : str
        Descriptive label for logging (e.g. "run1", "concat").
    logger : logging.Logger

    Returns
    -------
    str
        Path to the prepared motion file.

    Notes
    -----
    Rotation parameters are assumed to be in **degrees**. The pipeline passes
    motion values through to AFNI without unit conversion. The expected column
    order is ``[tx, ty, tz, rx, ry, rz, ...]`` (translations in mm first,
    rotations in degrees second). AFNI's ``1d_tool.py -censor_motion`` uses
    an Euclidean norm without radius scaling, so 1 degree ~ 1 mm of arc at
    the standard ~57.3 mm head radius -- this is AFNI's intended convention.
    Passing radians instead of degrees will underweight rotational FD by ~57x.
    """
    try:
        data = np.loadtxt(motion_path)
    except Exception as e:
        raise InputError(f"Cannot read motion file '{motion_path}': {e}") from e
    if data.ndim == 1:
        data = data.reshape(-1, 1)
    ncols = data.shape[1]
    if ncols < use_columns:
        raise InputError(f"Motion file '{motion_path}' has {ncols} columns, expected >= {use_columns}.")
    # Truncate to requested columns
    truncated = data[:, :use_columns]
    prepared_path = os.path.join(out_dir, f"{out_prefix}_{label}_motion_prepared.1D")
    np.savetxt(prepared_path, truncated, fmt="%.8f", delimiter="\t")
    if ncols > use_columns:
        logger.info("Motion file '%s': using %d of %d columns.", motion_path, use_columns, ncols)
    return prepared_path


def create_censor_file(motion_path, fd_threshold, censor_prev_tr, out_dir, out_prefix, label, logger):
    """
    Generate a censor file from motion regressors using AFNI's 1d_tool.py.

    Extracts the first 6 columns (base motion parameters) from the motion file,
    then runs 1d_tool.py to create an FD-based censor file.

    Parameters
    ----------
    motion_path : str
        Path to the original motion file (before prepare_motion_file).
    fd_threshold : float
        Framewise displacement threshold (mm) for censoring.
    censor_prev_tr : bool
        If True, also censor the TR preceding each high-motion TR.
    out_dir : str
        Output directory.
    out_prefix : str
        Filename prefix.
    label : str
        Descriptive label (e.g. "concat", "run1").
    logger : logging.Logger

    Returns
    -------
    str
        Path to the generated censor file.
    """
    # 1d_tool.py auto-appends _censor.1D to the prefix
    censor_prefix = os.path.join(out_dir, f"{out_prefix}_{label}")
    censor_path = f"{censor_prefix}_censor.1D"

    # Skip if censor file already exists (1d_tool.py won't overwrite)
    if os.path.exists(censor_path):
        logger.info("Censor file %s already exists (skipping generation).", censor_path)
    else:
        # Extract first 6 columns (base motion only) for FD calculation
        motion_6col = prepare_motion_file(motion_path, 6, out_dir, out_prefix, f"{label}_censor_src", logger)

        # Build 1d_tool.py command
        cmd = ["1d_tool.py",
               "-infile", motion_6col,
               "-censor_motion", str(fd_threshold), censor_prefix]
        if censor_prev_tr:
            cmd.append("-censor_prev_TR")

        run_afni_command(cmd, description=f"1d_tool.py censor {label}", logger=logger)

        if not os.path.exists(censor_path):
            raise ToolExecutionError(f"Expected censor file not found: {censor_path}")

    # Log count of censored TRs and warn at thresholds
    try:
        censor_data = np.loadtxt(censor_path)
        n_censored = int(np.sum(censor_data == 0))
        n_total = len(censor_data)
        pct_censored = 100.0 * n_censored / n_total if n_total > 0 else 0.0
        logger.info("Censor file %s: %d of %d TRs censored (%.1f%%).",
                     censor_path, n_censored, n_total, pct_censored)
        if pct_censored >= CENSOR_HIGH_THRESHOLD:
            logger.warning("HIGH CENSORING: %.1f%% of TRs censored (>= %.0f%%). "
                           "Results may be unreliable. Review motion QC carefully.",
                           pct_censored, CENSOR_HIGH_THRESHOLD)
        elif pct_censored >= CENSOR_WARN_THRESHOLD:
            logger.warning("Elevated censoring: %.1f%% of TRs censored (>= %.0f%%). "
                           "Consider reviewing motion QC.",
                           pct_censored, CENSOR_WARN_THRESHOLD)
    except Exception:
        pass  # Non-critical; censor file exists and will be used

    return censor_path


def notch_filter_motion(motion_path, tr, stopband, out_dir, out_prefix, label, logger):
    """
    Apply a notch (stopband) filter to motion parameters using AFNI's 3dTproject.

    Used to remove respiratory artifacts from motion parameters before FD-based
    censoring (Fair et al., 2020).

    Parameters
    ----------
    motion_path : str
        Path to the original motion file.
    tr : float
        Repetition time in seconds.
    stopband : list of float
        [low, high] Hz band to remove.
    out_dir : str
        Output directory.
    out_prefix : str
        Filename prefix.
    label : str
        Descriptive label (e.g. "run1").
    logger : logging.Logger

    Returns
    -------
    str
        Path to the notch-filtered motion file.
    """
    # Extract first 6 columns (base motion only)
    motion_6col = prepare_motion_file(motion_path, 6, out_dir, out_prefix, f"{label}_notch_src", logger)

    out_path = os.path.join(out_dir, f"{out_prefix}_{label}_notch_motion.1D")

    # AFNI interprets .1D files as rows=voxels, cols=timepoints.
    # A TRs×6 motion file is seen as TRs voxels × 6 timepoints, causing a
    # "too few timepoints" error in 3dTproject.  The trailing ' (AFNI transpose
    # operator) presents the file as 6 voxels × TRs timepoints so 3dTproject
    # operates correctly along the time axis.  After filtering, 3dTproject
    # writes its output in the same transposed orientation (rows=params,
    # cols=TRs); 1dtranspose is then used to restore rows=TRs, cols=params
    # for downstream use.
    cmd = ["3dTproject",
           "-polort", "-1",
           "-dt", str(tr),
           "-input", f"{motion_6col}'",
           "-stopband", str(stopband[0]), str(stopband[1]),
           "-prefix", out_path]

    run_afni_command(cmd, description=f"3dTproject notch filter {label}", logger=logger)

    if not os.path.exists(out_path):
        raise ToolExecutionError(f"Expected notch-filtered motion file not found: {out_path}")

    # Restore rows=TRs, cols=params orientation (3dTproject output is transposed)
    transposed_path = out_path + ".transposed.1D"
    transpose_cmd = ["1dtranspose", out_path, transposed_path]
    run_afni_command(transpose_cmd, description=f"1dtranspose notch filter {label}", logger=logger)
    if not os.path.exists(transposed_path):
        raise ToolExecutionError(f"1dtranspose failed for notch-filtered motion: {out_path}")
    os.replace(transposed_path, out_path)

    logger.info("Notch-filtered motion parameters (rows=TRs, cols=params) saved to %s", out_path)
    return out_path


def censor_interpolate_1d_afni(input_path, tr, censor_path, out_dir, out_prefix, label, logger):
    """
    Interpolate censored TRs in a nuisance regressor 1D file using AFNI 3dTproject -cenmode NTRP.

    Invokes ``3dTproject`` with ``-cenmode NTRP`` to replace censored TRs with
    interpolated values in the input 1D file.  Because AFNI interprets .1D files
    as rows=voxels, cols=timepoints, the input is presented to 3dTproject with a
    trailing apostrophe (AFNI transpose operator) so the time axis is read
    correctly.  After the command executes, 3dTproject writes its output in the
    transposed orientation (rows=columns, cols=TRs); ``1dtranspose`` is applied to
    restore rows=TRs, cols=columns for all downstream consumers.  This function is
    intended for sequenced denoising pipelines where censored TRs must be
    interpolated in nuisance regressors (e.g., tissue signals, motion parameters)
    before bandpass filtering so that the frequency-domain operation is not
    contaminated by zero-fill or mean-imputation artefacts.

    Parameters
    ----------
    input_path : str
        Path to the input 1D file (rows=TRs orientation) whose censored TRs will
        be interpolated.
    tr : float
        Repetition time in seconds; passed to 3dTproject via ``-dt``.
    censor_path : str
        Path to the AFNI-format censor file (1=keep, 0=censor).
    out_dir : str
        Output directory for the interpolated file.
    out_prefix : str
        Filename prefix used to construct the output filename.
    label : str
        Descriptive label appended to the output filename (e.g., ``"CSF"``).
    logger : logging.Logger
        Logger for info and error messages.

    Returns
    -------
    str
        Absolute path to the interpolated 1D file in rows=TRs, cols=columns
        orientation.
    """
    out_path = os.path.join(out_dir, f"{out_prefix}_{label}_interp.1D")

    cmd = ["3dTproject",
           "-polort", "-1",
           "-dt", str(tr),
           "-input", f"{input_path}'",
           "-censor", censor_path,
           "-cenmode", "NTRP",
           "-prefix", out_path]

    run_afni_command(cmd, description=f"3dTproject NTRP interpolate {label}", logger=logger)

    if not os.path.exists(out_path):
        raise ToolExecutionError(f"Expected NTRP-interpolated 1D file not found: {out_path}")

    # Restore rows=TRs, cols=cols orientation (3dTproject output is transposed)
    transposed_path = out_path + ".transposed.1D"
    transpose_cmd = ["1dtranspose", out_path, transposed_path]
    run_afni_command(transpose_cmd, description=f"1dtranspose interpolate {label}", logger=logger)
    if not os.path.exists(transposed_path):
        raise ToolExecutionError(f"1dtranspose failed for interpolated 1D file: {out_path}")
    os.replace(transposed_path, out_path)

    logger.info("NTRP-interpolated 1D file (rows=TRs, cols=cols) saved to %s", out_path)
    return out_path


def bandpass_filter_1d_afni(input_path, tr, bandpass, out_dir, out_prefix, label, logger):
    """
    Bandpass-filter a nuisance regressor 1D file using AFNI 3dBandpass -nodetrend.

    Invokes ``3dBandpass`` with ``-nodetrend`` to apply a bandpass filter to the
    input 1D file over the passband specified by ``bandpass[0]`` (fbot) and
    ``bandpass[1]`` (ftop).  The ``-nodetrend`` flag is required to preserve
    consistency with the ``polort -1`` convention used throughout the pipeline
    (i.e., no polynomial detrending is applied here, because detrending is handled
    separately), and the passband matches the BOLD bandpass step so that nuisance
    regressors and BOLD data share the same frequency content.  Because AFNI
    interprets .1D files as rows=voxels, cols=timepoints, the input is presented to
    3dBandpass with a trailing apostrophe (AFNI transpose operator) so the time axis
    is read correctly.  After the command executes, 3dBandpass writes its output in
    the transposed orientation (rows=columns, cols=TRs); ``1dtranspose`` is applied
    to restore rows=TRs, cols=columns for all downstream consumers.  This function
    is intended for use after ``censor_interpolate_1d_afni``, filtering interpolated
    nuisance regressors (e.g., tissue signals, motion parameters) at the same
    passband as the BOLD signal before they enter the final regression model.

    Parameters
    ----------
    input_path : str
        Path to the input 1D file (rows=TRs orientation) to be bandpass-filtered.
    tr : float
        Repetition time in seconds; passed to 3dBandpass via ``-dt``.
    bandpass : list or tuple of float
        Two-element sequence ``[fbot, ftop]`` specifying the lower and upper
        frequency bounds of the passband in Hz.
    out_dir : str
        Output directory for the filtered file.
    out_prefix : str
        Filename prefix used to construct the output filename.
    label : str
        Descriptive label appended to the output filename (e.g., ``"CSF"``).
    logger : logging.Logger
        Logger for info and error messages.

    Returns
    -------
    str
        Absolute path to the bandpass-filtered 1D file in rows=TRs, cols=columns
        orientation.
    """
    out_path = os.path.join(out_dir, f"{out_prefix}_{label}_bp.1D")

    cmd = ["3dBandpass",
           "-nodetrend",
           "-dt", str(tr),
           "-prefix", out_path,
           str(bandpass[0]), str(bandpass[1]),
           f"{input_path}'"]

    run_afni_command(cmd, description=f"3dBandpass {label}", logger=logger)

    if not os.path.exists(out_path):
        raise ToolExecutionError(f"Expected bandpass-filtered 1D file not found: {out_path}")

    # Restore rows=TRs, cols=cols orientation (3dBandpass output is transposed)
    transposed_path = out_path + ".transposed.1D"
    transpose_cmd = ["1dtranspose", out_path, transposed_path]
    run_afni_command(transpose_cmd, description=f"1dtranspose {label}", logger=logger)
    if not os.path.exists(transposed_path):
        raise ToolExecutionError(f"1dtranspose failed for bandpass-filtered 1D file: {out_path}")
    os.replace(transposed_path, out_path)

    logger.info("Bandpass-filtered 1D file (rows=TRs, cols=cols) saved to %s", out_path)
    return out_path


def compute_tissue_derivative(tissue_path, out_dir, out_prefix, tissue_label, logger):
    """
    Compute the first temporal derivative of a tissue signal file.

    Reads the tissue signal, computes backward difference (zero-padded to
    preserve length), and saves to out_dir.

    Parameters
    ----------
    tissue_path : str
        Path to the tissue signal file (single-column text).
    out_dir : str
        Output directory.
    out_prefix : str
        Filename prefix.
    tissue_label : str
        Label for the tissue type (e.g. "CSF", "WM", "run1_CSF").
    logger : logging.Logger

    Returns
    -------
    str
        Path to the derivative file.
    """
    try:
        data = np.loadtxt(tissue_path)
    except Exception as e:
        raise InputError(f"Cannot read tissue file '{tissue_path}': {e}") from e
    if data.ndim != 1:
        raise InputError(f"Tissue file '{tissue_path}' must be single-column, got shape {data.shape}.")
    deriv = np.diff(data, prepend=data[0])
    deriv_path = os.path.join(out_dir, f"{out_prefix}_{tissue_label}_deriv.txt")
    np.savetxt(deriv_path, deriv, fmt="%.8f")
    logger.info("Created tissue derivative: %s", deriv_path)
    return deriv_path


def gen_min_outlier_epi(scan_path, out_dir, out_file_pre, label, logger):
    """Extract the minimum-outlier EPI frame from a 4D scan.

    Identifies the TR with the lowest voxelwise outlier fraction (via AFNI's
    ``3dToutcount -automask -fraction``) and extracts that single volume with
    ``3dbucket``. This produces a representative EPI frame suitable for
    alignment QC without the blurring introduced by temporal averaging.

    Parameters
    ----------
    scan_path : str
        Path to the 4D NIfTI scan.
    out_dir : str
        Output directory.
    out_file_pre : str
        Output filename prefix.
    label : str
        Descriptive label appended to the filename. Use ``""`` for task
        pipelines (single scan) or ``"run1"``, ``"run2"``, etc. for
        rest_conn (per-run).
    logger : logging.Logger

    Returns
    -------
    str
        Path to the extracted single-volume NIfTI.
    """
    # Build output filename
    if label:
        out_name = f"{out_file_pre}_{label}_min_outlier_epi.nii.gz"
    else:
        out_name = f"{out_file_pre}_min_outlier_epi.nii.gz"
    out_path = os.path.join(out_dir, out_name)

    # Skip if already exists
    if os.path.exists(out_path):
        logger.info("Min-outlier EPI already exists: %s", out_path)
        return out_path

    # Run 3dToutcount to get per-TR outlier fractions
    toutcount_cmd = ["3dToutcount", "-automask", "-fraction", scan_path]
    try:
        toutcount_out = run_afni_command(
            toutcount_cmd, capture_output=True,
            description="3dToutcount min-outlier scan", logger=logger)
    except Exception as e:
        raise ToolExecutionError(f"3dToutcount failed for {scan_path}: {e}") from e

    # Parse outlier fractions (one float per TR)
    try:
        fractions = np.array([float(v) for v in toutcount_out.strip().split()])
    except (ValueError, AttributeError) as e:
        raise GuardError(f"Could not parse 3dToutcount output for {scan_path}: {e}") from e

    if len(fractions) == 0:
        raise GuardError(f"3dToutcount returned no data for {scan_path}.")

    min_idx = int(np.argmin(fractions))
    logger.info("Min-outlier TR for %s: index %d (outlier fraction = %.6f).",
                out_name, min_idx, fractions[min_idx])

    # Extract the minimum-outlier volume
    bucket_cmd = ["3dbucket", "-prefix", out_path, f"{scan_path}[{min_idx}]"]
    try:
        run_afni_command(bucket_cmd, description="3dbucket min-outlier EPI", logger=logger)
    except Exception as e:
        raise ToolExecutionError(f"3dbucket failed for {scan_path}[{min_idx}]: {e}") from e

    if os.path.exists(out_path):
        logger.info("Successfully extracted min-outlier EPI: %s", out_path)
    else:
        raise ToolExecutionError(f"Failed to create min-outlier EPI: {out_path}")

    return out_path


def scale_to_psc(scan_path, out_dir, out_file_pre, label, logger):
    """Scale a 4D NIfTI to percent signal change (PSC).

    Computes the voxelwise temporal mean via 3dTstat, then divides each
    voxel's time series by its mean and multiplies by 100, with a 200%
    ceiling and zero-guard via step functions.

    Parameters
    ----------
    scan_path : str
        Path to the input 4D NIfTI.
    out_dir : str
        Output directory.
    out_file_pre : str
        Output filename prefix.
    label : str
        Descriptive label appended to filenames. Use "" for task pipelines
        (single concatenated scan) or "run1", "run2", etc. for rest_conn.
    logger : logging.Logger

    Returns
    -------
    str
        Path to the PSC-scaled 4D NIfTI.
    """
    if label:
        mean_name = f"{out_file_pre}_{label}_mean.nii.gz"
        psc_name = f"{out_file_pre}_{label}_psc.nii.gz"
    else:
        mean_name = f"{out_file_pre}_mean.nii.gz"
        psc_name = f"{out_file_pre}_psc.nii.gz"
    mean_path = os.path.join(out_dir, mean_name)
    psc_path = os.path.join(out_dir, psc_name)

    if os.path.exists(psc_path):
        logger.info("PSC-scaled file already exists: %s", psc_path)
        return psc_path

    run_afni_command(
        ["3dTstat", "-mean", "-prefix", mean_path, scan_path],
        description="3dTstat temporal mean for PSC scaling",
        logger=logger,
    )

    run_afni_command(
        ["3dcalc",
         "-a", scan_path,
         "-b", mean_path,
         "-expr", "min(200,a/b*100)*step(a)*step(b)",
         "-prefix", psc_path],
        description="3dcalc PSC scaling",
        logger=logger,
    )

    logger.info("PSC-scaled scan written to %s", psc_path)
    return psc_path
