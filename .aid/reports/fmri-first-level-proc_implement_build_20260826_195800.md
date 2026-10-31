<implement_report>
  <meta project="fmri-first-level-proc" mode="implement" submodule="build" timestamp="2026-08-26T19:58:00Z" />
  <spec_ref>fmri-first-level-proc_implement_plan_20260826_195500.md</spec_ref>
  <changes_applied>
    <change id="C1" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_act_first_level.py" lines_changed="36" />
      </files_modified>
      <notes>New generate_bucket_stats_index() function inserted between _get_subbrik_stat_aux() and extract_stat_buckets(), per spec. Uses 3dinfo -label with pipe-delimited parsing, standard idempotency guard, and JSON write with indent=2. No deviations from spec.</notes>
    </change>
    <change id="C2" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_act_first_level.py" lines_changed="4" />
      </files_modified>
      <notes>Call site inserted after run_first_level() at line 741; output_files inclusion inserted after resids_path check at line 762. Both insertions are additive with no modification of existing lines. No deviations from spec.</notes>
    </change>
  </changes_applied>
  <summary>
    <total_changes>2</total_changes>
    <completed>2</completed>
    <skipped>0</skipped>
    <blocked>0</blocked>
  </summary>
  <next_steps>Recommended: run /test to validate all changes. The new function introduces a 3dinfo -label call and JSON write that should be tested for: (1) correct pipe-delimited parsing, (2) idempotency guard, (3) integration with the run() output_files collection, (4) inclusion in FirstLevelResult.output_files.</next_steps>
</implement_report>
