<test_report>
  <meta project="fmri_first_level_proc" mode="test" timestamp="2026-10-12T15:52:39Z" />
  <pre_design_run>
    <total>633</total>
    <passed>632</passed>
    <failed>1</failed>
    <errors>0</errors>
    <coverage_pct>null</coverage_pct>
    <failures>
      <failure test="TestRestNuisanceSimultaneous::test_over_regressed_run_crashes_instead_of_graceful_exclusion" file="tests/test_nuisance.py" line="264">
        <error_type>ModelError</error_type>
        <message>Every run has DOF &lt; 1: run 1: DOF=-8</message>
        <traceback>fmri_first_level_proc/nuisance.py:585: raise ModelError(f"Every run has DOF &lt; 1: ...", context={"excluded_runs": excluded}) -&gt; ModelError: Every run has DOF &lt; 1: run 1: DOF=-8. Preceding log: WARNING [RUN_SKIPPED] Run 1: DOF=-8 &lt; 1; run excluded.</traceback>
      </failure>
    </failures>
    <receipt_verification>
      <nonce>session-1</nonce>
      <clock>2026-10-12T15:14:33Z (approx, from dispatched run)</clock>
      <checks_passed>receipt-verified via tee file and partition/collect checks matching the dispatched return (632 passed, 1 failed, 633 total, 27 files)</checks_passed>
      <collect_only_oracle>633</collect_only_oracle>
    </receipt_verification>
  </pre_design_run>
  <failing_test_dispositions>
    <disposition test="TestRestNuisanceSimultaneous::test_over_regressed_run_crashes_instead_of_graceful_exclusion" file="tests/test_nuisance.py" classification="obsolete-test">
      <intended_contract>rest_nuisance() excludes a run whose DOF dry run comes back below 1 (reason dof_below_1, RUN_SKIPPED warning) rather than letting the whole analysis crash, per the fix applied this session to fmri_first_level_proc/nuisance.py (the fix this test was originally written to document the absence of, in the preceding /test invocation).</intended_contract>
      <current_test_claim>pytest.raises(ToolExecutionError) around rest_nuisance() for a single over-regressed run.</current_test_claim>
      <evidence>fmri_first_level_proc/nuisance.py now recognizes 3dTproject's "total number of fixed regressors (N) is too many for M retained time points" abort text, computes DOF = M - N, and routes the run through the existing dof_below_1 exclusion path (RUN_SKIPPED warning observed in the failure's captured log). With only one run supplied, excluding it leaves s_pre_labels empty, and the existing "every run has DOF &lt; 1" ModelError fires -- this is the correct, already-existing behavior for the all-runs-excluded case, not a new gap. The test's assertion pinned the pre-fix crash and is now obsolete against the corrected contract.</evidence>
      <action>re-express. Renamed to test_over_regressed_single_run_excluded_then_model_error; now asserts pytest.raises(ModelError, match="DOF &lt; 1") instead of ToolExecutionError. Added a second test, test_over_regressed_run_excluded_other_run_survives, with a two-run config (run 1 over-regressed and excluded with dof=-8, run 2 healthy with dof&gt;0), asserting state["excluded"] == [{"run": 1, "reason": "dof_below_1"}] and runsets.s_pre == (2,) -- this is the graceful single-run exclusion the fix is meant to enable, which the single-run test alone cannot demonstrate. No assertion was weakened; the replacement test is strictly more specific (exact exclusion record and exact DOF sign checks) and the new test adds coverage the prior suite lacked entirely.</action>
    </disposition>
  </failing_test_dispositions>
  <design_phase>
    <tests_created>1</tests_created>
    <tests_modified>1</tests_modified>
    <files_created>
      <file path="tests/test_nuisance.py" test_count="2" coverage_target="Re-expression of the over-regressed single-run case (now ModelError, not a crash) plus a new two-run case proving graceful single-run exclusion with a surviving sibling run." />
    </files_created>
    <design_rationale>This design pass follows directly from the implement build (fmri-first-level-proc_implement_build_20261012_153509.md) that fixed the three bugs routed by the preceding /test invocation (fmri-first-level-proc_test_20261012_151045.md). Scope was limited to the single test file whose assertion pinned the now-fixed crash; no other coverage gap was introduced by the three fixes (connectivity.py's -dem addition and runtime.py's guard split needed no test changes, since tests/test_connectivity.py and tests/test_runtime.py already encoded the correct/intended contracts and simply started passing). The user approved this exact scope (re-express plus one new multi-run test) via the Pre-Write Approval Gate before any file was touched.</design_rationale>
  </design_phase>
  <post_design_run>
    <total>634</total>
    <passed>634</passed>
    <failed>0</failed>
    <errors>0</errors>
    <coverage_pct>null</coverage_pct>
    <failures />
    <receipt_verification>
      <nonce>session-2</nonce>
      <clock>2026-10-12T15:48:21Z</clock>
      <checks_passed>14/14 (nonce, clock, duration, summary, partition, collect_total, total_advisory, collect_files, receipt_file_mtime, receipt_file_nonce, receipt_file_summary, receipt_file_partition, receipt_file_collect_total, receipt_file_collect_files)</checks_passed>
      <collect_only_oracle>634</collect_only_oracle>
    </receipt_verification>
  </post_design_run>
  <summary>
    <assertions_preserved_or_strengthened>true</assertions_preserved_or_strengthened>
    <bugs_routed_to_implement>0</bugs_routed_to_implement>
    <recommendation>proceed_to_document</recommendation>
  </summary>
  <action_items />
  <context>
    This invocation closes out the three product bugs routed to /implement by the preceding full-modernization test session (fmri-first-level-proc_test_20261012_151045.md): the missing -dem flag on connectivity.py's 1ddot call, runtime.py's load_lockfile() AttributeError on a malformed lockfile, and nuisance.py's rest_nuisance() crash on an over-regressed run. All three were fixed by /implement (fmri-first-level-proc_implement_plan_20261012_152847.md / fmri-first-level-proc_implement_build_20261012_153509.md) earlier in this session. The full 634-test suite, including the three real-AFNI pipeline test files and the real-AFNI connectivity/nuisance/runtime unit tests, now passes with zero failures and zero errors. No further test-side gaps were found. v4.0.0 on branch v4.0.0-build is implemented, reviewed, and tested with a clean suite; it has not yet been merged, tagged, or published.
  </context>
</test_report>
