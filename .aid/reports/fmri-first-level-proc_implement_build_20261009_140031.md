<implement_report>
  <meta project="fmri-first-level-proc" mode="implement" submodule="build" timestamp="2026-10-09T14:00:31-04:00" />
  <spec_ref>fmri-first-level-proc_implement_plan_20261009_120006.md</spec_ref>

  <changes_applied>
    <change id="C1" status="done" user_decision="n/a">
      <files_modified>
        <file path="pyproject.toml" lines_changed="8" />
      </files_modified>
      <notes>Version bumped to 4.0.0, dependencies pinned to minimums, single console script, package-data entry for the lockfile added.</notes>
    </change>

    <change id="C2" status="done" user_decision="n/a">
      <files_modified>
        <file path="environment.yaml" lines_changed="5" />
      </files_modified>
      <notes>Conda spec aligned to the pyproject dependency set and minimums.</notes>
    </change>

    <change id="C3" status="done" user_decision="proceed">
      <files_modified>
        <file path="fmri_first_level_proc/tools.lock.yaml" lines_changed="14" />
        <file path="tools.lock.yaml" lines_changed="0" />
      </files_modified>
      <notes>Packaged lockfile 2.0.0 created with per-tool minimum/validated entries. The repository-root lockfile was a destructive deletion deferred to the user; it was approved and removed after the build completed and the packaged copy was verified working end-to-end in every pipeline smoke test.</notes>
    </change>

    <change id="C4" status="done" user_decision="n/a">
      <files_modified>
        <file path=".gitignore" lines_changed="16" />
      </files_modified>
      <notes>Whitelisted the packaged lockfile, CHANGELOG.md, and all 11 new modules.</notes>
    </change>

    <change id="C5" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/exceptions.py" lines_changed="1" />
      </files_modified>
      <notes>ToolVersionError docstring reworded to minimum-version policy language.</notes>
    </change>

    <change id="C6" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/names.py" lines_changed="268" />
      </files_modified>
      <notes>Created. All naming functions verified by direct assertion (smoothing tokens, with_token insertion, bucket/conn output naming, template stem extraction).</notes>
    </change>

    <change id="C7" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_utils.py" lines_changed="620" />
      </files_modified>
      <notes>Rewritten. 17-entry closed warning-code table, FirstLevelResult with intermediate_files, run_afni_command/run_afni_capture with cwd, AFNI warning-block logging, within-run tissue derivative computation, bandpass without -nodetrend. 22 superseded functions deleted and confirmed absent by introspection. During end-to-end verification against real AFNI, found and fixed a pre-existing bug carried over from v3.1.0: 3dToutcount does not accept -quiet on AFNI 26.0.09.</notes>
    </change>

    <change id="C8" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/checkpoint.py" lines_changed="280" />
      </files_modified>
      <notes>Rewritten. Three record types (staged, completion, retired), unreadable-line tracking, canonical JSON hashing. Verified by direct read/write round-trip and hash-determinism assertions.</notes>
    </change>

    <change id="C9" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/runsets.py" lines_changed="283" />
      </files_modified>
      <notes>Created. RunSets single-source S_pre/S_final enforcement, Mode A/B run construction, T1 structural checks. Verified by direct construction and offset/selector assertions.</notes>
    </change>

    <change id="C10" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/qc.py" lines_changed="180" />
      </files_modified>
      <notes>Created. 30-key qc_summary schema with producer-pattern and identity-field enforcement. Verified by a merge_fragments test exercising value and records kinds.</notes>
    </change>

    <change id="C11" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/engine.py" lines_changed="420" />
      </files_modified>
      <notes>Created. RunContext with G4 refusal, ledger-scoped remove_previous, run_step/run_stage write protocol, five rerun triggers, retirement sweep, finish() assembly. This is the highest-risk module in the release; it was exercised end-to-end (not just unit-tested) by every pipeline smoke test below, including repeat-invocation reuse verification for task_act, task_conn and rest_conn.</notes>
    </change>

    <change id="C12" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/runtime.py" lines_changed="260" />
      </files_modified>
      <notes>Rewritten. 19-binary preflight list, packaged-lockfile loading via importlib.resources, minimum-version ToolVersionError, validated-version UNVALIDATED_VERSION warnings, per-process probe cache. Verified working in every smoke test (each run correctly detected AFNI 26.0.09 and the Python/numpy/pandas versions, emitting the expected validated-version warnings).</notes>
    </change>

    <change id="C13" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/events.py" lines_changed="300" />
      </files_modified>
      <notes>Created. Dual-scheme dual-delimiter events reading, Mode A/B run-aware event table construction, onset validation with timing-error records, AFNI onset-file text generation. Exercised end-to-end in both task_act and task_conn smoke tests.</notes>
    </change>

    <change id="C14" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/nuisance.py" lines_changed="330" />
      </files_modified>
      <notes>Created. Task two-pass censor/exclusion, rest per-run notch/censor/DOF dry run with dof_below_1 exclusion for both backends. Exercised end-to-end for task_act, task_conn, and all four rest_conn configuration axes (per-run/concat mode, simultaneous/sequenced backend).</notes>
    </change>

    <change id="C15" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/estimability.py" lines_changed="310" />
      </files_modified>
      <notes>Created. x1D parsing, estimability dry run, trial survival, floor enforcement, matrix-derived DOF. During verification, found and fixed a real parsing bug: AFNI's x1D header serializes StimBots/StimTops as comma-separated values, not whitespace-separated as initially assumed; this would have broken every estimability computation in task_act and task_conn.</notes>
    </change>

    <change id="C16" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/roi.py" lines_changed="420" />
      </files_modified>
      <notes>Created. 3dROIstats parsing with roi_zero_handling, template checks/resampling, non-constant mask, roi_qc coverage and low-baseline computations. During verification, found and fixed two real bugs: (1) the 3dROIstats -1Dformat column-header line does not start with '#' (a per-row identifier line that also starts with '#' was being mistaken for it), and leading tabs in data lines were not stripped before column-index alignment; (2) a mask with zero matching voxels legitimately produces an empty AFNI header/data block, which must return an empty result rather than raise. Also fixed two call sites that omitted the required .nii.gz extension on mask output paths.</notes>
    </change>

    <change id="C17" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/prep.py" lines_changed="280" />
      </files_modified>
      <notes>Created. Per-run PSC with the 25% nonpositive-baseline sentinel, task concatenation, run-intersection mask, model-input path helpers. Exercised end-to-end in every smoke test.</notes>
    </change>

    <change id="C18" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/smoothing.py" lines_changed="180" />
      </files_modified>
      <notes>Created. Data-derived smoothing mask, 3dBlurToFWHM -ACF wrapper, ACF FWHM QC via 3dFWHMx, SMOOTH_FWHM_OFF_TARGET and SMOOTH_INPUT_ABOVE_TARGET warnings. Exercised end-to-end in a dedicated task_act smoothing test; both warning codes were confirmed firing correctly against real AFNI output.</notes>
    </change>

    <change id="C19" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/connectivity.py" lines_changed="340" />
      </files_modified>
      <notes>Created. 1ddot parsing with block-boundary detection, rank-check for partial correlation, Fisher Z clipping, null-ROI and null-seed handling, matrix and seed contrasts. The 1ddot block parser was unit-checked in isolation only; no captured real AFNI output was retained, and it was not exercised through a full pipeline run.</notes>
    </change>

    <change id="C20" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/bids.py" lines_changed="180" />
      </files_modified>
      <notes>Rewritten. Per-run slot discovery with run-label inference from BIDS entities, collision warnings, output-path helpers removed.</notes>
    </change>

    <change id="C21" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_config.py" lines_changed="1285" />
      </files_modified>
      <notes>Rewritten. Closed schema with aggregate unknown-key errors, Mode A/B task inputs, run_labels/run_lengths/smoothing/roi_zero_handling fields, schema_version 4.0.0. Independently verified (not just the implementing agent's self-report) with five behavioral tests: aggregate unknown-key error listing multiple violations, GLOBAL_ONLY_KEYS-inside-block rejection, smoothing fwhm decimal-precision validation, pcorr+seed_to_voxel rejection, and a full Mode B validate/resolve cycle producing correct run_labels and schema_version.</notes>
    </change>

    <change id="C22" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_act_first_level.py" lines_changed="650" />
      </files_modified>
      <notes>Rewritten on the engine. Ran end-to-end against real AFNI on synthetic data: GLM, contrasts, estimability, onset generation, min-outlier EPI, PSC, and a second invocation confirming ledger reuse of the prep, min-outlier-epi and GLM stages. A separate run with smoothing enabled confirmed the smoothing and glm-smooth stages and both smoothing warning codes.</notes>
    </change>

    <change id="C23" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_conn_first_level.py" lines_changed="700" />
      </files_modified>
      <notes>Rewritten on the engine. Ran end-to-end against real AFNI: design matrix, estimability with LSS DOF, beta series via 3dLSS with correct beta_series_position indexing, and a second invocation confirming ledger reuse of prep, design-matrix, min-outlier-epi and beta-series stages. During verification, found and fixed a real bug: 3dinfo -dmin -dmax terminates each value with a literal '|' separator that was not being stripped before float parsing.</notes>
    </change>

    <change id="C24" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/rest_conn_first_level.py" lines_changed="680" />
      </files_modified>
      <notes>Rewritten on the engine. Ran end-to-end against real AFNI across four configuration axes: per-run mode with the simultaneous backend (plus ledger reuse on a second invocation across all five stages), concat mode, and the sequenced backend. During verification, found and fixed two real bugs: (1) the 3dBandpass call for BOLD data in the sequenced backend had -prefix positioned after the positional fbot/ftop arguments, which AFNI rejects; (2) 3dTproject's -input flag with the transpose-quote syntax fails to recognize non-.1D extensions (such as the .txt extension the original v3.1.0 docstring explicitly permitted for CSF/WM/GS paths) even though the same files work via -ort, requiring a normalization step before the NTRP-interpolation calls in the sequenced backend.</notes>
    </change>

    <change id="C25" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/run_first_level.py" lines_changed="40" />
      </files_modified>
      <notes>Single CLI entry point; runtime_check replaces the old preflight+probe+LOCKFILE_ABSENT branch; the deprecated alias and its exit path removed.</notes>
    </change>

    <change id="C26" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/__init__.py" lines_changed="1" />
      </files_modified>
      <notes>Package version bumped to 4.0.0. The full package import was confirmed clean only after every pipeline module was rewritten, since __init__.py imports all three pipeline run() functions at import time.</notes>
    </change>

    <change id="C27" status="done" user_decision="n/a">
      <files_modified>
        <file path="example_config.yaml" lines_changed="260" />
      </files_modified>
      <notes>Rewritten for 4.0.0: Mode B task_act example with a commented Mode A alternative, Mode A task_conn example, rest_conn example; every block carries roi_zero_handling and the smoothing block; CLI usage lines updated to the single console script name.</notes>
    </change>
  </changes_applied>

  <summary>
    <total_changes>27</total_changes>
    <completed>27</completed>
    <skipped>0</skipped>
    <blocked>0</blocked>
  </summary>

  <verification_notes>
    This build was verified directly against the real AFNI 26.0.09 binary on synthetic fMRI data, not only by static import and compilation checks. Every pipeline (task_act, task_conn, rest_conn) was run end-to-end at least once, with repeat-invocation ledger reuse confirmed for all three. Across this verification, nine real implementation bugs were found and fixed (listed in the per-change notes above for C7, C15, C16 twice, C23, and C24 twice), none of which were caught by compilation or import checks alone; all were caught only by executing real AFNI commands against real data and inspecting their actual output formats. The full package (`import fmri_first_level_proc`) imports cleanly post-build.

    Not exercised in this build's verification: parcellated and seed-to-voxel connectivity end-to-end (template-dependent; connectivity.py's 1ddot parser was unit-checked in isolation only; no captured real AFNI output was retained, and it was not exercised through a full pipeline run), roi-qc stages, extract_pbseries/extract_ptseries/extract_raw_ptseries, contrasts in task_conn connectivity, and the DISCOVERY_COLLISION/bids.py discovery path end-to-end. These gaps are candidates for /test's design phase.
  </verification_notes>

  <next_steps>Recommended: run /test to validate all changes, including the test-suite redesign required because every test that imports a deleted function will fail until rewritten (per the plan's build_notes), and to cover the verification gaps listed above.</next_steps>
</implement_report>
