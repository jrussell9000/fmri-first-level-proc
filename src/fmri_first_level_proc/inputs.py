"""Read-only input checks, shared by --dry-run and the start of every run."""

from pathlib import Path

import numpy as np

from .afni import get_3dinfo_properties, run_afni_command
from .design import check_onsets, read_and_validate_stim_data
from .exceptions import InputError

# 3dinfo prints the header TR to six decimals
_TR_TOLERANCE = 1e-3


def _scan_length(scan_path, tr, logger):
    """Return the scan's volume count, after checking its header TR against `tr`."""
    out = run_afni_command(["3dinfo", "-nt", "-tr", scan_path], capture_output=True,
                           description="3dinfo -nt -tr", logger=logger)
    n_vols, header_tr = out.split()[:2]
    if abs(float(header_tr) - tr) > _TR_TOLERANCE:
        raise InputError(f"Scan '{scan_path}' has header TR {header_tr}, but global.tr is {tr}.")
    return int(n_vols)


def _check_table(path, what, n_rows, min_columns):
    """Check that a regressor file has one finite row per volume and enough columns."""
    try:
        data = np.loadtxt(path, ndmin=2)
    except Exception as e:
        raise InputError(f"Cannot read {what} file '{path}': {e}") from e
    if len(data) != n_rows:
        raise InputError(f"{what} file '{path}' has {len(data)} rows, but its scan has {n_rows} volumes.")
    if data.shape[1] < min_columns:
        raise InputError(f"{what} file '{path}' has {data.shape[1]} columns, expected >= {min_columns}.")
    if not np.isfinite(data[:, :min_columns]).all():
        raise InputError(f"{what} file '{path}' has non-finite values.")


def _template_used(config):
    """Whether this block reads the template, by the same rules as its pipeline."""
    if config.analysis_type == "task_act":
        used = config.stat_buckets or config.extract_resids or config.extract_raw_ptseries
    elif config.analysis_type == "task_conn":
        used = config.extract_pbseries or config.extract_raw_ptseries or config.calc_conn
    else:
        used = config.extract_ptseries or config.extract_raw_ptseries or config.calc_conn
    return bool(used)


def _check_template(config, scan_path, logger):
    if config.template_path is None or config.force_diff_atlas or not _template_used(config):
        return
    if not Path(config.template_path).is_file():
        raise InputError(f"template_path does not exist: '{config.template_path}'.")
    template_space = get_3dinfo_properties(config.template_path, logger=logger)["space"]
    scan_space = get_3dinfo_properties(scan_path, logger=logger)["space"]
    if template_space != scan_space:
        raise InputError(f"Atlas space mismatch: scan '{scan_path}' is {scan_space}, "
                         f"template '{config.template_path}' is {template_space}.")


def check_inputs(config, logger, write_timing_errors=False):
    """Validate one analysis block's input files. Writes nothing unless asked.

    Checks each scan's volume count and header TR, the motion and tissue files'
    rows, columns and values, `run_lengths`, the timing file's conditions and
    onsets, and the template's atlas space.

    Parameters
    ----------
    config : ResolvedConfig
    logger : logging.Logger
    write_timing_errors : bool
        Write {pre}_timing_errors.json if an onset is out of range.

    Raises
    ------
    InputError
        The problem found. A run raises the same error before its first step.
    """
    if config.analysis_type == "rest_conn":
        min_columns = 6 * config.motion_deriv_degree
        tissue = [(config.CSF_paths, "CSF"), (config.WM_paths, "WM"), (config.GS_paths, "GS")]
        for i, scan_path in enumerate(config.scan_paths):
            n_vols = _scan_length(scan_path, config.tr, logger)
            _check_table(config.motion_paths[i], "Motion", n_vols, min_columns)
            for paths, what in tissue:
                if paths is not None:
                    _check_table(paths[i], what, n_vols, 1)
        _check_template(config, config.scan_paths[0], logger)
        return

    n_vols = _scan_length(config.scan_path, config.tr, logger)
    if config.run_lengths and sum(config.run_lengths) != n_vols:
        raise InputError(f"Scan '{config.scan_path}' has {n_vols} volumes, but run_lengths "
                         f"{config.run_lengths} sum to {sum(config.run_lengths)}.")
    _check_table(config.motion_path, "Motion", n_vols, 12 if config.include_motion_derivs else 6)
    for path, what in ((config.CSF_path, "CSF"), (config.WM_path, "WM")):
        if path is not None:
            _check_table(path, what, n_vols, 1)

    conditions = config.cond_labels if config.analysis_type == "task_act" else config.cond_beta_labels
    stim_data = read_and_validate_stim_data(config.task_timing_path, conditions, logger=logger)
    errors_path = None
    if write_timing_errors:
        errors_path = Path(config.out_dir) / f"{config.out_file_pre}_timing_errors.json"
    check_onsets(stim_data, n_vols, config.tr, config.analysis_type, errors_path)
    _check_template(config, config.scan_path, logger)
