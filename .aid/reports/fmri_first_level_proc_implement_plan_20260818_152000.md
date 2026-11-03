<implement_plan>
  <meta project="fmri_first_level_proc" mode="implement" submodule="plan" timestamp="2026-08-18T15:20:00-04:00" />
  <input_reports>
    <report path="fmri_first_level_proc_brainstorm_20260818_150000.md" mode="brainstorm" key_items="3" />
  </input_reports>
  <changes>
    <change id="C1" priority="P1" source_item="T1/A1: Exception base class context dict">
      <file path="fmri_first_level_proc/exceptions.py" action="modify" />
      <description>Add context: dict parameter to FmriFirstLevelError.__init__(). All six subclasses inherit the new signature automatically (none override __init__). All 123 existing raise sites are backward-compatible (context defaults to None, stored as {}).</description>
      <spec>
Replace the current bare class body:
```python
class FmriFirstLevelError(Exception):
    """Base exception for fmri-first-level-proc."""
```

With:
```python
class FmriFirstLevelError(Exception):
    """Base exception for fmri-first-level-proc."""

    def __init__(self, message: str = "", context: dict | None = None) -> None:
        super().__init__(message)
        self.context: dict = context if context is not None else {}
```

No changes to any subclass or raise site.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - additive, backward-compatible change; no downstream modifications needed</risk>
      <rollback>Revert exceptions.py to remove __init__ override; class reverts to bare Exception subclass.</rollback>
    </change>

    <change id="C2" priority="P1" source_item="T2/A1 + T3/A2: Lockfile value updates">
      <file path="tools.lock.yaml" action="modify" />
      <description>Replace AFNI PLACEHOLDER pin with 26.0.09 and add top-level python: "3.14.3" field.</description>
      <spec>
Replace the entire lockfile content:
```yaml
lockfile_version: "1.0.0"
python: "3.14.3"
binaries:
  AFNI: "26.0.09"
```

The `python` field is top-level (not under `binaries`), matching the orchestrator's schema. The `binaries` dict remains for tool-specific pins.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - declarative config file; no code logic changes</risk>
      <rollback>Restore AFNI to "PLACEHOLDER" and remove python field.</rollback>
    </change>

    <change id="C3" priority="P1" source_item="T3/A2: Python version validation in runtime.py">
      <file path="fmri_first_level_proc/runtime.py" action="modify" />
      <description>Add import sys. Restructure probe_tool_versions() to remove the early-return on AFNI PLACEHOLDER (replacing with if/else) so both the AFNI and Python checks run independently. Add Python minor-series validation block after the AFNI block. Update docstring to document both checks. Update the success log message to report the count of tools actually verified.</description>
      <spec>
1. Add `import sys` to the import block (after `import shutil`, before `import subprocess`, to maintain alphabetical order).

2. Replace probe_tool_versions() body (lines 145-189) with the restructured implementation:

```python
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
            raise ToolUnavailableError(
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
            raise ToolUnavailableError(
                f"Python: expected {pin_major}.{pin_minor}.x, "
                f"got {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            )

        tools_verified += 1

    if tools_verified > 0:
        logger.info("Startup version probe passed: %d pinned tool(s) verified.", tools_verified)
```

3. Update the docstring (lines 122-143) to document both checks:

```python
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
        If any checked tool's version does not match its pin, is unparseable,
        or the tool binary is unreachable.
    """
```
      </spec>
      <dependencies>C2 (lockfile must contain the python field for the check to be non-trivially exercised, though the code handles its absence gracefully)</dependencies>
      <risk>low - restructuring the AFNI block from early-return to if/else preserves identical behavior for all existing code paths; the Python check is additive</risk>
      <rollback>Revert runtime.py; remove import sys, restore early-return pattern, remove Python check block.</rollback>
    </change>

    <change id="C4" priority="P2" source_item="T3/A2: Generalize lockfile-absent warning message">
      <file path="fmri_first_level_proc/run_first_level.py" action="modify" />
      <description>Generalize the graded_warning message at the lockfile-absent code path from "skipping AFNI version pinning" to "skipping version pinning" since the lockfile now covers both AFNI and Python.</description>
      <spec>
At line 144, change:
```python
f"tools.lock.yaml not found at {_LOCKFILE_PATH}; skipping AFNI version pinning.",
```
to:
```python
f"tools.lock.yaml not found at {_LOCKFILE_PATH}; skipping version pinning.",
```
      </spec>
      <dependencies>none</dependencies>
      <risk>low - string change only</risk>
      <rollback>Restore "AFNI version pinning" wording.</rollback>
    </change>
  </changes>
  <execution_order>C1, C2, C3, C4 (C1 and C2 are independent; C3 logically follows C2; C4 is independent)</execution_order>
</implement_plan>
