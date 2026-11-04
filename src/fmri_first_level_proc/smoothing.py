"""Voxelwise spatial smoothing: data-derived mask, 3dBlurToFWHM, and ACF FWHM QC.

Smoothing feeds only voxelwise outputs. Parcel-level outputs never consume smoothed
data, and smoothed outputs are siblings of the unsmoothed ones, marked `_s{N}mm`.
"""

import math
import tempfile
from pathlib import Path

from .afni import run_afni_command
from .exceptions import ToolExecutionError
from .fileutils import with_token
from .preprocessing import count_nonzero, nonconstant_mask, psc_scale, run_segments
from .reporting import graded_warning


def smoothing_token(fwhm):
    """File name token for a target FWHM: 6 -> _s6mm, 4.5 -> _s4p5mm."""
    return f"_s{fwhm:g}mm".replace(".", "p")


def smoothing_mask(specs, mask_path, logger):
    """Write the intersection of each run's non-constant voxels. Automask is never used."""
    mask_path = Path(mask_path)
    with tempfile.TemporaryDirectory(dir=mask_path.parent) as tmp:
        masks = [nonconstant_mask(spec, Path(tmp) / f"nonconstant{i}.nii.gz", logger)
                 for i, spec in enumerate(specs)]
        cmd = ["3dMean", "-min", "-datum", "float", "-prefix", mask_path, *masks]
        if len(masks) == 1:
            cmd = ["3dcalc", "-a", masks[0], "-expr", "a", "-prefix", mask_path]
        run_afni_command(cmd, description="non-constant voxel intersection", logger=logger)
    return mask_path


def mask_stats(mask_path, logger):
    """Return (voxels in the mask, fraction of the field of view)."""
    n_voxels = count_nonzero(mask_path, logger)
    total = int(run_afni_command(["3dinfo", "-nijk", mask_path], capture_output=True,
                                 description="3dinfo -nijk mask", logger=logger).strip())
    return n_voxels, n_voxels / total if total > 0 else 0.0


def blur(input_spec, mask_path, fwhm, out_path, logger):
    """Smooth one run to the target FWHM with 3dBlurToFWHM -ACF."""
    run_afni_command(["3dBlurToFWHM", "-FWHM", f"{fwhm:g}", "-ACF", "-mask", mask_path,
                      "-input", input_spec, "-prefix", out_path],
                     description=f"3dBlurToFWHM {Path(out_path).name}", logger=logger)


def acf_fwhm(spec, mask_path, detrend, logger):
    """Estimate the ACF FWHM with 3dFWHMx: the last value of its last 4-value line.

    Returns None when the ACF fit fails, which 3dFWHMx shows beside a fallback estimate as
    NaN parameters or as b and c left at 0.01. 3dBlurToFWHM -ACF can fail the same way and
    then not blur at all; spatially white data does this intermittently.
    """
    cmd = ["3dFWHMx", "-mask", mask_path, *(["-detrend"] if detrend else []),
           "-acf", "NULL", "-input", spec]
    out = run_afni_command(cmd, capture_output=True, description="3dFWHMx ACF FWHM", logger=logger)
    lines = [line.split() for line in out.strip().splitlines()]
    values = [line for line in lines if len(line) == 4]
    if not values:
        raise ToolExecutionError(f"Could not find the ACF estimate in 3dFWHMx output:\n{out}")
    fit = [float(value) for value in values[-1]]
    failed = not all(math.isfinite(value) for value in fit) or fit[1:3] == [0.01, 0.01]
    return None if failed else fit[3]


def qc_record(run, fwhm, fwhm_in, fwhm_out, mask_stat, logger):
    """Build a smoothing_per_run record, warning if the target wasn't met or can't be checked."""
    if fwhm_in is None or fwhm_out is None:
        graded_warning(logger, "medium", "SMOOTH_ACF_FIT_FAILED",
                       f"Run {run}: 3dFWHMx could not fit the ACF, so the achieved FWHM is unknown "
                       "and the run may not have been smoothed.", user_facing=True)
    elif abs(fwhm_out - fwhm) > 0.1 * fwhm:
        graded_warning(logger, "medium", "SMOOTH_FWHM_OFF_TARGET",
                       f"Run {run}: achieved FWHM {fwhm_out:.2f} mm is more than 10% from "
                       f"the {fwhm} mm target.", user_facing=True)
    if fwhm_in is not None and fwhm_in > fwhm:
        graded_warning(logger, "medium", "SMOOTH_INPUT_ABOVE_TARGET",
                       f"Run {run}: input FWHM {fwhm_in:.2f} mm is above the {fwhm} mm target; "
                       "smoothing may have no effect.", user_facing=True)
    return {"run": run, "fwhm_target_mm": float(fwhm), "acf_fwhm_input_mm": fwhm_in,
            "acf_fwhm_output_mm": fwhm_out, "mask_n_voxels": mask_stat[0],
            "mask_fov_fraction": mask_stat[1]}


def smooth_task_scan(scan_path, config, logger):
    """Build the smoothed model input for a task analysis.

    Each run of the unscaled scan is blurred, then PSC-scaled by its own mean when
    config.scale_to_psc is set, then concatenated.

    Returns
    -------
    (pathlib.Path, list of dict)
        The smoothed model input and its smoothing_per_run records.
    """
    out_dir = Path(config.out_dir)
    pre = config.out_file_pre
    fwhm = config.smoothing_fwhm
    token = smoothing_token(fwhm)
    segments = run_segments(scan_path, config.run_lengths)
    mask = smoothing_mask([spec for _, spec in segments], out_dir / f"{pre}_smoothing_mask.nii.gz", logger)
    stat = mask_stats(mask, logger)

    records = []
    run_outputs = []
    intermediates = []
    for run, spec in segments:
        run_pre = f"{pre}_run{run}" if len(segments) > 1 else pre
        blurred = out_dir / f"{run_pre}_blur{token}.nii.gz"
        blur(spec, mask, fwhm, blurred, logger)
        records.append(qc_record(run, fwhm, acf_fwhm(spec, mask, True, logger),
                                 acf_fwhm(blurred, mask, True, logger), stat, logger))
        model_run = blurred
        if config.scale_to_psc:
            model_run = out_dir / f"{run_pre}_psc{token}.nii.gz"
            psc_scale(blurred, out_dir / f"{run_pre}_mean{token}.nii.gz", model_run, logger)
            intermediates.append(blurred)
        run_outputs.append(model_run)

    if len(run_outputs) == 1:
        model_input = run_outputs[0]
    else:
        stem = "psc" if config.scale_to_psc else "blur"
        model_input = out_dir / f"{pre}_{stem}{token}.nii.gz"
        run_afni_command(["3dTcat", "-prefix", model_input, *run_outputs],
                         description="3dTcat smoothed runs", logger=logger)
        intermediates.extend(run_outputs)
    for path in intermediates:
        path.unlink()
    return model_input, records


def smooth_rest_runs(residuals, mask_specs, concat_path, config, logger):
    """Smooth each run's residuals and concatenate them beside the unsmoothed output.

    Parameters
    ----------
    residuals : list of (int, pathlib.Path)
        (run number, residual dtseries) for the runs that entered the concatenation.
    mask_specs : list of str
        The same runs' scans, for the smoothing mask.
    concat_path : pathlib.Path
        The unsmoothed concatenated residual; its name sets the smoothed sibling's.

    Returns
    -------
    list of dict
        smoothing_per_run records.
    """
    fwhm = config.smoothing_fwhm
    token = smoothing_token(fwhm)
    mask = smoothing_mask(mask_specs, Path(config.out_dir) / f"{config.out_file_pre}_smoothing_mask.nii.gz", logger)
    stat = mask_stats(mask, logger)

    records = []
    smoothed = []
    for run, residual in residuals:
        out_path = with_token(residual, token)
        blur(residual, mask, fwhm, out_path, logger)
        records.append(qc_record(run, fwhm, acf_fwhm(residual, mask, False, logger),
                                 acf_fwhm(out_path, mask, False, logger), stat, logger))
        smoothed.append(out_path)
    run_afni_command(["3dTcat", "-TR", str(config.tr), "-prefix", with_token(concat_path, token), *smoothed],
                     description="3dTcat smoothed residuals", logger=logger)
    if not config.keep_run_res_dtseries:
        for path in smoothed:
            path.unlink()
    return records
