"""ROI template validation/resampling and ROI statistic extraction (3dinfo, 3dresample, 3dROIstats)."""

import logging
import os

import pandas as pd

from .afni import get_3dinfo_properties, run_afni_command
from .exceptions import ConfigError, GuardError, InputError, ToolExecutionError


def validate_extract_options(extract_flag_name, average_type, extract_out_file_pre, template_path, scan_path, out_dir, force_diff_atlas, logger=None):

    """Validate extraction-related args for task_conn or rest_conn pipelines.

    Parameters
    ----------
    extract_flag_name : str
        Name of the extract flag for error messages (e.g. '--extract_pbseries').
    average_type : str or None
    extract_out_file_pre : str or None
    template_path : str or None
    scan_path : str
        Path to the scan (used for template validation).
    out_dir : str
    force_diff_atlas : bool
    logger : logging.Logger, optional

    Returns
    -------
    str
        Validated (possibly resampled) template_path.
    """
    _log = logger or logging.getLogger(__name__)

    if average_type is None:
        raise ConfigError(f"--average_type must be provided if {extract_flag_name} is present.")

    if extract_out_file_pre is None:
        raise ConfigError(f"--extract_out_file_pre must be provided if {extract_flag_name} is present.")

    if template_path is None:
        raise ConfigError(f"{extract_flag_name} requires an ROI or ROI set (.nii) be provided to --template_path.")

    return validate_template(scan_path, template_path, out_dir, force_diff_atlas,
                              conn_type="extract", logger=logger)


def validate_connectivity_options(calc_conn, conn_out_file_pre, template_path, scan_path, out_dir, force_diff_atlas, data_label="data", logger=None):

    """Validate connectivity-related args for task_conn or rest_conn pipelines.

    Parameters
    ----------
    calc_conn : str or None
        'seed_to_voxel' or 'parcellated'.
    conn_out_file_pre : str or None
    template_path : str or None
    scan_path : str
        Path to scan (used for template validation).
    out_dir : str
    force_diff_atlas : bool
    data_label : str
        Label for log messages (e.g. 'task beta series', 'residual time series').
    logger : logging.Logger, optional

    Returns
    -------
    str or None
        Validated (possibly resampled) template_path, or None if calc_conn is None.
    """
    _log = logger or logging.getLogger(__name__)

    if calc_conn is None:
        _log.info("Connectivity will not be output after generating %s.", data_label)
        return template_path

    if conn_out_file_pre is None:
        raise ConfigError("--conn_out_file_pre must be provided if --calc_conn is present.")

    if calc_conn == "parcellated":
        if template_path is None:
            raise ConfigError(f"--calc_conn '{calc_conn}' requires an ROI set (.nii) be provided to --template_path.")
        validated = validate_template(scan_path, template_path, out_dir, force_diff_atlas,
                                       conn_type="parcellated", logger=logger)
        _log.info("Calculating parcellated (ROI-based) connectivity matrices after generating %s.", data_label)
    else:
        if template_path is None:
            raise ConfigError(f"--calc_conn '{calc_conn}' requires a seed ROI mask file (binary .nii) be provided to --template_path.")
        validated = validate_template(scan_path, template_path, out_dir, force_diff_atlas,
                                       conn_type="seed_to_voxel", logger=logger)
        _log.info("Calculating seed-to-voxel whole-brain connectivity (.nii) after generating %s.", data_label)

    return validated


def validate_template(scan_path, template_path, out_dir, force_diff_atlas, conn_type=None, logger=None):

    """
    Validate a template NIfTI against a scan, checking atlas space, orientation,
    grid spacing, and ROI content. Resample template if grid mismatch detected.

    Parameters
    ----------
    scan_path : str
        Path to the input scan NIfTI.
    template_path : str
        Path to the template NIfTI.
    out_dir : str
        Output directory (for resampled templates).
    force_diff_atlas : bool
        If True, allow atlas mismatch with a warning.
    conn_type : str or None
        None = skip binary/ROI check (e.g. task_act extraction-only)
        'seed_to_voxel' = require binary mask (max=1)
        'parcellated' = require 2+ ROIs (max>=2)
        'extract' = any non-empty template
    logger : logging.Logger, optional

    Returns
    -------
    str
        Path to the (possibly resampled) template.
    """
    _log = logger or logging.getLogger(__name__)

    # Get template properties
    tpl = get_3dinfo_properties(template_path, logger=logger)
    if any(v is None for v in tpl.values()):
        raise InputError(f"Could not get info from --template_path {template_path} with AFNI's 3dinfo - please check your template.")

    # Validate ROI content via dmax
    try:
        dmax_val = float(tpl["dmax"])
        int_upper = int(dmax_val)
    except ValueError:
        raise GuardError(f"Template provided to --template_path contained non-numeric data max value ('{tpl['dmax']}') - please check your template.")

    if dmax_val != int_upper:
        raise InputError("Template provided to --template_path contained floats, and should only contain ints (ROI set or binary mask) - please check your template.")
    if int_upper == 0:
        raise InputError("Template provided to --template_path contained no data - please check your template.")

    # conn_type-specific checks
    if conn_type == "parcellated" and int_upper < 2:
        raise ConfigError("Template provided to --template_path contained a binary mask. With --calc_conn 'parcellated', template must have at least 2 ROIs.")
    if conn_type == "seed_to_voxel" and int_upper > 1:
        raise ConfigError("Template provided to --template_path contained an ROI set. With --calc_conn 'seed_to_voxel', template must be a binary mask for a single ROI.")

    # Get scan properties
    scn = get_3dinfo_properties(scan_path, logger=logger)
    if any(v is None for v in [scn["space"], scn["orient"], scn["spacing"]]):
        raise InputError(f"Could not get info from --scan_path {scan_path} with AFNI's 3dinfo - please check your scan.")

    _log.info("Specs for scan %s and template %s", scan_path, template_path)
    _log.info("  orient template: %s | orient scan: %s", tpl["orient"], scn["orient"])
    _log.info("  atlas  template: %s | atlas  scan: %s", tpl["space"], scn["space"])
    _log.info("  spacing template: %s | spacing scan: %s", tpl["spacing"], scn["spacing"])

    # Atlas space check
    if tpl["space"] != scn["space"]:
        if force_diff_atlas:
            _log.warning("%s and %s are in different standard template spaces, but proceeding anyway with --force_diff_atlas.", scan_path, template_path)
        else:
            raise InputError(f"Atlas space mismatch between --scan_path {scan_path} and --template_path {template_path} - scan and template must be registered to the same atlas.")

    # Orientation / grid spacing check — resample if mismatch
    if tpl["orient"] != scn["orient"] or tpl["spacing"] != scn["spacing"]:
        _log.warning("Orientation and/or grid spacing for --scan_path %s and --template_path %s do not match.", scan_path, template_path)
        _log.info("Resampling --template_path %s to match --scan_path %s.", template_path, scan_path)

        template_base = os.path.basename(template_path)
        template_file_pre = template_base.replace(".nii.gz", "").replace(".nii", "")
        resampled_path = os.path.join(out_dir, f"{template_file_pre}_resampled.nii.gz")

        # Stale resampled template check: if it exists, verify grid still matches
        needs_resample = True
        if os.path.exists(resampled_path):
            resamp_props = get_3dinfo_properties(resampled_path, logger=logger)
            if resamp_props["orient"] == scn["orient"] and resamp_props["spacing"] == scn["spacing"]:
                _log.info("Resampled template %s already exists and matches scan grid.", resampled_path)
                needs_resample = False
            else:
                _log.warning("Existing resampled template %s has stale grid. Re-resampling.", resampled_path)
                os.remove(resampled_path)

        if needs_resample:
            run_afni_command(
                ["3dresample", "-master", scan_path, "-input", template_path,
                 "-prefix", resampled_path],
                description="resample template to scan grid",
                logger=logger,
            )

            if os.path.exists(resampled_path):
                _log.info("Successfully resampled template; saved to %s", resampled_path)
            else:
                raise ToolExecutionError(f"Could not resample --template_path {template_path}. Please manually resample and try again.")

        return resampled_path
    else:
        return template_path


def extract_roi_stats(nifti_path, template_path, average_type, logger=None):
    """
    Extract ROI-level statistics from a NIfTI file using a template via 3dROIstats.

    Parameters
    ----------
    nifti_path : str
        Path to input NIfTI (can include sub-brik selectors).
    template_path : str
        Path to the ROI template NIfTI.
    average_type : str
        "mean" or "median".
    logger : logging.Logger, optional

    Returns
    -------
    pd.DataFrame
        Columns named ROI_1, ROI_2, ... with the extracted statistics.
    """
    _log = logger or logging.getLogger(__name__)

    extract_cmd = ["3dROIstats", f"-nz{average_type}", "-1Dformat",
                   "-mask", template_path, nifti_path]
    extract_out = run_afni_command(
        extract_cmd,
        capture_output=True,
        description=f"3dROIstats on {nifti_path}",
        logger=logger,
    )

    # Parse the -1Dformat output.
    # Format: line 0 "#File\tSub-brick", line 1 = column headers,
    #         then for each sub-brick: label line (starts with #) + data line.
    #         Data lines are at indices 3, 5, 7, ... (every other line from 3).
    try:
        lines = extract_out.strip().split("\n")
        headers = [h.strip() for h in lines[1].split("\t") if h.strip() and h.strip() != "#"]
        # Collect all data lines (non-comment lines after the header)
        rows = []
        for line in lines[2:]:
            if line.startswith("#"):
                continue
            values = [v.strip() for v in line.split("\t") if v.strip()]
            if not values:
                continue
            if len(headers) != len(values):
                raise ValueError(f"Header count ({len(headers)}) != value count ({len(values)})")
            rows.append([float(v) for v in values])
        if not rows:
            raise ValueError("No data lines found in 3dROIstats output")
        out_df = pd.DataFrame(rows, columns=headers)
    except (IndexError, ValueError) as e:
        raise GuardError(f"Could not parse 3dROIstats output for {nifti_path}: {e}") from e

    # Filter columns based on average type
    ave_type_flag = "NZMed" if average_type == "median" else "NZMean"
    cols_to_keep = [colname for colname in out_df.columns if ave_type_flag in colname]

    if len(cols_to_keep) == 0:
        raise GuardError(f"No columns matching '{ave_type_flag}' found in 3dROIstats output. Available columns: {list(out_df.columns)}")

    new_df = out_df[cols_to_keep].copy()
    new_df.rename(
        columns={oldname: "ROI_" + str(oldname).split("_")[1] for oldname in new_df.columns},
        inplace=True,
    )
    return new_df
