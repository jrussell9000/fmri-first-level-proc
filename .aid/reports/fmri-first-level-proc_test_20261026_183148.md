<test_report>
  <meta project="fmri-first-level-proc" mode="test" timestamp="2026-10-26T18:31:48Z" />
  <spec_ref>fmri-first-level-proc_implement_build_20261026_173241.md (points-left-censoring-abort handling, rest censoring-total scope, and the three cosmetic/docstring/QC fixes it covered); fmri-first-level-proc_brainstorm_20261026_133954.md action item specifying the test targets (points-left abort scenarios, rest-totals scope test, unconditional CENSOR_HIGH assertion).</spec_ref>

  <pre_design_run>
    <total>682</total>
    <passed>682</passed>
    <failed>0</failed>
    <errors>0</errors>
    <coverage_pct>null</coverage_pct>
    <failures></failures>
  </pre_design_run>

  <failing_test_dispositions>
    <!-- No failures in the pre-design run; this section is empty. -->
  </failing_test_dispositions>

  <design_phase>
    <tests_created>3</tests_created>
    <tests_modified>1</tests_modified>
    <files_created>
      <file path="tests/test_nuisance.py" test_count="3" coverage_target="Added to TestRestNuisanceSimultaneous: test_points_left_censoring_abort_excluded_other_run_survives (two-run scenario; run 1 hits 3dTproject's 'only N points left after censoring' abort and is excluded as dof_below_1, run 2 survives into S_pre with positive DOF, and the aborted run's per_run_dof record carries n_stopband_regressors=None / n_stopband_regressors_null_reason=dry_run_aborted_censoring); test_points_left_censoring_abort_all_runs_excluded_raises_model_error (both runs hit the abort, ModelError 'DOF &lt; 1' fires); test_rest_pct_censored_scoped_to_s_pre_not_all_supplied_runs (reuses the first scenario, asserts the reported n_trs_total/n_trs_censored/pct_censored equal the retained run's own per-run figures and differ from an independently-computed all-supplied-runs value, and that per_run_censoring still lists both runs). Also modifies TestTaskNuisance.test_censor_high_warning_when_over_50_pct_censored: removes the conditional guard around the CENSOR_HIGH assertion and adds a preceding unconditional assertion that pct_censored exceeds the threshold." />
    </files_created>
    <design_rationale>
      All three new tests and the one modification were specified directly by the implement build this session just completed and its upstream brainstorm report, not discovered from a failing pre-design run (the baseline passed 682/682 cleanly). Before writing any assertion, each fixture was calibrated against the real codebase and real AFNI 26.0.09 binary rather than assumed: a standalone script exercised the actual _censor() and 3dTproject dry-run call sequence with the existing _spiky_motion helper across run lengths 15-40, confirming it reliably produces zero retained frames and the exact 'only 0 points left after censoring -- cannot continue (need at least 9)' abort text the new parser branch targets (distinct from the pre-existing 'too many fixed regressors' abort, which a different, already-passing fixture exercises). A second standalone run of task_nuisance against the existing CENSOR_HIGH fixture confirmed it currently produces 65.0% censored against the 50.0% threshold, so strengthening that test's conditional assertion to unconditional does not require any fixture change and passes under the already-implemented code. All four new/modified tests were also run locally in isolation (pytest -k) before the formal post-design dispatch, and passed. The modification to the existing CENSOR_HIGH test is a postcondition-strengthening re-expression (the conditional guard never changed what was actually being verified, only whether the verification ran); no existing assertion was weakened, removed, or replaced with a tautology.
    </design_rationale>
  </design_phase>

  <post_design_run>
    <total>685</total>
    <passed>685</passed>
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
    <item priority="P1" target_mode="document" description="U5 documentation corrections (INPUT_SPECIFICATION.md, README.md, example_config.yaml), now also including: the dry_run_aborted_censoring upper-bound note (recorded DOF for an aborted run omits the bandpass stopband-regressor count AFNI never reports before aborting, so it is an upper bound on the true DOF); the rest QC scope notes (n_trs_total/n_trs_censored/pct_censored and fd_summary/enorm_summary cover S_pre, the modeled runs; runs failing regression afterward are listed under failed_runs; per_run_censoring covers every supplied run including DOF-excluded ones). Deferred per standing user instruction until the pipeline and the ABCD_fmri_orchestrator_S3 orchestrator are fully harmonized." />
    <item priority="P2" target_mode="none" description="D1-D3 GitHub issues (all-row timing check on unmodeled conditions; log_nuisance_model singular-paths-only logging; dmBLOCK/-stim_times_IM rejection rule to verify) remain unopened, unchanged from the 2026-10-15 and 2026-10-22 upstream reports' action items. Not in scope for this session." />
    <item priority="P0" target_mode="none" description="This session's full action-item set from the 2026-10-26 brainstorm report is now complete and verified: the points-left-censoring-abort fix (U6), the rest pct_censored S_pre rescoping (U7), the stale stat_bucket_parcellations docstring fix, the concat-mode failed-run propagation into excluded_runs, and the task_conn nuisance-onset expected-set addition were all implemented and independently verified against the modified files; the three new tests and the one strengthened assertion specified for this change set were designed, calibrated against real AFNI 26.0.09, and verified (685/685 passing, receipt-verified against both the pre-design and post-design runs). Merge v4.0.0-build to main, tag v4.0.0, and publish only after U5 documentation lands, per standing user instruction." />
  </action_items>
</test_report>
