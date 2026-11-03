<implement_plan>
  <meta project="fmri-first-level-proc" mode="implement" submodule="plan" timestamp="2026-10-28T18:11:40Z" />
  <input_reports>
    <report path="fmri-first-level-proc_clean_20261028_131136.md" mode="clean" key_items="36 implement-target action items" />
    <report path="fmri-first-level-proc_cr_20261028_135535.md" mode="cr" key_items="2 implement-target action items (F2 grammar pin, F3 single build)" />
  </input_reports>
  <scope_notes>
    Included: every action item with target_mode="implement" in the two reports. Excluded by the reports' own routing: /test items, /document items (including the CR items marked "route: /document"), and the CR brainstorm item. Excluded by user decision (Gate 1, 2026-10-28): clean F36 (git-history rewrite and PR-ref purge) runs as a separate operation BEFORE this build, with its own runbook and per-step approval. Gate 1 resolution: clean F31 item 4 archive location is <sandbox>/archive_root_notes_20261028/.
    Build constraints (CR F3): every change below lands in ONE build; no intermediate pipeline run, commit or test of a subset. Line numbers are as of 2026-10-28 and drift as earlier changes land; each spec names a symbol anchor that the build must use in place of the raw line number. No runtime behavior changes except where a change says so. Source comments added by the build describe behavior only (no finding or change identifiers).
  </scope_notes>
  <changes>
    <change id="C1" priority="P2" source_item="clean F3">
      <file path="fmri_first_level_proc/first_level_config.py" action="modify" />
      <file path="fmri_first_level_proc/engine.py" action="modify" />
      <file path="fmri_first_level_proc/names.py" action="modify" />
      <file path="fmri_first_level_proc/runsets.py" action="modify" />
      <description>Remove design-session markers.</description>
      <spec>first_level_config.py: comment "# T5b: task_conn with custom HRF must produce exactly 1 column" -> "# task_conn with a custom HRF must produce exactly one basis column"; comment "# Merge overrides into every analysis block BEFORE validation (T9)" -> "# Merge overrides into every analysis block before validation". engine.py RunContext.start docstring "Initialize the engine: G4 refusal, remove_previous, history load." -> "Initialize the engine: refuse unrecorded files, apply remove_previous, load history."; _refuse_unrecorded docstring "G4(1): raise InputError if out_dir contains unrecorded files." -> "Raise InputError if out_dir contains files no ledger records.". names.legacy_template_resampled docstring "(for G4 refusal scan)" -> "(for the unrecorded-file refusal scan)". runsets.py: rename _t1_checks to _run_consistency_checks (definition and the single call in build_runsets); its docstring -> "Run run-consistency validation checks."; build_runsets docstring "(T1 checks)" -> "(run-consistency checks)"; comment "# T1 structural checks" -> "# Run-consistency checks".</spec>
      <dependencies>none</dependencies>
      <risk>low - text and a private function rename (single call site; no test or sibling references).</risk>
      <rollback>Revert the four files.</rollback>
    </change>
    <change id="C2" priority="P2" source_item="clean F4">
      <file path="fmri_first_level_proc/prep.py" action="modify" />
      <description>Fix the misplaced os import and remove unused logging import.</description>
      <spec>Delete the bottom-of-file lines `import os  # noqa: E402 -- already imported at top` and its adjacent comment (~352-353). Add `import os` to the top-level standard-library imports. Delete `import logging` (unused).</spec>
      <dependencies>none</dependencies>
      <risk>low</risk>
      <rollback>Revert prep.py.</rollback>
    </change>
    <change id="C3" priority="P2" source_item="clean F5, clean F37 (implement part)">
      <file path="fmri_first_level_proc/rest_conn_first_level.py" action="modify" />
      <description>Correct per-run regression wording; remove the always-constant intermediate_cls parameter.</description>
      <spec>(1) Module banner line ~5: state that nuisance regression and bandpass filtering run per run and residuals are then concatenated with 3dTcat. (2) Comment ~495: "One ledgered stage per run (keep_run_res_dtseries true) or one stage covering all runs (false)". (3) Comment ~625: "Single ledgered stage: per-run regressions, then 3dTcat concatenation". (4) Module docstring line ~50: replace "(kept only in per-run mode with keep_run_res_dtseries)" with "(kept only when keep_run_res_dtseries is true)". (5) _residual_sequenced: delete the intermediate_cls parameter and its docstring entry (~159-161); use the literal "intermediate" at its three Output constructions (bold_interp, bold_bp, regressed; ~185, ~198, ~268); remove the argument from both call sites (per-run stage ~568-570, concat-mode stage ~692-694).</spec>
      <dependencies>none</dependencies>
      <risk>low - both callers already pass "intermediate".</risk>
      <rollback>Revert rest_conn_first_level.py.</rollback>
    </change>
    <change id="C4" priority="P2" source_item="clean F6">
      <file path="fmri_first_level_proc/first_level_utils.py" action="modify" />
      <description>Replace argparse-flag wording in valid_contrast_functions errors.</description>
      <spec>Line ~1077 message -> f"Every contrast function must have exactly one contrast label ({len(contrast_list)} functions, {len(contrast_labs_list)} labels)." Line ~1123 message ending -> "... which is not among the configured condition labels ({cond_list})." Check logic and exception types unchanged.</spec>
      <dependencies>none</dependencies>
      <risk>low</risk>
      <rollback>Revert the two strings.</rollback>
    </change>
    <change id="C5" priority="P2" source_item="clean F7">
      <file path="fmri_first_level_proc/first_level_config.py" action="modify" />
      <description>Replace the version-tagged section comment.</description>
      <spec>Comment "# 4.0.0 additions" (~287) -> "# Run identity, smoothing, and ROI zero-handling (all analysis types; run_lengths is task-only)".</spec>
      <dependencies>none</dependencies>
      <risk>low</risk>
      <rollback>Revert the comment.</rollback>
    </change>
    <change id="C6" priority="P2" source_item="clean F8 items 1-2">
      <file path="fmri_first_level_proc/rest_conn_first_level.py" action="modify" />
      <file path="example_config.yaml" action="modify" />
      <description>Precise citations for the sequenced backend.</description>
      <spec>_residual_sequenced docstring summary -> "Compute residuals for one run via the sequenced backend: NTRP-interpolate censored TRs, 3dBandpass BOLD and nuisance regressors at the same passband, regress (no -bandpass), zero censored TRs. Interpolation before filtering and re-censoring follow Power et al. (2014), with linear rather than spectral interpolation; passband-matched regressors follow Hallquist et al. (2013), whose preferred single-step approach is the simultaneous backend." example_config.yaml line ~241 "(Ciric-inspired)" -> "(Power et al. 2014; Hallquist et al. 2013; linear NTRP rather than spectral interpolation)".</spec>
      <dependencies>C3</dependencies>
      <risk>low</risk>
      <rollback>Revert both texts.</rollback>
    </change>
    <change id="C7" priority="P2" source_item="clean F13">
      <file path="fmri_first_level_proc (19 modules)" action="modify" />
      <description>Remove hard-coded version lines.</description>
      <spec>Delete the module-docstring line "Version 4.0.0." and the blank line after it in bids.py, checkpoint.py, connectivity.py, engine.py, estimability.py, events.py, first_level_config.py (~16), nuisance.py, prep.py, qc.py, roi.py, runsets.py, runtime.py, smoothing.py. Delete the banner line "# Version: 4.0.0" in first_level_utils.py (~8), first_level_config.py (~11), task_act_first_level.py (~10), task_conn_first_level.py (~10), rest_conn_first_level.py (~12), run_first_level.py (~15). Keep banners and Author lines, __init__.__version__, pyproject version and the first_level_config error text "legacy key removed in 4.0.0".</spec>
      <dependencies>none</dependencies>
      <risk>low</risk>
      <rollback>Revert the deleted lines.</rollback>
    </change>
    <change id="C8" priority="P2" source_item="clean F14">
      <file path="fmri_first_level_proc/engine.py" action="modify" />
      <description>Condense the module docstring.</description>
      <spec>Replace module-docstring lines after the first line (formerly 5-32) with: "Provides ``RunContext``, which runs always-run steps and ledgered stages through a staging directory: outputs are validated, recorded in the ledger and promoted to out_dir with os.replace. A step appends a staged record only when its output path set changed; a stage appends a staged record and, after promotion, a completion record carrying its stage hash. A ledgered stage reruns when it has no valid completion record, its stage hash changed (declared config fields, derived files and values, upstream hashes or tool versions), a recorded output is missing, an upstream stage ran in this invocation, or its last completion recorded failed runs; otherwise its qc fragment and warnings are replayed. ``finish`` cross-checks expected outputs, retires unlisted recorded paths and writes qc_summary.json." Keep the first docstring line and all inline comments.</spec>
      <dependencies>C7</dependencies>
      <risk>low</risk>
      <rollback>Revert the docstring.</rollback>
    </change>
    <change id="C9" priority="P2" source_item="clean F15">
      <file path="fmri_first_level_proc/first_level_config.py" action="modify" />
      <description>Single source for schema_version.</description>
      <spec>Add module constant `SCHEMA_VERSION = "4.0.0"` near the other module constants; resolve_config's ResolvedConfig(...) construction uses schema_version=SCHEMA_VERSION. Module docstring: replace the schema_version policy paragraph and "Current schema_version" line (~25-32) with "Typed dataclass with all pipeline-specific fields; its docstring states the schema_version policy." ResolvedConfig docstring: "Current value: '4.0.0'." -> "Current value: SCHEMA_VERSION.". Field comment `# "4.0.0"` -> `# SCHEMA_VERSION`.</spec>
      <dependencies>C7</dependencies>
      <risk>low - same runtime value; field is exempt from stage hashes.</risk>
      <rollback>Revert first_level_config.py.</rollback>
    </change>
    <change id="C10" priority="P2" source_item="clean F16">
      <file path="fmri_first_level_proc/nuisance.py" action="modify" />
      <description>Condense the censoring paragraph; move the enorm definition into _enorm.</description>
      <spec>Replace the module-docstring "Motion censoring metric" paragraph (~12-27) with: "Censoring uses Power et al. (2012) framewise displacement (see ``_censor``); for rest_conn, FD is computed from the notch-filtered motion series when notch_filter_band is set. AFNI enorm is recorded for reference only (0.873 x enorm &lt;= FD &lt;= 2.30 x enorm). Motion input contract: the first six columns are [tx, ty, tz, rx, ry, rz] in mm and degrees; AFNI 3dvolreg -1Dfile/-dfile output (roll pitch yaw dS dL dP) must be reordered translations-first (otherwise FD is biased by roughly -13% to +15%), and fMRIPrep rotations converted from radians to degrees." (write the inequality with plain "&lt;=" characters in the source). _enorm docstring -> "Compute AFNI enorm (Euclidean norm of the backward difference, rotations unweighted in degrees) via 1d_tool.py and return the series."</spec>
      <dependencies>C7</dependencies>
      <risk>low</risk>
      <rollback>Revert nuisance.py docstrings.</rollback>
    </change>
    <change id="C11" priority="P2" source_item="clean F17">
      <file path="fmri_first_level_proc/roi.py" action="modify" />
      <file path="fmri_first_level_proc/rest_conn_first_level.py" action="modify" />
      <description>Condense two comment blocks.</description>
      <spec>roi._parse_roistats comment block (~61-68) -> `# 3dROIstats -1Dformat output: line 0 is the "#File" title; line 1 is the indented column-name line ("\t\t#\tNZMean_1...", not "#" at position 0); the remaining lines alternate a "#"-prefixed row-identifier line (skipped) and a data line.` rest_conn comment above _ensure_1d (~202-206, keep the preceding "Interpolate and bandpass..." line) -> `# AFNI opens a 1D file passed to -input with the transpose quote only when it has a .1D/.1d extension (any extension works via -ort), so user-supplied CSF/WM/GS paths are copied to a .1D name first.` connectivity.py precision paragraph unchanged.</spec>
      <dependencies>none</dependencies>
      <risk>low</risk>
      <rollback>Revert the comments.</rollback>
    </change>
    <change id="C12" priority="P2" source_item="clean F40">
      <file path="fmri_first_level_proc/nuisance.py" action="modify" />
      <description>Plain string for a placeholder-less f-string.</description>
      <spec>`producer=f"Power FD censor"` (~726) -> `producer="Power FD censor"`.</spec>
      <dependencies>none</dependencies>
      <risk>low</risk>
      <rollback>Re-add the f prefix.</rollback>
    </change>
    <change id="C13" priority="P2" source_item="clean F9">
      <file path="fmri_first_level_proc/first_level_utils.py" action="modify" />
      <description>Delete unused argparse helpers.</description>
      <spec>Delete dir_path_exists, file_path_exists, valid_string_list, valid_stat_type, valid_ave_type, valid_conn_type (~129-184), `import argparse` (~33), and the module-docstring bullet "- Argument validation and type helpers (argparse types)" (~16). Keep the "# General Helpers" section header above setup_logging. (The test-file edits are a /test item; the build report must state that tests/test_utils_unit.py still imports these names until /test runs.)</spec>
      <dependencies>none</dependencies>
      <risk>low - no package or sibling caller; local tests updated by /test.</risk>
      <rollback>Restore the functions from git (v3.1.0 commit 0ad0445 holds them).</rollback>
    </change>
    <change id="C14" priority="P2" source_item="clean F10">
      <file path="fmri_first_level_proc/first_level_config.py" action="modify" />
      <file path="fmri_first_level_proc/checkpoint.py" action="modify" />
      <file path="fmri_first_level_proc/names.py" action="modify" />
      <file path="fmri_first_level_proc/bids.py" action="modify" />
      <description>Delete unused symbols; keep EXEMPT_FIELDS, allowed_keys, runtime.reset_runtime_cache.</description>
      <spec>first_level_config.py: delete BOOL_KEYS and its comment (~148-155). checkpoint.py: delete latest_staged (~249-255). names.py: delete run_tag and its "Run identity" section header (~87-94). bids.py: delete the module-level logger (~22) and `import logging` (~15).</spec>
      <dependencies>none</dependencies>
      <risk>low - test references updated by /test.</risk>
      <rollback>Revert the four files.</rollback>
    </change>
    <change id="C15" priority="P2" source_item="clean F11">
      <file path="multiple" action="modify" />
      <description>Remove dead parameters, locals and always-true conditionals.</description>
      <spec>(1) task_act_expected: drop the contrast_labels parameter and the argument at its call. (2) nuisance._enorm: drop the motion6 parameter and update its call in _censor. (3) engine._promote: stop building and returning the records list; both callers (run_step, run_stage) call it without assignment. (4) events.py: delete run_violations_count (~280-281). (5) first_level_config._validate_extraction: delete the unused template_path local (~769). (6) rest_conn ~929: rename is_null to _. (7) runsets.build_runsets: delete is_rest (~248); in the run-consistency checks collapse the identical if/else (~338-341) to `motion = config.motion_paths[pos]`. (8) task_act ~599 and task_conn ~551: rename dropped to _. (9) task_act _glm_smooth_stage: delete k_sup (~991). (10) task_conn ~683: rename header_matrix to _. (11) task_conn _estimability_step: delete the first onset_specs assignment (~511-513). (12) raw-ptseries StageSpecs task_act ~744, task_conn ~610, rest_conn ~751: replace the conditional tuple with the literal two-element upstream tuple. (13) first_level_utils.valid_contrast_functions: delete the float(item) coefficient loop after the regex check (~1124-1129). (14) prep.py: replace the Mode A/B spec branch (~175-178) with `spec = ri.spec`, and collapse ~227-230 to `else: spec = ri.spec`.</spec>
      <dependencies>C3, C13</dependencies>
      <risk>low - behavior-preserving; verified per item during review.</risk>
      <rollback>Revert per file.</rollback>
    </change>
    <change id="C16" priority="P2" source_item="clean F21">
      <file path="fmri_first_level_proc/first_level_utils.py" action="modify" />
      <file path="fmri_first_level_proc/task_act_first_level.py" action="modify" />
      <file path="fmri_first_level_proc/task_conn_first_level.py" action="modify" />
      <file path="fmri_first_level_proc/estimability.py" action="modify" />
      <description>Shared HRF helper; hoist loop invariants.</description>
      <spec>Add next to build_hrf_string: `def hrf_for_durations(hrf_model, custom_hrf, durations):` docstring "Return the AFNI stim_times model string; duration models use the mean of *durations* (1.0 when empty)."; body: if hrf_model in HRF_DURATION_MODELS: return build_hrf_string(hrf_model, mean_dur=float(durations.mean()) if len(durations) else 1.0); else return build_hrf_string(hrf_model, custom_hrf=custom_hrf). At the five per-condition loops (task_act estimability step, GLM stage, smoothed GLM stage; task_conn design-matrix stage; estimability.estimability_dry_run), compute before the loop `run_df = event_table.for_runs(s_pre).df` (estimability: runsets.s_pre) and, where present, `married = needs_married_timing(config.hrf_model, config.custom_hrf)` and `stim_flag = "-stim_times_AM1" if married else "-stim_times"`; inside the loop `hrf = hrf_for_durations(config.hrf_model, config.custom_hrf, run_df.loc[run_df["condition"] == cond, "duration"])`. task_conn beta-HRF sites (design-matrix stage ~477 and estimability step ~515): `hrf_for_durations(config.hrf_model, config.custom_hrf, beta_only["duration"])`. HRF strings and command arguments must be byte-identical to the current output.</spec>
      <dependencies>C15</dependencies>
      <risk>low - byte-identical by construction (verified in review).</risk>
      <rollback>Revert the four files.</rollback>
    </change>
    <change id="C17" priority="P2" source_item="clean F27">
      <file path="fmri_first_level_proc/first_level_utils.py" action="modify" />
      <file path="fmri_first_level_proc/nuisance.py" action="modify" />
      <file path="fmri_first_level_proc/rest_conn_first_level.py" action="modify" />
      <file path="fmri_first_level_proc/task_conn_first_level.py" action="modify" />
      <description>One tissue-derivative writer.</description>
      <spec>Add next to compute_tissue_derivative: `def write_tissue_derivative(src_path, name, run_lengths, out_path):` docstring "Write the per-run first derivative of the first column of a tissue file and return the written text."; body: t = load_numeric_table(src_path, name); col = t[:, 0] if t.ndim &gt; 1 else t.ravel(); text = format_table(compute_tissue_derivative(col, run_lengths).reshape(-1, 1)); write with open(out_path, "w", newline=""); return text. Replace the seven file-based blocks: nuisance.rest_nuisance dry run (CSF/WM loop and GS branch), rest_conn residual-run stage (CSF/WM loop and GS branch), rest_conn concat-mode stage (CSF/WM loop and GS branch), task_conn design-matrix stage (use the returned text as expected_text). At each rest site merge the CSF/WM loop and GS branch into one loop over CSF, WM, GS in that order, skipping GS with the site's current idiom (nuisance: `gs_path is not None`; rest_conn: `tissue_paths.get("GS")` truthiness) and keeping each site's bookkeeping after the call (deriv_paths.append / tissue_paths["derivs"][t] = ...). Leave task_nuisance's array-based derivative unchanged.</spec>
      <dependencies>C3</dependencies>
      <risk>low - byte-identical files; regressor order preserved.</risk>
      <rollback>Revert the four files.</rollback>
    </change>
    <change id="C18" priority="P2" source_item="clean F28">
      <file path="fmri_first_level_proc/engine.py" action="modify" />
      <file path="fmri_first_level_proc/checkpoint.py" action="modify" />
      <description>Single JSON normalization path.</description>
      <spec>Delete engine._jsonable; in RunContext.stage_hash store `getattr(self.entry_config, f, None)` and `getattr(self.config, f, None)` directly. checkpoint._jsonable tuple branch -> `return [_jsonable(v) for v in obj]`.</spec>
      <dependencies>C8</dependencies>
      <risk>low - hashes identical for ResolvedConfig field types.</risk>
      <rollback>Revert both files.</rollback>
    </change>
    <change id="C19" priority="P2" source_item="clean F33">
      <file path="fmri_first_level_proc/rest_conn_first_level.py" action="modify" />
      <file path="fmri_first_level_proc/nuisance.py" action="modify" />
      <description>Remove repeated computations in the rest pipeline.</description>
      <spec>rest_conn: assign residual_stage_label once immediately before the "# Smoothing branch" comment; delete the assignment inside the smoothing branch and the one before the ptseries stage. In the rest-conn-smooth-residuals stage body call `n_mask, fov = smoothing.mask_stats(io.path(mask_rel), logger)` once before the per-run loop. nuisance.py: add `def _polort(n_vols, tr, bandpass):` returning `2 if bandpass[0] &gt; 0 else 1 + math.floor(n_vols * tr / 150)` with docstring "Return the per-run polynomial baseline order."; use it in rest_nuisance's dry run and in the returned state's "polort" dict.</spec>
      <dependencies>C3, C17</dependencies>
      <risk>low</risk>
      <rollback>Revert both files.</rollback>
    </change>
    <change id="C20" priority="P1" source_item="clean F26">
      <file path="fmri_first_level_proc/roi.py" action="modify" />
      <file path="fmri_first_level_proc/smoothing.py" action="modify" />
      <file path="fmri_first_level_proc/prep.py" action="modify" />
      <description>One non-constant intersection mask without a run limit.</description>
      <spec>Add to roi.py after nonconstant_mask: `def nonconstant_intersection(io, specs, rel, tag, logger):` docstring "Write the intersection of per-run non-constant masks to *rel* and return its absolute path. Each indicator is exactly 0 or 1 (step(max - min)), so the voxelwise minimum is the intersection."; body: indicators = [nonconstant_mask(io, s, f"_{tag}_nc_{i}.nii.gz", logger) for i, s in enumerate(specs)]; when len(indicators) == 1 run `3dcalc -a <indicator> -expr a -prefix io.path(rel)`; otherwise `3dMean -min -datum float -prefix io.path(rel) <indicators...>`; run with cwd=io.staging; return io.path(rel). smoothing.smoothing_mask: replace the 3dTstat loop and the 13-run 3dcalc branch with `nonconstant_intersection(io, unscaled_specs, rel, "smooth", logger)`, keep returning Output(rel, "intermediate", "nifti", producer="smoothing mask"); remove the now-unused letters string and ToolExecutionError branch. prep.py run-intersection mask block: keep the per-run spec selection (PSC run, Mode A source, else ri.spec), build the spec list, call `nonconstant_intersection(io, specs, mask_rel, "mask", logger)`, keep the Output append; remove the letters string and the InputError branch. smoothing.py and prep.py import nonconstant_intersection from .roi.</spec>
      <dependencies>C15</dependencies>
      <risk>medium - new AFNI call path (3dMean); voxel equivalence asserted by the routed /test item.</risk>
      <rollback>Revert the three files.</rollback>
    </change>
    <change id="C21" priority="P2" source_item="clean F18">
      <file path="fmri_first_level_proc/connectivity.py" action="modify" />
      <description>Vectorize parcellated().</description>
      <spec>Replace the null/non-null loop with `keep = np.ptp(df.values, axis=0) != 0`, `non_null_labels = [l for l, k in zip(all_labels, keep) if k]`, `null_labels = [l for l, k in zip(all_labels, keep) if not k]`, `nn_idx = np.flatnonzero(keep)`. Replace the partial-correlation double loop with `diag = np.diag(inv); vals = -inv / np.sqrt(np.outer(diag, diag)); np.fill_diagonal(vals, 1.0)`. Replace the NaN-expansion double loop and the all_labels.index comprehension with `full[np.ix_(nn_idx, nn_idx)] = vals`.</spec>
      <dependencies>none</dependencies>
      <risk>low - bitwise identical.</risk>
      <rollback>Revert connectivity.py.</rollback>
    </change>
    <change id="C22" priority="P2" source_item="clean F22, clean F42 item C">
      <file path="fmri_first_level_proc/first_level_utils.py" action="modify" />
      <file path="fmri_first_level_proc/roi.py" action="modify" />
      <description>Fewer AFNI calls in template checks and roi_qc; drop unused 3dinfo keys.</description>
      <spec>get_3dinfo_properties(nifti_path, logger=None, keys=None): query table becomes {"space": ["-space"], "dmax": ["-dmax"]}; when keys is None run all table keys, else only the listed keys; docstring "dict with the requested keys among 'space' and 'dmax'". roi.check_template: template call keys=("space", "dmax"); scan call keys=("space",). roi.roi_qc: replace the template_labels call and the count_nonzero_by_roi(template, template) call with one `n_vox = count_nonzero_by_roi(template_resolved, template_resolved, logger)` followed by `tlabels = sorted(n_vox)`. Delete roi.template_labels and remove it from the roi.py module-docstring "Provides" list.</spec>
      <dependencies>C15</dependencies>
      <risk>low - same values; test edits routed to /test (test_error_paths key set, test_roi template_labels test).</risk>
      <rollback>Revert both files.</rollback>
    </change>
    <change id="C23" priority="P2" source_item="clean F24">
      <file path="fmri_first_level_proc/nuisance.py" action="modify" />
      <description>task_act ortvec builder.</description>
      <spec>Add `def task_ortvecs(state, out_dir):` docstring "Return the ordered (path, name) -ortvec pairs for CSF and WM regressors and their derivatives from task_nuisance state. Derivatives are written by task_nuisance only for task_act, so this helper serves task_act."; body: pairs = []; deriv = state.get("tissue_deriv_rel", {}); for t in ("CSF", "WM"): append (f"{out_dir}/{state['tissue_rel'][t]}", f"{t}_regressor") when t in state["tissue_rel"]; then append (f"{out_dir}/{deriv[t]}", f"{t}_deriv_regressor") when t in deriv; return pairs. task_act preflight step: replace its inline loop with `ortvecs = nuisance.task_ortvecs(nuisance_state, config.out_dir)` (the GLM use is in C24). task_conn unchanged.</spec>
      <dependencies>none</dependencies>
      <risk>low</risk>
      <rollback>Revert nuisance.py and the preflight call.</rollback>
    </change>
    <change id="C24" priority="P2" source_item="clean F23">
      <file path="fmri_first_level_proc/task_act_first_level.py" action="modify" />
      <description>One GLM closure for the unsmoothed and smoothed stages.</description>
      <spec>Inside run(), define `_run_glm(io, token, stage_label, description, producer)` returning (outputs, bucket_stats_rel): model_input = prep.task_model_input(config, runsets, config.out_dir, token) (token None for unsmoothed); mask, censor, motion as today; ortvecs = nuisance.task_ortvecs(nuisance_state, config.out_dir); build_decon_base_command; -num_stimts; stim arguments via the C16 hoisted married/stim_flag/run_df and hrf_for_durations; gltsym_args; bucket_stats_rel = names.bucket_stats(pre, token), bucket_resids_rel = names.bucket_resids(pre, token); -errts/-fout/-rout/-tout/-bucket/-jobs; run_afni_command(cmd, description=description, ...); reml = collect_reml_cmds(io.staging, pre, stage_label); Outputs for stats and resids with producer=producer; REML_cmd outputs; generate_bucket_stats_index(io, bucket_stats_rel, names.bucket_stats_index(pre, token), logger). _glm_stage: `outputs, _ = _run_glm(io, None, "task-act-glm", "3dDeconvolve GLM", "3dDeconvolve GLM"); return Outcome(outputs=outputs)`. _glm_smooth_stage: `outputs, bucket_stats_rel = _run_glm(io, token, "task-act-glm-smooth", "3dDeconvolve smoothed GLM", "smoothed GLM")`, then its existing stat-bucket extraction and index writing. StageSpecs unchanged here (C30 adds derived_files).</spec>
      <dependencies>C15, C16, C23</dependencies>
      <risk>medium - large closure move; identical commands and output relpaths required.</risk>
      <rollback>Revert task_act_first_level.py.</rollback>
    </change>
    <change id="C25" priority="P2" source_item="clean F25">
      <file path="fmri_first_level_proc/roi.py" action="modify" />
      <file path="fmri_first_level_proc/smoothing.py" action="modify" />
      <file path="fmri_first_level_proc/prep.py" action="modify" />
      <file path="fmri_first_level_proc/task_act_first_level.py" action="modify" />
      <file path="fmri_first_level_proc/task_conn_first_level.py" action="modify" />
      <file path="fmri_first_level_proc/rest_conn_first_level.py" action="modify" />
      <description>Shared stage bodies.</description>
      <spec>(1) roi.template_stage(ctx, config, runsets, pre, same_grid, analysis, logger) -> str: builds StageSpec(label=f"{analysis}-template", fields=("template_path",), derived_files and derived_values as specified in C31), runs ctx.run_stage with the current resample-or-no-output body (roi.resample_template to names.template_resampled(pre, config.template_path) when not same_grid), and returns the resolved template path (f"{config.out_dir}/{names.template_resampled(pre, config.template_path)}" when not same_grid, else config.template_path). Replaces the template blocks in task_act, task_conn and rest_conn (analysis = "task-act", "task-conn", "rest-conn"). roi.py imports StageSpec and Outcome from .engine. (2) smoothing.task_smooth(io, config, runsets, s_pre, pre, token, logger) -> Outcome: the current task_act/task_conn _smooth_stage body with smoothing.mask_stats called once before the per-run loop; both stage closures become `return smoothing.task_smooth(io, config, runsets, s_pre, pre, token, logger)`; smoothing.py imports prep. (3) roi.task_roi_qc(io, config, runsets, s_pre, template_resolved, pre, logger) -> Outcome: the current task_act/task_conn _roiqc_stage body. (4) prep.task_raw_ptseries(io, config, runsets, template_resolved, logger) -> Outcome: the shared raw-ptseries body; unscaled input from `cp = copy.copy(config); cp.scale_to_psc = False; prep.task_model_input(cp, runsets, config.out_dir)`; delete task_act's module-level dataclasses_copy_without_psc and task_conn's inline copy. rest_conn smoothing, roi-qc and raw-ptseries bodies unchanged.</spec>
      <dependencies>C15, C20</dependencies>
      <risk>medium - cross-module moves; stage labels and hashes must be unchanged (other than C31's additions).</risk>
      <rollback>Revert the six files.</rollback>
    </change>
    <change id="C26" priority="P2" source_item="clean F32">
      <file path="fmri_first_level_proc/task_conn_first_level.py" action="modify" />
      <description>Top-level os import.</description>
      <spec>Add `import os` after `import logging` in the top-level imports; delete both function-local `import os as _os`; `_os.path.exists` -> `os.path.exists`.</spec>
      <dependencies>none</dependencies>
      <risk>low</risk>
      <rollback>Revert.</rollback>
    </change>
    <change id="C27" priority="P1" source_item="clean F2">
      <file path="fmri_first_level_proc/task_act_first_level.py" action="modify" />
      <file path="fmri_first_level_proc/first_level_config.py" action="modify" />
      <description>Correct -glt_label numbering; reject duplicate or colliding contrast labels.</description>
      <spec>gltsym_args: `for k, (contrast, label) in enumerate(zip(kept_contrasts, contrast_labels), 1):` and emit `"-glt_label", str(k), label`. first_level_config._validate_contrasts: for task_act contrasts.labels and task_conn connectivity.contrasts.labels, after the length checks raise ConfigError(f"[{label}] contrast labels must be unique; duplicated: {dups}.") when any label repeats, and ConfigError(f"[{label}] contrast labels {group} map to the same filename label '{safe}' after sanitization; rename them.") when two distinct labels share sanitize_filename_label(...) output. Import sanitize_filename_label from .first_level_utils.</spec>
      <dependencies>none</dependencies>
      <risk>low - consumer templates checked: no duplicates or collisions.</risk>
      <rollback>Revert both files.</rollback>
    </change>
    <change id="C28" priority="P0" source_item="clean F34, clean F19, CR F2 item 1">
      <file path="fmri_first_level_proc/task_act_first_level.py" action="modify" />
      <description>Rewrite stat-bucket selection and indexing with a pinned key grammar.</description>
      <spec>Key grammar (pinned): each sub-brick key is the exact label printed by `3dinfo -label` for the stats bucket (e.g. "ave_negface_GLT#0_Coef", "0_back_negface#0_Tstat", "Full_Fstat", "ave_negface_GLT_R^2"); a Z bucket uses the corresponding Tstat label with the trailing "Tstat" replaced by "Zstat"; the index JSON maps key -&gt; 0-based position in the extracted bucket; the parcellation CSV row label (index column "condition") is the same key. Selection: read labels with `3dinfo -label bucket_path` split on "|" (strip whitespace); a label belongs to stat type S when it ends with "_" + S, where Zstat selects "_Tstat" labels; this includes Full_Fstat and Full_R^2. Replace _get_subbrik_stat_aux with `_get_stataux(bucket_path, logger)` that runs `3dAttribute BRICK_STATAUX` once and returns {index: [params]} parsed from (index, stat_code, npar, params...) groups, binding the stat code to _, keeping the first occurrence of a duplicated index, stopping at a parse failure as today, and wrapping ToolExecutionError in GuardError. extract_stat_bucket_niftis: build matched lists [(key, orig_idx)] from the label list; for Zstat call _get_stataux once, look up `stataux.get(idx, [])` (GuardError when empty, as today), `dof = int(aux_params[0])`, and write temporaries with positional names `_zconv_tmp_{i}.nii.gz`; when a requested stat type matches nothing, keep the existing logger warning and skip. write_stat_indexes and stat_bucket_parcellations consume the new keys unchanged in shape. Module docstring: describe the key grammar in one sentence.</spec>
      <dependencies>C24</dependencies>
      <risk>medium - output index keys change (documented contract; /document and /test items routed).</risk>
      <rollback>Revert task_act_first_level.py.</rollback>
    </change>
    <change id="C29" priority="P1" source_item="clean F35, CR F2 item 1">
      <file path="fmri_first_level_proc/names.py" action="modify" />
      <file path="fmri_first_level_proc/estimability.py" action="modify" />
      <file path="fmri_first_level_proc/task_conn_first_level.py" action="modify" />
      <description>LSS sub-brick identity outputs with pinned schemas.</description>
      <spec>names.py: `def lss_index(pre, token=""): return with_token(f"{pre}_concat_LSS_index.json", token)` and `def bseries_index(pre, cond, token=""): return with_token(f"{pre}_concat_bseries_{cond}_index.json", token)`. Schemas (pinned): LSS index JSON = list ordered by sub-brick, one record per 3dLSS sub-brick: {"lss_index": int, "condition": str, "run": int, "onset": float, "survived": bool, "beta_series_position": int or null}, built from ctx._beta_column_order and the trials records. bseries index JSON = list ordered by beta_series_position: {"beta_series_position": int, "lss_index": int, "run": int, "onset": float}. estimability.build_trials (task_conn only): add "lss_index" to every record: the trial's position in column_order for trials in S_pre runs, None for run-excluded trials; task_act records unchanged. task_conn beta-series stage: write names.lss_index(pre) (always) and names.bseries_index(pre, cond) next to each bseries file it writes, as final py_text Outputs with expected_text (json.dumps(obj, indent=2) + "\n"); beta-series-smooth stage writes the same content under the smoothing token. task_conn_expected adds names.lss_index(pre) and names.bseries_index(pre, cond) for each surviving condition, plus the token siblings when smoothing is enabled.</spec>
      <dependencies>C26</dependencies>
      <risk>medium - new output files and a new trials field.</risk>
      <rollback>Revert the three files.</rollback>
    </change>
    <change id="C30" priority="P0" source_item="clean F42 item B, clean F42a">
      <file path="fmri_first_level_proc/task_act_first_level.py" action="modify" />
      <file path="fmri_first_level_proc/task_conn_first_level.py" action="modify" />
      <file path="fmri_first_level_proc/rest_conn_first_level.py" action="modify" />
      <description>Hash the content of files the model stages pass to AFNI.</description>
      <spec>task_act: before glm_spec, build `glm_files = [f"{config.out_dir}/{names.censor(pre, None)}", f"{config.out_dir}/{nuisance_state['motion_rel']}"] + [f"{config.out_dir}/{names.onset_file(pre, c)}" for c in config.cond_labels] + [f"{config.out_dir}/{nuisance_state['tissue_rel'][t]}" for t in ("CSF", "WM") if t in nuisance_state['tissue_rel']] + [f"{config.out_dir}/{d}" for t, d in sorted(nuisance_state.get('tissue_deriv_rel', {}).items())]`; pass derived_files=tuple(glm_files) to both glm_spec and glm_smooth_spec (explicitly; the smoothed spec does not inherit it). task_conn design-matrix StageSpec: derived_files = censor, prepared motion, names.onset_file(pre, c) for non-beta conditions, names.beta_onsets(pre), and names.tissue_prepared files present in nuisance_state['tissue_rel'] (all under config.out_dir). rest_conn: residual-run StageSpec derived_files additionally include config.CSF_paths[pos], config.WM_paths[pos] and, when config.GS_paths is set, config.GS_paths[pos] for that run; residuals-concat derived_files additionally include the same three per run for every run it regresses. Scan files remain path-only.</spec>
      <dependencies>C24, C25, C29</dependencies>
      <risk>medium - every affected stage reruns once after upgrade (intended).</risk>
      <rollback>Remove the derived_files additions.</rollback>
    </change>
    <change id="C31" priority="P0" source_item="clean F42 item A">
      <file path="fmri_first_level_proc/roi.py" action="modify" />
      <description>Template stage hashes template content and scan grid.</description>
      <spec>In roi.template_stage (C25): `scan_grid = " ".join(run_afni_command(["3dinfo", "-n3", "-aform_real", runsets.grid_ref], capture_output=True, description="3dinfo scan grid", logger=logger).split())`; StageSpec(label=f"{analysis}-template", fields=("template_path",), derived_files=(config.template_path,), derived_values={"same_grid": same_grid, "scan_grid": scan_grid}).</spec>
      <dependencies>C25</dependencies>
      <risk>low - one extra 3dinfo call per invocation.</risk>
      <rollback>Revert to fields and same_grid only.</rollback>
    </change>
    <change id="C32" priority="P2" source_item="clean F12">
      <file path="fmri_first_level_proc (15 modules)" action="modify" />
      <description>Remove unused imports after all other changes.</description>
      <spec>Run the scratchpad AST checker (unused_imports.py) against the package after C1-C31 and remove every unused name it reports, which must include the 38 listed in the clean report where they remain unused (connectivity: logging, re, pd, names; estimability: logging, Output, collect_reml_cmds; events: json, logging, names; first_level_config: re; first_level_utils: json, ModelError; nuisance: logging; rest_conn: json, logging, math, re, InputError, FirstLevelResult, run_afni_capture; roi: logging, os, names; runsets: logging, math; smoothing: logging, re; task_act: logging, ConfigError, ModelError, FirstLevelResult; task_conn: logging, pd, ConfigError, ToolExecutionError, FirstLevelResult) and any made unused by C16, C20, C25 (for example HRF_DURATION_MODELS and build_hrf_string in task_act/task_conn/estimability). Keep the run_* re-exports in __init__.py and `from __future__ import annotations`. Drop only unused names from multi-name statements. Run reexport_check.py to confirm no removed name is a re-export.</spec>
      <dependencies>C1-C31</dependencies>
      <risk>low</risk>
      <rollback>Re-add imports.</rollback>
    </change>
    <change id="C33" priority="P2" source_item="clean F31 items 2 and 4">
      <file path="project root" action="delete" />
      <description>Remove local clutter and archive working notes (all git-ignored).</description>
      <spec>Ask the user for per-invocation permission before each removal, then delete: 3dDeconvolve.err, Decon.REML_cmd, excalidraw.log, build/, fmri_first_level_proc.egg-info/. Create <sandbox>/archive_root_notes_20261028/ and move (not copy) into it: ABCD_fmri_orchestrator_S3_brainstorm_upstream_20261015_150913.md, FIX_fromOrch.txt, HARMONIZE_fmri-first-level-proc_20260816_212459.md, TODO_fmri-first-level-proc_20260812_132545.md, upstream_polort_dof_issue.md, proc_config_final.yaml, proc_config_final_run.yaml (each move removes the source, so each requires per-invocation permission; confirm no destination file exists before moving). The six root skill reports stay for /end-session; tests/ removals are a /test item.</spec>
      <dependencies>none</dependencies>
      <risk>low - none tracked by git; moves preserve content.</risk>
      <rollback>Move files back from the archive; rebuild build/ and egg-info with pip install -e.</rollback>
    </change>
  </changes>
  <execution_order>C1, C2, C3, C4, C5, C6, C7, C8, C9, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, C22, C23, C24, C25, C26, C27, C28, C29, C30, C31, C32, C33</execution_order>
  <post_build_routing>
    /test (from the input reports, not executed here): F9/F10/F22/F42(C) test edits; F18, F21, F26, F28 tests; F34 real-AFNI tests for every stat type with the F41 DOF assertion and the pinned key grammar including multi-basis HRFs (CR F2); F35 schema tests; F42/F42a ledger rerun tests; F10 coverage tests; F29 markers; F30 Python 3.14 suite run (release gate); F31 tests/ deletions; F38 contract test; all verification in fresh out_dirs, recomputing any pre-clean v4.0.0-build output directory (CR F3). /document: F1, F2, F8 items 3-5, F31 CHANGELOG (with CR F7 Removed entry and F38), F37, F38, F39, CR F2 grammar documentation. Separate operation before this build: F36 runbook.
  </post_build_routing>
</implement_plan>
