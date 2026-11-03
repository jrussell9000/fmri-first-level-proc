<implement_report>
  <meta project="fmri-first-level-proc" mode="implement" submodule="build" timestamp="2026-10-26T17:55:00Z" />
  <spec_ref>fmri-first-level-proc_implement_plan_20261026_173241.md</spec_ref>
  <changes_applied>
    <change id="C1" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/nuisance.py" lines_changed="1" />
      </files_modified>
      <notes>GuardError added to the exceptions import. Verified directly against the file.</notes>
    </change>
    <change id="C2" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/nuisance.py" lines_changed="26" />
      </files_modified>
      <notes>New points-left-abort parse branch added ahead of the two existing branches in the simultaneous-backend dry-run parser, with both invariant guards (point-count match, reconstructed DOF &lt; 1) and the per-branch null-reason assignment. The two pre-existing branches and the ToolExecutionError fallback are byte-identical in logic to before. Verified directly against the file.</notes>
    </change>
    <change id="C3" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/nuisance.py" lines_changed="19" />
      </files_modified>
      <notes>Rest QC totals (n_trs_total, n_trs_censored, pct_censored) and the CENSOR_HIGH warning now scope to the modeled runs, with the message text matching the task-side wording. per_run_censoring and per_run_dof are unchanged. Confirmed no remaining reference to the removed all-supplied-run variables. Verified directly against the file.</notes>
    </change>
    <change id="C4" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_act_first_level.py" lines_changed="1" />
      </files_modified>
      <notes>Docstring corrected to drop the stale index-JSON claim. Verified directly against the file.</notes>
    </change>
    <change id="C5" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_conn_first_level.py" lines_changed="5" />
      </files_modified>
      <notes>task_conn_expected takes the nuisance-condition list as a new parameter and adds each condition's onset file to the expected set; the single call site passes the list already in scope there. Verified directly against the file.</notes>
    </change>
    <change id="C6" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/rest_conn_first_level.py" lines_changed="2" />
      </files_modified>
      <notes>In the single-stage rest residual path, failed runs are now copied into the outer failed-run record from the stage's own QC fragment after the stage call, so the final excluded-runs list is identical whether the stage executed fresh or was reused from the ledger. Verified directly against the file.</notes>
    </change>
  </changes_applied>
  <summary>
    <total_changes>6</total_changes>
    <completed>6</completed>
    <skipped>0</skipped>
    <blocked>0</blocked>
  </summary>
  <verification>All four modified files (nuisance.py, task_act_first_level.py, task_conn_first_level.py, rest_conn_first_level.py) were independently re-read and compiled with py_compile after dispatch; no stray references to removed variables remain in nuisance.py. No tests were run in this skill.</verification>
  <next_steps>Recommended: run /test to add the points-left-abort scenarios (partial exclusion, all-runs-excluded ModelError, null-reason record), the rest totals/CENSOR_HIGH scope test, and the unconditional CENSOR_HIGH assertion hardening, then the full suite on real AFNI.</next_steps>
</implement_report>
