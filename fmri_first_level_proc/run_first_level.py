#!/usr/bin/env python3

# ============================================================================
# YAML CONFIG RUNNER FOR fMRI FIRST-LEVEL PROCESSING
# Reads a YAML config, validates it, and dispatches each analysis block
# to the appropriate pipeline script's run() function.
#
# Usage:
#   fmri-first-level-proc --config my_study.yaml
#   fmri-first-level-proc --config my_study.yaml --dry-run
#   fmri-first-level-proc --config my_study.yaml --analyses 0 2
#   fmri-first-level-proc --config my_study.yaml --log-file run.log
#
# Author: Taylor J. Keding, Ph.D.
# ============================================================================
"""
CLI entry point and dispatch runner for fmri_first_level_proc.

Reads a YAML configuration file, validates and resolves each analysis block via
first_level_config.load_and_validate_blocks, and dispatches each valid block to the
appropriate pipeline run() function.

Each analysis block is validated, checked or run independently: a failing
block stops at its first error and the remaining blocks proceed. Global
problems (unreadable YAML, top-level or global section errors, runtime
check) stop the whole run. The exit code is that of the first failing block
in config order; with no failing block it is 3 when any high-severity
warning was raised, otherwise 0. --dry-run validates the config and every
block's input files without executing or writing.

Exit codes
----------
0 : All analyses completed with no high-severity warnings.
1 : Pipeline invariant violation (GuardError); unwrapped OSError; unexpected exceptions.
2 : Configuration or input error (ConfigError, InputError).
3 : All analyses completed but one or more high-severity warnings were raised.
4 : External tool unavailable, version mismatch, or failed (ToolUnavailableError, ToolVersionError, ToolExecutionError).
5 : Model estimation failure (ModelError): singularity, insufficient DOF, etc.

Public API
----------
main()
    CLI entry point registered as the ``fmri-first-level-proc`` console script.
    Parses --config, --dry-run, --analyses, and --log-file flags.

DISPATCH : dict
    Mapping from analysis type string (``"task_act"``, ``"task_conn"``,
    ``"rest_conn"``) to the corresponding pipeline run() function.
    Available as a public export from the package for programmatic use.

Usage (CLI)
-----------
    fmri-first-level-proc --config my_study.yaml
    fmri-first-level-proc --config my_study.yaml --dry-run
    fmri-first-level-proc --config my_study.yaml --analyses 0 2
    fmri-first-level-proc --config my_study.yaml --log-file run.log

Usage (Python)
--------------
    from fmri_first_level_proc import load_and_validate, setup_logging, DISPATCH

    logger = setup_logging("my_analysis")
    configs = load_and_validate("my_config.yaml", logger)
    for config in configs:
        result = DISPATCH[config.analysis_type](config, logger)
"""

import sys
import time
import argparse

from .first_level_utils import setup_logging
from .first_level_config import load_and_validate_blocks
from .engine import write_failure_qc
from .exceptions import ConfigError, exit_code
from .inputs import check_inputs
from .runtime import runtime_check

from .task_act_first_level import run as run_task_act
from .task_conn_first_level import run as run_task_conn
from .rest_conn_first_level import run as run_rest_conn

# Dispatch table: analysis_type string -> pipeline run() function
DISPATCH = {
    "task_act": run_task_act,
    "task_conn": run_task_conn,
    "rest_conn": run_rest_conn,
}


def main() -> None:
    """CLI entry point: validate the config, then check or run each analysis block independently."""
    parser = argparse.ArgumentParser(
        description="Run fMRI first-level analyses from a YAML config file."
    )
    parser.add_argument(
        "--config", type=str, required=True,
        help="Path to the YAML configuration file."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate the config and the input files of every block without executing."
    )
    parser.add_argument(
        "--analyses", type=int, nargs="+", default=None,
        help="Run only specific analysis block indices (0-based). Default: run all."
    )
    parser.add_argument(
        "--log-file", type=str, default=None,
        help="Optional path to a log file (useful for parallel runs)."
    )

    args = parser.parse_args()
    logger = setup_logging('fmri_first_level_proc', log_file=args.log_file)

    try:
        versions = runtime_check(logger)
        blocks = load_and_validate_blocks(args.config, logger)
    except Exception as e:
        _log_failure(logger, "Global configuration or runtime check failed", e)
        sys.exit(exit_code(e))

    logger.info("Config read: %d analysis block(s) found.", len(blocks))

    if args.analyses is not None:
        for idx in args.analyses:
            if idx < 0 or idx >= len(blocks):
                logger.error(
                    "--analyses index %d is out of range (0-%d).", idx, len(blocks) - 1
                )
                sys.exit(exit_code(ConfigError("")))
        selected = set(args.analyses)
        blocks = [b for b in blocks if b.index in selected]
        logger.info("Running %d selected analysis block(s).", len(blocks))

    logger.info("=" * 60)
    logger.info("ANALYSIS PLAN")
    logger.info("=" * 60)
    for b in blocks:
        logger.info("  [%d] %s (type: %s)", b.index, b.name or "", b.analysis_type)
        if b.config is not None:
            logger.info("       out_dir: %s", b.config.out_dir)
            logger.info("       out_file_pre: %s", b.config.out_file_pre)
        else:
            logger.info("       INVALID: %s: %s", type(b.error).__name__, b.error)
    logger.info("=" * 60)

    start_time = time.time()
    all_warnings: list[dict] = []
    outcomes = []  # (index, name, outcome text, exit code or None)

    for b in blocks:
        name = b.name or ""
        if b.error is not None:
            _log_failure(logger, f"Analysis [{b.index}] '{name}' is invalid", b.error)
            if not args.dry_run:
                write_failure_qc(b.raw_out_dir, b.raw_out_file_pre, b.analysis_type,
                                 b.error, "config-validation", versions, logger)
            outcomes.append((b.index, name, f"invalid ({type(b.error).__name__})",
                             exit_code(b.error)))
            continue

        config = b.config
        logger.info("-" * 60)
        if args.dry_run:
            logger.info("Checking inputs of analysis [%d]: %s (type: %s)",
                        b.index, name, config.analysis_type)
            try:
                check_inputs(config, logger)
            except Exception as e:
                _log_failure(logger, f"Analysis [{b.index}] '{name}' inputs are invalid", e)
                outcomes.append((b.index, name, f"inputs invalid ({type(e).__name__})",
                                 exit_code(e)))
                continue
            outcomes.append((b.index, name, "valid", None))
            continue

        logger.info(
            "Starting analysis [%d]: %s (type: %s)", b.index, name, config.analysis_type,
        )
        logger.info("-" * 60)
        block_start = time.time()
        try:
            result = DISPATCH[config.analysis_type](config, logger)
        except Exception as e:
            _log_failure(logger, f"Analysis [{b.index}] '{name}' failed", e)
            outcomes.append((b.index, name, f"failed ({type(e).__name__})", exit_code(e)))
            continue
        all_warnings.extend(result.warnings)
        logger.info(
            "Analysis [%d] '%s' completed in %.2f seconds.",
            b.index, name, time.time() - block_start,
        )
        outcomes.append((b.index, name, result.status, None))

    logger.info("=" * 60)
    logger.info("SUMMARY" + (" (dry run; no analyses were executed)" if args.dry_run else ""))
    for index, name, text, _ in outcomes:
        logger.info("  [%d] %s: %s", index, name, text)
    if not args.dry_run:
        logger.info("All analyses finished in %.2f seconds.", time.time() - start_time)
    logger.info("=" * 60)

    failed_codes = [code for _, _, _, code in outcomes if code is not None]
    if failed_codes:
        sys.exit(failed_codes[0])
    if any(w['severity'] == 'high' for w in all_warnings):
        sys.exit(3)


def _log_failure(logger, prefix, exc):
    """Log an exception at the severity its exit code implies."""
    if exit_code(exc) == 1:
        logger.critical("%s: %s: %s", prefix, type(exc).__name__, exc)
    else:
        logger.error("%s: %s: %s", prefix, type(exc).__name__, exc)


if __name__ == "__main__":
    main()
