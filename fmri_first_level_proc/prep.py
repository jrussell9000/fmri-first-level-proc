"""Prep-stage computations: PSC scaling, task concatenation, intersection mask.

Provides:

- ``psc_run``: per-run percent signal change scaling via 3dTstat + 3dcalc.
- ``psc_qc``: per-run PSC QC record with the 25% sentinel.
- ``task_prep``, ``rest_prep``: ledgered prep-stage functions.
- ``task_model_input``, ``task_mask_path``, ``rest_run_input``: pure path helpers.
"""

import copy
import os

from . import names
from .engine import Output, Outcome
from .exceptions import InputError
from .first_level_utils import run_afni_command
from .roi import count_nonzero_by_roi, nonconstant_mask, nonconstant_intersection, extract_roi_stats


# ---------------------------------------------------------------------------
# PSC helpers
# ---------------------------------------------------------------------------

def psc_run(io, input_spec, mean_rel, psc_rel, n_vols, logger):
    """Compute temporal mean and PSC for one run.

    Returns
    -------
    list of Output
    """
    run_afni_command(
        ["3dTstat", "-mean", "-prefix", io.path(mean_rel), input_spec],
        description="3dTstat temporal mean for PSC",
        logger=logger, cwd=io.staging,
    )
    run_afni_command(
        ["3dcalc", "-a", input_spec, "-b", io.path(mean_rel),
         "-expr", "min(200,a/b*100)*step(a)*step(b)",
         "-prefix", io.path(psc_rel)],
        description="3dcalc PSC scaling",
        logger=logger, cwd=io.staging,
    )
    return [
        Output(mean_rel, "intermediate", "nifti", producer="3dTstat mean"),
        Output(psc_rel, "intermediate", "nifti", producer="3dcalc PSC",
               expected_nvols=n_vols),
    ]


def psc_qc(io, run_label, input_spec, mean_path, logger):
    """Compute PSC QC record for one run.

    Raises InputError when >= 25% of non-constant voxels have temporal
    mean <= 0 (sentinel for demeaned input).

    Returns
    -------
    dict
        psc_per_run record.
    """
    # Temporary min/max stats
    mm_rel = f"_pscqc_mm_run{run_label}.nii.gz"
    run_afni_command(
        ["3dTstat", "-min", "-max", "-prefix", io.path(mm_rel), input_spec],
        description="3dTstat min/max for PSC QC",
        logger=logger, cwd=io.staging,
    )

    # Non-constant mask
    mask_rel = f"_pscqc_mask_run{run_label}.nii.gz"
    mask_path = nonconstant_mask(io, input_spec, mask_rel, logger)

    mask_counts = count_nonzero_by_roi(mask_path, mask_path, logger)
    n_mask = mask_counts.get(1, 0)

    if n_mask == 0:
        return {
            "run": run_label,
            "n_mask_voxels": 0,
            "n_guarded_voxels": None,
            "pct_guarded_voxels": None,
            "n_capped_voxels": None,
            "pct_capped_voxels": None,
            "n_nonpositive_mean_voxels": None,
            "pct_nonpositive_mean_voxels": None,
        }

    # Guarded = masked AND (min <= 0 OR mean <= 0)
    guard_rel = f"_pscqc_guard_run{run_label}.nii.gz"
    run_afni_command(
        ["3dcalc", "-a", mask_path, "-b", f"{io.path(mm_rel)}[1]",
         "-c", mean_path, "-expr", "a*or(not(ispositive(b)),not(ispositive(c)))",
         "-prefix", io.path(guard_rel)],
        description="3dcalc guarded voxels",
        logger=logger, cwd=io.staging,
    )
    guard_counts = count_nonzero_by_roi(io.path(guard_rel), io.path(guard_rel), logger)
    n_guarded = guard_counts.get(1, 0)

    # Capped = masked AND mean > 0 AND max > 2*mean
    cap_rel = f"_pscqc_cap_run{run_label}.nii.gz"
    run_afni_command(
        ["3dcalc", "-a", mask_path, "-b", mean_path,
         "-c", f"{io.path(mm_rel)}[0]",
         "-expr", "a*ispositive(b)*step(c-2*b)",
         "-prefix", io.path(cap_rel)],
        description="3dcalc capped voxels",
        logger=logger, cwd=io.staging,
    )
    cap_counts = count_nonzero_by_roi(io.path(cap_rel), io.path(cap_rel), logger)
    n_capped = cap_counts.get(1, 0)

    # Nonpositive mean = masked AND mean <= 0
    np_rel = f"_pscqc_np_run{run_label}.nii.gz"
    run_afni_command(
        ["3dcalc", "-a", mask_path, "-b", mean_path,
         "-expr", "a*not(ispositive(b))",
         "-prefix", io.path(np_rel)],
        description="3dcalc nonpositive mean voxels",
        logger=logger, cwd=io.staging,
    )
    np_counts = count_nonzero_by_roi(io.path(np_rel), io.path(np_rel), logger)
    n_nonpos = np_counts.get(1, 0)

    pct_guarded = round(100.0 * n_guarded / n_mask, 2)
    pct_capped = round(100.0 * n_capped / n_mask, 2)
    pct_nonpos = round(100.0 * n_nonpos / n_mask, 2)

    # Sentinel: >= 25% nonpositive mean
    if pct_nonpos >= 25.0:
        raise InputError(
            f"Run {run_label}: {pct_nonpos}% of non-constant voxels have "
            f"temporal mean <= 0 (demeaned input); percent signal change "
            f"scaling requires positive-baseline input. "
            f"Set scale_to_psc: false for demeaned input."
        )

    return {
        "run": run_label,
        "n_mask_voxels": n_mask,
        "n_guarded_voxels": n_guarded,
        "pct_guarded_voxels": pct_guarded,
        "n_capped_voxels": n_capped,
        "pct_capped_voxels": pct_capped,
        "n_nonpositive_mean_voxels": n_nonpos,
        "pct_nonpositive_mean_voxels": pct_nonpos,
    }


# ---------------------------------------------------------------------------
# Task prep stage
# ---------------------------------------------------------------------------

def task_prep(io, config, runsets, logger):
    """Ledgered prep stage for task analyses.

    Returns
    -------
    Outcome
    """
    pre = config.out_file_pre
    s_pre = runsets.s_pre
    k_sup = runsets.k_supplied
    outputs = []
    qc_records = []

    if config.scale_to_psc:
        for lbl in s_pre:
            ri = runsets.run(lbl)
            mean_r = names.run_mean(pre, None if k_sup == 1 else lbl)
            psc_r = names.run_psc(pre, None if k_sup == 1 else lbl)

            spec = ri.spec

            outs = psc_run(io, spec, mean_r, psc_r, ri.n_vols, logger)
            outputs.extend(outs)

            qc_rec = psc_qc(io, lbl, spec, io.path(mean_r), logger)
            qc_records.append(qc_rec)

        # Concatenate PSC whenever more than one run was supplied, even if
        # only one survives pre-model exclusion: the model-input name depends
        # on K_supplied (task_model_input).
        if k_sup > 1:
            psc_files = [io.path(names.run_psc(pre, lbl)) for lbl in s_pre]
            concat_rel = names.psc_concat(pre)
            run_afni_command(
                ["3dTcat", "-prefix", io.path(concat_rel)] + psc_files,
                description="3dTcat PSC concat",
                logger=logger, cwd=io.staging,
            )
            outputs.append(Output(
                concat_rel, "intermediate", "nifti",
                producer="3dTcat PSC concat",
                expected_nvols=runsets.total_vols(s_pre),
            ))

    # Mode A multi-run: concatenate unscaled (same K_supplied rule as above)
    if runsets.input_mode == "A" and k_sup > 1:
        scan_files = [runsets.run(lbl).source_path for lbl in s_pre]
        concat_rel = names.concat_scan(pre)
        run_afni_command(
            ["3dTcat", "-prefix", io.path(concat_rel)] + scan_files,
            description="3dTcat unscaled concat",
            logger=logger, cwd=io.staging,
        )
        outputs.append(Output(
            concat_rel, "intermediate", "nifti",
            producer="3dTcat unscaled concat",
            expected_nvols=runsets.total_vols(s_pre),
        ))

    # Run-intersection mask (K_model > 1)
    if runsets.k_model > 1:
        specs = []
        for lbl in s_pre:
            ri = runsets.run(lbl)
            if config.scale_to_psc:
                spec = io.path(names.run_psc(pre, None if k_sup == 1 else lbl))
            else:
                spec = ri.spec
            specs.append(spec)

        mask_rel = names.run_intersect_mask(pre)
        nonconstant_intersection(io, specs, mask_rel, "mask", logger)

        outputs.append(Output(
            mask_rel, "intermediate", "nifti",
            producer="3dcalc run-intersection mask",
        ))

    qc_frag = {}
    if config.scale_to_psc:
        qc_frag["psc_per_run"] = qc_records

    return Outcome(outputs=outputs, qc=qc_frag)


# ---------------------------------------------------------------------------
# Rest prep stage
# ---------------------------------------------------------------------------

def rest_prep(io, config, runsets, logger):
    """Ledgered prep stage for rest analyses.

    Returns
    -------
    Outcome
    """
    pre = config.out_file_pre
    s_pre = runsets.s_pre
    outputs = []
    qc_records = []

    if config.scale_to_psc:
        for lbl in s_pre:
            ri = runsets.run(lbl)
            mean_r = names.run_mean(pre, lbl)
            psc_r = names.run_psc(pre, lbl)
            outs = psc_run(io, ri.source_path, mean_r, psc_r, ri.n_vols, logger)
            outputs.extend(outs)
            qc_rec = psc_qc(io, lbl, ri.source_path, io.path(mean_r), logger)
            qc_records.append(qc_rec)

    qc_frag = {}
    if config.scale_to_psc:
        qc_frag["psc_per_run"] = qc_records

    return Outcome(outputs=outputs, qc=qc_frag)


# ---------------------------------------------------------------------------
# Path helpers (pure)
# ---------------------------------------------------------------------------

def task_model_input(config, runsets, out_dir, token=""):
    """Return the path to the model-input series for task analyses."""
    pre = config.out_file_pre
    k_sup = runsets.k_supplied

    if config.scale_to_psc:
        if k_sup == 1:
            return os.path.join(out_dir, names.with_token(names.run_psc(pre, None), token))
        return os.path.join(out_dir, names.with_token(names.psc_concat(pre), token))
    else:
        if token:
            # The smoothing stage writes the same names in every input mode.
            if k_sup == 1:
                return os.path.join(out_dir, names.blurred_run(pre, None, token))
            return os.path.join(out_dir, names.blurred_concat(pre, token, False))
        if runsets.input_mode == "A":
            if k_sup == 1:
                return runsets.run(runsets.s_pre[0]).source_path
            return os.path.join(out_dir, names.with_token(names.concat_scan(pre), token))
        else:
            # Mode B
            if list(runsets.s_pre) == list(runsets.supplied):
                return config.scan_path
            return runsets.mode_b_selector(runsets.s_pre)


def task_mask_path(config, runsets, out_dir):
    """Return the run-intersection mask path, or None for single-run."""
    if runsets.k_model > 1:
        return os.path.join(out_dir, names.run_intersect_mask(config.out_file_pre))
    return None


def task_raw_ptseries(io, config, runsets, template_resolved, logger):
    """Raw (pre-regression) ptseries extraction stage body shared by
    task_act and task_conn: parcellates the unscaled model input, and the
    PSC-scaled input when scale_to_psc is enabled."""
    ext = config.extract_out_file_pre

    cp = copy.copy(config)
    cp.scale_to_psc = False
    unscaled = task_model_input(cp, runsets, config.out_dir)
    df = extract_roi_stats(
        unscaled, template_resolved, config.average_type,
        config.roi_zero_handling, logger, cwd=io.staging,
    )
    csv_text = df.to_csv(index=False)
    rel = names.raw_ptseries(ext, None)
    with open(io.path(rel), "w", newline="") as f:
        f.write(csv_text)
    outputs = [Output(rel, "final", "py_text",
                      producer="raw ptseries", expected_text=csv_text)]

    if config.scale_to_psc:
        psc_spec = task_model_input(config, runsets, config.out_dir)
        df2 = extract_roi_stats(
            psc_spec, template_resolved, config.average_type,
            config.roi_zero_handling, logger, cwd=io.staging,
        )
        csv2 = df2.to_csv(index=False)
        rel2 = names.raw_psc_ptseries(ext, None)
        with open(io.path(rel2), "w", newline="") as f:
            f.write(csv2)
        outputs.append(Output(rel2, "final", "py_text",
                              producer="raw PSC ptseries", expected_text=csv2))
    return Outcome(outputs=outputs)


def rest_run_input(config, runsets, out_dir, label):
    """Return the model-input path for a single rest run."""
    pre = config.out_file_pre
    if config.scale_to_psc:
        return os.path.join(out_dir, names.run_psc(pre, label))
    return runsets.run(label).source_path
