<test_report>
  <meta project="fmri_first_level_proc" mode="test" submodule="run_suite" timestamp="2026-08-13T14:07:00Z" />
  <pre_design_run>
    <total>635</total>
    <passed>596</passed>
    <failed>39</failed>
    <errors>0</errors>
    <coverage_pct>null</coverage_pct>
    <failures>
      <failure test="test_censor_creation.py::test_task_act_censor_before_deconvolve" file="tests/test_censor_creation.py" line="0">
        <error_type>FileNotFoundError</error_type>
        <message>sub01_concat_censor.1D not found</message>
        <traceback>task_act_first_level.py: np.loadtxt(config.censor_path) -&gt; numpy/_datasource.py:529: FileNotFoundError</traceback>
      </failure>
      <failure test="test_error_paths.py::TestAFNIFailurePropagation::test_task_act_deconvolve_failure_propagates" file="tests/test_error_paths.py" line="0">
        <error_type>FileNotFoundError</error_type>
        <message>out/censor.1D not found</message>
        <traceback>task_act_first_level.py: np.loadtxt(config.censor_path) -&gt; numpy/_datasource.py:529: FileNotFoundError</traceback>
      </failure>
      <failure test="test_error_paths.py::TestAFNIFailurePropagation::test_task_conn_deconvolve_failure_propagates" file="tests/test_error_paths.py" line="0">
        <error_type>FileNotFoundError</error_type>
        <message>out/censor.1D not found</message>
        <traceback>task_conn_first_level.py: np.loadtxt(config.censor_path) -&gt; numpy/_datasource.py:529: FileNotFoundError</traceback>
      </failure>
      <failure test="test_robust_survival.py::test_task_act_skips_low_survival_condition" file="tests/test_robust_survival.py" line="0">
        <error_type>FileNotFoundError</error_type>
        <message>out/test_subj_concat_censor.1D not found</message>
        <traceback>task_act_first_level.py: np.loadtxt(config.censor_path) -&gt; numpy/_datasource.py:526: FileNotFoundError</traceback>
      </failure>
      <failure test="test_robust_survival.py::test_task_conn_skips_low_survival_condition" file="tests/test_robust_survival.py" line="0">
        <error_type>FileNotFoundError</error_type>
        <message>out/test_subj_concat_censor.1D not found</message>
        <traceback>task_conn_first_level.py: np.loadtxt(config.censor_path) -&gt; numpy/_datasource.py:526: FileNotFoundError</traceback>
      </failure>
      <failure test="test_task_act_pipeline.py::test_task_act_basic (+4 more in same file)" file="tests/test_task_act_pipeline.py" line="0">
        <error_type>FileNotFoundError</error_type>
        <message>out/test_subj_concat_censor.1D not found (5 tests: test_task_act_basic, test_task_act_with_contrasts, test_task_act_tissue_regressors, test_task_act_tissue_derivs, test_task_act_dmblock_hrf)</message>
        <traceback>task_act_first_level.py: np.loadtxt(config.censor_path) -&gt; numpy/_datasource.py:526: FileNotFoundError</traceback>
      </failure>
      <failure test="test_task_conn_pipeline.py::test_task_conn_design_matrix (+6 more in same file)" file="tests/test_task_conn_pipeline.py" line="0">
        <error_type>FileNotFoundError</error_type>
        <message>out/test_subj_concat_censor.1D not found (7 tests: test_task_conn_design_matrix, test_task_conn_3dlss_called, test_task_conn_condition_split, test_task_conn_always_uses_stim_times_im, test_parcellated_contrast, test_seed_to_voxel_contrast, test_contrast_without_connectivity_warns)</message>
        <traceback>task_conn_first_level.py:762: np.loadtxt(config.censor_path) -&gt; numpy/_datasource.py:526: FileNotFoundError</traceback>
      </failure>
      <failure test="test_utils_unit.py::test_build_hrf_string_custom_requires_string" file="tests/test_utils_unit.py" line="130">
        <error_type>ConfigError</error_type>
        <message>Test expects ValueError; build_hrf_string raises ConfigError: custom_hrf is required when hrf_model='custom'</message>
        <traceback>tests/test_utils_unit.py:130: build_hrf_string('custom') -&gt; first_level_utils.py:481: raise ConfigError(...) -&gt; pytest.raises(ValueError) does not match</traceback>
      </failure>
      <failure test="test_utils_unit.py::test_build_hrf_string_unknown" file="tests/test_utils_unit.py" line="136">
        <error_type>ConfigError</error_type>
        <message>Test expects ValueError; build_hrf_string raises ConfigError: Unknown hrf_model: UNKNOWN_MODEL</message>
        <traceback>tests/test_utils_unit.py:136: build_hrf_string('UNKNOWN_MODEL') -&gt; first_level_utils.py:491: raise ConfigError(...) -&gt; pytest.raises(ValueError) does not match</traceback>
      </failure>
      <failure test="test_v230_regression.py (2 tests) + test_v240_extract_raw_ptseries.py (6 tests) + test_v240_pipeline_integration.py (12 tests)" file="tests/test_v230_regression.py, tests/test_v240_extract_raw_ptseries.py, tests/test_v240_pipeline_integration.py" line="0">
        <error_type>FileNotFoundError</error_type>
        <message>out/test_subj_concat_censor.1D not found (20 tests total across these 3 files, same root cause)</message>
        <traceback>task_act_first_level.py / task_conn_first_level.py: np.loadtxt(config.censor_path) -&gt; numpy/_datasource.py:526: FileNotFoundError</traceback>
      </failure>
    </failures>
  </pre_design_run>
  <failing_test_dispositions>
    <disposition test="37 tests across test_censor_creation.py, test_error_paths.py, test_robust_survival.py, test_task_act_pipeline.py, test_task_conn_pipeline.py, test_v230_regression.py, test_v240_extract_raw_ptseries.py, test_v240_pipeline_integration.py" file="multiple" classification="product-bug">
      <intended_contract>compute_dof() (first_level_utils.py:1449-1487) wraps its own np.loadtxt(censor_path) read in a try/except that gracefully returns None with a logged warning when the censor file is missing or unreadable, rather than raising. This is documented in its own docstring: "or None if the censor file could not be read." Test fixtures across the suite mock AFNI calls and create_censor_file without materializing a real file on disk, relying on this documented resilience.</intended_contract>
      <current_test_claim>These tests exercise the full run() pipeline through mocks and expect execution to proceed (or fail in a controlled, expected way unrelated to censor-file I/O) without a raw, uncaught FileNotFoundError.</current_test_claim>
      <evidence>first_level_utils.py:1471-1476 (compute_dof's pre-existing, unchanged guarded read) versus the current session's new insertion at task_act_first_level.py:705-708 and task_conn_first_level.py:762-765 (censor_data_preflight = np.loadtxt(config.censor_path)), which is unguarded and executes immediately before compute_dof(), duplicating the file read without its resilience contract.</evidence>
      <action>route-to-implement. This is a regression introduced by this session's polort A DOF-preflight insertion (brainstorm T3, implement C2/C3), not a pre-existing defect or a test-fixture gap. No assertion edit performed or warranted.</action>
    </disposition>
    <disposition test="test_build_hrf_string_custom_requires_string, test_build_hrf_string_unknown" file="tests/test_utils_unit.py" classification="obsolete-test">
      <intended_contract>build_hrf_string() raises ConfigError (not ValueError) for invalid custom_hrf or unknown hrf_model, per the explicitly approved v3.0.0 exception-hierarchy migration (brainstorm T4, implemented at first_level_utils.py:481 and 491).</intended_contract>
      <current_test_claim>pytest.raises(ValueError) at tests/test_utils_unit.py:129 and :135, asserting the pre-refactor exception type.</current_test_claim>
      <evidence>fmri_first_level_proc/exceptions.py: ConfigError extends FmriFirstLevelError(Exception), not ValueError, so it is a genuine type mismatch, not a false negative. first_level_utils.py:481,491: raise ConfigError(...). This exception-type change was an explicitly approved decision (brainstorm report T4 item 2; implement plan C1 item 4).</evidence>
      <action>re-express (not yet performed; this was a run_suite-only invocation, no test edits made). Recommended: change both assertions to pytest.raises(ConfigError) and update the two docstrings ("raises ValueError" to "raises ConfigError"). This preserves the postcondition exactly (invalid input still raises) while tracking the approved, more specific exception type — not a weakening.</action>
    </disposition>
  </failing_test_dispositions>
  <design_phase>
    <tests_created>0</tests_created>
    <tests_modified>0</tests_modified>
    <files_created></files_created>
    <design_rationale>Not run. This was a run_suite-only invocation (submodule explicitly specified as "run_suite"); the design submodule was not entered and no test files were edited. The disposition ledger above is provided to make the subsequent /test design pass (or direct re-express) immediately actionable.</design_rationale>
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
    <bugs_routed_to_implement>1</bugs_routed_to_implement>
    <recommendation>implement_fixes</recommendation>
  </summary>
  <action_items>
    <item priority="P0" target_mode="implement" description="Fix the polort A DOF-preflight regression (37 failing tests) by centralizing the censor-file read inside compute_dof() (first_level_utils.py:1449-1487), per user-approved design. Add an optional tr parameter to compute_dof(censor_path, n_regressors, logger, tr=None). When tr is provided, compute n_poly = 1 + int((len(censor_data) * tr) / 150.0) using the censor_data array already loaded inside compute_dof's existing try/except (no second file read), and add n_poly to n_regressors before the DOF check. When tr is omitted, behavior is unchanged from pre-T3. Update the docstring's Parameters and Returns sections to describe the tr parameter and the polort A adjustment. Then update both call sites: task_act_first_level.py:705-709 and task_conn_first_level.py:762-766, deleting the 4-line preflight block (censor_data_preflight/n_trs/n_poly/n_regressors +=) at each site and replacing the compute_dof call with compute_dof(config.censor_path, n_regressors, logger, tr=config.tr). This removes the duplicate, unguarded file read that caused the regression and restores compute_dof's pre-existing graceful-degradation contract for the polort A estimate as well." />
    <item priority="P1" target_mode="test" description="After the above fix lands, re-express tests/test_utils_unit.py:129 and :135 from pytest.raises(ValueError) to pytest.raises(ConfigError), and update the two associated docstrings, per the obsolete-test disposition above. Then re-run the full suite via /test run_suite to confirm 635/635." />
  </action_items>
</test_report>
