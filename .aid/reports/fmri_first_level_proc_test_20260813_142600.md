<test_report>
  <meta project="fmri_first_level_proc" mode="test" submodule="design" timestamp="2026-08-13T14:26:00Z" />
  <pre_design_run>
    <total>635</total>
    <passed>601</passed>
    <failed>34</failed>
    <errors>0</errors>
    <coverage_pct>null</coverage_pct>
    <failures>
      <failure test="34 tests across test_task_act_pipeline.py, test_robust_survival.py, test_task_conn_pipeline.py, test_v230_regression.py, test_v240_extract_raw_ptseries.py, test_v240_pipeline_integration.py" file="multiple" line="0">
        <error_type>TypeError</error_type>
        <message>make_pipeline_mocks.&lt;locals&gt;.fake_compute_dof() got an unexpected keyword argument 'tr' (see fmri_first_level_proc_test_20260813_142200.md for the full per-test enumeration; baseline carried forward unchanged into this design invocation)</message>
        <traceback>task_act_first_level.py:705 or task_conn_first_level.py:762: dof = compute_dof(config.censor_path, n_regressors, logger, tr=config.tr) -&gt; conftest.py:243: def fake_compute_dof(censor_path, n_regressors, logger): [no tr parameter] -&gt; unittest/mock.py:1234: TypeError</traceback>
      </failure>
    </failures>
  </pre_design_run>
  <failing_test_dispositions>
    <disposition test="34 tests across test_task_act_pipeline.py, test_robust_survival.py, test_task_conn_pipeline.py, test_v230_regression.py, test_v240_extract_raw_ptseries.py, test_v240_pipeline_integration.py" file="tests/conftest.py" classification="obsolete-test">
      <intended_contract>The shared fixture factory make_pipeline_mocks() (conftest.py) provides a fake_compute_dof side_effect standing in for first_level_utils.compute_dof() during mocked pipeline runs, returning a generous fixed DOF value so downstream pipeline logic can be exercised without a real censor file. Its calling contract must match compute_dof's actual signature at call sites in task_act_first_level.py and task_conn_first_level.py.</intended_contract>
      <current_test_claim>conftest.py:243 (pre-fix) defined fake_compute_dof(censor_path, n_regressors, logger) with no tr parameter, returning a fixed DOF of 100.</current_test_claim>
      <evidence>compute_dof's signature was changed this session (implement build, approved centralization fix) to compute_dof(censor_path, n_regressors, logger, tr=None); task_act_first_level.py:705 and task_conn_first_level.py:762 call compute_dof(config.censor_path, n_regressors, logger, tr=config.tr). The mock at conftest.py:243 had not been updated to accept the new keyword argument. The production compute_dof change is independently covered and already passing via test_error_paths.py::TestDOFCheck (test_sufficient_dof, test_insufficient_dof, test_zero_dof), none of which use make_pipeline_mocks.</evidence>
      <action>re-express. fake_compute_dof's signature updated to accept tr=None (value ignored; fixed return of 100 unchanged). This restores the mock's calling-contract alignment with the production interface without altering any assertion or postcondition in the 34 affected tests.</action>
    </disposition>
  </failing_test_dispositions>
  <design_phase>
    <tests_created>0</tests_created>
    <tests_modified>1</tests_modified>
    <files_created>
      <file path="tests/conftest.py" test_count="0" coverage_target="Shared fixture re-expression only: fake_compute_dof signature aligned to compute_dof(censor_path, n_regressors, logger, tr=None). No new test cases added; no existing assertions removed or weakened." />
    </files_created>
    <design_rationale>The 34 failures were not a coverage gap but a fixture-contract drift introduced by an approved production signature change earlier this session. The fix scope is limited to the single mock definition at conftest.py:243, since all 34 failing tests route through this one shared fixture factory (make_pipeline_mocks). No new tests were warranted: the new tr-adjustment behavior of compute_dof itself is already exercised directly by test_error_paths.py::TestDOFCheck, which does not use this mock and was unaffected by the regression.</design_rationale>
  </design_phase>
  <post_design_run>
    <total>635</total>
    <passed>635</passed>
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
  </action_items>
</test_report>
