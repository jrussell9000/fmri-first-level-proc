<implement_plan>
  <meta project="fmri-first-level-proc" mode="implement" submodule="plan" timestamp="2026-10-12T08:00:19-04:00" />
  <input_reports>
    <report path="fmri-first-level-proc_cr_20261011_080639.md" mode="cr" key_items="15 implement items (F1-F15); 15 test items are out of scope for this plan and are carried by /test" />
  </input_reports>

  <assumptions_and_decisions>
    D1. User decision (this plan session): INPUT_SPECIFICATION.md is edited in this build for the documentation items of F6, F10,
        F11, F14 and F15 (Option B, overriding locked assumption A11 for these items only); /document will revise the same sections
        again. README.md contains no description of the censoring metric (grep for "framewise" and "FD" returned no README hits), so
        README.md is not edited.
    D2. User decision (this plan session, via D1 rationale "rather redundant than missing"): INPUT_SPECIFICATION.md line 357 (events
        delimiter detection by file extension and a legacy deprecation warning, both stale against v4.0.0 and against F10 Reading A) is
        rewritten in the same events-section edit as F14. This is the only INPUT_SPEC edit beyond the CR's listed items.
    D3. CR locked decisions are applied verbatim: F6 Option A (pooled), F10 Reading A, F11 Option A, F14 Option A, F15 Option A.
    D4. No change to qc_summary schema: the global IM column index introduced for F1 is kept internal (not added to trial records).
    D5. F12 docstring precision is recorded from an observation made during build (1ddot run on a two-column file in the build staging
        area); the docstring states the observed format and the AFNI version observed, not an assumed one.
    D6. The task_act and task_conn expected-output sets are updated to mirror every write-condition change (F3, F5) so that
        RunContext.finish validation stays consistent.
  </assumptions_and_decisions>

  <changes>
    <change id="C1" priority="P0" source_item="F1, F7">
      <file path="fmri_first_level_proc/events.py" action="modify" />
      <description>Single source for onset-file row order with condition labels, so the beta onset file and the trial-to-column map
        cannot diverge and no reverse lookup by onset is needed.</description>
      <spec>
        Add onset_rows_labeled(event_table, conditions, model_runs) -> list[list[tuple[str, float, float]]]: identical iteration to the
        current onset_rows (per model run in the given order; per condition in the given order; that condition's trials sorted by onset
        with a stable sort) returning (condition, onset, duration) tuples. Reimplement onset_rows(event_table, conditions, model_runs) as
        [[(o, d) for (_, o, d) in run] for run in onset_rows_labeled(...)] so both share one ordering. Docstrings state that this order is
        the -stim_times_IM column order (verified file-order behavior of 3dDeconvolve, guarded at runtime by estimability.check_im_order).
      </spec>
      <dependencies>none</dependencies>
      <risk>low - pure function; onset_rows output unchanged byte-for-byte.</risk>
      <rollback>Revert events.py.</rollback>
    </change>

    <change id="C2" priority="P0" source_item="F1, F6, F7">
      <file path="fmri_first_level_proc/estimability.py" action="modify" />
      <description>Trial-level estimability for multi-column HRFs, global-index beta selection, duplicate-key guard and a runtime
        IM-column-order guard.</description>
      <spec>
        (a) trial_estimability(matrix, cols, censor_vec, n_trials) -> list[tuple[float, str | None]]: if n_trials == 0: return [] when
        len(cols) == 0, else GuardError. m = len(cols) / n_trials; GuardError naming len(cols) and n_trials unless m is a positive
        integer. For trial j, block = cols[j*m:(j+1)*m]; den = sum over block columns and all rows of x^2; num = same over rows with
        censor_vec == 1. den == 0 -> (0.0, "no_in_run_support"); f = num/den; f > 0 -> (f, None); else (f, "fully_censored"). Docstring:
        pooled energy ratio, identical to the single-column T7a definition when m = 1. Keep compute_estimability for single columns only
        if still referenced; otherwise remove it.
        (b) build_trials: build key_to_index = {(cond, run, onset): j} from column_order; GuardError naming the duplicated key if any key
        repeats. Replace the zip with an explicit check: len(column_order) == len(fvalues) else GuardError. Remove the running per-condition
        counter. After all trial records are built, for analysis_type == "task_conn": for each condition, take its surviving trials, sort
        by key_to_index[(cond, run, onset)], and set beta_series_position to the rank (0..n-1). Record schema unchanged.
        (c) beta_selection(trials, column_order) -> dict[str, list[int]]: for each condition, the sorted global indices
        key_to_index[(cond, run, onset)] of its surviving trials (same duplicate guard). The k-th entry corresponds to
        beta_series_position k.
        (d) check_im_order(matrix, cols, m, column_order, afni_version) -> None: for each trial j, first_row_j = smallest row index with any
        nonzero value in block j (skip trials whose block is all zero). Within each run label, order trials by onset; if for two trials
        onset_a &lt; onset_b but first_row_a &gt; first_row_b, raise GuardError stating that 3dDeconvolve -stim_times_IM column order differs
        from onset-file order under AFNI {afni_version}.
      </spec>
      <dependencies>none</dependencies>
      <risk>medium - changes the survival computation entry point used by both task pipelines.</risk>
      <rollback>Revert estimability.py together with C3 and C4.</rollback>
    </change>

    <change id="C3" priority="P0" source_item="F1, F7">
      <file path="fmri_first_level_proc/task_conn_first_level.py" action="modify" />
      <description>Correct 3dLSS sub-brick selection and guard the column order.</description>
      <spec>
        (a) task-conn-onsets step: build the beta onset text from events.onset_rows(...) as now (unchanged bytes); store
        ctx._beta_column_order = [(cond, lbl, onset) for i, lbl in enumerate(s_pre) for (cond, onset, _) in
        events.onset_rows_labeled(event_table, beta_cond_order, list(s_pre))[i]].
        (b) task-conn-estimability step (lines ~470-498): replace the reverse-lookup loop with the same onset_rows_labeled construction;
        fvals = estimability.trial_estimability(matrix, cols, censor_vec, len(column_order)); call estimability.check_im_order(matrix,
        cols, len(cols) // max(len(column_order), 1), column_order, ctx.versions afni string); store ctx._beta_column_order.
        (c) Beta-series stage and smoothed beta-series stage: after 3dLSS, n = 3dinfo -nv of the LSS output; GuardError if n !=
        len(im_columns(header, "beta_stims")) naming both counts. selection = estimability.beta_selection(trials_list,
        ctx._beta_column_order); for each surviving condition idx_str = ",".join(selection[cond]) (skip if empty). Remove the
        beta_series_position-based selection in both stages. The beta_series_spec derived_values "survival" entry becomes selection
        (global indices) so a change in selection reruns the stage.
      </spec>
      <dependencies>C1, C2</dependencies>
      <risk>high - core task_conn output path.</risk>
      <rollback>Revert task_conn_first_level.py.</rollback>
    </change>

    <change id="C4" priority="P1" source_item="F6, F7">
      <file path="fmri_first_level_proc/task_act_first_level.py" action="modify" />
      <description>Per-trial pooled estimability for multi-column HRFs and the column-order guard in task_act.</description>
      <spec>
        In the task-act-estimability step (lines ~528-545): for each condition, rows = events.onset_rows_labeled(event_table, [cond],
        list(s_pre)); cond_order = [(c, lbl, onset) per run]; if not cond_order: skip the condition before any division (no columns
        expected; GuardError if im_columns returns columns). fvals = estimability.trial_estimability(matrix, cols, censor_vec,
        len(cond_order)); estimability.check_im_order(matrix, cols, len(cols) // len(cond_order), cond_order, afni version); extend
        all_column_order and all_fvalues with explicit equal-length lists (no zip).
      </spec>
      <dependencies>C1, C2</dependencies>
      <risk>medium - survival and floors change only for multi-column HRFs.</risk>
      <rollback>Revert task_act_first_level.py.</rollback>
    </change>

    <change id="C5" priority="P0" source_item="F2, F8">
      <file path="fmri_first_level_proc/runsets.py" action="modify" />
      <description>Explicit whole-file run identity, and header TR checked against config.tr in every mode.</description>
      <spec>
        (a) RunInfo gains whole_file: bool (frozen dataclass field, documented). build_runsets sets whole_file=True for task Mode A and
        rest runs, False for task Mode B runs. spec returns source_path when whole_file, else
        f"{source_path}[{start}..{start + n_vols - 1}]" (including start == 0). Update the property docstring.
        (b) _t1_checks Mode A / rest: replace the first-run TR comparison with a per-run comparison against config.tr; abs difference
        > 1e-4 raises InputError: "TR mismatch: '{path}' header TR is {header} s but the configured tr is {config.tr} s. Correct tr in the
        config or fix the header with 3drefit -TR." (reuse the existing 3dinfo -tr call). Mode B: one 3dinfo -tr on config.scan_path with
        the same comparison and message.
      </spec>
      <dependencies>none</dependencies>
      <risk>medium - new InputError path may reject inputs that previously ran with a mismatched tr (intended).</risk>
      <rollback>Revert runsets.py.</rollback>
    </change>

    <change id="C6" priority="P0" source_item="F3, F4">
      <file path="fmri_first_level_proc/prep.py" action="modify" />
      <file path="fmri_first_level_proc/task_act_first_level.py" action="modify" />
      <file path="fmri_first_level_proc/task_conn_first_level.py" action="modify" />
      <description>Write the concatenated model input whenever more than one run was supplied, and route smoothed model input in every
        input mode.</description>
      <spec>
        (a) task_prep: PSC concat condition becomes `if k_sup > 1:` (3dTcat over the surviving runs, which may be one); Mode A unscaled
        concat condition becomes `if runsets.input_mode == "A" and k_sup > 1:`. expected_nvols unchanged (total_vols(s_pre)).
        (b) task_model_input: in the scale_to_psc false branch, when token is non-empty return
        os.path.join(out_dir, names.blurred_run(pre, None, token)) if k_sup == 1 else
        os.path.join(out_dir, names.blurred_concat(pre, token, False)), before the input-mode branch. Empty-token returns unchanged.
        (c) task_act_expected and task_conn_expected: wherever the concat model-input names (psc_concat, concat_scan) are added under a
        condition that includes the number of surviving runs, change the condition to K_supplied > 1 to mirror (a).
      </spec>
      <dependencies>C5</dependencies>
      <risk>medium - changes which files are written and expected in multi-run runs.</risk>
      <rollback>Revert the three files' hunks.</rollback>
    </change>

    <change id="C7" priority="P1" source_item="F5">
      <file path="fmri_first_level_proc/task_conn_first_level.py" action="modify" />
      <description>Smoothed seed-to-voxel maps use the unsmoothed seed; smoothed contrast siblings are produced and expected.</description>
      <spec>
        In _connectivity_stage (seed_to_voxel branch): smoothed map call becomes connectivity.seed_to_voxel(io, bseries_path,
        smoothed_bseries, template_resolved, ...). Replace the os.path.exists skip with a produced_paths_smoothed dict populated when
        output_s is not None; merge frag_s into qc_frag the same way as frag. After the unsmoothed contrast loop, when smoothing is
        enabled and calc_conn == "seed_to_voxel": for each kept contrast whose conditions are all in produced_paths_smoothed, call
        connectivity.seed_contrast(io, [produced_paths_smoothed[c] ...], coefs, names.conn_output(conn_pre, safe_label, fishZ, pcorr,
        calc_conn, token), label, logger). task_conn_expected: add those token contrast names when smoothing, seed_to_voxel,
        conn_out_file_pre and contrast_labels are set.
      </spec>
      <dependencies>C3, C6</dependencies>
      <risk>medium - new outputs; seed definition of smoothed maps changes.</risk>
      <rollback>Revert the hunk.</rollback>
    </change>

    <change id="C8" priority="P1" source_item="F5">
      <file path="fmri_first_level_proc/rest_conn_first_level.py" action="modify" />
      <description>Smoothed rest seed-to-voxel map uses the unsmoothed seed.</description>
      <spec>connectivity.seed_to_voxel(io, concat_path, smoothed_path, template_resolved, ...) for the smoothed map (line ~932); merge
        frag_s into qc_frag.</spec>
      <dependencies>none</dependencies>
      <risk>low.</risk>
      <rollback>Revert the hunk.</rollback>
    </change>

    <change id="C9" priority="P1" source_item="F10, F14">
      <file path="fmri_first_level_proc/events.py" action="modify" />
      <description>Delimiter ambiguity errors and rejection of missing or non-finite onset/duration values.</description>
      <spec>
        (a) Header probe loop: record per delimiter either the stripped column list or "unparseable" (when read_csv raises). len(recognized)
        == 0 or 2 -> InputError: "Events file '{path}': header recognized under {neither|both} delimiter(s). Columns found: tab ->
        {cols_or_unparseable}; comma -> {cols_or_unparseable}. Expected BIDS (onset, duration, trial_type) or CONDITION (CONDITION, ONSET,
        DURATION), tab- or comma-delimited." Remove the both-recognized BIDS preference. Within one delimiter, the existing BIDS-before-
        CONDITION check is unchanged.
        (b) After the existing astype(float) block, a separate block: for col in (onset, duration): bad = ~np.isfinite(df[col]); if
        bad.any(): rows = 1-based data-row numbers; InputError: "Events file '{path}': column '{col}' has missing or non-finite values
        (e.g. BIDS 'n/a', empty cells, inf) in data rows {rows}. 'n/a' is valid BIDS meaning the value is unknown, but this package
        cannot model it. " + remedy, where remedy is "Supply the true onset time." for onset and "Supply the true duration, or 0 for
        impulse events." for duration. No imputation anywhere.
      </spec>
      <dependencies>C1</dependencies>
      <risk>low - stricter input validation only.</risk>
      <rollback>Revert the hunks.</rollback>
    </change>

    <change id="C10" priority="P2" source_item="F9">
      <file path="fmri_first_level_proc/roi.py" action="modify" />
      <description>Compute ROI-invariant low-baseline quantities once per run.</description>
      <spec>In roi_qc, before the low-baseline ROI loop: if not sentinel_fail and any(masked_counts.get(r, 0) > 0 for r in tlabels): run
        the low-indicator 3dcalc (threshold = 0.2 * med) and count_nonzero_by_roi once (low_counts), and the masked-mean 3dcalc and
        median_by_roi once (roi_med_dict); file names drop the _roi{roi} suffix. The loop reads low_counts.get(roi, 0) and
        roi_med_dict.get(roi). Records, values and null reasons unchanged.</spec>
      <dependencies>none</dependencies>
      <risk>low.</risk>
      <rollback>Revert the hunk.</rollback>
    </change>

    <change id="C11" priority="P2" source_item="F11, F12">
      <file path="fmri_first_level_proc/nuisance.py" action="modify" />
      <file path="fmri_first_level_proc/connectivity.py" action="modify" />
      <file path="example_config.yaml" action="modify" />
      <description>Code-adjacent documentation of the censoring metric and of 1ddot print precision.</description>
      <spec>
        nuisance.py: _censor docstring (and module docstring where censoring is described) states the metric is AFNI's enorm: Euclidean
        norm of the per-TR backward difference of the six motion parameters, difference 0 at each run's first TR, rotations in the units
        supplied (degrees required), computed by 1d_tool.py -censor_motion (which implies -derivative and -collapse_cols
        euclidean_norm); not the Power et al. (2012) framewise displacement; thresholds are not interchangeable. example_config.yaml
        lines 87, 158, 234: comment becomes "# enorm censor threshold (mm/deg; AFNI 1d_tool.py -censor_motion, not Power FD)".
        connectivity.py module docstring: run 1ddot once during build on a two-column 1D file in the staging/scratch area, record the
        observed decimal format of both the correlation and inverse blocks and the AFNI version, and state the rounding bounds (r about
        0.5x10^-d; partial correlation at most about 10^-d; Fisher Z at most the input bound divided by 1 - 0.999329^2).
      </spec>
      <dependencies>none</dependencies>
      <risk>low - text only.</risk>
      <rollback>Revert the hunks.</rollback>
    </change>

    <change id="C12" priority="P2" source_item="F6, F10, F11, F14, F15">
      <file path="INPUT_SPECIFICATION.md" action="modify" />
      <description>Targeted INPUT_SPEC corrections for the reviewed behaviors (D1, D2).</description>
      <spec>
        Line 79 (fd_threshold row) and line 467 (qc row): "Censoring threshold on AFNI's enorm (Euclidean norm of the per-TR backward
        difference of the six motion parameters; translations mm, rotations degrees); not Power et al. (2012) FD; thresholds are not
        interchangeable." Line 371: replace "FD computation" with "enorm computation". Line 380: describe the censor computation as enorm
        via 1d_tool.py -censor_motion with run breaks. Line 557: "relaxing the censoring threshold".
        Events section (lines ~337-360): state both BIDS (onset, duration, trial_type) and CONDITION (CONDITION, ONSET, DURATION) schemes
        are accepted in tab- or comma-delimited files regardless of extension; the delimiter is the one under which the header is
        recognized; a header recognized under both or neither delimiter raises InputError listing the columns found; BIDS takes
        precedence only when one delimiter's header contains both schemes; no deprecation warning. Add: onset and duration must be finite
        numbers; 'n/a', empty cells and inf raise InputError (no imputation); use 0 duration for impulse events.
        Trial Survival section (lines ~544-550): replace the onset-volume description with the estimability definition: per trial, the
        fraction of regressor energy on uncensored TRs from the -stim_times_IM dry run; survives iff > 0; for HRFs with m basis columns
        per trial the energy is pooled over the trial's m columns (identical to the single-column definition when m = 1); floors
        unchanged.
        BIDS discovery table (line ~444): the matched motion file (desc-confounds, suffix regressors, .tsv) must be headerless with
        motion in the first six columns (translations mm, rotations degrees); fMRIPrep confounds files are not compatible.
      </spec>
      <dependencies>C9, C11</dependencies>
      <risk>low - documentation.</risk>
      <rollback>Revert INPUT_SPECIFICATION.md.</rollback>
    </change>

    <change id="C13" priority="P2" source_item="F13">
      <file path="fmri-first-level-proc_implement_build_20261009_140031.md" action="modify" />
      <description>Correct the unsupported verification claim in the prior build report.</description>
      <spec>In the verification_notes paragraph, replace "connectivity.py's 1ddot parser was verified against captured real AFNI output but
        not through a full pipeline run" with "connectivity.py's 1ddot parser was unit-checked in isolation only; no captured real AFNI
        output was retained, and it was not exercised through a full pipeline run". In the connectivity-module change note of the same
        report, apply the same correction.</spec>
      <dependencies>none</dependencies>
      <risk>low.</risk>
      <rollback>Revert the file.</rollback>
    </change>
  </changes>

  <execution_order>C1, C2, C5, C6, C9, C3, C4, C7, C8, C10, C11, C12, C13</execution_order>

  <build_notes>
    No tests are run in build (handled by /test). The CR's 15 /test action items, including the value-level real-AFNI suite (F13), are
    the required next step after this build.
  </build_notes>
</implement_plan>
