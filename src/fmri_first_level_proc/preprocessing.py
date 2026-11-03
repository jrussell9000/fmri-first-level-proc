"""Motion/censor preparation, nuisance-regressor filtering, PSC scaling, and min-outlier EPI."""

import shutil
import tempfile
from pathlib import Path

import numpy as np

from .afni import run_afni_command
from .exceptions import GuardError, InputError, ToolExecutionError


# ----------------------------------------------------------------------------
# Censoring QC thresholds (warn only — never abort based on percentage)
# ----------------------------------------------------------------------------
CENSOR_WARN_THRESHOLD = 30.0    # % censored → warning
CENSOR_HIGH_THRESHOLD = 50.0    # % censored → strong warning

CENSOR_METRIC = "power_fd"
FD_RADIUS_MM = 50.0             # head radius converting rotations to arc length (Power et al., 2012)
PSC_NONPOSITIVE_LIMIT = 25.0    # % of non-constant voxels with mean <= 0 → input is demeaned


def _labeled_name(out_file_pre, label, suffix):
    """Build '{pre}_{label}_{suffix}', or '{pre}_{suffix}' when label is empty."""
    return f"{out_file_pre}_{label}_{suffix}" if label else f"{out_file_pre}_{suffix}"


def _as_1d(path, out_dir, out_prefix, label):
    """Return a path AFNI will read as 1D data.

    AFNI identifies 1D datasets by the .1D suffix; with the transpose quote
    (``file'``) a .txt path is not recognised and the command fails with
    "Can't open dataset". Non-.1D inputs are copied to a .1D path in out_dir.
    """
    path = Path(path)
    if path.suffix == ".1D":
        return path
    copy = Path(out_dir) / f"{out_prefix}_{label}_src.1D"
    shutil.copyfile(path, copy)
    return copy


def _restore_time_rows(out_path, what, step, label, logger):
    """Transpose an AFNI 1D output back to rows=TRs in place.

    AFNI tools fed a transposed 1D input (``file'``) write their output with
    rows=columns, cols=TRs; 1dtranspose restores rows=TRs for downstream use.
    """
    if not out_path.exists():
        raise ToolExecutionError(f"Expected {what} file not found: {out_path}")
    transposed_path = out_path.with_name(out_path.name + ".transposed.1D")
    run_afni_command(["1dtranspose", out_path, transposed_path],
                     description=f"1dtranspose {step} {label}", logger=logger)
    if not transposed_path.exists():
        raise ToolExecutionError(f"1dtranspose failed for {what} file: {out_path}")
    transposed_path.replace(out_path)


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
    pathlib.Path
        Path to the prepared motion file.

    Notes
    -----
    Rotation parameters are assumed to be in **degrees**. The pipeline passes
    motion values through to AFNI without unit conversion. The expected column
    order is ``[tx, ty, tz, rx, ry, rz, ...]`` (translations in mm first,
    rotations in degrees second). Passing radians instead of degrees will
    underweight rotational FD by ~57x (see power_fd).
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
    prepared_path = Path(out_dir) / f"{out_prefix}_{label}_motion_prepared.1D"
    np.savetxt(prepared_path, truncated, fmt="%.8f", delimiter="\t")
    if ncols > use_columns:
        logger.info("Motion file '%s': using %d of %d columns.", motion_path, use_columns, ncols)
    return prepared_path


def power_fd(motion, run_lengths=None):
    """Compute Power et al. (2012) framewise displacement.

    FD is the sum of absolute backward differences of the six motion parameters,
    with rotations converted to arc length on a 50 mm sphere.

    Parameters
    ----------
    motion : np.ndarray
        (N, >=6) array whose first six columns are [tx, ty, tz, rx, ry, rz],
        translations in mm and rotations in degrees.
    run_lengths : list of int or None
        TRs per concatenated run. FD is 0 at each run's first TR, since the
        difference across a run boundary is not head motion.

    Returns
    -------
    np.ndarray
        FD per TR (length N). The first TR is 0.
    """
    deltas = np.vstack([np.zeros((1, 6)), np.diff(motion[:, :6], axis=0)])
    deltas[:, 3:6] = np.radians(deltas[:, 3:6]) * FD_RADIUS_MM
    fd = np.abs(deltas).sum(axis=1)
    if run_lengths:
        fd[np.cumsum(run_lengths)[:-1]] = 0.0
    return fd


def create_censor_file(motion_path, fd_threshold, censor_prev_tr, out_dir, out_prefix, label, logger, run_lengths=None):
    """
    Generate a censor file from motion regressors using Power framewise displacement.

    A TR is censored when FD > fd_threshold. Writes the FD series to
    ``{out_prefix}_{label}_fd.1D`` and the censor vector to
    ``{out_prefix}_{label}_censor.1D``.

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
    run_lengths : list of int or None
        TRs per concatenated run; see power_fd.

    Returns
    -------
    pathlib.Path
        Path to the generated censor file.

    Raises
    ------
    InputError
        If the motion file is unreadable, has fewer than 6 columns, holds
        non-finite values (NaN compares False, so that TR would not be censored),
        or does not match run_lengths.
    """
    censor_path = Path(out_dir) / f"{out_prefix}_{label}_censor.1D"

    # Skip if censor file already exists
    if censor_path.exists():
        logger.info("Censor file %s already exists (skipping generation).", censor_path)
    else:
        try:
            motion = np.loadtxt(motion_path, ndmin=2)
        except Exception as e:
            raise InputError(f"Cannot read motion file '{motion_path}': {e}") from e
        if motion.shape[1] < 6:
            raise InputError(f"Motion file '{motion_path}' has {motion.shape[1]} columns, expected >= 6.")
        if not np.isfinite(motion[:, :6]).all():
            raise InputError(f"Motion file '{motion_path}' has non-finite values in its first 6 columns.")
        if run_lengths and sum(run_lengths) != len(motion):
            raise InputError(f"Motion file '{motion_path}' has {len(motion)} rows, "
                             f"but run_lengths {run_lengths} sum to {sum(run_lengths)}.")

        fd = power_fd(motion, run_lengths)
        high_motion = fd > fd_threshold
        keep = ~high_motion
        if censor_prev_tr:
            # FD is 0 at each run's first TR, so this never crosses a run boundary
            keep[:-1] &= ~high_motion[1:]

        np.savetxt(censor_path.with_name(f"{out_prefix}_{label}_fd.1D"), fd, fmt="%.6f")
        np.savetxt(censor_path, keep.astype(int), fmt="%d")

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
    pathlib.Path
        Path to the notch-filtered motion file.
    """
    # Extract first 6 columns (base motion only)
    motion_6col = prepare_motion_file(motion_path, 6, out_dir, out_prefix, f"{label}_notch_src", logger)

    out_path = Path(out_dir) / f"{out_prefix}_{label}_notch_motion.1D"

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
    _restore_time_rows(out_path, "notch-filtered motion", "notch filter", label, logger)

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
    pathlib.Path
        Absolute path to the interpolated 1D file in rows=TRs, cols=columns
        orientation.
    """
    out_path = Path(out_dir) / f"{out_prefix}_{label}_interp.1D"
    input_path = _as_1d(input_path, out_dir, out_prefix, label)

    cmd = ["3dTproject",
           "-polort", "-1",
           "-dt", str(tr),
           "-input", f"{input_path}'",
           "-censor", censor_path,
           "-cenmode", "NTRP",
           "-prefix", out_path]

    run_afni_command(cmd, description=f"3dTproject NTRP interpolate {label}", logger=logger)
    _restore_time_rows(out_path, "NTRP-interpolated 1D", "interpolate", label, logger)

    logger.info("NTRP-interpolated 1D file (rows=TRs, cols=cols) saved to %s", out_path)
    return out_path


def bandpass_filter_1d_afni(input_path, tr, bandpass, out_dir, out_prefix, label, logger):
    """
    Bandpass-filter a nuisance regressor 1D file using AFNI 3dBandpass.

    Invokes ``3dBandpass`` to apply its quadratic detrend and a bandpass filter to
    the input 1D file over the passband specified by ``bandpass[0]`` (fbot) and
    ``bandpass[1]`` (ftop).  Both match the BOLD bandpass step so that nuisance
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
    pathlib.Path
        Absolute path to the bandpass-filtered 1D file in rows=TRs, cols=columns
        orientation.
    """
    out_path = Path(out_dir) / f"{out_prefix}_{label}_bp.1D"
    input_path = _as_1d(input_path, out_dir, out_prefix, label)

    cmd = ["3dBandpass",
           "-dt", str(tr),
           "-prefix", out_path,
           str(bandpass[0]), str(bandpass[1]),
           f"{input_path}'"]

    run_afni_command(cmd, description=f"3dBandpass {label}", logger=logger)
    _restore_time_rows(out_path, "bandpass-filtered 1D", "bandpass", label, logger)

    logger.info("Bandpass-filtered 1D file (rows=TRs, cols=cols) saved to %s", out_path)
    return out_path


def compute_tissue_derivative(tissue_path, out_dir, out_prefix, tissue_label, logger, run_lengths=None):
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
    run_lengths : list of int or None
        TRs per concatenated run. The derivative is 0 at each run's first TR.

    Returns
    -------
    pathlib.Path
        Path to the derivative file.
    """
    try:
        data = np.loadtxt(tissue_path)
    except Exception as e:
        raise InputError(f"Cannot read tissue file '{tissue_path}': {e}") from e
    if data.ndim != 1:
        raise InputError(f"Tissue file '{tissue_path}' must be single-column, got shape {data.shape}.")
    deriv = np.diff(data, prepend=data[0])
    if run_lengths:
        deriv[np.cumsum(run_lengths)[:-1]] = 0.0
    deriv_path = Path(out_dir) / f"{out_prefix}_{tissue_label}_deriv.txt"
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
    pathlib.Path
        Path to the extracted single-volume NIfTI.
    """
    out_name = _labeled_name(out_file_pre, label, "min_outlier_epi.nii.gz")
    out_path = Path(out_dir) / out_name

    # Skip if already exists
    if out_path.exists():
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

    if out_path.exists():
        logger.info("Successfully extracted min-outlier EPI: %s", out_path)
    else:
        raise ToolExecutionError(f"Failed to create min-outlier EPI: {out_path}")

    return out_path


def run_segments(scan_path, run_lengths=None):
    """(run number, AFNI selector) for each run of a scan; a scan without run_lengths is one run."""
    if not run_lengths or len(run_lengths) < 2:
        return [(1, str(scan_path))]
    segments = []
    start = 0
    for run, n_trs in enumerate(run_lengths, 1):
        segments.append((run, f"{scan_path}[{start}..{start + n_trs - 1}]"))
        start += n_trs
    return segments


def count_nonzero(path, logger):
    """Count a dataset's non-zero voxels."""
    out = run_afni_command(["3dBrickStat", "-non-zero", "-count", path], capture_output=True,
                           description="3dBrickStat -count", logger=logger)
    return int(out.split()[0])


def nonconstant_mask(input_spec, mask_path, logger):
    """Write a mask of the voxels whose maximum differs from their minimum."""
    mask_path = Path(mask_path)
    range_path = mask_path.with_name(f"range_{mask_path.name}")
    run_afni_command(["3dTstat", "-max", "-min", "-prefix", range_path, input_spec],
                     description="3dTstat max and min", logger=logger)
    run_afni_command(["3dcalc", "-a", f"{range_path}[0]", "-b", f"{range_path}[1]",
                      "-expr", "step(a-b)", "-prefix", mask_path],
                     description="3dcalc non-constant mask", logger=logger)
    return mask_path


def psc_qc(input_spec, mean_path, run, logger):
    """Build a psc_per_run record for one run, and refuse demeaned input.

    Raises
    ------
    InputError
        If PSC_NONPOSITIVE_LIMIT percent or more of the non-constant voxels have a
        temporal mean <= 0. Dividing by such a mean gives no percent signal change.
    """
    mean_path = Path(mean_path)
    with tempfile.TemporaryDirectory(dir=mean_path.parent) as tmp:
        tmp = Path(tmp)
        mask = nonconstant_mask(input_spec, tmp / "mask.nii.gz", logger)
        n_mask = count_nonzero(mask, logger)
        if n_mask == 0:
            return {"run": run, "n_mask_voxels": 0, "n_guarded_voxels": None, "pct_guarded_voxels": None,
                    "n_capped_voxels": None, "pct_capped_voxels": None,
                    "n_nonpositive_mean_voxels": None, "pct_nonpositive_mean_voxels": None}
        data_range = tmp / "range_mask.nii.gz"

        def count(name, *inputs, expr):
            path = tmp / f"{name}.nii.gz"
            run_afni_command(["3dcalc", *inputs, "-expr", expr, "-prefix", path],
                             description=f"3dcalc PSC QC {name}", logger=logger)
            return count_nonzero(path, logger)

        n_guarded = count("guarded", "-a", mask, "-b", f"{data_range}[1]", "-c", mean_path,
                          expr="a*or(not(ispositive(b)),not(ispositive(c)))")
        n_capped = count("capped", "-a", mask, "-b", mean_path, "-c", f"{data_range}[0]",
                         expr="a*ispositive(b)*step(c-2*b)")
        n_nonpositive = count("nonpositive", "-a", mask, "-b", mean_path, expr="a*not(ispositive(b))")

    pct_nonpositive = round(100.0 * n_nonpositive / n_mask, 2)
    if pct_nonpositive >= PSC_NONPOSITIVE_LIMIT:
        raise InputError(f"Run {run}: {pct_nonpositive}% of non-constant voxels have a temporal mean <= 0, "
                         "so the input looks demeaned. Percent signal change needs a positive baseline; "
                         "set scale_to_psc: false for demeaned input.")
    return {"run": run, "n_mask_voxels": n_mask,
            "n_guarded_voxels": n_guarded, "pct_guarded_voxels": round(100.0 * n_guarded / n_mask, 2),
            "n_capped_voxels": n_capped, "pct_capped_voxels": round(100.0 * n_capped / n_mask, 2),
            "n_nonpositive_mean_voxels": n_nonpositive, "pct_nonpositive_mean_voxels": pct_nonpositive}


def psc_scale(input_spec, mean_path, psc_path, logger):
    """Write the voxelwise mean of input_spec and input_spec scaled to PSC."""
    run_afni_command(
        ["3dTstat", "-mean", "-prefix", mean_path, input_spec],
        description="3dTstat temporal mean for PSC scaling",
        logger=logger,
    )

    run_afni_command(
        ["3dcalc",
         "-a", input_spec,
         "-b", mean_path,
         "-expr", "min(200,a/b*100)*step(a)*step(b)",
         "-prefix", psc_path],
        description="3dcalc PSC scaling",
        logger=logger,
    )


def scale_to_psc(scan_path, out_dir, out_file_pre, label, logger, run_lengths=None, qc_records=None, run=1):
    """Scale a 4D NIfTI to percent signal change (PSC).

    Computes the voxelwise temporal mean via 3dTstat, then divides each
    voxel's time series by its mean and multiplies by 100, with a 200%
    ceiling and zero-guard via step functions.

    With more than one run in run_lengths, each run is scaled by its own mean
    and the scaled runs are concatenated, so that the mean is
    ``{out_file_pre}_run{N}_mean.nii.gz`` per run.

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
    run_lengths : list of int or None
        TRs per concatenated run.
    qc_records : list or None
        If given, each run's psc_qc record is appended to it.
    run : int
        Run number for the record when the scan is a single run.

    Returns
    -------
    pathlib.Path
        Path to the PSC-scaled 4D NIfTI.

    Raises
    ------
    InputError
        If the input looks demeaned; see psc_qc.
    """
    out_dir = Path(out_dir)
    psc_path = out_dir / _labeled_name(out_file_pre, label, "psc.nii.gz")

    if psc_path.exists():
        logger.info("PSC-scaled file already exists: %s", psc_path)
        return psc_path

    segments = run_segments(scan_path, run_lengths)
    if len(segments) > 1:
        run_psc_paths = []
        for segment_run, spec in segments:
            run_label = f"{label}_run{segment_run}" if label else f"run{segment_run}"
            run_psc = out_dir / _labeled_name(out_file_pre, run_label, "psc.nii.gz")
            mean_path = out_dir / _labeled_name(out_file_pre, run_label, "mean.nii.gz")
            psc_scale(spec, mean_path, run_psc, logger)
            if qc_records is not None:
                qc_records.append(psc_qc(spec, mean_path, segment_run, logger))
            run_psc_paths.append(run_psc)
        run_afni_command(["3dTcat", "-prefix", psc_path, *run_psc_paths],
                         description="3dTcat per-run PSC scans", logger=logger)
        for run_psc in run_psc_paths:
            run_psc.unlink()
    else:
        mean_path = out_dir / _labeled_name(out_file_pre, label, "mean.nii.gz")
        psc_scale(scan_path, mean_path, psc_path, logger)
        if qc_records is not None:
            qc_records.append(psc_qc(scan_path, mean_path, run, logger))

    logger.info("PSC-scaled scan written to %s", psc_path)
    return psc_path
