<implement_report>
  <meta project="fmri-first-level-proc" mode="implement" submodule="build" timestamp="2026-10-16T20:11:48Z" />
  <spec_ref>fmri-first-level-proc_implement_plan_20261016_195454.md</spec_ref>
  <changes_applied>
    <change id="C1" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/names.py" lines_changed="12" />
      </files_modified>
      <notes>censor_enorm and censor_fd helpers added; censor_side_files now returns the enorm and fd names with no CENSORTR entry; bucket_stats_index and stat_index both take an optional token argument via with_token. Verified: censor_side_files('pre') returns ['pre_concat_enorm.1D', 'pre_concat_fd.1D']; tokened and untokened index names match the spec exactly.</notes>
    </change>
    <change id="C2" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/qc.py" lines_changed="4" />
      </files_modified>
      <notes>censor_metric and fd_radius_mm inserted immediately after censor_prev_tr; fd_summary and enorm_summary inserted immediately after pct_censored. Verified insertion order in QC_KEYS matches the spec.</notes>
    </change>
    <change id="C3" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/nuisance.py" lines_changed="approximately 140" />
      </files_modified>
      <notes>Module constants CENSOR_METRIC and FD_RADIUS_MM added. New functions _power_fd, _enorm, _summary added; _censor rewritten to return (censor_vec, fd, enorm) and to censor on strict FD > fd_threshold, with censor_prev_tr confined to within-run censoring. 1d_tool.py -censor_motion is no longer called anywhere; no CENSORTR file is produced. task_nuisance and rest_nuisance updated to unpack the three-tuple, write explicit enorm/fd outputs, and add fd_summary/enorm_summary (task_nuisance) or per-run fd_mean/fd_max/enorm_mean/enorm_max (rest_nuisance) to their QC fragments. Module docstring rewritten per the spec. A functional smoke test confirmed the formula: a 1 mm translation produces FD=1.0, a 1-degree rotation produces FD=0.8727 (matching the locked 0.873 enorm/FD bound), and FD resets to 0 at each run's first TR.</notes>
    </change>
    <change id="C4" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/events.py" lines_changed="approximately 15" />
      </files_modified>
      <notes>Mode A now calls read_events_file(path, []) per run (no per-file enforcement) and performs a post-loop union check across all supplied runs' valid events, raising InputError with context {missing_conditions, events_files} only when no timing violations were recorded. Mode B is unchanged. Docstring updated.</notes>
    </change>
    <change id="C5" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_act_first_level.py" lines_changed="approximately 60" />
      </files_modified>
      <notes>Added the shared gltsym_args helper and the write_stat_indexes helper; both the unsmoothed and smoothed GLM stages now build their -gltsym/-glt_label arguments from the same helper. stat_bucket_parcellations no longer writes index JSONs (CSV-writing only); index writing now goes through write_stat_indexes, called from both the unsmoothed extraction stage (untokened) and the smoothed extraction stage (tokened). The smoothed GLM stage also writes a tokened bucket_stats_index. task_act_expected's smoothing branch adds both tokened names. _qc_fragment gained censor_metric and fd_radius_mm.</notes>
    </change>
    <change id="C6" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_conn_first_level.py" lines_changed="approximately 15" />
      </files_modified>
      <notes>non_beta_conditions is now derived from event_table.for_runs(list(s_pre)).conditions(), restricting nuisance regressors to the modeled runs. A dropped_nuisance list is computed and logged via logger.warning when non-empty, naming the dropped conditions and the excluded runs. _qc_fragment gained censor_metric and fd_radius_mm.</notes>
    </change>
    <change id="C7" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/rest_conn_first_level.py" lines_changed="approximately 12" />
      </files_modified>
      <notes>Concat mode now computes and writes the GS derivative inside the use_tissue_derivs block, mirroring the per-run mode's CSF/WM/GS derivative pattern. _qc_fragment gained censor_metric and fd_radius_mm, sourced via the file's existing nuisance_mod import alias (the spec's literal "from . import nuisance" was adapted to the file's established alias, since the file already imports the module under that name to avoid a local-variable collision).</notes>
    </change>
    <change id="C8" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/rest_conn_first_level.py" lines_changed="approximately 6" />
      </files_modified>
      <notes>In the sequenced backend, tissue-derivative interpolation/bandpass now stores results under keys ending in "_deriv" (e.g. "CSF_deriv") rather than overwriting the base "CSF"/"WM"/"GS" keys; the associated intermediate-file tags were updated to match. The final-regression loop's existing exclusion filter (motion, CSF, WM, GS) means these renamed derivative entries are now appended after the base regressors instead of replacing them, closing the silent regressor loss present in the v4.0.0 rewrite.</notes>
    </change>
  </changes_applied>

  <verification>
    All seven modified files pass ast.parse. The full package (fmri_first_level_proc and its seven submodules) imports cleanly with no import-time errors. A functional smoke test of _power_fd confirmed correct per-run backward-differencing, the degree-to-mm rotation conversion, and the run-boundary reset to zero. No test suite was run (out of scope for /implement; routed to /test per each change's tests_for_test_mode block in the tech spec).
  </verification>

  <summary>
    <total_changes>8</total_changes>
    <completed>8</completed>
    <skipped>0</skipped>
    <blocked>0</blocked>
  </summary>

  <next_steps>Run /test to write the per-change test requirements listed in the tech spec and to update the existing tests in tests/test_nuisance.py and tests/test_names.py that reference CENSORTR, censor_side_files, or the enorm-based _censor contract, plus any test asserting per-file Mode A required-condition errors or smoothed task_act sub-brick counts. The U5 and documentation action items (example_config.yaml fd_threshold comments; INPUT_SPECIFICATION.md lines 79, 373, 382, 471) remain for /document and were not touched by this build.</next_steps>
</implement_report>
