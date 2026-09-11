<test_report>
  <meta project="fmri-first-level-proc" mode="test" timestamp="2026-08-26T12:37:20Z" />
  <pre_design_run>
    <total>677</total>
    <passed>677</passed>
    <failed>0</failed>
    <errors>0</errors>
    <coverage_pct>null</coverage_pct>
    <failures></failures>
  </pre_design_run>
  <failing_test_dispositions>
    <!-- No failures in the pre-design run; no dispositions to record. The 677-test
         baseline reflects the 659-test suite verified in fmri-first-level-proc_test_20260825_194710.md
         plus the 18 tests added by the fmri-first-level-proc_implement_build_20260825_214115.md build
         (warning accumulator lifecycle, ToolVersionError exit-code mapping, scale_to_psc true-path,
         extract_stat_buckets edge cases, stat_buckets rejection-path validation). -->
  </failing_test_dispositions>
  <design_phase>
    <tests_created>4</tests_created>
    <tests_modified>0</tests_modified>
    <files_created>
      <file path="tests/test_config_validation.py" test_count="1" coverage_target="stat_buckets accept-path: valid config resolves ResolvedConfig.stat_buckets and .extract_out_file_pre correctly (the prior build only covered the 4 rejection paths)" />
      <file path="tests/test_task_act_pipeline.py" test_count="1" coverage_target="warning-accumulator leak prevention: run() must call clear_warnings() at entry so a stale warning from a prior caller does not appear in this run's FirstLevelResult.warnings" />
      <file path="tests/test_task_conn_pipeline.py" test_count="1" coverage_target="warning-accumulator leak prevention (task_conn analog of the task_act test above)" />
      <file path="tests/test_rest_conn_pipeline.py" test_count="1" coverage_target="warning-accumulator leak prevention (rest_conn analog of the task_act test above)" />
    </files_created>
    <design_rationale>
      The pre-design run found zero failures, so the design phase investigated the codebase directly
      (per the Test Design Discipline's first-class-peer mandate) rather than routing from disposition
      ledger entries. Candidate gap areas were checked against actual code and existing tests before
      any new test was written: ToolVersionError raise sites in runtime.py were already directly
      unit-tested; Zstat synthesis (fitt_t2z conversion, DOF lookup) in extract_stat_buckets was already
      tested; scale_to_psc AFNI-failure propagation is covered generically by the centralized
      run_afni_command error-wrapping tests and is not a distinct gap. Two genuine gaps were confirmed:
      (1) stat_buckets config validation had 4 rejection-path tests but no accept-path test verifying a
      valid config actually resolves; (2) the module-level _WARNING_ACCUMULATOR's clear_warnings() call
      at each pipeline's run() entry was unit-tested in isolation (via direct graded_warning/get_warnings/
      clear_warnings calls) but never exercised through an actual pipeline run() invocation. Because the
      accumulator is global state, a future refactor that silently dropped a clear_warnings() call would
      leak warnings across pipeline invocations in a batch/orchestrator loop undetected by any existing
      test. One leak-prevention test per pipeline (task_act, task_conn, rest_conn) closes this gap by
      seeding a stale warning before run() and asserting its absence from the returned result.
    </design_rationale>
  </design_phase>
  <post_design_run>
    <total>681</total>
    <passed>681</passed>
    <failed>0</failed>
    <errors>0</errors>
    <coverage_pct>null</coverage_pct>
    <failures></failures>
  </post_design_run>
  <summary>
    <assertions_preserved_or_strengthened>true</assertions_preserved_or_strengthened>
    <bugs_routed_to_implement>0</bugs_routed_to_implement>
    <recommendation>proceed_to_document</recommendation>
  </summary>
  <action_items>
    <!-- None. All 4 designed tests passed against the existing implementation; no product-bug
         dispositions were routed. The v3.1.0-scope feature set (warning accumulator, ToolVersionError,
         PSC scaling, stat_buckets extraction) is now covered by 681/681 passing tests spanning unit,
         config-validation, and pipeline-integration levels. Version bump to v3.1.0 and git commit/tag
         remain outstanding per cross-session item AI-004 (fmri-first-level-proc project memory), unrelated
         to this test pass. -->
  </action_items>
</test_report>
