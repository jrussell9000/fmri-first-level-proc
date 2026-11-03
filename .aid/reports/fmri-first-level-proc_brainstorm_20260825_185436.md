<brainstorm_report>
  <meta project="fmri-first-level-proc" mode="brainstorm" timestamp="2026-08-25T18:54:36Z" />
  <context_files>
    <file path="fmri_first_level_proc/first_level_utils.py" relevance="T1: graded_warning() and FirstLevelResult.warnings (accumulator target); T3: PSC scaling utility placement" />
    <file path="fmri_first_level_proc/first_level_config.py" relevance="T3: scale_to_psc config field; T4: ResolvedConfig extraction field redesign; VALID_STAT_TYPES replacement" />
    <file path="fmri_first_level_proc/task_act_first_level.py" relevance="T3: PSC scaling integration; T4: _find_subbrik_index, _get_subbrik_stat_aux, extract_effects (replacement targets)" />
    <file path="fmri_first_level_proc/task_conn_first_level.py" relevance="T3: PSC scaling integration (concatenated scan)" />
    <file path="fmri_first_level_proc/rest_conn_first_level.py" relevance="T3: PSC scaling integration (per-run scaling)" />
    <file path="fmri_first_level_proc/exceptions.py" relevance="T2: ToolVersionError addition to exception hierarchy" />
    <file path="fmri_first_level_proc/runtime.py" relevance="T2: probe_tool_versions() ToolUnavailableError-to-ToolVersionError migration" />
    <file path="fmri_first_level_proc/run_first_level.py" relevance="T2: exit code mapping for ToolVersionError" />
    <file path="example_config.yaml" relevance="T3: scale_to_psc field; T4: extraction block redesign" />
    <file path="fmri-first-level-proc_brainstorm_20260824_140104.md" relevance="Upstream harmonization report containing T1 and T2 pre-decided items" />
  </context_files>
  <topics>
    <topic id="T1" title="Warning accumulation: add module-level _WARNING_ACCUMULATOR">
      <summary>The cross-pipeline contract (from fmri-proc-orchestrator harmonization) standardizes warning accumulation via a module-level list with get/clear API. Currently, graded_warning() (first_level_utils.py:225) returns a dict that callers manually append to local warnings lists threaded through intermediate function signatures into FirstLevelResult.warnings. The accumulator pattern centralizes this: graded_warning() appends to the module-level list, and pipeline entry points call clear_warnings() at entry and get_warnings() at FirstLevelResult construction.</summary>
      <research>Pre-decided from orchestrator harmonization. No independent research required.</research>
      <approaches>
        <approach id="A1" label="Module-level accumulator" feasibility="high" risk="low">
          <description>Add _WARNING_ACCUMULATOR (list[dict]), get_warnings() -> list[dict], and clear_warnings() -> None to first_level_utils.py. Have graded_warning() append to the accumulator in addition to returning the dict. Update each pipeline entry point (run_task_act, run_task_conn, run_rest_conn): call clear_warnings() at entry; at FirstLevelResult construction, use get_warnings(). Remove the local warnings list threading from intermediate function signatures where it is no longer needed.</description>
          <pros>Consistent with sister modules (bids-recon, preproc); eliminates signature pollution; centralizes warning lifecycle</pros>
          <cons>Module-level mutable state requires clear_warnings() discipline at entry points to avoid cross-run leakage</cons>
        </approach>
      </approaches>
      <decision status="decided" chosen="A1">Pre-decided in fmri-proc-orchestrator harmonization (T4 of that report). Adopted as-is for cross-pipeline consistency.</decision>
    </topic>
    <topic id="T2" title="Add ToolVersionError to exception hierarchy">
      <summary>The cross-pipeline contract distinguishes ToolUnavailableError (binary not found on PATH) from ToolVersionError (binary exists but version below required floor). Currently, runtime.py uses ToolUnavailableError for both conditions. Verified in code: probe_tool_versions() raises ToolUnavailableError at runtime.py:191-193 for AFNI version mismatch (binary found, version wrong) and at runtime.py:217-221 for Python minor-series mismatch. These version-mismatch sites should raise ToolVersionError instead, while the binary-absent and probe-failure sites (runtime.py:180, 187) should retain ToolUnavailableError.</summary>
      <research>Pre-decided from orchestrator harmonization. No independent research required.</research>
      <approaches>
        <approach id="A1" label="ToolVersionError subclass" feasibility="high" risk="low">
          <description>Add ToolVersionError as a subclass of FmriFirstLevelError (with context: dict parameter, matching the existing exception hierarchy pattern) in exceptions.py. Update runtime.py: raise ToolVersionError on version mismatch (AFNI version wrong at line 192, Python minor-series mismatch at line 218). Retain ToolUnavailableError for binary genuinely absent (line 180) and version unparseable (line 187). Edge case: malformed Python pin strings (lines 206, 213) are lockfile configuration errors rather than runtime version mismatches; classification is an implementation-level detail for /implement. Update run_first_level.py to map ToolVersionError to exit code 4 (same bucket as ToolUnavailableError and ToolExecutionError).</description>
          <pros>Semantic precision; orchestrator can distinguish "install the tool" from "upgrade the tool" in error handling; consistent with bids-recon</pros>
          <cons>Minimal: one additional exception class to maintain</cons>
        </approach>
      </approaches>
      <decision status="decided" chosen="A1">Pre-decided in fmri-proc-orchestrator harmonization (T5 of that report). Adopted as-is for cross-pipeline consistency.</decision>
    </topic>
    <topic id="T3" title="Percent signal change (PSC) scaling">
      <summary>Investigation revealed zero instances of within-subject intensity standardization in either fmri-first-level-proc (7 modules) or a downstream consumer orchestrator. The only Z-scoring found was in the orchestrator's QC carpet plot (purely cosmetic, not analytical). PSC scaling (dividing each voxel's time series by its temporal mean, multiplying by 100) is the standard AFNI preprocessing step for normalizing arbitrary scanner intensity units. Without it, raw beta coefficients (Coef sub-bricks) are not comparable across subjects at the group level. T-statistics, F-statistics, and R-squared are scale-invariant, but Coef values are directly affected.</summary>
      <research>
        R1 (within-subject standardization survey): Confirmed PSC scaling is the standard first-level normalization approach. AFNI's 3dDeconvolve applies no implicit scaling. T/F/Z/R-squared statistics are scale-invariant; raw betas are not. PSC should be applied before regression. Grand mean scaling and Z-scoring are alternatives used in other software (FSL, SPM) but PSC is the AFNI convention.

        R2 (resting-state PSC verification, consensus): Four converging sources:
        (1) AFNI afni_proc.py places the 'scale' block at the identical sequential position for task and rest ("despike tshift align tlrc volreg blur mask scale regress"). Most resting-state examples (Ex. 9, 11, 11b, 12b) include it, though framed as optional for correlation-only analyses.
        (2) AFNI documentation states PSC has no direct effect on voxelwise correlations (Pearson/partial are scale-invariant) but does affect ROI averages used for connectivity, since it equalizes the contribution of voxels with different raw intensity means within an averaged mask.
        (3) XCP-D (PennLINC) omits PSC from its main denoising/connectivity path, reserving amplitude normalization for ALFF-type metrics only.
        (4) PerAF literature (Jia et al. 2020, PLOS ONE) confirms amplitude metrics are scale-sensitive while correlation-based connectivity is scale-invariant.

        Resting-state conclusion: PSC is defensible for rest_conn because this pipeline computes parcellated connectivity (ROI averages before correlation), where PSC equalizes voxel-weighting within ROIs. PSC is not mathematically required for the correlation step itself (scale-invariant) but affects the ROI-averaging step that precedes it.
      </research>
      <approaches>
        <approach id="A1" label="Optional PSC scaling, default true" feasibility="high" risk="low">
          <description>Add scale_to_psc boolean config field (per-block, default true). New shared utility scale_to_psc() in first_level_utils.py using 3dTstat -mean + 3dcalc with AFNI expression min(200, a/b*100)*step(a)*step(b). PSC-scaled file is a standard pipeline output. Pipeline placement: after min-outlier EPI extraction, before regression (consistent with AFNI canonical block ordering). task_act/task_conn: scale concatenated scan. rest_conn: scale each run independently (before gen_residual_ts).</description>
          <pros>Makes raw betas comparable across subjects; equalizes voxel weighting in ROI averages for connectivity; consistent with AFNI canonical pipeline ordering; opt-out available for users who do not need it</pros>
          <cons>Additional processing step and output file per run/scan; moderate justification for rest_conn (affects ROI averaging, not correlation itself)</cons>
          <statistical_considerations>PSC scaling is a monotonic, voxelwise transformation that does not alter the rank ordering or relative differences within a time series. It transforms arbitrary scanner units to a standardized percent-change metric. The 200% ceiling (step functions + min) guards against division-by-near-zero in low-signal voxels. For task analyses, PSC is required to make beta coefficients interpretable and comparable across subjects. For resting-state parcellated connectivity, PSC equalizes the contribution of voxels with different baseline intensities within ROI averages, preventing high-intensity voxels from dominating the mean signal used for correlation.</statistical_considerations>
        </approach>
        <approach id="A2" label="No PSC scaling" feasibility="high" risk="medium">
          <description>Leave the pipeline without intensity standardization, relying on the scale-invariance of T/F/Z statistics for task analyses and the scale-invariance of correlation for connectivity analyses.</description>
          <pros>No additional processing step; simpler pipeline</pros>
          <cons>Raw betas uncomparable across subjects; ROI averages dominated by high-intensity voxels; inconsistent with AFNI standard processing; limits downstream analysis options</cons>
        </approach>
      </approaches>
      <decision status="decided" chosen="A1">Implement optional PSC scaling (default true) across all three pipelines. Justification strength varies by analysis type (strong for task_act/task_conn betas, moderate for rest_conn ROI averaging), but default-on with opt-out handles this cleanly. PSC-scaled file is a standard pipeline output. Verified by research agent R2 that the sequential position (after EPI selection, before regression) is consistent with AFNI canonical block ordering for both task and resting-state.</decision>
    </topic>
    <topic id="T4" title="Stat bucket extraction redesign">
      <summary>The current extraction system (extract_effects in task_act_first_level.py:344) requires the user to specify individual condition/contrast labels and a single stat type, producing one single-sub-brick NIfTI per label. This design has three limitations: (1) users must know and enumerate their condition/contrast labels in advance, which vary across subjects; (2) only one stat type is extracted per run; (3) the per-label output pattern creates many small files. The redesign replaces this with stat-type-based bucket outputs: one multi-sub-brick NIfTI per requested stat type containing all conditions/contrasts, plus a subject-specific JSON index mapping condition/contrast labels to sub-brick indices.</summary>
      <research>No external research required. Design derived from AFNI's native bucket output structure (3dDeconvolve produces labeled sub-bricks with suffixes like condName#0_Coef, condName#0_Tstat) and the existing _find_subbrik_index() utility (task_act_first_level.py:280) which already parses 3dinfo -subbrick_info output.</research>
      <approaches>
        <approach id="A1" label="Stat-type bucket outputs with JSON index" feasibility="high" risk="low">
          <description>Replace extract/extract_labels/extract_stat config fields with stat_buckets: list[str]. VALID_STAT_BUCKET_TYPES = {"Coef", "Tstat", "Fstat", "R^2", "Zstat"} (Zstat is synthetic T-to-Z conversion via p2dsetstat). For each requested stat type, output: (a) a multi-sub-brick NIfTI containing all conditions/contrasts for that stat type (via 3dbucket), (b) a JSON index mapping condition/contrast labels to sub-brick indices, and (c) when template_path is available, a parcellated CSV (rows = conditions/contrasts, columns = ROIs). Two-layer validation: config-time validation against VALID_STAT_BUCKET_TYPES, plus runtime discovery via 3dinfo -subbrick_info to identify which stat types are actually present in the bucket output and communicate availability to the user. extract_resids remains as a separate toggle. extract_raw_ptseries remains unchanged.</description>
          <pros>Eliminates need to know condition labels in advance; supports multiple stat types per run; produces fewer, more organized output files; JSON index enables programmatic downstream access; runtime discovery makes stat availability transparent</pros>
          <cons>Breaks backward compatibility with current extraction config schema (extract/extract_labels/extract_stat removed); requires migration documentation for existing users</cons>
          <statistical_considerations>The stat-type bucket approach preserves sub-brick ordering from AFNI's bucket output. The JSON index provides the ground-truth mapping between condition/contrast labels and sub-brick positions, which is essential because AFNI's sub-brick ordering in the bucket output is determined by the 3dDeconvolve stimulus ordering (not alphabetical or user-specified). The Zstat option applies a T-to-Z conversion using AFNI's p2dsetstat with DOF extracted from BRICK_STATAUX, matching the existing _get_subbrik_stat_aux() pattern.</statistical_considerations>
        </approach>
        <approach id="A2" label="Keep per-effect extraction, add multi-stat support" feasibility="high" risk="low">
          <description>Retain the current per-label extraction pattern but allow multiple stat types. Users still specify individual labels; the system extracts one sub-brick per label per stat type.</description>
          <pros>Backward compatible; incremental improvement</pros>
          <cons>Still requires users to enumerate labels; still produces many small files; does not solve the cross-subject label variability problem</cons>
        </approach>
      </approaches>
      <decision status="decided" chosen="A1">Replace extract/extract_labels/extract_stat entirely with stat_buckets config field. Output triple per stat type: NIfTI bucket + JSON index (always) + parcellated CSV (when template_path available, rows = conditions/contrasts, columns = ROIs). extract_resids stays as a separate toggle. Config shape: extraction: { stat_buckets: ["Tstat", "Coef"], extract_out_file_pre: "...", extract_resids: false, extract_raw_ptseries: false }.</decision>
    </topic>
  </topics>
  <action_items>
    <item priority="P1" target_mode="implement" description="T1: Add _WARNING_ACCUMULATOR (list[dict]), get_warnings() -> list[dict], and clear_warnings() -> None to first_level_utils.py. Have graded_warning() append to the accumulator. Update run_task_act, run_task_conn, run_rest_conn: call clear_warnings() at entry, use get_warnings() at FirstLevelResult construction. Remove local warnings list threading from intermediate function signatures." />
    <item priority="P1" target_mode="implement" description="T2: Add ToolVersionError(FmriFirstLevelError) with context: dict parameter to exceptions.py. Update runtime.py probe_tool_versions(): raise ToolVersionError at lines 192 (AFNI version mismatch) and 218 (Python minor-series mismatch). Retain ToolUnavailableError for binary-absent (line 180) and version-unparseable (line 187). Update run_first_level.py to map ToolVersionError to exit code 4." />
    <item priority="P1" target_mode="implement" description="T3: Add scale_to_psc() utility to first_level_utils.py (3dTstat -mean + 3dcalc, expression: min(200, a/b*100)*step(a)*step(b)). Add scale_to_psc: bool = True to ResolvedConfig. Add config validation/resolution in first_level_config.py. Integrate into task_act (scale concatenated scan after min-outlier EPI, before censor file), task_conn (same position), and rest_conn (scale each run independently before gen_residual_ts). PSC-scaled file is a standard pipeline output." />
    <item priority="P1" target_mode="implement" description="T4: Replace extract/extract_labels/extract_stat with stat_buckets: list[str] | None in ResolvedConfig. Replace VALID_STAT_TYPES with VALID_STAT_BUCKET_TYPES = {'Coef', 'Tstat', 'Fstat', 'R^2', 'Zstat'}. Implement two-layer validation: config-time check against VALID_STAT_BUCKET_TYPES, runtime discovery via 3dinfo -subbrick_info. Replace extract_effects() with stat-bucket extraction: per stat type, output NIfTI bucket (3dbucket) + JSON index (label-to-index mapping) + parcellated CSV when template_path available (rows = conditions/contrasts, columns = ROIs). Retain extract_resids and extract_raw_ptseries as separate toggles." />
    <item priority="P1" target_mode="implement" description="T3/T4: Update example_config.yaml to reflect new config schema: add scale_to_psc field, replace extraction block with stat_buckets-based schema." />
    <item priority="P1" target_mode="test" description="T1-T4: Extend test suite for all four topics. T1: warning accumulator lifecycle (clear/append/get, cross-run isolation). T2: ToolVersionError raise sites and exit code mapping. T3: scale_to_psc() utility, config validation, pipeline integration. T4: stat bucket extraction (NIfTI + JSON + CSV outputs), VALID_STAT_BUCKET_TYPES validation, runtime discovery." />
  </action_items>
  <next_steps>Proceed to /implement for all four topics. Recommended implementation order: T1 (warning accumulator, foundational) -> T2 (ToolVersionError, isolated exception change) -> T3 (PSC scaling, pipeline-wide integration) -> T4 (stat bucket extraction, most complex redesign). Follow with /test to extend the test suite.</next_steps>
</brainstorm_report>
