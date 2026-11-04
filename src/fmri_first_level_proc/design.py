"""HRF models, stimulus timing I/O, trial survival, contrast parsing, DOF, and 3dDeconvolve base command."""

import itertools
import json
import logging
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from .afni import run_afni_command
from .exceptions import ConfigError, GuardError, InputError, ModelError, ToolExecutionError
from .reporting import graded_warning


# HRF model categories
HRF_DURATION_MODELS = {"GAM", "BLOCK"}       # Use mean_dur in model string
HRF_DM_MODELS = {"dmBLOCK"}                  # Per-trial duration via married timing
HRF_IMPULSE_MODELS = {"SPMG1"}               # No duration parameter
VALID_HRF_MODELS = HRF_DURATION_MODELS | HRF_DM_MODELS | HRF_IMPULSE_MODELS | {"custom"}


# Known AFNI model name prefixes for custom HRF validation (first pass)
AFNI_MODEL_PREFIXES = {
    "GAM", "BLOCK", "dmBLOCK", "dmUBLOCK", "TENT", "TENTzero",
    "CSPLIN", "CSPLINzero", "SPMG1", "SPMG2", "SPMG3",
    "TWOGAMpw", "MION", "MIONN", "WAV", "EXPR", "POLY", "SIN",
}


def validate_custom_hrf(custom_hrf, logger):
    """
    Two-stage validation of a custom HRF string:
    1. Prefix check: verify the string starts with a known AFNI model name
    2. AFNI dry run: use 3dDeconvolve -nodata to validate full syntax

    Returns True if valid, False otherwise (errors logged).
    """
    # Stage 1: prefix whitelist
    prefix_match = any(custom_hrf == name or custom_hrf.startswith(name + "(")
                       for name in AFNI_MODEL_PREFIXES)
    if not prefix_match:
        known = ", ".join(sorted(AFNI_MODEL_PREFIXES))
        logger.error("custom_hrf '%s' does not start with a known AFNI model name. "
                     "Known models: %s", custom_hrf, known)
        return False

    # Stage 2: AFNI -nodata dry run (run inside the temp dir so 3dDeconvolve.err lands there too)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_timing = Path(tmp) / "timing.1D"
        tmp_timing.write_text("10\n")
        cmd = ["3dDeconvolve", "-nodata", "100", "1",
               "-polort", "-1", "-num_stimts", "1",
               "-stim_times", "1", tmp_timing, custom_hrf,
               "-x1D", Path(tmp) / "test.x1D", "-x1D_stop", "-nobucket"]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=tmp)
    if result.returncode != 0:
        logger.error("custom_hrf '%s' failed AFNI validation. "
                     "3dDeconvolve error: %s", custom_hrf,
                     result.stderr.strip())
        return False
    return True


def needs_married_timing(hrf_model, custom_hrf=None):
    """Check if the HRF model requires married timing (onset*duration).

    Handles both named models (e.g. 'dmBLOCK') and custom strings
    (e.g. hrf_model='custom', custom_hrf='dmBLOCK(1)').
    """
    if hrf_model in HRF_DM_MODELS:
        return True
    if hrf_model == "custom" and custom_hrf is not None:
        return any(custom_hrf == name or custom_hrf.startswith(name + "(")
                   for name in HRF_DM_MODELS)
    return False


def validate_onset_file_format(onset_file, expects_married, logger=None):
    """Check if onset file format (married vs single-column) matches expectations.

    Married timing files contain '*' characters (e.g. '10.5*3.0').
    Single-column files contain only onset times.

    Returns True if format matches expectations, False if mismatch.
    """
    _log = logger or logging.getLogger(__name__)
    try:
        with open(onset_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    has_star = '*' in line
                    if has_star != expects_married:
                        fmt_found = "married" if has_star else "single-column"
                        fmt_expected = "married" if expects_married else "single-column"
                        _log.warning(
                            "Onset file '%s' is in %s format but %s format is expected. "
                            "This file may be stale from a previous run with a different HRF model. "
                            "Consider using --remove_previous or deleting this file.",
                            onset_file, fmt_found, fmt_expected)
                        return False
                    return True
    except OSError as e:
        _log.warning("Could not read onset file '%s' for format validation: %s", onset_file, e)
    return True  # If file is empty or unreadable, don't block — downstream will catch errors


def build_hrf_string(hrf_model, mean_dur=None, custom_hrf=None):
    """Construct AFNI stim_times model string for the selected HRF."""
    if hrf_model == "custom":
        if not custom_hrf:
            raise ConfigError("custom_hrf is required when hrf_model='custom'")
        return custom_hrf
    if hrf_model == "GAM":
        return f"GAM(8.6,.547,{mean_dur})"
    if hrf_model == "BLOCK":
        return f"BLOCK({mean_dur},1)"
    if hrf_model == "dmBLOCK":
        return "dmBLOCK(0)"
    if hrf_model == "SPMG1":
        return "SPMG1"
    raise ConfigError(f"Unknown hrf_model: {hrf_model}")


def read_and_validate_stim_data(timing_path, cond_labels, logger=None):
    """Read task timing file (BIDS _events.tsv or legacy CSV), validate columns, sort by onset.

    Detection is content-authoritative: the file extension determines the delimiter
    (.tsv -> tab; .csv/other -> comma), then the header is inspected to classify the
    format. BIDS format is identified by onset/duration/trial_type columns (case-
    insensitive). Legacy CSV format is identified by ONSET/DURATION/CONDITION columns
    (case-insensitive). A deprecation warning is emitted when legacy format is detected.
    The returned DataFrame uses BIDS column names (onset, duration, trial_type) regardless
    of the input format.

    Parameters
    ----------
    timing_path : str
        Path to the timing file. BIDS _events.tsv (preferred) or legacy CSV (deprecated).
    cond_labels : list of str
        Expected condition labels (must all exist in the timing file).
    logger : logging.Logger, optional

    Returns
    -------
    pd.DataFrame
        Sorted by onset, reset index. Columns use BIDS names: onset, duration, trial_type.

    Raises
    ------
    InputError
        If the file header does not match either known format, or if required condition
        labels are absent from the timing file.
    """
    _log = logger or logging.getLogger(__name__)

    # Determine delimiter from extension
    delimiter = '\t' if Path(timing_path).suffix.lower() == '.tsv' else ','

    # Read header to detect format (content-authoritative)
    try:
        header_df = pd.read_csv(timing_path, sep=delimiter, nrows=0)
    except Exception as e:
        raise InputError(f"Cannot read timing file '{timing_path}': {e}") from e
    cols_lower = [c.strip().lower() for c in header_df.columns]

    bids_required = {'onset', 'duration', 'trial_type'}
    legacy_required = {'condition', 'onset', 'duration'}

    if bids_required.issubset(set(cols_lower)):
        # BIDS format
        stim_df = pd.read_csv(timing_path, sep=delimiter)
        stim_df.columns = stim_df.columns.str.strip()
        # Normalize to lower-case BIDS names for any mixed-case BIDS files
        rename_map = {c: c.lower() for c in stim_df.columns if c.lower() in bids_required}
        stim_df = stim_df.rename(columns=rename_map)
    elif legacy_required.issubset(set(cols_lower)):
        # Legacy CSV format — emit deprecation warning
        graded_warning(
            _log, 'low', 'EVENTS_LEGACY',
            'Legacy CSV events format detected. Migrate to BIDS _events.tsv. '
            'CSV support will be removed in version 4.0.0.',
            user_facing=True,
        )
        stim_df = pd.read_csv(timing_path, sep=delimiter)
        stim_df.columns = stim_df.columns.str.strip()
        # Rename legacy columns to BIDS names (case-insensitive match)
        col_map = {c: c.lower() for c in stim_df.columns if c.lower() in legacy_required}
        stim_df = stim_df.rename(columns=col_map)
        # CONDITION -> trial_type
        if 'condition' in stim_df.columns:
            stim_df = stim_df.rename(columns={'condition': 'trial_type'})
    else:
        raise InputError(
            f"Timing file '{timing_path}' header does not match any known format. "
            "Expected BIDS columns (onset, duration, trial_type) or legacy columns "
            "(CONDITION, ONSET, DURATION). Found: " + str(list(header_df.columns))
        )

    # Numeric codes in the file match quoted condition labels in the config
    stim_df['trial_type'] = stim_df['trial_type'].astype(str)
    stim_df['onset'] = pd.to_numeric(stim_df['onset'], errors='coerce')
    stim_df['duration'] = pd.to_numeric(stim_df['duration'], errors='coerce')

    bad_durations = stim_df[~np.isfinite(stim_df['duration']) | (stim_df['duration'] < 0)]
    if not bad_durations.empty:
        raise InputError(f"Timing file '{timing_path}' has {len(bad_durations)} negative or non-finite duration(s), "
                         f"for example {bad_durations['trial_type'].iloc[0]} at onset {bad_durations['onset'].iloc[0]}.")
    duplicates = stim_df[stim_df.duplicated(['trial_type', 'onset'])]
    if not duplicates.empty:
        examples = [(row.trial_type, row.onset) for row in duplicates.head(10).itertuples()]
        raise InputError(f"Timing file '{timing_path}' repeats {len(duplicates)} trial(s) with the same "
                         f"condition and onset: {examples}")

    sorted_df = stim_df.sort_values(by='onset', ascending=True)

    # Check conditions exist in the timing file
    missing = [c for c in cond_labels if c not in sorted_df['trial_type'].unique()]
    if missing:
        raise InputError(
            f"Task condition(s) not found in timing file '{timing_path}': {missing}"
        )

    # Check for conditions with too few trials
    for cond in cond_labels:
        n_trials = len(sorted_df[sorted_df['trial_type'] == cond])
        if n_trials == 0:
            _log.warning("Condition '%s' has 0 trials in the timing file. "
                       "Cannot create onset file for a condition with no events.", cond)
        elif n_trials < 2:
            _log.warning("Condition '%s' has only %d trial(s). At least 2 trials are required "
                       "for a reliable estimate.", cond, n_trials)
        elif n_trials < 3:
            _log.warning("Condition '%s' has only %d trial(s). Estimates may be unreliable.", cond, n_trials)

    return sorted_df.reset_index(drop=True)


def write_onset_file(condition_df, filepath, hrf_model, custom_hrf=None, logger=None):
    """Write AFNI-compatible onset file. Validates format on existing files.

    Parameters
    ----------
    condition_df : pd.DataFrame
        Must contain 'onset' column, and 'duration' if married timing needed.
        Expects BIDS column names (onset, duration, trial_type).
    filepath : str
        Output onset file path.
    hrf_model : str
        HRF model name.
    custom_hrf : str or None
        Custom HRF string (used when hrf_model='custom').
    logger : logging.Logger, optional

    Returns
    -------
    bool
        True if file was created or already exists with correct format.
    """
    _log = logger or logging.getLogger(__name__)
    married = needs_married_timing(hrf_model, custom_hrf)

    filepath = Path(filepath)
    if filepath.exists():
        validate_onset_file_format(filepath, married, logger=logger)
        _log.info("%s already exists.", filepath)
        return True

    if married:
        # iterrows upcasts each row to a common dtype; keep it so output formatting is unchanged
        lines = [f"{row['onset']}*{row['duration']}\n" for _, row in condition_df.iterrows()]
    else:
        lines = [f"{onset}\n" for onset in condition_df['onset']]
    filepath.write_text("".join(lines))
    _log.info("Created %s", filepath)
    return True


def check_onsets(stim_df, n_trs, tr, analysis_type, errors_path=None):
    """Refuse onsets outside the scan, or non-finite ones, for every row of a timing file.

    Parameters
    ----------
    stim_df : pd.DataFrame
        Timing data with trial_type and onset columns, including conditions not modelled.
    n_trs : int
        Volumes in the scan.
    tr : float
        Repetition time in seconds.
    analysis_type : str
        Recorded in the error file.
    errors_path : str or pathlib.Path or None
        Where to write the violations as JSON, if any are found.

    Raises
    ------
    InputError
        If any onset is negative, at or after the end of the scan, or not finite.
    """
    run_end = n_trs * tr
    violations = []
    for row in stim_df.itertuples():
        kind = ("non_finite" if not np.isfinite(row.onset)
                else "negative" if row.onset < 0
                else "at_or_after_run_end" if row.onset >= run_end
                else None)
        if kind:
            violations.append({"condition": str(row.trial_type), "onset_s": float(row.onset), "violation": kind})
    if not violations:
        return
    message = (f"{len(violations)} onset(s) outside the {run_end:g} s scan, for example "
               f"{violations[0]['condition']} at {violations[0]['onset_s']:g} s.")
    if errors_path is not None:
        record = {"analysis_type": analysis_type, "tr": tr, "n_trs": n_trs, "run_end_s": run_end,
                  "violations": violations}
        Path(errors_path).write_text(json.dumps(record, indent=2))
        message += f" See {errors_path}."
    raise InputError(message)


def onset_run(onset, tr, run_lengths=None):
    """1-based run containing an onset given in seconds from the start of the scan."""
    if not run_lengths:
        return 1
    run_ends = np.cumsum(run_lengths) * tr
    return int(np.searchsorted(run_ends, onset, side="right")) + 1


def parse_x1d(path):
    """Read an AFNI x1D design matrix: (rows x columns array, {stim label: column indices}).

    Columns come from ColumnLabels ("label#k"), because AFNI run-length encodes StimBots
    and StimTops (for example "0..4") when conditions have equal trial counts.
    """
    match = re.search(r'#\s*ColumnLabels\s*=\s*"(.*?)"', Path(path).read_text())
    if match is None:
        raise ToolExecutionError(f"x1D file '{path}' has no ColumnLabels header.")
    columns = {}
    for i, label in enumerate(match.group(1).split(";")):
        columns.setdefault(label.strip().split("#")[0], []).append(i)
    return np.loadtxt(path, comments="#", ndmin=2), columns


def lss_dof(matrix_path):
    """Degrees of freedom for each 3dLSS trial's fit, from its censored design matrix.

    Each fit has the matrix's non-beta columns, the trial's own regressor, and one
    regressor summing the other trials, on the matrix's uncensored rows.

    Raises
    ------
    ModelError
        If DOF < 1.
    """
    matrix, columns = parse_x1d(matrix_path)
    n_nuisance = matrix.shape[1] - len(columns["beta_stims"])
    dof = matrix.shape[0] - n_nuisance - 2
    if dof < 1:
        raise ModelError(f"Insufficient degrees of freedom for 3dLSS (DOF={dof}): {matrix.shape[0]} uncensored "
                         f"TRs and {n_nuisance} non-beta regressors. Consider relaxing the FD threshold "
                         "or reducing the model complexity.")
    return dof


def trial_energy_ratios(stim_df, cond_labels, censor_path, config, logger):
    """Share of each trial's squared regressor that falls on uncensored TRs.

    Builds an uncensored -stim_times_IM design without data, so each trial has its own
    columns. A trial's ratio is pooled over its columns for multi-basis HRFs. It is 0
    when censoring removes the trial's whole response.

    Parameters
    ----------
    stim_df : pd.DataFrame
        Timing data with trial_type, onset and duration columns, sorted by onset.
    cond_labels : list of str
        Conditions to measure.
    censor_path : str
        Path to the censor file (binary 1D).
    config : ResolvedConfig
        Must include: tr, hrf_model, custom_hrf, run_lengths, out_dir.
    logger : logging.Logger

    Returns
    -------
    dict
        {condition: [ratio per trial, in onset order]}.

    Raises
    ------
    GuardError
        If the design's columns can't be divided evenly among a condition's trials.
    """
    keep = np.loadtxt(censor_path) == 1
    cmd = ["3dDeconvolve", "-nodata", str(len(keep)), str(config.tr), "-polort", "-1"]
    if config.run_lengths and len(config.run_lengths) > 1:
        run_starts = [0, *itertools.accumulate(config.run_lengths[:-1])]
        cmd.extend(["-concat", "1D: " + " ".join(map(str, run_starts)), "-global_times"])
    cmd.extend(["-num_stimts", str(len(cond_labels))])

    with tempfile.TemporaryDirectory(dir=config.out_dir) as tmp:
        tmp = Path(tmp)
        for k, cond in enumerate(cond_labels, 1):
            cond_df = stim_df[stim_df['trial_type'] == cond]
            onset_path = tmp / f"stim{k}.txt"
            write_onset_file(cond_df, onset_path, config.hrf_model, config.custom_hrf, logger=logger)
            hrf = build_hrf_string(config.hrf_model, mean_dur=np.mean(cond_df['duration']), custom_hrf=config.custom_hrf)
            cmd.extend(["-stim_times_IM", str(k), onset_path, hrf, "-stim_label", str(k), f"stim{k}"])
        matrix_path = tmp / "estimability.x1D"
        cmd.extend(["-x1D", matrix_path, "-x1D_stop", "-nobucket"])
        run_afni_command(cmd, description="3dDeconvolve trial estimability", logger=logger)
        matrix, columns = parse_x1d(matrix_path)

    ratios = {}
    for k, cond in enumerate(cond_labels, 1):
        cols = columns[f"stim{k}"]
        n_trials = int((stim_df['trial_type'] == cond).sum())
        if n_trials == 0 or len(cols) % n_trials != 0:
            raise GuardError(f"Condition '{cond}': the IM design has {len(cols)} column(s) for {n_trials} trial(s).")
        per_trial = len(cols) // n_trials
        energy = [matrix[:, cols[j * per_trial:(j + 1) * per_trial]] ** 2 for j in range(n_trials)]
        ratios[cond] = [float(block[keep].sum() / block.sum()) if block.sum() > 0 else 0.0 for block in energy]
    return ratios


def trial_records(stim_df, ratios, tr, run_lengths=None):
    """One QC record per measured trial, in onset order within each condition."""
    records = []
    for cond, cond_ratios in ratios.items():
        cond_df = stim_df[stim_df['trial_type'] == cond]
        for row, ratio in zip(cond_df.itertuples(), cond_ratios, strict=True):
            records.append({"run": onset_run(row.onset, tr, run_lengths), "condition": str(cond),
                            "onset": float(row.onset), "duration": float(row.duration),
                            "estimability": round(ratio, 6), "survived": ratio > 0})
    return records


def check_trial_survival(ratios, logger):
    """Count each condition's surviving trials, those with a ratio above 0, and warn if few.

    Parameters
    ----------
    ratios : dict
        From trial_energy_ratios.
    logger : logging.Logger

    Returns
    -------
    dict
        {condition: n_surviving_trials} for each condition.
    """
    survival = {}
    for cond, cond_ratios in ratios.items():
        n_total = len(cond_ratios)
        n_surviving = sum(ratio > 0 for ratio in cond_ratios)
        survival[cond] = n_surviving
        if n_surviving < 2:
            logger.warning("Condition '%s': only %d of %d trials survive censoring. "
                         "Cannot reliably estimate this condition (minimum 2 required). Skipping.",
                         cond, n_surviving, n_total)
        elif n_surviving == 2:
            logger.warning("Condition '%s': only 2 of %d trials survive censoring. "
                           "Estimate will have very low power.", cond, n_total)
        elif n_surviving < 5:
            logger.warning("Condition '%s': only %d of %d trials survive censoring. "
                           "Estimates may be unreliable.", cond, n_surviving, n_total)
        else:
            logger.info("Condition '%s': %d of %d trials survive censoring.",
                        cond, n_surviving, n_total)
    return survival


def build_decon_base_command(scan_path, censor_path, motion_path, CSF_path=None, WM_path=None, CSF_deriv_path=None, WM_deriv_path=None, tr=None, run_lengths=None):
    """Build base 3dDeconvolve command with standard nuisance regressors.

    Constructs the invariant portion of the 3dDeconvolve command shared by both
    task_act (full GLM) and task_conn (design matrix only, -x1D_stop). The caller
    is responsible for appending stimulus timing and output flags.

    Parameters
    ----------
    scan_path : str
        Path to the input NIfTI time series.
    censor_path : str
        Path to the binary censor file.
    motion_path : str
        Path to the prepared motion regressor file.
    CSF_path : str or None, optional
        Path to the CSF mean signal file.
    WM_path : str or None, optional
        Path to the WM mean signal file.
    CSF_deriv_path : str or None, optional
        Path to the first temporal derivative of CSF signal.
    WM_deriv_path : str or None, optional
        Path to the first temporal derivative of WM signal.
    tr : float or None, optional
        Repetition time in seconds; adds -TR_times if provided.
    run_lengths : list of int or None, optional
        TRs per concatenated run. With more than one run, adds -concat so each run
        gets its own polynomial baseline, and -global_times because onsets count from
        the start of the concatenated scan.

    Returns
    -------
    list of str
        Partial 3dDeconvolve command: [-quiet, -input, optional -concat, -polort A,
        -censor, motion -ortvec, optional tissue -ortvec flags, optional -TR_times,
        optional -global_times].
    """
    cmd = ["3dDeconvolve", "-quiet",
           "-input", scan_path]
    multi_run = run_lengths is not None and len(run_lengths) > 1
    if multi_run:
        run_starts = [0, *itertools.accumulate(run_lengths[:-1])]
        cmd.extend(["-concat", "1D: " + " ".join(map(str, run_starts))])
    cmd.extend(["-polort", "A",
                "-censor", censor_path,
                "-ortvec", motion_path, "motion_regressors"])
    if multi_run:
        cmd.append("-global_times")
    if tr is not None:
        cmd.extend(["-TR_times", str(tr)])
    if CSF_path is not None:
        cmd.extend(["-ortvec", CSF_path, "CSF_regressor"])
    if WM_path is not None:
        cmd.extend(["-ortvec", WM_path, "WM_regressor"])
    if CSF_deriv_path is not None:
        cmd.extend(["-ortvec", CSF_deriv_path, "CSF_deriv_regressor"])
    if WM_deriv_path is not None:
        cmd.extend(["-ortvec", WM_deriv_path, "WM_deriv_regressor"])
    return cmd


def log_hrf_model(hrf_model, custom_hrf, logger):
    """Log the HRF model being used."""
    logger.info("HRF model: %s", hrf_model if hrf_model != "custom" else f"custom ({custom_hrf})")


def log_nuisance_model(CSF_path, WM_path, logger, use_tissue_derivs=False):
    """Log the nuisance regressors being used."""
    nuisance_parts = ["motion"]
    if CSF_path is not None:
        nuisance_parts.append("CSF")
        if use_tissue_derivs:
            nuisance_parts.append("CSF_deriv")
    if WM_path is not None:
        nuisance_parts.append("WM")
        if use_tissue_derivs:
            nuisance_parts.append("WM_deriv")
    logger.info("Nuisance regressors: %s", ", ".join(nuisance_parts))


def polort_a_regressors(run_lengths, tr):
    """Polynomial regressors 3dDeconvolve adds for -polort A.

    Every run gets degree + 1 regressors, where the degree is
    1 + floor(longest run duration / 150 s).
    """
    degree = 1 + int(max(run_lengths) * tr / 150.0)
    return (degree + 1) * len(run_lengths)


def compute_dof(censor_path, n_regressors, logger, tr=None, run_lengths=None):
    """Compute degrees of freedom from censor file and regressor count.

    Parameters
    ----------
    censor_path : str
        Path to the censor file (binary 1D).
    n_regressors : int
        Total number of regressors in the model.
    logger : logging.Logger
    tr : float or None, optional
        Repetition time in seconds. When provided, the AFNI polort A
        polynomial regressors are added to n_regressors before the DOF check.
        When None (default), no polort adjustment is applied.
    run_lengths : list of int or None, optional
        TRs per concatenated run. The censor file is one run when None.

    Returns
    -------
    int or None
        Degrees of freedom (n_uncensored - adjusted_n_regressors), or None
        if the censor file could not be read. When tr is provided, the
        returned DOF accounts for the polort A adjustment.

    Raises
    ------
    ModelError
        If DOF < 1 (too many TRs censored and/or too many regressors).
    """
    try:
        censor_data = np.loadtxt(censor_path)
        n_uncensored = int(np.sum(censor_data == 1))
        if tr is not None:
            lengths = run_lengths or [len(censor_data)]
            n_regressors = n_regressors + polort_a_regressors(lengths, tr)
    except Exception:
        logger.warning("Could not read censor file for DOF check.")
        return None
    dof = n_uncensored - n_regressors
    logger.info("Estimated DOF: %d (uncensored TRs: %d, regressors: %d)",
                dof, n_uncensored, n_regressors)
    if dof < 1:
        raise ModelError(
            f"Insufficient degrees of freedom (DOF={dof}). "
            "Too many TRs censored and/or too many regressors for AFNI "
            "to produce valid output. Consider relaxing the FD threshold "
            "or reducing the model complexity."
        )
    return dof


def valid_contrast_functions(contrast_list, contrast_labs_list, cond_list, logger=None):
    """Parse and validate linear contrast equations.

    Accepted format: ``coef*COND[+-coef*COND...]``
    Examples: ``1*stimA-1*stimB``, ``-1*A+0.5*B+0.5*C``, ``+1*X-1*Y``

    Returns a list of dicts, one per contrast, each with keys 'COEFS' (list of
    str coefficients with signs) and 'CONDS' (list of condition names).
    """

    # Check that contrast_list and contrast_labs_list are same size
    if len(contrast_list) != len(contrast_labs_list):
        raise ConfigError("Every contrast in --contrast_functions must have a label in --contrast_labels")

    # Regex for a single term: optional sign, a numeric coefficient, *, condition name
    _TERM_RE = re.compile(r'([+-]?\d*\.?\d+)\*(\w+)')
    # Regex that matches the entire valid contrast string (one or more terms)
    _FULL_RE = re.compile(r'^([+-]?\d*\.?\d+\*\w+)([+-]\d*\.?\d+\*\w+)*$')

    _log = logger or logging.getLogger(__name__)
    out = []
    for contrast in contrast_list:
        raw = contrast
        contrast = contrast.replace(" ", "")

        if not contrast:
            raise ConfigError(f"Empty contrast equation (original: '{raw}').")

        # Validate the entire string matches the expected grammar
        if not _FULL_RE.match(contrast):
            # Provide a targeted diagnostic
            if '*' not in contrast:
                raise ConfigError(
                    f"Contrast '{raw}' is missing coefficients. "
                    "Every condition must have an explicit coefficient "
                    "(e.g. '1*stimA-1*stimB', not 'stimA-stimB')."
                )
            elif re.search(r'[*/]{2,}', contrast):
                raise ConfigError(f"Contrast '{raw}' has consecutive operators.")
            elif contrast.endswith(('+', '-', '*')):
                raise ConfigError(f"Contrast '{raw}' has a trailing operator.")
            elif re.search(r'[^+\-\d.*\w]', contrast):
                bad = re.findall(r'[^+\-\d.*\w]', contrast)
                raise ConfigError(f"Contrast '{raw}' contains invalid characters: {bad}")
            else:
                raise ConfigError(
                    f"Contrast '{raw}' could not be parsed. "
                    "Expected format: coef*COND[+-coef*COND...] "
                    "(e.g. '1*stimA-1*stimB')."
                )

        matches = _TERM_RE.findall(contrast)

        coefs = [m[0] for m in matches]
        conds = [m[1] for m in matches]

        # Check all contrast conditions exist in cond_list
        for item in conds:
            if item not in cond_list:
                raise ConfigError(f"Contrast '{raw}' references condition '{item}' which is not in --cond_labels ({cond_list}).")

        # Validate coefficients are valid floats
        for item in coefs:
            try:
                float(item)
            except ValueError:
                raise ConfigError(f"Contrast '{raw}' has invalid coefficient '{item}'.")

        # Warn about zero coefficients (technically valid but likely a mistake)
        for coef, cond in zip(coefs, conds):
            if float(coef) == 0.0:
                _log.warning("Contrast '%s': coefficient for '%s' is 0 — "
                               "this condition will have no effect.", raw, cond)

        out.append({'COEFS': coefs, 'CONDS': conds})
    return out
