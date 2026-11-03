<implement_plan>
  <meta project="fmri-first-level-proc" mode="implement" submodule="plan" timestamp="2026-10-16T19:54:54Z" />
  <input_reports>
    <report path="fmri-first-level-proc_brainstorm_20261016_193730.md" mode="brainstorm" key_items="6 implement action items (U1 with T4(i) and A1; U2; U3 per T3; U4 per T4(ii); T5; nuisance.py docstring for U1 and T2(a))" />
    <report path="ABCD_fmri_orchestrator_S3_brainstorm_upstream_20261015_150913.md" mode="brainstorm (context only)" key_items="U1-U4 text referenced by the input report as 'as written'" />
  </input_reports>

  <plan_scope>
    In scope: all action items with target_mode="implement" in the input report, plus one change added during planning with explicit user approval (C8, sequenced-backend tissue-derivative collision, a v4.0.0 regression absent from v3.1.0). Out of scope for this plan by the input report's own routing: U5 and every INPUT_SPECIFICATION.md, README.md and example_config.yaml text change (target_mode="document"; example_config.yaml lines 87, 158, 234 and INPUT_SPECIFICATION.md lines 79, 373, 382, 471 still describe enorm censoring and are covered by that /document pass), D1-D3 (deferred), and all test writing (routed to /test; requirements listed per change below).
  </plan_scope>

  <rollback_baseline>
    The v4.0.0-build working tree is uncommitted. Before the first build edit, the build orchestrator copies the seven files this plan modifies (names.py, qc.py, nuisance.py, events.py, task_act_first_level.py, task_conn_first_level.py, rest_conn_first_level.py) into the session scratchpad directory under implement_backup_20261016/, preserving basenames. Every per-change rollback below restores from that copy.
  </rollback_baseline>

  <changes>
    <change id="C1" priority="P0" source_item="A1(2-4); T3(2)">
      <file path="fmri_first_level_proc/names.py" action="modify" />
      <description>Censor side files become the enorm and FD series; tokened variants of the two task_act index names.</description>
      <spec>
        (a) censor_side_files(pre, label=None) returns [pfx + "_enorm.1D", pfx + "_fd.1D"] where pfx = censor_prefix(pre, label). The "_CENSORTR.txt" entry is removed. Add two single-file helpers used by nuisance.py: censor_enorm(pre, label=None) -> censor_prefix(pre, label) + "_enorm.1D"; censor_fd(pre, label=None) -> censor_prefix(pre, label) + "_fd.1D". censor_side_files returns [censor_enorm(pre, label), censor_fd(pre, label)].
        (b) bucket_stats_index(pre, token="") returns with_token(f"{pre}_concat_bucket_stats_index.json", token).
        (c) stat_index(ext, stat, token="") returns with_token(f"{ext}_{stat}_index.json", token).
        Existing call sites without a token produce identical names to today.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - pure name functions; defaults preserve existing names.</risk>
      <rollback>Restore names.py from the backup.</rollback>
      <tests_for_test_mode>test_names.py: censor_side_files returns exactly the enorm and fd names for label None and an integer label; no CENSORTR name; tokened and untokened bucket_stats_index/stat_index names (token "_s4mm" inserted before ".json").</tests_for_test_mode>
    </change>

    <change id="C2" priority="P0" source_item="A1(5)">
      <file path="fmri_first_level_proc/qc.py" action="modify" />
      <description>Register the new censoring QC keys in the closed schema.</description>
      <spec>
        Insert into QC_KEYS, preserving insertion order:
        immediately after "censor_prev_tr":
          "censor_metric": QCKeySpec("value", (), ("{t}-qc",), ALL),
          "fd_radius_mm": QCKeySpec("value", (), ("{t}-qc",), ALL),
        immediately after "pct_censored":
          "fd_summary": QCKeySpec("value", (), ("{t}-nuisance",), ALL),
          "enorm_summary": QCKeySpec("value", (), ("{t}-nuisance",), ALL),
        No other key changes. per_run_censoring remains a records key with identity ("run",); its records gain fields (C3), which merge_fragments already permits.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - additive schema entries.</risk>
      <rollback>Restore qc.py from the backup.</rollback>
      <tests_for_test_mode>merge_fragments accepts the four keys from the stated producers for all three analysis types, rejects them from any other producer, and emits them in the stated order.</tests_for_test_mode>
    </change>

    <change id="C3" priority="P0" source_item="U1; T4(i); A1(1-5); T2(a) docstring; U1(5) docstring">
      <file path="fmri_first_level_proc/nuisance.py" action="modify" />
      <description>Censor on Power et al. (2012) framewise displacement computed in Python; compute enorm with 1d_tool.py for reference; write both series; add FD/enorm QC summaries; update docstrings.</description>
      <spec>
        (a) Module constants: CENSOR_METRIC = "power_fd"; FD_RADIUS_MM = 50.
        (b) New function _power_fd(motion6, run_lengths) -> np.ndarray (float, length sum(run_lengths)). motion6 columns are [tx, ty, tz, rx, ry, rz], translations mm, rotations degrees. For each run segment: d = backward difference of the segment rows (first row of each run set to 0); rotation columns 3:6 of d multiplied by (math.pi / 180.0) * FD_RADIUS_MM; fd = sum over the six columns of abs(d). Segments are taken in order from the concatenated array using run_lengths.
        (c) New function _enorm(io, motion6, run_lengths, src_path, out_rel, logger) -> np.ndarray: runs ["1d_tool.py", "-infile", src_path, "-set_run_lengths", *run_lengths, "-derivative", "-collapse_cols", "euclidean_norm", "-write", io.path(out_rel)] via run_afni_command (description "1d_tool.py enorm", cwd=io.staging) and returns np.loadtxt(io.path(out_rel), ndmin=1).ravel() as float. A load failure raises InputError naming the file (same pattern as the current censor read).
        (d) Rewrite _censor(io, motion6, run_lengths, prefix_rel, fd_threshold, censor_prev_tr, logger) to return a tuple (censor_vec, fd, enorm):
          1. Write motion6 to prefix_rel + "_censor_src.1D" exactly as today (format_table(motion6, fmt="%.8f")).
          2. enorm = _enorm(io, motion6, run_lengths, src_path, prefix_rel + "_enorm.1D", logger).
          3. fd = _power_fd(motion6, run_lengths); write format_table(fd.reshape(-1, 1)) to prefix_rel + "_fd.1D".
          4. flag = fd > fd_threshold (strict). keep = ~flag. If censor_prev_tr: for every index i where flag[i] is True and i is not the first TR of its run, set keep[i - 1] = False. Previous-TR censoring is driven by flag only (not cascading).
          5. censor_vec = keep.astype(int); write "\n".join(str(v) for v in censor_vec) + "\n" to prefix_rel + "_censor.1D".
          6. Remove the temporary source file as today. 1d_tool.py -censor_motion is no longer invoked anywhere; no CENSORTR file is produced.
          The function docstring states: censoring uses Power FD (50 mm sphere, rotations degrees x pi/180 x 50, difference 0 at each run's first TR, TR censored when FD > fd_threshold, censor_prev_tr also censors the immediately preceding TR within the same run); enorm is computed for reference only.
        (e) task_nuisance:
          - Pass 1 call: censor_vec only is used (unpack the tuple); _pass1 files are deleted as today.
          - Pass 2 call: unpack (pass2_censor, fd_s_pre, enorm_s_pre).
          - Replace the censor_side_files loop with explicit outputs: Output(names.censor_enorm(pre, None), "intermediate", "afni_text", producer="1d_tool.py enorm", expected_rows=runsets.total_vols(s_pre), expected_cols=1) and Output(names.censor_fd(pre, None), "intermediate", "py_text", producer="Power FD", expected_text=&lt;the exact FD text written&gt;). The censor Output keeps its name; its producer string becomes "Power FD censor".
          - QC fragment adds fd_summary = _summary(fd_s_pre) and enorm_summary = _summary(enorm_s_pre), where _summary(x) = {"mean": round(float(np.mean(x)), 4), "median": round(float(np.median(x)), 4), "max": round(float(np.max(x)), 4)} computed over all TRs of the model runs (S_pre), censored TRs included.
        (f) rest_nuisance:
          - Per-run censor call unpacks (censor_vec, fd_run, enorm_run); keep fd_run and enorm_run in dicts keyed by run label.
          - Each per_run_censoring record gains "fd_mean", "fd_max", "enorm_mean", "enorm_max" (round(float(...), 4)).
          - In the S_pre outputs loop, replace the censor_side_files loop with the same two explicit outputs as (e) using names.censor_enorm(pre, lbl) and names.censor_fd(pre, lbl), expected_rows=ri.n_vols for enorm, expected_text from re-formatting fd_run[lbl] identically to the written text.
          - QC fragment adds fd_summary and enorm_summary computed with _summary over the concatenation of fd_run / enorm_run for the S_pre runs (s_pre_labels order).
          - The notch-filtered motion is used for FD and enorm when notch_filter_band is set, unmodified motion otherwise (unchanged source selection).
        (g) Module docstring (lines 12-20) replaced: censoring metric is Power et al. (2012) framewise displacement on a 50 mm sphere (translations mm; rotations degrees converted as degrees x pi/180 x 50; difference 0 at each run's first TR; TR censored when FD > fd_threshold; censor_prev_tr censors the preceding TR within the same run); for rest_conn, FD is computed from the notch-filtered motion when notch_filter_band is set. AFNI enorm (Euclidean norm of the backward difference, rotations unweighted) is computed with 1d_tool.py and recorded for reference only; for any TR, 0.873 x enorm &lt;= FD &lt;= 2.30 x enorm. Input contract: the first six motion columns must be [tx, ty, tz, rx, ry, rz] in mm and degrees; AFNI 3dvolreg -1Dfile/-dfile output (roll pitch yaw dS dL dP) must be reordered translations-first (otherwise FD is biased by roughly -13% to +15%), and fMRIPrep confounds rotations (radians) must be converted to degrees (otherwise the FD rotation term is about 57x too small).
      </spec>
      <dependencies>C1</dependencies>
      <risk>medium - changes which TRs are censored for every analysis type, which propagates to S_pre exclusion, DOF and all model outputs; mitigated by the deterministic FD formula and the unchanged censor file format and name.</risk>
      <rollback>Restore nuisance.py from the backup (C1 may stay; the CENSORTR name is then simply absent).</rollback>
      <tests_for_test_mode>FD formula on synthetic motion with known translations and rotations, including the degree conversion and the per-run first-TR zero; threshold strictness (FD exactly equal to fd_threshold is kept); censor_prev_tr within a run and never across a run boundary; enorm file equals the Python Euclidean norm of the per-run backward differences; FD and enorm files exist with one row per TR and no CENSORTR file is produced; rest uses notch-filtered motion for FD when notch_filter_band is set; a case where enorm and FD disagree changes the censor count; DOF dry runs consume the FD-based censor file; QC fd_summary/enorm_summary values and the rest per-run fields; censor_metric and fd_radius_mm present in qc_summary.json for all three types (with C4, C6, C7).</tests_for_test_mode>
    </change>

    <change id="C4" priority="P0" source_item="U2">
      <file path="fmri_first_level_proc/events.py" action="modify" />
      <description>Mode A checks required conditions against the union of the supplied runs' valid events instead of every per-run file.</description>
      <spec>
        In build_event_table, Mode A branch: call read_events_file(path, []) for each per-run file (no per-file required-condition enforcement). After the per-run loop, and only when no timing violations were recorded (violations already produce a fatal timing InputError in the caller), compute present = set of "condition" values over the accumulated valid rows; missing = [c for c in required_conditions if c not in present], preserving required_conditions order. If missing is non-empty, raise InputError(f"Required condition(s) {missing} not found in any supplied events file (checked the union of valid events across: {paths})", context={"missing_conditions": missing, "events_files": paths}) where paths is the list of Mode A events file paths in supplied-run order. Mode B is unchanged (read_events_file(path, required_conditions) on the single file). Update the build_event_table docstring: required_conditions must each appear in at least one supplied events file (Mode A: union over valid events of all supplied runs; Mode B: the single file).
      </spec>
      <dependencies>none</dependencies>
      <risk>low - relaxes a check; downstream handling of conditions absent from model runs already exists (task_act apply_floor; task_conn via C8).</risk>
      <rollback>Restore events.py from the backup.</rollback>
      <tests_for_test_mode>Two runs where each required condition appears in only one run: task_act and task_conn both succeed; a required condition absent from every file raises InputError naming it; a file set with timing violations still reports the timing error record first.</tests_for_test_mode>
    </change>

    <change id="C5" priority="P0" source_item="U3 via T3(1-4)">
      <file path="fmri_first_level_proc/task_act_first_level.py" action="modify" />
      <description>Smoothed task_act GLM carries the same contrasts as the unsmoothed GLM and writes tokened bucket and per-stat index files.</description>
      <spec>
        (a) New module-level helper gltsym_args(kept_contrasts, contrast_labels) -> list of str returning, for each (contrast, label) pair, ["-gltsym", "SYM: " + "".join(f"{c}*{cd} " for c, cd in zip(contrast["COEFS"], contrast["CONDS"])).strip(), "-glt_label", str(contrast_labels.index(label) + 1), label]; returns [] when kept_contrasts or contrast_labels is falsy. This reproduces the current unsmoothed construction exactly.
        (b) Unsmoothed _glm_stage: replace the inline -gltsym loop with cmd.extend(gltsym_args(getattr(ctx, "_kept_contrasts", None), config.contrast_labels)).
        (c) Smoothed _glm_smooth_stage: after the -stim_times loop, cmd.extend(gltsym_args(getattr(ctx, "_kept_contrasts", None), config.contrast_labels)). After the 3dDeconvolve call, append generate_bucket_stats_index(io, bucket_stats_rel, names.bucket_stats_index(pre, token), logger) to outputs.
        (d) Split stat_bucket_parcellations: new function write_stat_indexes(io, ext, matched, token="") -> list of Output that writes, for each stat_type in matched, the JSON {label: i for i, (label, _) in enumerate(items)} to names.stat_index(ext, stat_type, token) with the existing text format (json.dumps(..., indent=2) + "\n") and returns the same Output objects as today (cls "final", kind "py_text", producer f"{stat_type} index", expected_text). stat_bucket_parcellations no longer writes indexes and only writes parcellated CSVs when template is not None. The unsmoothed _extract_stage calls write_stat_indexes(io, ext, matched) followed by stat_bucket_parcellations (outputs unchanged in name and content).
        (e) Smoothed extraction (inside _glm_smooth_stage, under "if config.stat_buckets"): after extract_stat_bucket_niftis, outputs.extend(write_stat_indexes(io, config.extract_out_file_pre, matched, token)). No parcellated CSV for smoothed buckets.
        (f) task_act_expected, smoothing branch: add names.bucket_stats_index(pre, token); inside the stat_buckets loop add names.stat_index(ext, stat, token).
        (g) _qc_fragment adds "censor_metric": nuisance.CENSOR_METRIC and "fd_radius_mm": nuisance.FD_RADIUS_MM.
      </spec>
      <dependencies>C1, C2, C3</dependencies>
      <risk>medium - smoothed GLM gains sub-bricks; mitigated by sharing one helper and by the unchanged unsmoothed command text.</risk>
      <rollback>Restore task_act_first_level.py from the backup.</rollback>
      <tests_for_test_mode>Smoothed and unsmoothed bucket sub-brick label lists identical; each smoothed index JSON equals its unsmoothed counterpart; each smoothed stat bucket has the same volume count as its unsmoothed counterpart; unsmoothed 3dDeconvolve arguments byte-identical to the pre-change construction; expected-output set includes the two tokened names when smoothing is enabled.</tests_for_test_mode>
    </change>

    <change id="C6" priority="P0" source_item="T5(1-3); A1(5)">
      <file path="fmri_first_level_proc/task_conn_first_level.py" action="modify" />
      <description>Nuisance (non-beta) conditions are taken from the modeled runs only; QC names the censoring metric.</description>
      <spec>
        (a) Replace the non_beta_conditions computation (lines ~337-339) with: model_conditions = event_table.for_runs(list(s_pre)).conditions(); non_beta_conditions = sorted(c for c in model_conditions if c not in set(config.cond_beta_labels)). Compute dropped_nuisance = sorted(c for c in event_table.conditions() if c not in set(config.cond_beta_labels) and c not in model_conditions). If dropped_nuisance is non-empty, logger.warning(f"Nuisance condition(s) {dropped_nuisance} occur only in runs excluded before modeling ({sorted(set(runsets.supplied) - set(s_pre))}); not modeled."). non_beta_conditions remains the single list used for the onset files, -num_stimts (n_nuisance + 1) and the beta regressor index (k_beta = n_nuisance + 1).
        (b) _qc_fragment adds "censor_metric": nuisance.CENSOR_METRIC and "fd_radius_mm": nuisance.FD_RADIUS_MM.
      </spec>
      <dependencies>C2, C3</dependencies>
      <risk>low - restricts an iteration set to the runs actually modeled, matching beta_cond_order.</risk>
      <rollback>Restore task_conn_first_level.py from the backup.</rollback>
      <tests_for_test_mode>Real-AFNI test with two supplied runs where a non-beta condition occurs only in a run excluded before modeling: the analysis completes, no onset file or design-matrix column exists for that condition, the warning names it, and the beta series equals that from the same data with the condition removed from the timing files.</tests_for_test_mode>
    </change>

    <change id="C7" priority="P0" source_item="U4; T4(ii); A1(5)">
      <file path="fmri_first_level_proc/rest_conn_first_level.py" action="modify" />
      <description>Concat mode adds the GS derivative exactly as per-run mode does; QC names the censoring metric.</description>
      <spec>
        (a) In _concat_mode_stage, inside "if config.use_tissue_derivs:" after the CSF/WM loop: if tissue_paths.get("GS"): load it with load_numeric_table(tissue_paths["GS"], "GS"), take the first column, deriv = compute_tissue_derivative(tcol, [ri.n_vols]), write format_table(deriv.reshape(-1, 1)) to f"{subdir}/GS_deriv.1D", and set tissue_paths["derivs"]["GS"] = io.path(f"{subdir}/GS_deriv.1D"). This mirrors the per-run block at lines ~544-552.
        (b) _qc_fragment adds "censor_metric": nuisance.CENSOR_METRIC and "fd_radius_mm": nuisance.FD_RADIUS_MM.
      </spec>
      <dependencies>C2, C3</dependencies>
      <risk>low - adds one regressor already counted by the DOF dry run.</risk>
      <rollback>Restore rest_conn_first_level.py from the backup.</rollback>
      <tests_for_test_mode>With GS_paths set and use_tissue_derivs true, per-run and concat modes regress the same nuisance columns; in concat mode the DOF recorded from the dry run equals the residual DOF of the model actually fitted.</tests_for_test_mode>
    </change>

    <change id="C8" priority="P0" source_item="planning-time addition (user-approved): sequenced-backend tissue-derivative collision">
      <file path="fmri_first_level_proc/rest_conn_first_level.py" action="modify" />
      <description>In the sequenced backend, tissue derivatives overwrite their base regressors because both use the same dictionary key and file tag; rekey derivatives so base and derivative regressors are both regressed (restores v3.1.0 behavior).</description>
      <spec>
        In _residual_sequenced, the loop over tissue_paths.get("derivs", {}).items() uses dkey = f"{dname}_deriv" for the nuisance_interp key and f"{dname}_deriv_run{label}" as the label argument to censor_interpolate_1d_afni and bandpass_filter_1d_afni. No other change: the final-regression loop already appends every nuisance_interp entry whose key is not in ("motion", "CSF", "WM", "GS"), so derivatives follow the base regressors.
      </spec>
      <dependencies>none (same file as C7; applied by the same build agent after C7)</dependencies>
      <risk>low - local rename; fixes silent omission of base CSF/WM/GS regressors when use_sequenced_bandpass and use_tissue_derivs are both true.</risk>
      <rollback>Restore rest_conn_first_level.py from the backup.</rollback>
      <tests_for_test_mode>Sequenced backend with use_tissue_derivs true and GS set: the final 3dTproject receives seven distinct nuisance inputs (motion, CSF, WM, GS and three derivatives) with distinct intermediate files; residuals at uncensored TRs are orthogonal, within tolerance, to every bandpassed base and derivative regressor.</tests_for_test_mode>
    </change>
  </changes>

  <execution_order>C1, C2, C3, C4, C5, C6, C7, C8</execution_order>

  <build_partition>
    Group 1 (names.py, qc.py): C1, C2. Group 2 (nuisance.py): C3. Group 3 (events.py): C4. Group 4 (task_act_first_level.py): C5. Group 5 (task_conn_first_level.py): C6. Group 6 (rest_conn_first_level.py): C7 then C8. Groups 1 and 3 have no dependencies and run first in parallel; Group 2 follows Group 1; Groups 4-6 follow Group 2 and run in parallel (non-overlapping files).
  </build_partition>

  <known_test_impact>
    Existing tests in tests/test_nuisance.py and tests/test_names.py reference CENSORTR, censor_side_files or the enorm-based _censor contract and will need updating by /test, as will any test asserting per-file Mode A required-condition errors or smoothed task_act sub-brick counts.
  </known_test_impact>
</implement_plan>
