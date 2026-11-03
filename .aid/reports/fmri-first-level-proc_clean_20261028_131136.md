<clean_report>
  <meta project="fmri-first-level-proc" mode="clean" timestamp="2026-10-28T17:11:36Z" />
  <scope>Full package fmri_first_level_proc/ (22 modules) on branch v4.0.0-build (uncommitted), plus README.md, INPUT_SPECIFICATION.md, example_config.yaml, pyproject.toml, environment.yaml, tools.lock.yaml, .gitignore, .aid/ reports, AID_LOG.md, tests/ (local only) and every blob reachable from every git ref (participant-ID sweep). Focus: dead code, stale or verbose comments, stale citations, project/session markers, Big-O inefficiencies, and anything inappropriate to publish. Sibling projects fmri-proc-orchestrator and fmri-preproc and the private downstream consumer project were read (not modified) to check harmonization and external use of anything proposed for removal. Downstream consumers of this report: /implement, /test, /document, /end-session.</scope>
  <research_conducted>
    R1 (approved topic, F8): sequenced denoising citations. Receipts checked against PMC full text: Ciric et al. 2017 (doi 10.1016/j.neuroimage.2017.03.020, PMID 28302591), Hallquist et al. 2013 (doi 10.1016/j.neuroimage.2013.05.116, PMID 23747457), Power et al. 2014 (doi 10.1016/j.neuroimage.2013.08.048, PMID 23994314), Ciric et al. 2018 (doi 10.1038/s41596-018-0065-y, PMID 30446748).
    Empirical AFNI 26.0.09 checks: sub-brick labelling of 3dDeconvolve buckets (F2, F34); BRICK_STATAUX DOF across five synthetic 3dDeconvolve configurations using the package's base flags (F41: every t DOF integer and equal to uncensored TRs minus design-matrix columns); local AFNI help for 3dinfo (-nijk is a product; -n3 gives per-axis counts), 3dMean (-min), 3dmask_tool and 3dcalc (fitt_t2z).
    Design-intent sources: brainstorm_history/fmri-first-level-proc_brainstorm_20261009_112745.md (stage hashing, template stage T11-b, output classification, CLI alias A2, lockfile T12f, smoothing) and implement_plan_20261009_120006.md.
    Every presented recommendation was checked by one proposal-verification agent (per the user's process instruction); concerns were folded in before presentation and are recorded per finding.
  </research_conducted>
  <metrics>
    <loc>12169 (package .py)</loc>
    <files>22 package modules</files>
    <avg_complexity>not measured (radon/ruff not installed; AST scripts used for import analysis)</avg_complexity>
  </metrics>
  <decisions_note>
    Locked-decision revisions made in this review: (a) brainstorm_20261009_112745 stage-hashing decision (5) is revised for tissue files: CSF/WM/GS regressor content is now hashed (F42a); the historical brainstorm report is not edited. (b) F10's original removal of EXEMPT_FIELDS and allowed_keys was withdrawn because the v4.0.0 design uses both (F10 revised). (c) F42(C) supersedes F22's retention of the orient/spacing 3dinfo queries. (d) F5 item (5) and F37 item (2) describe the same change (remove _residual_sequenced's intermediate_cls parameter); implement once.
  </decisions_note>
  <findings>
    <finding id="F1" severity="major" category="maintainability">
      <location file=".aid/reports/fmri-first-level-proc_brainstorm_20260825_185436.md" lines="41" />
      <description>A published .aid report names the private downstream consumer project (one occurrence). References to fmri-bids-recon, fmri-preproc and fmri-proc-orchestrator are permitted.</description>
      <current>Private project name present in a published report.</current>
      <proposed>/document: redact that single occurrence. Git history unchanged.</proposed>
      <literature>n/a</literature>
      <impact>Removes a private-project disclosure from the published repository.</impact>
    </finding>
    <finding id="F2" severity="major" category="correctness">
      <location file="fmri_first_level_proc/task_act_first_level.py" lines="139-150" />
      <description>gltsym_args numbers -glt_label with contrast_labels.index(label), which returns the first match, so duplicate labels get the wrong index; config never rejects duplicate or post-sanitization-colliding contrast labels.</description>
      <current>Index by list.index; no duplicate check.</current>
      <proposed>/implement: number -glt_label by enumerate position; raise ConfigError on duplicate contrast labels and on labels that collide after filename sanitization. /document: every post-regression output (task_act and task_conn) explicitly documents its sub-brick identifiers; the regression-command contrast index must never be assumed equal to the output sub-brick index. /test: duplicate and colliding labels raise ConfigError; -glt_label indices are 1..K in order.</proposed>
      <literature>AFNI 26.0.09 bucket labelling probed empirically (several sub-bricks per condition/contrast).</literature>
      <impact>Prevents mislabelled contrasts and silent filename collisions.</impact>
    </finding>
    <finding id="F3" severity="minor" category="maintainability">
      <location file="fmri_first_level_proc/first_level_config.py; engine.py; names.py; runsets.py" lines="first_level_config 668, 1271; engine 196, 213; names 331; runsets 229, 287, 327" />
      <description>Design-session markers (T5b, T9, G4, G4(1), T1) in comments and the function name _t1_checks.</description>
      <current>Session-specific shorthand in published code.</current>
      <proposed>/implement: reword each marker to a plain description; rename _t1_checks to _run_consistency_checks and use "run-consistency checks" wording. /test: update the tests/test_names.py docstring marker.</proposed>
      <literature>n/a</literature>
      <impact>Removes unpublishable session shorthand.</impact>
    </finding>
    <finding id="F4" severity="minor" category="maintainability">
      <location file="fmri_first_level_proc/prep.py" lines="352-353" />
      <description>Bottom-of-file `import os  # noqa: E402 -- already imported at top` with a false comment; os is not imported at top; `import logging` unused.</description>
      <current>Late import with an inaccurate comment.</current>
      <proposed>/implement: delete lines 352-353, add top-level `import os`, remove unused `import logging`.</proposed>
      <literature>n/a</literature>
      <impact>Correct, conventional imports.</impact>
    </finding>
    <finding id="F5" severity="minor" category="maintainability">
      <location file="fmri_first_level_proc/rest_conn_first_level.py" lines="5, 50, 159-161, 495, 625" />
      <description>Wording implies a concatenated regression mode; regression is always per run, followed by 3dTcat. _residual_sequenced's intermediate_cls parameter is always "intermediate".</description>
      <current>Misleading banner/comments; dead parameter.</current>
      <proposed>/implement: (1) line 5 banner: nuisance regression and bandpass run per run, residuals then concatenated with 3dTcat; (2) line 495: one ledgered stage per run (keep_run_res_dtseries true) or one stage covering all runs (false); (3) line 625: "Single ledgered stage: per-run regressions, then 3dTcat concatenation"; (4) line 50: "(kept only when keep_run_res_dtseries is true)"; (5) remove intermediate_cls, hard-code "intermediate" at its three Output constructions, update both call sites, correct the docstring (same change as F37 item 2).</proposed>
      <literature>n/a</literature>
      <impact>Accurate documentation; behavior-preserving.</impact>
    </finding>
    <finding id="F6" severity="minor" category="maintainability">
      <location file="fmri_first_level_proc/first_level_utils.py" lines="1077, 1123" />
      <description>valid_contrast_functions error messages cite argparse flags that no longer exist.</description>
      <current>"--contrast_functions/--contrast_labels/--cond_labels" in ConfigError text.</current>
      <proposed>/implement: line 1077 f"Every contrast function must have exactly one contrast label ({len(contrast_list)} functions, {len(contrast_labs_list)} labels)."; line 1123 ending "... which is not among the configured condition labels ({cond_list})." Checks unchanged.</proposed>
      <literature>n/a</literature>
      <impact>Error messages refer to YAML keys users actually set.</impact>
    </finding>
    <finding id="F7" severity="style" category="maintainability">
      <location file="fmri_first_level_proc/first_level_config.py" lines="287" />
      <description>"# 4.0.0 additions" comment.</description>
      <current>Version-tagged comment.</current>
      <proposed>/implement: replace with "# Run identity, smoothing, and ROI zero-handling (all analysis types; run_lengths is task-only)". (The first_level_utils argparse docstring bullet is removed under F9.)</proposed>
      <literature>n/a</literature>
      <impact>Descriptive comment that will not go stale.</impact>
    </finding>
    <finding id="F8" severity="minor" category="maintainability">
      <location file="rest_conn_first_level.py; example_config.yaml; README.md; INPUT_SPECIFICATION.md; AID_LOG.md; .aid/reports/fmri_first_level_proc_test_20260501_140346.md" lines="docstring; 241; 10; 295; 105; 52" />
      <description>Vague "(Ciric-inspired)" citation for the sequenced backend and a wrong PMID in an .aid report.</description>
      <current>Imprecise attribution.</current>
      <proposed>/implement: (1) _residual_sequenced docstring: "Compute residuals for one run via the sequenced backend: NTRP-interpolate censored TRs, 3dBandpass BOLD and nuisance regressors at the same passband, regress (no -bandpass), zero censored TRs. Interpolation before filtering and re-censoring follow Power et al. (2014), with linear rather than spectral interpolation; passband-matched regressors follow Hallquist et al. (2013), whose preferred single-step approach is the simultaneous backend." (2) example_config.yaml:241 "(Power et al. 2014; Hallquist et al. 2013; linear NTRP rather than spectral interpolation)". /document: (3) README.md:10 and INPUT_SPECIFICATION.md:295 "following Power et al. (2014) and Hallquist et al. (2013), as benchmarked in Ciric et al. (2017), with linear NTRP rather than spectral interpolation"; (4) AID_LOG.md:105 "Implements interpolate-before-filter ordering (Power et al. 2014; Ciric et al. 2017) using linear NTRP interpolation, with nuisance regressors filtered at the same passband (Hallquist et al. 2013)"; (5) the .aid test report line 52 PMID 30446748 -> 28302591.</proposed>
      <literature>Power et al. 2014 PMID 23994314; Hallquist et al. 2013 PMID 23747457; Ciric et al. 2017 PMID 28302591; Ciric et al. 2018 PMID 30446748.</literature>
      <impact>Defensible, specific citations.</impact>
    </finding>
    <finding id="F9" severity="minor" category="redundancy">
      <location file="fmri_first_level_proc/first_level_utils.py" lines="16, 33, 129-184" />
      <description>Six argparse type helpers (dir_path_exists, file_path_exists, valid_string_list, valid_stat_type, valid_ave_type, valid_conn_type) referenced only by tests.</description>
      <current>Dead helpers and `import argparse`.</current>
      <proposed>/implement: delete lines 129-184, `import argparse` (33) and the docstring bullet (16); keep the "# General Helpers" header. /test: tests/test_utils_unit.py delete TestArgparseValidators and its header (56-103), the six import names (18-19) and `import argparse` (9); docstring drops "argparse validators, " and "(including the CR F15 headerless-confounds requirement)" becomes "(including headerless confounds)".</proposed>
      <literature>n/a</literature>
      <impact>About 60 fewer lines; no external users (sibling/consumer imports checked).</impact>
    </finding>
    <finding id="F10" severity="minor" category="redundancy">
      <location file="first_level_config.py; checkpoint.py; names.py; bids.py" lines="148-155; 249-255; 87-94; 15, 22" />
      <description>Unused BOOL_KEYS, checkpoint.latest_staged, names.run_tag, and bids' shadowed module logger. EXEMPT_FIELDS and allowed_keys are kept (v4.0.0 design uses them).</description>
      <current>Dead symbols.</current>
      <proposed>/implement: delete BOOL_KEYS (148-155), latest_staged (249-255), run_tag and its "Run identity" header (87-94), bids module logger (22) and `import logging` (15). Keep EXEMPT_FIELDS, allowed_keys, runtime.reset_runtime_cache. /test: test_sequenced_config.py remove BOOL_KEYS import (23), delete the bool_keys test and header (93-100), docstrings 3-4 -> resolve_config coerces with bool() (null->False), line 9 -> "The key is rejected under the global section", delete line-13 marker, line-131 header -> "Global section rejects block-only keys", line-151 docstring -> coerced to False by resolve_config; test_checkpoint.py remove latest_staged import and its test; test_names.py delete test_run_tag_unpadded and header (87-93). New /test items: (a) stage-field coverage: every ResolvedConfig field is declared by some StageSpec or listed in EXEMPT_FIELDS, and an attribute-read proxy confirms no stage reads an undeclared field (beyond exempt fields and censor_path); (b) every allowed_keys(atype) key is documented in INPUT_SPECIFICATION.md.</proposed>
      <literature>brainstorm_20261009_112745 stage-hashing decision (4) and INPUT_SPEC decision (9).</literature>
      <impact>Dead code removed; design-mandated coverage tests added.</impact>
    </finding>
    <finding id="F11" severity="minor" category="redundancy">
      <location file="multiple" lines="see proposed" />
      <description>Dead parameters, locals, assignments and always-true conditionals.</description>
      <current>14 instances.</current>
      <proposed>/implement: (1) task_act_expected drop contrast_labels param (347) and argument (1098); (2) nuisance._enorm drop motion6 (86; call 134); (3) engine._promote only moves files (drop records list/return, 419-430), calls at 487/603 without assignment; (4) events.py delete run_violations_count (280-281); (5) first_level_config.py delete template_path local (769); (6) rest_conn 929 is_null -> _; (7) runsets.py delete is_rest (248) and collapse identical if/else (338-341) to `motion = config.motion_paths[pos]`; (8) task_act 599 and task_conn 551 dropped -> _; (9) task_act 991 delete k_sup; (10) task_conn 683 header_matrix -> _; (11) task_conn delete the first onset_specs assignment (511-513); (12) literal upstream tuples at task_act 744, task_conn 610, rest_conn 751; (13) first_level_utils delete the float(item) coefficient loop (~1124-1129); (14) prep.py 175-178 -> spec = ri.spec and 227-230 collapse to else: spec = ri.spec. (task_act stype handled in F19.)</proposed>
      <literature>n/a</literature>
      <impact>Behavior-preserving simplification.</impact>
    </finding>
    <finding id="F12" severity="minor" category="redundancy">
      <location file="15 modules" lines="see proposed" />
      <description>38 unused imports.</description>
      <current>Unused names imported.</current>
      <proposed>/implement: remove only these names. connectivity: logging, re, pd, names; estimability: logging, Output, collect_reml_cmds; events: json, logging, names; first_level_config: re; first_level_utils: json, ModelError; nuisance: logging; rest_conn: json, logging, math, re, InputError, FirstLevelResult, run_afni_capture; roi: logging, os, names; runsets: logging, math; smoothing: logging, re; task_act: logging, ConfigError, ModelError, FirstLevelResult; task_conn: logging, pd, ConfigError, ToolExecutionError, FirstLevelResult. Keep the run_* re-exports in __init__.py and `from __future__ import annotations`. Imports made newly used or unused by other findings (e.g., os in roi under F25/F26, HRF_DURATION_MODELS/build_hrf_string under F21) are resolved at implementation time against the final code.</proposed>
      <literature>n/a</literature>
      <impact>Cleaner module surfaces; no external users.</impact>
    </finding>
    <finding id="F13" severity="style" category="maintainability">
      <location file="19 modules" lines="see proposed" />
      <description>Hard-coded version strings in docstrings and banners.</description>
      <current>"Version 4.0.0." in 14 module docstrings; "# Version: 4.0.0" in 6 banners.</current>
      <proposed>/implement: delete the "Version 4.0.0." docstring line (and following blank line) in bids, checkpoint, connectivity, engine, estimability, events, first_level_config (16), nuisance, prep, qc, roi, runsets, runtime, smoothing; delete "# Version: 4.0.0" in first_level_utils (8), first_level_config (11), task_act (10), task_conn (10), rest_conn (12), run_first_level (15). Keep banners, Author lines, __version__, pyproject version and first_level_config:416 "legacy key removed in 4.0.0".</proposed>
      <literature>n/a</literature>
      <impact>Single source of version truth.</impact>
    </finding>
    <finding id="F14" severity="style" category="maintainability">
      <location file="fmri_first_level_proc/engine.py" lines="5-32" />
      <description>28-line module docstring enumerating protocol steps duplicated by inline comments.</description>
      <current>Numbered write protocol, (a)-(e) triggers, end-of-run list.</current>
      <proposed>/implement: replace lines 5-32 with: "Provides ``RunContext``, which runs always-run steps and ledgered stages through a staging directory: outputs are validated, recorded in the ledger and promoted to out_dir with os.replace. A step appends a staged record only when its output path set changed; a stage appends a staged record and, after promotion, a completion record carrying its stage hash. A ledgered stage reruns when it has no valid completion record, its stage hash changed (declared config fields, derived files and values, upstream hashes or tool versions), a recorded output is missing, an upstream stage ran in this invocation, or its last completion recorded failed runs; otherwise its qc fragment and warnings are replayed. ``finish`` cross-checks expected outputs, retires unlisted recorded paths and writes qc_summary.json." Keep the first line and inline comments.</proposed>
      <literature>n/a</literature>
      <impact>Same contract in one paragraph.</impact>
    </finding>
    <finding id="F15" severity="minor" category="redundancy">
      <location file="fmri_first_level_proc/first_level_config.py" lines="25-32, 207-215, 918" />
      <description>schema_version policy written twice; "4.0.0" literal in four places.</description>
      <current>Duplicated policy text and literal.</current>
      <proposed>/implement: add SCHEMA_VERSION = "4.0.0" and use it at 918; module docstring 25-32 -> "Typed dataclass with all pipeline-specific fields; its docstring states the schema_version policy."; class docstring "Current value: '4.0.0'." -> "Current value: SCHEMA_VERSION."; line-215 comment -> "# SCHEMA_VERSION".</proposed>
      <literature>n/a</literature>
      <impact>One literal to change at each schema bump.</impact>
    </finding>
    <finding id="F16" severity="minor" category="redundancy">
      <location file="fmri_first_level_proc/nuisance.py" lines="12-27, 87" />
      <description>16-line FD paragraph duplicates _censor; unique content must be kept.</description>
      <current>Verbose module docstring paragraph.</current>
      <proposed>/implement: replace 12-27 with: "Censoring uses Power et al. (2012) framewise displacement (see ``_censor``); for rest_conn, FD is computed from the notch-filtered motion series when notch_filter_band is set. AFNI enorm is recorded for reference only (0.873 x enorm &lt;= FD &lt;= 2.30 x enorm). Motion input contract: the first six columns are [tx, ty, tz, rx, ry, rz] in mm and degrees; AFNI 3dvolreg -1Dfile/-dfile output (roll pitch yaw dS dL dP) must be reordered translations-first (otherwise FD is biased by roughly -13% to +15%), and fMRIPrep rotations converted from radians to degrees." _enorm docstring -> "Compute AFNI enorm (Euclidean norm of the backward difference, rotations unweighted in degrees) via 1d_tool.py and return the series."</proposed>
      <literature>Power et al. 2012.</literature>
      <impact>About 10 fewer lines, no content lost.</impact>
    </finding>
    <finding id="F17" severity="style" category="maintainability">
      <location file="roi.py; rest_conn_first_level.py; connectivity.py" lines="61-68; 202-206; 9-15" />
      <description>Comment blocks longer than three lines.</description>
      <current>8-, 6- and 7-line comments.</current>
      <proposed>/implement: roi.py 61-68 -> `# 3dROIstats -1Dformat output: line 0 is the "#File" title; line 1 is the indented column-name line ("\t\t#\tNZMean_1...", not "#" at position 0); the remaining lines alternate a "#"-prefixed row-identifier line (skipped) and a data line.`; rest_conn 202-206 (keep 201) -> `# AFNI opens a 1D file passed to -input with the transpose quote only when it has a .1D/.1d extension (any extension works via -ort), so user-supplied CSF/WM/GS paths are copied to a .1D name first.`; connectivity precision paragraph unchanged (numerical justification).</proposed>
      <literature>n/a</literature>
      <impact>Shorter comments, content preserved.</impact>
    </finding>
    <finding id="F18" severity="minor" category="time_complexity">
      <location file="fmri_first_level_proc/connectivity.py" lines="189-197, 243-250, 259-262" />
      <description>Per-ROI Python loops and list.index (O(R^2) comparisons); full-rank partial-correlation values untested.</description>
      <current>Loops for null detection, pcorr and NaN expansion.</current>
      <proposed>/implement: keep = np.ptp(df.values, axis=0) != 0 with non_null_labels, null_labels and nn_idx = np.flatnonzero(keep); diag = np.diag(inv); vals = -inv / np.sqrt(np.outer(diag, diag)); np.fill_diagonal(vals, 1.0); full[np.ix_(nn_idx, nn_idx)] = vals. /test: known-answer test of parcellated(pcorr=True) on full-rank synthetic data against numpy partial correlations from inv(corr), tolerance consistent with 1ddot's five-decimal output.</proposed>
      <literature>n/a</literature>
      <impact>Bitwise-identical output; simpler code; closes a test gap.</impact>
    </finding>
    <finding id="F19" severity="minor" category="performance">
      <location file="fmri_first_level_proc/task_act_first_level.py" lines="94-132, 261" />
      <description>One 3dAttribute BRICK_STATAUX subprocess per Zstat sub-brick; unused local stype.</description>
      <current>K identical subprocesses.</current>
      <proposed>/implement (within the F34 rewrite): replace _get_subbrik_stat_aux with _get_stataux(bucket_path, logger) returning {index: params} from one call (stat code bound to _, first occurrence kept on a duplicate index, GuardError wrapping kept); call once before the T-to-Z loop and use stataux.get(idx, []) with the existing GuardError on empty.</proposed>
      <literature>n/a</literature>
      <impact>K subprocesses -> 1.</impact>
    </finding>
    <finding id="F20" severity="minor" category="time_complexity">
      <location file="fmri_first_level_proc/events.py" lines="412-444" />
      <description>onset_rows_labeled does O(R x C x N) mask work.</description>
      <current>Per-(run, condition) boolean masks.</current>
      <proposed>No action. Cost is about a millisecond at realistic sizes; the function is the single source of onset-row order relied on by -stim_times_IM and check_im_order. beta_cond_order holds condition names (task_conn 329-337), not trials.</proposed>
      <literature>n/a</literature>
      <impact>Reviewed; no change.</impact>
    </finding>
    <finding id="F21" severity="minor" category="redundancy">
      <location file="task_act_first_level.py; task_conn_first_level.py; estimability.py; first_level_utils.py" lines="task_act ~533, ~814, ~1012; task_conn ~464, ~477, ~515; estimability ~547" />
      <description>Loop-invariant married/stim_flag and for_runs(s_pre) copies inside condition loops; HRF-string block repeated at seven sites.</description>
      <current>Recomputed per condition.</current>
      <proposed>/implement: add hrf_for_durations(hrf_model, custom_hrf, durations) next to build_hrf_string (duration models use durations.mean(), 1.0 if empty; else build_hrf_string(hrf_model, custom_hrf=custom_hrf)); hoist run_df = event_table.for_runs(s_pre).df and married/stim_flag above each of the five loops and call hrf_for_durations(..., run_df.loc[run_df["condition"] == cond, "duration"]); beta sites use beta_only["duration"]; remove HRF_DURATION_MODELS and build_hrf_string imports that become unused. /test: unit test for hrf_for_durations (GAM/BLOCK mean, empty -> 1.0, SPMG1/dmBLOCK/custom ignore durations).</proposed>
      <literature>n/a</literature>
      <impact>Byte-identical HRF strings and commands; one HRF code path.</impact>
    </finding>
    <finding id="F22" severity="minor" category="performance">
      <location file="first_level_utils.py; roi.py" lines="691-720; 233-236, 265, 303, 409-410" />
      <description>check_template runs eight 3dinfo calls to read three values; roi_qc runs the same 3dROIstats twice.</description>
      <current>Redundant AFNI calls.</current>
      <proposed>/implement: get_3dinfo_properties gains optional keys (default all); check_template uses keys=("space", "dmax") for the template and ("space",) for the scan; roi_qc uses one count_nonzero_by_roi(template, template) and tlabels = sorted(n_vox); delete roi.template_labels and its module-docstring mention (roi.py 10-11). (orient/spacing queries removed under F42 C.) /test: remove test_template_labels_returns_sorted_rois, the template_labels import and its header-comment mention in tests/test_roi.py. Implement and test together.</proposed>
      <literature>n/a</literature>
      <impact>8 -> 3 3dinfo calls per invocation; one fewer 3dROIstats per roi-qc.</impact>
    </finding>
    <finding id="F23" severity="minor" category="redundancy">
      <location file="fmri_first_level_proc/task_act_first_level.py" lines="792-855, 990-1048" />
      <description>GLM and smoothed-GLM stage bodies duplicate about 55 lines.</description>
      <current>Two near-identical bodies.</current>
      <proposed>/implement: closure _run_glm(io, token, stage_label, description, producer) returning (outputs, bucket_stats_rel); _glm_stage -> _run_glm(io, None, "task-act-glm", "3dDeconvolve GLM", "3dDeconvolve GLM"); _glm_smooth_stage -> _run_glm(io, token, "task-act-glm-smooth", "3dDeconvolve smoothed GLM", "smoothed GLM") then its stat-bucket extraction. StageSpecs unchanged. Note: unsmoothed extraction stays in task-act-extract (parcellations and resids); smoothed outputs stay voxelwise by design.</proposed>
      <literature>brainstorm_20261009_112745 smoothing decision (voxelwise-only smoothing; parcel outputs never smoothed).</literature>
      <impact>One GLM code path; identical outputs and REML_cmd names.</impact>
    </finding>
    <finding id="F24" severity="minor" category="redundancy">
      <location file="nuisance.py; task_act_first_level.py" lines="task_act ~649-656, GLM body" />
      <description>task_act -ortvec list built by identical loops (HRF parts absorbed by F21).</description>
      <current>Three copies (two after F23).</current>
      <proposed>/implement: add nuisance.task_ortvecs(state, out_dir) (CSF then WM; base then derivative when present; docstring: relies on task_nuisance derivatives, task_act only) and use it in the preflight step and _run_glm. task_conn keeps its own loop (its derivative is computed in-stage by design).</proposed>
      <literature>n/a</literature>
      <impact>Identical ordered list; one builder.</impact>
    </finding>
    <finding id="F25" severity="minor" category="redundancy">
      <location file="task_act/task_conn/rest_conn_first_level.py; roi.py; smoothing.py; prep.py" lines="see proposed" />
      <description>Stage bodies copied across pipelines.</description>
      <current>_template_stage x3, _smooth_stage x2 (52 lines), _roiqc_stage x2, _raw_ptseries_stage x2.</current>
      <proposed>/implement: (1) roi.template_stage(ctx, config, runsets, pre, same_grid, analysis, logger) -> template_resolved, building the {analysis}-template StageSpec with F42's SHA-256 derived_files and scan_grid; replaces task_act ~676-696, task_conn ~384-404, rest_conn ~440-461; (2) smoothing.task_smooth(io, config, runsets, s_pre, pre, token, logger) with mask_stats hoisted before the run loop; (3) roi.task_roi_qc(io, config, runsets, s_pre, template_resolved, pre, logger); (4) prep.task_raw_ptseries(io, config, runsets, template_resolved, logger); delete dataclasses_copy_without_psc and task_conn's inline copy; raw-ptseries upstream becomes the plain ("...-prep", "...-template") tuple. Other StageSpecs stay in pipeline modules.</proposed>
      <literature>n/a</literature>
      <impact>Identical commands, outputs, QC and hashes; F42 written once.</impact>
    </finding>
    <finding id="F26" severity="minor" category="correctness">
      <location file="smoothing.py; prep.py; roi.py" lines="smoothing ~43-71; prep ~221-260" />
      <description>Duplicate mask algorithm; both fail above 13 runs (26 3dcalc letters) after computing every run's max/min, with different exception types.</description>
      <current>Letter-limited 3dcalc product.</current>
      <proposed>/implement: roi.nonconstant_intersection(io, specs, rel, tag, logger): per-spec indicator via roi.nonconstant_mask; one spec -> 3dcalc -expr a to rel; two or more -> 3dMean -min -datum float -prefix rel; docstring notes indicators are exactly 0/1 so min equals intersection. Use in smoothing.smoothing_mask (tag "smooth") and prep's run-intersection mask (tag "mask", keeping per-run spec selection); delete both 13-run branches. /test: 2-4 runs voxel-identical to the current masks with float datum; a 14-run synthetic case builds both masks and equals the expected intersection.</proposed>
      <literature>AFNI 3dMean -help (-min); 3dcalc step()/ispositive() equivalence.</literature>
      <impact>Removes an arbitrary 13-run ceiling; one implementation.</impact>
    </finding>
    <finding id="F27" severity="minor" category="redundancy">
      <location file="nuisance.py; rest_conn_first_level.py; task_conn_first_level.py; first_level_utils.py" lines="nuisance ~531-548; rest_conn ~535-552, ~664-681; task_conn ~444-453" />
      <description>Tissue-derivative load/compute/format/write sequence repeated seven times.</description>
      <current>Seven copies.</current>
      <proposed>/implement: write_tissue_derivative(src_path, name, run_lengths, out_path) -> str next to compute_tissue_derivative; use at all seven sites (task_conn uses the returned text as expected_text); merge each rest-site CSF/WM loop and GS branch into one CSF, WM, GS loop keeping each site's GS-absent idiom and bookkeeping. task_nuisance's array-based derivative and task_conn's in-stage placement unchanged.</proposed>
      <literature>n/a</literature>
      <impact>Byte-identical files; regressor order preserved.</impact>
    </finding>
    <finding id="F28" severity="style" category="redundancy">
      <location file="engine.py; checkpoint.py" lines="engine ~507-508, ~796-806; checkpoint 284-294" />
      <description>engine._jsonable duplicates checkpoint._jsonable; checkpoint's tuple branch does not recurse.</description>
      <current>Double normalization.</current>
      <proposed>/implement: delete engine._jsonable and store raw getattr values in stage_hash; checkpoint._jsonable tuple branch returns [_jsonable(v) for v in obj]. /test: canonical_json case with a tuple containing a set -> sorted list.</proposed>
      <literature>n/a</literature>
      <impact>Hashes byte-identical for current field types; latent TypeError removed.</impact>
    </finding>
    <finding id="F29" severity="style" category="maintainability">
      <location file="pyproject.toml" lines="34-44" />
      <description>Eight level markers declared but unused locally; fmri-proc-orchestrator declares and applies the same set.</description>
      <current>Unused declarations.</current>
      <proposed>Keep pyproject unchanged. /test: apply the markers at class or function granularity (class decorators where a class is single-level, per-function where mixed), matching the orchestrator.</proposed>
      <literature>n/a</literature>
      <impact>Harmonized level-based test selection.</impact>
    </finding>
    <finding id="F30" severity="minor" category="dependencies">
      <location file="fmri_first_level_proc/tools.lock.yaml" lines="7-8" />
      <description>python.validated "3.14", but the v4.0.0 suite passed on 3.13.12; production (orchestrator and consumer) pins 3.14.</description>
      <current>Unverified validated value; UNVALIDATED_VERSION in the dev environment.</current>
      <proposed>Keep "3.14". /test (run_suite): run the full suite under a Python 3.14 interpreter with numpy 2.4.2, pandas 3.0.1 and AFNI 26.0.09 (environment creation needs per-invocation approval). RELEASE GATE: v4.0.0 is not published until that run passes. If the run is not performed, python.validated must be set to "3.13", and orchestrator/consumer runs on 3.14 will then emit UNVALIDATED_VERSION.</proposed>
      <literature>brainstorm_20261009_112745 lockfile decision ("validated" = version the suite passed on).</literature>
      <impact>Accurate provenance.</impact>
    </finding>
    <finding id="F31" severity="style" category="maintainability">
      <location file="project root; tests/" lines="n/a" />
      <description>Local clutter; all files git-ignored (none published). CHANGELOG.md whitelisted but absent.</description>
      <current>Dead repro script and outputs in tests/; AFNI side files, a log and build artifacts in root; unarchived skill reports; working notes.</current>
      <proposed>Every deletion only with per-invocation permission. (1) /test: delete tests/reproduce_issue.py (imports a removed function), tests/test_motion.txt, tests/test_subj_run1_notch_motion.1D, tests/test_subj_run1_notch_src_motion_prepared.txt. (2) Delete root 3dDeconvolve.err, Decon.REML_cmd (from an earlier ad-hoc command, not package code), excalidraw.log, build/, fmri_first_level_proc.egg-info/. (3) /end-session archives the six root skill reports. (4) Move, not delete, the inbound upstream report from the private consumer project, FIX_fromOrch.txt, HARMONIZE_fmri-first-level-proc_20260816_212459.md, TODO_fmri-first-level-proc_20260812_132545.md, upstream_polort_dof_issue.md, proc_config_final.yaml and proc_config_final_run.yaml to an archive location the user names outside the repo. (5) /document: create CHANGELOG.md for 4.0.0.</proposed>
      <literature>n/a</literature>
      <impact>Clean working tree; release notes for a breaking release.</impact>
    </finding>
    <finding id="F32" severity="style" category="maintainability">
      <location file="fmri_first_level_proc/task_conn_first_level.py" lines="~66, ~750, ~907" />
      <description>`import os as _os` inside two loop bodies.</description>
      <current>Function-local imports.</current>
      <proposed>/implement: top-level `import os` after `import logging`; delete both local imports; `_os.path.exists` -> `os.path.exists`.</proposed>
      <literature>n/a</literature>
      <impact>Conventional imports.</impact>
    </finding>
    <finding id="F33" severity="minor" category="redundancy">
      <location file="rest_conn_first_level.py; nuisance.py" lines="rest_conn 812, 847, 866; nuisance 512, 779-781" />
      <description>residual_stage_label assigned twice; rest smoothing calls mask_stats per run; polort formula written twice.</description>
      <current>Repeated computations.</current>
      <proposed>/implement: assign residual_stage_label once before "# Smoothing branch" (~809); hoist mask_stats above the rest smoothing run loop; add nuisance._polort(n_vols, tr, bandpass) used at both polort sites.</proposed>
      <literature>n/a</literature>
      <impact>Values unchanged; no formula drift.</impact>
    </finding>
    <finding id="F34" severity="critical" category="correctness">
      <location file="fmri_first_level_proc/task_act_first_level.py" lines="157-300 (extract_stat_bucket_niftis, write_stat_indexes, stat_bucket_parcellations)" />
      <description>Stat-bucket extraction parses `3dinfo -subbrick_info`: labels keep a leading apostrophe; multi-basis HRF sub-bricks collapse to one index key (last basis wins); Zstat always fails (apostrophe in the temp prefix rejected by 3dcalc); Fstat and R^2 match nothing and are skipped with a plain logger warning; untested.</description>
      <current>Broken selection and indexing.</current>
      <proposed>/implement: select sub-bricks from `3dinfo -label` by label suffix; full-label index keys (Tstat -> Zstat for Z); positional temp names; include Full_Fstat and Full_R^2; incorporate F19. /test: real-AFNI tests for every stat type, including the F41 assertion (each T sub-brick DOF is an integer equal to uncensored TRs minus design-matrix columns, and Zstat equals an independently computed fitt_t2z(t, DOF)).</proposed>
      <literature>AFNI 26.0.09 bucket labels probed empirically.</literature>
      <impact>Fixes wrong or missing stat outputs.</impact>
    </finding>
    <finding id="F35" severity="major" category="correctness">
      <location file="fmri_first_level_proc/task_conn_first_level.py" lines="LSS outputs" />
      <description>concat_LSS sub-bricks are labelled generically; no output maps a sub-brick to (condition, run, onset).</description>
      <current>Unrecoverable trial identity.</current>
      <proposed>/implement: lss_index on trial records (null for run-excluded trials); {pre}_concat_LSS_index.json and per-condition {pre}_concat_bseries_{cond}_index.json (written only when the bseries file is written), smoothed siblings, names helpers, expected-set entries. /test: index contents against the trial table.</proposed>
      <literature>n/a</literature>
      <impact>Trial-level outputs become interpretable downstream.</impact>
    </finding>
    <finding id="F36" severity="critical" category="maintainability">
      <location file="git history and PR refs" lines="n/a" />
      <description>Exhaustive participant-ID sweep (direct content reads of the working tree and every blob reachable from every ref, including PR #1 refs). One participant identifier and one absolute path exist in a historical blob reachable from main, tags and the PR refs.</description>
      <current>Identifier present in published history.</current>
      <proposed>Each step outside /clean with explicit per-invocation approval: (2) git filter-repo --replace-text in a fresh disposable clone (installing git-filter-repo needs approval), replacing the identifier with a placeholder and the absolute path with a relative one; re-add origin; force-push main and all tags. (3) GitHub Support request to purge refs/pull/1/* and cached views. (4) The PR author's fork can only be cleaned by its owner. (5) Never push the local refs/claude checkpoint ref; root working notes stay local. (6) Rewritten commits and tags get new SHAs; SHA pins break, tag-name pins survive after re-push.</proposed>
      <literature>n/a</literature>
      <impact>Removes PII from the public repository to the extent GitHub allows.</impact>
    </finding>
    <finding id="F37" severity="minor" category="maintainability">
      <location file="INPUT_SPECIFICATION.md; rest_conn_first_level.py" lines="293, 295, 535; _residual_sequenced" />
      <description>Retention of per-run residuals and sequenced intermediates described with v3 behavior.</description>
      <current>"delete after concatenation"; "{out_dir}/_sequenced_intermediates/run{N}/"; "removed after each run unless ... or on failure"; "preserved on failure regardless of flag".</current>
      <proposed>/document (with U5): keep_run_res_dtseries selects the residual mode (true: per-run rest-conn-residuals-run{N} stages plus rest-conn-concat, per-run residuals final; false: single rest-conn-residuals-concat stage, per-run residuals never written); sequenced intermediates are written under {out_dir}/{out_file_pre}_sequenced_intermediates/run{N}/ only in per-run mode and always ledgered as intermediate; concat mode keeps them in staging; a failed stage promotes nothing. /implement: same change as F5 item (5).</proposed>
      <literature>brainstorm_20261009_112745 output classification (~line 590).</literature>
      <impact>Accurate user documentation.</impact>
    </finding>
    <finding id="F38" severity="minor" category="maintainability">
      <location file="README.md; INPUT_SPECIFICATION.md" lines="47; 612" />
      <description>Removed run-first-level alias still documented; A2's contract test missing.</description>
      <current>Docs describe a nonexistent command and warning.</current>
      <proposed>/document: README.md:47 delete the alias sentence (keep "The primary CLI entry point is fmri-first-level-proc."); INPUT_SPECIFICATION.md:612 delete the alias sentence; CHANGELOG records the removal as breaking. /test: [project.scripts] has exactly fmri-first-level-proc = fmri_first_level_proc.run_first_level:main, and neither CLI_DEPRECATED nor run-first-level appears in package source, README.md, INPUT_SPECIFICATION.md or example_config.yaml.</proposed>
      <literature>brainstorm_20261009_112745 topic A2.</literature>
      <impact>Docs match the CLI.</impact>
    </finding>
    <finding id="F39" severity="major" category="maintainability">
      <location file="README.md; INPUT_SPECIFICATION.md" lines="README 15, 16, 76, 125; INPUT_SPEC 77, 412-424, 579-582, 625" />
      <description>v3 ledger, lockfile and remove_previous semantics documented; stage reuse undocumented.</description>
      <current>"config-hash invalidation and cascade rerun"; optional/absence-tolerant exact-match lockfile with LOCKFILE_ABSENT and lockfile_version 1.0.0; remove_previous deletes all files.</current>
      <proposed>/document (with U5, after F42/F42a are implemented): correct README 15 (packaged lockfile; minimum -> ToolVersionError; validated -> UNVALIDATED_VERSION; AFNI, Python, numpy, pandas), README 16 (per-stage hashes; five rerun triggers; QC and warnings replayed on reuse), README 76 and 125, INPUT_SPEC 412-424 and 625 (packaged, lockfile_version 2.0.0, minimum/validated), INPUT_SPEC 579-582 (AFNI minimum floor plus validated warning), INPUT_SPEC 77 (remove_previous removes only this analysis's ledger-recorded outputs). Add a "Stage reuse and reruns" section: five triggers; content-hashed inputs (motion via censor and motion files, events via onset files, template file and scan grid, CSF/WM/GS tissue files); scan content path-only; any package/AFNI/Python/numpy/pandas version change reruns every stage; qc_summary.json lists reused_stages.</proposed>
      <literature>brainstorm_20261009_112745 stage-hashing decision (5) (revised by F42a) and lockfile decision.</literature>
      <impact>Users can predict reruns and version behavior.</impact>
    </finding>
    <finding id="F40" severity="style" category="maintainability">
      <location file="fmri_first_level_proc/nuisance.py" lines="726" />
      <description>f-string without placeholders.</description>
      <current>producer=f"Power FD censor"</current>
      <proposed>/implement: producer="Power FD censor".</proposed>
      <literature>n/a</literature>
      <impact>Cosmetic.</impact>
    </finding>
    <finding id="F41" severity="minor" category="numerical_stability">
      <location file="fmri_first_level_proc/task_act_first_level.py" lines="267" />
      <description>int(aux_params[0]) on the BRICK_STATAUX DOF before fitt_t2z. Confirmed lossless: both GLM buckets come from 3dDeconvolve's OLS fit (3dREMLfit is never executed; no -GOFORIT), so t DOF = uncensored TRs - rank(X); five synthetic AFNI 26.0.09 runs with the package's base flags (1-3 runs, GAM/BLOCK/SPMG1/married dmBLOCK, GLTs, 8-40% censoring) gave integer DOF equal to uncensored TRs minus design-matrix columns in every T sub-brick. IM timing never feeds this function.</description>
      <current>int() applied to an integer-valued float.</current>
      <proposed>No code change. /test: the assertion recorded under F34.</proposed>
      <literature>AFNI 26.0.09 empirical check (session scratchpad script f41_dof_check/run_check.py).</literature>
      <impact>Confirmed no defect; invariant guarded by test.</impact>
    </finding>
    <finding id="F42" severity="major" category="correctness">
      <location file="task_act/task_conn/rest_conn_first_level.py; first_level_utils.py" lines="template StageSpecs (task_act ~679, task_conn ~386, rest_conn ~444); task-act-glm ~780; task-act-glm-smooth ~982; task-conn-design-matrix ~418; get_3dinfo_properties" />
      <description>Stage hashes omit content the locked design requires (template SHA-256 and scan grid; motion bytes for task analyses), so in-place edits of template, motion or events files reuse stale outputs.</description>
      <current>Template stage hashes template_path and same_grid only; task model stages declare no derived_files.</current>
      <proposed>/implement: (A) template StageSpecs add derived_files=(config.template_path,) and derived_values["scan_grid"] = stripped stdout of `3dinfo -n3 -aform_real <runsets.grid_ref>` (per-axis dims and full affine; not -nijk, which is a product, and not -n4, which adds the volume count); (B) derived_files for out_dir files passed to 3dDeconvolve: task-act-glm and task-act-glm-smooth: names.censor(pre, None), nuisance_state["motion_rel"], names.onset_file(pre, cond) for config.cond_labels; task-conn-design-matrix: censor, prepared motion, non-beta onset files, names.beta_onsets(pre). Events-file edits now rerun model stages. (C) remove the orient and spacing queries from get_3dinfo_properties. /test: test_error_paths expected key set -> {space, dmax}; (D) ledger tests: same-grid template edit -> template stage and all consumers rerun; mismatched grid with changed scan geometry -> template stage reruns; motion edit -> model stages rerun; events edit -> model stages rerun; unchanged inputs -> all stages reused.</proposed>
      <literature>brainstorm_20261009_112745 T11-b(2), T11-b(5), stage-hashing decision (5); AFNI 3dinfo -help (-nijk, -n3, -n4, -aform_real).</literature>
      <impact>Prevents silently stale results after in-place input edits.</impact>
    </finding>
    <finding id="F42a" severity="major" category="correctness">
      <location file="task_act/task_conn/rest_conn_first_level.py" lines="task-act-glm, task-act-glm-smooth, task-conn-design-matrix, rest-conn-residuals-run{N}, rest-conn-residuals-concat StageSpecs" />
      <description>No stage hashes tissue regressor content in any analysis; the design is internally inconsistent on this. Decision (5) is revised for tissue files.</description>
      <current>Tissue paths hashed as strings only.</current>
      <proposed>/implement: task-act-glm and task-act-glm-smooth (one shared list with F42's files, passed explicitly to the smoothed spec, which does not inherit derived_files): names.tissue_prepared(pre, t) for each present CSF/WM and names.tissue_deriv(pre, t, None) when use_tissue_derivs; task-conn-design-matrix: names.tissue_prepared(pre, t) for each present CSF/WM; rest_conn residual-run and residuals-concat: the per-run config.CSF_paths, WM_paths and (when present) GS_paths entries for the runs regressed. Scan content stays path-only. /test: in-place CSF/WM/GS edits rerun the model stage in each analysis type, with and without use_tissue_derivs; unchanged files are reused.</proposed>
      <literature>brainstorm_20261009_112745 stage declaration (~line 457) and decision (5) (~line 431), revised here.</literature>
      <impact>Corrected regressors always take effect.</impact>
    </finding>
  </findings>
  <summary>
    <critical_count>2</critical_count>
    <major_count>6</major_count>
    <total_findings>43</total_findings>
    <overall_assessment>needs_major_refactor</overall_assessment>
  </summary>
  <action_items>
    <item priority="P0" target_mode="implement" finding_ref="F34" description="Rewrite stat-bucket selection on 3dinfo -label suffix matching with full-label keys, positional temp names, Full_Fstat/Full_R^2; include F19's single-call _get_stataux" />
    <item priority="P0" target_mode="test" finding_ref="F34" description="Real-AFNI tests for every stat type, including the F41 DOF/Zstat assertion" />
    <item priority="P0" target_mode="implement" finding_ref="F42" description="Template SHA-256 and 3dinfo -n3 -aform_real scan_grid in template stages; censor/motion/onset derived_files in task model stages; drop orient/spacing 3dinfo queries" />
    <item priority="P0" target_mode="implement" finding_ref="F42a" description="Hash tissue regressor files in task and rest model stages (shared list for task-act-glm and task-act-glm-smooth)" />
    <item priority="P0" target_mode="test" finding_ref="F42" description="Ledger rerun tests for template, scan grid, motion, events and unchanged inputs; test_error_paths key set {space, dmax}" />
    <item priority="P0" target_mode="test" finding_ref="F42a" description="Tissue in-place edit rerun tests per analysis type, with and without use_tissue_derivs" />
    <item priority="P0" target_mode="implement" finding_ref="F36" description="History rewrite and PR-ref purge plan (steps 2-6), each step with explicit per-invocation approval" />
    <item priority="P1" target_mode="implement" finding_ref="F2" description="enumerate-based -glt_label numbering; ConfigError on duplicate or sanitize-colliding contrast labels" />
    <item priority="P1" target_mode="test" finding_ref="F2" description="Duplicate/colliding contrast labels raise ConfigError; -glt_label indices 1..K" />
    <item priority="P1" target_mode="document" finding_ref="F2" description="Document sub-brick identifiers for every post-regression output" />
    <item priority="P1" target_mode="implement" finding_ref="F35" description="LSS index JSONs and lss_index on trial records" />
    <item priority="P1" target_mode="test" finding_ref="F35" description="LSS index contents against the trial table" />
    <item priority="P1" target_mode="document" finding_ref="F1" description="Redact the private consumer project name in the 2026-08-25 .aid brainstorm report" />
    <item priority="P1" target_mode="test" finding_ref="F30" description="Full suite under Python 3.14 (numpy 2.4.2, pandas 3.0.1, AFNI 26.0.09); release gate; else set validated to 3.13" />
    <item priority="P1" target_mode="document" finding_ref="F39" description="Correct README/INPUT_SPEC ledger, lockfile and remove_previous text; add stage reuse and reruns section (after F42/F42a)" />
    <item priority="P1" target_mode="implement" finding_ref="F26" description="roi.nonconstant_intersection with 3dMean -min; remove 13-run limits" />
    <item priority="P1" target_mode="test" finding_ref="F26" description="Mask equivalence for 2-4 runs and a 14-run case" />
    <item priority="P1" target_mode="test" finding_ref="F10" description="Stage-field coverage tests and allowed_keys documentation test" />
    <item priority="P1" target_mode="test" finding_ref="F18" description="Known-answer partial-correlation test" />
    <item priority="P2" target_mode="implement" finding_ref="F3" description="Reword session markers; rename _t1_checks to _run_consistency_checks" />
    <item priority="P2" target_mode="implement" finding_ref="F4" description="prep.py imports" />
    <item priority="P2" target_mode="implement" finding_ref="F5" description="rest_conn wording; remove _residual_sequenced intermediate_cls (shared with F37)" />
    <item priority="P2" target_mode="implement" finding_ref="F6" description="valid_contrast_functions messages" />
    <item priority="P2" target_mode="implement" finding_ref="F7" description="first_level_config line-287 comment" />
    <item priority="P2" target_mode="implement" finding_ref="F8" description="Sequenced-backend citations in code and example_config" />
    <item priority="P2" target_mode="document" finding_ref="F8" description="Citations in README, INPUT_SPEC, AID_LOG and .aid test report PMID" />
    <item priority="P2" target_mode="implement" finding_ref="F9" description="Delete argparse helpers" />
    <item priority="P2" target_mode="test" finding_ref="F9" description="Remove TestArgparseValidators and imports; docstring" />
    <item priority="P2" target_mode="implement" finding_ref="F10" description="Delete BOOL_KEYS, latest_staged, run_tag, bids logger" />
    <item priority="P2" target_mode="test" finding_ref="F10" description="Test edits in test_sequenced_config, test_checkpoint, test_names" />
    <item priority="P2" target_mode="implement" finding_ref="F11" description="14 dead parameter/local/conditional edits" />
    <item priority="P2" target_mode="implement" finding_ref="F12" description="Remove 38 unused imports" />
    <item priority="P2" target_mode="implement" finding_ref="F13" description="Remove hard-coded version lines" />
    <item priority="P2" target_mode="implement" finding_ref="F14" description="engine module docstring paragraph" />
    <item priority="P2" target_mode="implement" finding_ref="F15" description="SCHEMA_VERSION constant" />
    <item priority="P2" target_mode="implement" finding_ref="F16" description="nuisance FD paragraph and _enorm docstring" />
    <item priority="P2" target_mode="implement" finding_ref="F17" description="roi and rest_conn comment condensation" />
    <item priority="P2" target_mode="implement" finding_ref="F18" description="Vectorize parcellated" />
    <item priority="P2" target_mode="implement" finding_ref="F21" description="hrf_for_durations and loop hoisting" />
    <item priority="P2" target_mode="test" finding_ref="F21" description="hrf_for_durations unit test" />
    <item priority="P2" target_mode="implement" finding_ref="F22" description="3dinfo keys argument; single roi_qc 3dROIstats; delete template_labels" />
    <item priority="P2" target_mode="test" finding_ref="F22" description="Remove template_labels test and import" />
    <item priority="P2" target_mode="implement" finding_ref="F23" description="_run_glm closure" />
    <item priority="P2" target_mode="implement" finding_ref="F24" description="nuisance.task_ortvecs" />
    <item priority="P2" target_mode="implement" finding_ref="F25" description="Shared template, task smoothing, task roi-qc and raw-ptseries functions" />
    <item priority="P2" target_mode="implement" finding_ref="F27" description="write_tissue_derivative helper" />
    <item priority="P2" target_mode="implement" finding_ref="F28" description="Remove engine._jsonable; recursive tuple branch" />
    <item priority="P2" target_mode="test" finding_ref="F28" description="canonical_json tuple-with-set case" />
    <item priority="P2" target_mode="test" finding_ref="F29" description="Apply level markers at class/function granularity" />
    <item priority="P2" target_mode="test" finding_ref="F31" description="Delete tests/reproduce_issue.py and its three output files (per-invocation permission)" />
    <item priority="P2" target_mode="implement" finding_ref="F31" description="Delete root AFNI side files, log, build/ and egg-info (per-invocation permission); move working notes to a user-named archive" />
    <item priority="P2" target_mode="document" finding_ref="F31" description="Create CHANGELOG.md for 4.0.0" />
    <item priority="P2" target_mode="implement" finding_ref="F32" description="Top-level os import in task_conn" />
    <item priority="P2" target_mode="implement" finding_ref="F33" description="Single residual_stage_label; hoist rest mask_stats; nuisance._polort" />
    <item priority="P2" target_mode="document" finding_ref="F37" description="Correct residual-mode and sequenced-intermediate retention text" />
    <item priority="P2" target_mode="document" finding_ref="F38" description="Remove legacy alias sentences; CHANGELOG entry" />
    <item priority="P2" target_mode="test" finding_ref="F38" description="Console-script and no-alias contract test" />
    <item priority="P2" target_mode="implement" finding_ref="F40" description="Plain string producer in nuisance.py:726" />
  </action_items>
</clean_report>
