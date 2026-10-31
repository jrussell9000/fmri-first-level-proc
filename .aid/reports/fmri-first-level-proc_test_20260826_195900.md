<test_report>
  <meta project="fmri-first-level-proc" mode="test" timestamp="2026-08-26T19:59:00Z" />
  <pre_design_run>
    <total>681</total>
    <passed>681</passed>
    <failed>0</failed>
    <errors>0</errors>
    <coverage_pct>null</coverage_pct>
    <failures></failures>
  </pre_design_run>
  <failing_test_dispositions>
    <!-- No failures in the pre-design run; no dispositions to record. The 681-test
         baseline confirms the two changes applied by
         fmri-first-level-proc_implement_build_20260826_195800.md (new
         generate_bucket_stats_index() function and its wiring into run()) did not
         regress any existing test, even though every existing task_act pipeline
         test now exercises the new function unconditionally (it is called for
         every run() invocation, not gated behind a config flag). -->
  </failing_test_dispositions>
  <design_phase>
    <tests_created>5</tests_created>
    <tests_modified>0</tests_modified>
    <files_created>
      <file path="tests/test_generate_bucket_stats_index.py" test_count="4" coverage_target="Direct unit tests for generate_bucket_stats_index(): pipe-delimited label parsing into a {label: 0-based index} map, idempotency guard (skips 3dinfo when the index already exists), whitespace/empty-token stripping, and single-label (no-delimiter) input." />
      <file path="tests/test_task_act_pipeline.py" test_count="1" coverage_target="Pipeline integration: run() calls generate_bucket_stats_index() after run_first_level() and includes its returned path in FirstLevelResult.output_files." />
    </files_created>
    <design_rationale>
      The pre-design run passed 681/681 with zero failures, so the design phase
      investigated the codebase directly rather than routing from a disposition
      ledger. The investigation found that generate_bucket_stats_index() (added by
      the prior implement/build pass in response to the user's observation that the
      bucket_stats output needed a sub-brick index analogous to the existing
      {stat}_bucket index JSONs, since individual subjects/sessions can have
      differing sets of surviving conditions and contrasts) had zero dedicated test
      coverage. Critically, the existing pipeline-level tests in
      test_task_act_pipeline.py already exercise the new function on every run()
      call (it is unconditional, not gated by a config flag), and all continued to
      pass without modification -- but this was found to be a false signal, not
      genuine coverage: the generic run_afni_command mock in conftest.py's
      make_pipeline_mocks() returns a bare MagicMock for any command it does not
      specifically recognize (including the new 3dinfo -label call), and
      MagicMock's default __iter__ implementation silently yields an empty
      iterator. This means every existing pipeline test that reached the new
      function produced and wrote an empty {} index without erroring, masking the
      function's actual parsing contract entirely. Two independent proposed gap
      areas were checked and confirmed genuine: (1) no test verified that
      3dinfo -label's pipe-delimited output is correctly parsed into the
      {label: index} map (the core contract, directly analogous to
      test_extract_effects.py's coverage of extract_stat_buckets()'s 3dinfo
      -subbrick_info parsing); (2) no test verified that run() actually wires the
      new function's output into FirstLevelResult.output_files, which is the
      pipeline-level integration point the user's request was specifically about
      (downstream consumers need this key surfaced as a deliverable, not just
      written to disk as a side effect). The new unit test file mirrors the
      established SimpleNamespace + run_afni_command/os.path.exists mocking
      pattern from test_extract_effects.py exactly, including an idempotency test
      (mirroring the {stat}_bucket idempotency guard) and edge cases for
      whitespace/empty-token handling and single-label input (no pipe delimiter
      present). The pipeline integration test patches generate_bucket_stats_index
      directly (following the existing precedent of patching write_onset_file at
      the module level in the same file) to isolate the output_files wiring from
      the parsing logic already covered by the unit tests.
    </design_rationale>
  </design_phase>
  <post_design_run>
    <total>686</total>
    <passed>686</passed>
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
    <!-- None. All 5 designed tests passed against the existing implementation on
         first run; no product-bug dispositions were routed. The bucket_stats
         sub-brick index feature (generate_bucket_stats_index(), wired into
         task_act_first_level.run()) is now covered by 686/686 passing tests
         spanning direct unit-level parsing/idempotency and pipeline-level
         output_files integration. This closes the coverage gap for the change
         applied in fmri-first-level-proc_implement_build_20260826_195800.md.
         Version bump to v3.1.0 and git commit/tag remain outstanding per
         cross-session item AI-004 (fmri-first-level-proc project memory),
         unrelated to this test pass; the bucket_stats index addition should be
         folded into that same outstanding version-bump scope before publish. -->
  </action_items>
</test_report>
