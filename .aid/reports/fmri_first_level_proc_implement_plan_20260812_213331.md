<implement_plan>
  <meta project="fmri_first_level_proc" mode="implement" submodule="plan" timestamp="2026-08-12T21:33:32Z" />
  <input_reports>
    <report path="fmri_first_level_proc_brainstorm_20260812_181523.md" mode="brainstorm" key_items="12" />
  </input_reports>

  <gate1_resolution>
    Gate 1 scan of the brainstorm report found one deferred item requiring resolution:

    **Deferred item (P1 implement):** "Finalize BIDS entity naming conventions during /implement based on BIDS-Derivatives and BIDS-Stats Model specifications." This was explicitly deferred from brainstorm per the upstream TODO instruction.

    **Resolution:** BIDS entity naming conventions are fully specified in C10 below, derived from BIDS-Derivatives (v1.8+), BIDS-Stats Model (BEP002) proposals, and the brainstorm's user-chosen `conn_mat` suffix (normalized to `connmat` for BIDS underscore-separator compliance). Two additional implementation-level details were resolved by codebase analysis: (a) complete AFNI binary list verified by grepping all pipeline modules (14 binaries, specified in C5); (b) complete graded_warning code list enumerated from all warning-worthy sites (11 codes, specified in C2).

    No conditional gates, pending markers, or unapproved assumptions remain. Gate 1: PASS.
  </gate1_resolution>

  <scope_summary>
    14 changes across 13 files (5 new, 8 modified). Total sys.exit(1) replacement: 123 sites across 6 modules. 4 new Python modules (exceptions.py, runtime.py, checkpoint.py, bids.py), 1 new lockfile (tools.lock.yaml).
  </scope_summary>

  <changes>

    <!-- ================================================================== -->
    <!-- C1: Exception Hierarchy (T3a)                                      -->
    <!-- ================================================================== -->
    <change id="C1" priority="P0" source_item="T3/AI-3">
      <file path="fmri_first_level_proc/exceptions.py" action="create" />
      <description>Create the custom exception hierarchy replacing all ~123 sys.exit(1) calls. FmriFirstLevelError base with 6 subclasses, each mapping to a specific exit code in main().</description>
      <spec>
```python
class FmriFirstLevelError(Exception):
    """Base exception for fmri-first-level-proc."""

class ConfigError(FmriFirstLevelError):
    """Invalid config: missing required fields, incompatible options, schema violations."""

class InputError(FmriFirstLevelError):
    """Input file missing, malformed, wrong dimensions, or unreadable."""

class ToolUnavailableError(FmriFirstLevelError):
    """External tool binary not found on PATH or version mismatch."""

class ToolExecutionError(FmriFirstLevelError):
    """External tool command returned non-zero or failed to produce expected output."""

class ModelError(FmriFirstLevelError):
    """Data quality prevents model estimation: singularity, insufficient DOF, no surviving trials."""

class GuardError(FmriFirstLevelError):
    """Pipeline invariant violation: unexpected state indicating a bug."""
```

Exit code mapping (enforced in main() only, see C9):
| Exception | Exit Code | Semantics |
|---|---|---|
| (none, no high warnings) | 0 | clean success |
| (none, high warnings) | 3 | success with significant QC concerns |
| ConfigError, InputError | 2 | user-correctable input problem |
| ModelError | 5 | data quality issue, skip subject |
| ToolUnavailableError, ToolExecutionError | 4 | external tool failure |
| GuardError | 1 | pipeline bug, halt batch |

Special rule: "AFNI produced output but it has unexpected format" (wrong dimensions, unexpected column count, unparseable output from a command that returned exit 0) is GuardError (invariant violation), not ToolExecutionError.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - new file, no existing code modified</risk>
      <rollback>delete exceptions.py</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C3: Config Pipeline + ResolvedConfig (T5)                          -->
    <!-- ================================================================== -->
    <change id="C3" priority="P0" source_item="T5/AI-5, T3/AI-3 (config sys.exit)">
      <file path="fmri_first_level_proc/first_level_config.py" action="modify" />
      <description>Replace argparse.Namespace with ResolvedConfig typed dataclass. Refactor config pipeline to 3-stage (load_config, validate_config, resolve_config). Replace all 37 sys.exit(1) with ConfigError/InputError. Expose load_and_validate() -> list[ResolvedConfig].</description>
      <spec>
**ResolvedConfig dataclass** (flat, all pipeline-specific fields Optional):

```python
@dataclasses.dataclass
class ResolvedConfig:
    # Schema and identity
    schema_version: str       # "3.0.0", additive-growth policy
    analysis_type: str        # "task_act" | "task_conn" | "rest_conn"
    analysis_name: str | None = None

    # Common
    out_dir: str = ""
    out_file_pre: str = ""
    tr: float = 0.0
    fd_threshold: float = 0.0
    average_type: str = ""
    num_cores: int = 1
    remove_previous: bool = False
    censor_prev_tr: bool = False
    template_path: str | None = None
    force_diff_atlas: bool = False

    # BIDS discovery (optional)
    derivatives_dirs: list[str] | None = None

    # Task-common (task_act + task_conn)
    scan_path: str | None = None
    task_timing_path: str | None = None
    motion_path: str | None = None
    hrf_model: str | None = None
    custom_hrf: str | None = None
    CSF_path: str | None = None
    WM_path: str | None = None
    include_motion_derivs: bool = False
    use_tissue_derivs: bool = False

    # Condition labels
    cond_labels: list[str] | None = None        # task_act
    cond_beta_labels: list[str] | None = None   # task_conn

    # Contrasts (task_act + task_conn)
    contrast_functions: list[str] | None = None
    contrast_labels: list[str] | None = None

    # task_act extraction
    extract: bool = False
    extract_labels: list[str] | None = None
    extract_stat: str | None = None
    extract_out_file_pre: str | None = None
    extract_resids: bool = False
    extract_raw_ptseries: bool = False

    # task_conn extraction
    extract_pbseries: bool = False

    # Connectivity (task_conn + rest_conn)
    calc_conn: str | None = None
    conn_out_file_pre: str | None = None
    pcorr: bool = False
    fishZ: bool = False

    # rest_conn specific
    scan_paths: list[str] | None = None
    motion_paths: list[str] | None = None
    CSF_paths: list[str] | None = None
    WM_paths: list[str] | None = None
    GS_paths: list[str] | None = None
    bandpass: list[float] | None = None
    notch_filter_band: list[float] | None = None
    motion_deriv_degree: int | None = None
    use_sequenced_bandpass: bool = False
    keep_run_res_dtseries: bool = True

    # rest_conn extraction
    extract_ptseries: bool = False
```

**3-stage pipeline:**

1. `load_config(config_path: str) -> dict` (existing, minimal change): raise ConfigError on parse failure or missing file (replacing sys.exit at lines 81-88).

2. `validate_config(raw_config: dict, logger: logging.Logger | None = None) -> dict` (refactored): all 37 sys.exit(1) sites replaced with ConfigError or InputError:
   - Structure checks (missing "analyses", not a list, empty): ConfigError
   - Type/enum checks (invalid analysis type, HRF model, stat type): ConfigError
   - Required key checks per analysis_type: ConfigError
   - Path existence checks: InputError (user-specified file not found) or ConfigError (path spec malformed)
   - Value range checks (tr <= 0, fd_threshold <= 0): ConfigError
   - Contrast parity, extraction dependency, connectivity dependency: ConfigError
   - Duplicate (out_dir, out_file_pre): ConfigError
   REQUIRED_KEYS and REQUIRED_PATHS dicts replaced by declarative validation against ResolvedConfig field requirements per analysis_type.

3. `resolve_config(validated_block: dict, global_cfg: dict, logger: logging.Logger | None = None) -> ResolvedConfig` (new, replaces _merge_global_into_block + build_namespace): merge global into block, construct ResolvedConfig, set schema_version="3.0.0". If derivatives_dirs is set, call discover_inputs() (C11) and apply three-tier resolution.

**Public API:**

```python
def load_and_validate(
    config_path: str,
    logger: logging.Logger | None = None,
    **overrides,
) -> list[ResolvedConfig]:
```

Returns one ResolvedConfig per analysis block. Overrides applied before resolve_config() (orchestrator injects subject-specific values).

**Eliminated:** argparse import, build_namespace() function, REQUIRED_KEYS/REQUIRED_PATHS dicts.
      </spec>
      <dependencies>C1</dependencies>
      <risk>high - every downstream module consumes the config type. Attribute names preserved 1:1 (config.out_dir, config.scan_path, etc.) to minimize downstream changes.</risk>
      <rollback>git restore first_level_config.py</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C2: Logging Overhaul (T4)                                          -->
    <!-- ================================================================== -->
    <change id="C2" priority="P0" source_item="T4/AI-4">
      <file path="fmri_first_level_proc/first_level_utils.py" action="modify" />
      <description>Refactor setup_logging() to harmonize with fmri-preproc (stderr, ISO 8601, format). Add graded_warning() function with complete warning code registry.</description>
      <spec>
**setup_logging() changes** (lines 172-212):
- Console handler: `StreamHandler(sys.stdout)` -> `StreamHandler(sys.stderr)`
- Format: `"%(asctime)s [%(name)s] [%(levelname)s] %(message)s"` -> `"%(asctime)s [%(levelname)s] %(name)s: %(message)s"`
- Date format: `"%Y-%m-%d %H:%M:%S"` -> `"%Y-%m-%dT%H:%M:%S"`
- Signature unchanged: `setup_logging(name: str, log_file: str | None = None) -> logging.Logger`
- Idempotent guard retained

**graded_warning() (new):**

```python
def graded_warning(
    logger: logging.Logger,
    severity: str,
    code: str,
    message: str,
    *,
    user_facing: bool = False,
) -> dict:
```

- severity: "low" (no exit code effect), "medium" (no exit code effect), "high" (triggers exit code 3)
- user_facing: True -> log at WARNING (console visible); False -> log at INFO (file only when --log-file provided)
- Returns `{"severity": severity, "code": code, "message": message, "user_facing": user_facing}`
- Callers accumulate returned dicts in a list threaded through run() -> FirstLevelResult.warnings

**Complete warning code registry (11 codes):**

| Code | Severity | Site | user_facing |
|---|---|---|---|
| CENSOR_HIGH | high | >50% TRs censored | True |
| DOF_LOW | high | DOF critically low (>= 1, near threshold) | True |
| RUN_SKIPPED | high | rest_conn run skipped, DOF < 1 | True |
| TRIALS_FEW | medium | condition has few surviving trials (>= 2) | True |
| COND_DROPPED | medium | condition dropped, < 2 surviving trials | True |
| CONTRAST_DROPPED | medium | contrast dropped, references dropped condition | True |
| EXTRACT_DROPPED | medium | extraction dropped, references dropped condition | True |
| GS_MISSING | low | GS_paths not provided for rest_conn | False |
| CLI_DEPRECATED | low | deprecated `run-first-level` name used | True |
| EVENTS_LEGACY | low | legacy CSV events format detected | True |
| DISCOVERY_COLLISION | low | same entity found in multiple derivatives_dirs | False |
      </spec>
      <dependencies>C1</dependencies>
      <risk>low - setup_logging signature unchanged, graded_warning is additive. Console output moves from stdout to stderr (intentional, prevents log contamination of data streams).</risk>
      <rollback>git restore first_level_utils.py (logging section)</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C4: Python Version Floor (T7)                                      -->
    <!-- ================================================================== -->
    <change id="C4" priority="P0" source_item="T7/AI-7">
      <file path="pyproject.toml" action="modify" />
      <description>Raise requires-python from ">=3.8" to ">=3.12". No shims to remove (verified by grep). No CI/CD to update.</description>
      <spec>
Change `requires-python = ">=3.8"` to `requires-python = ">=3.12"`.

All new code in subsequent changes uses Python 3.12+ syntax: `X | None`, `list[str]`, `dict[str, str]` (no `typing` imports for these).
      </spec>
      <dependencies>none</dependencies>
      <risk>low - single-line change</risk>
      <rollback>revert the requires-python line</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C5: AFNI Version Validation (T9)                                   -->
    <!-- ================================================================== -->
    <change id="C5" priority="P0" source_item="T9/AI-9">
      <file path="tools.lock.yaml" action="create" />
      <file path="fmri_first_level_proc/runtime.py" action="create" />
      <description>Create AFNI version lockfile and validation module. Preflight binary reachability check and version probe with strict exact-match enforcement, harmonized with fmri-preproc.</description>
      <spec>
**tools.lock.yaml** (project root):

```yaml
lockfile_version: "1.0.0"
binaries:
  AFNI: "PLACEHOLDER"
```

Version placeholder populated from `afni -ver` on target deployment system before first use.

**runtime.py functions:**

```python
def _parse_afni_version(stdout: str, stderr: str) -> str | None:
```
Regex `r"AFNI[_\s]+(\d+\.\d+\.\d+)"` on stdout+stderr concatenation. Return version string or None.

```python
def preflight_tool_environments(
    afni_home: str | None = None,
    logger: logging.Logger | None = None,
) -> None:
```
Check reachability of all 14 AFNI binaries via shutil.which() (or os.path.join if afni_home set). AFNI home discovery: (1) afni_home parameter, (2) shutil.which("afni") parent dir, (3) ~/abin. Collect-then-fail: accumulate all unreachable binaries, raise single ToolUnavailableError with complete list.

**Complete AFNI binary list (14, verified by codebase grep):**
3dDeconvolve, 3dTproject, 3dBandpass, 3dROIstats, 3dNetCorr, 3dresample, 3dinfo, 3dToutcount, 3dbucket, 3dcalc, 3dLSS, 3dTcat, 1d_tool.py, 1dtranspose

```python
def probe_tool_versions(
    lockfile_path: str,
    afni_home: str | None = None,
    logger: logging.Logger | None = None,
) -> None:
```
Read lockfile, run `afni -ver`, parse via _parse_afni_version(), strict exact-match (Python !=). Raise ToolUnavailableError on mismatch. Success log: "Startup version probe passed: 1 pinned tool(s) verified." (INFO).

Error messages (harmonized with fmri-preproc):
- Not reachable: `"{tool}: probe command {cmd!r} failed ({exc}); expected version {expected}"`
- Unparseable: `"{tool}: version not parseable from probe output; expected {expected}"`
- Mismatch: `"{tool}: expected {expected}, got {actual}"`

Both functions called sequentially from main() before pipeline dispatch.
      </spec>
      <dependencies>C1</dependencies>
      <risk>low - new files, no existing code modified. Lockfile placeholder requires user action before deployment.</risk>
      <rollback>delete runtime.py and tools.lock.yaml</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C6: Events File Format (T6)                                        -->
    <!-- ================================================================== -->
    <change id="C6" priority="P0" source_item="T6/AI-6">
      <file path="fmri_first_level_proc/first_level_utils.py" action="modify" />
      <description>Refactor read_and_validate_stim_data() for dual-format support: BIDS _events.tsv primary, legacy CSV fallback with deprecation warning. Content-authoritative detection.</description>
      <spec>
**Refactored: read_and_validate_stim_data()** (line 447, signature unchanged):

```python
def read_and_validate_stim_data(
    timing_path: str,
    cond_labels: list[str],
    logger: logging.Logger | None = None,
) -> pd.DataFrame:
```

**Detection algorithm (content-authoritative, delimiter from extension):**
1. Determine delimiter: `.tsv` -> tab; `.csv`/other -> comma
2. Read header row using determined delimiter
3. If header contains BIDS columns (`onset`, `duration`, `trial_type`, case-insensitive): BIDS format
4. If header contains legacy columns (`CONDITION`, `ONSET`, `DURATION`, case-insensitive): legacy CSV
5. Neither matches: raise InputError listing both expected header formats

**Column renaming on load (legacy -> BIDS):** CONDITION -> trial_type, ONSET -> onset, DURATION -> duration

**Internal representation:** DataFrame uses BIDS column names (onset, duration, trial_type) exclusively. All downstream code references BIDS names only. This requires updating write_onset_file() and any code that references the old column names.

**Deprecation warning on legacy detection:**
```python
graded_warning(logger, "low", "EVENTS_LEGACY",
    "Legacy CSV events format detected. Migrate to BIDS _events.tsv. "
    "CSV support will be removed in version 4.0.0.", user_facing=True)
```

**sys.exit replacement (2 sites):** Lines 471 (missing columns) and 479 (condition labels not found) -> InputError.

**Edge case:** A .csv with BIDS columns is BIDS format read comma-delimited.
      </spec>
      <dependencies>C1, C2</dependencies>
      <risk>medium - changes parsing logic for existing input format. Legacy CSV path must produce identical downstream results.</risk>
      <rollback>git restore read_and_validate_stim_data and related functions</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C7: Utils sys.exit Bulk Migration (T3b)                            -->
    <!-- ================================================================== -->
    <change id="C7" priority="P0" source_item="T3/AI-3">
      <file path="fmri_first_level_proc/first_level_utils.py" action="modify" />
      <description>Replace remaining ~45 sys.exit(1) sites in first_level_utils.py with appropriate exception raises (2 handled in C6, 47 total). Per-site categorization by condition pattern.</description>
      <spec>
**Categorization rules applied per-site:**

| Condition Pattern | Exception | Sites |
|---|---|---|
| Cannot read/parse input file (motion, tissue, timing) | InputError | 6 |
| Input file has wrong format/dimensions (columns, shape) | InputError | 4 |
| AFNI command CalledProcessError | ToolExecutionError | 11 |
| Expected AFNI output file not found after command | ToolExecutionError | 8 |
| AFNI output unparseable or unexpected format (returned 0) | GuardError | 4 |
| Validation of options (missing required param) | ConfigError | 7 |
| Connectivity matrix load/dimension mismatch | InputError | 2 |
| Safety guard (remove_files_from_dir root/home check) | GuardError | 1 |
| DOF < 1 (compute_dof, exit_on_error=True) | ModelError | 1 |
| Contrast parsing (invalid equation, missing condition) | ConfigError | 4 |

**45 sites remaining** (47 total minus 2 handled in C6).

**compute_dof special case (line 1418):** Eliminate `exit_on_error` parameter. When DOF < 1, raise ModelError unconditionally. Rest_conn callers that currently pass `exit_on_error=False` instead catch ModelError and emit graded_warning(severity="high", code="RUN_SKIPPED").

**Detailed per-function categorization** (from explorer structural map):

prepare_motion_file (lines 113, 120): InputError
validate_extract_options (lines 241, 244, 248): ConfigError
validate_connectivity_options (lines 284, 289, 296): ConfigError
remove_files_from_dir (line 309): GuardError
create_censor_file (line 590): ToolExecutionError
notch_filter_motion (lines 720, 728): ToolExecutionError
censor_interpolate_1d_afni (lines 789, 796): ToolExecutionError
bandpass_filter_1d_afni (lines 859, 866): ToolExecutionError
compute_tissue_derivative (lines 901, 904): InputError
validate_template (lines 1107, 1114, 1118, 1121, 1125, 1129): InputError (content) or ConfigError (options)
validate_template (lines 1135, 1148, 1180, 1186): InputError (1135), ConfigError (1148), ToolExecutionError (1180), ToolExecutionError (1186)
extract_roi_stats (lines 1224, 1249, 1257): ToolExecutionError (1224), GuardError (1249, 1257)
gen_min_outlier_epi (lines 1318, 1324, 1328, 1340, 1346): ToolExecutionError (1318, 1340), GuardError (1324, 1328), ToolExecutionError (1346)
compute_dof (line 1418): ModelError
valid_contrast_functions (lines 1439, 1453, 1473, 1485, 1493): ConfigError
compute_matrix_contrast (lines 1594, 1604): InputError
parcellated_conn (lines 1864, 1867): ToolExecutionError
      </spec>
      <dependencies>C1</dependencies>
      <risk>medium - 45 individual sites, each needs correct exception selection. Error detection conditions and messages preserved.</risk>
      <rollback>git restore first_level_utils.py</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C8: Pipeline Module Refactoring (T3c + T5 integration)             -->
    <!-- ================================================================== -->
    <change id="C8" priority="P0" source_item="T3/AI-3, T5/AI-5, T2/AI-2">
      <file path="fmri_first_level_proc/task_act_first_level.py" action="modify" />
      <file path="fmri_first_level_proc/task_conn_first_level.py" action="modify" />
      <file path="fmri_first_level_proc/rest_conn_first_level.py" action="modify" />
      <description>Replace all sys.exit(1) in pipeline modules (35 total: 18 + 10 + 7). Adopt ResolvedConfig parameter type. Return FirstLevelResult from run(). Collect graded_warnings throughout. Remove standalone main() from each module.</description>
      <spec>
**Parameter type change:** All functions accepting `args` (argparse.Namespace) change to `config` (ResolvedConfig). Attribute names preserved 1:1: `args.out_dir` -> `config.out_dir`.

**run() signature change (all three modules):**

```python
def run(config: ResolvedConfig, logger: logging.Logger | None = None) -> FirstLevelResult:
```

**run() return construction:** At end of successful execution:
1. Collect all graded_warning dicts accumulated during the run
2. Determine status: "success_with_warnings" if any warning has severity != "low", else "success"
3. Populate qc_summary from write_qc_summary output (pct_censored, dof, trial_counts)
4. Populate output_files from all deliverable paths created
5. Return FirstLevelResult

**sys.exit categorization per module:**

task_act (18 sites):
- Lines 494, 498, 513, 523, 528, 537, 542: ConfigError (option validation)
- Lines 257, 357, 399, 419: ToolExecutionError (AFNI command failure)
- Lines 380, 389: GuardError (unexpected sub-brick or stat aux output)
- Lines 431, 450, 552: InputError (expected output file not found after write)
- Line 137: ConfigError (extract label not in condition/contrast lists)
- Line 588: ModelError (all conditions dropped, no surviving trials)

task_conn (10 sites):
- Lines 619, 624, 661, 665: ConfigError
- Lines 277, 327, 374: ToolExecutionError
- Lines 408, 633: InputError
- Line 688: ModelError (all conditions dropped)

rest_conn (7 sites):
- Lines 567, 612, 615: ConfigError
- Lines 434, 443: ToolExecutionError
- Lines 485, 628: InputError

**graded_warning integration points** (existing logger.warning calls converted):
- trial survival check: TRIALS_FEW (per condition with few but >= 2 trials)
- condition dropping: COND_DROPPED
- contrast dropping: CONTRAST_DROPPED
- extraction dropping: EXTRACT_DROPPED (task_act)
- run skipping (rest_conn, DOF < 1): RUN_SKIPPED
- censoring stats: CENSOR_HIGH (per run with > 50% censored)
- GSR warning: GS_MISSING (rest_conn, when GS_paths absent)

**Removed from each module:** standalone `main()`, `import sys`, `import argparse`.
      </spec>
      <dependencies>C1, C3, C7</dependencies>
      <risk>high - 3 files, 35 sys.exit sites, full parameter type migration. Every function in the call chain must accept ResolvedConfig.</risk>
      <rollback>git restore task_act_first_level.py task_conn_first_level.py rest_conn_first_level.py</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C9: CLI Rename + Python API (T2)                                   -->
    <!-- ================================================================== -->
    <change id="C9" priority="P0" source_item="T2/AI-2">
      <file path="fmri_first_level_proc/first_level_utils.py" action="modify" />
      <file path="fmri_first_level_proc/run_first_level.py" action="modify" />
      <file path="fmri_first_level_proc/__init__.py" action="modify" />
      <file path="pyproject.toml" action="modify" />
      <description>Define FirstLevelResult dataclass. Refactor main() as thin wrapper with exception-to-exit-code mapping. Rename CLI entry point with deprecated alias. Update exports.</description>
      <spec>
**FirstLevelResult** (added to first_level_utils.py):

```python
@dataclasses.dataclass
class FirstLevelResult:
    status: str              # "success" | "success_with_warnings"
    output_dir: Path         # resolved output directory
    warnings: list[dict]     # graded_warning dicts from run()
    qc_summary: dict         # {pct_censored: dict, dof: int|dict, trial_counts: dict}
    output_files: list[str]  # absolute paths to all deliverables
```

No exit_code field. Exceptions communicate failure (no FirstLevelResult returned).

**main() refactoring** (run_first_level.py):

```python
def main(cli_name: str = "fmri-first-level-proc") -> None:
```

Flow:
1. If cli_name == "run-first-level": emit CLI_DEPRECATED graded_warning
2. Parse CLI args: --config (required), --dry-run, --analyses (int list), --log-file
3. logger = setup_logging("fmri_first_level_proc", log_file=args.log_file)
4. preflight_tool_environments(logger=logger) (from C5)
5. probe_tool_versions(lockfile_path, logger=logger) (from C5)
6. configs = load_and_validate(args.config, logger)
7. If --analyses: filter configs by index (raise ConfigError if out of range)
8. If --dry-run: log plan and return
9. For each config: result = DISPATCH[config.analysis_type](config, logger)
10. Aggregate warnings across all results
11. Determine exit code: 3 if any high-severity warning, else 0

Exception handling (wrapping steps 4-10):
```python
try:
    ...
except ConfigError as e:
    logger.error(str(e)); sys.exit(2)
except InputError as e:
    logger.error(str(e)); sys.exit(2)
except ModelError as e:
    logger.error(str(e)); sys.exit(5)
except (ToolUnavailableError, ToolExecutionError) as e:
    logger.error(str(e)); sys.exit(4)
except GuardError as e:
    logger.critical(str(e)); sys.exit(1)
```

**Deprecated alias:**

```python
def _main_deprecated() -> None:
    main(cli_name="run-first-level")
```

**pyproject.toml [project.scripts]:**
```toml
fmri-first-level-proc = "fmri_first_level_proc.run_first_level:main"
run-first-level = "fmri_first_level_proc.run_first_level:_main_deprecated"
```

**__init__.py exports:**
```python
from .first_level_config import load_and_validate, ResolvedConfig
from .first_level_utils import setup_logging, FirstLevelResult, graded_warning
from .run_first_level import DISPATCH

__all__ = [
    "load_and_validate", "ResolvedConfig",
    "setup_logging", "FirstLevelResult", "graded_warning",
    "DISPATCH", "__version__",
]
```

Pipeline-specific functions (run_task_act, run_task_conn, run_rest_conn) remain importable but NOT in __all__. Unused v2 exports removed: build_hrf_string, validate_custom_hrf, needs_married_timing, VALID_HRF_MODELS, HRF_DURATION_MODELS, HRF_DM_MODELS, HRF_IMPULSE_MODELS (internal implementation details, not public API).

**4 sys.exit sites in run_first_level.py replaced:**
- Line 99 (AFNI not found): eliminated (preflight handles this via ToolUnavailableError)
- Line 111 (--analyses out of range): ConfigError
- Lines 143, 146 (run() failure): eliminated (exceptions propagate to main()'s handler)
      </spec>
      <dependencies>C1, C2, C3, C8</dependencies>
      <risk>medium - CLI rename may affect existing users (mitigated by deprecated alias with 4.0.0 removal timeline).</risk>
      <rollback>git restore run_first_level.py __init__.py; revert pyproject.toml scripts</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C10: BIDS-Derivative Output (T1a)                                  -->
    <!-- ================================================================== -->
    <change id="C10" priority="P0" source_item="T1/AI-1, P1-implement (BIDS naming)">
      <file path="fmri_first_level_proc/bids.py" action="create" />
      <description>Create BIDS output module: derivative path construction with entity naming (resolving the P1 deferred item) and dataset_description.json writer.</description>
      <spec>
**Output directory structure:**
`{out_dir}/sub-{sub}[/ses-{ses}]/func/`

Session directory included only when session entity is present. `out_dir` from ResolvedConfig serves as the derivatives root for this analysis.

**build_bids_output_path():**

```python
def build_bids_output_path(
    output_dir: str,
    entities: dict[str, str],
    suffix: str,
    ext: str,
) -> str:
```

Entity ordering: sub, ses, task, acq, rec, run, space, desc, stat. Only non-None entities included. Values sanitized via sanitize_filename_label(). Returns absolute path under the BIDS-derivative directory structure.

**BIDS entity naming conventions (P1 resolution):**

Suffixes: `statmap` (statistical maps), `bold` (time series volumes), `epi` (reference volumes), `connmat` (connectivity matrices, BIDS-safe form of user-chosen "conn_mat"), `timeseries` (parcellated/extracted series), `stats` (ROI statistics), `qc` (quality control), `regressors` (nuisance/censor files).

| Output | desc | stat | suffix | ext |
|---|---|---|---|---|
| Condition z-map | {cond} | z | statmap | .nii.gz |
| Condition t-map | {cond} | t | statmap | .nii.gz |
| Condition beta | {cond} | beta | statmap | .nii.gz |
| Contrast z-map | {contrast} | z | statmap | .nii.gz |
| GLM bucket | bucket | -- | statmap | .nii.gz |
| Full beta series | betaseries | -- | bold | .nii.gz |
| Condition betas | {cond}betas | -- | bold | .nii.gz |
| Parcel beta series | {cond} | -- | timeseries | .csv |
| Connectivity matrix | {cond} | -- | connmat | .tsv |
| Connectivity contrast | {contrast} | -- | connmat | .tsv |
| Residual TS (concat) | residual | -- | bold | .nii.gz |
| Parcel residual TS | residual | -- | timeseries | .csv |
| ROI extraction | {cond} | {stat} | stats | .csv |
| Residual ROI | residuals | -- | stats | .csv |
| Pre-reg ptseries | preregression | -- | timeseries | .csv |
| Min-outlier EPI | minoutlier | -- | epi | .nii.gz |
| QC summary | -- | -- | qc | .json |
| Censor file | censor | -- | regressors | .1D |
| Motion regressors | motion | -- | regressors | .1D |

Entity `space` included only for volumetric NIfTI outputs.
Entity `run` included for rest_conn per-run outputs.

**write_dataset_description():**

```python
def write_dataset_description(
    derivatives_dir: str,
    source_datasets: list[dict] | None = None,
) -> None:
```

Creates `{derivatives_dir}/dataset_description.json` with Name="fmri-first-level-proc", BIDSVersion="1.9.0", DatasetType="derivative", GeneratedBy and SourceDatasets. No-op if file already exists.

**Integration:** Pipeline run() functions call build_bids_output_path() for each output instead of current manual os.path.join + string formatting. Existing build_conn_output_path() in utils.py is replaced by build_bids_output_path() calls with appropriate entities.
      </spec>
      <dependencies>C8, C9</dependencies>
      <risk>medium - changes all output file paths. Existing path construction in 3 pipeline modules replaced. Output consumers (downstream orchestrator, tests) must update expectations.</risk>
      <rollback>delete bids.py; revert pipeline output path construction</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C11: BIDS Input Discovery (T1b)                                    -->
    <!-- ================================================================== -->
    <change id="C11" priority="P0" source_item="T1/AI-1">
      <file path="fmri_first_level_proc/bids.py" action="modify" />
      <file path="fmri_first_level_proc/first_level_config.py" action="modify" />
      <description>Implement BIDS input discovery with multi-directory search, priority ordering (first-directory match wins), collision warning, and three-tier resolution (explicit config > discovery > InputError on mandatory miss).</description>
      <spec>
**DiscoveredInputs dataclass** (bids.py):

```python
@dataclasses.dataclass
class DiscoveredInputs:
    scan_path: str | None = None
    motion_path: str | None = None
    task_timing_path: str | None = None
    CSF_path: str | None = None
    WM_path: str | None = None
    scan_paths: list[str] | None = None     # rest_conn per-run
    motion_paths: list[str] | None = None
    CSF_paths: list[str] | None = None
    WM_paths: list[str] | None = None
    GS_paths: list[str] | None = None
    template_path: str | None = None
    source_dirs: dict[str, str] = dataclasses.field(default_factory=dict)
```

`source_dirs` maps field name to the directory where the input was discovered.

**discover_inputs():**

```python
def discover_inputs(
    derivatives_dirs: list[str],
    subject: str,
    session: str | None,
    task: str | None,
    analysis_type: str,
    logger: logging.Logger | None = None,
) -> DiscoveredInputs:
```

**Default discovery contract** (per-slot BIDS entity patterns):

| Slot | desc | suffix | ext | Mandatory |
|---|---|---|---|---|
| scan_path/scan_paths | preproc | bold | .nii.gz | yes |
| motion_path/motion_paths | confounds | regressors | .tsv | yes |
| task_timing_path | -- | events | .tsv | yes (task) |
| CSF_path/CSF_paths | CSF | timeseries | .1D | rest: yes, task: optional |
| WM_path/WM_paths | WM | timeseries | .1D | rest: yes, task: optional |
| GS_paths | GS | timeseries | .1D | optional |
| template_path | -- | dseg | .nii.gz | optional |

Pattern: `sub-{sub}[_ses-{ses}][_task-{task}][_run-*]*[_desc-{desc}]_{suffix}{ext}` matched within `{dir}/sub-{sub}[/ses-{ses}]/func/`.

Search order: iterate derivatives_dirs in list order. For each slot, search each directory until a match is found (first-directory match wins). Collision (same entity in >1 directory): graded_warning DISCOVERY_COLLISION. Missing mandatory: raise InputError.

Every discovered input logged at INFO with source directory.

**Three-tier resolution** (integrated into resolve_config() in config.py):
1. Explicit path in config (always wins if set)
2. Discovered path from discover_inputs()
3. InputError on mandatory miss
      </spec>
      <dependencies>C3, C10</dependencies>
      <risk>high - discovery patterns must correctly match upstream pipeline outputs. Patterns may need adjustment during integration testing with fmri-preproc and fmri-proc-orchestrator.</risk>
      <rollback>revert bids.py discovery functions; revert config resolve_config changes</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C12: Processing DAG / Checkpoint (T1c)                             -->
    <!-- ================================================================== -->
    <change id="C12" priority="P0" source_item="T1/AI-1">
      <file path="fmri_first_level_proc/checkpoint.py" action="create" />
      <description>Implement processing DAG with checkpoint/resume via append-only JSONL ledger. LedgerEntry, append/read/reconstruct functions, config-hash invalidation. Harmonized with fmri-preproc's checkpoint patterns.</description>
      <spec>
**LedgerEntry dataclass:**

```python
@dataclasses.dataclass
class LedgerEntry:
    stage_id: str           # "TA.prep", "TC.beta", "RC.resid.0", etc.
    scope_key: str          # BIDS entity key, e.g. "sub-01_ses-01_task-nback"
    status: str             # "completed" | "reconstructed"
    timestamp_utc: str      # ISO 8601
    wall_clock_s: float
    config_hash: str | None # SHA-256 of ResolvedConfig; None for reconstructed
    qc_summary: dict
    output_files: list[str]
```

**DAG dependency graphs:**

```python
DAG_TASK_ACT = ["TA.prep", "TA.glm", "TA.extract", "TA.qc"]
DAG_TASK_CONN = ["TC.prep", "TC.design", "TC.beta", "TC.conn", "TC.qc"]
DAG_REST_CONN_PER_RUN = ["RC.prep.{n}", "RC.resid.{n}"]
DAG_REST_CONN_POST = ["RC.concat", "RC.conn", "RC.qc"]
```

rest_conn per-run stages are independent (can fail individually without blocking other runs). Post-concat stages are sequential and depend on all successful per-run stages.

**Functions:**

```python
def append_ledger_entry(ledger_path: str, entry: LedgerEntry) -> None:
```
open(path, "a"), write JSON line, flush(), os.fsync(). No write on failure.

```python
def read_ledger(ledger_path: str) -> dict[tuple[str, str], LedgerEntry]:
```
Parse JSONL, last-writer-wins keyed by (stage_id, scope_key).

```python
def resolve_rerun_set(
    ledger: dict[tuple[str, str], LedgerEntry],
    dag: list[str],
    scope_key: str,
    current_config_hash: str,
) -> list[str]:
```
Walk DAG in order. Return stage_ids needing (re)run: stages without completed entries, or stages with config_hash mismatch (which also invalidates all downstream).

```python
def auto_reconstruct_ledger(
    output_dir: str, analysis_type: str, scope_key: str,
) -> list[LedgerEntry]:
```
Scan output artifacts, infer producing stages, create entries with status="reconstructed", config_hash=None.

```python
def compute_config_hash(config: ResolvedConfig) -> str:
```
SHA-256 of json.dumps(dataclasses.asdict(config), sort_keys=True).

**Ledger file:** `{output_dir}/processing_ledger.jsonl`

**Integration:** Each pipeline run() wraps stage execution:
1. compute_config_hash(config)
2. read_ledger() or auto_reconstruct_ledger() if no ledger exists
3. resolve_rerun_set() to determine which stages to run
4. For each stage: if in rerun set, execute and append_ledger_entry(); if not, skip with log
      </spec>
      <dependencies>C8, C10</dependencies>
      <risk>high - DAG logic and config-hash invalidation must be correct. Incorrect invalidation causes unnecessary reruns; missing invalidation produces stale results.</risk>
      <rollback>delete checkpoint.py; revert pipeline integration</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C13: Testing Overhaul (T8)                                         -->
    <!-- ================================================================== -->
    <change id="C13" priority="P0" source_item="T8/AI-8">
      <file path="pyproject.toml" action="modify" />
      <description>Add pytest marker taxonomy to pyproject.toml. Map existing ~460 tests to taxonomy levels (labeling exercise, add @pytest.mark decorators). Factory functions in conftest.py remain as explicit helpers.</description>
      <spec>
**pyproject.toml [tool.pytest.ini_options]:**

```toml
[tool.pytest.ini_options]
markers = [
    "level0_unit: Pure-function unit tests",
    "level1_internal_integration: Cross-function integration within a module",
    "level2_tool_equivalence: Verify tool wrapper output matches known reference",
    "level3_checkpoint: Checkpoint/resume round-trip",
    "level4_stage_integration: Single pipeline stage end-to-end",
    "level5_adversarial: Edge cases, malformed input, boundary conditions",
    "level6_cross_stage: Multi-stage integration",
    "level7_pipeline: Full pipeline end-to-end",
]
```

**Test mapping guidelines:**
- test_contrast_parser, test_config_validation, test_utils_unit, test_tr_explicit: level0_unit
- test_connectivity, test_extract_effects, test_subbrik_and_dispatch: level1_internal_integration / level2_tool_equivalence
- test_contrast_adversarial, test_config_edge_cases, test_error_paths: level5_adversarial
- test_roi_extraction, test_cenmode, test_censor_creation, test_qc_summary: level0_unit or level4_stage_integration
- test_rest_conn_pipeline, test_task_act_pipeline, test_task_conn_pipeline: level7_pipeline
- test_v230_regression, test_utils_extended: level5_adversarial or level1_internal_integration

Specific per-test mapping determined during build by reading each test function's scope.

**conftest.py:** Factory functions remain explicit helpers (make_task_act_args, make_timing_csv, etc.). Signature updates needed: accept ResolvedConfig instead of argparse.Namespace (make_task_act_args -> make_task_act_config, etc.). Exception: expensive shared setup for new v3.0.0 tests (e.g., mock BIDS directory tree) may use session-scoped @pytest.fixture.
      </spec>
      <dependencies>all prior changes</dependencies>
      <risk>low - labeling only for markers. conftest.py signature updates mechanical (follows C3/C8 type changes).</risk>
      <rollback>revert pyproject.toml pytest section; remove markers from test files</rollback>
    </change>

    <!-- ================================================================== -->
    <!-- C14: Version Bump                                                  -->
    <!-- ================================================================== -->
    <change id="C14" priority="P0" source_item="AI-version-bump">
      <file path="pyproject.toml" action="modify" />
      <file path="fmri_first_level_proc/__init__.py" action="modify" />
      <description>Bump version from 2.5.0 to 3.0.0. Major version bump reflecting breaking API changes across all 9 topics.</description>
      <spec>
pyproject.toml: `version = "2.5.0"` -> `version = "3.0.0"`
__init__.py: `__version__ = "2.5.0"` -> `__version__ = "3.0.0"`
      </spec>
      <dependencies>all prior changes</dependencies>
      <risk>low - version string change</risk>
      <rollback>revert version strings</rollback>
    </change>

  </changes>

  <execution_order>C1, C3, C2, C4, C5, C6, C7, C8, C9, C10, C11, C12, C13, C14</execution_order>

  <execution_order_rationale>
    Follows brainstorm-recommended topic order (T3 -> T5 -> T4 -> T7 -> T9 -> T6 -> T2 -> T1 -> T8) with T3 split into foundation (C1), utils migration (C7), and pipeline migration (C8) placed at dependency-correct points. T1 split into output (C10), discovery (C11), and DAG (C12) for manageable scope. Version bump (C14) applied last.

    Dependency graph:
    C1 (exceptions) <- foundation, no deps
    C3 (config) <- C1
    C2 (logging) <- C1
    C4 (python floor) <- none
    C5 (AFNI validation) <- C1
    C6 (events) <- C1, C2
    C7 (utils sys.exit) <- C1
    C8 (pipeline) <- C1, C3, C7
    C9 (CLI/API) <- C1, C2, C3, C8
    C10 (BIDS output) <- C8, C9
    C11 (BIDS discovery) <- C3, C10
    C12 (DAG) <- C8, C10
    C13 (testing) <- all
    C14 (version) <- all
  </execution_order_rationale>

  <risk_summary>
    High-risk changes: C3 (config refactoring, pervasive type change), C8 (pipeline refactoring, 35 sys.exit sites + type migration), C11 (BIDS discovery, pattern matching), C12 (processing DAG, correctness-critical checkpoint logic).

    Medium-risk changes: C6 (events format, parsing logic), C7 (utils sys.exit, 45 sites), C9 (CLI rename), C10 (output path changes).

    Low-risk changes: C1, C2, C4, C5, C13, C14.

    Recommended: /test design session after build to cover all new v3.0.0 functionality (per brainstorm P1 test action item).
  </risk_summary>

</implement_plan>
