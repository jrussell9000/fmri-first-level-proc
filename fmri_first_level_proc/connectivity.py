"""Parcellated and seed-to-voxel connectivity computation.

Parcellated connectivity uses 3dROIstats + 1ddot -dem (columns demeaned, so
the matrix is Pearson correlation) with rank gate, partial correlation,
Fisher Z clip and null-ROI NaN handling.

Precision: 1ddot prints the correlation matrix and its inverse with five
fixed decimals (observed on AFNI 26.0.09, both blocks), and values are parsed
from that text. With d = 5, r carries rounding error of about 0.5 x 10^-d,
partial correlation (from the inverse, whose diagonal is at least 1) at most
about 10^-d, and Fisher Z at most the input bound divided by
1 - 0.999329^2 at the clip. These are far below the sampling error of r at
typical first-level series lengths.

Seed-to-voxel connectivity uses 3dTcorr1D + 3dcalc with clipped atanh,
null-seed and zero-variance target handling.

Linear contrasts: matrix_contrast for parcellated, seed_contrast for
seed-to-voxel.
"""

import os

import numpy as np

from .engine import Output
from .exceptions import InputError, ToolExecutionError
from .first_level_utils import run_afni_command, graded_warning, format_table
from .roi import extract_roi_stats, count_nonzero_by_roi


R_CLIP = 0.999329


# ---------------------------------------------------------------------------
# 1ddot parsing
# ---------------------------------------------------------------------------

def parse_1ddot(stdout):
    """Parse 1ddot output into correlation and inverse-correlation matrices.

    Parameters
    ----------
    stdout : str

    Returns
    -------
    (np.ndarray, np.ndarray)
        Correlation matrix and correlation-matrix inverse.
    """
    def _parse_block(lines, start_idx):
        """Parse a matrix block starting at start_idx (after header + dashes)."""
        # Skip the index header line and dashed separator line
        i = start_idx + 1  # skip the column-index header
        if i < len(lines) and "-----" in lines[i]:
            i += 1  # skip dashes
        rows = []
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                break
            # Parse "NN: v1 v2 ..."
            parts = line.split(":")
            if len(parts) < 2:
                break
            values = parts[1].split()
            try:
                rows.append([float(v) for v in values])
            except ValueError:
                break
            i += 1
        return np.array(rows), i

    lines = stdout.splitlines()

    corr = None
    inv = None
    i = 0
    while i < len(lines):
        if "++ Correlation Matrix:" in lines[i]:
            # Next line is the column-index header
            corr, i = _parse_block(lines, i + 1)
        elif "++ Correlation Matrix Inverse:" in lines[i] and "Normalized" not in lines[i]:
            inv, i = _parse_block(lines, i + 1)
        else:
            i += 1

    if corr is None:
        raise ToolExecutionError(
            "1ddot output: could not find '++ Correlation Matrix:' block."
        )
    if inv is None:
        raise ToolExecutionError(
            "1ddot output: could not find '++ Correlation Matrix Inverse:' block."
        )

    return corr, inv


# ---------------------------------------------------------------------------
# Rank check
# ---------------------------------------------------------------------------

def rank_check(series_df):
    """Compute (n_rois, rank, n_timepoints) for a parcellated time-series DataFrame.

    Parameters
    ----------
    series_df : pd.DataFrame
        Rows = time points, columns = ROIs.

    Returns
    -------
    (int, int, int)
        (n_rois, rank, n_timepoints)
    """
    X = series_df.values.astype(np.float64)
    X = X - X.mean(axis=0)
    n, m = X.shape
    s = np.linalg.svd(X, compute_uv=False)
    tol = s.max() * max(n, m) * np.finfo(np.float32).eps
    rank = int((s > tol).sum())
    return m, rank, n


# ---------------------------------------------------------------------------
# Matrix text formatting
# ---------------------------------------------------------------------------

def matrix_text(mat):
    """Format a matrix as tab-delimited text with NaN support.

    Returns
    -------
    str
        Tab-delimited rows, values f"{v:.8f}" or "NaN". Trailing newline.
    """
    lines = []
    for row in mat:
        tokens = []
        for v in row:
            if np.isnan(v):
                tokens.append("NaN")
            else:
                tokens.append(f"{v:.8f}")
        lines.append("\t".join(tokens))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Parcellated connectivity
# ---------------------------------------------------------------------------

def parcellated(io, input_spec, template, average_type, roi_zero_handling,
                fishZ, pcorr, out_rel, condition, logger):
    """Compute parcellated (Pearson) connectivity via 3dROIstats + 1ddot -dem.

    Parameters
    ----------
    io : StepIO
    input_spec : str
        Input NIfTI (e.g. beta-series or residual concat).
    template : str
        Resolved template path.
    average_type : str
    roi_zero_handling : str
    fishZ : bool
    pcorr : bool
    out_rel : str
        Output relpath for the matrix file.
    condition : str or None
    logger : logging.Logger

    Returns
    -------
    (Output or None, dict)
        Output is None when pcorr is skipped (rank deficient).
    """
    df = extract_roi_stats(input_spec, template, average_type,
                           roi_zero_handling, logger)
    all_labels = [int(c.replace("ROI_", "")) for c in df.columns]

    # Identify null ROIs (zero variance)
    keep = np.ptp(df.values, axis=0) != 0
    non_null_labels = [l for l, k in zip(all_labels, keep) if k]
    null_labels = [l for l, k in zip(all_labels, keep) if not k]
    nn_idx = np.flatnonzero(keep)

    qc = {}

    # Pcorr rank check (on full matrix including nulls)
    if pcorr:
        m, rank, n = rank_check(df)
        cond_name = condition or "rest"
        qc["pcorr_rank_checks"] = [{
            "condition": cond_name,
            "n_rois": m,
            "rank": rank,
            "n_timepoints": n,
            "skipped": rank < m,
        }]
        if rank < m:
            graded_warning(
                logger, "high", "PCORR_RANK_DEFICIENT",
                f"Partial correlation skipped for {cond_name}: "
                f"rank {rank} < {m} ROIs (n={n} time points).",
                user_facing=True,
            )
            return None, qc

    # Write non-null series for 1ddot
    if not non_null_labels:
        raise ToolExecutionError(
            "All ROIs have zero variance; cannot compute correlations."
        )

    non_null_df = df[[f"ROI_{lbl}" for lbl in non_null_labels]]
    series_text = format_table(non_null_df.values, fmt="%.9g")
    series_path = io.path("_series.1D")
    with open(series_path, "w", newline="") as f:
        f.write(series_text)

    stdout = run_afni_command(
        ["1ddot", "-dem", series_path],
        capture_output=True,
        description="1ddot parcellated correlation",
        logger=logger, cwd=io.staging,
    )
    corr, inv = parse_1ddot(stdout)

    if pcorr:
        # Partial correlation from inverse
        diag = np.diag(inv)
        vals = -inv / np.sqrt(np.outer(diag, diag))
        np.fill_diagonal(vals, 1.0)
    else:
        vals = corr

    if fishZ:
        vals = np.arctanh(np.clip(vals, -R_CLIP, R_CLIP))

    # Expand to full matrix with NaN for null ROIs
    full = np.full((len(all_labels), len(all_labels)), np.nan)
    full[np.ix_(nn_idx, nn_idx)] = vals

    # Null ROI warning
    if null_labels:
        cond_name = condition or "rest"
        graded_warning(
            logger, "high", "NULL_ROI",
            f"Condition {cond_name}: ROIs with zero variance (null): "
            f"{null_labels}. Corresponding rows/columns are NaN.",
            user_facing=True,
        )
        qc["null_rois"] = [{
            "condition": cond_name,
            "output": os.path.basename(out_rel),
            "rois": null_labels,
        }]

    text = matrix_text(full)
    with open(io.path(out_rel), "w", newline="") as f:
        f.write(text)

    output = Output(out_rel, "final", "py_text",
                    producer="parcellated connectivity",
                    expected_text=text)
    return output, qc


# ---------------------------------------------------------------------------
# Seed-to-voxel connectivity
# ---------------------------------------------------------------------------

def seed_to_voxel(io, seed_input_spec, target_spec, seed_mask,
                  average_type, roi_zero_handling, fishZ, out_rel,
                  condition, logger):
    """Compute seed-to-voxel connectivity via 3dTcorr1D.

    Parameters
    ----------
    io : StepIO
    seed_input_spec : str
        Input NIfTI for seed extraction.
    target_spec : str
        Target NIfTI for correlation.
    seed_mask : str
        Single-ROI mask for seed extraction.
    average_type, roi_zero_handling : str
    fishZ : bool
    out_rel : str
    condition : str or None
    logger : logging.Logger

    Returns
    -------
    (Output or None, dict, bool)
        (output, qc, is_null_seed)
    """
    seed_df = extract_roi_stats(seed_input_spec, seed_mask, average_type,
                                roi_zero_handling, logger)
    seed_col = seed_df.iloc[:, 0].values

    if np.ptp(seed_col) == 0:
        cond_name = condition or "rest"
        graded_warning(
            logger, "high", "SEED_NULL",
            f"Seed time series has zero variance for {cond_name}.",
            user_facing=True,
        )
        qc = {}
        if condition is not None:
            qc["null_seed_conditions"] = [{"condition": condition}]
        return None, qc, True

    # Write seed to 1D
    seed_path = io.path("_seed.1D")
    seed_text = format_table(seed_col.reshape(-1, 1), fmt="%.9g")
    with open(seed_path, "w", newline="") as f:
        f.write(seed_text)

    # 3dTcorr1D
    r_rel = "_r.nii.gz"
    run_afni_command(
        ["3dTcorr1D", "-pearson", "-prefix", io.path(r_rel),
         target_spec, seed_path],
        description="3dTcorr1D seed-to-voxel",
        logger=logger, cwd=io.staging,
    )

    # Zero-variance target voxel detection
    sd_rel = "_sd.nii.gz"
    absmax_rel = "_absmax_target.nii.gz"
    run_afni_command(
        ["3dTstat", "-stdev", "-prefix", io.path(sd_rel), target_spec],
        description="3dTstat stdev target",
        logger=logger, cwd=io.staging,
    )
    run_afni_command(
        ["3dTstat", "-absmax", "-prefix", io.path(absmax_rel), target_spec],
        description="3dTstat absmax target",
        logger=logger, cwd=io.staging,
    )

    zv_indicator_rel = "_zv_indicator.nii.gz"
    run_afni_command(
        ["3dcalc", "-a", io.path(sd_rel), "-b", io.path(absmax_rel),
         "-expr", "step(b)*iszero(a)",
         "-prefix", io.path(zv_indicator_rel)],
        description="3dcalc zero-variance indicator",
        logger=logger, cwd=io.staging,
    )
    zv_counts = count_nonzero_by_roi(
        io.path(zv_indicator_rel), io.path(zv_indicator_rel), logger
    )
    n_zero = zv_counts.get(1, 0)

    # Clean r-map (zero out zero-variance voxels)
    r_clean_rel = "_r_clean.nii.gz"
    run_afni_command(
        ["3dcalc", "-a", io.path(r_rel), "-b", io.path(sd_rel),
         "-expr", "a*step(b)",
         "-prefix", io.path(r_clean_rel)],
        description="3dcalc clean r-map",
        logger=logger, cwd=io.staging,
    )

    if fishZ:
        run_afni_command(
            ["3dcalc", "-a", io.path(r_clean_rel),
             "-expr", f"atanh(max(-{R_CLIP},min({R_CLIP},a)))",
             "-prefix", io.path(out_rel)],
            description="3dcalc Fisher Z",
            logger=logger, cwd=io.staging,
        )
    else:
        os.replace(io.path(r_clean_rel), io.path(out_rel))

    output = Output(out_rel, "final", "nifti", producer="seed-to-voxel connectivity")
    qc = {
        "zero_variance_target_voxels": [{
            "output": os.path.basename(out_rel),
            "n_voxels": n_zero,
        }],
    }
    return output, qc, False


# ---------------------------------------------------------------------------
# Contrasts
# ---------------------------------------------------------------------------

def matrix_contrast(paths, coefs, out_rel, io):
    """Compute a linear contrast of parcellated connectivity matrices.

    Parameters
    ----------
    paths : list of str
        Paths to the condition-level matrix text files.
    coefs : list of float
        Contrast coefficients aligned with paths.
    out_rel : str
        Output relpath.
    io : StepIO

    Returns
    -------
    Output
    """
    matrices = []
    for path in paths:
        m = np.loadtxt(path, delimiter="\t")
        matrices.append(m)

    # Shapes must match
    shape = matrices[0].shape
    for i, m in enumerate(matrices):
        if m.shape != shape:
            raise InputError(
                f"Matrix contrast: shape mismatch. Matrix 0 is {shape}, "
                f"matrix {i} is {m.shape}."
            )

    # Weighted sum (NaN preserved: NaN + anything = NaN)
    result = np.zeros(shape)
    for m, c in zip(matrices, coefs):
        result = result + c * m

    text = matrix_text(result)
    with open(io.path(out_rel), "w", newline="") as f:
        f.write(text)

    return Output(out_rel, "final", "py_text",
                  producer="matrix contrast",
                  expected_text=text)


def seed_contrast(io, paths, coefs, out_rel, label, logger):
    """Compute a linear contrast of seed-to-voxel connectivity maps.

    Parameters
    ----------
    io : StepIO
    paths : list of str
        Paths to the condition-level NIfTI maps.
    coefs : list of float
        Contrast coefficients.
    out_rel : str
    label : str
        Contrast label for logging.
    logger : logging.Logger

    Returns
    -------
    Output
    """
    letters = "abcdefghijklmnopqrstuvwxyz"
    if len(paths) > 26:
        raise InputError(
            f"Seed contrast '{label}' has {len(paths)} inputs (max 26)."
        )

    cmd = ["3dcalc"]
    expr_parts = []
    for i, path in enumerate(paths):
        letter = letters[i]
        cmd.extend([f"-{letter}", path])
        c = coefs[i]
        if c >= 0:
            expr_parts.append(f"{c}*{letter}")
        else:
            expr_parts.append(f"({c})*{letter}")

    cmd.extend(["-expr", "+".join(expr_parts), "-prefix", io.path(out_rel)])
    run_afni_command(
        cmd, description=f"3dcalc seed contrast {label}",
        logger=logger, cwd=io.staging,
    )

    return Output(out_rel, "final", "nifti", producer=f"seed contrast {label}")
