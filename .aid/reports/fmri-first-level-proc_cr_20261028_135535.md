<cr_report>
  <meta project="fmri-first-level-proc" mode="cr" timestamp="2026-10-28T17:55:35Z" />
  <scope>Cross-project compatibility review of the clean report fmri-first-level-proc_clean_20261028_131136.md (43 findings) against the I/O contracts and harmonization conventions of fmri-bids-recon, fmri-preproc and fmri-proc-orchestrator, and alignment (not harmonization) with the private downstream consumer project. Sources read directly: fmri-proc-orchestrator (pipeline.py first-level invocation and exception map, qc.py first-level QC reading, adapters/seam2.py, pyproject.toml, tools.lock.yaml, TODO file); consumer (orchestrate_first_level.py imports and invocation, orchestrator_utils.py QC builders, warning filter, config builder, template validation, version window; three proc templates; environment.yaml; README.md; INPUT_SPECIFICATION.md; TODO file); fmri-preproc (output_contract.py write_motion_1d, confounds.py tissue_mean, environment.yaml, pyproject.toml); fmri-bids-recon (package sources and pyproject.toml); fmri-first-level-proc public surface (__init__.py, names.py, first_level_utils.FirstLevelResult, qc.py key specs) and published v3.1.0 (git 0ad0445).</scope>
  <research_conducted>No literature research (contract review). Repository-wide searches of all four sibling projects for every name the clean pass removes, renames or changes. Local computation: the consumer's 29 contrast labels in each of three proc templates run through first_level_utils.sanitize_filename_label (no duplicates, no collisions). Consolidated recommendation checked by three independent proposal-verification agents: PV-1 verified, PV-2 verified (two minor scope concerns), PV-3 concerns (one minor: F35 lacked the pin-and-document gate proposed for F34; folded into F2 below). Agent access gaps (fmri-preproc file scope; no git for agents) were closed by direct orchestrator reads (output_contract.py 596-640; git show 0ad0445:fmri_first_level_proc/first_level_utils.py lines 100-203, 1161).</research_conducted>
  <findings>
    <finding id="F1" severity="note" category="reproducibility">
      <location file="fmri_first_level_proc/__init__.py; names.py; first_level_utils.py; runtime.py; exceptions.py; run_first_level.py; first_level_config.py" lines="public surface" />
      <description>Python interface used by the siblings is untouched by every clean item.</description>
      <evidence>fmri-proc-orchestrator pipeline.py:248-257 imports load_and_validate, run_first_level.DISPATCH, exceptions.FmriFirstLevelError and maps exceptions by class name (ConfigError, InputError, GuardError, ToolUnavailableError, ToolVersionError, ToolExecutionError, ModelError). The consumer imports first_level_utils.setup_logging, first_level_config.load_and_validate, run_first_level.DISPATCH, names (frozen_primary, ledger, qc_summary, timing_errors), the seven exception classes, runtime.preflight_tool_environments/runtime_check/load_lockfile, and reads FirstLevelResult.output_files/warnings/status/qc_summary and __version__. Searches of all four projects found no use of any name the clean pass removes or changes (argparse helpers, BOOL_KEYS, latest_staged, run_tag, template_labels, _get_subbrik_stat_aux, dataclasses_copy_without_psc, _t1_checks, _jsonable, get_3dinfo_properties, extract/index helpers, intermediate_cls). QC keys read (pct_censored, dof) and frozen primary filenames are unchanged; __version__ and schema_version stay "4.0.0", inside the consumer's [4.0.0, 5.0.0) window.</evidence>
      <literature>n/a</literature>
      <impact>No sibling breakage from the clean pass.</impact>
      <recommendation>No change.</recommendation>
    </finding>
    <finding id="F2" severity="major" category="reproducibility">
      <location file="fmri_first_level_proc/task_act_first_level.py; task_conn_first_level.py; estimability.py" lines="clean F34 (stat-bucket index and parcellation outputs), clean F35 (LSS index outputs)" />
      <description>Clean F34 and F35 define new consumer-visible output formats (F34: {ext}_{stat}_index.json keys and stat-bucket parcellation CSV row labels; F35: {pre}_concat_LSS_index.json, per-condition {pre}_concat_bseries_{cond}_index.json, and an lss_index field on qc_summary trials records) without pinning their grammar.</description>
      <evidence>Clean report F34 specifies only "full-label index keys (Tstat -> Zstat for Z)"; F35 specifies files but not schemas. The consumer requests stat_buckets ["Coef", "Tstat", "Zstat"], states "address by label, never by sub-brick index" in its proc template, and uploads every FirstLevelResult.output_files entry, so these formats become the analysis contract for its outputs. No consumer or orchestrator code currently parses them (PV-2). The current keys are themselves defective (leading apostrophe; multi-basis collapse), so F34 is required for the consumer.</evidence>
      <literature>n/a</literature>
      <impact>Unpinned formats invite drift and silent misaddressing of contrasts by downstream analyses.</impact>
      <recommendation>(1) /implement plan pins, before building F34/F35: F34 index key = exact `3dinfo -label` sub-brick label (e.g. ave_negface_GLT#0_Tstat; a Z bucket uses the same label with Tstat replaced by Zstat), value = 0-based position in the extracted bucket, parcellation CSV row label = the same key; F35 index JSON key/value schema (each LSS sub-brick position to condition, run, onset, linking to trials records) and the lss_index type and null rule. (2) /document both in INPUT_SPECIFICATION.md and the 4.0.0 CHANGELOG (part of clean F2's sub-brick-identifier documentation). (3) /test asserts each grammar on real AFNI output, including multi-basis HRFs for F34. (4) At v4.0.0 publish, give the consumer project a short downstream note describing the new key format and new files (and the F8 item below).</recommendation>
    </finding>
    <finding id="F3" severity="minor" category="reproducibility">
      <location file="fmri_first_level_proc/engine.py; task_act_first_level.py; task_conn_first_level.py; rest_conn_first_level.py" lines="run_stage rerun triggers (552-562); StageSpecs" />
      <description>Stage hashes cover declared config fields, derived files/values, upstream hashes and tool versions, not code logic; the package version stays 4.0.0. Clean F34 and F35 change outputs only through code, so on their own they leave stage hashes unchanged. F42/F42a change template and model-stage hashes, which reruns every downstream stage once only when all four land together.</description>
      <evidence>engine.stage_hash payload (label, fields, derived_files, derived_values, upstream, versions). Consumer templates set remove_previous true in two of three (ledger-scoped removal disables reuse); proc_config_final.yaml sets false. PV-3: logic-only fixes would otherwise reuse stale, incorrectly computed stat-bucket outputs.</evidence>
      <literature>brainstorm_20261009_112745 design decision (9): numerics-changing releases must bump the package version.</literature>
      <impact>Partial builds, or reuse of pre-clean v4.0.0-build output directories, could leave buggy stat-bucket or LSS outputs in place.</impact>
      <recommendation>(1) /implement F34, F35, F42 and F42a in one build, with no intermediate run or commit containing only some of them. (2) /test runs all post-clean verification in fresh out_dirs and recomputes (never reuses) any directory produced by the pre-clean v4.0.0-build; this is a pre-release step. (3) No version bump is needed because v4.0.0 is unreleased; any later logic-only output change must bump the package version or add a hash-visible input.</recommendation>
    </finding>
    <finding id="F4" severity="note" category="robustness">
      <location file="fmri_first_level_proc/task_act_first_level.py; first_level_config.py" lines="clean F2" />
      <description>Clean F2's new ConfigError for duplicate or sanitize-colliding contrast labels does not reject any consumer template.</description>
      <evidence>All three consumer proc templates (29 contrast labels each, containing hyphens) have no duplicates and no collisions under first_level_utils.sanitize_filename_label (computed directly). fmri-proc-orchestrator maps ConfigError.</evidence>
      <literature>n/a</literature>
      <impact>None.</impact>
      <recommendation>No change.</recommendation>
    </finding>
    <finding id="F5" severity="note" category="reproducibility">
      <location file="pyproject.toml; tools.lock.yaml; smoothing.py; prep.py" lines="clean F26, F29, F30, F13, F15" />
      <description>Remaining harmonization points hold.</description>
      <evidence>F29: the eight level0..level7 markers are identical in fmri-bids-recon and fmri-proc-orchestrator pyproject.toml (fmri-preproc declares none). F30: validated Python 3.14 matches fmri-proc-orchestrator tools.lock.yaml (3.14.3) and the consumer's environment (python=3.14); all siblings keep a >=3.12 floor; the consumer filters only AFNI drift warnings, so the F30 fallback (3.13) would surface a medium Python UNVALIDATED_VERSION in consumer QC (status unaffected), already stated in the clean F30 gate. F26 removes the 13-run cap; consumer tasks use 2-4 runs. F13/F15 keep __version__ and SCHEMA_VERSION at "4.0.0".</evidence>
      <literature>n/a</literature>
      <impact>None.</impact>
      <recommendation>No change.</recommendation>
    </finding>
    <finding id="F6" severity="note" category="assumptions">
      <location file="fmri_first_level_proc/nuisance.py" lines="clean F16 (module docstring)" />
      <description>The motion input contract restated by clean F16 ([tx, ty, tz, rx, ry, rz], mm and degrees; reorder 3dvolreg output translations-first) matches fmri-preproc's declared output contract; tissue inputs (confound columns csf/white_matter) are not affected by any clean item.</description>
      <evidence>fmri-preproc output_contract.py write_motion_1d docstring: "6 columns [tx, ty, tz, rx, ry, rz], translations in millimetres, rotations in DEGREES". Both orchestrators extract motion by confound column name.</evidence>
      <literature>n/a</literature>
      <impact>None from the clean pass (preproc-side mislabel in F8).</impact>
      <recommendation>No change.</recommendation>
    </finding>
    <finding id="F7" severity="minor" category="reproducibility">
      <location file="fmri_first_level_proc/first_level_utils.py" lines="clean F9; clean F22/F42(C)" />
      <description>The clean pass removes names that were importable from published v3.1.0: dir_path_exists, file_path_exists, valid_string_list, valid_stat_type, valid_ave_type, valid_conn_type (v3.1.0 first_level_utils.py lines 100-203) and the orient/spacing keys of get_3dinfo_properties (v3.1.0 line 1161). None were in __all__ and no sibling uses them; third-party v3.1.0 code could.</description>
      <evidence>git show 0ad0445:fmri_first_level_proc/first_level_utils.py; sibling searches (F1).</evidence>
      <literature>Semantic Versioning: removals permitted in a major release when documented.</literature>
      <impact>Undocumented breaking removals.</impact>
      <recommendation>/document: add a "Removed" entry to the 4.0.0 CHANGELOG (clean F31 item 5) listing the six helpers and the two get_3dinfo_properties keys, alongside the run-first-level alias removal (clean F38).</recommendation>
    </finding>
    <finding id="F8" severity="note" category="generalizability">
      <location file="sibling projects" lines="see evidence" />
      <description>Pre-existing sibling-side misalignments, neither caused nor fixed by the clean pass.</description>
      <evidence>(a) fmri-proc-orchestrator qc.py:108 reads qc_summary "trial_counts", which v4 does not emit (tracked: orchestrator TODO line 43). (b) fmri-proc-orchestrator seam2.py:82-111 concatenates runs without run labels/lengths (tracked: orchestrator TODO item 3, A1). (c) Consumer environment.yaml pins git+...fmri_first_level_proc.git@v3.2.0 (nonexistent tag, old repo name) while requiring >=4.0.0 (tracked: consumer TODO item 3). (d) Consumer README.md:213 and INPUT_SPECIFICATION.md:159 say remove_previous is forced to true, while build_first_level_config preserves the template value and proc_config_final.yaml sets false with a stale "forced to true" comment (partly tracked: consumer TODO item 5 covers only the code docstring). (e) fmri-preproc output_contract.py write_motion_1d calls translations-first the "AFNI 3dvolreg native" order (tracked: pipeline harmonization report F1).</evidence>
      <literature>n/a</literature>
      <impact>(d) matters more after the clean pass: F42/F42a stage hashing is only active when remove_previous is false.</impact>
      <recommendation>No change in fmri-first-level-proc. Track each item in its owning project per the references above, and add item (d) to the consumer downstream note (F2 item 4).</recommendation>
    </finding>
    <finding id="F9" severity="note" category="generalizability">
      <location file="fmri_first_level_proc/bids.py" lines="clean F10" />
      <description>fmri-bids-recon has no code dependency on this package; the only clean change in bids.py is removal of a shadowed module logger; BIDS output naming and discovery are untouched.</description>
      <evidence>Searches of fmri_bids_recon/ sources; clean F10.</evidence>
      <literature>n/a</literature>
      <impact>None.</impact>
      <recommendation>No change.</recommendation>
    </finding>
  </findings>
  <summary>
    <critical_count>0</critical_count>
    <major_count>1</major_count>
    <minor_count>2</minor_count>
    <overall_assessment>conditionally_defensible</overall_assessment>
  </summary>
  <action_items>
    <item priority="P1" target_mode="implement" finding_ref="F2" description="In /implement plan, pin F34 index-key/parcellation-row grammar (exact 3dinfo -label label; Tstat->Zstat for Z; 0-based position) and F35 index JSON schemas and lss_index type/null rule before building" />
    <item priority="P1" target_mode="test" finding_ref="F2" description="Real-AFNI assertions of F34 and F35 output grammars, including multi-basis HRFs" />
    <item priority="P1" target_mode="implement" finding_ref="F3" description="Build F34, F35, F42 and F42a in one build; no partial intermediate run or commit" />
    <item priority="P1" target_mode="test" finding_ref="F3" description="All post-clean verification in fresh out_dirs; recompute any pre-clean v4.0.0-build output directory before release" />
    <item priority="P2" target_mode="implement" finding_ref="F2" description="Document F34/F35 grammars in INPUT_SPECIFICATION.md and the 4.0.0 CHANGELOG (route: /document)" />
    <item priority="P2" target_mode="implement" finding_ref="F7" description="4.0.0 CHANGELOG Removed entry: six v3.1.0 first_level_utils helpers and get_3dinfo_properties orient/spacing keys (route: /document)" />
    <item priority="P2" target_mode="brainstorm" finding_ref="F8" description="At v4.0.0 publish, write the consumer downstream note: new index key format and files (F2) and the remove_previous documentation/template mismatch (F8 d); sibling items (a)-(c), (e) stay with their owning projects" />
  </action_items>
</cr_report>
