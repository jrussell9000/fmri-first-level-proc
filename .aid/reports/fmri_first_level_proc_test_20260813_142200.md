<test_report>
  <meta project="fmri_first_level_proc" mode="test" submodule="run_suite" timestamp="2026-08-13T14:22:00Z" />
  <pre_design_run>
    <total>635</total>
    <passed>601</passed>
    <failed>34</failed>
    <errors>0</errors>
    <coverage_pct>null</coverage_pct>
    <failures>
      <failure test="test_task_act_pipeline.py (5 tests) + test_robust_survival.py (2 tests) + test_task_conn_pipeline.py (7 tests) + test_v230_regression.py (2 tests) + test_v240_extract_raw_ptseries.py (6 tests) + test_v240_pipeline_integration.py (12 tests)" file="multiple" line="0">
        <error_type>TypeError</error_type>
        <message>make_pipeline_mocks.&lt;locals&gt;.fake_compute_dof() got an unexpected keyword argument 'tr' (34 tests total, all routed through the shared make_pipeline_mocks fixture)</message>
        <traceback>task_act_first_level.py:705 or task_conn_first_level.py:762: dof = compute_dof(config.censor_path, n_regressors, logger, tr=config.tr) -&gt; conftest.py:243: def fake_compute_dof(censor_path, n_regressors, logger): [no tr parameter] -&gt; unittest/mock.py:1234: TypeError</traceback>
      </failure>
    </failures>
  </pre_design_run>
  <failing_test_dispositions>
    <disposition test="34 tests across test_task_act_pipeline.py, test_robust_survival.py, test_task_conn_pipeline.py, test_v230_regression.py, test_v240_extract_raw_ptseries.py, test_v240_pipeline_integration.py" file="tests/conftest.py" classification="obsolete-test">
      <intended_contract>The shared fixture factory make_pipeline_mocks() (conftest.py) provides a fake_compute_dof side_effect that stands in for first_level_utils.compute_dof() during mocked pipeline runs, returning a generous fixed DOF value so downstream pipeline logic can be exercised without a real censor file. Its calling contract must match compute_dof's actual signature at call sites in task_act_first_level.py and task_conn_first_level.py.</intended_contract>
      <current_test_claim>conftest.py:243 defines fake_compute_dof(censor_path, n_regressors, logger) with no tr parameter, and returns a fixed DOF of 100.</current_test_claim>
      <evidence>compute_dof's signature was changed this session (implement build, approved centralization fix) to compute_dof(censor_path, n_regressors, logger, tr=None); task_act_first_level.py:705 and task_conn_first_level.py:762 now call compute_dof(config.censor_path, n_regressors, logger, tr=config.tr). The shared mock at conftest.py:243 was not updated to accept the new keyword argument, so every test using make_pipeline_mocks() (which patches compute_dof with this side_effect) raises TypeError on the first pipeline call that reaches the DOF check.</evidence>
      <action>route-to-test-design. The mock's calling contract is out of sync with the production interface it doubles; re-expression (adding tr=None to fake_compute_dof's signature, with the value ignored — the fixed-DOF-100 return behavior is unchanged) resolves all 34 failures without weakening any assertion. This is a fixture update, not a product defect: the production compute_dof change itself is correct and already covered by the passing tests in test_error_paths.py::TestDOFCheck (test_sufficient_dof, test_insufficient_dof, test_zero_dof), none of which use make_pipeline_mocks and all of which passed in this run.</action>
    </disposition>
  </failing_test_dispositions>
  <design_phase>
    <tests_created>0</tests_created>
    <tests_modified>0</tests_modified>
    <files_created></files_created>
    <design_rationale>Not run. This was a run_suite-only invocation (submodule explicitly specified as "run_suite"); the design submodule was not entered and no test files were edited. The disposition above is provided to make a subsequent /test design pass (or direct re-express) immediately actionable.</design_rationale>
  </design_phase>
  <post_design_run>
    <total></total>
    <passed></passed>
    <failed></failed>
    <errors></errors>
    <coverage_pct></coverage_pct>
    <failures></failures>
  </post_design_run>
  <summary>
    <assertions_preserved_or_strengthened>true</assertions_preserved_or_strengthened>
    <bugs_routed_to_implement>0</bugs_routed_to_implement>
    <recommendation>implement_fixes</recommendation>
  </summary>
  <action_items>
    <item priority="P0" target_mode="test" description="Re-express tests/conftest.py:243 fake_compute_dof(censor_path, n_regressors, logger) to fake_compute_dof(censor_path, n_regressors, logger, tr=None), per the obsolete-test disposition above. The tr parameter is accepted and ignored; the fixed return value of 100 is unchanged. This is a design-submodule edit (tests/ only) and resolves all 34 failing tests routed through make_pipeline_mocks(). Re-run /test run_suite afterward to confirm 635/635." />
  </action_items>
</test_report>
