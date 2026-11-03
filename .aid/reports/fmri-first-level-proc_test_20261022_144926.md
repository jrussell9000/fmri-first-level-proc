<test_report>
  <meta project="fmri-first-level-proc" mode="test" timestamp="2026-10-22T14:49:26Z" />
  <spec_ref>Verification audit conducted in this session's prior /brainstorm-mode discussion (no written report; items P2-P5 identified by direct code inspection against the orchestrator's upstream feedback report ABCD_fmri_orchestrator_S3_brainstorm_upstream_20261015_150913.md and this project's 2026-10-16 amendments T1-T6/A1). P1 (U5 documentation) and P6 (D1-D3 GitHub issues) are explicitly deferred per user instruction to a later session, after pipeline/orchestrator harmonization is complete.</spec_ref>

  <pre_design_run>
    <total>677</total>
    <passed>677</passed>
    <failed>0</failed>
    <errors>0</errors>
    <coverage_pct>null</coverage_pct>
    <failures></failures>
  </pre_design_run>

  <failing_test_dispositions>
    <!-- No failures in the pre-design run; this section is empty. -->
  </failing_test_dispositions>

  <design_phase>
    <tests_created>5</tests_created>
    <tests_modified>1</tests_modified>
    <files_created>
      <file path="tests/test_rest_conn_pipeline.py" test_count="1" coverage_target="P2: adds test_concat_mode_fitted_regressor_count_matches_dry_run_assumption to TestRestConnConcatModeGSDerivative. The pre-existing test_concat_mode_dof_matches_per_run_mode compares nuisance.py's dry-run DOF between per-run and concat modes, but rest_nuisance() never reads keep_run_res_dtseries, so its dry run is identical in both modes regardless of whether rest_conn_first_level.py's downstream concat-mode regression correctly builds the GS derivative -ort (the actual U4 regression: concat mode silently omitted GS_deriv while the dry run already counted it). The new test spies on both the dry-run 3dTproject invocation (nuisance.py) and the real, non-dry-run regression invocation (rest_conn_first_level.py's _residual_simultaneous) via unittest.mock.patch with pass-through side_effect, counts -ort occurrences in each, and asserts they match and equal 7 (motion, CSF, WM, GS, CSF_deriv, WM_deriv, GS_deriv) -- the count was 6 before the U4 fix." />
      <file path="tests/test_nuisance.py" test_count="2" coverage_target="P3(a): adds test_rest_fd_computed_from_notch_filtered_motion to TestRestNuisanceSimultaneous. Independently recomputes Power FD (via _power_fd) from the written notch-filtered motion file and compares to the FD series rest_nuisance wrote, and confirms the result differs from the raw-motion FD so the test cannot pass vacuously if notch filtering were bypassed. P3(b): adds new class TestDofDryRunUsesFdCensorFile with test_dry_run_censor_arg_is_the_fd_censor_file, which spies on the dry-run 3dTproject invocation and asserts its -censor argument is the exact path of the FD-based censor file _censor() wrote for that run (confirms wiring, not re-deriving censor-file correctness, which is already covered by TestCensor/TestCensorThresholdStrictness/TestMetricDisagreement)." />
      <file path="tests/test_task_act_pipeline.py" test_count="1" coverage_target="P4 (task_act half): adds new class TestTaskActModeAUnionOfRunsRequiredConditions with test_condition_present_in_only_one_of_two_runs_succeeds, a two-Mode-A-run end-to-end pipeline test (stimA only in run 1's timing file, stimB only in run 2's, both in cond_labels). Asserts the analysis completes (does not raise InputError) and both conditions are actually modeled (present in the 3dDeconvolve bucket-stats sub-brick labels). The design's U2 test list specified task_act and task_conn end-to-end coverage; the only existing coverage was a bare unit test of build_event_table() in test_events.py, not tied to either pipeline." />
      <file path="tests/test_task_conn_pipeline.py" test_count="1" coverage_target="P4 (task_conn half): adds new class TestTaskConnModeAUnionOfRunsRequiredConditions with the task_conn analog of the task_act union test (cond_beta_labels), asserting both per-condition beta-series output files exist. P5 (modification, not a new test): strengthens the existing T5 test test_distractor_confined_to_excluded_run_does_not_leak_or_change_results by adding a direct assertion that the dropped nuisance condition's label is absent from the design matrix's ColumnLabels header (parsed via estimability.parse_x1d on names.bseries_dmat), alongside the pre-existing onset-file-absence and beta-series-identity checks. Purely additive; no prior assertion removed or weakened." />
    </files_created>
    <design_rationale>
      All four items were identified as coverage gaps during a code-level verification of orchestrator feedback implementation (not from a failing pre-design run, since the baseline suite passed 677/677 cleanly). Each gap was the same shape: a test existed and passed, but its assertions did not exercise the property the design report actually specified, either because the two sides of a comparison shared the same code path (P2), because only existence/wiring was checked rather than the actual data transformation (P3), or because the test's scope was narrower than the two analysis types the design named (P4), or because an indirect check (beta-series equality) stood in for a direct one (P5) that was cheap to add once a precedent (estimability.parse_x1d, already used in test_estimability.py) was identified. No disposition ledger was required since none of these were failing-test reclassifications; all are coverage-gap additions per the design submodule's general mandate, consolidated into one Pre-Write Approval message and approved before any file was touched.
    </design_rationale>
  </design_phase>

  <post_design_run>
    <total>682</total>
    <passed>682</passed>
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
    <item priority="P1" target_mode="document" description="U5 documentation corrections (INPUT_SPECIFICATION.md, README.md, example_config.yaml) remain outstanding, deferred per explicit user instruction until the pipeline and the ABCD_fmri_orchestrator_S3 orchestrator are fully harmonized. See prior session's verification list (P1) for the itemized discrepancy list: stale enorm/censor-metric text, stale lockfile schema description, stale remove_previous semantics, undocumented roi_zero_handling/Mode A/run_labels/smoothing, the global-only-key-raises-ConfigError-not-warning mismatch, the missing run-first-level CLI alias, the stale 15-binary list (actual: 19), stale output names, stale QC schema, and the undocumented 13-run caps." />
    <item priority="P2" target_mode="none" description="D1-D3 GitHub issues (all-row timing check on unmodeled conditions; log_nuisance_model singular-paths-only logging; dmBLOCK/-stim_times_IM rejection rule to verify) were never opened, per both the 2026-10-15 orchestrator report and the 2026-10-16 upstream response report's action items. Not in scope for this session." />
    <item priority="P2" target_mode="none" description="Observed during the prior code-level verification, outside the orchestrator feedback's scope, surfaced for a future scope decision (not auto-descoped): (1) stat_bucket_parcellations docstring in task_act_first_level.py still claims it writes index JSONs, which it no longer does. (2) test_censor_high_warning_when_over_50_pct_censored in test_nuisance.py is a conditional assertion (only checks when pct_censored exceeds 50%) and can pass without exercising the warning path. (3) In rest_conn concat mode, a failed run is recorded in failed_runs but not excluded_runs, unlike per-run mode, which records both; predates v4.0.0. (4) task_conn_expected() does not list nuisance onset files in its cross-check set; this is cosmetic since the set is advisory only (ctx.finish's retirement sweep), not an output omission." />
    <item priority="P0" target_mode="none" description="Merge v4.0.0-build to main, tag v4.0.0, and publish once U5 documentation lands. All implement and test work for the Power-FD/U1-U5/T5 change set, including this session's P2-P5 test-coverage strengthening, is complete and verified (682/682 passing, receipt-verified against the real AFNI 26.0.09 environment)." />
  </action_items>
</test_report>
