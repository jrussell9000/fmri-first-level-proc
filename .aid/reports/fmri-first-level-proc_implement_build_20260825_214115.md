<implement_report>
  <meta project="fmri-first-level-proc" mode="implement" submodule="build" timestamp="2026-08-25T21:41:15Z" />
  <spec_ref>fmri-first-level-proc_implement_plan_20260825_213459.md</spec_ref>
  <changes_applied>
    <change id="C1" status="done" user_decision="n/a">
      <files_modified>
        <file path="tests/test_graded_warning.py" lines_changed="49" />
      </files_modified>
      <notes>Added TestWarningAccumulatorLifecycle class with 5 tests: clear-then-get returns empty, graded_warning accumulates across calls (verifies ordering), get_warnings returns a copy (mutation isolation), clear_warnings resets accumulator, cross-pipeline isolation via clear. All tests use clear_warnings() at entry to avoid cross-test contamination from the module-level accumulator.</notes>
    </change>
    <change id="C2" status="done" user_decision="n/a">
      <files_modified>
        <file path="tests/test_runtime.py" lines_changed="29" />
      </files_modified>
      <notes>Added TestMainToolVersionErrorExitCode class with 1 test. Monkeypatches _LOCKFILE_PATH to an existing tmp file (so the exists() gate passes), patches probe_tool_versions to raise ToolVersionError, and asserts SystemExit with code 4. Adapted from the existing TestMainLockfileAbsentResilience pattern.</notes>
    </change>
    <change id="C3" status="done" user_decision="n/a">
      <files_modified>
        <file path="tests/test_scale_to_psc.py" lines_changed="95" />
      </files_modified>
      <notes>Created new test file with TestScaleToPsc class and 5 tests: happy-path verifies 3dTstat + 3dcalc calls and return path, label-appended verifies label appears in filenames, empty-label verifies no double underscore or spurious segments, idempotency verifies early return without AFNI calls when output exists, formula verifies the exact PSC expression. All patches target first_level_utils module namespace (not pipeline modules) because scale_to_psc's internal calls bind to its own module.</notes>
    </change>
    <change id="C4" status="done" user_decision="n/a">
      <files_modified>
        <file path="tests/test_extract_effects.py" lines_changed="120" />
      </files_modified>
      <notes>Added 3 tests to TestExtractStatBucketsWholeBrain: multi-stat-type verifies separate 3dbucket calls and JSON indexes for ["Coef", "Tstat"], idempotency-skip verifies no 3dbucket call when bucket_out exists but JSON index still written, creation-failure verifies ToolExecutionError raised when bucket_out absent after 3dbucket. All use the existing fake_run_afni/fake_3dinfo/fake_exists infrastructure from the class.</notes>
    </change>
    <change id="C5" status="done" user_decision="n/a">
      <files_modified>
        <file path="tests/test_config_validation.py" lines_changed="39" />
      </files_modified>
      <notes>Added TestStatBucketsValidation class with 4 tests: non-list raises ConfigError ("must be a non-empty list"), empty list raises ConfigError ("must be a non-empty list"), invalid type raises ConfigError ("invalid type 'InvalidStat'"), missing extract_out_file_pre raises ConfigError ("missing 'extract_out_file_pre'"). All use the existing _validate(raw) helper which patches os.path.isfile to bypass template_path filesystem checks.</notes>
    </change>
  </changes_applied>
  <summary>
    <total_changes>5</total_changes>
    <completed>5</completed>
    <skipped>0</skipped>
    <blocked>0</blocked>
  </summary>
  <next_steps>Recommended: run /test to validate all changes. The 18 new tests (5 + 1 + 5 + 3 + 4) cover the P1 coverage gaps flagged in the v3.1.0-scope test report (fmri-first-level-proc_test_20260825_194710.md). Expected suite total: 677 tests (659 prior + 18 new).</next_steps>
</implement_report>
