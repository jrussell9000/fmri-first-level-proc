"""Seed-to-voxel and parcellated functional connectivity via 3dNetCorr, plus matrix contrasts."""

import logging
import shutil
import tempfile
from pathlib import Path

import numpy as np

from .afni import run_afni_command
from .exceptions import InputError, ToolExecutionError
from .fileutils import with_token
from .templates import extract_roi_stats


def _conn_suffix(fishZ, pcorr, calc_conn):
    """Filename suffix encoding the correlation type and output format."""
    stat = {(True, True): "_pcorr_fishZ", (True, False): "_fishZ",
            (False, True): "_pcorr", (False, False): "_corr"}[(bool(fishZ), bool(pcorr))]
    return stat + ("_mat.txt" if calc_conn == "parcellated" else ".nii.gz")


def _conn_prefix(conn_out_file_pre, condition):
    return f"{conn_out_file_pre}_{condition}" if condition is not None else conn_out_file_pre


def build_conn_output_path(out_dir, conn_out_file_pre, condition, fishZ, pcorr, calc_conn, token=""):
    """Construct the expected connectivity output path for a given condition.

    Parameters
    ----------
    out_dir : str or os.PathLike
        Output directory.
    conn_out_file_pre : str
        Connectivity output file prefix.
    condition : str or None
        Condition name; None for resting-state (no condition in the filename).
    fishZ : bool
        Whether Fisher Z-transform was applied.
    pcorr : bool
        Whether partial correlation was used.
    calc_conn : str
        Either 'parcellated' or 'seed_to_voxel'.
    token : str
        Smoothing token for a smoothed sibling; see smoothing.smoothing_token.

    Returns
    -------
    pathlib.Path
        Full path to the expected connectivity output file.
    """
    prefix = _conn_prefix(conn_out_file_pre, condition)
    return with_token(Path(out_dir) / (prefix + _conn_suffix(fishZ, pcorr, calc_conn)), token)


def compute_matrix_contrast(condition_matrix_paths, coefs, out_path, logger):
    """Apply a weighted linear combination to tab-delimited square connectivity matrices.

    Parameters
    ----------
    condition_matrix_paths : list of str or os.PathLike
        Paths to the condition-specific connectivity matrices (tab-delimited text).
    coefs : list of str
        Coefficients corresponding to each matrix (as strings, will be cast to float).
    out_path : str or os.PathLike
        Path to save the resulting contrast matrix.
    logger : logging.Logger

    Raises
    ------
    InputError
        If matrices have mismatched dimensions or cannot be loaded.
    """
    matrices = []
    for path in condition_matrix_paths:
        try:
            mat = np.loadtxt(path, delimiter='\t')
        except Exception as e:
            raise InputError(f"Could not load connectivity matrix '{path}': {e}") from e
        matrices.append(mat)

    # Validate all matrices have identical dimensions
    ref_shape = matrices[0].shape
    for i, mat in enumerate(matrices[1:], start=1):
        if mat.shape != ref_shape:
            raise InputError(
                f"Connectivity matrix dimension mismatch: '{condition_matrix_paths[i]}' has shape {mat.shape}, "
                f"expected {ref_shape} (from '{condition_matrix_paths[0]}')."
            )

    # Compute weighted linear combination
    result = np.zeros(ref_shape)
    for coef_str, mat in zip(coefs, matrices):
        result += float(coef_str) * mat

    # Write using standard I/O (avoids numpy DataSource path resolution issues)
    if result.ndim == 1:
        result = result.reshape(1, -1)
    Path(out_path).write_text("".join('\t'.join(f'{val:.8f}' for val in row) + '\n' for row in result))
    logger.info("Connectivity contrast matrix saved to %s", out_path)


def seed_to_voxel_conn(inset_path, out_dir, conn_out_file_pre, template_path, fishZ, pcorr, condition=None, logger=None):

    """
    Run seed-to-voxel functional connectivity using AFNI's 3dNetCorr.

    Parameters
    ----------
    inset_path : str or os.PathLike
        Path to the input time series / beta series NIfTI.
    out_dir : str or os.PathLike
        Output directory.
    conn_out_file_pre : str
        Output file prefix.
    template_path : str or os.PathLike
        Path to the binary seed mask.
    fishZ : bool
        Whether to Fisher Z-transform correlations.
    pcorr : bool
        Whether to use partial correlation.
    condition : str or None
        If provided, included in the output filename (task-based).
        If None, omitted (resting-state).
    logger : logging.Logger, optional
    """
    _log = logger or logging.getLogger(__name__)

    prefix = _conn_prefix(conn_out_file_pre, condition)
    out_path = build_conn_output_path(out_dir, conn_out_file_pre, condition, fishZ, pcorr, "seed_to_voxel")

    if out_path.exists():
        _log.info("Functional connectivity for %s already exists.", prefix)
        return

    # Build and run 3dNetCorr
    netcorr_prefix = Path(out_dir) / prefix
    netCorr_command = [
        "3dNetCorr", "-prefix", netcorr_prefix,
        "-inset", inset_path,
        "-in_rois", template_path, "-push_thru_many_zeros",
        "-ts_wb_corr", "-nifti",
    ]
    if fishZ:
        netCorr_command.append("-ts_wb_Z")
    if pcorr:
        netCorr_command.append("-part_corr")

    try:
        run_afni_command(netCorr_command, description="3dNetCorr seed-to-voxel", logger=logger)
    except ToolExecutionError:
        _log.warning("Could not create functional connectivity for seed %s.", template_path)
        return

    # Clean up auxiliary outputs
    for ext in ["_000.niml.dset", "_000.roidat", "_000.netcc"]:
        netcorr_prefix.with_name(netcorr_prefix.name + ext).unlink(missing_ok=True)

    # Move the connectivity map from the INDIV directory
    indiv_dir = netcorr_prefix.with_name(netcorr_prefix.name + "_000_INDIV")
    if not indiv_dir.is_dir():
        _log.warning("Could not create functional connectivity for seed %s.", template_path)
        return

    src_file = indiv_dir / ("WB_Z_ROI_001.nii.gz" if fishZ else "WB_CORR_ROI_001.nii.gz")
    if src_file.exists():
        src_file.rename(out_path)
    else:
        _log.warning("Could not create functional connectivity for seed %s.", template_path)

    # Remove the INDIV directory and anything left in it (e.g. the unused WB_CORR map)
    shutil.rmtree(indiv_dir, ignore_errors=True)

    if out_path.exists():
        _log.info("Seed-to-voxel functional connectivity maps created for %s with seed from template %s.", prefix, template_path)
    else:
        _log.warning("Could not move functional connectivity file for seed %s. Check permissions and rerun.", template_path)


def seed_to_voxel_smoothed(seed_inset_path, target_path, out_dir, conn_out_file_pre, template_path,
                           fishZ, pcorr, token, condition=None, logger=None):
    """Write the smoothed sibling of a seed-to-voxel map.

    The seed time series comes from the unsmoothed data and the target is smoothed.
    3dNetCorr takes both from one dataset, so this uses 3dTcorr1D, with the same Fisher Z
    cap as 3dNetCorr. With one seed, the map is the same whether or not pcorr is set.

    Parameters
    ----------
    seed_inset_path : str or os.PathLike
        Unsmoothed series the seed time series is averaged from.
    target_path : str or os.PathLike
        Smoothed series.
    out_dir, conn_out_file_pre, template_path, fishZ, pcorr, condition
        As for seed_to_voxel_conn.
    token : str
        Smoothing token for the output file name.
    logger : logging.Logger, optional
    """
    out_path = build_conn_output_path(out_dir, conn_out_file_pre, condition, fishZ, pcorr,
                                      "seed_to_voxel", token)
    if out_path.exists():
        return
    seed = extract_roi_stats(seed_inset_path, template_path, "mean", logger=logger)
    with tempfile.TemporaryDirectory(dir=out_dir) as tmp:
        seed_path = Path(tmp) / "seed.1D"
        np.savetxt(seed_path, seed.to_numpy()[:, 0])
        r_path = out_path if not fishZ else Path(tmp) / "r.nii.gz"
        run_afni_command(["3dTcorr1D", "-pearson", "-prefix", r_path, target_path, seed_path],
                         description="3dTcorr1D smoothed seed-to-voxel", logger=logger)
        if fishZ:
            limit = np.tanh(_FISHER_Z_CAP)
            run_afni_command(["3dcalc", "-a", r_path, "-expr", f"atanh(min(max(a,{-limit}),{limit}))",
                              "-prefix", out_path],
                             description="3dcalc Fisher Z of smoothed seed map", logger=logger)


# 3dNetCorr's FZ section is arctanh with |z| capped at 4.0 (r = 1 -> 4.0). Partial
# correlations are transformed with the same cap so both Fisher-Z outputs agree.
_FISHER_Z_CAP = 4.0


def _netcc_sections(netcorr_file):
    """Split a .netcc file into {section name: rows of tokens}.

    Section headers are '# NAME' lines (e.g. '# CC'); the ROI label/index rows
    that follow '# WITH_ROI_LABELS' land in that pseudo-section and are ignored.
    """
    sections, current = {}, None
    for line in Path(netcorr_file).read_text().splitlines():
        tokens = line.split()
        if not tokens:
            continue
        if tokens[0] == "#":
            current = tokens[1] if len(tokens) == 2 else None
            if current is not None:
                sections[current] = []
        elif current is not None:
            sections[current].append(tokens)
    return sections


def format_netcorr_mat(netcorr_file, fishZ, pcorr, curr_out_path):
    """Parse a 3dNetCorr .netcc output file and save the desired matrix as tab-delimited text.

    3dNetCorr writes CC always, FZ with -fish_z, and PC and PCB with -part_corr.
    The flags select:
    - fishZ=False, pcorr=False  -> CC (Pearson correlation), verbatim
    - fishZ=False, pcorr=True   -> PC (partial correlation), verbatim
    - fishZ=True,  pcorr=False  -> FZ (Fisher Z of CC), verbatim
    - fishZ=True,  pcorr=True   -> Fisher Z of PC, computed here as arctanh with
      |z| capped at 4.0 like AFNI's FZ. AFNI writes no Fisher-Z partial
      correlation; PCB holds asymmetric partial-correlation regression
      coefficients and is never used. AFNI's PC diagonal is -1, so this
      matrix's diagonal is -4.0; it carries no connectivity information.

    Parameters
    ----------
    netcorr_file : str or os.PathLike
        Path to the 3dNetCorr .netcc output file.
    fishZ : bool
        Whether Fisher Z-transform was requested.
    pcorr : bool
        Whether partial correlation was requested.
    curr_out_path : str or os.PathLike
        Destination path for the tab-delimited matrix text file.

    Raises
    ------
    ToolExecutionError
        If the .netcc file lacks the section the flags require.
    """
    name = "PC" if pcorr else ("FZ" if fishZ else "CC")
    sections = _netcc_sections(netcorr_file)
    if not sections.get(name):
        raise ToolExecutionError(f"3dNetCorr output {netcorr_file} has no '{name}' matrix.")
    rows = sections[name]

    if fishZ and pcorr:
        r = np.array(rows, dtype=float)
        limit = np.tanh(_FISHER_Z_CAP)
        z = np.arctanh(np.clip(r, -limit, limit))
        rows = [[f"{v:.4f}" for v in row] for row in z]

    Path(curr_out_path).write_text("".join("\t".join(row) + "\n" for row in rows))


def parcellated_conn(inset_path, out_dir, conn_out_file_pre, template_path, fishZ, pcorr, condition=None, logger=None):

    """
    Run parcellated (ROI-to-ROI) functional connectivity using AFNI's 3dNetCorr.

    Parameters
    ----------
    inset_path : str or os.PathLike
        Path to the input time series / beta series NIfTI.
    out_dir : str or os.PathLike
        Output directory.
    conn_out_file_pre : str
        Output file prefix.
    template_path : str or os.PathLike
        Path to the multi-ROI parcellation template.
    fishZ : bool
        Whether to Fisher Z-transform correlations.
    pcorr : bool
        Whether to use partial correlation.
    condition : str or None
        If provided, included in the output filename (task-based).
        If None, omitted (resting-state).
    logger : logging.Logger, optional
    """
    _log = logger or logging.getLogger(__name__)

    prefix = _conn_prefix(conn_out_file_pre, condition)
    out_path = build_conn_output_path(out_dir, conn_out_file_pre, condition, fishZ, pcorr, "parcellated")

    if out_path.exists():
        _log.info("Functional connectivity for %s already exists.", prefix)
        return

    # Build and run 3dNetCorr
    netcorr_prefix = Path(out_dir) / prefix
    netCorr_command = [
        "3dNetCorr", "-prefix", netcorr_prefix,
        "-inset", inset_path,
        "-in_rois", template_path, "-push_thru_many_zeros",
    ]
    if fishZ:
        netCorr_command.append("-fish_z")
    if pcorr:
        netCorr_command.append("-part_corr")

    try:
        run_afni_command(netCorr_command, description="3dNetCorr parcellated", logger=logger)
    except ToolExecutionError:
        _log.warning("Could not create functional connectivity for template %s.", template_path)
        return

    # Clean up auxiliary outputs
    for ext in ["_000.niml.dset", "_000.roidat"]:
        netcorr_prefix.with_name(netcorr_prefix.name + ext).unlink(missing_ok=True)

    netcc_file = netcorr_prefix.with_name(netcorr_prefix.name + "_000.netcc")
    if not netcc_file.exists():
        raise ToolExecutionError(f"Could not create functional connectivity for template {template_path}.")
    format_netcorr_mat(netcc_file, fishZ, pcorr, out_path)
    if not out_path.exists():
        raise ToolExecutionError(f"Could not format functional connectivity for template {template_path}. Likely an internal bug.")
    netcc_file.unlink()
    _log.info("Parcellated functional connectivity matrix created for %s with ROIs from template %s.", prefix, template_path)
