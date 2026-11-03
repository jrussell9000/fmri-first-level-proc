<implement_report>
  <meta project="fmri_first_level_proc" mode="implement" submodule="build" timestamp="2026-08-13T09:49:00Z" />
  <spec_ref>fmri_first_level_proc_implement_plan_20260813_023100.md</spec_ref>
  <changes_applied>
    <change id="C1" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_act_first_level.py" lines_changed="4" />
        <file path="fmri_first_level_proc/task_conn_first_level.py" lines_changed="15" />
      </files_modified>
      <notes>All stim_data and cond_df DataFrame column accesses renamed from legacy uppercase (CONDITION, ONSET, DURATION) to BIDS lowercase (trial_type, onset, duration). Includes line 205 (betas_df construction), which was not in the test report's line list but is required for write_onset_file compatibility. The bseries_out/bseries_info dict keys ('CONDITION', 'PATH') were left unchanged per the approved plan (internal tracking structure, not DataFrame column access). Post-edit grep confirms zero remaining stale DataFrame column references in both files.</notes>
    </change>
    <change id="C2" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_utils.py" lines_changed="1" />
      </files_modified>
      <notes>Added 'import argparse' as the first stdlib import (alphabetical order, before 'import dataclasses'). Restores argparse.ArgumentTypeError availability for 6 validator functions (dir_path_exists, file_path_exists, valid_string_list, valid_stat_type, valid_ave_type, valid_conn_type).</notes>
    </change>
  </changes_applied>
  <summary>
    <total_changes>2</total_changes>
    <completed>2</completed>
    <skipped>0</skipped>
    <blocked>0</blocked>
  </summary>
  <next_steps>Recommended: run /test run_suite to verify the 46 previously-failing tests now pass and the full suite reaches 635/635.</next_steps>
</implement_report>
