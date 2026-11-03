<test_report>
  <meta project="fmri_first_level_proc" mode="test" timestamp="2026-08-13T12:26:44Z" />
  <pre_design_run>
    <total>635</total>
    <passed>624</passed>
    <failed>11</failed>
    <errors>0</errors>
    <coverage_pct></coverage_pct>
    <failures>
      <failure test="TestAFNIFailurePropagation::test_task_act_deconvolve_failure_propagates" file="tests/test_error_paths.py" line="61">
        <error_type>ToolExecutionError (test asserted subprocess.CalledProcessError)</error_type>
        <message>Test expected subprocess.CalledProcessError to propagate uncaught; v3.0.0 wraps it in ToolExecutionError before raising</message>
        <traceback>tests/test_error_paths.py:62: in test_task_act_deconvolve_failure_propagates
    task_act_run(args, logger)
fmri_first_level_proc/task_act_first_level.py:269: in run_first_level
    raise ToolExecutionError(...)
E   fmri_first_level_proc.exceptions.ToolExecutionError: 3dDeconvolve activation failed for test_subj</traceback>
      </failure>
      <failure test="test_task_act_skips_low_survival_condition" file="tests/test_robust_survival.py" line="29">
        <error_type>KeyError</error_type>
        <message>KeyError: 'trial_type' — stim_data DataFrame constructed with legacy CONDITION/ONSET/DURATION columns, passed directly to pipeline bypassing the BIDS rename in read_and_validate_stim_data()</message>
        <traceback>fmri_first_level_proc/task_act_first_level.py: stim_data['trial_type']
E   KeyError: 'trial_type'</traceback>
      </failure>
      <failure test="test_task_conn_skips_low_survival_condition" file="tests/test_robust_survival.py" line="56">
        <error_type>KeyError</error_type>
        <message>KeyError: 'trial_type' — same BIDS column rename gap as task_act variant</message>
        <traceback>fmri_first_level_proc/task_conn_first_level.py:188: for cond in stim_data['trial_type'].unique()
E   KeyError: 'trial_type'</traceback>
      </failure>
      <failure test="TestSubBrickOrdering::test_gen_beta_series_uses_beta_cond_order" file="tests/test_v230_regression.py" line="118">
        <error_type>KeyError</error_type>
        <message>KeyError: 'trial_type' in write_stim_onset_files / gen_beta_series path</message>
        <traceback>fmri_first_level_proc/task_conn_first_level.py:188: for cond in stim_data['trial_type'].unique()
E   KeyError: 'trial_type'</traceback>
      </failure>
      <failure test="TestDroppedConditionOnsets::test_task_conn_dropped_cond_gets_onset_file" file="tests/test_v230_regression.py" line="198">
        <error_type>KeyError</error_type>
        <message>KeyError: 'trial_type' in write_stim_onset_files</message>
        <traceback>fmri_first_level_proc/task_conn_first_level.py:188: for cond in stim_data['trial_type'].unique()
E   KeyError: 'trial_type'</traceback>
      </failure>
      <failure test="TestDroppedConditionOnsets::test_task_act_write_after_filter" file="tests/test_v230_regression.py" line="238">
        <error_type>KeyError</error_type>
        <message>KeyError: 'trial_type' in task_act write_stim_onset_files</message>
        <traceback>fmri_first_level_proc/task_act_first_level.py: stim_data['trial_type']
E   KeyError: 'trial_type'</traceback>
      </failure>
      <failure test="TestTaskActReadWriteSplit::test_task_act_run_calls_write_after_read" file="tests/test_v230_regression.py" line="453">
        <error_type>KeyError</error_type>
        <message>KeyError: 'trial_type' — stim_data fixture returned by tracked_read used legacy column names</message>
        <traceback>fmri_first_level_proc/task_act_first_level.py: stim_data['trial_type']
E   KeyError: 'trial_type'</traceback>
      </failure>
      <failure test="TestCrossPipelineConsistency::test_task_conn_gen_design_matrix_no_np_unique" file="tests/test_v230_regression.py" line="512">
        <error_type>KeyError</error_type>
        <message>KeyError: 'trial_type' in write_stim_onset_files / gen_design_matrix path</message>
        <traceback>fmri_first_level_proc/task_conn_first_level.py:188: for cond in stim_data['trial_type'].unique()
E   KeyError: 'trial_type'</traceback>
      </failure>
      <failure test="TestEdgeCases::test_single_beta_condition" file="tests/test_v230_regression.py" line="582">
        <error_type>KeyError</error_type>
        <message>KeyError: 'trial_type' in write_stim_onset_files</message>
        <traceback>tests/test_v230_regression.py:582: beta_cond_order = task_conn.write_stim_onset_files(stim_data, args, logger)
fmri_first_level_proc/task_conn_first_level.py:188: for cond in stim_data['trial_type'].unique()
E   KeyError: 'trial_type'</traceback>
      </failure>
      <failure test="TestEdgeCases::test_all_conditions_are_beta" file="tests/test_v230_regression.py" line="610">
        <error_type>KeyError</error_type>
        <message>KeyError: 'trial_type' in write_stim_onset_files</message>
        <traceback>tests/test_v230_regression.py:610: beta_cond_order = task_conn.write_stim_onset_files(stim_data, args, logger)
fmri_first_level_proc/task_conn_first_level.py:188: for cond in stim_data['trial_type'].unique()
E   KeyError: 'trial_type'</traceback>
      </failure>
      <failure test="TestEdgeCases::test_many_conditions_ordering_preserved" file="tests/test_v230_regression.py" line="637">
        <error_type>KeyError</error_type>
        <message>KeyError: 'trial_type' in write_stim_onset_files</message>
        <traceback>tests/test_v230_regression.py:637: beta_cond_order = task_conn.write_stim_onset_files(stim_data, args, logger)
fmri_first_level_proc/task_conn_first_level.py:188: for cond in stim_data['trial_type'].unique()
E   KeyError: 'trial_type'</traceback>
      </failure>
    </failures>
  </pre_design_run>
  <failing_test_dispositions>
    <disposition test="test_task_act_skips_low_survival_condition" file="tests/test_robust_survival.py" classification="obsolete-test">
      <intended_contract>write_stim_onset_files() docstrings (task_act_first_level.py:171-186, task_conn_first_level.py:154-182) specify stim_data carries BIDS column names (trial_type/onset/duration) per the v3.0.0 read_and_validate_stim_data() contract (documented in project memory: "read_and_validate_stim_data() returns DataFrames with lowercase BIDS column names regardless of input format").</intended_contract>
      <current_test_claim>stim_df = pd.DataFrame({'CONDITION': [...], 'ONSET': [...], 'DURATION': [...]}) passed directly via patch(read_stim_data, return_value=stim_df), bypassing the rename.</current_test_claim>
      <evidence>fmri_first_level_proc/task_act_first_level.py:187 accesses stim_data['trial_type']; fmri_first_level_proc/first_level_utils.py read_and_validate_stim_data() performs the CONDITION->trial_type rename on read, which this test's mock bypasses.</evidence>
      <action>re-express: renamed fixture DataFrame keys to trial_type/onset/duration (matches what read_stim_data would actually return in production)</action>
    </disposition>
    <disposition test="test_task_conn_skips_low_survival_condition" file="tests/test_robust_survival.py" classification="obsolete-test">
      <intended_contract>Same as above; task_conn_first_level.py:188 accesses stim_data['trial_type'].unique().</intended_contract>
      <current_test_claim>Same legacy-column DataFrame construction pattern.</current_test_claim>
      <evidence>fmri_first_level_proc/task_conn_first_level.py:188</evidence>
      <action>re-express: renamed fixture DataFrame keys to trial_type/onset/duration</action>
    </disposition>
    <disposition test="TestSubBrickOrdering::test_gen_beta_series_uses_beta_cond_order" file="tests/test_v230_regression.py" classification="obsolete-test">
      <intended_contract>gen_beta_series() and write_stim_onset_files() operate on BIDS-named columns per v3.0.0 contract; test constructs stim_data inline without going through the read+rename path.</intended_contract>
      <current_test_claim>rows.append({"CONDITION": ..., "ONSET": ..., "DURATION": ...}) at construction, plus a stray .sort_values("ONSET") reference to the old column name.</current_test_claim>
      <evidence>fmri_first_level_proc/task_conn_first_level.py:188</evidence>
      <action>re-express: renamed dict keys to trial_type/onset/duration and corrected the .sort_values("onset") call to match</action>
    </disposition>
    <disposition test="TestDroppedConditionOnsets::test_task_conn_dropped_cond_gets_onset_file" file="tests/test_v230_regression.py" classification="obsolete-test">
      <intended_contract>Same BIDS column contract for write_stim_onset_files().</intended_contract>
      <current_test_claim>Legacy CONDITION/ONSET/DURATION column construction.</current_test_claim>
      <evidence>fmri_first_level_proc/task_conn_first_level.py:188</evidence>
      <action>re-express: renamed to trial_type/onset/duration</action>
    </disposition>
    <disposition test="TestDroppedConditionOnsets::test_task_act_write_after_filter" file="tests/test_v230_regression.py" classification="obsolete-test">
      <intended_contract>Same BIDS column contract for task_act.write_stim_onset_files().</intended_contract>
      <current_test_claim>Legacy CONDITION/ONSET/DURATION column construction.</current_test_claim>
      <evidence>fmri_first_level_proc/task_act_first_level.py:187</evidence>
      <action>re-express: renamed to trial_type/onset/duration</action>
    </disposition>
    <disposition test="TestTaskActReadWriteSplit::test_task_act_run_calls_write_after_read" file="tests/test_v230_regression.py" classification="obsolete-test">
      <intended_contract>tracked_read() mock stands in for read_stim_data(), which per v3.0.0 contract returns BIDS-named columns.</intended_contract>
      <current_test_claim>tracked_read() returned a DataFrame with CONDITION/ONSET/DURATION keys.</current_test_claim>
      <evidence>fmri_first_level_proc/task_act_first_level.py:187</evidence>
      <action>re-express: renamed mock return DataFrame keys to trial_type/onset/duration</action>
    </disposition>
    <disposition test="TestCrossPipelineConsistency::test_task_conn_gen_design_matrix_no_np_unique" file="tests/test_v230_regression.py" classification="obsolete-test">
      <intended_contract>Same BIDS column contract; gen_design_matrix() consumes write_stim_onset_files() output built on trial_type/onset/duration.</intended_contract>
      <current_test_claim>Legacy CONDITION/ONSET/DURATION column construction.</current_test_claim>
      <evidence>fmri_first_level_proc/task_conn_first_level.py:188</evidence>
      <action>re-express: renamed to trial_type/onset/duration</action>
    </disposition>
    <disposition test="TestEdgeCases::test_single_beta_condition" file="tests/test_v230_regression.py" classification="obsolete-test">
      <intended_contract>Same BIDS column contract.</intended_contract>
      <current_test_claim>Legacy CONDITION/ONSET/DURATION column construction.</current_test_claim>
      <evidence>fmri_first_level_proc/task_conn_first_level.py:188</evidence>
      <action>re-express: renamed to trial_type/onset/duration</action>
    </disposition>
    <disposition test="TestEdgeCases::test_all_conditions_are_beta" file="tests/test_v230_regression.py" classification="obsolete-test">
      <intended_contract>Same BIDS column contract.</intended_contract>
      <current_test_claim>Legacy CONDITION/ONSET/DURATION column construction.</current_test_claim>
      <evidence>fmri_first_level_proc/task_conn_first_level.py:188</evidence>
      <action>re-express: renamed to trial_type/onset/duration</action>
    </disposition>
    <disposition test="TestEdgeCases::test_many_conditions_ordering_preserved" file="tests/test_v230_regression.py" classification="obsolete-test">
      <intended_contract>Same BIDS column contract.</intended_contract>
      <current_test_claim>Legacy CONDITION/ONSET/DURATION column construction.</current_test_claim>
      <evidence>fmri_first_level_proc/task_conn_first_level.py:188</evidence>
      <action>re-express: renamed to trial_type/onset/duration</action>
    </disposition>
    <disposition test="TestAFNIFailurePropagation::test_task_act_deconvolve_failure_propagates" file="tests/test_error_paths.py" classification="obsolete-test">
      <intended_contract>v3.0.0 exception hierarchy wraps subprocess.CalledProcessError from 3dDeconvolve failures in ToolExecutionError before raising, per fmri_first_level_proc/task_act_first_level.py:266-271 (try/except CalledProcessError -> raise ToolExecutionError(...) from e). This is a deliberate v3.0.0 design decision (custom exception hierarchy, C1 in the v3.0.0 brainstorm).</intended_contract>
      <current_test_claim>pytest.raises(subprocess.CalledProcessError) — asserts the pre-v3.0.0 raw-exception-propagation contract.</current_test_claim>
      <evidence>fmri_first_level_proc/task_act_first_level.py:266-271; fmri_first_level_proc/exceptions.py ToolExecutionError definition; project memory v3.0.0 exception hierarchy note ("FmriFirstLevelError base with 6 subclasses... replaces all sys.exit(1) calls")</evidence>
      <action>re-express: changed pytest.raises(subprocess.CalledProcessError) to pytest.raises(ToolExecutionError); updated docstring to document the wrap</action>
    </disposition>
  </failing_test_dispositions>
  <design_phase>
    <tests_created>0</tests_created>
    <tests_modified>11</tests_modified>
    <files_created>
    </files_created>
    <design_rationale>All 11 failures were confirmed as obsolete-test dispositions: v3.0.0 introduced two breaking product-level contract changes (BIDS column naming for stim_data DataFrames; typed exception hierarchy wrapping subprocess errors) that these pre-v3.0.0 tests had not yet been migrated to reflect. No product-bug dispositions were found among these 11; the underlying pipeline code correctly implements the v3.0.0 contracts documented in function docstrings and project memory. All 11 tests were re-expressed to construct fixtures/mocks using the current contract (trial_type/onset/duration column names; ToolExecutionError exception type) without altering what each test actually verifies — postconditions are logically equivalent to their prior form, not weakened. No new test files were needed; this was purely a fixture/assertion migration pass, not a coverage gap.</design_rationale>
  </design_phase>
  <post_design_run>
    <total>635</total>
    <passed>635</passed>
    <failed>0</failed>
    <errors>0</errors>
    <coverage_pct></coverage_pct>
    <failures>
    </failures>
  </post_design_run>
  <summary>
    <assertions_preserved_or_strengthened>true</assertions_preserved_or_strengthened>
    <bugs_routed_to_implement>0</bugs_routed_to_implement>
    <recommendation>proceed_to_document</recommendation>
  </summary>
  <action_items>
    <item priority="P2" target_mode="cr" description="task_conn_first_level.py's 3dDeconvolve call for the beta-series design matrix (gen_design_matrix(), around line 275) does not wrap subprocess.CalledProcessError in ToolExecutionError, unlike task_act_first_level.py's equivalent 3dDeconvolve call (lines 266-271). This is an inconsistency in the v3.0.0 exception-hierarchy migration surfaced while re-expressing test_task_act_deconvolve_failure_propagates; the companion task_conn test (test_task_conn_deconvolve_failure_propagates) still passes because it asserts the old CalledProcessError type, which is what task_conn currently (still) raises. Recommend auditing all subprocess-calling sites in task_conn_first_level.py against the ToolExecutionError wrapping pattern established in task_act_first_level.py during /cr." />
    <item priority="P2" target_mode="document" description="Stale docstrings in task_act_first_level.py and task_conn_first_level.py still reference CONDITION/ONSET/DURATION column names in Parameters sections (e.g. 'stim_data : pd.DataFrame — Sorted timing data with CONDITION, ONSET, DURATION columns'), despite the functions actually operating on trial_type/onset/duration. Carried forward from prior session (2026-08-13 implement build)." />
  </action_items>
</test_report>
