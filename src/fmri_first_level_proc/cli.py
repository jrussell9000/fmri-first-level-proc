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

Reads a YAML configuration file, validates it via config.load_and_validate,
and dispatches each analysis block to the appropriate pipeline run() function.

Exit codes
----------
0 : All analyses completed with no high-severity warnings.
1 : Pipeline invariant violation (GuardError); indicates a bug.
2 : Configuration or input error (ConfigError, InputError).
3 : All analyses completed but one or more high-severity warnings were raised.
4 : External tool unavailable, version mismatch, or failed (ToolUnavailableError, ToolVersionError, ToolExecutionError).
5 : Model estimation failure (ModelError): singularity, insufficient DOF, etc.

Public API
----------
main(cli_name)
    CLI entry point registered as the ``fmri-first-level-proc`` console script.
    Parses --config, --dry-run, --analyses, --log-file, and --force flags.

_main_deprecated()
    Deprecated alias for main() registered as the ``run-first-level`` console
    script. Emits a CLI_DEPRECATED graded_warning before delegating.

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

import subprocess
import sys
import time
import argparse
from importlib.resources import as_file, files

from .config import load_and_validate
from .exceptions import (
    ConfigError,
    InputError,
    ModelError,
    GuardError,
    ToolUnavailableError,
    ToolVersionError,
    ToolExecutionError,
)
from .pipelines import DISPATCH
from .reporting import setup_logging, graded_warning
from .runtime import preflight_tool_environments, probe_tool_versions

# Tool version lockfile shipped as package data
_LOCKFILE = files("fmri_first_level_proc") / "data" / "tools.lock.yaml"


def main(cli_name: str = 'fmri-first-level-proc') -> None:
    """CLI entry point: parse config, validate, preflight, and dispatch analysis blocks.

    Parameters
    ----------
    cli_name:
        Name of the invoked console script. Used to detect the deprecated
        ``run-first-level`` alias and emit CLI_DEPRECATED graded_warning.
    """
    parser = argparse.ArgumentParser(
        description="Run fMRI first-level analyses from a YAML config file."
    )
    parser.add_argument(
        "--config", type=str, required=True,
        help="Path to the YAML configuration file."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate the config and print the analysis plan without executing."
    )
    parser.add_argument(
        "--analyses", type=int, nargs="+", default=None,
        help="Run only specific analysis block indices (0-based). Default: run all."
    )
    parser.add_argument(
        "--log-file", type=str, default=None,
        help="Optional path to a log file (useful for parallel runs)."
    )
    parser.add_argument(
        "--force", action="store_true",
        help="If a block's out_dir holds outputs from a different configuration, "
             "delete that block's previous outputs and rerun instead of failing."
    )

    args = parser.parse_args()
    logger = setup_logging('fmri_first_level_proc', log_file=args.log_file)

    if cli_name == 'run-first-level':
        graded_warning(
            logger, 'low', 'CLI_DEPRECATED',
            'The "run-first-level" command is deprecated; use "fmri-first-level-proc" instead.',
            user_facing=True,
        )

    try:
        preflight_tool_environments(logger=logger)
        if _LOCKFILE.is_file():
            with as_file(_LOCKFILE) as lockfile_path:
                probe_tool_versions(str(lockfile_path), logger=logger)
        else:
            graded_warning(
                logger, 'low', 'LOCKFILE_ABSENT',
                f"tools.lock.yaml not found at {_LOCKFILE}; skipping version pinning.",
                user_facing=True,
            )

        configs = load_and_validate(args.config, logger)
        logger.info("Config validated: %d analysis block(s) found.", len(configs))

        if args.analyses is not None:
            for idx in args.analyses:
                if idx < 0 or idx >= len(configs):
                    raise ConfigError(
                        f"--analyses index {idx} is out of range (0-{len(configs) - 1})."
                    )
            selected = set(args.analyses)
            configs = [c for i, c in enumerate(configs) if i in selected]
            logger.info("Running %d selected analysis block(s).", len(configs))

        logger.info("=" * 60)
        logger.info("ANALYSIS PLAN")
        logger.info("=" * 60)
        for i, config in enumerate(configs):
            logger.info(
                "  [%d] %s (type: %s)", i, config.analysis_name or "", config.analysis_type
            )
            logger.info("       out_dir: %s", config.out_dir)
            logger.info("       out_file_pre: %s", config.out_file_pre)
        logger.info("=" * 60)

        if args.dry_run:
            logger.info("Dry run complete. No analyses were executed.")
            return

        start_time = time.time()
        all_warnings: list[dict] = []

        for i, config in enumerate(configs):
            logger.info("-" * 60)
            logger.info(
                "Starting analysis [%d]: %s (type: %s)",
                i, config.analysis_name or "", config.analysis_type,
            )
            logger.info("-" * 60)
            block_start = time.time()
            result = DISPATCH[config.analysis_type](config, logger, force=args.force)
            all_warnings.extend(result.warnings)
            logger.info(
                "Analysis [%d] '%s' completed in %.2f seconds.",
                i, config.analysis_name or "", time.time() - block_start,
            )

        logger.info("=" * 60)
        logger.info(
            "All analyses completed in %.2f seconds.", time.time() - start_time
        )

        if any(w['severity'] == 'high' for w in all_warnings):
            sys.exit(3)

    except ConfigError as e:
        logger.error(str(e)); sys.exit(2)
    except InputError as e:
        logger.error(str(e)); sys.exit(2)
    except ModelError as e:
        logger.error(str(e)); sys.exit(5)
    except (ToolUnavailableError, ToolVersionError, ToolExecutionError) as e:
        logger.error(str(e)); sys.exit(4)
    except GuardError as e:
        logger.critical(str(e)); sys.exit(1)
    except subprocess.CalledProcessError as e:
        logger.error("Unexpected subprocess failure: %s", e); sys.exit(4)
    except Exception as e:
        logger.critical("Unexpected error: %s", e); sys.exit(1)


def _main_deprecated() -> None:
    """Deprecated CLI alias; delegates to main() with deprecation warning."""
    main(cli_name='run-first-level')


if __name__ == "__main__":
    main()
