"""Always-run nuisance steps for task and resting-state pipelines.

Provides:

- ``task_nuisance``: censor/exclusion/motion/tissue preparation for task
  analyses. Sets S_pre via runsets.set_s_pre.
- ``rest_nuisance``: per-run notch/censor/motion and DOF dry runs with
  dof_below_1 exclusion for rest analyses. Sets S_pre.

Censoring uses Power et al. (2012) framewise displacement (see ``_censor``);
for rest_conn, FD is computed from the notch-filtered motion series when
notch_filter_band is set. AFNI enorm is recorded for reference only
(0.873 x enorm <= FD <= 2.30 x enorm). Motion input contract: the first six
columns are [tx, ty, tz, rx, ry, rz] in mm and degrees; AFNI 3dvolreg
-1Dfile/-dfile output (roll pitch yaw dS dL dP) must be reordered
translations-first (otherwise FD is biased by roughly -13% to +15%), and
fMRIPrep rotations converted from radians to degrees. Tissue regressors use
the first column of each CSF/WM/GS file for every analysis type.
"""

import math
import os
import re

import numpy as np

from . import names
from .engine import Output, Outcome
from .exceptions import GuardError, InputError, ModelError, ToolExecutionError
from .first_level_utils import (
    graded_warning,
    run_afni_command,
    run_afni_capture,
    load_numeric_table,
    format_table,
    compute_tissue_derivative,
    write_tissue_derivative,
)

CENSOR_HIGH_PCT = 50.0
CENSOR_METRIC = "power_fd"
FD_RADIUS_MM = 50


# ---------------------------------------------------------------------------
# Internal: censor file creation
# ---------------------------------------------------------------------------

def _power_fd(motion6, run_lengths):
    """Compute Power et al. (2012) framewise displacement.

    Parameters
    ----------
    motion6 : np.ndarray
        (N, 6) array: [tx, ty, tz, rx, ry, rz], translations mm, rotations degrees.
    run_lengths : list of int
        Number of TRs per run.

    Returns
    -------
    np.ndarray
        Per-TR FD (length N). First TR of each run is 0.
    """
    fd = np.zeros(motion6.shape[0])
    offset = 0
    rot_weight = math.pi / 180.0 * FD_RADIUS_MM
    for n in run_lengths:
        seg = motion6[offset:offset + n].copy()
        d = np.zeros_like(seg)
        d[1:] = seg[1:] - seg[:-1]
        d[:, 3:6] *= rot_weight
        fd[offset:offset + n] = np.sum(np.abs(d), axis=1)
        offset += n
    return fd


def _enorm(io, run_lengths, src_path, out_rel, logger):
    """Compute AFNI enorm (Euclidean norm of the backward difference, rotations
    unweighted in degrees) via 1d_tool.py and return the series."""
    cmd = [
        "1d_tool.py",
        "-infile", src_path,
        "-set_run_lengths", *[str(n) for n in run_lengths],
        "-derivative",
        "-collapse_cols", "euclidean_norm",
        "-write", io.path(out_rel),
    ]
    run_afni_command(cmd, description="1d_tool.py enorm", logger=logger, cwd=io.staging)
    try:
        return np.loadtxt(io.path(out_rel), ndmin=1).ravel().astype(float)
    except Exception as e:
        raise InputError(f"Cannot read enorm file '{io.path(out_rel)}': {e}") from e


def _summary(x):
    """Return {mean, median, max} summary dict rounded to 4 decimals."""
    return {
        "mean": round(float(np.mean(x)), 4),
        "median": round(float(np.median(x)), 4),
        "max": round(float(np.max(x)), 4),
    }


def _censor(io, motion6, run_lengths, prefix_rel, fd, censor_prev_tr, logger):
    """Create a censor file from Power FD and compute AFNI enorm.

    Censoring uses Power et al. (2012) framewise displacement on a 50 mm
    sphere (rotations degrees x pi/180 x 50, difference 0 at each run's
    first TR). A TR is censored when FD > fd (strict inequality).
    censor_prev_tr also censors the immediately preceding TR within the
    same run. AFNI enorm is computed for reference only.

    Returns
    -------
    (np.ndarray, np.ndarray, np.ndarray)
        (censor_vec int 1=keep/0=censor, fd_series float, enorm_series float)
    """
    src_rel = prefix_rel + "_censor_src.1D"
    src_path = io.path(src_rel)
    text = format_table(motion6, fmt="%.8f")
    with open(src_path, "w", newline="") as f:
        f.write(text)

    # Enorm via AFNI
    enorm_rel = prefix_rel + "_enorm.1D"
    enorm_series = _enorm(io, run_lengths, src_path, enorm_rel, logger)

    # Power FD in Python
    fd_series = _power_fd(motion6, run_lengths)
    fd_text = format_table(fd_series.reshape(-1, 1))
    fd_rel = prefix_rel + "_fd.1D"
    with open(io.path(fd_rel), "w", newline="") as f:
        f.write(fd_text)

    # Censor on FD (strict >)
    flag = fd_series > fd
    keep = ~flag
    if censor_prev_tr:
        offset = 0
        for n in run_lengths:
            for i in range(offset + 1, offset + n):
                if flag[i]:
                    keep[i - 1] = False
            offset += n
    censor_vec = keep.astype(int)

    # Write censor file
    censor_path = io.path(prefix_rel + "_censor.1D")
    with open(censor_path, "w", newline="") as f:
        f.write("\n".join(str(v) for v in censor_vec) + "\n")

    # Remove temporary source
    if os.path.exists(src_path):
        os.remove(src_path)

    return censor_vec, fd_series, enorm_series


# ---------------------------------------------------------------------------
# Task nuisance step
# ---------------------------------------------------------------------------

def task_nuisance(io, config, runsets, logger):
    """Always-run nuisance step for task analyses.

    Sets S_pre via runsets.set_s_pre.

    Parameters
    ----------
    io : StepIO
    config : ResolvedConfig
    runsets : RunSets
    logger : logging.Logger

    Returns
    -------
    (Outcome, dict)
        Outcome with nuisance outputs and QC fragment, and a dict with
        nuisance state for downstream steps.
    """
    pre = config.out_file_pre
    use_cols = 12 if config.include_motion_derivs else 6
    is_task_act = config.analysis_type == "task_act"

    # 1. Motion per supplied run
    per_run_motion = {}
    if runsets.input_mode == "A":
        for lbl in runsets.supplied:
            ri = runsets.run(lbl)
            m = load_numeric_table(config.motion_paths[ri.position], "motion")
            if m.shape[1] < use_cols:
                raise InputError(
                    f"Motion file '{config.motion_paths[ri.position]}' has "
                    f"{m.shape[1]} columns, expected >= {use_cols}."
                )
            per_run_motion[lbl] = m[:, :use_cols]
    else:
        # Mode B: split single file
        m_all = load_numeric_table(config.motion_path, "motion")
        if m_all.shape[1] < use_cols:
            raise InputError(
                f"Motion file '{config.motion_path}' has "
                f"{m_all.shape[1]} columns, expected >= {use_cols}."
            )
        m_all = m_all[:, :use_cols]
        offset = 0
        for lbl in runsets.supplied:
            n = runsets.run(lbl).n_vols
            per_run_motion[lbl] = m_all[offset:offset + n]
            offset += n

    # 2. DERIV_RUN_BOUNDARY check (Mode B + include_motion_derivs)
    if runsets.input_mode == "B" and config.include_motion_derivs:
        boundary_issues = []
        offsets = runsets.offsets(runsets.supplied)
        for lbl in list(runsets.supplied)[1:]:
            s = offsets[lbl]
            for i in range(6):
                d = m_all[s, i] - m_all[s - 1, i]
                if d != 0 and abs(m_all[s, 6 + i] - d) <= 1e-6 * max(1.0, abs(d)):
                    boundary_issues.append((lbl, 7 + i))
        if boundary_issues:
            graded_warning(
                logger, "medium", "DERIV_RUN_BOUNDARY",
                f"Mode B derivative columns appear to cross run boundaries: "
                f"{boundary_issues}. Derivative columns must be computed within run.",
                user_facing=True,
            )

    # 3. Pass 1: censor all supplied runs (temporary, drives exclusion)
    all_motion6 = np.vstack([per_run_motion[lbl][:, :6] for lbl in runsets.supplied])
    all_run_lengths = runsets.run_lengths(runsets.supplied)

    pass1_censor, _, _ = _censor(
        io, all_motion6, all_run_lengths, "_pass1",
        config.fd_threshold, config.censor_prev_tr, logger,
    )

    # Per-run uncensored counts
    p = 1 + math.floor(runsets.d_max_seconds() / 150)
    excluded = []
    offset = 0
    remaining = []
    for lbl in runsets.supplied:
        n = runsets.run(lbl).n_vols
        uncensored = int(np.sum(pass1_censor[offset:offset + n]))
        offset += n
        if uncensored <= p + 1:
            graded_warning(
                logger, "high", "RUN_INSUFFICIENT_TRS",
                f"Run {lbl}: {uncensored} uncensored TRs <= {p + 1}; "
                f"run excluded from the model.",
                user_facing=True,
            )
            excluded.append({"run": lbl, "reason": "insufficient_uncensored_trs"})
        else:
            remaining.append(lbl)

    # Delete pass-1 files
    for entry in os.listdir(io.staging):
        if entry.startswith("_pass1"):
            os.remove(io.path(entry))

    if not remaining:
        raise ModelError(
            f"No run has enough uncensored TRs for the model. "
            f"Runs: {[(e['run'], 'excluded') for e in excluded]}",
            context={"excluded_runs": excluded},
        )

    # 4. Set S_pre
    runsets.set_s_pre(remaining)
    s_pre = runsets.s_pre

    # 5. Pass 2: censor over S_pre only
    outputs = []
    s_pre_motion6 = np.vstack([per_run_motion[lbl][:, :6] for lbl in s_pre])
    s_pre_lengths = runsets.run_lengths(s_pre)

    censor_prefix_rel = names.censor_prefix(pre, None)
    pass2_censor, fd_s_pre, enorm_s_pre = _censor(
        io, s_pre_motion6, s_pre_lengths, censor_prefix_rel,
        config.fd_threshold, config.censor_prev_tr, logger,
    )

    censor_rel = names.censor(pre, None)
    outputs.append(Output(
        censor_rel, "intermediate", "afni_text",
        producer="Power FD censor",
        expected_rows=runsets.total_vols(s_pre),
        expected_cols=1,
    ))
    outputs.append(Output(
        names.censor_enorm(pre, None), "intermediate", "afni_text",
        producer="1d_tool.py enorm",
        expected_rows=runsets.total_vols(s_pre), expected_cols=1,
    ))
    fd_text_s_pre = format_table(fd_s_pre.reshape(-1, 1))
    outputs.append(Output(
        names.censor_fd(pre, None), "intermediate", "py_text",
        producer="Power FD",
        expected_text=fd_text_s_pre,
    ))

    # 6. Motion prepared
    motion_concat = np.vstack([per_run_motion[lbl] for lbl in s_pre])
    motion_rel = names.motion_prepared(pre, None)
    motion_text = format_table(motion_concat)
    with open(io.path(motion_rel), "w", newline="") as f:
        f.write(motion_text)
    outputs.append(Output(
        motion_rel, "intermediate", "py_text",
        producer="motion preparation",
        expected_text=motion_text,
    ))

    # 7. Tissue (CSF, WM)
    tissue_rels = {}
    tissue_deriv_rels = {}
    for tissue_name, path_attr_s, path_attr_p in [
        ("CSF", "CSF_path", "CSF_paths"),
        ("WM", "WM_path", "WM_paths"),
    ]:
        if runsets.input_mode == "A":
            paths = getattr(config, path_attr_p, None)
            if paths is None:
                continue
            segments = []
            for lbl in s_pre:
                ri = runsets.run(lbl)
                t = load_numeric_table(paths[ri.position], tissue_name)
                segments.append(t[:, 0] if t.ndim > 1 else t.ravel())
            tissue_concat = np.concatenate(segments)
        else:
            path = getattr(config, path_attr_s, None)
            if path is None:
                continue
            t_all = load_numeric_table(path, tissue_name)
            t_col = t_all[:, 0] if t_all.ndim > 1 else t_all.ravel()
            # Extract S_pre rows
            segments = []
            for lbl in s_pre:
                ri = runsets.run(lbl)
                segments.append(t_col[ri.start:ri.start + ri.n_vols])
            tissue_concat = np.concatenate(segments)

        t_rel = names.tissue_prepared(pre, tissue_name)
        t_text = format_table(tissue_concat.reshape(-1, 1))
        with open(io.path(t_rel), "w", newline="") as f:
            f.write(t_text)
        outputs.append(Output(
            t_rel, "intermediate", "py_text",
            producer=f"{tissue_name} preparation",
            expected_text=t_text,
        ))
        tissue_rels[tissue_name] = t_rel

        # Tissue derivative (task_act only when use_tissue_derivs)
        if is_task_act and config.use_tissue_derivs:
            deriv = compute_tissue_derivative(tissue_concat, s_pre_lengths)
            d_rel = names.tissue_deriv(pre, tissue_name, None)
            d_text = format_table(deriv.reshape(-1, 1))
            with open(io.path(d_rel), "w", newline="") as f:
                f.write(d_text)
            outputs.append(Output(
                d_rel, "intermediate", "py_text",
                producer=f"{tissue_name} derivative",
                expected_text=d_text,
            ))
            tissue_deriv_rels[tissue_name] = d_rel

    # 8. QC fragment
    total_vols = runsets.total_vols(s_pre)
    n_censored = int(np.sum(pass2_censor == 0))
    pct_censored = round(100.0 * n_censored / total_vols, 2) if total_vols > 0 else 0.0

    logger.info(
        "Censoring: %d/%d TRs (%.2f%%) over %d model runs.",
        n_censored, total_vols, pct_censored, len(s_pre),
    )

    if pct_censored > CENSOR_HIGH_PCT:
        graded_warning(
            logger, "high", "CENSOR_HIGH",
            f"{pct_censored}% of TRs censored (threshold: {CENSOR_HIGH_PCT}%).",
            user_facing=True,
        )

    qc_frag = {
        "n_trs_total": total_vols,
        "n_trs_censored": n_censored,
        "pct_censored": pct_censored,
        "fd_summary": _summary(fd_s_pre),
        "enorm_summary": _summary(enorm_s_pre),
    }

    state = {
        "excluded": excluded,
        "censor_rel": censor_rel,
        "motion_rel": motion_rel,
        "tissue_rel": tissue_rels,
        "tissue_deriv_rel": tissue_deriv_rels,
    }

    return Outcome(outputs=outputs, qc=qc_frag), state


def task_ortvecs(state, out_dir):
    """Return the ordered (path, name) -ortvec pairs for CSF and WM regressors
    and their derivatives from task_nuisance state. Derivatives are written
    by task_nuisance only for task_act, so this helper serves task_act.
    """
    pairs = []
    tissue_rel = state["tissue_rel"]
    deriv = state.get("tissue_deriv_rel", {})
    for t in ("CSF", "WM"):
        if t in tissue_rel:
            pairs.append((f"{out_dir}/{tissue_rel[t]}", f"{t}_regressor"))
        if t in deriv:
            pairs.append((f"{out_dir}/{deriv[t]}", f"{t}_deriv_regressor"))
    return pairs


def _polort(n_vols, tr, bandpass):
    """Return the per-run polynomial baseline order."""
    return 2 if bandpass[0] > 0 else 1 + math.floor(n_vols * tr / 150)


# ---------------------------------------------------------------------------
# Rest nuisance step
# ---------------------------------------------------------------------------

def rest_nuisance(io, config, runsets, logger):
    """Always-run nuisance step for rest analyses.

    Sets S_pre via runsets.set_s_pre.

    Parameters
    ----------
    io : StepIO
    config : ResolvedConfig
    runsets : RunSets
    logger : logging.Logger

    Returns
    -------
    (Outcome, dict)
    """
    pre = config.out_file_pre
    use_cols = 6 * config.motion_deriv_degree
    has_gs = config.GS_paths is not None

    n_tissue = 2 + (1 if has_gs else 0)
    n_deriv_tissue = n_tissue if config.use_tissue_derivs else 0
    n_orts = use_cols + n_tissue + n_deriv_tissue

    outputs = []
    per_run_censoring = []
    per_run_dof = []
    excluded = []
    run_dof = {}
    fd_by_run = {}
    enorm_by_run = {}
    tissue_by_run = {}

    for lbl in runsets.supplied:
        ri = runsets.run(lbl)
        pos = ri.position

        # a. Motion
        m = load_numeric_table(config.motion_paths[pos], "motion")
        if m.shape[1] < use_cols:
            raise InputError(
                f"Motion file '{config.motion_paths[pos]}' has "
                f"{m.shape[1]} columns, expected >= {use_cols}."
            )

        # b. Notch filter
        if config.notch_filter_band is not None:
            base6 = m[:, :6]
            src_rel = f"_notch_src_run{lbl}.1D"
            src_text = format_table(base6)
            with open(io.path(src_rel), "w", newline="") as f:
                f.write(src_text)

            notch_t_rel = f"_notch_t_run{lbl}.1D"
            run_afni_command(
                ["3dTproject", "-polort", "-1", "-dt", str(config.tr),
                 "-input", f"{io.path(src_rel)}'",
                 "-stopband", str(config.notch_filter_band[0]),
                 str(config.notch_filter_band[1]),
                 "-prefix", io.path(notch_t_rel)],
                description=f"3dTproject notch motion run {lbl}",
                logger=logger, cwd=io.staging,
            )
            # Transpose back
            notch_rel = names.notch_motion(pre, lbl)
            run_afni_command(
                ["1dtranspose", io.path(notch_t_rel), io.path(notch_rel)],
                description=f"1dtranspose notch motion run {lbl}",
                logger=logger, cwd=io.staging,
            )
            censor_src_6 = np.loadtxt(io.path(notch_rel), ndmin=2)[:, :6]
        else:
            censor_src_6 = m[:, :6]

        # c. Censor
        censor_prefix_rel = names.censor_prefix(pre, lbl)
        censor_vec, fd_run, enorm_run = _censor(
            io, censor_src_6, [ri.n_vols], censor_prefix_rel,
            config.fd_threshold, config.censor_prev_tr, logger,
        )
        fd_by_run[lbl] = fd_run
        enorm_by_run[lbl] = enorm_run
        n_uncensored = int(np.sum(censor_vec))
        n_censored_run = ri.n_vols - n_uncensored
        pct_censored_run = round(100.0 * n_censored_run / ri.n_vols, 2) if ri.n_vols > 0 else 0.0

        # d. Motion prepared
        motion_rel = names.motion_prepared(pre, lbl)
        motion_text = format_table(m[:, :use_cols])
        with open(io.path(motion_rel), "w", newline="") as f:
            f.write(motion_text)

        # e. DOF dry run
        polort = _polort(ri.n_vols, config.tr, config.bandpass)

        # Surrogate: one row of n_vols values
        surr_rel = f"_dof_surrogate_run{lbl}.1D"
        surr_vals = np.arange(1, ri.n_vols + 1, dtype=float)
        surr_text = " ".join(f"{v:.1f}" for v in surr_vals) + "\n"
        with open(io.path(surr_rel), "w") as f:
            f.write(surr_text)

        censor_path = io.path(names.censor(pre, lbl))
        motion_path = io.path(motion_rel)

        # Prepared single-column tissue copies (first column of each file),
        # used by the dry run and by the residual stages
        tissue_rels = {}
        for tissue_name, src_list in [("CSF", config.CSF_paths), ("WM", config.WM_paths),
                                      ("GS", config.GS_paths if has_gs else None)]:
            if src_list is None:
                continue
            t = load_numeric_table(src_list[pos], tissue_name)
            col = t[:, 0] if t.ndim > 1 else t.ravel()
            t_rel = names.tissue_prepared(pre, tissue_name, lbl)
            t_text = format_table(col.reshape(-1, 1))
            with open(io.path(t_rel), "w", newline="") as f:
                f.write(t_text)
            tissue_rels[tissue_name] = (t_rel, t_text)
        tissue_by_run[lbl] = tissue_rels

        csf_path = io.path(tissue_rels["CSF"][0])
        wm_path = io.path(tissue_rels["WM"][0])
        gs_path = io.path(tissue_rels["GS"][0]) if has_gs else None

        # Tissue derivatives (temporary, in staging)
        deriv_paths = []
        if config.use_tissue_derivs:
            for tissue_path, tissue_name in [(csf_path, "CSF"), (wm_path, "WM"), (gs_path, "GS")]:
                if tissue_name == "GS" and gs_path is None:
                    continue
                d_rel = f"_dof_deriv_{tissue_name}_run{lbl}.1D"
                write_tissue_derivative(tissue_path, tissue_name, [ri.n_vols], io.path(d_rel))
                deriv_paths.append(io.path(d_rel))

        if not config.use_sequenced_bandpass:
            # Simultaneous backend
            dry_cmd = [
                "3dTproject",
                "-input", io.path(surr_rel),
                "-prefix", io.path(f"_dof_dry_run{lbl}.1D"),
                "-polort", str(polort),
                "-censor", censor_path,
                "-cenmode", "ZERO",
                "-ort", motion_path,
                "-ort", csf_path,
                "-ort", wm_path,
            ]
            if gs_path:
                dry_cmd.extend(["-ort", gs_path])
            for dp in deriv_paths:
                dry_cmd.extend(["-ort", dp])
            dry_cmd.extend([
                "-bandpass", str(config.bandpass[0]), str(config.bandpass[1]),
                "-dt", str(config.tr),
            ])
            cp = run_afni_capture(
                dry_cmd, description="3dTproject DOF dry run",
                logger=logger, cwd=io.staging,
            )
            text = (cp.stdout or "") + (cp.stderr or "")
            k_match = re.search(r"(\d+)\s+stopband regressors", text)
            dof_match = re.search(r"==>\s*(-?\d+)\s+D\.O\.F\. left", text)
            # 3dTproject aborts without a DOF line when fixed regressors >=
            # retained time points; its error text still carries both counts.
            over_match = re.search(
                r"total number of fixed regressors \((\d+)\) is too many "
                r"for (\d+) retained time points",
                text,
            )
            # 3dTproject aborts before regression when censoring leaves fewer
            # than its minimum retained frames; no DOF or stopband count is
            # reported, so DOF is reconstructed from the fixed regressors.
            left_match = re.search(
                r"only (\d+) points left after censoring -- cannot continue "
                r"\(need at least (\d+)\)",
                text,
            )
            if left_match:
                n_left = int(left_match.group(1))
                n_min = int(left_match.group(2))
                if n_left != n_uncensored:
                    raise GuardError(
                        f"3dTproject DOF dry run for run {lbl}: reported "
                        f"{n_left} points left after censoring, but the censor "
                        f"vector retains {n_uncensored}."
                    )
                dof = n_uncensored - n_orts - (polort + 1)
                if dof >= 1:
                    raise GuardError(
                        f"3dTproject DOF dry run for run {lbl}: censoring abort "
                        f"(points left {n_left}, minimum {n_min}) produced "
                        f"reconstructed DOF={dof} >= 1."
                    )
                logger.info(
                    "Run %s: 3dTproject dry run aborted (%d points left after "
                    "censoring, minimum %d); reconstructed DOF=%d.",
                    lbl, n_left, n_min, dof,
                )
                n_stopband = None
                n_stopband_null_reason = "dry_run_aborted_censoring"
            elif k_match and dof_match:
                n_stopband = int(k_match.group(1))
                dof = int(dof_match.group(1))
                n_stopband_null_reason = None
            elif k_match and over_match:
                n_stopband = int(k_match.group(1))
                dof = int(over_match.group(2)) - int(over_match.group(1))
                n_stopband_null_reason = None
            else:
                raise ToolExecutionError(
                    f"3dTproject DOF dry run for run {lbl}: could not parse "
                    f"stopband regressors or DOF from output. "
                    f"Return code: {cp.returncode}. "
                    f"stderr: {(cp.stderr or '').strip()}"
                )
            bandpass_dim = None
            bandpass_dim_null_reason = "simultaneous_backend"
            n_stopband_regressors = n_stopband
        else:
            # Sequenced backend
            bp_cmd = [
                "3dBandpass",
                "-dt", str(config.tr),
                "-prefix", io.path(f"_dof_bp_run{lbl}.1D"),
                str(config.bandpass[0]), str(config.bandpass[1]),
                io.path(surr_rel),
            ]
            cp = run_afni_capture(
                bp_cmd, description="3dBandpass DOF probe",
                logger=logger, cwd=io.staging,
            )
            text = (cp.stdout or "") + (cp.stderr or "")
            nfft_match = re.search(r"nFFT=(\d+)", text)
            idx_match = re.search(r"passband indexes=(\d+)\.\.(\d+)", text)
            if not nfft_match or not idx_match:
                raise ToolExecutionError(
                    f"3dBandpass DOF probe for run {lbl}: could not parse "
                    f"nFFT or passband indexes from output. "
                    f"stderr: {(cp.stderr or '').strip()}"
                )
            nfft = int(nfft_match.group(1))
            a = int(idx_match.group(1))
            b = int(idx_match.group(2))
            bp_dim = 0
            for k in range(a, b + 1):
                if k == 0 or (nfft % 2 == 0 and k == nfft // 2):
                    bp_dim += 1
                else:
                    bp_dim += 2
            dof = min(bp_dim, n_uncensored) - n_orts
            bandpass_dim = bp_dim
            bandpass_dim_null_reason = None
            n_stopband_regressors = None
            n_stopband_null_reason = "sequenced_backend"

        run_dof[lbl] = dof

        # f. DOF < 1 -> excluded
        if dof < 1:
            graded_warning(
                logger, "high", "RUN_SKIPPED",
                f"Run {lbl}: DOF={dof} < 1; run excluded.",
                user_facing=True,
            )
            excluded.append({"run": lbl, "reason": "dof_below_1"})

        # g. QC records
        per_run_censoring.append({
            "run": lbl,
            "n_trs_total": ri.n_vols,
            "n_trs_censored": n_censored_run,
            "pct_censored": pct_censored_run,
            "fd_mean": round(float(np.mean(fd_run)), 4),
            "fd_max": round(float(np.max(fd_run)), 4),
            "enorm_mean": round(float(np.mean(enorm_run)), 4),
            "enorm_max": round(float(np.max(enorm_run)), 4),
        })
        per_run_dof.append({
            "run": lbl,
            "dof": dof,
            "bandpass_dim": bandpass_dim,
            "bandpass_dim_null_reason": bandpass_dim_null_reason,
            "n_stopband_regressors": n_stopband_regressors,
            "n_stopband_regressors_null_reason": n_stopband_null_reason,
        })

    # Set S_pre
    s_pre_labels = [lbl for lbl in runsets.supplied if lbl not in {e["run"] for e in excluded}]
    if not s_pre_labels:
        raise ModelError(
            f"Every run has DOF < 1: "
            f"{', '.join(f'run {lbl}: DOF={run_dof[lbl]}' for lbl in runsets.supplied)}",
            context={"excluded_runs": excluded},
        )
    runsets.set_s_pre(s_pre_labels)

    # Outputs: S_pre runs only
    for lbl in s_pre_labels:
        ri = runsets.run(lbl)
        # Notch motion
        if config.notch_filter_band is not None:
            outputs.append(Output(
                names.notch_motion(pre, lbl), "intermediate", "afni_text",
                producer=f"notch motion run {lbl}",
                expected_rows=ri.n_vols, expected_cols=6,
            ))
        # Censor
        outputs.append(Output(
            names.censor(pre, lbl), "intermediate", "afni_text",
            producer="Power FD censor",
            expected_rows=ri.n_vols, expected_cols=1,
        ))
        outputs.append(Output(
            names.censor_enorm(pre, lbl), "intermediate", "afni_text",
            producer=f"1d_tool.py enorm run {lbl}",
            expected_rows=ri.n_vols, expected_cols=1,
        ))
        fd_text_run = format_table(fd_by_run[lbl].reshape(-1, 1))
        outputs.append(Output(
            names.censor_fd(pre, lbl), "intermediate", "py_text",
            producer=f"Power FD run {lbl}",
            expected_text=fd_text_run,
        ))
        # Motion prepared
        motion_rel = names.motion_prepared(pre, lbl)
        motion_text = format_table(
            load_numeric_table(config.motion_paths[ri.position], "motion")[:, :use_cols]
        )
        outputs.append(Output(
            motion_rel, "intermediate", "py_text",
            producer=f"motion preparation run {lbl}",
            expected_text=motion_text,
        ))
        # Prepared tissue (first column)
        for tissue_name, (t_rel, t_text) in tissue_by_run[lbl].items():
            outputs.append(Output(
                t_rel, "intermediate", "py_text",
                producer=f"{tissue_name} preparation run {lbl}",
                expected_text=t_text,
            ))

    # QC fragment (totals over S_pre; per_run_censoring covers every supplied run)
    s_pre_set = set(s_pre_labels)
    total_vols = sum(runsets.run(lbl).n_vols for lbl in s_pre_labels)
    n_censored = sum(
        r["n_trs_censored"] for r in per_run_censoring if r["run"] in s_pre_set
    )
    pct_censored = round(100.0 * n_censored / total_vols, 2) if total_vols > 0 else 0.0

    if pct_censored > CENSOR_HIGH_PCT:
        graded_warning(
            logger, "high", "CENSOR_HIGH",
            f"{pct_censored}% of TRs censored (threshold: {CENSOR_HIGH_PCT}%).",
            user_facing=True,
        )

    qc_frag = {
        "n_trs_total": total_vols,
        "n_trs_censored": n_censored,
        "pct_censored": pct_censored,
        "fd_summary": _summary(np.concatenate([fd_by_run[lbl] for lbl in s_pre_labels])),
        "enorm_summary": _summary(np.concatenate([enorm_by_run[lbl] for lbl in s_pre_labels])),
        "per_run_censoring": per_run_censoring,
        "per_run_dof": per_run_dof,
    }

    state = {
        "excluded": excluded,
        "dof": run_dof,
        "polort": {lbl: _polort(runsets.run(lbl).n_vols, config.tr, config.bandpass)
                   for lbl in runsets.supplied},
        "n_orts": n_orts,
        "tissue_prepared": {
            lbl: {t: rel for t, (rel, _) in tissue_by_run[lbl].items()}
            for lbl in s_pre_labels
        },
    }

    return Outcome(outputs=outputs, qc=qc_frag), state
