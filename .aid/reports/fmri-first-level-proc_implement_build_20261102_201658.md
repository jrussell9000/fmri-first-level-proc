<implement_report>
  <meta project="fmri-first-level-proc" mode="implement" submodule="build" timestamp="2026-11-02T20:16:58Z" />
  <spec_ref>fmri-first-level-proc_implement_plan_20261102_201021.md</spec_ref>
  <changes_applied>
    <change id="C1" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_config.py" lines_changed="6" />
      </files_modified>
      <notes>As specified. _check_required_block_keys now treats boolean keys and bandpass as missing only when absent; all other required keys keep the null-as-missing rule, and the error message is unchanged.</notes>
    </change>
    <change id="C2" status="done" user_decision="n/a">
      <files_modified>
        <file path="INPUT_SPECIFICATION.md" lines_changed="1" />
        <file path="CHANGELOG.md" lines_changed="1" />
      </files_modified>
      <notes>As specified.</notes>
    </change>
  </changes_applied>
  <summary>
    <total_changes>2</total_changes>
    <completed>2</completed>
    <skipped>0</skipped>
    <blocked>0</blocked>
  </summary>
  <verification_performed>Compilation of the modified module, a package import check, and an em-dash scan of the edited files. No tests were run (per this skill).</verification_performed>
  <expected_test_impact>tests/test_config_edge_cases.py::TestResolveConfigGlobalMerge::test_bool_keys_default_false and tests/test_config_validation.py::TestRestParamValidation::test_bandpass_null_rejected are expected to pass; no other test should change.</expected_test_impact>
  <next_steps>Recommended: run /test to validate all changes.</next_steps>
</implement_report>
