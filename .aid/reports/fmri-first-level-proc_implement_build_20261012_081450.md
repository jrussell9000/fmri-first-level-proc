<implement_report>
  <meta project="fmri-first-level-proc" mode="implement" submodule="build" timestamp="2026-10-12T08:14:50-04:00" />
  <spec_ref>fmri-first-level-proc_implement_plan_20261012_080019.md</spec_ref>

  <changes_applied>
    <change id="C1" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/events.py" lines_changed="97" />
      </files_modified>
      <notes>Added onset_rows_labeled as the single source of onset-file order; onset_rows is now a projection of it. The per-condition onset sort is now explicitly stable (mergesort); output is byte-identical except for exact duplicate onsets, which the new duplicate-trial guard rejects. The line count for this file also includes the events-reader changes below.</notes>
    </change>

    <change id="C2" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/estimability.py" lines_changed="190" />
      </files_modified>
      <notes>Replaced the per-column estimability function with trial_estimability (pooled energy over each trial's basis columns; identical to the previous definition for one column per trial). build_trials now rejects duplicate (condition, run, onset) trials and length mismatches, and assigns the per-condition beta-series position as the rank by global column index. Added beta_selection and check_im_order. Deviation: check_im_order derives the number of columns per trial internally (signature matrix, cols, column_order, afni_version) instead of taking it as an argument, so callers cannot pass an inconsistent value. Ties in onset are ordered by first row before the adjacent-pair comparison, which makes the pairwise check equivalent to the full ordering condition.</notes>
    </change>

    <change id="C5" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/runsets.py" lines_changed="64" />
      </files_modified>
      <notes>RunInfo has a whole_file field, set at all three construction sites; spec returns an explicit sub-brick selector for every task Mode B run, including the first. A shared header-TR check compares each run's header (Mode A and rest) or the concatenated file's header (Mode B) directly with the configured tr, replacing the first-run comparison.</notes>
    </change>

    <change id="C6" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/prep.py" lines_changed="17" />
      </files_modified>
      <notes>The PSC and Mode A unscaled concatenations are now written whenever more than one run was supplied. With PSC off and a smoothing token, the model-input helper returns the smoothed file in every input mode. The planned expected-output edits in both task pipelines were not needed: those sets already used the K_supplied condition, so only the write side was inconsistent.</notes>
    </change>

    <change id="C9" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/events.py" lines_changed="0" />
      </files_modified>
      <notes>Line count included under the onset-order change above. A header recognized under both or neither delimiter raises InputError listing the stripped columns (or "unparseable") per delimiter; the cross-delimiter BIDS preference is removed. A separate post-conversion check rejects NaN and infinite onset or duration values with per-column remedies; nothing is imputed.</notes>
    </change>

    <change id="C3" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_conn_first_level.py" lines_changed="138" />
      </files_modified>
      <notes>The estimability step builds the trial list from onset_rows_labeled (replacing the reverse lookup by onset), uses trial_estimability and the column-order guard, and stores the trial list on the run context. Both beta-series stages select 3dLSS sub-bricks by global index from beta_selection, and raise GuardError if the 3dLSS sub-brick count or the design-matrix IM column count differs from the number of trials. The stage hash now covers the global selection. Deviation: the trial list is stored only by the always-run estimability step, not also by the onsets step, since the estimability step always precedes the beta-series stages. The line count also includes the smoothed seed-to-voxel changes below.</notes>
    </change>

    <change id="C4" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_act_first_level.py" lines_changed="41" />
      </files_modified>
      <notes>Per-condition trial lists come from onset_rows_labeled; estimability is pooled per trial and the column-order guard runs per condition; the zip pairing is replaced with explicit list extension. A condition with no trials in the model runs is skipped before any division, with a GuardError if the design matrix nevertheless has IM columns for it.</notes>
    </change>

    <change id="C7" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_conn_first_level.py" lines_changed="0" />
      </files_modified>
      <notes>Line count included under the 3dLSS selection change above. Smoothed seed-to-voxel maps take the seed from the unsmoothed beta series and the target from the smoothed one; the silent file-existence skip is replaced by a smoothed-path map; smoothed QC records are merged (their identity is the output filename, so no duplicates). Smoothed contrast siblings are computed and added to the expected-output set.</notes>
    </change>

    <change id="C8" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/rest_conn_first_level.py" lines_changed="6" />
      </files_modified>
      <notes>The smoothed rest seed-to-voxel map takes the seed from the unsmoothed concatenated residual; its QC record is merged.</notes>
    </change>

    <change id="C10" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/roi.py" lines_changed="54" />
      </files_modified>
      <notes>The low-baseline indicator and masked-mean volumes and their two 3dROIstats calls run once per run, skipped when the non-positive-baseline sentinel fails or no ROI has masked voxels; records and null reasons are unchanged.</notes>
    </change>

    <change id="C11" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/nuisance.py" lines_changed="15" />
        <file path="fmri_first_level_proc/connectivity.py" lines_changed="8" />
        <file path="example_config.yaml" lines_changed="6" />
      </files_modified>
      <notes>The censoring metric is documented as AFNI enorm, not Power et al. (2012) FD, in the nuisance module and censor docstrings and the three example_config comments. 1ddot was run once on a 50 x 3 synthetic series: under AFNI 26.0.09 both the correlation matrix and its inverse print five fixed decimals, and the connectivity docstring records this with the rounding bounds.</notes>
    </change>

    <change id="C12" status="done" user_decision="n/a">
      <files_modified>
        <file path="INPUT_SPECIFICATION.md" lines_changed="24" />
      </files_modified>
      <notes>Edited: fd_threshold rows (config and qc tables), the motion-units note, the censor-file description, the DOF remedy, the events-file section (detection by header content under either delimiter, ambiguity errors, no deprecation warning, missing-value rule), the trial-survival definition (estimability, pooled for multi-column HRFs), and a motion-file requirement note under the discovery table. Rationale correction for the events-detection rewrite: the plan's assumption list records it as a user decision; it is instead the documentation of the delimiter behavior changed in this build, under the user's rule that implement and document both update documentation for changed behavior.</notes>
    </change>

    <change id="C13" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri-first-level-proc_implement_build_20261009_140031.md" lines_changed="4" />
      </files_modified>
      <notes>Both statements that the 1ddot parser was verified against captured real AFNI output now say it was unit-checked in isolation only, with no captured output retained.</notes>
    </change>
  </changes_applied>

  <summary>
    <total_changes>13</total_changes>
    <completed>13</completed>
    <skipped>0</skipped>
    <blocked>0</blocked>
  </summary>

  <verification_notes>
    Build-level checks only (no tests, per mode rules): every module compiles; the package imports (version 4.0.0); the new
    estimability, events and run-identity symbols are present and the removed per-column estimability function has no remaining
    references. A pre-build snapshot of all modified files is in the session scratchpad (prebuild_snapshot_20261012) for rollback.
    None of the behavior changes have been executed against AFNI in this build.
  </verification_notes>

  <next_steps>Recommended: run /test to validate all changes, carrying the review report's fifteen test action items, including the value-level real-AFNI suite.</next_steps>
</implement_report>
