<brainstorm_report>
  <meta project="fmri-first-level-proc" mode="brainstorm" timestamp="2026-10-08T06:30:17" status="interim" />

  <resume_point>
    INTERIM REPORT. The v4.0.0 brainstorm is paused at report generation. All topics T1-T12, the restart-safety gaps G1-G4 and the Pre-Report
    Audit (pass 1: A1-A4; pass 2: P2-1, P2-2; pass 3: P3-1; pass 4 = 4-pass cap: P4-1, P4-2, user chose resolve-now) are locked; no audit item
    remains open. Next session: re-enter /brainstorm with this report plus the two prior reports below as inputs, then (1) generate the final
    consolidated report (T1-T11 from the prior reports + every lock below + the amendment ledger in topic AMEND + a consolidated enumerated
    doc-item list per T12d(2) + the two orchestrator report item lists), (2) run the exit sequence, (3) write the two orchestrator reports.
  </resume_point>

  <context_files>
    <file path="~/.claude/projects/-Volumes-Backup-Plus-Yale-Research-Faculty-projects-fmri-first-level-proc/brainstorm_history/fmri-first-level-proc_brainstorm_20261005_060843.md" relevance="Locked T1-T11 (multi-run input, run boundaries, DOF, trial survival, frozen names, closed schema, ledger wiring, per-stage hashing table)" />
    <file path="~/.claude/projects/-Volumes-Backup-Plus-Yale-Research-Faculty-projects-fmri-first-level-proc/brainstorm_history/fmri-first-level-proc_brainstorm_20261006_191039.md" relevance="Locked T11-b, T11-c and later T1-T11 refinements" />
    <file path="fmri_first_level_proc/bids.py" relevance="discover_inputs (lexical sort L92, slot tables L156-172, matches[0] L202), unused output helpers removed by P2-1" />
    <file path="fmri_first_level_proc/first_level_config.py" relevance="GLOBAL_ONLY_KEYS L77, discovery merge L759-783, mandatory-slot check L785-807" />
    <file path="fmri_first_level_proc/first_level_utils.py" relevance="write_qc_summary OSError swallow L1536-1537, validate_onset_file_format L480-507, resampled template name L1271-1273" />
    <file path="fmri_first_level_proc/rest_conn_first_level.py" relevance="_sequenced_intermediates naming L235, positional run{i+1} indexing L718" />
    <file path="fmri_first_level_proc/run_first_level.py" relevance="Deprecated run-first-level alias removed by A2" />
    <file path="fmri_first_level_proc/exceptions.py" relevance="ToolVersionError docstring says 'does not match the lockfile pin' (doc item: change to minimum wording)" />
    <file path="pyproject.toml" relevance="Version, dependencies, console scripts (A2, A3)" />
    <file path="environment.yaml" relevance="python>=3.8, missing packaging (A3)" />
    <file path="ABCD_fmri_orchestrator_S3 (sibling project)" relevance="Orchestrator items: G4(5), A1(8), A4, T12e AI-011" />
    <file path="fmri-proc-orchestrator (sibling project)" relevance="Orchestrator items: G4(5), A1(8), A4" />
  </context_files>

  <topics>
    <topic id="T11b" title="Intermediate vs final outputs in FirstLevelResult">
      <summary>Split of FirstLevelResult file lists into final products and intermediates, with a per-file classification table.</summary>
      <research>Codebase enumeration of every file each pipeline leaves in out_dir; PV 3/3 concerns (enumeration gaps only), folded in.</research>
      <approaches>
        <approach id="A1" label="output_files + intermediate_files lists" feasibility="high" risk="low">
          <description>Two disjoint string lists; no typed record schema, no on-disk manifest.</description>
          <pros>Minimal API change; contract-testable.</pros>
          <cons>Reclassification of PSC/mean/censor/motion files is breaking.</cons>
        </approach>
      </approaches>
      <decision status="decided" chosen="A1">
        T11b-design: Option A: output_files = final products only; new FirstLevelResult.intermediate_files: list[str] for every other file the
        analysis leaves on disk. Staging dirs and in-stage-deleted temp files (e.g. _zconv_tmp) in neither list. No typed record schema, no
        on-disk manifest. Contract test: every analysis-produced file in out_dir (recursive walk, incl. the sequenced-intermediates run
        directories) appears in exactly one list; lists disjoint; CLI --log-file excluded. Revisions: (1) task_act
        {extract_out_file_pre}_{stat}_bucket.nii.gz + _{stat}_index.json are final; (2) task_conn {pre}_concat_LSS.1d is final; (3) recursive
        walk; (4) log file excluded. User approved 2026-10-07.
        T11b-table (approved 2026-10-07): FINAL: qc_summary.json; min_outlier_epi (all); raw_ptseries + raw_psc_ptseries (rest: run{N});
        task_act concat_bucket_stats, concat_bucket_resids, bucket_stats_index.json, {ext}_{stat}_bucket.nii.gz, {ext}_{stat}_index.json,
        {ext}_{stat}_parcellated.csv, {ext}_resids.csv; task_conn concat_LSS.nii.gz, concat_LSS.1d, concat_bseries_{cond}.nii.gz,
        concat_bseries_dmat.x1D, {ext}_pbseries_{cond}.csv, {conn}_{cond}_{corr|fishZ|pcorr|pcorr_fishZ}_mat.txt|.nii.gz + contrasts; rest_conn
        concat_residual_dtseries, run{N}_residual_dtseries (keep_run_res_dtseries), {ext}_residual_ptseries.csv, {conn}_* connectivity.
        _s{N}mm siblings inherit class. INTERMEDIATE: ledger.jsonl; psc+mean volumes; concat_scan, run_intersect_mask, resampled template,
        smoothing mask, smoothed per-run inputs; onset txt, beta_onsets, preflight_dmat; censor.1D + 1d_tool side files, motion_prepared,
        notch/interp/bp .1D, deriv.txt; connectivity-feed series; sequenced intermediates when kept. Catch-all: unlisted AFNI side file =
        intermediate except a design matrix of a final model output = final. Both lists retained on disk; only staging dirs and in-stage temp
        files are not kept. (1) PSC/mean/censor/motion reclassification is breaking: T12 release note + INPUT_SPEC 490-531 rewrite; (2)
        min_outlier_epi final, counting is the orchestrator's call (AI-011 note); (3) explicit conn patterns; (4) fix INPUT_SPEC:501 to the code
        name _{stat}_parcellated.csv in T12 docs.
      </decision>
    </topic>

    <topic id="T12a" title="Release version">
      <summary>Next release number.</summary>
      <research>SemVer 2.0.0; PV 2/3 verified, 1 concerns.</research>
      <approaches><approach id="A1" label="4.0.0 major" feasibility="high" risk="low"><description>Breaking changes require a major.</description><pros>SemVer-correct.</pros><cons>Orchestrators must re-pin.</cons></approach></approaches>
      <decision status="decided" chosen="A1">Release version 4.0.0 (SemVer major), not 3.2.0; __version__ and pyproject version = 4.0.0. Numerical-output changes (polort/DOF, zero handling) listed in release notes as result-changing. Approved 2026-10-07.</decision>
    </topic>

    <topic id="T12b" title="schema_version policy">
      <summary>Meaning and value of ResolvedConfig.schema_version.</summary>
      <research>Codebase: first_level_config.py:619 and test fixtures.</research>
      <approaches><approach id="A1" label="MAJOR.MINOR.0 of last schema change" feasibility="high" risk="low"><description>Version tied to the package release that last changed the schema.</description><pros>Deterministic.</pros><cons>Fixture updates.</cons></approach></approaches>
      <decision status="decided" chosen="A1">schema_version='4.0.0'. Policy: schema_version = MAJOR.MINOR.0 of the package release in which the config schema (ResolvedConfig fields AND YAML validation rules) last changed; removal/rename/meaning change/validation tightening are breaking and ship only in a package major; additions bump minor at the package minor that adds them; patch always 0. Policy stated in ResolvedConfig docstring (replacing 'additive-growth') and newly added to INPUT_SPEC. Update first_level_config.py:619 and test fixtures (conftest.py:96,142,185; test_exceptions.py; test_runtime.py; test_checkpoint.py). Keep field. Approved 2026-10-07.</decision>
    </topic>

    <topic id="T12c" title="CHANGELOG">
      <summary>Release-notes vehicle.</summary>
      <research>Keep a Changelog 1.1.0; PV 3/3 verified.</research>
      <approaches><approach id="A1" label="CHANGELOG.md, Keep a Changelog 1.1.0" feasibility="high" risk="low"><description>Root CHANGELOG reused as GitHub release body.</description><pros>Standard.</pros><cons>None material.</cons></approach></approaches>
      <decision status="decided" chosen="A1">CHANGELOG.md at repo root, Keep a Changelog 1.1.0 (newest first, ISO dates, Added/Changed/Deprecated/Removed/Fixed/Security), whitelisted in .gitignore; empty [Unreleased] section at top; 4.0.0 entry opens with 'Breaking changes and migration' (closed schema, output_files/intermediate_files, remove_previous ledger scoping, removed cross-analysis raw-ptseries reuse, smoothing moved in, lockfile 2.0.0 minimums) and 'Changes that affect numerical results' (rest_conn polort/DOF, zero-exclusion default + 3dROIstats/1ddot parcellated backend, unscaled rest_conn raw ptseries); no back-fill, one line pointing to tags v2.3.0-v3.1.0; 4.0.0 section reused verbatim as GitHub v4.0.0 release body. Approved 2026-10-07.</decision>
    </topic>

    <topic id="T12d" title="Documentation process and drift tests">
      <summary>When and how docs are written; contract tests against drift.</summary>
      <research>Codebase review of README, INPUT_SPEC, docstrings.</research>
      <approaches><approach id="A1" label="Code-adjacent docs in /implement, prose docs in one /document pass" feasibility="high" risk="low"><description>Split by proximity to code.</description><pros>Docs match final behavior.</pros><cons>Requires consolidated doc-item list.</cons></approach></approaches>
      <decision status="decided" chosen="A1">(1) code-adjacent docs (module OUTPUTS docstrings, function docstrings, example_config.yaml, tools.lock.yaml) updated in the same /implement change as the behavior. (2) README, INPUT_SPEC, CHANGELOG written in one /document pass after the 4.0.0 suite passes, from a consolidated enumerated doc-item list in the final brainstorm report. (3) drift contract tests: (a) per analysis type, keys tabulated in INPUT_SPEC == closed-schema accepted keys incl. nested as dotted names; INPUT_SPEC restructured so every key (incl. nested) has a table row, YAML blocks illustrative only; (b) every T8 frozen-name constant and T11b final-output pattern appears verbatim in INPUT_SPEC Output Files. (4) closed schema (T9) exposes an introspectable module-level per-type allowed-key set incl. nested; filenames as T8 constants; tests written after these land. Approved 2026-10-07.</decision>
    </topic>

    <topic id="T12e" title="Events file formats">
      <summary>Legacy CSV timing format status.</summary>
      <research>Orchestrator audit: fmri-proc-orchestrator writes tab BIDS *_adjusted_events.tsv (seam2.py:191-248); ABCD writes per-run tab BIDS {run_prefix}_timing.tsv (orchestrate_first_level.py:678); ABCD pre-v4.0 sessions have comma CONDITION *_timing.csv.</research>
      <approaches><approach id="A1" label="Option C: format-agnostic reader indefinitely" feasibility="high" risk="low"><description>Both schemes and both delimiters supported permanently.</description><pros>No deprecation stub.</pros><cons>Two schemes to test.</cons></approach></approaches>
      <decision status="decided" chosen="A1">(1) delimiter by trial-parse of header with tab and comma; accept the one yielding a recognized column set; both/neither -> InputError naming file + columns found under each. (2) BIDS onset/duration/trial_type precedence, else CONDITION/ONSET/DURATION mapped to BIDS. (3) remove EVENTS_LEGACY warning + 4.0.0 promise; no 'legacy/deprecated' wording in docstring, README, INPUT_SPEC (incl. cond_labels/cond_beta_labels rows), example_config comments; document schemes x delimiters as orthogonal, equally supported. (4) BIDS discovery unchanged (*_events.tsv only); explicit task_timing_path any combination. (5) keep example_subj.timing.csv. (6) release note: removal withdrawn (non-breaking). AI-011: ABCD README:262 + INPUT_SPEC:424 removal statement must be corrected. EVENTS_LEGACY tests updated at /test. Approved 2026-10-07.</decision>
    </topic>

    <topic id="T12f" title="Version provenance and enforcement">
      <summary>Tool-version probing, provenance, hashing, and minimum-version policy.</summary>
      <research>AFNI forum receipt t/7286 verified; PV 0/3 verified for T12f-min (AFNI exact-pin concern; user kept minimums with warning mitigation).</research>
      <approaches><approach id="A1" label="Minimum versions + validated version + warning" feasibility="high" risk="med"><description>Enforce minimums; warn when installed differs from validated.</description><pros>Installable across environments.</pros><cons>AFNI numerics may drift above minimum; mitigated by UNVALIDATED_VERSION warning and provenance.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        T12f: (1) always attempt the AFNI version probe [bypass clauses superseded by T12h]. (2) qc_summary.json gains provenance block:
        package_version, schema_version, afni_version, python_version, numpy_version, pandas_version. (3) all five versions (package, AFNI,
        Python, numpy, pandas) in every stage hash and recorded in every ledger entry; any change reruns all. (5) docs: upgrade invalidates
        ledger; numerics-changing releases must bump package version. Amendment (user): enforcement changes from exact pins to MINIMUM versions
        for AFNI, Python, numpy, pandas (supersedes the 2026-08-18 exact AFNI pin).
        T12f-min: (1) tools.lock.yaml records per tool {minimum (enforced, ToolVersionError if below), validated (version the suite passed
        on)}; lockfile_version 2.0.0. (2) installed != validated -> medium graded warning UNVALIDATED_VERSION + recorded in provenance
        [bypass retention superseded by T12h]. (3) Python minimum 3.12, validated 3.14. (4) numpy/pandas minimum = validated = versions
        installed when the 4.0.0 suite passes; no upper bounds anywhere. (5) add 'packaging' to pyproject dependencies; used only for
        numpy/pandas PEP 440 comparison via packaging.version.Version (AFNI via _parse_afni_version int tuple; Python via sys.version_info).
        (6) contract test: tools.lock.yaml, pyproject.toml, environment.yaml state identical minimums. Approved 2026-10-07.
      </decision>
    </topic>

    <topic id="T12g" title="Runtime check function and lockfile packaging">
      <summary>Where the lockfile lives and when version checks run.</summary>
      <research>Codebase: runtime.py, importlib.resources.</research>
      <approaches><approach id="A1" label="Packaged lockfile + single runtime-check function" feasibility="high" risk="low"><description>Lockfile as package data; one check per run().</description><pros>Works under pip install.</pros><cons>Reverses v3.0.0 T2/A1 placement.</cons></approach></approaches>
      <decision status="decided" chosen="A1">(1) lockfile moves to fmri_first_level_proc/tools.lock.yaml as package data (pyproject), read via importlib.resources, .gitignore whitelist updated; deliberately reverses v3.0.0 T2/A1 (premise changed: minimums + warning, not exact pin). (2) one runtime-check function: reads lockfile, runs preflight_tool_environments, probes AFNI/Python/numpy/pandas; ONLY probes cached per process; minimum enforcement + UNVALIDATED_VERSION warning re-evaluated every run() call (warning accumulator is cleared per run). (3) called from every pipeline run() and CLI main(); sole source for provenance block and hash version components. (4) [superseded by T12h]. (5) cache-reset hook for tests. (6) per-worker re-probe accepted. Restart-safety gaps raised here are resolved by G1-G4. Approved 2026-10-07.</decision>
    </topic>

    <topic id="T12h" title="Remove version-check bypasses">
      <summary>No-stubs release policy applied to PLACEHOLDER and absent-lockfile bypasses.</summary>
      <research>Codebase: runtime.py:208-217.</research>
      <approaches><approach id="A1" label="Remove both bypasses" feasibility="high" risk="low"><description>Version checks always enforced.</description><pros>No stubs in the release.</pros><cons>Tests needing isolation must mock the AFNI probe.</cons></approach></approaches>
      <decision status="decided" chosen="A1">(1) delete PLACEHOLDER handling; add AFNI-pin format validation mirroring the Python-pin check (runtime.py:208-217) -> ToolUnavailableError. (2) delete absent-lockfile bypass + LOCKFILE_ABSENT; missing/unparseable lockfile -> ToolUnavailableError naming resource path; sequenced in /implement after T12g(1) packaging; CHANGELOG breaking entry. (3) AFNI version undeterminable always fatal; T12f null afni_version and 'unknown' hash token never built. (4) delete bypass tests; refactor tests using afni='PLACEHOLDER' as isolation sentinel (e.g. test_python_field_absent_skips_check) to mock the AFNI probe; add tests: non-version AFNI value, missing lockfile, unprobeable AFNI -> ToolUnavailableError. Supersedes T12g(4) and T12f(1) bypass clauses. Approved 2026-10-07.</decision>
    </topic>

    <topic id="G1" title="Result lists assembled from the ledger">
      <summary>output_files/intermediate_files must be complete on partial reruns.</summary>
      <research>Codebase: checkpoint.py ledger.</research>
      <approaches><approach id="A1" label="Ledger-derived assembly, ledger_format 2" feasibility="high" risk="low"><description>Lists built from latest valid ledger records of every current-DAG stage.</description><pros>Identical lists for reuse and rerun.</pros><cons>Ledger format bump.</cons></approach></approaches>
      <decision status="decided" chosen="A1">(1) ledger entry replaces output_files:list[str] with outputs:[{path,class:final|intermediate}] and carries ledger_format:2. (2) end of successful run(): output_files/intermediate_files = union over every stage in current DAG of latest valid ledger entry outputs (executed or reused) + always-run outputs [source per G3(6)] + ledger file as intermediate. (3) never assembled from executed code paths. (4) unparseable or missing/unknown ledger_format lines -> stage reruns + medium graded warning LEDGER_ENTRY_UNREADABLE naming line numbers (no silent skip). (5) tests: full-reuse rerun identical lists; partial rerun (downstream-only field changed) identical lists; old-format ledger line -> warning + rerun. auto_reconstruct_ledger deletion and missing-output invalidation already locked in T11-optA. Approved 2026-10-07.</decision>
    </topic>

    <topic id="G2" title="Retirement sweep for orphaned outputs">
      <summary>Outputs no longer produced after a config change (e.g. _s6mm after fwhm 8) must be removed.</summary>
      <research>PV 0/3 verified, 3/3 concerns, all folded in.</research>
      <approaches><approach id="A1" label="Ledger-history sweep with independent expected-path cross-check" feasibility="high" risk="med"><description>Delete only ledger-recorded paths that are neither current nor expected.</description><pros>Never touches user files.</pros><cons>Requires full-history reader.</cons></approach></approaches>
      <decision status="decided" chosen="A1">Retirement sweep at end of every successful run(). (1) new full-history ledger reader returning every record; existing last-writer-wins read_ledger kept for reuse decisions. (2) independent cross-check: compute expected-path set from current config alone (no ledger) [extended by A1(5)]; every expected path existing on disk must be in output_files/intermediate_files, else internal error (GuardError) raised before any deletion. (3) delete only paths that are in this analysis ledger history AND not in current lists AND not in expected-path set; T8 frozen names never deleted; each deletion logged INFO, listed in qc_summary.json retired_outputs, recorded in ledger. (4) deletion failure -> high graded warning RETIREMENT_FAILED (status warning), retried next run; not an error. (5) tests: fwhm 6->8 retires _s6mm; smoothing disabled retires all smoothed; condition removed retires its outputs; user file never touched; reused-stage outputs never retired; partial rest_conn per-run rerun keeps other runs; deliberately omitted current path raises before deletion. Approved 2026-10-07.</decision>
    </topic>

    <topic id="G3" title="Uniform write protocol">
      <summary>Ledger must record only successfully written and validated files; always-run files must be recorded for cleanup.</summary>
      <research>Revised after user challenge (append only after a successful write); PV round 2: 1 verified, 2 concerns, folded in.</research>
      <approaches><approach id="A1" label="Stage, validate, record, replace, complete" feasibility="high" risk="low"><description>Every file written through staging with validation before any ledger record.</description><pros>Crash-safe; no record of corrupt output.</pros><cons>Validation cost per file.</cons></approach></approaches>
      <decision status="decided" chosen="A1">Uniform write protocol for every file (ledgered stages and always-run steps). (1) write into the staging directory [name per G4(2)] -> validate -> only then append+fsync staged record {record_type:staged, step, outputs:[{path,class}], ledger_format:2} -> os.replace into out_dir -> ledgered stages then append completion entry (sole reuse gate). (2) validation by producer: .nii.gz full gzip decompress + 3dinfo grid check vs scan grid (and nvols where known); Python-written text (onsets, extracted CSVs, qc_summary.json) read back byte-equal to intended string; AFNI-written text (censor/enorm .1D, .x1D, 1ddot/3dROIstats outputs) parsed with package reader + row/col check where known (censor rows = total TRs; conn matrices NxN). Delete validate_onset_file_format (first_level_utils.py:480-507). (3) always-run steps append staged record only when path set differs from latest; cleanup-only, not content integrity (docstring says so). (4) write_qc_summary stops swallowing OSError (first_level_utils.py:1536-1537). (5) remove_previous deletes every existing path in any staged/completion record of full history + all own staging dirs, ledger file last; failed deletion raises. (6) G1 assembly: always-run paths from each current step latest staged record (validity = validated this run); listed path missing or in more than one step -> GuardError. (7) G2 sweep reads full history of staged+completion records. (8) tests: crash after staged record before move; crash after move before completion then config change retires; validation failure leaves no record/file; truncated .gz/.1D/.csv/.x1D raise; wrong-grid NIfTI raises; unchanged rerun appends no always-run records; A->B->A lists; remove_previous complete + user file untouched; interrupted remove_previous completes; qc write failure raises. Approved 2026-10-07.</decision>
    </topic>

    <topic id="G4" title="Refuse to run over unrecorded files">
      <summary>Upgrading over a 3.1.0 out_dir (no ledger) would leave untracked files.</summary>
      <research>PV 1 verified, 2 concerns, folded in. Both orchestrators checked.</research>
      <approaches><approach id="A1" label="InputError on unrecorded prefixed files; naming invariant" feasibility="high" risk="low"><description>Detect, never auto-delete.</description><pros>No silent mixing of versions.</pros><cons>Migration step for users.</cons></approach></approaches>
      <decision status="decided" chosen="A1">(1) at run() start, before remove_previous and any write, if this analysis ledger is absent: collect out_dir entries (recursive into matching dirs) starting with {out_file_pre}_/{extract_out_file_pre}_/{conn_out_file_pre}_ plus the two pre-4.0.0 unprefixed names ({template}_resampled.nii.gz per configured template; _sequenced_intermediates/), excluding the CLI log file and paths recorded in other ledger_format-2 ledgers in out_dir; any remaining -> InputError before any write (count, first 20 paths, statement that no ledger for this analysis records them, e.g. earlier version or deleted ledger; remove_previous cannot remove them; use an empty out_dir or remove the listed paths); never auto-delete. (2) naming invariant: every package-created path in out_dir starts with an analysis prefix; _sequenced_intermediates -> {out_file_pre}_sequenced_intermediates/run{N}/; staging -> .staging_{out_file_pre}_{step}/; staging cleanup + remove_previous touch only own; contract test. (3) CHANGELOG Breaking changes and migration + README/INPUT_SPEC. (4) tests: 3.1.0-style dir incl only-unprefixed-template / only-_sequenced_intermediates -> InputError nothing written; empty dir runs; shared out_dir with string-prefix-overlapping prefixes no error, no cross staging/sequenced interference; prefixed log file / unprefixed user file no error; naming contract test. (5) orchestrator items: see topic ORCH. Approved 2026-10-07.</decision>
    </topic>

    <topic id="A1" title="Run identity by label value">
      <summary>Run numbers keep their true values; gaps stay visible; never renumbered, never list position.</summary>
      <research>PV 0/3 verified, 3/3 concerns folded in; user rejected renumbering and positional identity (runs 1, 3, 4 must stay 1, 3, 4).</research>
      <approaches><approach id="A1" label="Option A: integer label identity, label required" feasibility="high" risk="low"><description>Labels from run_labels, BIDS run- entity, or Mode A basename; no default.</description><pros>Gaps preserved; no silent mislabeling.</pros><cons>Single-run configs must supply a label.</cons></approach></approaches>
      <decision status="decided" chosen="A1">(1) run identity = integer value of the run label, unpadded run{N} in filenames, QC, excluded_runs, ledger scope keys, warnings; never list position, never renumbered; concat offsets/-concat/-local_times rows from an internal label->offset map over surviving runs. (2) label source precedence: new closed-schema run_labels (unique non-negative ints aligned with scan_paths (Mode A) or run_lengths (Mode B); length 1 for single scan) > BIDS discovery run- entity > Mode A run- entity parsed from scan basename ((^|_)run-(\d+)(_|\.)); Mode B only run_labels; no label (incl K=1) -> ConfigError. (3) duplicate labels -> ConfigError; Mode A per-run input filename run- entity != label -> InputError. (4) qc_summary excluded_runs [{run, reason}], surviving runs by label. (5) amendments: see topic AMEND. (6) run_labels in INPUT_SPEC (drift test) + CHANGELOG breaking. (7) tests: labels [1,3,4] -> run1/run3/run4 + QC indices {1,3,4}; exclude run3 -> excluded_runs, no run3 outputs, only stale run3 retired; label/filename mismatch InputError; duplicates ConfigError; unlabeled single run ConfigError; BIDS labels used; condition below floor retires stale outputs incl onsets; unchanged config expected set == lists. (8) orchestrator items: see topic ORCH. Approved 2026-10-07.</decision>
    </topic>

    <topic id="A2" title="Remove the run-first-level CLI alias">
      <summary>Deprecated alias conflicts with the no-stubs release policy.</summary>
      <research>PV 1 verified, 2 concerns folded in; neither orchestrator uses the alias.</research>
      <approaches><approach id="A1" label="Remove entirely in 4.0.0" feasibility="high" risk="low"><description>Single console script.</description><pros>No deprecated code shipped.</pros><cons>Breaking for alias users.</cons></approach></approaches>
      <decision status="decided" chosen="A1">(1) delete pyproject [project.scripts] run-first-level entry; delete run_first_level.py _main_deprecated (L219-221), CLI_DEPRECATED branch (L131-136), main() cli_name param; update docstrings L39-41, L105-106; remove alias text README:47, INPUT_SPEC:607; example_config.yaml:6-8 -> fmri-first-level-proc. (2) CHANGELOG Breaking changes and migration: run-first-level removed. (3) tests: [project.scripts] exactly one entry fmri-first-level-proc -> fmri_first_level_proc.run_first_level:main; neither CLI_DEPRECATED nor run-first-level occurs in package source, README, INPUT_SPEC, example_config.yaml. Historical .aid/ reports untouched. Approved 2026-10-07.</decision>
    </topic>

    <topic id="A3" title="environment.yaml and pyproject.toml dependencies">
      <summary>environment.yaml states python>=3.8 and lacks packaging.</summary>
      <research>PV 1 verified, 2 concerns minor.</research>
      <approaches><approach id="A1" label="Align both files with lockfile minimums" feasibility="high" risk="low"><description>Contract-tested parity.</description><pros>No drift.</pros><cons>None material.</cons></approach></approaches>
      <decision status="decided" chosen="A1">(1) environment.yaml: python>=3.12; numpy/pandas >= lockfile minimums; add packaging; keep pyyaml; keep AFNI-installed-separately comment. (2) pyproject.toml deps: numpy/pandas >= lockfile minimums; add packaging; keep pyyaml; requires-python >=3.12; packaging and pyyaml carry no minimum (packaging.version.Version used; parse() not used). (3) extend the T12f-min(6) contract test: package-name sets in pyproject deps and environment.yaml deps equal (excluding python, pip); explicit name map added only if a future dependency has a different conda name. Approved 2026-10-07.</decision>
    </topic>

    <topic id="A4" title="Orchestrator version references">
      <summary>Orchestrators reference 3.2.0, which will never exist.</summary>
      <research>PV 1 verified, 2 concerns folded in.</research>
      <approaches><approach id="A1" label="Re-pin to 4.0.0 with next-major cap" feasibility="high" risk="low"><description>Orchestrator report items only.</description><pros>Correct install target.</pros><cons>Lands only after publish.</cons></approach></approaches>
      <decision status="decided" chosen="A1">Orchestrator report items only (see topic ORCH). No change to the first-level package. Approved 2026-10-07.</decision>
    </topic>

    <topic id="P2-1" title="Remove unused BIDS output helpers">
      <summary>T8 deferred removal of unused bids.py helpers to a later pass, contrary to the no-deferred-work policy.</summary>
      <research>Zero call sites in the package; not in __all__; neither orchestrator imports fmri_first_level_proc.bids (fmri-proc-orchestrator has its own write_dataset_description). PV 1/3 verified, 2/3 minor concerns folded in.</research>
      <approaches><approach id="A1" label="Delete in 4.0.0" feasibility="high" risk="low"><description>Remove helpers and their tests.</description><pros>No dead code shipped.</pros><cons>None material.</cons></approach></approaches>
      <decision status="decided" chosen="A1">(1) delete from bids.py build_bids_output_path(), write_dataset_description(), _ENTITY_ORDER, the json import and the sanitize_filename_label import (still used by task_conn_first_level.py:492, so only the bids.py import goes), and the module-docstring text for the two helpers; keep discover_inputs and private helpers; in tests/test_bids.py delete TestBuildBidsOutputPath and TestWriteDatasetDescription plus imports left unused (the two names, json, pytest if unused). (2) CHANGELOG 4.0.0 'Removed' entry; supersedes T8 'removal deferred to a future /clean pass'. (3) test: fmri_first_level_proc.bids has no attribute build_bids_output_path or write_dataset_description. Approved 2026-10-07.</decision>
    </topic>

    <topic id="P2-2" title="BIDS discovery run handling">
      <summary>Lexical sort misorders run-10; BIDS allows omitting run- for a single run; ambiguous matches unspecified.</summary>
      <research>PV 0/3 verified, 3/3 identical minor concerns folded in. Scope narrowed by P3-1(1) to per-run slots.</research>
      <approaches><approach id="A1" label="Integer ordering, explicit labels, InputError on ambiguity" feasibility="high" risk="low"><description>No inferred default label.</description><pros>Consistent with A1.</pros><cons>Single unlabeled runs need run_labels.</cons></approach></approaches>
      <decision status="decided" chosen="A1">(1) discovered runs in every per-run slot ordered by integer run- value, never lexical sort (bids.py:92 sorted(glob) bug). (2) slot files with no run- entity: run label comes from run_labels, which must have exactly one entry; run_labels absent -> ConfigError naming run_labels; no default label ever inferred. (3) InputError listing conflicting files when a slot mixes files with and without run-, has two or more unlabeled files, or has two files with the same run label (e.g. two space- variants). (4) run_labels set + discovered files carry run-: run_labels must equal discovered labels in integer order, else InputError (same agreement rule as A1(3)). (5) INPUT_SPECIFICATION.md + README.md. (6) tests: run-1/run-2/run-10 ordered 1,2,10; single unlabeled + run_labels [1] -> run1; single unlabeled without run_labels -> ConfigError; each of the three ambiguity cases -> InputError; run_labels disagreeing with discovered labels -> InputError. Approved 2026-10-07.</decision>
    </topic>

    <topic id="P3-1" title="Per-run slot scope and cross-slot run agreement">
      <summary>P2-2 rules stated for every slot; explicit and discovered slots not cross-checked.</summary>
      <research>PV 2/3 verified, 1/3 concerns incl. one major (cross-directory collision), addressed. Template rules (points 1-2) superseded by P4-2(A).</research>
      <approaches><approach id="A1" label="Per-run scope + label-set agreement" feasibility="high" risk="low"><description>All populated per-run slots carry the scan label set.</description><pros>Catches mixed explicit/discovered mismatches.</pros><cons>GS must be all-or-none.</cons></approach></approaches>
      <decision status="decided" chosen="A1">(1) P2-2 rules apply only to per-run slots (scan, motion/confounds, events, CSF, WM, GS). [Template-slot text superseded: P4-2(A) removes the template from discovery.] (2) [Superseded by P4-2(A).] Cross-directory precedence for per-run slots unchanged from v3.0.0 (first directory in derivatives_dirs wins, medium DISCOVERY_COLLISION warning). (3) after explicit config and discovered values merge slot by slot, every populated per-run slot must carry exactly the scan slot's run-label set (explicit-slot labels per A1(2) precedence), else InputError naming slot and missing/extra labels; optional GS all-or-none (partial GS = run-varying nuisance model). Applies in Mode A only (P4-2(B3)). (4) tests: explicit scans runs 1,3 + discovered motion 1,2,3 -> InputError naming motion and label 2; GS subset -> InputError. Approved 2026-10-07.</decision>
    </topic>

    <topic id="P4-1" title="run_labels in per-stage hash declarations">
      <summary>Stage table predates run_labels and identified rest_conn per-run stages by list position.</summary>
      <research>PV 0/3 verified, 3/3 concerns incl. one major (task-conn-beta-series omitted), folded in.</research>
      <approaches><approach id="A1" label="Declare run_labels wherever run structure is declared" feasibility="high" risk="low"><description>Label-keyed per-run stage declarations.</description><pros>No stale label-named reuse.</pros><cons>Relabel triggers full rerun (intended).</cons></approach></approaches>
      <decision status="decided" chosen="A1">Amends T11-table. (1) run_labels declared by every stage declaring scan_path, scan_paths or run_lengths: task-act-prep, task-act-raw-ptseries, task-act-glm, task-conn-prep, task-conn-raw-ptseries, task-conn-design-matrix, task-conn-beta-series, rest-conn-prep, rest-conn-raw-ptseries; rest-conn-residuals-concat inherits via union of component-stage fields. (2) rest-conn-residuals-run{N}: N = run label; declares the label value + scan/motion/CSF/WM/GS entries for that label (not n-th element). (3) rest-conn-concat derived list = ordered surviving run labels. (4) run_labels not exempt; existing declared-or-exempt contract test enforces. (5) test: change only run_labels -> declaring stages rerun, run{N} names for new labels, retirement sweep deletes old-label files. Relabel full rerun intended; label uniqueness per A1(3). Approved 2026-10-07.</decision>
    </topic>

    <topic id="P4-2" title="Template out of discovery; discovery with Mode B">
      <summary>Discovery searched for a subject- and task-specific dseg although template_path is global; order of mode checks vs discovery merge unspecified.</summary>
      <research>User correction: parcellation templates span subjects, sessions and runs. first_level_config.py:77 GLOBAL_ONLY_KEYS includes template_path ('shared ROI template for all analyses'). PV 2/3 verified, 1/3 minor concerns folded in. Neither orchestrator sets derivatives_dirs.</research>
      <approaches><approach id="A1" label="Global-only template; merge-then-validate" feasibility="high" risk="low"><description>Discovery covers per-run slots only; all mode checks on the merged result.</description><pros>Consistent with global template semantics; catches Mode B mixing.</pros><cons>Mode B gets no per-run discovery.</cons></approach></approaches>
      <decision status="decided" chosen="A1">(A) remove the template slot from BIDS discovery: dseg entry in both slot tables, DiscoveredInputs.template_path, first_level_config.py:782-783, template text in the discover_inputs docstring table and the DiscoveredInputs class docstring (bids.py:29-34), INPUT_SPECIFICATION.md:449; template_path only from the global config key (GLOBAL_ONLY_KEYS); CHANGELOG breaking; test: a dseg file in a subject func dir is never picked up. Supersedes P3-1 points 1-2 template rules. (B1) discover_inputs returns per-run lists for every per-run slot in all analysis types, never matches[0]; a single run = length-1 list; DiscoveredInputs docstring updated; CHANGELOG breaking. (B2) merge explicit+discovered first, then T1 mode checks (no singular/plural mixing; no run_lengths with per-run lists) and the Tier-3 mandatory-slot check (accepting either mode) run on the merged result; violation -> ConfigError naming conflicting fields; remedy: give every per-run input explicitly as a single file (Mode B), or remove run_lengths + singular fields so discovery supplies per-run files (Mode A); run_labels with discovered files allowed per P2-2(4). (B3) P3-1(3) cross-slot agreement applies in Mode A only; Mode B identity only from run_labels aligned with run_lengths. (B4) INPUT_SPEC + README: Mode B gets no per-run discovery. (B5) tests: explicit Mode B scan + discovered motion -> ConfigError naming both; run_lengths with all paths left to discovery -> ConfigError; Mode B all explicit + derivatives_dirs succeeds; single discovered run -> length-1 list. Approved 2026-10-08.</decision>
    </topic>

    <topic id="AMEND" title="Amendment ledger for earlier locked topics">
      <summary>Every place a later lock changes the text of an earlier lock; the final report must apply these.</summary>
      <research>Derived from the locks in this report and the two prior reports.</research>
      <approaches><approach id="A1" label="Apply amendments in the final consolidated report" feasibility="high" risk="low"><description>Earlier text is rewritten, not annotated.</description><pros>Single source of truth for /implement.</pros><cons>None.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        T1: Mode B "omitted run_lengths preserves v3.1.0 single-run behavior" superseded by A1(2): run_labels required, including K=1. T1 BIDS
        discovery pairing is specified by P2-2, P3-1(1,3) and P4-2(B).
        T3: rest_conn per-run names use the label even at K=1; task_act/task_conn K=1 names unchanged (A1(5)).
        T6: the internal event table stores run labels only; "with runs renumbered" removed (A1(5)).
        T8: "removal deferred to a future /clean pass" replaced by the P2-1 removal.
        T11 / T11-table: per-run stages and scope keys keyed by label (A1(5)); run_labels declarations per P4-1; staging directories named
        .staging_{out_file_pre}_{step}/ (G4(2)).
        T11b: _sequenced_intermediates/run{N}/ becomes {out_file_pre}_sequenced_intermediates/run{N}/, N = label (G4(2), A1).
        T12f: exact pins replaced by minimums (T12f amendment, T12f-min); T12f(1) bypass clauses superseded by T12h.
        T12f-min(2): "PLACEHOLDER/absent-lockfile bypasses retained" superseded by T12h.
        T12g(4): superseded by T12h. T12g open restart-safety gaps resolved by G1-G4.
        G1(2): always-run outputs sourced per G3(6).
        G2(2): expected-path set extended per A1(5) (config + surviving labels + surviving conditions, incl. task_act onset files; contrasts with a
        dropped condition not expected).
        P2-2: scope narrowed to per-run slots by P3-1(1).
        P3-1(1,2): template rules superseded by P4-2(A); "template glob keeps task- entity" moot.
      </decision>
    </topic>

    <topic id="ORCH" title="Orchestrator report items">
      <summary>Changes each sibling orchestrator must make; written as two separate orchestrator reports at session end.</summary>
      <research>Both orchestrators read under session-bound grants. Verified: neither sets derivatives_dirs (P2-2, P3-1, P4-2 impose no orchestrator change); neither imports fmri_first_level_proc.bids (P2-1 imposes no change).</research>
      <approaches><approach id="A1" label="Two orchestrator reports" feasibility="high" risk="low"><description>One report per orchestrator.</description><pros>Each project acts independently.</pros><cons>Must land after v4.0.0 publish.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        ABCD_fmri_orchestrator_S3:
        (G4) stop relying on remove_previous=True wholesale clear (orchestrator_utils.py:2945-2947, 3009); clear its own
        first_level_out/{analysis} directory itself when a clean slate is needed, and update the docstring; migration note that a reused 3.1.0
        out_dir raises InputError.
        (A1) pass run_labels explicitly (run_label at orchestrator_utils.py:1355 already embeds run-{n}).
        (A4) MIN_UPSTREAM_VERSION = '4.0.0' (orchestrator_utils.py:1160) + docstring L1168; every 'fmri_first_level_proc >= 3.2.0' reference ->
        4.0.0 (orchestrator_utils.py:1737, 1823, 2624, 2938; README:67, 197, 209, 215, 296, 377; INPUT_SPEC:56, 172, 211, 301, 461, 557, 577,
        724; example_orchestrator_config.yaml:64); test on the constant; environment.yaml:30 ->
        git+https://github.com/tjkeding/fmri-first-level-proc.git@v4.0.0 (canonical hyphenated name); verify_upstream_version also rejects
        versions at or above 5.0.0.
        (T12e, AI-011) correct the CSV-removal statement at README:262 and INPUT_SPEC:424 (removal withdrawn).
        (T11b-table, AI-011) min_outlier_epi is a final output; whether to count it is the orchestrator's call.
        fmri-proc-orchestrator:
        (G4) qc.py:99-104 first-glob-match -> per-analysis qc_summary from FirstLevelResult.output_files; reconcile hard-coded
        derivatives/fmri-first-level-proc (pipeline.py:273) with the user-configured out_dir; migration note that a reused 3.1.0 out_dir raises
        InputError.
        (A1) seam2.py _adapt_task concatenates without run_lengths/labels -> send per-run lists, or Mode B + run_lengths + run_labels; remove the
        run=1 default at bids.py:65 (int(entities.get('run', 1))); pipeline.py:240-241 adapter_result has no consumer found, confirm the
        adapter-to-first-level wiring.
        (A4) pyproject.toml:14 -> fmri-first-level-proc>=4.0.0,&lt;5; tools.lock.yaml -> lockfile 2.0.0 {minimum, validated}.
        Both: all items land only after v4.0.0 is published.
      </decision>
    </topic>
  </topics>

  <action_items>
    <item priority="P0" target_mode="brainstorm" description="Resume /brainstorm with this report and the two prior reports; generate the final consolidated report (T1-T11 + all locks here + AMEND applied + consolidated enumerated doc-item list per T12d(2), including the ToolVersionError docstring change from 'does not match the lockfile pin' to minimum-version wording); run the exit sequence; write the two orchestrator reports from topic ORCH." />
    <item priority="P0" target_mode="implement" description="After the final report: implement v4.0.0 per the consolidated spec (T1-T12, G1-G4, A1-A3, P2-1, P2-2, P3-1, P4-1, P4-2)." />
    <item priority="P1" target_mode="test" description="Design and run tests enumerated in each lock; drift contract tests per T12d(3)." />
  </action_items>

  <next_steps>Next session: /brainstorm resume for final report generation only (no open decisions). Then /implement plan from the final report, /test, /document (README, INPUT_SPEC, CHANGELOG per T12d(2)), publish v4.0.0, then the orchestrator changes.</next_steps>
</brainstorm_report>
