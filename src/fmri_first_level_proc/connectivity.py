"""Seed-to-voxel and parcellated functional connectivity via 3dNetCorr, plus matrix contrasts."""

import logging
import shutil
from pathlib import Path

import numpy as np

from .afni import run_afni_command
from .exceptions import InputError, ToolExecutionError


def _conn_suffix(fishZ, pcorr, calc_conn):
    """Filename suffix encoding the correlation type and output format."""
    stat = {(True, True): "_pcorr_fishZ", (True, False): "_fishZ",
            (False, True): "_pcorr", (False, False): "_corr"}[(bool(fishZ), bool(pcorr))]
    return stat + ("_mat.txt" if calc_conn == "parcellated" else ".nii.gz")


def _conn_prefix(conn_out_file_pre, condition):
    return f"{conn_out_file_pre}_{condition}" if condition is not None else conn_out_file_pre


def build_conn_output_path(out_dir, conn_out_file_pre, condition, fishZ, pcorr, calc_conn):
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

    Returns
    -------
    pathlib.Path
        Full path to the expected connectivity output file.
    """
    prefix = _conn_prefix(conn_out_file_pre, condition)
    return Path(out_dir) / (prefix + _conn_suffix(fishZ, pcorr, calc_conn))


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


def format_netcorr_mat(netcorr_file, fishZ, pcorr, curr_out_path):
    """Parse a 3dNetCorr .netcc output file and save the desired matrix as tab-delimited text.

    The .netcc file contains multiple labeled matrix sections. The section to extract
    depends on the fishZ and pcorr flags:
    - fishZ=False, pcorr=False  → CC (Pearson correlation)
    - fishZ=False, pcorr=True   → PC (partial correlation)
    - fishZ=True,  pcorr=False  → FZ (Fisher Z-transformed correlation)
    - fishZ=True,  pcorr=True   → PCB (Fisher Z-transformed partial correlation)

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
    """
    if not fishZ and not pcorr:
        entry_to_check = "CC"
        end_to_check = "Z"
    elif not fishZ and pcorr:
        entry_to_check = "PC"
        end_to_check = "PCB"
    elif fishZ and not pcorr:
        entry_to_check = "FZ"
        end_to_check = "Z"
    else:
        entry_to_check = "PCB"
        end_to_check = "Z"

    conn_mat = [line.split() for line in Path(netcorr_file).read_text().splitlines()]

    start_row = 0
    end_row = 0
    for i, entry in enumerate(conn_mat):
        if len(entry) == 2 and entry[1] == entry_to_check:
            start_row = i + 1
            for j, next_entry in enumerate(conn_mat[i + 1:]):
                if len(next_entry) == 2 and next_entry[1] == end_to_check:
                    end_row = j + i + 1
                    break
            if end_row == 0:
                end_row = len(conn_mat)
            break

    out_conn_mat = conn_mat[start_row:end_row]
    Path(curr_out_path).write_text("".join("\t".join(row) + "\n" for row in out_conn_mat))


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
