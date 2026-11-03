<implement_report>
  <meta project="fmri_first_level_proc" mode="implement" submodule="build" timestamp="2026-08-12T23:05:00Z" />
  <spec_ref>fmri_first_level_proc_implement_plan_20260812_213331.md</spec_ref>
  <changes_applied>
    <change id="C1" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/exceptions.py" lines_changed="27" />
      </files_modified>
      <notes>Created exception hierarchy: FmriFirstLevelError base with 6 subclasses (ConfigError, InputError, ToolUnavailableError, ToolExecutionError, ModelError, GuardError). Executed inline.</notes>
    </change>
    <change id="C3" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_config.py" lines_changed="736" />
      </files_modified>
      <notes>ResolvedConfig dataclass (49 fields, schema_version='3.0.0'). 3-stage pipeline (load_config, validate_config, resolve_config). All 37 sys.exit(1) replaced with ConfigError/InputError. Removed argparse, build_namespace, REQUIRED_KEYS/REQUIRED_PATHS.</notes>
    </change>
    <change id="C2" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_utils.py" lines_changed="45" />
      </files_modified>
      <notes>setup_logging: stderr handler, ISO 8601 datefmt, harmonized format. graded_warning function added with severity/code/message/user_facing contract.</notes>
    </change>
    <change id="C4" status="done" user_decision="n/a">
      <files_modified>
        <file path="pyproject.toml" lines_changed="1" />
      </files_modified>
      <notes>requires-python raised from >=3.8 to >=3.12. Executed inline.</notes>
    </change>
    <change id="C5" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/runtime.py" lines_changed="186" />
        <file path="tools.lock.yaml" lines_changed="3" />
      </files_modified>
      <notes>Created runtime.py with _parse_afni_version, preflight_tool_environments (14 AFNI binaries), probe_tool_versions (strict exact-match, PLACEHOLDER skip). Lockfile with PLACEHOLDER version.</notes>
    </change>
    <change id="C6" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_utils.py" lines_changed="95" />
      </files_modified>
      <notes>Dual-format events support (BIDS _events.tsv primary, legacy CSV fallback). Content-authoritative detection. EVENTS_LEGACY graded_warning. All downstream code uses BIDS column names (onset, duration, trial_type). 2 sys.exit sites replaced with InputError.</notes>
    </change>
    <change id="C7" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_utils.py" lines_changed="90" />
      </files_modified>
      <notes>45 remaining sys.exit(1) sites replaced with typed exceptions (ConfigError, InputError, ToolExecutionError, GuardError, ModelError). compute_dof exit_on_error parameter eliminated. import sys preserved (sys.stderr in setup_logging).</notes>
    </change>
    <change id="C8" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_act_first_level.py" lines_changed="588" />
        <file path="fmri_first_level_proc/task_conn_first_level.py" lines_changed="688" />
        <file path="fmri_first_level_proc/rest_conn_first_level.py" lines_changed="629" />
        <file path="fmri_first_level_proc/first_level_utils.py" lines_changed="10" />
      </files_modified>
      <notes>All 35 sys.exit sites replaced across 3 pipeline modules. ResolvedConfig parameter type adopted. run() returns FirstLevelResult. graded_warning integration for TRIALS_FEW, COND_DROPPED, CONTRAST_DROPPED, EXTRACT_DROPPED, CENSOR_HIGH, RUN_SKIPPED, GS_MISSING. Standalone main() removed from all modules. Deviation: FirstLevelResult dataclass defined in utils.py as part of C8 preparation (pulled forward from C9 spec to resolve circular dependency: C8 needs FirstLevelResult as return type but precedes C9 in execution order).</notes>
    </change>
    <change id="C9" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/run_first_level.py" lines_changed="207" />
        <file path="fmri_first_level_proc/__init__.py" lines_changed="25" />
        <file path="pyproject.toml" lines_changed="2" />
      </files_modified>
      <notes>main() refactored with exception-to-exit-code mapping (6 exit codes: 0, 1, 2, 3, 4, 5). _main_deprecated alias. Dual CLI entry points (fmri-first-level-proc + run-first-level). __init__.py exports updated (ResolvedConfig, FirstLevelResult, graded_warning, load_and_validate, DISPATCH). Old v2 HRF exports removed.</notes>
    </change>
    <change id="C10" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/bids.py" lines_changed="130" />
      </files_modified>
      <notes>BIDS output module with build_bids_output_path (entity ordering sub/ses/task/acq/rec/run/space/desc/stat, sanitize_filename_label) and write_dataset_description (BIDS 1.9.0 derivative JSON, no-op if exists).</notes>
    </change>
    <change id="C11" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/bids.py" lines_changed="120" />
        <file path="fmri_first_level_proc/first_level_config.py" lines_changed="40" />
      </files_modified>
      <notes>DiscoveredInputs dataclass. discover_inputs with BIDS entity pattern matching, multi-directory priority search, DISCOVERY_COLLISION graded_warning. Three-tier resolution integrated into resolve_config. Deviation: discover_inputs returns None for unresolved slots instead of raising InputError directly; resolve_config handles Tier 3 errors after checking explicit config values. This is architecturally correct for three-tier resolution.</notes>
    </change>
    <change id="C12" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/checkpoint.py" lines_changed="330" />
      </files_modified>
      <notes>Processing DAG with JSONL ledger. LedgerEntry dataclass, 4 DAG constants, 5 functions (append_ledger_entry, read_ledger, resolve_rerun_set with cascade invalidation, auto_reconstruct_ledger, compute_config_hash).</notes>
    </change>
    <change id="C13" status="done" user_decision="n/a">
      <files_modified>
        <file path="pyproject.toml" lines_changed="11" />
        <file path="tests/conftest.py" lines_changed="40" />
      </files_modified>
      <notes>8-level pytest marker taxonomy registered. conftest.py factory functions renamed (make_*_args -> make_*_config) and updated to return ResolvedConfig instead of argparse.Namespace/SimpleNamespace.</notes>
    </change>
    <change id="C14" status="done" user_decision="n/a">
      <files_modified>
        <file path="pyproject.toml" lines_changed="1" />
        <file path="fmri_first_level_proc/__init__.py" lines_changed="1" />
      </files_modified>
      <notes>Version bumped from 2.5.0 to 3.0.0. Executed inline.</notes>
    </change>
  </changes_applied>
  <summary>
    <total_changes>14</total_changes>
    <completed>14</completed>
    <skipped>0</skipped>
    <blocked>0</blocked>
  </summary>
  <deviations>
    <deviation change="C8">FirstLevelResult dataclass defined in first_level_utils.py during C8 preparation rather than in C9 as originally specified. Required to resolve circular dependency: C8 run() functions return FirstLevelResult but C8 precedes C9 in execution order.</deviation>
    <deviation change="C11">discover_inputs returns None for unresolved mandatory slots instead of raising InputError directly. resolve_config handles Tier 3 mandatory-miss errors after checking whether an explicit config value covers the slot. This prevents false rejection of valid configurations where a user provides a non-BIDS path for a mandatory slot that has no match in the derivatives directories.</deviation>
  </deviations>
  <files_created>
    <file>fmri_first_level_proc/exceptions.py</file>
    <file>fmri_first_level_proc/runtime.py</file>
    <file>fmri_first_level_proc/bids.py</file>
    <file>fmri_first_level_proc/checkpoint.py</file>
    <file>tools.lock.yaml</file>
  </files_created>
  <files_modified>
    <file>fmri_first_level_proc/first_level_config.py</file>
    <file>fmri_first_level_proc/first_level_utils.py</file>
    <file>fmri_first_level_proc/run_first_level.py</file>
    <file>fmri_first_level_proc/__init__.py</file>
    <file>fmri_first_level_proc/task_act_first_level.py</file>
    <file>fmri_first_level_proc/task_conn_first_level.py</file>
    <file>fmri_first_level_proc/rest_conn_first_level.py</file>
    <file>pyproject.toml</file>
    <file>tests/conftest.py</file>
  </files_modified>
  <next_steps>Recommended: run /test to validate all changes. The existing 460-test suite will need updates to accommodate the v3.0.0 API changes (ResolvedConfig parameter type, exception types instead of sys.exit, graded_warning integration). New tests should cover: BIDS discovery patterns, checkpoint/resume round-trips, graded_warning accumulation, exception-to-exit-code mapping, dual-format events detection, and AFNI version validation.</next_steps>
</implement_report>
