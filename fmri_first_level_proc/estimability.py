"""Estimability dry run, trial survival, condition floor and DOF for task pipelines.

Provides:

- ``parse_x1d``: read an AFNI x1D design matrix and its header metadata.
- ``im_columns``: extract IM column indices for a stim label.
- ``estimability_dry_run``: run a 3dDeconvolve -nodata dry run with -stim_times_IM
  to produce the uncensored design matrix.
- ``trial_estimability``: per-trial estimability fraction (f_j), pooled over
  the trial's basis columns for multi-column HRFs.
- ``check_im_order``: runtime guard that IM columns follow onset-file order.
- ``build_trials``: assemble the trial-level QC record.
- ``beta_selection``: global 3dLSS sub-brick indices of surviving trials.
- ``survival_summary``: aggregate per-condition and per-run trial counts.
- ``apply_floor``: enforce minimum surviving trials and drop conditions/contrasts.
- ``task_act_preflight_dof``: matrix-derived DOF for task_act.
- ``task_conn_lss_dof``: matrix-derived DOF for task_conn.
"""

import re

import numpy as np

from . import names
from .exceptions import GuardError, ModelError, ToolExecutionError
from .first_level_utils import (
    run_afni_command,
    build_decon_nodata_command,
    needs_married_timing,
    hrf_for_durations,
    graded_warning,
)


MIN_SURVIVING_TRIALS = {"task_act": 2, "task_conn": 3}


# ---------------------------------------------------------------------------
# x1D parsing
# ---------------------------------------------------------------------------

def parse_x1d(path):
    """Parse an AFNI x1D design matrix file.

    Parameters
    ----------
    path : str

    Returns
    -------
    (np.ndarray, dict)
        Matrix (rows x columns) and header dict with keys:
        ColumnLabels, StimLabels, StimBots, StimTops.
    """
    header = {}
    with open(path, "r") as f:
        for line in f:
            if not line.startswith("#"):
                break
            # Parse "# Name = \"value\""
            m = re.match(r'#\s*(\w+)\s*=\s*"(.*)"', line)
            if m:
                key = m.group(1)
                val = m.group(2)
                if key == "ColumnLabels":
                    header["ColumnLabels"] = [s.strip() for s in val.split(";")]
                elif key == "StimLabels":
                    header["StimLabels"] = [s.strip() for s in val.split(";")]
                elif key == "StimBots":
                    header["StimBots"] = [int(x) for x in val.replace(",", " ").split()]
                elif key == "StimTops":
                    header["StimTops"] = [int(x) for x in val.replace(",", " ").split()]

    try:
        matrix = np.loadtxt(path, comments="#", ndmin=2)
    except Exception as e:
        raise ToolExecutionError(
            f"Cannot parse x1D matrix from '{path}': {e}"
        ) from e

    return matrix, header


def im_columns(header, stim_label):
    """Return the column indices for an IM stim label.

    Parameters
    ----------
    header : dict
        From ``parse_x1d``.
    stim_label : str
        The stim label to look up.

    Returns
    -------
    list of int
        Column indices (0-based).
    """
    stim_labels = header.get("StimLabels", [])
    bots = header.get("StimBots", [])
    tops = header.get("StimTops", [])

    for i, label in enumerate(stim_labels):
        if label == stim_label:
            if i < len(bots) and i < len(tops):
                return list(range(bots[i], tops[i] + 1))
    raise ToolExecutionError(
        f"Stim label '{stim_label}' not found in x1D header. "
        f"Available: {stim_labels}"
    )


# ---------------------------------------------------------------------------
# Estimability
# ---------------------------------------------------------------------------

def estimability_dry_run(io, config, runsets, onset_specs, logger):
    """Run a 3dDeconvolve -nodata dry run with -stim_times_IM.

    Parameters
    ----------
    io : StepIO
    config : ResolvedConfig
    runsets : RunSets
    onset_specs : list of (str, str, str)
        Each is ``(stim_label, onset_file_abs_path, hrf_string)``.
    logger : logging.Logger

    Returns
    -------
    (np.ndarray, dict)
        Design matrix and header from parse_x1d.
    """
    total_vols = runsets.total_vols(runsets.s_pre)
    run_starts = runsets.run_starts(runsets.s_pre)

    cmd = build_decon_nodata_command(total_vols, config.tr, run_starts, "-1")
    cmd.extend(["-num_stimts", str(len(onset_specs))])

    for k, (label, path, hrf) in enumerate(onset_specs, 1):
        cmd.extend([
            "-stim_times_IM", str(k), path, hrf,
            "-stim_label", str(k), label,
        ])

    dmat_rel = names.estimability_dmat(config.out_file_pre)
    cmd.extend([
        "-x1D_uncensored", io.path(dmat_rel),
        "-x1D_stop", "-nobucket",
    ])

    run_afni_command(
        cmd, description="3dDeconvolve estimability dry run",
        logger=logger, cwd=io.staging,
    )

    return parse_x1d(io.path(dmat_rel))


def _columns_per_trial(cols, n_trials):
    """Return m, the number of IM design-matrix columns per trial."""
    if n_trials <= 0 or len(cols) % n_trials != 0 or len(cols) // n_trials < 1:
        raise GuardError(
            f"IM design matrix has {len(cols)} column(s) for {n_trials} trial(s); "
            "expected a positive whole number of basis columns per trial."
        )
    return len(cols) // n_trials


def trial_estimability(matrix, cols, censor_vec, n_trials):
    """Compute per-trial estimability fractions.

    With ``-stim_times_IM``, 3dDeconvolve creates m basis columns per trial,
    grouped trial by trial (trial j owns columns ``cols[j*m:(j+1)*m]``). The
    estimability of trial j is the pooled energy ratio

        f_j = sum over its m columns and uncensored TRs of x^2
              / sum over its m columns and all TRs of x^2,

    which is identical to the single-column definition when m = 1.

    Parameters
    ----------
    matrix : np.ndarray
        Uncensored design matrix (rows x columns).
    cols : list of int
        IM column indices for one stim label, in design-matrix order.
    censor_vec : np.ndarray
        1-D binary censor vector (1=keep, 0=censor).
    n_trials : int
        Number of trials (onsets) in the stim label's onset file.

    Returns
    -------
    list of (float, str or None)
        One ``(f_j, reason)`` per trial in onset-file order; reason is None
        when f_j > 0, ``'no_in_run_support'`` when the trial's columns are all
        zeros, or ``'fully_censored'`` when every non-zero row is censored.
    """
    if n_trials == 0:
        if cols:
            raise GuardError(
                f"IM design matrix has {len(cols)} column(s) but the onset file "
                "has no trials."
            )
        return []
    m = _columns_per_trial(cols, n_trials)
    keep = np.asarray(censor_vec).ravel() == 1
    results = []
    for j in range(n_trials):
        block = matrix[:, cols[j * m:(j + 1) * m]]
        den = float(np.sum(block ** 2))
        if den == 0:
            results.append((0.0, "no_in_run_support"))
            continue
        f = float(np.sum(block[keep] ** 2)) / den
        results.append((f, None) if f > 0 else (f, "fully_censored"))
    return results


def check_im_order(matrix, cols, column_order, afni_version):
    """Guard that IM columns follow onset-file order within each run.

    For each trial, the first design-matrix row with a non-zero value in its
    column block is compared across trials of the same run: a trial with an
    earlier onset must not start on a later row. Trials whose block is all
    zero are skipped.

    Parameters
    ----------
    matrix : np.ndarray
    cols : list of int
    column_order : list of (str, int, float)
        One ``(condition, run_label, onset)`` per trial, in onset-file order.
    afni_version : str

    Raises
    ------
    GuardError
        If the column order contradicts the onset order.
    """
    if not column_order:
        return
    m = _columns_per_trial(cols, len(column_order))
    by_run = {}
    for j, (cond, rlbl, onset) in enumerate(column_order):
        block = matrix[:, cols[j * m:(j + 1) * m]]
        nz = np.flatnonzero(np.any(block != 0, axis=1))
        if nz.size == 0:
            continue
        by_run.setdefault(rlbl, []).append((onset, int(nz[0]), cond))
    for rlbl, entries in by_run.items():
        # Sorting ties by row makes the adjacent-pair check sufficient: it
        # compares each tie group's latest start with the next group's earliest.
        entries.sort(key=lambda e: (e[0], e[1]))
        for (o_a, r_a, c_a), (o_b, r_b, c_b) in zip(entries, entries[1:]):
            if o_a < o_b and r_a > r_b:
                raise GuardError(
                    "3dDeconvolve -stim_times_IM column order differs from "
                    f"onset-file order under AFNI {afni_version}: run {rlbl}, "
                    f"onset {o_a} ({c_a}) starts at row {r_a} but later onset "
                    f"{o_b} ({c_b}) starts at row {r_b}."
                )


# ---------------------------------------------------------------------------
# Trial records
# ---------------------------------------------------------------------------

def build_trials(event_table, conditions, s_pre, supplied, column_order,
                 fvalues, analysis_type):
    """Build the trial-level QC record.

    Parameters
    ----------
    event_table : EventTable
    conditions : list of str
    s_pre : tuple of int
    supplied : tuple of int
    column_order : list of (str, int, float)
        For each trial in onset-file order: (condition, run_label, onset).
        Aligned with fvalues. For task_conn the position in this list is the
        trial's global 3dLSS sub-brick index.
    fvalues : list of (float or None, str or None)
        Output of trial_estimability.
    analysis_type : str

    Returns
    -------
    list of dict
        One record per trial. For task_conn, beta_series_position is the
        trial's sub-brick index within its condition's beta-series file,
        i.e. its rank among the condition's surviving trials ordered by
        global 3dLSS sub-brick index; lss_index (task_conn only) is the
        trial's position in column_order (its global 3dLSS sub-brick
        index), or None for a run-excluded or unsupported trial.
    """
    trials = []
    s_pre_set = set(s_pre)
    is_conn = analysis_type == "task_conn"

    if len(column_order) != len(fvalues):
        raise GuardError(
            f"Trial list has {len(column_order)} entries but estimability has "
            f"{len(fvalues)} values."
        )
    key_to_index = _key_to_index(column_order)

    # Map (condition, run, onset) -> (f, reason)
    fmap = {key: fvalues[j] for key, j in key_to_index.items()}

    df = event_table.df
    for _, row in df.iterrows():
        lbl = int(row["run"])
        cond = str(row["condition"])
        if cond not in conditions:
            continue
        onset = float(row["onset"])

        if lbl not in s_pre_set:
            record = {
                "run": lbl,
                "condition": cond,
                "onset": onset,
                "estimability": None,
                "survived": False,
                "reason": "run_excluded",
                "beta_series_position": None,
            }
            if is_conn:
                record["lss_index"] = None
            trials.append(record)
            continue

        key = (cond, lbl, onset)
        f, reason = fmap.get(key, (None, "no_in_run_support"))

        survived = f is not None and f > 0 and reason is None

        record = {
            "run": lbl,
            "condition": cond,
            "onset": onset,
            "estimability": f,
            "survived": survived,
            "reason": reason,
            "beta_series_position": None,
        }
        if is_conn:
            record["lss_index"] = key_to_index.get(key)
        trials.append(record)

    if is_conn:
        for cond in conditions:
            surv = [t for t in trials if t["condition"] == cond and t["survived"]]
            surv.sort(key=lambda t: key_to_index[(cond, t["run"], t["onset"])])
            for rank, t in enumerate(surv):
                t["beta_series_position"] = rank

    return trials


def _key_to_index(column_order):
    """Map (condition, run, onset) to its position, rejecting duplicates."""
    key_to_index = {}
    for j, key in enumerate(column_order):
        if key in key_to_index:
            raise GuardError(
                f"Duplicate trial {key} (condition, run, onset) in the onset "
                "file; trials must be unique within a condition and run."
            )
        key_to_index[key] = j
    return key_to_index


def beta_selection(trials, column_order):
    """Return the global 3dLSS sub-brick indices of each condition's surviving trials.

    Parameters
    ----------
    trials : list of dict
        Output of build_trials (task_conn).
    column_order : list of (str, int, float)
        The same trial list passed to build_trials.

    Returns
    -------
    dict of str -> list of int
        Sorted global indices per condition; the k-th entry is the sub-brick
        whose beta_series_position is k.
    """
    key_to_index = _key_to_index(column_order)
    selection = {}
    for t in trials:
        if not t["survived"]:
            continue
        key = (t["condition"], t["run"], t["onset"])
        selection.setdefault(t["condition"], []).append(key_to_index[key])
    return {cond: sorted(idx) for cond, idx in selection.items()}


def survival_summary(trials, conditions):
    """Aggregate trial counts and run counts from the trial list.

    Returns
    -------
    (dict, dict, list)
        (trial_counts, surviving, run_counts)
    """
    trial_counts = {}
    surviving = {}
    for cond in conditions:
        cond_trials = [t for t in trials if t["condition"] == cond]
        trial_counts[cond] = len(cond_trials)
        surviving[cond] = sum(1 for t in cond_trials if t["survived"])

    # Per-run per-condition counts
    run_conds = {}
    for t in trials:
        key = (t["run"], t["condition"])
        if key not in run_conds:
            run_conds[key] = {"n_trials": 0, "n_surviving": 0}
        run_conds[key]["n_trials"] += 1
        if t["survived"]:
            run_conds[key]["n_surviving"] += 1

    run_counts = []
    for (rlbl, cond), counts in sorted(run_conds.items()):
        run_counts.append({
            "run": rlbl,
            "condition": cond,
            "n_trials": counts["n_trials"],
            "n_surviving": counts["n_surviving"],
        })

    return trial_counts, surviving, run_counts


# ---------------------------------------------------------------------------
# Floor enforcement
# ---------------------------------------------------------------------------

def apply_floor(analysis_type, conditions, surviving, contrasts,
                contrast_labels, logger):
    """Enforce minimum surviving trials; drop conditions and contrasts.

    Parameters
    ----------
    analysis_type : str
    conditions : list of str
    surviving : dict
        condition -> surviving count.
    contrasts : list of dict or None
        Parsed contrast dicts (from valid_contrast_functions).
    contrast_labels : list of str or None
    logger : logging.Logger

    Returns
    -------
    (kept_conditions, kept_contrasts, kept_labels, dropped)
    """
    floor = MIN_SURVIVING_TRIALS.get(analysis_type, 2)
    dropped = []
    kept = []

    for cond in conditions:
        n = surviving.get(cond, 0)
        if n < floor:
            graded_warning(
                logger, "medium", "COND_DROPPED",
                f"Condition '{cond}' has {n} surviving trial(s) "
                f"(floor: {floor}); condition dropped.",
                user_facing=True,
            )
            dropped.append(cond)
        else:
            kept.append(cond)

    if not kept:
        raise ModelError(
            f"No task condition has at least {floor} estimable trials."
        )

    # Drop contrasts referencing dropped conditions
    kept_contrasts = []
    kept_labels = []
    dropped_set = set(dropped)
    if contrasts and contrast_labels:
        for c, label in zip(contrasts, contrast_labels):
            refs_dropped = any(cond in dropped_set for cond in c["CONDS"])
            if refs_dropped:
                graded_warning(
                    logger, "medium", "CONTRAST_DROPPED",
                    f"Contrast '{label}' references a dropped condition; "
                    f"contrast dropped.",
                    user_facing=True,
                )
            else:
                kept_contrasts.append(c)
                kept_labels.append(label)

    return kept, kept_contrasts or None, kept_labels or None, dropped


# ---------------------------------------------------------------------------
# DOF computation
# ---------------------------------------------------------------------------

def task_act_preflight_dof(io, config, runsets, onset_files, censor,
                           motion, ortvecs, event_table, logger):
    """Compute matrix-derived DOF for task_act via a 3dDeconvolve dry run.

    Parameters
    ----------
    io : StepIO
    config : ResolvedConfig
    runsets : RunSets
    onset_files : list of (str, str)
        ``(condition, absolute_path)`` for each surviving condition.
    censor : str
        Absolute path to the censor file.
    motion : str
        Absolute path to the prepared motion file.
    ortvecs : list of (str, str)
        Additional ortvec ``(path, name)`` pairs.
    event_table : EventTable
    logger : logging.Logger

    Returns
    -------
    int
        Degrees of freedom.

    Raises
    ------
    ModelError
        If DOF < 1.
    """
    total_vols = runsets.total_vols(runsets.s_pre)
    run_starts = runsets.run_starts(runsets.s_pre)
    married = needs_married_timing(config.hrf_model, config.custom_hrf)
    stim_flag = "-stim_times_AM1" if married else "-stim_times"
    run_df = event_table.for_runs(runsets.s_pre).df

    cmd = build_decon_nodata_command(total_vols, config.tr, run_starts, "A")
    cmd.extend(["-censor", censor, "-ortvec", motion, "motion_regressors"])
    for path, name in ortvecs:
        cmd.extend(["-ortvec", path, name])
    cmd.extend(["-num_stimts", str(len(onset_files))])

    for k, (cond, path) in enumerate(onset_files, 1):
        hrf = hrf_for_durations(
            config.hrf_model, config.custom_hrf,
            run_df.loc[run_df["condition"] == cond, "duration"],
        )
        cmd.extend([stim_flag, str(k), path, hrf, "-stim_label", str(k), cond])

    dmat_rel = names.preflight_dmat(config.out_file_pre)
    cmd.extend(["-x1D", io.path(dmat_rel), "-x1D_stop", "-nobucket"])

    run_afni_command(
        cmd, description="3dDeconvolve preflight DOF",
        logger=logger, cwd=io.staging,
    )

    matrix, _ = parse_x1d(io.path(dmat_rel))
    dof = matrix.shape[0] - matrix.shape[1]

    if dof < 1:
        raise ModelError(
            f"Insufficient degrees of freedom (DOF={dof}). "
            f"Matrix: {matrix.shape[0]} rows, {matrix.shape[1]} columns."
        )

    return dof


def task_conn_lss_dof(dmat_path):
    """Compute DOF for task_conn LSS from the design matrix.

    Parameters
    ----------
    dmat_path : str
        Path to the bseries design matrix x1D.

    Returns
    -------
    int
        Degrees of freedom.

    Raises
    ------
    ModelError
        If DOF < 1.
    """
    matrix, header = parse_x1d(dmat_path)
    im_cols = im_columns(header, "beta_stims")
    n_non_im = matrix.shape[1] - len(im_cols)
    dof = matrix.shape[0] - (n_non_im + 2)

    if dof < 1:
        raise ModelError(
            f"Insufficient degrees of freedom for LSS (DOF={dof}). "
            f"Matrix: {matrix.shape[0]} rows, {matrix.shape[1]} columns, "
            f"{len(im_cols)} IM columns."
        )

    return dof
