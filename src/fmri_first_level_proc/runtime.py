"""Preflight binary reachability, version-lock validation, and CPU discovery for fmri-first-level-proc."""

import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from .exceptions import ToolUnavailableError, ToolVersionError
from .reporting import graded_warning


def _cgroup_cpu_limit(cgroup_root: Path) -> int | None:
    """Whole CPUs allowed by the cgroup CPU quota (v2 cpu.max, else v1 CFS), or None if unlimited."""
    try:
        quota, period = (cgroup_root / "cpu.max").read_text().split()[:2]
        if quota == "max":
            return None
        return max(1, int(quota) // int(period))
    except (OSError, ValueError):
        pass
    try:
        quota = int((cgroup_root / "cpu" / "cpu.cfs_quota_us").read_text())
        period = int((cgroup_root / "cpu" / "cpu.cfs_period_us").read_text())
        return max(1, quota // period) if quota > 0 and period > 0 else None
    except (OSError, ValueError):
        return None


def _schedulable_cpus() -> int:
    """CPUs this process may run on (affinity-aware where the platform supports it)."""
    if hasattr(os, "process_cpu_count"):  # Python 3.13+
        return os.process_cpu_count() or 1
    if hasattr(os, "sched_getaffinity"):
        return len(os.sched_getaffinity(0)) or 1
    return os.cpu_count() or 1


def available_cpus(environ=None, cgroup_root: Path = Path("/sys/fs/cgroup")) -> tuple[int, str]:
    """Resolve ``num_cores: auto`` to a CPU count and a description of its source.

    Order:
    1. ``OMP_NUM_THREADS``, when set to a positive integer. Orchestrators such as
       Kubernetes set it from the pod's CPU request (downward API), which is the
       reservation the scheduler guarantees. Capped at the cgroup limit if lower.
    2. The cgroup CPU quota (the container's CPU limit), rounded down, minimum 1.
    3. CPUs schedulable for this process.
    """
    environ = os.environ if environ is None else environ
    limit = _cgroup_cpu_limit(cgroup_root)

    omp = environ.get("OMP_NUM_THREADS", "").strip()
    if omp.isdigit() and int(omp) > 0:
        if limit is not None and limit < int(omp):
            return limit, f"OMP_NUM_THREADS={omp}, capped at cgroup CPU limit {limit}"
        return int(omp), "OMP_NUM_THREADS"
    if limit is not None:
        return limit, "cgroup CPU limit"
    return _schedulable_cpus(), "schedulable CPUs"

# Complete AFNI binary list
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
    "1dtranspose",
    "3dBlurToFWHM",
    "3dFWHMx",
    "3dMean",
    "3dBrickStat",
    "3dTcorr1D",
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
            resolved_home = str(Path(afni_which).parent)
        else:
            candidate = Path.home() / "abin"
            if candidate.is_dir():
                resolved_home = str(candidate)

    missing: list[str] = []
    for binary in _AFNI_BINARIES:
        # With path=None, which() searches $PATH; otherwise only resolved_home
        reachable = shutil.which(binary, path=resolved_home) is not None

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
    top-level ``python`` field (patch version ignored). A mismatch is advisory:
    it emits a medium-severity ``PYTHON_VERSION_MISMATCH`` graded warning and
    the run continues, since ``requires-python`` defines what is supported. If
    the lockfile has no ``python`` field, the check is skipped with an INFO log.

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
        If the installed AFNI version does not match its lockfile pin.
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    lockfile: dict = yaml.safe_load(Path(lockfile_path).read_text())

    tools_verified: int = 0

    # --- AFNI version check ---
    expected_afni: str = lockfile.get("binaries", {}).get("AFNI", "PLACEHOLDER")

    if expected_afni == "PLACEHOLDER":
        logger.info("AFNI version pinning skipped (lockfile contains PLACEHOLDER).")
    else:
        cmd = ["afni", "-ver"]
        if afni_home is not None:
            cmd[0] = str(Path(afni_home) / "afni")

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

    # --- Python version check (major.minor; advisory) ---
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
            # Advisory only: pyproject's requires-python is the support contract, and a
            # different interpreter minor rarely changes numerics. AFNI stays strict above.
            graded_warning(
                logger, 'medium', 'PYTHON_VERSION_MISMATCH',
                f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} "
                f"differs from the {pin_major}.{pin_minor}.x pinned in tools.lock.yaml; results "
                "were validated on the pinned version.",
                user_facing=True,
            )
        else:
            tools_verified += 1

    if tools_verified > 0:
        logger.info("Startup version probe passed: %d pinned tool(s) verified.", tools_verified)
