<implement_plan>
  <meta project="fmri-first-level-proc" mode="implement" submodule="plan" timestamp="2026-08-25T21:34:59Z" />
  <input_reports>
    <report path="fmri-first-level-proc_test_20260825_194710.md" mode="test" key_items="1" />
  </input_reports>

  <assumptions>
    None. All 5 coverage areas are explicitly enumerated in the test report's P1 action item.
    All changes target tests/ only (new-feature test coverage). No source-file modifications.
  </assumptions>

  <changes>
    <change id="C1" priority="P1" source_item="test_report action_item[0], area (1)">
      <file path="tests/test_graded_warning.py" action="modify" />
      <description>Add warning accumulator lifecycle tests. The existing file tests graded_warning's return contract and logging level dispatch but does not test the module-level _WARNING_ACCUMULATOR, get_warnings(), or clear_warnings(). These three functions form the cross-pipeline warning lifecycle contract: each pipeline's run() calls clear_warnings() at entry, graded_warning() accumulates during execution, and get_warnings() collects the results into FirstLevelResult.warnings at exit.</description>
      <spec>
Add a new test class TestWarningAccumulatorLifecycle to tests/test_graded_warning.py with the following tests:

1. test_clear_then_get_returns_empty:
   - Call clear_warnings(), then get_warnings().
   - Assert result is [].

2. test_graded_warning_accumulates_across_calls:
   - Call clear_warnings().
   - Call graded_warning() 3 times with different codes ("A", "B", "C").
   - Call get_warnings().
   - Assert len == 3 and codes match ["A", "B", "C"] in order.

3. test_get_warnings_returns_copy:
   - Call clear_warnings(), then graded_warning() once.
   - Call get_warnings(), mutate the returned list (append a dict).
   - Call get_warnings() again.
   - Assert the second call's length is 1 (not 2), proving the copy contract.

4. test_clear_warnings_resets_accumulator:
   - Call clear_warnings(), then graded_warning() twice.
   - Call clear_warnings() again.
   - Call get_warnings().
   - Assert result is [].

5. test_cross_pipeline_isolation_via_clear:
   - Call clear_warnings(), then graded_warning() with code "PIPELINE_A".
   - Call clear_warnings() (simulating a second pipeline's entry).
   - Call graded_warning() with code "PIPELINE_B".
   - Call get_warnings().
   - Assert len == 1 and code == "PIPELINE_B" (PIPELINE_A is gone).

Import get_warnings and clear_warnings from fmri_first_level_proc.first_level_utils.
Each test must call clear_warnings() at the start to ensure test isolation (since the accumulator is module-level global state).
      </spec>
      <dependencies>none</dependencies>
      <risk>low - pure unit tests on module-level functions with no I/O</risk>
      <rollback>Remove the TestWarningAccumulatorLifecycle class from test_graded_warning.py</rollback>
    </change>

    <change id="C2" priority="P1" source_item="test_report action_item[0], area (2)">
      <file path="tests/test_runtime.py" action="modify" />
      <description>Add ToolVersionError exit-code-4 mapping test. The existing TestMainLockfileAbsentResilience class tests the lockfile-absent path in run_first_level.main() but no test verifies that a ToolVersionError raised during probe_tool_versions produces sys.exit(4). The catch clause at run_first_level.py:209 groups ToolUnavailableError, ToolVersionError, and ToolExecutionError under exit code 4.</description>
      <spec>
Add a new test class TestMainToolVersionErrorExitCode to tests/test_runtime.py with 1 test:

1. test_tool_version_error_exits_with_code_4:
   - Use the same monkeypatch pattern as TestMainLockfileAbsentResilience.
   - monkeypatch _LOCKFILE_PATH to a real tmp_path file (so .exists() is True).
   - monkeypatch preflight_tool_environments to no-op.
   - monkeypatch probe_tool_versions to raise ToolVersionError("AFNI: expected 26.0.09, got 25.0.01").
   - monkeypatch sys.argv to ["fmri-first-level-proc", "--config", "/fake/config.yaml"].
   - Call main() within pytest.raises(SystemExit) as exc_info.
   - Assert exc_info.value.code == 4.

Import main from fmri_first_level_proc.run_first_level.
Import ToolVersionError from fmri_first_level_proc.exceptions (already imported in the file).
      </spec>
      <dependencies>none</dependencies>
      <risk>low - monkeypatched unit test, no I/O, no subprocess</risk>
      <rollback>Remove the TestMainToolVersionErrorExitCode class from test_runtime.py</rollback>
    </change>

    <change id="C3" priority="P1" source_item="test_report action_item[0], area (3)">
      <file path="tests/test_scale_to_psc.py" action="create" />
      <description>Add scale_to_psc unit tests. No existing test exercises the true-path of scale_to_psc (first_level_utils.py:1433). The function has three behavioral branches: (a) idempotency guard (psc_path already exists, returns early without AFNI calls), (b) happy path with non-empty label, (c) happy path with empty label. It also integrates into all three pipeline run() functions via config.scale_to_psc.</description>
      <spec>
Create tests/test_scale_to_psc.py with:

MODULE = "fmri_first_level_proc.first_level_utils"

Import scale_to_psc from fmri_first_level_proc.first_level_utils.

class TestScaleToPsc:

1. test_happy_path_calls_3dtstat_and_3dcalc:
   - Patch MODULE.run_afni_command to capture calls, MODULE.os.path.exists to return False for psc_path and True otherwise.
   - Call scale_to_psc("/fake/scan.nii.gz", "/fake/out", "subj01", "", logger).
   - Assert 2 AFNI calls: first is 3dTstat with -mean, second is 3dcalc with the PSC expression.
   - Assert the -prefix arguments construct correct paths: subj01_mean.nii.gz and subj01_psc.nii.gz.
   - Assert return value is the psc_path.

2. test_label_appended_to_filenames:
   - Same patch pattern.
   - Call scale_to_psc("/fake/scan.nii.gz", "/fake/out", "subj01", "run1", logger).
   - Assert -prefix paths are subj01_run1_mean.nii.gz and subj01_run1_psc.nii.gz.
   - Assert return value includes "run1_psc".

3. test_empty_label_no_label_segment:
   - Same patch pattern, label="".
   - Assert -prefix paths are subj01_mean.nii.gz and subj01_psc.nii.gz (no double underscore, no "run" segment).

4. test_idempotency_returns_existing_without_afni_calls:
   - Patch MODULE.os.path.exists to return True for the psc_path.
   - Patch MODULE.run_afni_command to capture calls.
   - Call scale_to_psc.
   - Assert run_afni_command was never called.
   - Assert return value is the psc_path.

5. test_3dcalc_expr_contains_psc_formula:
   - From the happy-path captured calls, extract the 3dcalc command.
   - Assert "min(200,a/b*100)*step(a)*step(b)" is in the -expr argument.

Use logging.getLogger("test_scale_to_psc") as the logger fixture.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - isolated unit tests with mocked AFNI I/O</risk>
      <rollback>Delete tests/test_scale_to_psc.py</rollback>
    </change>

    <change id="C4" priority="P1" source_item="test_report action_item[0], area (4)">
      <file path="tests/test_extract_effects.py" action="modify" />
      <description>Add extract_stat_buckets edge-case tests beyond the prior pass's coverage. Current tests cover single-stat-type extraction (Tstat, Zstat, Fstat-no-match), parcellated CSV, and residuals. Missing: (a) multiple stat types in one call, (b) idempotency skip when bucket_out already exists, (c) ToolExecutionError when 3dbucket fails to produce output.</description>
      <spec>
Add 3 tests to the existing TestExtractStatBucketsWholeBrain class in tests/test_extract_effects.py:

1. test_multiple_stat_types_produces_separate_buckets:
   - config with stat_buckets=["Coef", "Tstat"].
   - BUCKET_INFO contains both Coef and Tstat tokens (the existing constant already has both).
   - Assert 2 separate 3dbucket calls (one per stat type).
   - Assert output_files contains both bucket paths and both index paths.
   - Assert both JSON index files exist and are independently correct.

2. test_existing_bucket_skips_3dbucket_but_writes_index:
   - config with stat_buckets=["Tstat"].
   - fake_exists returns True for bucket_out (simulating a pre-existing bucket file).
   - Assert no 3dbucket command was called.
   - Assert output_files still includes bucket_out (it is appended even when skipped).
   - Assert the JSON index file is still written (the index is always regenerated regardless of bucket idempotency).

3. test_bucket_creation_failure_raises_tool_execution_error:
   - config with stat_buckets=["Tstat"].
   - fake_exists returns False for bucket_out even after 3dbucket runs (simulating a write failure).
   - Assert pytest.raises(ToolExecutionError) with a match on "Failed to create".

The BUCKET_INFO and _make_config helpers are already in the file and can be reused directly.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - extends existing test class with mocked I/O</risk>
      <rollback>Remove the 3 new test methods from TestExtractStatBucketsWholeBrain</rollback>
    </change>

    <change id="C5" priority="P1" source_item="test_report action_item[0], area (5)">
      <file path="tests/test_config_validation.py" action="modify" />
      <description>Add stat_buckets config validation rejection tests. The extraction validation at first_level_config.py:501-518 has 3 rejection paths: (a) stat_buckets is not a list or is empty (line 507-509), (b) stat_buckets contains an invalid type (lines 510-514), (c) extract_out_file_pre missing when stat_buckets is set (lines 515-518). No existing test exercises these paths.</description>
      <spec>
Add a new test class TestStatBucketsValidation to tests/test_config_validation.py with 4 tests. All use the existing _base_config("task_act") helper and patch os.path.isfile to return True (the template_path validation at line 552 calls os.path.isfile and would otherwise raise InputError before reaching the extraction checks).

1. test_stat_buckets_non_list_raises_config_error:
   - Set extraction.stat_buckets to "Tstat" (a string, not a list).
   - Assert pytest.raises(ConfigError, match="must be a non-empty list").

2. test_stat_buckets_empty_list_raises_config_error:
   - Set extraction.stat_buckets to [].
   - Assert pytest.raises(ConfigError, match="must be a non-empty list").

3. test_stat_buckets_invalid_type_raises_config_error:
   - Set extraction.stat_buckets to ["InvalidStat"] with extract_out_file_pre set.
   - Assert pytest.raises(ConfigError, match="invalid type 'InvalidStat'").

4. test_stat_buckets_missing_extract_out_file_pre_raises_config_error:
   - Set extraction.stat_buckets to ["Tstat"] but do NOT include extract_out_file_pre.
   - Assert pytest.raises(ConfigError, match="missing 'extract_out_file_pre'").

All tests call validate_config(raw, logger) (already imported) after constructing the raw config dict. The _base_config helper already produces a raw config dict suitable for validate_config.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - config validation unit tests, no I/O beyond os.path.isfile mock</risk>
      <rollback>Remove the TestStatBucketsValidation class from test_config_validation.py</rollback>
    </change>
  </changes>

  <execution_order>C1, C2, C3, C4, C5</execution_order>
</implement_plan>
