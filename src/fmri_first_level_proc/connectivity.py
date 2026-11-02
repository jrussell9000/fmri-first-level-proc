"""Seed-to-voxel and parcellated functional connectivity via 3dNetCorr, plus matrix contrasts."""

import logging
import os
import shutil

import numpy as np

from .afni import run_afni_command
from .exceptions import InputError, ToolExecutionError


def build_conn_output_path(out_dir, conn_out_file_pre, condition, fishZ, pcorr, calc_conn):
    """Construct the expected connectivity output path for a given condition.

    Parameters
    ----------
    out_dir : str
        Output directory.
    conn_out_file_pre : str
        Connectivity output file prefix.
    condition : str
        Condition name.
    fishZ : bool
        Whether Fisher Z-transform was applied.
    pcorr : bool
        Whether partial correlation was used.
    calc_conn : str
        Either 'parcellated' or 'seed_to_voxel'.

    Returns
    -------
    str
        Full path to the expected connectivity output file.
    """
    prefix = f"{conn_out_file_pre}_{condition}"
    out_path = os.path.join(out_dir, prefix)

    if calc_conn == "parcellated":
        if fishZ and pcorr:
            out_path += "_pcorr_fishZ_mat.txt"
        elif fishZ:
            out_path += "_fishZ_mat.txt"
        elif pcorr:
            out_path += "_pcorr_mat.txt"
        else:
            out_path += "_corr_mat.txt"
    else:  # seed_to_voxel
        if fishZ and pcorr:
            out_path += "_pcorr_fishZ.nii.gz"
        elif fishZ:
            out_path += "_fishZ.nii.gz"
        elif pcorr:
            out_path += "_pcorr.nii.gz"
        else:
            out_path += "_corr.nii.gz"

    return out_path


def compute_matrix_contrast(condition_matrix_paths, coefs, out_path, logger):
    """Apply a weighted linear combination to tab-delimited square connectivity matrices.

    Parameters
    ----------
    condition_matrix_paths : list of str
        Paths to the condition-specific connectivity matrices (tab-delimited text).
    coefs : list of str
        Coefficients corresponding to each matrix (as strings, will be cast to float).
    out_path : str
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
    with open(out_path, 'w') as f:
        for row in result:
            f.write('\t'.join(f'{val:.8f}' for val in row) + '\n')
    logger.info("Connectivity contrast matrix saved to %s", out_path)


def seed_to_voxel_conn(inset_path, out_dir, conn_out_file_pre, template_path, fishZ, pcorr, condition=None, logger=None):

    """
    Run seed-to-voxel functional connectivity using AFNI's 3dNetCorr.

    Parameters
    ----------
    inset_path : str
        Path to the input time series / beta series NIfTI.
    out_dir : str
        Output directory.
    conn_out_file_pre : str
        Output file prefix.
    template_path : str
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

    # Build output prefix and final path
    if condition is not None:
        prefix = f"{conn_out_file_pre}_{condition}"
    else:
        prefix = conn_out_file_pre

    out_path = os.path.join(out_dir, prefix)
    if fishZ and pcorr:
        out_path += "_pcorr_fishZ.nii.gz"
    elif fishZ:
        out_path += "_fishZ.nii.gz"
    elif pcorr:
        out_path += "_pcorr.nii.gz"
    else:
        out_path += "_corr.nii.gz"

    if os.path.exists(out_path):
        _log.info("Functional connectivity for %s already exists.", prefix)
        return

    # Build and run 3dNetCorr
    netcorr_prefix = os.path.join(out_dir, prefix)
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
        aux = f"{netcorr_prefix}{ext}"
        if os.path.exists(aux):
            os.remove(aux)

    # Move the connectivity map from the INDIV directory
    indiv_dir = f"{netcorr_prefix}_000_INDIV"
    if os.path.isdir(indiv_dir):
        if fishZ:
            src_file = os.path.join(indiv_dir, "WB_Z_ROI_001.nii.gz")
            alt_file = os.path.join(indiv_dir, "WB_CORR_ROI_001.nii.gz")
            if os.path.exists(src_file):
                os.rename(src_file, out_path)
                if os.path.exists(alt_file):
                    os.remove(alt_file)
            else:
                _log.warning("Could not create functional connectivity for seed %s.", template_path)
        else:
            src_file = os.path.join(indiv_dir, "WB_CORR_ROI_001.nii.gz")
            if os.path.exists(src_file):
                os.rename(src_file, out_path)
            else:
                _log.warning("Could not create functional connectivity for seed %s.", template_path)

        # Remove the (now empty) INDIV directory
        try:
            os.rmdir(indiv_dir)
        except OSError:
            shutil.rmtree(indiv_dir, ignore_errors=True)

        if os.path.exists(out_path):
            _log.info("Seed-to-voxel functional connectivity maps created for %s with seed from template %s.", prefix, template_path)
        else:
            _log.warning("Could not move functional connectivity file for seed %s. Check permissions and rerun.", template_path)
    else:
        _log.warning("Could not create functional connectivity for seed %s.", template_path)


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
    netcorr_file : str
        Path to the 3dNetCorr .netcc output file.
    fishZ : bool
        Whether Fisher Z-transform was requested.
    pcorr : bool
        Whether partial correlation was requested.
    curr_out_path : str
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

    conn_mat = []
    with open(netcorr_file) as f:
        for line in f:
            if line:
                parts = line.split()
                conn_mat.append([entry.strip() for entry in parts])

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
    with open(curr_out_path, "w") as f:
        for row in out_conn_mat:
            f.write("\t".join(str(x) for x in row) + "\n")


def parcellated_conn(inset_path, out_dir, conn_out_file_pre, template_path, fishZ, pcorr, condition=None, logger=None):

    """
    Run parcellated (ROI-to-ROI) functional connectivity using AFNI's 3dNetCorr.

    Parameters
    ----------
    inset_path : str
        Path to the input time series / beta series NIfTI.
    out_dir : str
        Output directory.
    conn_out_file_pre : str
        Output file prefix.
    template_path : str
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

    # Build output prefix and final path
    if condition is not None:
        prefix = f"{conn_out_file_pre}_{condition}"
    else:
        prefix = conn_out_file_pre

    out_path = os.path.join(out_dir, prefix)
    if fishZ and pcorr:
        out_path += "_pcorr_fishZ_mat.txt"
    elif fishZ:
        out_path += "_fishZ_mat.txt"
    elif pcorr:
        out_path += "_pcorr_mat.txt"
    else:
        out_path += "_corr_mat.txt"

    if os.path.exists(out_path):
        _log.info("Functional connectivity for %s already exists.", prefix)
        return

    # Build and run 3dNetCorr
    netcorr_prefix = os.path.join(out_dir, prefix)
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
        aux = f"{netcorr_prefix}{ext}"
        if os.path.exists(aux):
            os.remove(aux)

    netcc_file = f"{netcorr_prefix}_000.netcc"
    if os.path.exists(netcc_file):
        format_netcorr_mat(netcc_file, fishZ, pcorr, out_path)
        if os.path.exists(out_path):
            os.remove(netcc_file)
            _log.info("Parcellated functional connectivity matrix created for %s with ROIs from template %s.", prefix, template_path)
        else:
            raise ToolExecutionError(f"Could not format functional connectivity for template {template_path}. Likely an internal bug.")
    else:
        raise ToolExecutionError(f"Could not create functional connectivity for template {template_path}.")
