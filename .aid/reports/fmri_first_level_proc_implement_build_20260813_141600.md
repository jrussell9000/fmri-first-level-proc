<implement_report>
  <meta project="fmri_first_level_proc" mode="implement" submodule="build" timestamp="2026-08-13T14:16:00Z" />
  <spec_ref>fmri_first_level_proc_implement_plan_20260813_141500.md</spec_ref>
  <changes_applied>
    <change id="C1" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_utils.py" lines_changed="8" />
      </files_modified>
      <notes>Added optional tr parameter to compute_dof(); polort A polynomial regressor estimate is now computed inside the existing guarded try/except block when tr is provided. Updated docstring Parameters and Returns sections.</notes>
    </change>

    <change id="C2" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_act_first_level.py" lines_changed="5" />
      </files_modified>
      <notes>Deleted 4-line unguarded censor-file preflight block; updated compute_dof call to pass tr=config.tr.</notes>
    </change>

    <change id="C3" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_conn_first_level.py" lines_changed="5" />
      </files_modified>
      <notes>Deleted 4-line unguarded censor-file preflight block; updated compute_dof call to pass tr=config.tr.</notes>
    </change>

    <change id="C4" status="done" user_decision="n/a">
      <files_modified>
        <file path="tests/test_utils_unit.py" lines_changed="5" />
      </files_modified>
      <notes>Added ConfigError import; re-expressed two pytest.raises(ValueError) assertions to pytest.raises(ConfigError); updated two docstrings accordingly.</notes>
    </change>
  </changes_applied>
  <summary>
    <total_changes>4</total_changes>
    <completed>4</completed>
    <skipped>0</skipped>
    <blocked>0</blocked>
  </summary>
  <next_steps>Recommended: run /test run_suite to confirm 635/635.</next_steps>
</implement_report>
