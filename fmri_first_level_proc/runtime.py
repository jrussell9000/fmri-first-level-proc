"""Preflight binary reachability and version-lock validation for fmri-first-level-proc."""

import logging
import os
import re
import shutil
import subprocess
import sys

import yaml

from .exceptions import ToolUnavailableError, ToolVersionError

# Complete AFNI binary list (15 binaries, verified by codebase grep)
_AFNI_BINARIES: list[str] = [
    "3dDeconvolve",
    "3dTproject",
    "3dTstat",
    "3dBandpass",
    "3dROIstats",
    "3dNetCorr",
    "3dresample",
    "3dinfo",
    "3dToutcount",
    "3dbucket",
    "3dcalc",
    "3dLSS",
    "3dTcat",
    "1d_tool.py",
    "1dtranspose",
]


def _parse_afni_version(stdout: str, stderr: str) -> str | None:
    """Parse AFNI version string from combined stdout and stderr output.

    Applies regex r'AFNI[_\\s]+(\\d+\\.\\d+\\.\\d+)' to the concatenation of
    stdout and stderr. Returns the first matching version string or None if no
    match is found.

    Parameters
    ----------
    stdout:
        Captured standard output from the AFNI version probe command.
    stderr:
        Captured standard error from the AFNI version probe command.

    Returns
    -------
    str | None
        Version string (e.g. '24.0.05') or None if unparseable.
    """
    combined = stdout + stderr
    match = re.search(r"AFNI[_\s]+(\d+\.\d+\.\d+)", combined)
    if match:
        return match.group(1)
    return None


def preflight_tool_environments(
    afni_home: str | None = None,
    logger: logging.Logger | None = None,
) -> None:
    """Verify that all required AFNI binaries are reachable on the current system.

    AFNI home discovery order: (1) ``afni_home`` parameter, (2) parent directory
    of ``shutil.which('afni')``, (3) ``~/abin``. All 14 required binaries are
    checked; unreachable binaries are accumulated and a single
    ``ToolUnavailableError`` is raised listing all missing tools.

    Parameters
    ----------
    afni_home:
        Optional explicit path to the directory containing AFNI binaries.
    logger:
        Optional logger for diagnostic messages.

    Raises
    ------
    ToolUnavailableError
        If one or more required AFNI binaries cannot be found.
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    # Discover AFNI home directory
    resolved_home: str | None = None
    if afni_home is not None:
        resolved_home = afni_home
    else:
        afni_which = shutil.which("afni")
        if afni_which is not None:
            resolved_home = os.path.dirname(afni_which)
        else:
            candidate = os.path.expanduser("~/abin")
            if os.path.isdir(candidate):
                resolved_home = candidate

    missing: list[str] = []
    for binary in _AFNI_BINARIES:
        if resolved_home is not None:
            full_path = os.path.join(resolved_home, binary)
            reachable = os.path.isfile(full_path) and os.access(full_path, os.X_OK)
        else:
            reachable = shutil.which(binary) is not None

        if not reachable:
            logger.debug("AFNI binary not found: %s", binary)
            missing.append(binary)

    if missing:
        raise ToolUnavailableError(
            f"The following AFNI binaries could not be found: {', '.join(missing)}"
        )

    logger.info("Preflight binary check passed: %d AFNI tool(s) verified.", len(_AFNI_BINARIES))


def probe_tool_versions(
    lockfile_path: str,
    afni_home: str | None = None,
    logger: logging.Logger | None = None,
) -> None:
    """Validate installed tool versions against the pinned versions in the lockfile.

    Reads the lockfile at ``lockfile_path`` and performs two independent checks:

    **AFNI**: runs ``afni -ver``, parses the output via ``_parse_afni_version()``,
    and enforces strict exact-match comparison. If the lockfile contains
    ``PLACEHOLDER`` for the AFNI version, the check is skipped with an INFO log.

    **Python**: compares ``sys.version_info`` major.minor against the lockfile's
    top-level ``python`` field (minor-series match: patch version is ignored per
    PEP 440 compatibility semantics). If the lockfile has no ``python`` field,
    the check is skipped with an INFO log.

    Parameters
    ----------
    lockfile_path:
        Absolute or relative path to ``tools.lock.yaml``.
    afni_home:
        Optional explicit path to the directory containing AFNI binaries.
    logger:
        Optional logger for diagnostic messages.

    Raises
    ------
    ToolUnavailableError
        If a tool binary is unreachable or its version output is unparseable.
    ToolVersionError
        If a tool's installed version does not match its lockfile pin.
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    with open(lockfile_path, "r") as fh:
        lockfile: dict = yaml.safe_load(fh)

    tools_verified: int = 0

    # --- AFNI version check ---
    expected_afni: str = lockfile.get("binaries", {}).get("AFNI", "PLACEHOLDER")

    if expected_afni == "PLACEHOLDER":
        logger.info("AFNI version pinning skipped (lockfile contains PLACEHOLDER).")
    else:
        cmd = ["afni", "-ver"]
        if afni_home is not None:
            cmd[0] = os.path.join(afni_home, "afni")

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
            )
            stdout = result.stdout
            stderr = result.stderr
        except (subprocess.SubprocessError, OSError) as exc:
            raise ToolUnavailableError(
                f"AFNI: probe command {cmd!r} failed ({exc}); expected version {expected_afni}"
            ) from exc

        actual_afni = _parse_afni_version(stdout, stderr)

        if actual_afni is None:
            raise ToolUnavailableError(
                f"AFNI: version not parseable from probe output; expected {expected_afni}"
            )

        if actual_afni != expected_afni:
            raise ToolVersionError(
                f"AFNI: expected {expected_afni}, got {actual_afni}"
            )

        tools_verified += 1

    # --- Python version check (minor-series match) ---
    expected_python: str | None = lockfile.get("python")

    if expected_python is None:
        logger.info("Python version pinning skipped (no python field in lockfile).")
    else:
        parts = expected_python.split(".")
        if len(parts) < 2:
            raise ToolUnavailableError(
                f"Python: lockfile pin '{expected_python}' is not a valid major.minor version string"
            )
        try:
            pin_major = int(parts[0])
            pin_minor = int(parts[1])
        except ValueError:
            raise ToolUnavailableError(
                f"Python: lockfile pin '{expected_python}' is not a valid major.minor version string"
            )

        if sys.version_info.major != pin_major or sys.version_info.minor != pin_minor:
            raise ToolVersionError(
                f"Python: expected {pin_major}.{pin_minor}.x, "
                f"got {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            )

        tools_verified += 1

    if tools_verified > 0:
        logger.info("Startup version probe passed: %d pinned tool(s) verified.", tools_verified)
