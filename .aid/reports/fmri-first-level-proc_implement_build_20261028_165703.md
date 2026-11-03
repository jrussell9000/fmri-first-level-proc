<implement_report>
  <meta project="fmri-first-level-proc" mode="implement" submodule="build" timestamp="2026-10-28T20:57:03Z" />
  <spec_ref>fmri-first-level-proc_implement_plan_20261028_150008.md</spec_ref>
  <changes_applied>
    <change id="C1" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_config.py" lines_changed="2" />
        <file path="fmri_first_level_proc/engine.py" lines_changed="2" />
        <file path="fmri_first_level_proc/names.py" lines_changed="1" />
        <file path="fmri_first_level_proc/runsets.py" lines_changed="3" />
      </files_modified>
      <notes>Removed six design-session code markers (comments, docstrings and one private function rename) with no behavior change.</notes>
    </change>
    <change id="C2" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/prep.py" lines_changed="3" />
      </files_modified>
      <notes>Moved the os import to the top-level block and removed the unused logging import.</notes>
    </change>
    <change id="C3" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/rest_conn_first_level.py" lines_changed="12" />
      </files_modified>
      <notes>Corrected the banner and two inline comments to describe per-run regression with 3dTcat concatenation. Removed the always-constant intermediate_cls parameter from _residual_sequenced (both call sites already passed "intermediate").</notes>
    </change>
    <change id="C4" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_utils.py" lines_changed="8" />
      </files_modified>
      <notes>Replaced two argparse-flag-styled error messages in valid_contrast_functions with messages that match the YAML config vocabulary.</notes>
    </change>
    <change id="C5" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_config.py" lines_changed="1" />
      </files_modified>
      <notes>Replaced the version-tagged section comment with a description of the fields it covers.</notes>
    </change>
    <change id="C6" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/rest_conn_first_level.py" lines_changed="7" />
        <file path="example_config.yaml" lines_changed="1" />
      </files_modified>
      <notes>Replaced the "Ciric-inspired" label with explicit citations (Power et al. 2014; Hallquist et al. 2013) and a one-sentence description of the sequenced backend's actual steps, in both the function docstring and the example config comment.</notes>
    </change>
    <change id="C7" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/bids.py" lines_changed="2" />
        <file path="fmri_first_level_proc/checkpoint.py" lines_changed="2" />
        <file path="fmri_first_level_proc/connectivity.py" lines_changed="2" />
        <file path="fmri_first_level_proc/engine.py" lines_changed="2" />
        <file path="fmri_first_level_proc/estimability.py" lines_changed="2" />
        <file path="fmri_first_level_proc/events.py" lines_changed="2" />
        <file path="fmri_first_level_proc/first_level_config.py" lines_changed="6" />
        <file path="fmri_first_level_proc/nuisance.py" lines_changed="2" />
        <file path="fmri_first_level_proc/prep.py" lines_changed="2" />
        <file path="fmri_first_level_proc/qc.py" lines_changed="2" />
        <file path="fmri_first_level_proc/roi.py" lines_changed="2" />
        <file path="fmri_first_level_proc/runsets.py" lines_changed="2" />
        <file path="fmri_first_level_proc/runtime.py" lines_changed="2" />
        <file path="fmri_first_level_proc/smoothing.py" lines_changed="2" />
        <file path="fmri_first_level_proc/first_level_utils.py" lines_changed="2" />
        <file path="fmri_first_level_proc/task_act_first_level.py" lines_changed="2" />
        <file path="fmri_first_level_proc/task_conn_first_level.py" lines_changed="2" />
        <file path="fmri_first_level_proc/rest_conn_first_level.py" lines_changed="2" />
        <file path="fmri_first_level_proc/run_first_level.py" lines_changed="2" />
      </files_modified>
      <notes>Removed the hard-coded "Version 4.0.0." docstring line (and its blank line) or "# Version: 4.0.0" banner line from all 19 modules. __version__, pyproject version and the legacy-key error text were left untouched.</notes>
    </change>
    <change id="C8" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/engine.py" lines_changed="20" />
      </files_modified>
      <notes>Condensed the module docstring's rerun-trigger enumeration into one descriptive paragraph; all inline comments in the module body were left unchanged.</notes>
    </change>
    <change id="C9" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_config.py" lines_changed="9" />
      </files_modified>
      <notes>Added module constant SCHEMA_VERSION; resolve_config now builds ResolvedConfig with schema_version=SCHEMA_VERSION instead of a repeated literal. Docstring and field comment updated to reference the constant.</notes>
    </change>
    <change id="C10" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/nuisance.py" lines_changed="14" />
      </files_modified>
      <notes>Condensed the module-docstring censoring paragraph and moved the enorm definition into _enorm's own docstring.</notes>
    </change>
    <change id="C11" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/roi.py" lines_changed="5" />
        <file path="fmri_first_level_proc/rest_conn_first_level.py" lines_changed="4" />
      </files_modified>
      <notes>Condensed the _parse_roistats 3dROIstats-output-structure comment and the rest_conn transpose-quote comment to one-sentence descriptions each.</notes>
    </change>
    <change id="C12" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/nuisance.py" lines_changed="1" />
      </files_modified>
      <notes>Removed an f-string prefix on a literal with no placeholders.</notes>
    </change>
    <change id="C13" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_utils.py" lines_changed="58" />
      </files_modified>
      <notes>Deleted six unused argparse-type helper functions (dir_path_exists, file_path_exists, valid_string_list, valid_stat_type, valid_ave_type, valid_conn_type), the argparse import, and the corresponding module-docstring bullet. tests/test_utils_unit.py still imports these names; routed to /test per the plan's post-build routing.</notes>
    </change>
    <change id="C14" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_config.py" lines_changed="8" />
        <file path="fmri_first_level_proc/checkpoint.py" lines_changed="8" />
        <file path="fmri_first_level_proc/names.py" lines_changed="9" />
        <file path="fmri_first_level_proc/bids.py" lines_changed="4" />
      </files_modified>
      <notes>Deleted BOOL_KEYS, checkpoint.latest_staged, names.run_tag and bids.py's module-level logger (plus its now-unused logging import). EXEMPT_FIELDS, allowed_keys and runtime.reset_runtime_cache were confirmed still used and left in place.</notes>
    </change>
    <change id="C15" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_act_first_level.py" lines_changed="12" />
        <file path="fmri_first_level_proc/nuisance.py" lines_changed="4" />
        <file path="fmri_first_level_proc/engine.py" lines_changed="6" />
        <file path="fmri_first_level_proc/events.py" lines_changed="2" />
        <file path="fmri_first_level_proc/first_level_config.py" lines_changed="2" />
        <file path="fmri_first_level_proc/rest_conn_first_level.py" lines_changed="1" />
        <file path="fmri_first_level_proc/runsets.py" lines_changed="5" />
        <file path="fmri_first_level_proc/task_conn_first_level.py" lines_changed="2" />
        <file path="fmri_first_level_proc/first_level_utils.py" lines_changed="6" />
        <file path="fmri_first_level_proc/prep.py" lines_changed="6" />
      </files_modified>
      <notes>Removed 14 dead parameters, locals and an always-true conditional branch across 10 files, each confirmed unused by direct inspection before removal (task_act_expected's contrast_labels parameter; nuisance._enorm's motion6 parameter; engine._promote's unused return list; events.run_violations_count; first_level_config's unused template_path local; three unused-unpacking renames to "_"; task_act's unused k_sup local; task_conn's unused onset_specs pre-assignment; three raw-ptseries StageSpecs' dead conditional upstream tuples; first_level_utils's dead post-regex coefficient-float loop; prep.py's redundant Mode A/B branch collapsed to ri.spec).</notes>
    </change>
    <change id="C16" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_utils.py" lines_changed="7" />
        <file path="fmri_first_level_proc/task_act_first_level.py" lines_changed="30" />
        <file path="fmri_first_level_proc/task_conn_first_level.py" lines_changed="25" />
        <file path="fmri_first_level_proc/estimability.py" lines_changed="15" />
      </files_modified>
      <notes>Added hrf_for_durations to first_level_utils.py and used it at all five per-condition HRF-building loops (task_act estimability/GLM/smoothed-GLM, task_conn design-matrix and two beta-HRF sites, estimability.task_act_preflight_dof), hoisting married/stim_flag/run_df out of each loop. Verified byte-identical output for GAM, BLOCK, dmBLOCK, SPMG1 and custom HRF models against the prior inline logic.</notes>
    </change>
    <change id="C17" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_utils.py" lines_changed="8" />
        <file path="fmri_first_level_proc/nuisance.py" lines_changed="10" />
        <file path="fmri_first_level_proc/rest_conn_first_level.py" lines_changed="20" />
        <file path="fmri_first_level_proc/task_conn_first_level.py" lines_changed="9" />
      </files_modified>
      <notes>Added write_tissue_derivative to first_level_utils.py and replaced the seven duplicated file-read/derivative/write blocks across nuisance.py, rest_conn_first_level.py (two sites) and task_conn_first_level.py, merging each site's separate CSF/WM loop and GS branch into one loop over CSF, WM, GS. task_nuisance's array-based (already-in-memory) derivative was left unchanged per the plan. Verified byte-identical output against the manual computation path.</notes>
    </change>
    <change id="C18" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/engine.py" lines_changed="6" />
        <file path="fmri_first_level_proc/checkpoint.py" lines_changed="2" />
      </files_modified>
      <notes>Deleted engine._jsonable (stage_hash now stores raw field values directly); fixed checkpoint._jsonable's tuple branch to recurse into tuple elements rather than only converting the outer tuple to a list. Verified canonical_json now correctly normalizes nested tuples/sets/dicts in a single pass.</notes>
    </change>
    <change id="C19" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/rest_conn_first_level.py" lines_changed="10" />
        <file path="fmri_first_level_proc/nuisance.py" lines_changed="9" />
      </files_modified>
      <notes>Hoisted residual_stage_label to a single assignment used by both the smoothing branch and the ptseries/connectivity stages; hoisted the per-run-loop-invariant smoothing.mask_stats call out of the per-run loop in _smooth_stage (now smoothing.task_smooth, see C25). Added nuisance._polort and used it at both of its duplicated computation sites.</notes>
    </change>
    <change id="C20" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/roi.py" lines_changed="20" />
        <file path="fmri_first_level_proc/smoothing.py" lines_changed="35" />
        <file path="fmri_first_level_proc/prep.py" lines_changed="30" />
      </files_modified>
      <notes>Added roi.nonconstant_intersection (per-run non-constant indicator via the existing nonconstant_mask, then a single 3dcalc for one run or 3dMean -min across indicators for multiple runs, removing the 26-letter/13-run 3dcalc limit) and used it in smoothing.smoothing_mask and prep.py's run-intersection mask block, removing both ToolExecutionError/InputError "not implemented" branches. Verified voxel-identical output against the prior lettered-3dcalc approach with real AFNI (3dTstat/3dcalc/3dMean) on a synthetic 3-run dataset, including the single-run case.</notes>
    </change>
    <change id="C21" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/connectivity.py" lines_changed="20" />
      </files_modified>
      <notes>Vectorized parcellated()'s null/non-null ROI identification, partial-correlation computation and NaN-matrix expansion with numpy operations (np.ptp/np.outer/np.ix_), replacing three Python-level loops. Bitwise-identical by construction.</notes>
    </change>
    <change id="C22" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_utils.py" lines_changed="10" />
        <file path="fmri_first_level_proc/roi.py" lines_changed="16" />
      </files_modified>
      <notes>get_3dinfo_properties now takes an optional keys filter and its query table is reduced to the two keys actually consumed (space, dmax); both check_template call sites pass explicit keys. roi_qc's duplicate count_nonzero_by_roi(template, template) call was collapsed into one call, with tlabels now derived from its result. Deleted roi.template_labels (confirmed unused elsewhere in the package after this change) and its module-docstring mention.</notes>
    </change>
    <change id="C23" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/nuisance.py" lines_changed="12" />
        <file path="fmri_first_level_proc/task_act_first_level.py" lines_changed="8" />
      </files_modified>
      <notes>Added nuisance.task_ortvecs and used it to replace task_act's preflight-step inline ortvec-building loop. The two GLM-stage sites with the same inline loop are consolidated by C24's _run_glm closure, which calls task_ortvecs directly.</notes>
    </change>
    <change id="C24" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_act_first_level.py" lines_changed="110" />
      </files_modified>
      <notes>Added a _run_glm(io, token, stage_label, description, producer) closure inside run() covering model-input resolution, ortvec building (via task_ortvecs), the full 3dDeconvolve command construction (hoisted HRF/married/stim_flag per C16), gltsym arguments, REML_cmd collection and bucket-stats-index generation. _glm_stage and _glm_smooth_stage now call this closure; the smoothed stage's stat-bucket extraction and per-stat index writing (unique to that stage) remain after the call. Verified both stages still produce the same output relpaths and command structure.</notes>
    </change>
    <change id="C25" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/roi.py" lines_changed="75" />
        <file path="fmri_first_level_proc/smoothing.py" lines_changed="60" />
        <file path="fmri_first_level_proc/prep.py" lines_changed="45" />
        <file path="fmri_first_level_proc/task_act_first_level.py" lines_changed="40" />
        <file path="fmri_first_level_proc/task_conn_first_level.py" lines_changed="40" />
        <file path="fmri_first_level_proc/rest_conn_first_level.py" lines_changed="6" />
      </files_modified>
      <notes>Four shared-body extractions: (1) roi.template_stage (also carries C31's derived_files/scan_grid hashing) replaces the three byte-identical template-check-and-resample stage bodies in task_act, task_conn and rest_conn. (2) smoothing.task_smooth replaces the byte-identical task_act/task_conn smoothing stage bodies. (3) roi.task_roi_qc replaces the byte-identical task_act/task_conn ROI-QC stage bodies. (4) prep.task_raw_ptseries replaces the byte-identical task_act/task_conn raw-ptseries stage bodies, and task_act's now-dead module-level dataclasses_copy_without_psc helper was deleted (task_conn's equivalent inline copy was already being replaced in the same edit). rest_conn's own smoothing/roi-qc/raw-ptseries bodies were left untouched, per the plan. Stage labels and all StageSpec contents (other than C31's additions) are unchanged.</notes>
    </change>
    <change id="C26" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_conn_first_level.py" lines_changed="7" />
      </files_modified>
      <notes>Added a top-level os import and replaced both function-local "import os as _os" statements with the top-level import.</notes>
    </change>
    <change id="C27" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_act_first_level.py" lines_changed="4" />
        <file path="fmri_first_level_proc/first_level_config.py" lines_changed="28" />
      </files_modified>
      <notes>gltsym_args now numbers -glt_label sequentially by loop position instead of looking up the first index of a (possibly repeated) label in the full label list. Added _check_contrast_label_integrity, called from _validate_contrasts for both task_act contrasts.labels and task_conn connectivity.contrasts.labels, raising ConfigError on duplicate labels or on two distinct labels colliding after sanitize_filename_label. Confirmed none of the three consumer proc templates trigger either new check.</notes>
    </change>
    <change id="C28" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_act_first_level.py" lines_changed="95" />
      </files_modified>
      <notes>Replaced _get_subbrik_stat_aux (one 3dAttribute call per sub-brick) with _get_stataux (one call for the whole bucket, returning a dict keyed by sub-brick index). Rewrote extract_stat_bucket_niftis to select sub-bricks by their exact 3dinfo -label label (ends-with-suffix matching) instead of parsing 3dinfo -subbrick_info tokens by position, fixing the index-grammar defects the clean and CR reports identified. A Zstat bucket's key is the matching Tstat label with "Zstat" substituted for "Tstat". Verified against a real 3dDeconvolve run (two conditions plus a GLT contrast, Coef/Tstat/Fstat/R^2/Zstat all requested): every sub-brick, including Full_Fstat and Full_R^2, was correctly selected and keyed, and the Z-converted values matched a hand-computed fitt_t2z reference using the DOF our own _get_stataux retrieved, to floating-point precision.</notes>
    </change>
    <change id="C29" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/names.py" lines_changed="7" />
        <file path="fmri_first_level_proc/estimability.py" lines_changed="20" />
        <file path="fmri_first_level_proc/task_conn_first_level.py" lines_changed="70" />
      </files_modified>
      <notes>Added names.lss_index and names.bseries_index. build_trials now adds an lss_index field for task_conn records only (the trial's position in column_order, or null for a run-excluded trial); task_act's build_trials output is unchanged. Both the beta-series and beta-series-smooth stages now write a {pre}_concat_LSS_index.json (one record per 3dLSS sub-brick) and a per-condition {pre}_concat_bseries_{cond}_index.json (one record per surviving trial, ordered by beta_series_position) as final JSON outputs. task_conn_expected enumerates both new files. Verified the lss_index/beta_series_position assignment against a synthetic trial set (survived/excluded/multiple-condition cases) and confirmed task_act's output has no lss_index key.</notes>
    </change>
    <change id="C30" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_act_first_level.py" lines_changed="12" />
        <file path="fmri_first_level_proc/task_conn_first_level.py" lines_changed="10" />
        <file path="fmri_first_level_proc/rest_conn_first_level.py" lines_changed="12" />
      </files_modified>
      <notes>task-act-glm and task-act-glm-smooth's StageSpecs now hash the censor file, prepared motion file, every onset file and every tissue/tissue-derivative regressor file the GLM command references. task-conn-design-matrix hashes the same set (non-beta onset files, beta onsets, tissue files). rest-conn-residuals-run{N} and rest-conn-residuals-concat now additionally hash each run's CSF/WM/GS source files by content, not only by path (closing the gap where editing a tissue regressor's contents without changing its path or config would silently reuse a stale stage).</notes>
    </change>
    <change id="C31" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/roi.py" lines_changed="0" />
      </files_modified>
      <notes>Folded into C25's roi.template_stage: it hashes config.template_path by content (derived_files) and includes a scan_grid value (3dinfo -n3 -aform_real on the run grid reference) in derived_values, alongside the existing same_grid flag.</notes>
    </change>
    <change id="C32" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/connectivity.py" lines_changed="5" />
        <file path="fmri_first_level_proc/estimability.py" lines_changed="8" />
        <file path="fmri_first_level_proc/events.py" lines_changed="4" />
        <file path="fmri_first_level_proc/first_level_config.py" lines_changed="1" />
        <file path="fmri_first_level_proc/first_level_utils.py" lines_changed="2" />
        <file path="fmri_first_level_proc/nuisance.py" lines_changed="1" />
        <file path="fmri_first_level_proc/rest_conn_first_level.py" lines_changed="9" />
        <file path="fmri_first_level_proc/roi.py" lines_changed="2" />
        <file path="fmri_first_level_proc/runsets.py" lines_changed="2" />
        <file path="fmri_first_level_proc/smoothing.py" lines_changed="2" />
        <file path="fmri_first_level_proc/task_act_first_level.py" lines_changed="12" />
        <file path="fmri_first_level_proc/task_conn_first_level.py" lines_changed="16" />
      </files_modified>
      <notes>Ran a read-only AST-based unused-import scan after C1-C31 and removed every name it reported (41 names across 12 files: the clean report's original 38 plus build_hrf_string/HRF_DURATION_MODELS/load_numeric_table/format_table/compute_tissue_derivative, made unused by C16/C17/C25), each confirmed by a targeted grep that the only remaining mentions were inside docstrings. Re-ran the scanner afterward: the only two remaining hits are the __init__.py run_* re-exports and first_level_config's "from __future__ import annotations", both explicitly exempted by the plan. Ran the companion re-export checker against every removed name across the whole package: no external references found.</notes>
    </change>
    <change id="C33" status="done" user_decision="proceed">
      <files_modified>
        <file path="3dDeconvolve.err" lines_changed="deleted" />
        <file path="Decon.REML_cmd" lines_changed="deleted" />
        <file path="excalidraw.log" lines_changed="deleted" />
        <file path="build/" lines_changed="deleted" />
        <file path="fmri_first_level_proc.egg-info/" lines_changed="deleted" />
        <file path="ABCD_fmri_orchestrator_S3_brainstorm_upstream_20261015_150913.md" lines_changed="moved" />
        <file path="FIX_fromOrch.txt" lines_changed="moved" />
        <file path="HARMONIZE_fmri-first-level-proc_20260816_212459.md" lines_changed="moved" />
        <file path="TODO_fmri-first-level-proc_20260812_132545.md" lines_changed="moved" />
        <file path="upstream_polort_dof_issue.md" lines_changed="moved" />
      </files_modified>
      <notes>The orchestrator paused here and asked the user for per-invocation permission before any deletion, per the user's destructive-operations rule. The user asked for a non-grep verification sweep before proceeding; each of the five deletion targets and five move targets was read directly (not merely grepped) and confirmed unused by the package, its tests and its docs, then the user approved all five deletions and five moves. The filesystem-scope hook additionally required two explicit, session-bound grants (destructive on the project root for the deletions; write on the archive directory for the moves), which the orchestrator surfaced verbatim and the user approved running. All five deletions and five moves completed with no destination collisions; verified absent from the project root and present in the archive directory afterward.</notes>
    </change>
    <change id="C34" status="done" user_decision="n/a">
      <files_modified>
        <file path="example_config.yaml" lines_changed="7" />
      </files_modified>
      <notes>Replaced the three stale enorm-censoring fd_threshold comments with Power-FD wording; task_act's stat_buckets example now lists all five stat types with a comment describing the index-key grammar; added a comment to task_conn's extraction block describing the new LSS/beta-series index files. Re-validated the whole file against the live v4 schema validator: every analysis block fails only on its placeholder scan paths, with zero schema violations.</notes>
    </change>
    <change id="C35" status="done" user_decision="n/a">
      <files_modified>
        <file path="proc_config_final.yaml" lines_changed="rewritten" />
        <file path="proc_config_final_run.yaml" lines_changed="rewritten" />
      </files_modified>
      <notes>Both git-ignored, local-only root configs were rewritten in place on the v4 structure (laid out like example_config.yaml), porting every path, label, contrast, HRF choice and setting from the prior files verbatim, with no old copy kept. Per the user's directive: all analyses now set censor_prev_tr/scale_to_psc true and roi_zero_handling "exclude"; task_act's legacy extract/extract_labels/extract_stat keys are replaced by stat_buckets listing all five stat types; the Mode B task blocks carry run_lengths/run_labels as null with an orchestrator-filled comment; rest_conn's run_labels are set from the scan file order ([1, 2] and [1, 2, 3, 4] respectively); rest_conn gained explicit use_sequenced_bandpass: false and every extraction block gained extract_raw_ptseries: false. Re-validated both files against the live v4 schema validator: every analysis block fails only on a placeholder/missing-template path, with zero schema violations.</notes>
    </change>
    <change id="C36" status="skipped" user_decision="defer">
      <files_modified />
      <notes>Not started. Per the tech spec, this change edits a file in a separate private downstream repository and requires its own write approval in that project, to be sought after this build report is reviewed.</notes>
    </change>
  </changes_applied>
  <summary>
    <total_changes>36</total_changes>
    <completed>35</completed>
    <skipped>1</skipped>
    <blocked>0</blocked>
  </summary>
  <next_steps>Recommended: run /test to validate all changes, including real-AFNI assertions of the new F34/F35 output grammars (stat-bucket index keys, LSS/beta-series index schemas) across every stat type and HRF model, the F42/F42a ledger-rerun behavior, and the full suite in fresh out_dirs. After /test, run /document for the INPUT_SPECIFICATION.md and CHANGELOG.md updates the clean and CR reports routed there. C36 (the consumer project's proc_config_final.yaml comment fixes) remains, pending a separate write approval in that repository.</next_steps>
</implement_report>
