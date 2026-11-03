<test_report>
  <meta project="fmri_first_level_proc" mode="test" timestamp="2026-03-12T12:11:55Z" />
  <pre_design_run>
    <total>286</total>
    <passed>282</passed>
    <failed>4</failed>
    <errors>0</errors>
    <coverage_pct>N/A</coverage_pct>
    <failures>
      <failure test="test_notch_filter_motion_command" file="tests/test_censor_creation.py" line="82">
        <error_type>SystemExit</error_type>
        <message>notch_filter_motion now calls 1dtranspose after 3dTproject (v2.3.0 BUG-003 fix); mock did not produce transposed file, causing sys.exit(1)</message>
        <traceback>SystemExit: 1 at first_level_utils.py notch_filter_motion — expected transposed file not found</traceback>
      </failure>
      <failure test="test_notch_filter_no_backslash" file="tests/test_censor_creation.py" line="119">
        <error_type>SystemExit</error_type>
        <message>Same root cause as test_notch_filter_motion_command; mock missing 1dtranspose output</message>
        <traceback>SystemExit: 1 at first_level_utils.py notch_filter_motion — expected transposed file not found</traceback>
      </failure>
      <failure test="test_task_act_skips_low_survival_condition" file="tests/test_robust_survival.py" line="26">
        <error_type>AttributeError</error_type>
        <message>Test patches 'get_stim_data' which was renamed to 'read_stim_data' in v2.3.0</message>
        <traceback>AttributeError: task_act_first_level does not have the attribute 'get_stim_data'</traceback>
      </failure>
      <failure test="test_task_conn_skips_low_survival_condition" file="tests/test_robust_survival.py" line="46">
        <error_type>AttributeError</error_type>
        <message>Test patches 'get_stim_data' which was renamed to 'read_stim_data' in v2.3.0</message>
        <traceback>AttributeError: task_conn_first_level does not have the attribute 'get_stim_data'</traceback>
      </failure>
    </failures>
  </pre_design_run>
  <design_phase>
    <tests_created>19</tests_created>
    <tests_modified>4</tests_modified>
    <files_created>
      <file path="tests/test_v230_regression.py" test_count="19" coverage_target="BUG-001 sub-brick ordering, BUG-002 dropped onset files, BUG-003 notch filter transpose, task_act harmonization read/write split, cross-pipeline consistency, edge cases" />
    </files_created>
    <files_modified>
      <file path="tests/test_censor_creation.py" test_count="2" reason="Updated test_notch_filter_motion_command to mock 1dtranspose output; replaced test_notch_filter_no_backslash with test_notch_filter_transpose_suffix verifying AFNI transpose operator" />
      <file path="tests/test_robust_survival.py" test_count="2" reason="Updated to reference read_stim_data and write_stim_onset_files instead of removed get_stim_data" />
    </files_modified>
    <design_rationale>
      All 4 pre-design failures stemmed from the v2.3.0 implementation changes:
      (1) notch_filter_motion now requires 1dtranspose mock output;
      (2) get_stim_data was split into read_stim_data + write_stim_onset_files.
      Existing tests were updated to match the new API. New regression tests in
      test_v230_regression.py were designed to specifically verify each of the 4
      bug fixes cannot regress, including: first-appearance ordering contract for
      beta_cond_order (BUG-001), correct onset file generation for dropped and
      non-beta conditions (BUG-002), AFNI transpose operator and 1dtranspose
      round-trip (BUG-003), and task_act read/write split consistency.
    </design_rationale>
  </design_phase>
  <post_design_run>
    <total>305</total>
    <passed>305</passed>
    <failed>0</failed>
    <errors>0</errors>
    <coverage_pct>N/A</coverage_pct>
    <failures />
  </post_design_run>
  <summary>
    <all_passing>true</all_passing>
    <recommendation>proceed_to_document</recommendation>
  </summary>
  <action_items>
    <!-- No action items - all tests pass -->
  </action_items>
</test_report>
