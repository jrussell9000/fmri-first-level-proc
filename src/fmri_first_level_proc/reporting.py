"""Logging setup, graded warnings, pipeline result type, and QC summary output."""

import dataclasses
import json
import logging
import os
import sys
from pathlib import Path


# Module-level warning accumulator (cross-pipeline contract)
_WARNING_ACCUMULATOR: list[dict] = []


def get_warnings() -> list[dict]:
    """Return a shallow copy of the module-level warning accumulator."""
    return list(_WARNING_ACCUMULATOR)


def clear_warnings() -> None:
    """Clear all accumulated warnings. Call at pipeline entry before dispatching."""
    _WARNING_ACCUMULATOR.clear()


@dataclasses.dataclass
class FirstLevelResult:
    """Structured result returned by each pipeline's run() function.

    Attributes
    ----------
    status : str
        ``'completed'`` on success.
    output_dir : Path
        Directory where output files were written.
    warnings : list[dict]
        Accumulated graded_warning records from the pipeline run.
    qc_summary : dict
        Quality-control metrics (written to the QC summary JSON).
    output_files : list[str]
        Paths to all files produced by the pipeline run.
    """

    status: str
    output_dir: Path
    warnings: list[dict]
    qc_summary: dict
    output_files: list[str]


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


def graded_warning(
    logger: logging.Logger,
    severity: str,
    code: str,
    message: str,
    *,
    user_facing: bool = False,
) -> dict:
    """
    Emit a graded warning and return a structured record for accumulation.

    Parameters
    ----------
    logger : logging.Logger
        Logger instance to use for emission.
    severity : str
        One of 'low', 'medium', or 'high'. High-severity warnings trigger
        exit code 3 when accumulated in FirstLevelResult.warnings.
    code : str
        Machine-readable warning code (e.g. 'W001_MISSING_RUNS').
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

    Notes
    -----
    Appends to the module-level _WARNING_ACCUMULATOR and returns the dict.
    Pipeline entry points should call clear_warnings() at entry and
    get_warnings() at FirstLevelResult construction.
    """
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


def write_qc_summary(out_dir, out_file_pre, qc_data, logger):
    """Write a QC summary JSON file.

    Parameters
    ----------
    out_dir : str
        Output directory.
    out_file_pre : str
        Output file prefix.
    qc_data : dict
        QC data to write. Typical keys include:
        - analysis_type, hrf_model, fd_threshold, censor_prev_tr
        - n_trs_total, n_trs_censored, pct_censored
        - per_condition_trial_counts, per_condition_surviving_trials (task only)
        - dof (degrees of freedom)
        - per_run_censoring (rest_conn only)
    logger : logging.Logger
    """
    qc_path = os.path.join(out_dir, f"{out_file_pre}_qc_summary.json")
    try:
        with open(qc_path, 'w') as f:
            json.dump(qc_data, f, indent=2)
        logger.info("QC summary written to %s", qc_path)
    except OSError as e:
        logger.warning("Could not write QC summary to %s: %s", qc_path, e)
