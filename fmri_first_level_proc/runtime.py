"""Runtime version validation for fmri-first-level-proc.

Minimum-version policy: installed versions below the lockfile minimum raise
``ToolVersionError``. Validated-version policy: installed versions that
differ from the lockfile validated version emit an ``UNVALIDATED_VERSION``
graded warning (medium severity, user_facing) per tool.

Probes are cached per process (the first call runs the checks; subsequent
calls reuse the cached result). Minimum and validated comparisons are
re-evaluated on every ``runtime_check`` call.
"""

import importlib.resources
import logging
import os
import re
import shutil
import subprocess
import sys

import yaml
from packaging.version import Version, InvalidVersion

from .exceptions import ToolUnavailableError, ToolVersionError
from .first_level_utils import graded_warning


# 19 AFNI binaries used by the package (3dNetCorr is a test-only dependency)
_AFNI_BINARIES: list[str] = [
    "3dDeconvolve",
    "3dTproject",
    "3dTstat",
    "3dBandpass",
    "3dROIstats",
    "3dresample",
    "3dinfo",
    "3dToutcount",
    "3dbucket",
    "3dcalc",
    "3dLSS",
    "3dTcat",
    "1d_tool.py",
    "1dtranspose",
    "3dAttribute",
    "1ddot",
    "3dTcorr1D",
    "3dBlurToFWHM",
    "3dFWHMx",
]

LOCKFILE_RESOURCE = "tools.lock.yaml"


def _parse_afni_version(stdout: str, stderr: str) -> str | None:
    """Parse AFNI version string from combined stdout and stderr output.

    Applies regex r'AFNI[_\\s]+(\\d+\\.\\d+\\.\\d+)' to the concatenation of
    stdout and stderr. Returns the first matching version string or None if no
    match is found.
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
    """Verify that all 19 required AFNI binaries are reachable.

    AFNI home discovery order: (1) *afni_home* parameter, (2) parent directory
    of ``shutil.which('afni')``, (3) ``~/abin``. Unreachable binaries are
    accumulated and a single ``ToolUnavailableError`` is raised listing all
    missing tools.
    """
    if logger is None:
        logger = logging.getLogger(__name__)

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

    logger.info(
        "Preflight binary check passed: %d AFNI tool(s) verified.",
        len(_AFNI_BINARIES),
    )


# ---------------------------------------------------------------------------
# Lockfile loading
# ---------------------------------------------------------------------------

def load_lockfile() -> dict:
    """Load and validate the packaged tools.lock.yaml.

    Returns
    -------
    dict
        Parsed lockfile with validated structure.

    Raises
    ------
    ToolUnavailableError
        If the lockfile is missing, unreadable, malformed or fails
        structural validation.
    """
    try:
        ref = importlib.resources.files("fmri_first_level_proc").joinpath(LOCKFILE_RESOURCE)
        raw = ref.read_text(encoding="utf-8")
    except Exception as e:
        raise ToolUnavailableError(
            f"Packaged lockfile '{LOCKFILE_RESOURCE}' is missing or unreadable: {e}"
        ) from e

    try:
        lock = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        raise ToolUnavailableError(
            f"Packaged lockfile '{LOCKFILE_RESOURCE}' is not valid YAML: {e}"
        ) from e

    # Structural validation
    if not isinstance(lock, dict):
        raise ToolUnavailableError(
            f"Packaged lockfile '{LOCKFILE_RESOURCE}' top level must be a mapping, "
            f"got {type(lock).__name__}."
        )
    if lock.get("lockfile_version") != "2.0.0":
        raise ToolUnavailableError(
            f"Packaged lockfile lockfile_version must be '2.0.0', "
            f"got {lock.get('lockfile_version')!r}."
        )

    tools = lock.get("tools")
    if not isinstance(tools, dict):
        raise ToolUnavailableError("Packaged lockfile missing 'tools' mapping.")

    for tool_name in ("afni", "python", "numpy", "pandas"):
        entry = tools.get(tool_name)
        if not isinstance(entry, dict):
            raise ToolUnavailableError(
                f"Packaged lockfile: tool '{tool_name}' entry is missing or invalid."
            )
        for field in ("minimum", "validated"):
            val = entry.get(field)
            if not isinstance(val, str):
                raise ToolUnavailableError(
                    f"Packaged lockfile: tools.{tool_name}.{field} must be a string, "
                    f"got {val!r}."
                )

        # Format validation
        if tool_name == "afni":
            for field in ("minimum", "validated"):
                if not re.match(r"^\d+\.\d+\.\d+$", entry[field]):
                    raise ToolUnavailableError(
                        f"Packaged lockfile: tools.afni.{field} '{entry[field]}' "
                        f"does not match NN.NN.NN format."
                    )
        elif tool_name == "python":
            for field in ("minimum", "validated"):
                if not re.match(r"^\d+\.\d+$", entry[field]):
                    raise ToolUnavailableError(
                        f"Packaged lockfile: tools.python.{field} '{entry[field]}' "
                        f"does not match NN.NN format."
                    )
        else:
            for field in ("minimum", "validated"):
                try:
                    Version(entry[field])
                except InvalidVersion:
                    raise ToolUnavailableError(
                        f"Packaged lockfile: tools.{tool_name}.{field} "
                        f"'{entry[field]}' is not a valid PEP 440 version."
                    )

    return lock


# ---------------------------------------------------------------------------
# Probe cache
# ---------------------------------------------------------------------------

_PROBE_CACHE: dict = {}


def reset_runtime_cache() -> None:
    """Clear the probe cache (test hook)."""
    _PROBE_CACHE.clear()


def _probe(afni_home=None) -> dict:
    """Probe installed versions and cache the result.

    Returns
    -------
    dict
        Keys: ``'afni'``, ``'python'``, ``'numpy'``, ``'pandas'``.
    """
    if _PROBE_CACHE:
        return _PROBE_CACHE

    logger = logging.getLogger(__name__)

    # Preflight: ensure all binaries are reachable
    preflight_tool_environments(afni_home, logger)

    # AFNI version
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
    except (subprocess.SubprocessError, OSError) as exc:
        raise ToolUnavailableError(
            f"AFNI version probe failed ({cmd!r}): {exc}"
        ) from exc

    afni_ver = _parse_afni_version(result.stdout, result.stderr)
    if afni_ver is None:
        raise ToolUnavailableError(
            "AFNI version could not be determined from 'afni -ver' output."
        )

    # Python version
    python_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    # numpy / pandas
    import numpy
    import pandas
    numpy_ver = numpy.__version__
    pandas_ver = pandas.__version__

    cached = {
        "afni": afni_ver,
        "python": python_ver,
        "numpy": numpy_ver,
        "pandas": pandas_ver,
    }
    _PROBE_CACHE.update(cached)
    return cached


# ---------------------------------------------------------------------------
# Runtime check
# ---------------------------------------------------------------------------

def runtime_check(logger=None, afni_home=None) -> dict:
    """Validate installed tools against the packaged lockfile.

    Minimum violations raise ``ToolVersionError``. Validated-version
    mismatches emit ``UNVALIDATED_VERSION`` graded warnings.

    Parameters
    ----------
    logger : logging.Logger, optional
    afni_home : str, optional
        Explicit AFNI home directory.

    Returns
    -------
    dict
        Provenance versions: ``{'package_version', 'afni_version',
        'python_version', 'numpy_version', 'pandas_version'}``.
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    lock = load_lockfile()
    probed = _probe(afni_home)
    tools = lock["tools"]

    # --- AFNI minimum and validated ---
    afni_min = tools["afni"]["minimum"]
    afni_val = tools["afni"]["validated"]
    afni_inst = probed["afni"]
    afni_inst_t = tuple(int(x) for x in afni_inst.split("."))
    afni_min_t = tuple(int(x) for x in afni_min.split("."))
    if afni_inst_t < afni_min_t:
        raise ToolVersionError(
            f"AFNI {afni_inst} is below the minimum {afni_min}."
        )
    if afni_inst != afni_val:
        graded_warning(
            logger, "medium", "UNVALIDATED_VERSION",
            f"AFNI {afni_inst} differs from the validated version {afni_val}; "
            "results are produced with an unvalidated version.",
            user_facing=True,
        )

    # --- Python minimum and validated ---
    py_min = tools["python"]["minimum"]
    py_val = tools["python"]["validated"]
    py_inst = probed["python"]
    py_inst_mm = tuple(int(x) for x in py_inst.split(".")[:2])
    py_min_mm = tuple(int(x) for x in py_min.split(".")[:2])
    if py_inst_mm < py_min_mm:
        raise ToolVersionError(
            f"Python {py_inst} is below the minimum {py_min}."
        )
    py_val_mm = tuple(int(x) for x in py_val.split(".")[:2])
    if py_inst_mm != py_val_mm:
        graded_warning(
            logger, "medium", "UNVALIDATED_VERSION",
            f"Python {py_inst} differs from the validated version {py_val}; "
            "results are produced with an unvalidated version.",
            user_facing=True,
        )

    # --- numpy / pandas minimum and validated ---
    for lib_name in ("numpy", "pandas"):
        lib_min = tools[lib_name]["minimum"]
        lib_val = tools[lib_name]["validated"]
        lib_inst = probed[lib_name]
        try:
            v_inst = Version(lib_inst)
            v_min = Version(lib_min)
            v_val = Version(lib_val)
        except InvalidVersion as e:
            raise ToolUnavailableError(
                f"{lib_name} version '{lib_inst}' is not a valid version: {e}"
            ) from e
        if v_inst < v_min:
            raise ToolVersionError(
                f"{lib_name} {lib_inst} is below the minimum {lib_min}."
            )
        if v_inst != v_val:
            graded_warning(
                logger, "medium", "UNVALIDATED_VERSION",
                f"{lib_name} {lib_inst} differs from the validated version "
                f"{lib_val}; results are produced with an unvalidated version.",
                user_facing=True,
            )

    # Provenance dict
    from fmri_first_level_proc import __version__
    return {
        "package_version": __version__,
        "afni_version": probed["afni"],
        "python_version": probed["python"],
        "numpy_version": probed["numpy"],
        "pandas_version": probed["pandas"],
    }
