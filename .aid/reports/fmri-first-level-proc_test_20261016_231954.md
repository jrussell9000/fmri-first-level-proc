<test_report>
  <meta project="fmri-first-level-proc" mode="test" timestamp="2026-10-16T23:19:54Z" />
  <spec_ref>fmri-first-level-proc_implement_build_20261016_201148.md</spec_ref>

  <pre_design_run>
    <total>634</total>
    <passed>630</passed>
    <failed>4</failed>
    <errors>0</errors>
    <failures>
      <failure test="TestCensorNaming::test_censor_side_files_pair" file="tests/test_names.py">
        <msg>Asserted censor_side_files("sub01", 2) returned a list including a "_CENSORTR.txt" entry; the C1-updated function no longer includes one.</msg>
      </failure>
      <failure test="TestCensor::test_low_motion_mostly_kept" file="tests/test_nuisance.py">
        <msg>Called _censor(...) expecting a 2-tuple return; the C3-updated function now returns a 3-tuple (censor_vec, fd_series, enorm_series).</msg>
      </failure>
      <failure test="TestCensor::test_high_motion_mostly_censored" file="tests/test_nuisance.py">
        <msg>Same 2-tuple-vs-3-tuple mismatch as test_low_motion_mostly_kept.</msg>
      </failure>
      <failure test="TestCensor::test_rotation_only_spike_censored_under_enorm_but_kept_under_fd" file="tests/test_nuisance.py">
        <msg>Same 2-tuple-vs-3-tuple mismatch; this test's own name and intent (enorm vs. FD metric disagreement) directly anticipates the C3 metric swap it was written against the old interface for.</msg>
      </failure>
    </failures>
  </pre_design_run>

  <failing_test_dispositions>
    <disposition test="TestCensorNaming::test_censor_side_files_pair" classification="obsolete-test">
      <intended_contract>censor_side_files returns the list of per-run motion-QC side-file names associated with a censoring run.</intended_contract>
      <current_test_claim>The list must include a "_CENSORTR.txt" entry (the legacy 1d_tool.py -censor_motion output).</current_test_claim>
      <evidence>Change C1 (implement build 20261016_201148) rewrote censor_side_files to return only [censor_enorm(...), censor_fd(...)], since 1d_tool.py -censor_motion is no longer invoked anywhere in the pipeline (superseded by the Power-FD censoring metric, change C3). No CENSORTR file is produced under v4.0.0.</evidence>
      <action>Re-expressed the assertion to require exactly ["sub01_run2_enorm.1D", "sub01_run2_fd.1D"], with no CENSORTR entry. The postcondition (the function returns exactly the side files the pipeline actually writes) is preserved, not weakened.</action>
    </disposition>
    <disposition test="TestCensor::test_low_motion_mostly_kept" classification="obsolete-test">
      <intended_contract>_censor computes which TRs survive censoring given a motion threshold.</intended_contract>
      <current_test_claim>_censor(...) returns a 2-tuple (censor_vec, <something>).</current_test_claim>
      <evidence>Change C3 rewrote _censor to return (censor_vec, fd_series, enorm_series): the censoring decision plus both the FD series used to make it and the enorm reference series, per the v4.0.0 U1 Power-FD switch. The underlying censoring assertion (most TRs kept under low motion) is unaffected.</evidence>
      <action>Re-expressed the unpacking as censor_vec, fd, enorm = _censor(...), preserving the original censor_vec assertions unchanged.</action>
    </disposition>
    <disposition test="TestCensor::test_high_motion_mostly_censored" classification="obsolete-test">
      <intended_contract>Same as above, for the high-motion case.</intended_contract>
      <current_test_claim>Same 2-tuple unpacking assumption.</current_test_claim>
      <evidence>Same as test_low_motion_mostly_kept.</evidence>
      <action>Re-expressed the unpacking identically; original censor_vec assertions unchanged.</action>
    </disposition>
    <disposition test="TestCensor::test_rotation_only_spike_censored_under_enorm_but_kept_under_fd" classification="obsolete-test">
      <intended_contract>A rotation-only motion spike is flagged by the enorm metric (rotation-unweighted) but not by the Power-FD metric (rotation-weighted at the 50mm sphere radius), demonstrating the two metrics can disagree.</intended_contract>
      <current_test_claim>Same 2-tuple unpacking assumption as the other two; the test's own intent already anticipates the two-metric comparison the C3 rewrite introduces.</current_test_claim>
      <evidence>Change C3 added the enorm_series as the vehicle for exactly this comparison; the test's name and docstring written before C3 already described the intended two-metric contract, and the failure was solely the unpacking arity.</evidence>
      <action>Re-expressed the unpacking as censor_vec, fd, enorm = _censor(...); added the enorm-vs-fd disagreement assertions the test's name already promised.</action>
    </disposition>
  </failing_test_dispositions>

  <design_phase>
    <files>
      <file path="tests/test_names.py" test_count="10" coverage_target="censor_enorm/censor_fd filename helpers; bucket_stats_index/stat_index optional token parameter (C1)" />
      <file path="tests/test_nuisance.py" test_count="12" coverage_target="_power_fd known-answer tests; _summary; censor-threshold strictness; censor_prev_tr run-boundary isolation; enorm reference computation; censor_side_files; enorm/FD metric disagreement (C3)" />
      <file path="tests/test_qc.py" test_count="10" coverage_target="censor_metric/fd_radius_mm/fd_summary/enorm_summary QC_KEYS acceptance, producer-pattern rejection, and insertion order (C2)" />
      <file path="tests/test_events.py" test_count="3" coverage_target="Mode A union-of-runs required-condition check: success, failure, and precedence over per-run timing violations (C4)" />
      <file path="tests/test_task_act_pipeline.py" test_count="2" coverage_target="Smoothed vs. unsmoothed GLM sub-brick labels, bucket_stats_index/stat_index JSON equality, and stat-bucket volume counts (C5); qc_summary censor_metric/fd_radius_mm contract (U1)" />
      <file path="tests/test_task_conn_pipeline.py" test_count="2" coverage_target="A nuisance condition confined to a run excluded before modeling must not leak an onset file, must be logged, and must leave the beta series unaffected (C6); qc_summary censor_metric/fd_radius_mm contract (U1)" />
      <file path="tests/test_rest_conn_pipeline.py" test_count="4" coverage_target="Concat-mode GS-derivative equivalence with per-run mode and matching DOF (C7); sequenced-backend tissue-derivative regressor key collision fix, verified via a call-spy on the real bandpass helper (C8); qc_summary censor_metric/fd_radius_mm contract (U1)" />
    </files>
    <design_rationale>
      Coverage was derived directly from the eight implemented changes' tests_for_test_mode blocks in the tech spec, plus the shared U1 QC-contract requirement (censor_metric/fd_radius_mm present in every analysis type's final qc_summary) that cuts across all three pipelines. Four pre-existing tests required re-expression (see failing_test_dispositions); the remaining 43 tests are new coverage for interface and behavior changes that had no prior test exercising them (confirmed by reading the pre-change test suite before writing: no existing test exercised Mode A's old per-file required-condition enforcement specifically, the sequenced backend's real derivative-regression path end-to-end, or the smoothed/unsmoothed index-equality contract).

      Two test-construction defects were found and corrected during the design phase's own verification, before the authoritative post-design run: (1) a Power-FD boundary test's hand-constructed motion array exercised five columns instead of one between the within-run rows it was comparing, producing a wrong expected value; (2) three new rest_conn tests used too few TRs (60, matching the fixture default) for the regressor set they exercised (GS + tissue derivatives), leaving negative degrees of freedom — empirically re-verified at n=100/150/200/250/300 via a direct, non-AFNI dry-run probe of rest_nuisance before settling on n=200; (3) a new task_act smoothed-extraction test omitted the global.template_path the config schema requires whenever extraction features are present; (4) the task_conn nuisance-condition-confinement test originally regenerated AFNI's unseeded synthetic scan data independently for its two comparison variants, so the "with" and "without" configurations were being compared against two different noise realizations rather than identical inputs sharing only the one intended difference. All four were test-authoring defects, not product defects; each was corrected (the fourth by building the shared scan/motion/timing inputs exactly once and varying only the one file under test) and individually re-verified passing before the authoritative post-design run below.
    </design_rationale>
  </design_phase>

  <post_design_run>
    <total>677</total>
    <passed>677</passed>
    <failed>0</failed>
    <errors>0</errors>
  </post_design_run>

  <summary>
    <assertions_preserved_or_strengthened>true</assertions_preserved_or_strengthened>
    <bugs_routed_to_implement>0</bugs_routed_to_implement>
    <narrative>
      All four pre-design failures were confirmed obsolete-test (test-interface mismatches against the two intentional v4.0.0 interface changes, C1 and C3), not regressions. No product bugs were found in the design phase for any of the eight implemented changes: all eight behave as specified, including the one that most directly risked a silent correctness failure if wrong (C6's nuisance-condition exclusion, where the beta series equivalence test confirmed bit-for-bit identity between the condition-present and condition-absent cases once the test's own comparison methodology was corrected to hold the underlying synthetic data fixed). The suite grew from 634 to 677 tests (43 added, 4 re-expressed), and the full suite passes cleanly: 677/677, 0 failures, 0 errors.
    </narrative>
  </summary>

  <action_items>
    <item priority="P2" target_mode="document" description="Per the implement build report's next_steps: update example_config.yaml's fd_threshold comments and INPUT_SPECIFICATION.md lines 79, 373, 382, and 471 to reflect the Power-FD censoring metric and the removal of the CENSORTR side file (U5 from the brainstorm report)." />
  </action_items>

  <next_steps>Run /document to update example_config.yaml and INPUT_SPECIFICATION.md per the U5 documentation action item above, then proceed to merging v4.0.0-build, tagging, and publishing (no outstanding test or implementation work remains).</next_steps>
</test_report>
