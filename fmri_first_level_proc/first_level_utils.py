#!/usr/bin/env python3

# ============================================================================
# SHARED UTILITIES FOR fMRI FIRST-LEVEL PROCESSING
# Common functions used across task_act, task_conn, and rest_conn pipelines.
#
# Author: Taylor J. Keding, Ph.D.
# ============================================================================
"""
Shared utility functions for the fmri_first_level_proc package.

This module provides functions used by all three analysis pipelines
(task_act_first_level, task_conn_first_level, rest_conn_first_level):

- Logging setup
- Graded warning system with closed warning-code table
- FirstLevelResult dataclass
- HRF model string construction, validation, and logging
- AFNI command execution wrappers (run_afni_command, run_afni_capture)
- 3dinfo property queries
- Linear contrast parsing and validation
- Filename sanitization
- Numeric table I/O helpers (load_numeric_table, format_table)
- Within-run tissue derivative computation
- Censor-interpolation and bandpass filtering of 1D files
- 3dDeconvolve base command construction
- REML_cmd collection
- Min-outlier EPI extraction
"""

import dataclasses
import logging
import os
import re
import subprocess
import sys
import tempfile

import numpy as np
from pathlib import Path
from .exceptions import (
    ConfigError, GuardError, InputError, ToolExecutionError,
)


# ---------------------------------------------------------------------------
# Closed warning-code table
# ---------------------------------------------------------------------------

WARNING_CODES = {
    "CENSOR_HIGH": "high",
    "COND_DROPPED": "medium",
    "CONTRAST_DROPPED": "medium",
    "GS_MISSING": "low",
    "RUN_SKIPPED": "high",
    "DISCOVERY_COLLISION": "medium",
    "UNVALIDATED_VERSION": "medium",
    "LEDGER_ENTRY_UNREADABLE": "medium",
    "RETIREMENT_FAILED": "high",
    "NULL_ROI": "high",
    "SEED_NULL": "high",
    "PCORR_RANK_DEFICIENT": "high",
    "RUN_FAILED": "high",
    "RUN_INSUFFICIENT_TRS": "high",
    "DERIV_RUN_BOUNDARY": "medium",
    "SMOOTH_FWHM_OFF_TARGET": "medium",
    "SMOOTH_INPUT_ABOVE_TARGET": "medium",
}

# Module-level warning accumulator (cross-pipeline contract)
_WARNING_ACCUMULATOR: list[dict] = []


def get_warnings() -> list[dict]:
    """Return a shallow copy of the module-level warning accumulator."""
    return list(_WARNING_ACCUMULATOR)


def clear_warnings() -> None:
    """Clear all accumulated warnings. Call at pipeline entry before dispatching."""
    _WARNING_ACCUMULATOR.clear()


def warning_count() -> int:
    """Return the current number of accumulated warnings."""
    return len(_WARNING_ACCUMULATOR)


@dataclasses.dataclass
class FirstLevelResult:
    """Structured result returned by each pipeline's run() function.

    Attributes
    ----------
    status : str
        ``'success'`` when no high-severity warnings were emitted, or
        ``'warning'`` when at least one high-severity warning was emitted
        (CLI exit code 3).
    output_dir : Path
        Directory where output files were written.
    warnings : list[dict]
        Accumulated graded_warning records from the pipeline run.
    qc_summary : dict
        Quality-control metrics (written to the QC summary JSON).
    output_files : list[str]
        Absolute paths to all final products of the analysis.
    intermediate_files : list[str]
        Absolute paths to every other file the analysis leaves on disk.
        Disjoint from output_files. Excludes staging directories and the
        CLI log file.
    """

    status: str
    output_dir: Path
    warnings: list[dict]
    qc_summary: dict
    output_files: list[str]
    intermediate_files: list[str]


# ---------------------------------------------------------------------------
# General Helpers
# ---------------------------------------------------------------------------

def setup_logging(name: str, log_file: str | None = None) -> logging.Logger:
    """
    Configure and return a logger with console output (and optional file output).

    Parameters
    ----------
    name : str
        Name used in log format, e.g. "task_act_first_level".
    log_file : str, optional
        Path to a log file. If provided, logs are also written to this file.

    Returns
    -------
    logging.Logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Prevent duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Console handler (stderr to keep stdout clean for piped output)
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Optional file handler
    if log_file is not None:
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


# ---------------------------------------------------------------------------
# Graded Warnings
# ---------------------------------------------------------------------------

def graded_warning(
    logger: logging.Logger,
    severity: str,
    code: str,
    message: str,
    *,
    user_facing: bool = False,
) -> dict:
    """Emit a graded warning and return a structured record for accumulation.

    High-severity warnings set FirstLevelResult.status to ``'warning'`` and
    CLI exit code 3.

    Parameters
    ----------
    logger : logging.Logger
        Logger instance to use for emission.
    severity : str
        One of 'low', 'medium', or 'high'.
    code : str
        Machine-readable warning code from WARNING_CODES.
    message : str
        Human-readable warning description.
    user_facing : bool, optional
        If True, log at WARNING level (visible on console). If False, log at
        INFO level (written to file only when --log-file is provided).

    Returns
    -------
    dict
        {'severity': severity, 'code': code, 'message': message,
         'user_facing': user_facing}

    Raises
    ------
    GuardError
        If *code* is not in WARNING_CODES or *severity* does not match the
        table entry.
    """
    if code not in WARNING_CODES:
        raise GuardError(
            f"Unknown warning code '{code}'. Valid codes: {sorted(WARNING_CODES)}"
        )
    if severity != WARNING_CODES[code]:
        raise GuardError(
            f"Warning code '{code}' has severity '{WARNING_CODES[code]}', "
            f"not '{severity}'."
        )
    level = logging.WARNING if user_facing else logging.INFO
    logger.log(level, "[%s] %s", code, message)
    record = {
        "severity": severity,
        "code": code,
        "message": message,
        "user_facing": user_facing,
    }
    _WARNING_ACCUMULATOR.append(record)
    return record


def reemit_warning(record: dict, logger: logging.Logger, prefix: str) -> None:
    """Re-emit a warning record (e.g. from a reused stage) into the accumulator.

    Parameters
    ----------
    record : dict
        A warning record dict with keys severity, code, message, user_facing.
    logger : logging.Logger
    prefix : str
        Prefix prepended to the log message (e.g. ``'[reused stage X]'``).
    """
    if record["code"] not in WARNING_CODES:
        raise GuardError(
            f"Reemitted warning code '{record['code']}' is not in WARNING_CODES."
        )
    level = logging.WARNING if record.get("user_facing") else logging.INFO
    logger.log(level, "%s [%s] %s", prefix, record["code"], record["message"])
    _WARNING_ACCUMULATOR.append(dict(record))


# ---------------------------------------------------------------------------
# HRF Model Constants
# ---------------------------------------------------------------------------

HRF_DURATION_MODELS = {"GAM", "BLOCK"}       # Use mean_dur in model string
HRF_DM_MODELS = {"dmBLOCK"}                  # Per-trial duration via married timing
HRF_IMPULSE_MODELS = {"SPMG1"}               # No duration parameter
VALID_HRF_MODELS = HRF_DURATION_MODELS | HRF_DM_MODELS | HRF_IMPULSE_MODELS | {"custom"}

# Mapping from HRF model name to AFNI model prefix (for prefix whitelist validation)
AFNI_MODEL_PREFIXES = {
    "GAM": "GAM",
    "BLOCK": "BLOCK",
    "dmBLOCK": "dmBLOCK",
    "SPMG1": "SPMG",
    "TWOGAMpw": "TWOGAMpw",
    "TENT": "TENT",
    "TENTzero": "TENTzero",
    "CSPLIN": "CSPLIN",
    "CSPLINzero": "CSPLINzero",
}


def validate_custom_hrf(custom_hrf, logger) -> int:
    """Validate a custom HRF string against AFNI and return the column count.

    Stage 1: check that the string starts with a recognized AFNI model prefix.
    Stage 2: run a minimal 3dDeconvolve dry run and return the number of columns
    produced by the model.

    Parameters
    ----------
    custom_hrf : str
        Custom HRF string (e.g. ``'TENT(0,14,8)'``).
    logger : logging.Logger

    Returns
    -------
    int
        Number of columns the model generates in the design matrix.

    Raises
    ------
    ConfigError
        If the prefix is not recognized or the AFNI dry run fails.
    """
    # Stage 1: prefix whitelist
    matched = False
    for prefix in AFNI_MODEL_PREFIXES.values():
        if custom_hrf == prefix or custom_hrf.startswith(prefix + "("):
            matched = True
            break
    if not matched:
        raise ConfigError(
            f"Custom HRF '{custom_hrf}' does not start with a recognized AFNI model prefix. "
            f"Known prefixes: {sorted(AFNI_MODEL_PREFIXES.values())}"
        )

    # Stage 2: AFNI dry-run validation
    with tempfile.TemporaryDirectory() as tmp:
        timing_path = os.path.join(tmp, "timing.1D")
        with open(timing_path, "w") as f:
            f.write("10\n")
        x1d_path = os.path.join(tmp, "hrf_test.x1D")
        try:
            run_afni_command(
                ["3dDeconvolve", "-nodata", "100", "1",
                 "-polort", "-1",
                 "-num_stimts", "1",
                 "-stim_times", "1", "timing.1D", custom_hrf,
                 "-x1D", "hrf_test.x1D",
                 "-x1D_stop", "-nobucket"],
                description="custom_hrf validation",
                logger=logger,
                cwd=tmp,
            )
        except ToolExecutionError as e:
            raise ConfigError(
                f"custom_hrf '{custom_hrf}' failed AFNI validation: {e}"
            ) from e

        matrix = np.loadtxt(x1d_path, comments="#", ndmin=2)
        return matrix.shape[1]


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

def hrf_for_durations(hrf_model, custom_hrf, durations):
    """Return the AFNI stim_times model string; duration models use the mean
    of *durations* (1.0 when empty)."""
    if hrf_model in HRF_DURATION_MODELS:
        mean_dur = float(durations.mean()) if len(durations) else 1.0
        return build_hrf_string(hrf_model, mean_dur=mean_dur)
    return build_hrf_string(hrf_model, custom_hrf=custom_hrf)

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


# ---------------------------------------------------------------------------
# Numeric I/O helpers
# ---------------------------------------------------------------------------

def load_numeric_table(path, what: str) -> np.ndarray:
    """Load a numeric text file as a 2-D ndarray.

    Parameters
    ----------
    path : str
        Path to the text file.
    what : str
        Description for error messages (e.g. ``'motion'``).

    Returns
    -------
    np.ndarray
        2-D array (rows x columns).

    Raises
    ------
    InputError
        If the file cannot be read or parsed.
    """
    try:
        data = np.loadtxt(path, ndmin=2)
    except Exception as e:
        raise InputError(f"Cannot read {what} file '{path}': {e}") from e
    return data


def format_table(array: np.ndarray, fmt="%.8f") -> str:
    """Format a 2-D array as tab-delimited text with a trailing newline.

    This is the canonical format for Python-written 1D text files in the
    package. The engine uses byte-exact comparison against this text.

    Parameters
    ----------
    array : np.ndarray
        2-D array (will be reshaped to 2-D if 1-D).
    fmt : str
        printf-style format for each value.

    Returns
    -------
    str
        Tab-delimited text with a trailing newline.
    """
    if array.ndim == 1:
        array = array.reshape(-1, 1)
    lines = []
    for row in array:
        lines.append("\t".join(fmt % v for v in row))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Within-run tissue derivative
# ---------------------------------------------------------------------------

def compute_tissue_derivative(values: np.ndarray, run_lengths: list[int]) -> np.ndarray:
    """Compute per-run first temporal derivative of a tissue signal.

    For each run segment the first difference is computed with the first
    element set to 0 (np.diff with prepend of the segment's first value),
    and the segments are concatenated.

    Parameters
    ----------
    values : np.ndarray
        1-D array of tissue signal values (all runs concatenated).
    run_lengths : list[int]
        Number of TRs in each run.

    Returns
    -------
    np.ndarray
        1-D array of derivatives, same length as *values*.

    Raises
    ------
    InputError
        If *values* is not 1-D or run lengths do not sum to its length.
    """
    if values.ndim != 1:
        raise InputError(
            f"Tissue signal must be 1-D, got shape {values.shape}."
        )
    if sum(run_lengths) != len(values):
        raise InputError(
            f"Run lengths sum to {sum(run_lengths)} but tissue signal "
            f"has {len(values)} values."
        )
    segments = []
    offset = 0
    for n in run_lengths:
        seg = values[offset : offset + n]
        deriv = np.diff(seg, prepend=seg[0])
        segments.append(deriv)
        offset += n
    return np.concatenate(segments)


def write_tissue_derivative(src_path, name, run_lengths, out_path):
    """Write the per-run first derivative of the first column of a tissue
    file and return the written text."""
    t = load_numeric_table(src_path, name)
    col = t[:, 0] if t.ndim > 1 else t.ravel()
    text = format_table(compute_tissue_derivative(col, run_lengths).reshape(-1, 1))
    with open(out_path, "w", newline="") as f:
        f.write(text)
    return text


# ---------------------------------------------------------------------------
# AFNI Command Execution
# ---------------------------------------------------------------------------

def run_afni_command(command, capture_output=False, description="", logger=None, cwd=None):
    """Run an AFNI command via subprocess with standardized error handling.

    On success, if the command is ``3dDeconvolve``, any AFNI warning blocks
    in stderr are logged at WARNING.

    Parameters
    ----------
    command : list of str
        The command and arguments.
    capture_output : bool
        If True, capture and return stdout.
    description : str
        Human-readable description for logging.
    logger : logging.Logger, optional
    cwd : str or None, optional
        Working directory for the subprocess.

    Returns
    -------
    subprocess.CompletedProcess or str
        If capture_output is True, returns stdout as a string.
        Otherwise returns the CompletedProcess object.

    Raises
    ------
    ToolExecutionError
        If the command exits with non-zero status. Message includes the
        command, description, and stderr.
    """
    if logger:
        logger.debug("Running: %s", " ".join(command))

    try:
        env = os.environ.copy()
        env["AFNI_COMPRESSOR"] = "GZIP"
        env["AFNI_USE_ERROR_FILE"] = "NO"
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            env=env,
            cwd=cwd,
        )
        # Log AFNI warnings from 3dDeconvolve
        if os.path.basename(command[0]) == "3dDeconvolve":
            _log_afni_warnings(result.stderr, logger)
        if capture_output:
            return result.stdout
        return result
    except subprocess.CalledProcessError as e:
        desc = f" ({description})" if description else ""
        msg = f"AFNI command failed{desc}: {' '.join(command)}"
        if e.stderr:
            msg += f"\n  stderr: {e.stderr.strip()}"
        if logger:
            logger.error(msg)
        raise ToolExecutionError(msg) from e


def run_afni_capture(command, description="", logger=None, cwd=None):
    """Run an AFNI command and return the CompletedProcess without raising on failure.

    Unlike ``run_afni_command``, this function never raises for a nonzero
    exit code. It raises ``ToolExecutionError`` only if the executable
    cannot be started (OSError).

    Parameters
    ----------
    command : list of str
        The command and arguments.
    description : str
        Human-readable description for error messages.
    logger : logging.Logger, optional
    cwd : str or None, optional
        Working directory for the subprocess.

    Returns
    -------
    subprocess.CompletedProcess
    """
    if logger:
        logger.debug("Running (capture): %s", " ".join(command))

    env = os.environ.copy()
    env["AFNI_COMPRESSOR"] = "GZIP"
    env["AFNI_USE_ERROR_FILE"] = "NO"
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            env=env,
            cwd=cwd,
        )
    except OSError as e:
        raise ToolExecutionError(
            f"Could not start AFNI command ({description}): "
            f"{' '.join(command)}: {e}"
        ) from e


def _log_afni_warnings(stderr: str, logger) -> None:
    """Log AFNI warning blocks from stderr at WARNING level.

    A warning block starts at a line containing ``*+ WARNING`` and continues
    with lines that do not start with ``++``, ``**``, ``*+`` or `` + ``.
    """
    if not logger or not stderr:
        return
    lines = stderr.splitlines()
    block = []
    in_block = False
    for line in lines:
        if "*+ WARNING" in line:
            if block:
                logger.warning("AFNI: %s", "\n".join(block))
            block = [line]
            in_block = True
        elif in_block:
            stripped = line.lstrip()
            if stripped.startswith(("++", "**", "*+", "+ ")):
                # End of block
                logger.warning("AFNI: %s", "\n".join(block))
                block = []
                in_block = False
            else:
                block.append(line)
    if block:
        logger.warning("AFNI: %s", "\n".join(block))


# ---------------------------------------------------------------------------
# 3dinfo
# ---------------------------------------------------------------------------

def get_3dinfo_properties(nifti_path, logger=None, keys=None):
    """
    Get key properties from a NIfTI file using targeted 3dinfo flags.

    Parameters
    ----------
    keys : iterable of str, optional
        Subset of the available keys to query; all keys when None.

    Returns
    -------
    dict with the requested keys among 'space' and 'dmax'
    """
    props = {}
    queries = {
        "space": ["-space"],
        "dmax": ["-dmax"],
    }
    if keys is not None:
        queries = {k: v for k, v in queries.items() if k in keys}
    for key, flags in queries.items():
        try:
            out = run_afni_command(
                ["3dinfo"] + flags + [nifti_path],
                capture_output=True,
                description=f"3dinfo {flags[0]} {nifti_path}",
                logger=logger,
            )
            props[key] = out.strip()
        except ToolExecutionError:
            if logger:
                logger.error("Could not retrieve %s from %s with 3dinfo.", key, nifti_path)
            props[key] = None

    return props


# ---------------------------------------------------------------------------
# 3dDeconvolve base command builders
# ---------------------------------------------------------------------------

def build_decon_base_command(input_spec, censor_path, motion_path, ortvecs,
                             run_starts, mask_path, tr):
    """Build the base 3dDeconvolve command with nuisance regressors.

    Parameters
    ----------
    input_spec : str
        Path (or AFNI sub-brick selector) for -input.
    censor_path : str
        Path to the binary censor file.
    motion_path : str
        Path to the prepared motion regressor file.
    ortvecs : list of (str, str)
        Additional -ortvec pairs ``(path, name)``.
    run_starts : list of int or None
        Concatenation offsets for -concat. Pass None or a single-element
        list to omit -concat.
    mask_path : str or None
        Path to a mask file (omitted when None).
    tr : float
        Repetition time in seconds.

    Returns
    -------
    list of str
        Partial 3dDeconvolve command (caller appends stimulus and output flags).
    """
    cmd = [
        "3dDeconvolve", "-quiet",
        "-input", input_spec,
        "-polort", "A",
    ]
    if run_starts is not None and len(run_starts) > 1:
        concat_str = "1D: " + " ".join(str(s) for s in run_starts)
        cmd.extend(["-concat", concat_str])
    if mask_path:
        cmd.extend(["-mask", mask_path])
    cmd.extend(["-censor", censor_path])
    cmd.extend(["-ortvec", motion_path, "motion_regressors"])
    for path, name in ortvecs:
        cmd.extend(["-ortvec", path, name])
    cmd.extend(["-TR_times", str(tr), "-local_times"])
    return cmd


def build_decon_nodata_command(total_trs, tr, run_starts, polort):
    """Build a 3dDeconvolve -nodata command for dry runs.

    Parameters
    ----------
    total_trs : int
        Total number of TRs.
    tr : float
        Repetition time in seconds.
    run_starts : list of int or None
        Concatenation offsets for -concat.
    polort : str or int
        Polort value (e.g. ``"A"``, ``"-1"``).

    Returns
    -------
    list of str
        Partial 3dDeconvolve command.
    """
    cmd = [
        "3dDeconvolve", "-nodata", str(total_trs), str(tr),
        "-polort", str(polort),
    ]
    if run_starts is not None and len(run_starts) > 1:
        concat_str = "1D: " + " ".join(str(s) for s in run_starts)
        cmd.extend(["-concat", concat_str])
    cmd.extend(["-local_times"])
    return cmd


# ---------------------------------------------------------------------------
# REML_cmd collection
# ---------------------------------------------------------------------------

def collect_reml_cmds(staging_dir, pre, step):
    """Collect and rename REML_cmd files from a staging directory.

    Unprefixed REML_cmd files (e.g. ``3dDeconvolve.REML_cmd``,
    ``Decon.REML_cmd``) are renamed to ``{pre}_{step}.REML_cmd``. More
    than one unprefixed file raises GuardError.

    Parameters
    ----------
    staging_dir : str
        Absolute path to the staging directory.
    pre : str
        Output file prefix.
    step : str
        Step label for the renamed file.

    Returns
    -------
    list of (str, str)
        Each element is ``(relpath, 'reml_cmd')`` where relpath is the
        filename relative to the staging directory.

    Raises
    ------
    GuardError
        If multiple unprefixed REML_cmd files exist or a prefixed file
        does not start with *pre*.
    """
    from . import names as _names  # avoid circular at module level

    results = []
    unprefixed = []
    for entry in os.listdir(staging_dir):
        if entry.endswith(".REML_cmd"):
            full = os.path.join(staging_dir, entry)
            if not os.path.isfile(full):
                continue
            if entry.startswith(pre):
                results.append((entry, "reml_cmd"))
            else:
                unprefixed.append(entry)

    if len(unprefixed) > 1:
        raise GuardError(
            f"Multiple unprefixed REML_cmd files in {staging_dir}: {unprefixed}"
        )
    if unprefixed:
        old = os.path.join(staging_dir, unprefixed[0])
        new_name = _names.reml_cmd(pre, step)
        new = os.path.join(staging_dir, new_name)
        os.replace(old, new)
        results.append((new_name, "reml_cmd"))

    # Validate prefixed files
    for relpath, _ in results:
        if not relpath.startswith(pre):
            raise GuardError(
                f"REML_cmd file '{relpath}' does not start with prefix '{pre}'."
            )

    return results


# ---------------------------------------------------------------------------
# Min-outlier EPI extraction
# ---------------------------------------------------------------------------

def gen_min_outlier_epi(source_path, start, n_vols, out_path, logger, cwd=None):
    """Extract the minimum-outlier EPI frame from a volume range.

    Parameters
    ----------
    source_path : str
        Path to the 4D NIfTI scan.
    start : int
        First volume index (0-based).
    n_vols : int
        Number of volumes in the range.
    out_path : str
        Path for the output single-volume NIfTI.
    logger : logging.Logger
    cwd : str or None, optional
        Working directory for the subprocess.

    Returns
    -------
    dict
        ``{'tr_index': int, 'fraction': float}``

    Raises
    ------
    ToolExecutionError
        If 3dToutcount output cannot be parsed or 3dbucket fails.
    """
    selector = f"{source_path}[{start}..{start + n_vols - 1}]"
    toutcount_out = run_afni_command(
        ["3dToutcount", "-automask", "-fraction", selector],
        capture_output=True,
        description="3dToutcount min-outlier scan",
        logger=logger,
        cwd=cwd,
    )

    try:
        fractions = [float(v) for v in toutcount_out.strip().split()]
    except (ValueError, AttributeError) as e:
        raise ToolExecutionError(
            f"Could not parse 3dToutcount output for {selector}: {e}"
        ) from e

    if not fractions:
        raise ToolExecutionError(
            f"3dToutcount returned no data for {selector}."
        )

    idx = int(np.argmin(fractions))
    logger.info(
        "Min-outlier TR: index %d (outlier fraction = %.6f).",
        idx, fractions[idx],
    )

    run_afni_command(
        ["3dbucket", "-prefix", out_path,
         f"{source_path}[{start + idx}]"],
        description="3dbucket min-outlier EPI",
        logger=logger,
        cwd=cwd,
    )

    return {"tr_index": idx, "fraction": fractions[idx]}


# ---------------------------------------------------------------------------
# Censor-interpolation and bandpass filtering of 1D files
# ---------------------------------------------------------------------------

def censor_interpolate_1d_afni(input_path, tr, censor_path, out_dir,
                                out_prefix, label, logger, cwd=None):
    """Interpolate censored TRs in a nuisance regressor 1D file using AFNI 3dTproject -cenmode NTRP.

    Invokes ``3dTproject`` with ``-cenmode NTRP`` to replace censored TRs with
    interpolated values in the input 1D file.  Because AFNI interprets .1D files
    as rows=voxels, cols=timepoints, the input is presented to 3dTproject with a
    trailing apostrophe (AFNI transpose operator) so the time axis is read
    correctly.  After the command executes, ``1dtranspose`` is applied to restore
    rows=TRs, cols=columns for all downstream consumers.

    Parameters
    ----------
    input_path : str
        Path to the input 1D file (rows=TRs orientation).
    tr : float
        Repetition time in seconds.
    censor_path : str
        Path to the AFNI-format censor file (1=keep, 0=censor).
    out_dir : str
        Output directory for the interpolated file.
    out_prefix : str
        Filename prefix for the output filename.
    label : str
        Descriptive label appended to the output filename.
    logger : logging.Logger
    cwd : str or None, optional
        Working directory for the subprocess.

    Returns
    -------
    str
        Absolute path to the interpolated 1D file.
    """
    out_path = os.path.join(out_dir, f"{out_prefix}_{label}_interp.1D")

    cmd = ["3dTproject",
           "-polort", "-1",
           "-dt", str(tr),
           "-input", f"{input_path}'",
           "-censor", censor_path,
           "-cenmode", "NTRP",
           "-prefix", out_path]

    run_afni_command(cmd, description=f"3dTproject NTRP interpolate {label}",
                     logger=logger, cwd=cwd)

    if not os.path.exists(out_path):
        raise ToolExecutionError(f"Expected NTRP-interpolated 1D file not found: {out_path}")

    # Restore rows=TRs, cols=cols orientation (3dTproject output is transposed)
    transposed_path = out_path + ".transposed.1D"
    transpose_cmd = ["1dtranspose", out_path, transposed_path]
    run_afni_command(transpose_cmd, description=f"1dtranspose interpolate {label}",
                     logger=logger, cwd=cwd)
    if not os.path.exists(transposed_path):
        raise ToolExecutionError(f"1dtranspose failed for interpolated 1D file: {out_path}")
    os.replace(transposed_path, out_path)

    logger.info("NTRP-interpolated 1D file (rows=TRs, cols=cols) saved to %s", out_path)
    return out_path


def bandpass_filter_1d_afni(input_path, tr, bandpass, out_dir, out_prefix,
                             label, logger, cwd=None):
    """Bandpass-filter a nuisance regressor 1D file using AFNI 3dBandpass.

    3dBandpass applies its default quadratic detrend, matching the BOLD path.

    Parameters
    ----------
    input_path : str
        Path to the input 1D file (rows=TRs orientation).
    tr : float
        Repetition time in seconds.
    bandpass : list or tuple of float
        ``[fbot, ftop]`` passband in Hz.
    out_dir : str
        Output directory for the filtered file.
    out_prefix : str
        Filename prefix for the output filename.
    label : str
        Descriptive label appended to the output filename.
    logger : logging.Logger
    cwd : str or None, optional
        Working directory for the subprocess.

    Returns
    -------
    str
        Absolute path to the bandpass-filtered 1D file.
    """
    out_path = os.path.join(out_dir, f"{out_prefix}_{label}_bp.1D")

    cmd = ["3dBandpass",
           "-dt", str(tr),
           "-prefix", out_path,
           str(bandpass[0]), str(bandpass[1]),
           f"{input_path}'"]

    run_afni_command(cmd, description=f"3dBandpass {label}",
                     logger=logger, cwd=cwd)

    if not os.path.exists(out_path):
        raise ToolExecutionError(f"Expected bandpass-filtered 1D file not found: {out_path}")

    # Restore rows=TRs, cols=cols orientation (3dBandpass output is transposed)
    transposed_path = out_path + ".transposed.1D"
    transpose_cmd = ["1dtranspose", out_path, transposed_path]
    run_afni_command(transpose_cmd, description=f"1dtranspose {label}",
                     logger=logger, cwd=cwd)
    if not os.path.exists(transposed_path):
        raise ToolExecutionError(f"1dtranspose failed for bandpass-filtered 1D file: {out_path}")
    os.replace(transposed_path, out_path)

    logger.info("Bandpass-filtered 1D file (rows=TRs, cols=cols) saved to %s", out_path)
    return out_path


# ---------------------------------------------------------------------------
# Contrast Parsing
# ---------------------------------------------------------------------------

def valid_contrast_functions(contrast_list, contrast_labs_list, cond_list, logger=None):
    """Parse and validate linear contrast equations.

    Accepted format: ``coef*COND[+-coef*COND...]``
    Examples: ``1*stimA-1*stimB``, ``-1*A+0.5*B+0.5*C``, ``+1*X-1*Y``

    Returns a list of dicts, one per contrast, each with keys 'COEFS' (list of
    str coefficients with signs) and 'CONDS' (list of condition names).
    """

    # Check that contrast_list and contrast_labs_list are same size
    if len(contrast_list) != len(contrast_labs_list):
        raise ConfigError(
            f"Every contrast function must have exactly one contrast label "
            f"({len(contrast_list)} functions, {len(contrast_labs_list)} labels)."
        )

    # Regex for a single term: optional sign, a numeric coefficient, *, condition name
    _TERM_RE = re.compile(r'([+-]?\d*\.?\d+)\*(\w+)')
    # Regex that matches the entire valid contrast string (one or more terms)
    _FULL_RE = re.compile(r'^([+-]?\d*\.?\d+\*\w+)([+-]\d*\.?\d+\*\w+)*$')

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
                raise ConfigError(
                    f"Contrast '{raw}' references condition '{item}' "
                    f"which is not among the configured condition labels ({cond_list})."
                )

        # Warn about zero coefficients (technically valid but likely a mistake)
        for coef, cond in zip(coefs, conds):
            if float(coef) == 0.0:
                if logger:
                    logger.warning("Contrast '%s': coefficient for '%s' is 0 -- "
                                   "this condition will have no effect.", raw, cond)

        out.append({'COEFS': coefs, 'CONDS': conds})
    return out


# ---------------------------------------------------------------------------
# Filename Sanitization
# ---------------------------------------------------------------------------

def sanitize_filename_label(label):
    """Replace filesystem-unsafe characters with underscores.

    Preserves alphanumerics, hyphens, underscores, and periods. All other
    characters (including spaces, slashes, colons) are replaced with '_'.
    Consecutive underscores are collapsed.
    """
    sanitized = re.sub(r'[^\w.\-]', '_', label)
    sanitized = re.sub(r'_+', '_', sanitized)
    return sanitized.strip('_')
