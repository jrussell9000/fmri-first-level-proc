<implement_plan>
  <meta project="fmri-first-level-proc" mode="implement" submodule="plan" timestamp="2026-08-25T19:00:18Z" />
  <input_reports>
    <report path="fmri-first-level-proc_brainstorm_20260825_185436.md" mode="brainstorm" key_items="6" />
  </input_reports>
  <changes>

    <!-- ================================================================== -->
    <!-- C1: Warning accumulator in first_level_utils.py                    -->
    <!-- ================================================================== -->
    <change id="C1" priority="P1" source_item="T1">
      <file path="fmri_first_level_proc/first_level_utils.py" action="modify" />
      <description>Add module-level warning accumulator with get/clear API. Have graded_warning() append to the accumulator in addition to returning its dict.</description>
      <spec>
After the CENSOR_HIGH_THRESHOLD constant (line 56), add:

```python
_WARNING_ACCUMULATOR: list[dict] = []

def get_warnings() -> list[dict]:
    return list(_WARNING_ACCUMULATOR)

def clear_warnings() -> None:
    _WARNING_ACCUMULATOR.clear()
```

Modify graded_warning() (line 225): after building the return dict (line 264), append it to _WARNING_ACCUMULATOR before the return statement:

```python
    record = {
        "severity": severity,
        "code": code,
        "message": message,
        "user_facing": user_facing,
    }
    _WARNING_ACCUMULATOR.append(record)
    return record
```

Update the docstring Notes section (lines 257-260) to reflect that graded_warning() now both appends to the module-level accumulator AND returns the dict (backward compatible for callers that still use the return value).
      </spec>
      <dependencies>none</dependencies>
      <risk>low - additive change; existing return value preserved for backward compatibility</risk>
      <rollback>Remove _WARNING_ACCUMULATOR, get_warnings(), clear_warnings(); revert graded_warning() to its current form.</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C2: Update __init__.py exports for warning accumulator             -->
    <!-- ================================================================== -->
    <change id="C2" priority="P1" source_item="T1">
      <file path="fmri_first_level_proc/__init__.py" action="modify" />
      <description>Export get_warnings and clear_warnings from the package public API.</description>
      <spec>
Add get_warnings and clear_warnings to the import from first_level_utils (line 13):

```python
from .first_level_utils import setup_logging, FirstLevelResult, graded_warning, get_warnings, clear_warnings
```

Add both to __all__ (line 16):

```python
__all__ = [
    'load_and_validate', 'ResolvedConfig',
    'setup_logging', 'FirstLevelResult', 'graded_warning',
    'get_warnings', 'clear_warnings',
    'DISPATCH', '__version__',
]
```
      </spec>
      <dependencies>C1</dependencies>
      <risk>low - additive export</risk>
      <rollback>Remove the two new names from the import and __all__.</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C3: Update pipeline entry points to use warning accumulator        -->
    <!-- ================================================================== -->
    <change id="C3" priority="P1" source_item="T1">
      <file path="fmri_first_level_proc/task_act_first_level.py" action="modify" />
      <file path="fmri_first_level_proc/task_conn_first_level.py" action="modify" />
      <file path="fmri_first_level_proc/rest_conn_first_level.py" action="modify" />
      <description>In each pipeline's run() function: (a) import get_warnings and clear_warnings, (b) call clear_warnings() at entry, (c) replace the local warnings list with get_warnings() at FirstLevelResult construction, (d) remove the local _warnings/warnings list variable and all .append(graded_warning(...)) patterns in favor of bare graded_warning() calls (the accumulator handles collection).</description>
      <spec>
**task_act_first_level.py:**
- Add to imports (from .first_level_utils): get_warnings, clear_warnings
- In run() (line 472): after `config = copy.copy(config)` (line 530), insert `clear_warnings()`. Remove `_warnings: list[dict] = []` (line 531).
- Every `_warnings.append(graded_warning(...))` call (lines 629, 642, 727) becomes a bare `graded_warning(...)` call (drop the `_warnings.append()` wrapper).
- At FirstLevelResult construction (line 766): change `warnings=_warnings` to `warnings=get_warnings()`.
- At the status check (line 764): change `any(w.get("severity") == "high" for w in _warnings)` to `any(w.get("severity") == "high" for w in get_warnings())`.

**task_conn_first_level.py:**
- Add to imports: get_warnings, clear_warnings
- In run() (line 560): after `config = copy.copy(config)` (line 607), insert `clear_warnings()`. Remove `warnings: list[dict] = []` (line 608).
- Every `warnings.append(graded_warning(...))` call becomes a bare `graded_warning(...)` call.
- At FirstLevelResult construction: change `warnings=warnings` to `warnings=get_warnings()`.
- At the status check: use `get_warnings()` instead of the local list.

**rest_conn_first_level.py:**
- Add to imports: get_warnings, clear_warnings
- In run() (line 559): after `config = copy.copy(config)` (line 609), insert `clear_warnings()`. Remove `warnings: list[dict] = []` (line 610).
- `warnings.append(graded_warning(...))` calls (e.g., lines 634, 734) become bare `graded_warning(...)` calls.
- `warnings.extend(residual_warnings)` (line 706): gen_residual_ts() internally calls graded_warning() which already appends to the accumulator, so remove this line. Also remove the `residual_warnings` return value from the gen_residual_ts() call site; the function's return signature will need to drop the warnings list (it currently returns `(per_run_dof, warnings)`). Instead, gen_residual_ts should return only per_run_dof; its internal graded_warning() calls will accumulate automatically.
- At FirstLevelResult construction: change `warnings=warnings` to `warnings=get_warnings()`.
- At the status check: use `get_warnings()` instead of the local list.

**rest_conn gen_residual_ts() return signature change:** The function currently returns `tuple[dict, list[dict]]` where the second element is the accumulated warnings list. Since graded_warning() now auto-accumulates, change the return to `dict` (just per_run_dof). Update the call site in run() accordingly. The internal `run_warnings: list[dict]` variable and its `.append()` calls inside gen_residual_ts() should be removed; the bare graded_warning() calls replace them.
      </spec>
      <dependencies>C1</dependencies>
      <risk>medium - touches all three pipeline entry points; must verify that all graded_warning() call sites in intermediate functions (not just run()) also accumulate correctly. Key concern: gen_residual_ts() return signature change in rest_conn.</risk>
      <rollback>Restore local warnings lists, .append() wrappers, and gen_residual_ts() return signature.</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C4: ToolVersionError exception class                                -->
    <!-- ================================================================== -->
    <change id="C4" priority="P1" source_item="T2">
      <file path="fmri_first_level_proc/exceptions.py" action="modify" />
      <description>Add ToolVersionError subclass distinguishing version mismatch from binary-absent.</description>
      <spec>
After ToolUnavailableError (line 20-21), add:

```python
class ToolVersionError(FmriFirstLevelError):
    """External tool binary found but version does not match the lockfile pin."""
```

Update ToolUnavailableError docstring (line 21) from "External tool binary not found on PATH or version mismatch." to "External tool binary not found on PATH."
      </spec>
      <dependencies>none</dependencies>
      <risk>low - additive class; docstring-only change to existing class</risk>
      <rollback>Remove ToolVersionError; restore ToolUnavailableError docstring.</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C5: Update runtime.py to raise ToolVersionError                    -->
    <!-- ================================================================== -->
    <change id="C5" priority="P1" source_item="T2">
      <file path="fmri_first_level_proc/runtime.py" action="modify" />
      <description>Import ToolVersionError and raise it (instead of ToolUnavailableError) at version-mismatch sites.</description>
      <spec>
Update import (line 12):
```python
from .exceptions import ToolUnavailableError, ToolVersionError
```

Change the following raise sites from ToolUnavailableError to ToolVersionError:
- Line 192: `raise ToolUnavailableError(f"AFNI: expected {expected_afni}, got {actual_afni}")` -> `raise ToolVersionError(f"AFNI: expected {expected_afni}, got {actual_afni}")`
- Line 218: `raise ToolUnavailableError(f"Python: expected {pin_major}.{pin_minor}.x, ...")` -> `raise ToolVersionError(f"Python: expected {pin_major}.{pin_minor}.x, ...")`

Retain ToolUnavailableError at:
- Line 180: probe command failed (binary may be absent or broken)
- Line 187: version not parseable (binary exists but output unreadable)
- Lines 206, 213: malformed lockfile pin string (configuration error, not a runtime version mismatch; these are edge cases where the lockfile itself is invalid, and ToolUnavailableError is the conservative classification)
      </spec>
      <dependencies>C4</dependencies>
      <risk>low - two raise-site changes with clear semantics</risk>
      <rollback>Revert both raise sites to ToolUnavailableError; remove ToolVersionError import.</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C6: Update run_first_level.py exit code mapping for ToolVersionError -->
    <!-- ================================================================== -->
    <change id="C6" priority="P1" source_item="T2">
      <file path="fmri_first_level_proc/run_first_level.py" action="modify" />
      <description>Add ToolVersionError to the exit-code-4 exception handler alongside ToolUnavailableError and ToolExecutionError.</description>
      <spec>
Update import (line 73-80): add ToolVersionError:
```python
from .exceptions import (
    ConfigError,
    InputError,
    ModelError,
    GuardError,
    ToolUnavailableError,
    ToolExecutionError,
    ToolVersionError,
)
```

Update the except clause (line 208): add ToolVersionError to the tuple:
```python
    except (ToolUnavailableError, ToolVersionError, ToolExecutionError) as e:
        logger.error(str(e)); sys.exit(4)
```

Update the docstring exit codes section (lines 24-31): add ToolVersionError to the exit code 4 description:
```
4 : External tool unavailable, version mismatch, or failed (ToolUnavailableError, ToolVersionError, ToolExecutionError).
```
      </spec>
      <dependencies>C4</dependencies>
      <risk>low - additive to existing exception handler tuple</risk>
      <rollback>Remove ToolVersionError from import, except clause, and docstring.</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C7: Add scale_to_psc() utility to first_level_utils.py             -->
    <!-- ================================================================== -->
    <change id="C7" priority="P1" source_item="T3">
      <file path="fmri_first_level_proc/first_level_utils.py" action="modify" />
      <description>Add scale_to_psc() shared utility function that performs percent signal change scaling on a 4D NIfTI using AFNI's 3dTstat and 3dcalc.</description>
      <spec>
Add the function after gen_min_outlier_epi() (after line ~1410, i.e., after that function ends). The function signature and logic:

```python
def scale_to_psc(scan_path, out_dir, out_file_pre, label, logger):
    """Scale a 4D NIfTI to percent signal change (PSC).

    Computes the voxelwise temporal mean via 3dTstat, then divides each
    voxel's time series by its mean and multiplies by 100, with a 200%
    ceiling and zero-guard via step functions. This is the standard AFNI
    PSC transformation: min(200, a/b*100)*step(a)*step(b).

    Parameters
    ----------
    scan_path : str
        Path to the input 4D NIfTI.
    out_dir : str
        Output directory.
    out_file_pre : str
        Output filename prefix.
    label : str
        Descriptive label appended to filenames. Use "" for task pipelines
        (single concatenated scan) or "run1", "run2", etc. for rest_conn.
    logger : logging.Logger

    Returns
    -------
    str
        Path to the PSC-scaled 4D NIfTI.
    """
    if label:
        mean_name = f"{out_file_pre}_{label}_mean.nii.gz"
        psc_name = f"{out_file_pre}_{label}_psc.nii.gz"
    else:
        mean_name = f"{out_file_pre}_mean.nii.gz"
        psc_name = f"{out_file_pre}_psc.nii.gz"
    mean_path = os.path.join(out_dir, mean_name)
    psc_path = os.path.join(out_dir, psc_name)

    if os.path.exists(psc_path):
        logger.info("PSC-scaled file already exists: %s", psc_path)
        return psc_path

    # Compute voxelwise temporal mean
    run_afni_command(
        ["3dTstat", "-mean", "-prefix", mean_path, scan_path],
        description="3dTstat temporal mean for PSC scaling",
        logger=logger,
    )

    # Scale to PSC: min(200, a/b*100)*step(a)*step(b)
    run_afni_command(
        ["3dcalc",
         "-a", scan_path,
         "-b", mean_path,
         "-expr", "min(200,a/b*100)*step(a)*step(b)",
         "-prefix", psc_path],
        description="3dcalc PSC scaling",
        logger=logger,
    )

    logger.info("PSC-scaled scan written to %s", psc_path)
    return psc_path
```

The mean file is an intermediate output (retained for QC). The PSC file is the primary output, used as the input to subsequent regression steps.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - new function with no impact on existing code paths until integrated</risk>
      <rollback>Remove the function.</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C8: Add 3dTstat to AFNI binary preflight list                      -->
    <!-- ================================================================== -->
    <change id="C8" priority="P1" source_item="T3">
      <file path="fmri_first_level_proc/runtime.py" action="modify" />
      <description>Add 3dTstat to _AFNI_BINARIES so the preflight check verifies its availability.</description>
      <spec>
Add "3dTstat" to the _AFNI_BINARIES list (line 15-30). Insert it alphabetically among the 3d-prefixed tools, e.g., after "3dTproject":

```python
_AFNI_BINARIES: list[str] = [
    "3dDeconvolve",
    "3dTproject",
    "3dTstat",       # <-- new
    "3dBandpass",
    ...
]
```

Update the comment on line 14 to reflect the new count: "15 binaries" (was "14 binaries").
      </spec>
      <dependencies>none</dependencies>
      <risk>low - additive to preflight list; 3dTstat is a core AFNI utility always present in AFNI installations</risk>
      <rollback>Remove "3dTstat" from the list; revert comment count.</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C9: Add scale_to_psc config field                                  -->
    <!-- ================================================================== -->
    <change id="C9" priority="P1" source_item="T3">
      <file path="fmri_first_level_proc/first_level_config.py" action="modify" />
      <description>Add scale_to_psc boolean field to ResolvedConfig (default True) and wire it through validate_config() and resolve_config().</description>
      <spec>
**ResolvedConfig (line 84):** Add after the template_path field (line 106):
```python
    scale_to_psc: bool = True
```

**validate_config():** No validation needed beyond type checking (bool). The YAML key `scale_to_psc` lives at the analysis block level (not inside extraction or connectivity). If present and not a bool, raise ConfigError.

**resolve_config() (line 573):** In each analysis type branch (task_act at line 634, task_conn at line 668, rest_conn at line 703), read the block-level value:
```python
    cfg.scale_to_psc = bool(validated_block.get("scale_to_psc", True))
```

This defaults to True when absent from the YAML, consistent with the brainstorm decision.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - new field with sensible default; no existing code reads it until C10</risk>
      <rollback>Remove the field from ResolvedConfig and the resolution logic.</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C10: Integrate PSC scaling into all three pipelines                 -->
    <!-- ================================================================== -->
    <change id="C10" priority="P1" source_item="T3">
      <file path="fmri_first_level_proc/task_act_first_level.py" action="modify" />
      <file path="fmri_first_level_proc/task_conn_first_level.py" action="modify" />
      <file path="fmri_first_level_proc/rest_conn_first_level.py" action="modify" />
      <description>Call scale_to_psc() at the correct pipeline position (after min-outlier EPI, before regression) in all three pipelines. When enabled, subsequent steps use the PSC-scaled scan instead of the raw scan. Add the PSC output path to the output_files list.</description>
      <spec>
**task_act_first_level.py:**
- Import scale_to_psc from first_level_utils.
- After gen_min_outlier_epi (line 608), before create_censor_file (line 611):
```python
    if config.scale_to_psc:
        psc_path = scale_to_psc(
            config.scan_path, config.out_dir, config.out_file_pre, "", logger)
        config.scan_path = psc_path
```
- In the output_files collection section (after line 744), add:
```python
    psc_path = os.path.join(config.out_dir, f"{config.out_file_pre}_psc.nii.gz")
    if os.path.exists(psc_path):
        output_files.append(psc_path)
```

**task_conn_first_level.py:**
- Import scale_to_psc from first_level_utils.
- After gen_min_outlier_epi (line 662), before create_censor_file (line 664):
```python
    if config.scale_to_psc:
        psc_path = scale_to_psc(
            config.scan_path, config.out_dir, config.out_file_pre, "", logger)
        config.scan_path = psc_path
```
- Add PSC path to output_files collection.

**rest_conn_first_level.py:**
- Import scale_to_psc from first_level_utils.
- After the gen_min_outlier_epi per-run loop (line 665-666), before the extract_raw_ptseries block (line 668):
```python
    if config.scale_to_psc:
        for i, scan in enumerate(config.scan_paths):
            psc_path = scale_to_psc(
                scan, config.out_dir, config.out_file_pre, f"run{i+1}", logger)
            config.scan_paths[i] = psc_path
```
Note: config.scan_paths is already a mutable list since config = copy.copy(config) (line 609) performs a shallow copy. The list object is shared with the original, so we need config.scan_paths = list(config.scan_paths) before mutating. Add this line before the PSC loop.
- Add per-run PSC paths to output_files collection.
      </spec>
      <dependencies>C7, C9</dependencies>
      <risk>medium - modifies the critical scan_path variable that feeds into all downstream processing. The copy.copy + list() pattern for rest_conn ensures the original config is not mutated. The "already exists" guard in scale_to_psc() provides idempotency.</risk>
      <rollback>Remove the PSC scaling blocks and scan_path reassignment in all three files.</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C11: Replace extraction config fields with stat_buckets            -->
    <!-- ================================================================== -->
    <change id="C11" priority="P1" source_item="T4">
      <file path="fmri_first_level_proc/first_level_config.py" action="modify" />
      <description>Replace extract/extract_labels/extract_stat with stat_buckets in ResolvedConfig. Replace VALID_STAT_TYPES with VALID_STAT_BUCKET_TYPES. Update validate_config() and resolve_config().</description>
      <spec>
**Constants (line 63):** Replace:
```python
VALID_STAT_TYPES = {"z", "t", "r"}
```
with:
```python
VALID_STAT_BUCKET_TYPES = {"Coef", "Tstat", "Fstat", "R^2", "Zstat"}
```

**ResolvedConfig (line 84):** Replace the task_act extraction fields (lines 131-137):
```python
    # task_act extraction
    extract: bool = False
    extract_labels: list[str] | None = None
    extract_stat: str | None = None
    extract_out_file_pre: str | None = None
    extract_resids: bool = False
    extract_raw_ptseries: bool = False
```
with:
```python
    # task_act extraction
    stat_buckets: list[str] | None = None
    extract_out_file_pre: str | None = None
    extract_resids: bool = False
    extract_raw_ptseries: bool = False
```

**validate_config() extraction block (lines 502-537):** For task_act (lines 505-519), replace the extract/extract_labels/extract_stat validation:
```python
            if atype == "task_act":
                stat_buckets = ext.get("stat_buckets")
                if stat_buckets is not None:
                    if not isinstance(stat_buckets, list) or not stat_buckets:
                        _cfg_err(logger,
                                 "[%s] extraction.stat_buckets must be a non-empty list.", label)
                    for sb in stat_buckets:
                        if sb not in VALID_STAT_BUCKET_TYPES:
                            _cfg_err(logger,
                                     "[%s] extraction.stat_buckets contains invalid type '%s'. "
                                     "Must be one of %s.", label, sb, VALID_STAT_BUCKET_TYPES)
                    if "extract_out_file_pre" not in ext:
                        _cfg_err(logger,
                                 "[%s] extraction block missing 'extract_out_file_pre' for task_act "
                                 "when stat_buckets is set.", label)
                if ext.get("extract_raw_ptseries", False) and "extract_out_file_pre" not in ext:
                    _cfg_err(logger,
                             "[%s] extraction block missing 'extract_out_file_pre' for task_act "
                             "when extract_raw_ptseries=true.", label)
```

**resolve_config() task_act extraction block (lines 654-666):** Replace:
```python
        if extraction is not None:
            cfg.stat_buckets = extraction.get("stat_buckets", None)
            cfg.extract_raw_ptseries = bool(extraction.get("extract_raw_ptseries", False))
            if cfg.stat_buckets is not None:
                cfg.extract_out_file_pre = extraction.get("extract_out_file_pre")
                cfg.extract_resids = bool(extraction.get("extract_resids", False))
            else:
                cfg.extract_out_file_pre = (
                    extraction.get("extract_out_file_pre") if cfg.extract_raw_ptseries else None
                )
```
      </spec>
      <dependencies>none</dependencies>
      <risk>medium - breaking change to config schema; existing YAML configs using extract/extract_labels/extract_stat will fail validation. This is intentional per brainstorm decision.</risk>
      <rollback>Restore the original fields and validation logic.</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C12: Implement stat bucket extraction in task_act                   -->
    <!-- ================================================================== -->
    <change id="C12" priority="P1" source_item="T4">
      <file path="fmri_first_level_proc/task_act_first_level.py" action="modify" />
      <description>Replace extract_effects() with extract_stat_buckets(). The new function: (a) queries 3dinfo -subbrick_info to discover available sub-bricks, (b) for each requested stat type, extracts all matching sub-bricks into a single NIfTI via 3dbucket, (c) writes a JSON index mapping condition/contrast labels to sub-brick indices, (d) optionally writes a parcellated CSV when template_path is available. Retain extract_resids as a separate block. Update run() to call the new function.</description>
      <spec>
**Replace extract_effects (lines 344-470) with extract_stat_buckets:**

```python
def extract_stat_buckets(config: ResolvedConfig, logger: logging.Logger) -> list[str]:
    """Extract stat-type-based bucket outputs from the 3dDeconvolve bucket dataset.

    For each stat type in config.stat_buckets, this function:
    1. Discovers all sub-bricks matching that stat type via 3dinfo -subbrick_info.
    2. Extracts them into a single multi-sub-brick NIfTI via 3dbucket.
    3. Writes a JSON index mapping condition/contrast labels to sub-brick indices.
    4. When template_path is available and not 'WB', writes a parcellated CSV
       (rows = conditions/contrasts, columns = ROIs).

    For Zstat: finds Tstat sub-bricks, converts each to Z via 3dcalc fitt_t2z(),
    then assembles the Z volumes into the bucket.

    Parameters
    ----------
    config : ResolvedConfig
        Must include: out_dir, out_file_pre, stat_buckets, extract_out_file_pre,
        template_path, average_type, extract_resids.
    logger : logging.Logger

    Returns
    -------
    list[str]
        Paths of all output files created.
    """
    bucket_path = f"{config.out_dir}/{config.out_file_pre}_concat_bucket_stats.nii.gz"
    output_files = []

    # Get subbrik info
    bucket_info = run_afni_command(
        ['3dinfo', '-subbrick_info', bucket_path],
        capture_output=True,
        description="3dinfo subbrick_info for stat bucket extraction",
        logger=logger,
    )
    bucket_split = bucket_info.split()

    # Discover available stat types and log for user awareness
    available_stats = set()
    for token in bucket_split:
        for st in ("Coef", "Tstat", "Fstat", "R^2"):
            if st in token:
                available_stats.add(st)
    if any("Tstat" in token for token in bucket_split):
        available_stats.add("Zstat")  # synthetic, derivable from Tstat
    logger.info("Available stat types in bucket: %s", sorted(available_stats))

    for stat_type in config.stat_buckets:
        # Determine which sub-brick suffix to search for
        search_stat = "Tstat" if stat_type == "Zstat" else stat_type
        need_t2z = (stat_type == "Zstat")

        # Collect all matching sub-bricks
        matched = []  # list of (label, subbrik_index)
        for i, token in enumerate(bucket_split):
            if search_stat in token and "#" in token:
                # Parse the label: e.g., "condName#0_Tstat" -> "condName"
                label_part = token.split("#")[0]
                try:
                    idx = int(bucket_split[i - 1][1:])
                    matched.append((label_part, idx))
                except (ValueError, IndexError):
                    continue

        if not matched:
            logger.warning(
                "No sub-bricks found for stat type '%s' in %s. Skipping.",
                stat_type, bucket_path)
            continue

        logger.info("Found %d sub-bricks for stat type '%s': %s",
                    len(matched), stat_type, [m[0] for m in matched])

        # Build output paths
        bucket_out = os.path.join(
            config.out_dir,
            f"{config.extract_out_file_pre}_{stat_type}_bucket.nii.gz")
        index_out = os.path.join(
            config.out_dir,
            f"{config.extract_out_file_pre}_{stat_type}_index.json")

        if not os.path.exists(bucket_out):
            if need_t2z:
                # Convert each T sub-brick to Z, collect temp files
                z_vols = []
                for label, idx in matched:
                    aux_params = _get_subbrik_stat_aux(bucket_path, idx, logger=logger)
                    if not aux_params:
                        raise GuardError(
                            f"Could not retrieve DOF for sub-brick {idx} ({label}) in "
                            f"{bucket_path}; cannot convert T to Z.")
                    dof = int(aux_params[0])
                    z_tmp = os.path.join(
                        config.out_dir,
                        f"{config.out_file_pre}_{label}_zconv_tmp.nii.gz")
                    run_afni_command(
                        ["3dcalc", "-a", f"{bucket_path}[{idx}]",
                         "-expr", f"fitt_t2z(a,{dof})",
                         "-prefix", z_tmp],
                        description=f"T-to-Z conversion for {label}",
                        logger=logger)
                    z_vols.append(z_tmp)

                # Assemble Z volumes into bucket
                bucket_cmd = ["3dbucket", "-prefix", bucket_out] + z_vols
                run_afni_command(bucket_cmd,
                    description=f"3dbucket assemble {stat_type} bucket",
                    logger=logger)

                # Clean up temp Z files
                for zv in z_vols:
                    if os.path.exists(zv):
                        os.remove(zv)
            else:
                # Direct extraction via 3dbucket
                sub_brik_selectors = [f"{bucket_path}[{idx}]" for _, idx in matched]
                bucket_cmd = ["3dbucket", "-prefix", bucket_out] + sub_brik_selectors
                run_afni_command(bucket_cmd,
                    description=f"3dbucket extract {stat_type} bucket",
                    logger=logger)

            if not os.path.exists(bucket_out):
                raise ToolExecutionError(
                    f"Failed to create {stat_type} bucket: {bucket_out}")
            logger.info("Created %s bucket: %s", stat_type, bucket_out)
        else:
            logger.info("%s bucket already exists: %s", stat_type, bucket_out)

        output_files.append(bucket_out)

        # Write JSON index (label -> sub-brick index in the NEW bucket, 0-based)
        index_map = {label: i for i, (label, _) in enumerate(matched)}
        with open(index_out, "w") as f:
            json.dump(index_map, f, indent=2)
        output_files.append(index_out)
        logger.info("Wrote %s index: %s", stat_type, index_out)

        # Parcellated CSV when template is available and not whole-brain
        if config.template_path is not None and config.template_path != "WB":
            csv_out = os.path.join(
                config.out_dir,
                f"{config.extract_out_file_pre}_{stat_type}_parcellated.csv")
            if not os.path.exists(csv_out):
                rows = {}
                for new_idx, (label, _) in enumerate(matched):
                    roi_df = extract_roi_stats(
                        f"{bucket_out}[{new_idx}]",
                        config.template_path, config.average_type, logger=logger)
                    rows[label] = roi_df.iloc[0]
                parcellated_df = pd.DataFrame(rows).T
                parcellated_df.index.name = "condition"
                parcellated_df.to_csv(csv_out)
                logger.info("Wrote %s parcellated CSV: %s", stat_type, csv_out)
            else:
                logger.info("%s parcellated CSV already exists: %s", stat_type, csv_out)
            output_files.append(csv_out)

    # Extract residuals (separate toggle)
    if config.extract_resids:
        resid_path = f"{config.out_dir}/{config.out_file_pre}_concat_bucket_resids.nii.gz"
        resid_csv = f"{config.out_dir}/{config.extract_out_file_pre}_resids.csv"
        if not os.path.exists(resid_csv):
            resid_df = extract_roi_stats(
                resid_path, config.template_path, config.average_type, logger=logger)
            resid_df.to_csv(resid_csv)
            if os.path.exists(resid_csv):
                logger.info("Extracted residuals to %s", resid_csv)
            else:
                raise ToolExecutionError("Could not extract residuals using ROI template.")
        output_files.append(resid_csv)

    return output_files
```

**Update run() (lines 472-773):**
- Remove the `_find_subbrik_index` function (lines 280-305) -- retained; still used internally by extract_stat_buckets via inline logic. Actually, the new function uses its own inline parsing. _find_subbrik_index and _get_subbrik_stat_aux can be kept as private utilities: _get_subbrik_stat_aux is still used by extract_stat_buckets for T-to-Z DOF lookup.
- Change the extraction call (line 737-738) from:
```python
    if config.extract:
        extract_effects(config, logger)
```
to:
```python
    extraction_files = []
    if config.stat_buckets:
        extraction_files = extract_stat_buckets(config, logger)
```
- Update output_files collection (lines 744-758): replace the per-label file collection with:
```python
    output_files.extend(extraction_files)
```
Remove the old per-label extraction file collection loop.
- _find_subbrik_index (lines 280-305) may be removed since the new function handles sub-brick discovery internally. However, keep _get_subbrik_stat_aux (lines 308-341) as it is still used by the T-to-Z conversion path within extract_stat_buckets.
      </spec>
      <dependencies>C11</dependencies>
      <risk>medium - complete replacement of the extraction pipeline; the new function's sub-brick parsing logic must correctly handle all AFNI sub-brick label formats. _get_subbrik_stat_aux is preserved for T-to-Z DOF retrieval.</risk>
      <rollback>Restore extract_effects() and the old run() extraction call.</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C13: Update example_config.yaml                                     -->
    <!-- ================================================================== -->
    <change id="C13" priority="P1" source_item="T3/T4">
      <file path="example_config.yaml" action="modify" />
      <description>Update the example config to reflect the new scale_to_psc field and the stat_buckets-based extraction schema.</description>
      <spec>
**Add scale_to_psc to each analysis block.** Insert after the censor_prev_tr line in each block:
```yaml
    scale_to_psc: true             # true = scale to percent signal change before regression (default: true)
```

**Update task_act extraction block (lines 79-85).** Replace:
```yaml
    extraction:
      extract: true
      extract_labels: ["stimFear", "stimSad", "Fear-Neutral", "Sad-Neutral"]
      extract_stat: "z"
      extract_out_file_pre: "subj001_nback_baseline_Shen368"
      extract_resids: false
      extract_raw_ptseries: false
```
with:
```yaml
    extraction:
      stat_buckets: ["Tstat", "Coef"]    # Stat types to extract as bucket outputs. Valid: Coef, Tstat, Fstat, R^2, Zstat
      extract_out_file_pre: "subj001_nback_baseline_Shen368"
      extract_resids: false              # true = extract residuals (parcellated CSV)
      extract_raw_ptseries: false        # true = extract pre-regression parcellated time series
```
      </spec>
      <dependencies>C9, C11</dependencies>
      <risk>low - documentation/example file only</risk>
      <rollback>Restore original extraction block and remove scale_to_psc.</rollback>
    </change>

  </changes>
  <execution_order>C1, C2, C4, C7, C8, C9, C11, C3, C5, C6, C10, C12, C13</execution_order>
</implement_plan>
