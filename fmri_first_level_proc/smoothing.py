"""Spatial smoothing helpers: data-derived mask, 3dBlurToFWHM, ACF QC.

Smoothing feeds only voxelwise outputs; parcel-level stages never consume
smoothed data. Automask is never used (the mask is data-derived from the
non-constant voxel intersection of the run series).
"""

from . import names, prep
from .engine import Output, Outcome
from .exceptions import ToolExecutionError
from .first_level_utils import run_afni_command, graded_warning
from .roi import count_nonzero_by_roi, nonconstant_intersection


# ---------------------------------------------------------------------------
# Smoothing mask
# ---------------------------------------------------------------------------

def smoothing_mask(io, unscaled_specs, rel, logger):
    """Create a data-derived smoothing mask from unscaled run specs.

    The mask is the intersection of non-constant voxels across all runs.

    Parameters
    ----------
    io : StepIO
    unscaled_specs : list of str
        AFNI selectors for each run's unscaled series.
    rel : str
        Output relpath for the mask.
    logger : logging.Logger

    Returns
    -------
    Output
    """
    nonconstant_intersection(io, unscaled_specs, rel, "smooth", logger)
    return Output(rel, "intermediate", "nifti", producer="smoothing mask")


# ---------------------------------------------------------------------------
# Blur
# ---------------------------------------------------------------------------

def blur(io, input_spec, mask_path, fwhm, out_rel, logger):
    """Apply 3dBlurToFWHM -ACF to a single run.

    Returns
    -------
    Output
    """
    run_afni_command(
        ["3dBlurToFWHM", "-FWHM", names.smoothing_canonical(fwhm),
         "-ACF", "-mask", mask_path,
         "-input", input_spec, "-prefix", io.path(out_rel)],
        description=f"3dBlurToFWHM {out_rel}",
        logger=logger, cwd=io.staging,
    )
    return Output(out_rel, "intermediate", "nifti", producer="3dBlurToFWHM")


# ---------------------------------------------------------------------------
# ACF FWHM estimation
# ---------------------------------------------------------------------------

def acf_fwhm(io, spec, mask_path, detrend, logger):
    """Estimate ACF FWHM via 3dFWHMx.

    Parameters
    ----------
    io : StepIO
    spec : str
        AFNI selector for the input.
    mask_path : str
    detrend : bool
        Whether to apply -detrend.
    logger : logging.Logger

    Returns
    -------
    float
        ACF FWHM estimate (4th value on the ACF line).
    """
    cmd = ["3dFWHMx", "-mask", mask_path]
    if detrend:
        cmd.append("-detrend")
    cmd.extend(["-acf", "NULL", "-input", spec])

    result = run_afni_command(
        cmd, capture_output=True,
        description="3dFWHMx ACF FWHM estimate",
        logger=logger, cwd=io.staging,
    )

    # The ACF line has exactly 4 floats; take the last such line
    acf_value = None
    for line in result.strip().splitlines():
        tokens = line.split()
        if len(tokens) == 4:
            try:
                vals = [float(t) for t in tokens]
                acf_value = vals[3]  # 4th float = estimated FWHM
            except ValueError:
                continue

    if acf_value is None:
        raise ToolExecutionError(
            f"3dFWHMx ACF FWHM estimate: could not find a line with "
            f"4 floats in output. Output:\n{result}"
        )

    return acf_value


# ---------------------------------------------------------------------------
# Mask stats
# ---------------------------------------------------------------------------

def mask_stats(mask_path, logger):
    """Return (n_voxels, fov_fraction) for a mask.

    Returns
    -------
    (int, float)
    """
    counts = count_nonzero_by_roi(mask_path, mask_path, logger)
    n = counts.get(1, 0)
    total_str = run_afni_command(
        ["3dinfo", "-nijk", mask_path],
        capture_output=True,
        description="3dinfo -nijk mask",
        logger=logger,
    )
    total = int(total_str.strip())
    fov = n / total if total > 0 else 0.0
    return n, fov


# ---------------------------------------------------------------------------
# QC record
# ---------------------------------------------------------------------------

def qc_record(label, fwhm, fin, fout, n_mask, fov, logger):
    """Build a smoothing_per_run QC record and emit warnings if needed.

    Parameters
    ----------
    label : int
        Run label.
    fwhm : float
        Target FWHM.
    fin : float
        Input ACF FWHM.
    fout : float
        Output ACF FWHM.
    n_mask : int
        Mask voxel count.
    fov : float
        Mask FOV fraction.
    logger : logging.Logger

    Returns
    -------
    dict
    """
    if abs(fout - fwhm) > 0.1 * fwhm:
        graded_warning(
            logger, "medium", "SMOOTH_FWHM_OFF_TARGET",
            f"Run {label}: achieved FWHM {fout:.2f} mm differs from "
            f"target {fwhm} mm by more than 10%.",
            user_facing=True,
        )
    if fin > fwhm:
        graded_warning(
            logger, "medium", "SMOOTH_INPUT_ABOVE_TARGET",
            f"Run {label}: input FWHM {fin:.2f} mm exceeds target {fwhm} mm; "
            f"smoothing may have no effect.",
            user_facing=True,
        )

    return {
        "run": label,
        "fwhm_target_mm": float(fwhm),
        "acf_fwhm_input_mm": fin,
        "acf_fwhm_output_mm": fout,
        "mask_n_voxels": n_mask,
        "mask_fov_fraction": fov,
    }


def task_smooth(io, config, runsets, s_pre, pre, token, logger):
    """Smoothing stage body shared by task_act and task_conn: blur each
    run to the target FWHM, compute ACF QC, scale to PSC, and concatenate
    when more than one run was supplied."""
    outputs = []
    unscaled_specs = [runsets.run(lbl).spec for lbl in s_pre]
    mask_rel = names.smoothing_mask(pre)
    mask_out = smoothing_mask(io, unscaled_specs, mask_rel, logger)
    outputs.append(mask_out)
    n_mask, fov = mask_stats(io.path(mask_rel), logger)

    qc_records = []
    k_sup = runsets.k_supplied
    blurred_specs = []
    for lbl in s_pre:
        ri = runsets.run(lbl)
        out_rel = names.blurred_run(pre, None if k_sup == 1 else lbl, token)
        blur(io, ri.spec, io.path(mask_rel), config.smoothing_fwhm, out_rel, logger)
        outputs.append(Output(out_rel, "intermediate", "nifti",
                              producer="3dBlurToFWHM"))
        blurred_specs.append(io.path(out_rel))

        fin = acf_fwhm(io, ri.spec, io.path(mask_rel), True, logger)
        fout = acf_fwhm(io, io.path(out_rel), io.path(mask_rel), True, logger)
        qc_records.append(qc_record(
            lbl, config.smoothing_fwhm, fin, fout, n_mask, fov, logger,
        ))

        if config.scale_to_psc:
            psc_out_rel = names.blurred_psc_run(pre, None if k_sup == 1 else lbl, token)
            mean_rel = f"_smooth_psc_mean_{lbl}.nii.gz"
            prep.psc_run(io, io.path(out_rel), mean_rel, psc_out_rel, ri.n_vols, logger)
            outputs.append(Output(psc_out_rel, "intermediate", "nifti",
                                  producer="smoothed PSC"))

    if k_sup > 1:
        concat_rel = names.blurred_concat(pre, token, config.scale_to_psc)
        if config.scale_to_psc:
            psc_files = [io.path(names.blurred_psc_run(pre, lbl, token)) for lbl in s_pre]
            run_afni_command(
                ["3dTcat", "-prefix", io.path(concat_rel)] + psc_files,
                description="3dTcat smoothed PSC concat", logger=logger,
                cwd=io.staging,
            )
        else:
            run_afni_command(
                ["3dTcat", "-prefix", io.path(concat_rel)] + blurred_specs,
                description="3dTcat smoothed concat", logger=logger,
                cwd=io.staging,
            )
        outputs.append(Output(concat_rel, "intermediate", "nifti",
                              producer="smoothed concat"))

    return Outcome(outputs=outputs, qc={"smoothing_per_run": qc_records})
