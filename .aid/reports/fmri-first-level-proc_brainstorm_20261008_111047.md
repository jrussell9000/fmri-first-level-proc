<brainstorm_report>
  <meta project="fmri-first-level-proc" mode="brainstorm" timestamp="2026-10-08T15:10:47Z" status="interim" />

  <resume_point>
    INTERIM REPORT. The v4.0.0 brainstorm is paused INSIDE the Pre-Report Audit of this session (a fresh audit run over this
    session's new locks; pass 4 = 4-pass cap reached; user chose "resolve now, one at a time"). Resume EXACTLY at the pending
    question in topic P4a below: the Agent Return Validation Gate recovery decision for the P4a proposal verification
    (recommended option (i): dispatch three fresh proposal-verification agents on the REVISED P4a; alternatives (ii) retry
    stricter, (iii) drop PV-1 slot UNVERIFIED, (iv) abort). After P4a locks: P4b (always-run step names, needs 3-agent PV),
    then P4c (_s{N}mm decimal formatting, formatting only), then FINAL (consolidated report), then the two orchestrator
    TODO files per ORCH-W, then the brainstorm exit sequence. The exit sequence has NOT been run; mode state is brainstorm.
    Inputs for the final report: this report plus fmri-first-level-proc_brainstorm_20261008_063017.md (T11b, T12a-h, G1-G4,
    A1-A4, P2-1, P2-2, P3-1, P4-1, P4-2, AMEND, ORCH), fmri-first-level-proc_brainstorm_20261006_191039.md (T11-raw,
    T11-demean, T11-polort, SMOOTH-ARCH, T11-psc, T11-nz, T11-lowbase, T11-rawdoc, T11-b, T11-c, amendments) and
    fmri-first-level-proc_brainstorm_20261005_060843.md (T1-T11), all in brainstorm_history.
  </resume_point>

  <context_files>
    <file path="brainstorm_history/fmri-first-level-proc_brainstorm_20261008_063017.md" relevance="Prior interim report; its locks carry forward unchanged except where amended below" />
    <file path="brainstorm_history/fmri-first-level-proc_brainstorm_20261006_191039.md" relevance="T11 sub-locks and SMOOTH-ARCH; amended below by KI-005, C1, C3, AUD-S" />
    <file path="brainstorm_history/fmri-first-level-proc_brainstorm_20261005_060843.md" relevance="T1-T11; amended below by C1-C6" />
    <file path="cr_history/ABCD_fmri_orchestrator_S3_cr_20261001_142121.md" relevance="Source CR; all upstream-facing findings (F2, F3b, F4, F5, F10b, D4, release) verified mapped to T1-T12" />
    <file path="fmri_first_level_proc/first_level_utils.py" relevance="seed_to_voxel_conn/parcellated_conn L1788-2029; GuardError parse sites L1236, L1355, L1362, L1427, L1430; gen_min_outlier_epi L1375-1444" />
    <file path="fmri_first_level_proc/runtime.py" relevance="_AFNI_BINARIES L15-31 (C1)" />
    <file path="fmri_first_level_proc/rest_conn_first_level.py" relevance="dead bandpass guard L169 (C5); qc_data L702-735 (AUD-Q); positional min-outlier label L664 (P4a)" />
    <file path="fmri_first_level_proc/task_conn_first_level.py" relevance="-x1D_stop -nobucket design-matrix call L274-275 (C2)" />
    <file path="fmri_first_level_proc/task_act_first_level.py" relevance="-bucket GLM call L243 (C2); min-outlier call L628 (P4a)" />
    <file path="fmri_first_level_proc/run_first_level.py" relevance="exception-to-exit-code mapping L203-216 (C4)" />
  </context_files>

  <topics>
    <topic id="SCOPE" title="Session finding: brainstorm was not finished">
      <summary>Re-investigation at session start showed the 2026-10-08 interim report's "no open decisions" claim was wrong.</summary>
      <research>CR report coverage verified complete; two apparently unanswered prompts (TRIALS_FEW, low-baseline) verified answered (T6b, T11-lowbase option A); multi-column HRF note closed by T5b. Open items found: KI-005 (cross-session state), lock contradictions C1-C6 missing from the amendment ledger, ORCH items O1-O5 and SMOOTH-ARCH items missing from the ORCH topic, orchestrator report destination.</research>
      <approaches><approach id="A1" label="Resolve one at a time" feasibility="high" risk="low"><description>Each item discussed and locked sequentially.</description><pros>No unreviewed decisions.</pros><cons>None.</cons></approach></approaches>
      <decision status="decided" chosen="A1">User confirmed the brainstorm was unfinished and directed one-at-a-time resolution. 2026-10-08.</decision>
    </topic>

    <topic id="ORCH-R" title="Restore orchestrator items O1-O5 and SMOOTH-ARCH items">
      <summary>Items locked 2026-10-02/05/06 but absent from every report's ORCH text; O1-O4 recovered from the 2026-10-05 session transcript.</summary>
      <research>Transcript recovery (0094b7ee, d734ee58 sessions).</research>
      <approaches><approach id="A1" label="Restore verbatim" feasibility="high" risk="low"><description>No new decision; carried forward.</description><pros>Complete orchestrator handoff.</pros><cons>None.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        Restore verbatim to the ORCH lists (alongside the 2026-10-08 ORCH items): O1 (from T9, ABCD) renderer orchestrator_utils.py:3019-3023
        replaces task-block paths wholesale, discarding template CSF_path/WM_path and never supplying per-run CSF_paths/WM_paths; supply
        per-run task tissue paths or reject templates that set them. O2 (from T9, ABCD) example_proc_config.yaml/proc_config_final.yaml task
        blocks mix scan_paths with CSF_path/WM_path: null (valid under null-as-absent; remove for clarity). O3 (from T9, ABCD) add an
        orchestrator test rendering a config through load_and_validate; F3a validate_proc_template legacy-key check becomes redundant but
        harmless. O4 (from T10, ABCD) make generated config paths absolute, then remove os.chdir(session_out) (orchestrate_first_level.py
        817-821, 913). O5 (T11-rawdoc, both) rest_conn _run{N}_raw_ptseries.csv keeps its name but holds unscaled values under default
        scale_to_psc true. SMOOTH-ARCH (ABCD) remove smoothing from code and config; collect _s{N}mm outputs when smoothing is enabled;
        the smoothing block lives in the first-level config template (proc_config_final.yaml). SMOOTH-ARCH (fmri-proc-orchestrator) remove
        smoothing (retires the 3dmerge -doall bug); collect _s{N}mm outputs. Approved 2026-10-08.
      </decision>
    </topic>

    <topic id="KI-005" title="Review of empirical checks run without prior approval (2026-10-06)">
      <summary>User review of four checks whose results fed locked decisions.</summary>
      <research>E1 real-data PSC audit, 24 sandbox runs: masked voxels with temporal mean &lt;= 0 max 1.33%, median 0.007% (fed T11-psc 25% gate). E2 AFNI 26.0.09 synthetic equivalence: 1ddot vs 3dNetCorr r within 4e-5, partial correlation 5e-5, capped atanh 4.4e-5, 3dTcorr1D vs 3dNetCorr seed maps 1.8e-4; v3.1.0 zero-excluding ROI series vs zero-including 3dNetCorr averaging differed up to 0.65 in r with 1% scattered zeros (fed T11-nz, SMOOTH-ARCH seed method). E3 synthetic: 3dAutomask dropped all 652 voxels of a low-signal region (fed automask ban). E4 one real run: 6.3% of masked voxels below 20% of brain-mask median baseline with about 74x typical PSC variance (fed planned T11-lowbase INPUT_SPEC text). PV: 1 verified, 2 concerns (2 major, resolved).</research>
      <approaches><approach id="A1" label="Retain locks; re-ground evidence; no re-runs" feasibility="high" risk="low"><description>Analytic justification, standing tests, qualitative docs.</description><pros>Documented behavior does not rest on unreviewed figures.</pros><cons>No independent replication of E1/E4.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        (1) T11-psc: keep the 25% gate; documented basis = half the expected fraction under demeaning (demeaned voxel means are zero up to
        rounding, sign arbitrary, about 50% at or below zero); no dataset percentages in package docs; this report records E1 as reviewed
        supporting evidence. (2) T11-nz and seed-to-voxel backends kept; contract tests on synthetic data in roi_zero_handling include mode vs
        3dNetCorr, absolute tolerance 1e-3, for r, partial correlation and Fisher Z (cap 4) matrices and seed-to-voxel r and Z maps
        (-ts_wb_corr/-ts_wb_Z); CHANGELOG cites the v3.1.0 0.65 r discrepancy as the fixed bug. (3) SMOOTH-ARCH data-derived mask and
        automask ban kept, justified analytically (input arrives brain-masked so its nonzero support is the correct mask; an
        intensity-threshold mask can only remove in-brain voxels; 3dBlurToFWHM zeros outside its mask); 652 not cited; integration test:
        after 3dBlurToFWHM -mask no in-mask voxel is zero and no out-of-mask voxel is nonzero. (4) T11-lowbase decision and both QC fields
        kept; INPUT_SPEC replaces the 6%/74x figures with a qualitative statement (voxelwise PSC amplifies noise in inverse proportion to a
        voxel's baseline); 20% labeled a reporting convention. (5) KI-005 closed, no re-runs. Approved 2026-10-08.
      </decision>
    </topic>

    <topic id="C1" title="Connectivity failure and null handling after 3dNetCorr removal">
      <summary>T6e specified rules in terms of 3dNetCorr, which SMOOTH-ARCH/T11-nz removed; seed-to-voxel handling was unspecified.</summary>
      <research>Code: warn-and-return blocks first_level_utils.py:1847-1851, 2008-2012; 3dTcorr1D -Fisher is unclipped (Inf at r = 1); 1ddot can abort on all-zero vectors. PV: 2 verified, 1 concerns (minor, folded in).</research>
      <approaches><approach id="A1" label="Re-derive T6e on the new backends" feasibility="high" risk="low"><description>Zero-variance null definition; explicit Z clip.</description><pros>Same contract, valid tools.</pros><cons>Amends SMOOTH-ARCH Z computation.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        Replaces T6e's 3dNetCorr clauses. (1) Nonzero exit of 3dROIstats, 1ddot, 3dTcorr1D or 3dcalc in seed_to_voxel_conn/parcellated_conn
        raises ToolExecutionError via the centralized wrapper; delete both warn-and-return blocks, format_netcorr_mat and netcc/INDIV
        handling. (2) Missing/invalid outputs caught by G3 validation (NIfTI decompress + grid; N x N matrices; 3dROIstats table rows = time
        points, columns = ROI labels). (3) Null series (both types) = extracted parcel or seed series (same 3dROIstats extraction, under
        roi_zero_handling) with zero temporal variance. (4) Parcellated r/Fisher Z: drop null-ROI columns before 1ddot; NaN in each null
        ROI's row and column incl. diagonal, placed by label; NULL_ROI high warning + qc_summary; partial correlation keeps the T6c rank gate
        on the full set (null ROI -&gt; PCORR_RANK_DEFICIENT). (5) Seed-to-voxel: null seed -&gt; SEED_NULL high; task_conn skips the condition
        (ModelError only if none yields a map); rest_conn ModelError; r via 3dTcorr1D -pearson; Z = atanh(r) in 3dcalc with |r| &lt;= 0.999329
        (|Z| &lt;= 4); -Fisher not used (explicit amendment to SMOOTH-ARCH); zero-variance target voxels written as 0 with in-mask count per
        map in qc_summary; KI-005 contract test compares Z where |r| &lt; 0.999329, cap checked separately. (6) _AFNI_BINARIES = 3dDeconvolve,
        3dTproject, 3dTstat, 3dBandpass, 3dROIstats, 3dresample, 3dinfo, 3dToutcount, 3dbucket, 3dcalc, 3dLSS, 3dTcat, 1d_tool.py,
        1dtranspose, 3dAttribute, 1ddot, 3dTcorr1D, 3dBlurToFWHM (3dNetCorr removed; test-only dependency); contract test: list equals the set
        of programs passed to run_afni_command. (7) Tests: null ROI NaN at correct labels and other entries equal the matrix without it; null
        seed skip (task_conn) / ModelError (rest_conn); mocked failure of each tool propagates ToolExecutionError; single-voxel seed inside
        the target gives Z = 4; zero-variance target voxel gives 0 and is counted. Approved 2026-10-08.
      </decision>
    </topic>

    <topic id="C2" title="AFNI working directory and .REML_cmd files">
      <summary>T10 cwd=out_dir conflicted with T11-optA/G3 staging cwd; unprefixed REML_cmd from -nobucket calls violated G4.</summary>
      <research>AFNI 26.0.09 (2026-10-02 tests): only 3dDeconvolve writes into cwd (3dDeconvolve.err, suppressed by AFNI_USE_ERROR_FILE=NO; 3dDeconvolve.REML_cmd with -nobucket; Decon.REML_cmd with no bucket option). task_conn design matrix uses -x1D_stop -nobucket (task_conn_first_level.py:274-275); task_act GLM uses -bucket (task_act_first_level.py:243). PV: 1 verified, 2 concerns (minor, folded in).</research>
      <approaches><approach id="A1" label="Staging cwd everywhere; prefix-rename REML_cmd" feasibility="high" risk="low"><description>Uniform with G3/G4.</description><pros>Naming invariant holds; nothing to process cwd.</pros><cons>Embedded staging paths in provenance text.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        Supersedes T10(2) cwd=out_dir and T10 "REML_cmd files remain in out_dir". (1) Every AFNI call that writes files (ledgered stages and
        always-run steps: task_act GLM, task_conn design matrix, T5 preflight, T7a dry run) runs with cwd = its step's staging dir
        .staging_{out_file_pre}_{step}/, prefixes into it; files reach out_dir only via G3; custom_hrf check keeps its TemporaryDirectory;
        AFNI_USE_ERROR_FILE=NO and logging of stderr "*+ WARNING" lines retained; the package writes nothing to the process cwd.
        (2) .REML_cmd: prefixed -&gt; promoted as intermediate; unprefixed (3dDeconvolve.REML_cmd, Decon.REML_cmd) renamed in staging to
        {out_file_pre}_{step}.REML_cmd then promoted as intermediate; validation = non-empty UTF-8 text containing "3dREMLfit"; more than one
        unprefixed REML_cmd in one staging dir -&gt; GuardError. (3) INPUT_SPEC: REML_cmd text and NIfTI AFNI history record staging paths
        (provenance only; the package never runs REML_cmd). (4) Tests: mocked calls receive their step staging cwd; process cwd gains no files;
        design-matrix REML_cmd lands as {out_file_pre}_task-conn-design-matrix.REML_cmd in intermediate_files; two unprefixed REML_cmd in one
        staging dir -&gt; GuardError. Approved 2026-10-08.
      </decision>
    </topic>

    <topic id="C3" title="T3 mask rationale and low-baseline QC applicability">
      <summary>T3's "data are demeaned" rationale is false (T11-demean); demeaned input is accepted when scale_to_psc is false.</summary>
      <research>T11-psc gate applies only when scale_to_psc is true (2026-10-06 transcript). max - min is invariant to an additive shift. PV: 1 verified, 2 concerns (minor).</research>
      <approaches>
        <approach id="A" label="Low-baseline QC only when scale_to_psc true" feasibility="high" risk="low"><description>Tie fields to PSC.</description><pros>Simple.</pros><cons>Loses dropout diagnostics without PSC.</cons></approach>
        <approach id="B" label="Low-baseline QC gated on the positive-baseline sentinel" feasibility="high" risk="low"><description>Fields present iff fewer than 25% of masked voxels have mean &lt;= 0.</description><pros>Keeps diagnostics; no division by near-zero median.</pros><cons>Partial offsets not detected.</cons></approach>
      </approaches>
      <decision status="decided" chosen="B">
        (1) T3 mask criterion unchanged (max &gt; min exact in every run, on the series entering the model; smoothing mask same criterion on
        unscaled input). (2) T3 rationale replaced: max &gt; min keeps exactly the voxels with non-constant signal in every run and holds for
        PSC-scaled, unscaled positive-baseline and demeaned input (demeaned input accepted only when scale_to_psc is false); a mean-positive
        criterion would drop every voxel of demeaned input. (3) Option B, explicit amendment to T11-lowbase: low_baseline fields emitted iff
        fewer than 25% of masked voxels have temporal mean &lt;= 0 (T11-psc sentinel applied regardless of scale_to_psc); otherwise null with a
        reason. (4) INPUT_SPEC: mask criterion; demeaned input accepted only with scale_to_psc false; null rule; the 25% sentinel catches full
        demeaning but not partial offsets. (5) Tests: demeaned + PSC off -&gt; mask keeps every non-constant voxel, fields null with reason;
        positive-baseline PSC off -&gt; fields present; PSC on -&gt; present. Approved 2026-10-08.
      </decision>
    </topic>

    <topic id="C4" title="T11-optA vs G3 reconciliation; exception classes for validation failures">
      <summary>G3 superseded T11-optA checks and remove_previous scope; G3 left the exception class unnamed.</summary>
      <research>CLI mapping run_first_level.py:203-216 (ToolExecutionError 4, GuardError 1, other 1). Existing GuardError on unparseable AFNI output at first_level_utils.py:1355, 1362 (3dROIstats), 1427, 1430 (3dToutcount). PV: 0 verified, 3 concerns (2 major, folded in).</research>
      <approaches><approach id="A1" label="Producer-based exception mapping" feasibility="high" risk="low"><description>AFNI-written -&gt; ToolExecutionError; Python-written -&gt; GuardError.</description><pros>Actionable exit codes; consistent with C1/T6e.</pros><cons>Exit-code change for four sites.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        (1) Consolidated T11-optA: write sequence = G3; a missing expected output is a validation failure; "invalid if a recorded output is
        missing" binds to completion entries (sole reuse gate; staged records are never evidence; remove_previous and the retirement sweep skip
        recorded paths that no longer exist); remove_previous = G3(5); NEW rule: a step's own leftover staging dir is deleted before any step
        (ledgered or always-run) runs; all recorded in the amendment ledger. (2) AFNI-written file validation failure -&gt; ToolExecutionError
        naming file, command + description, failed check (expected vs found); reclassify first_level_utils.py:1355, 1362, 1427, 1430 from
        GuardError to ToolExecutionError (exit 1 -&gt; 4), CHANGELOG. (3) Python-written file missing or not byte-equal -&gt; GuardError naming the
        file; in (2) and (3) nothing is recorded or moved. (4) OSError in write/replace/fsync/delete (write protocol, remove_previous) propagates
        unwrapped (exit 1); retirement failures stay RETIREMENT_FAILED; INPUT_SPEC exit-code table states all mappings. (5) Tests: each class
        gives its exception and exit code; injected OSError at os.replace exits 1 with no completion entry; completion entry with a missing
        output reruns; leftover always-run staging deleted before its step; unparseable 3dROIstats/3dToutcount -&gt; ToolExecutionError.
        (6) first_level_utils.py:1236 non-numeric template data max: GuardError -&gt; InputError (exit 2), CHANGELOG. Approved 2026-10-08.
      </decision>
    </topic>

    <topic id="C5" title="T6d null-bandpass clause">
      <summary>Unreachable clause and dead guard.</summary>
      <research>first_level_config.py:385-400 requires bandpass for rest_conn; rest_conn_first_level.py:169 guard dead; L261 already unguarded. PV 3/3 verified.</research>
      <approaches><approach id="A1" label="Delete clause and guard" feasibility="high" risk="low"><description>No behavior change.</description><pros>No dead code.</pros><cons>None.</cons></approach></approaches>
      <decision status="decided" chosen="A1">(1) Delete T6d "a null bandpass setting keeps the current formula". (2) Delete the guard at rest_conn_first_level.py:169; simultaneous 3dTproject always gets -bandpass low high. (3) rest_conn DOF docs: bandpass always required, 0 &lt;= low &lt; high; low = 0 (lowpass only) covered by T11-polort's per-context polort. (4) Tests: bandpass absent/null -&gt; ConfigError; simultaneous 3dTproject command always contains -bandpass. Approved 2026-10-08.</decision>
    </topic>

    <topic id="C6" title="v3.2.0 wording in earlier locks">
      <summary>Obsolete release label.</summary>
      <research>Only T8 and T9 lock text uses v3.2.0; T12a and A4/ORCH references are intentional.</research>
      <approaches><approach id="A1" label="Relabel T8 and T9 only" feasibility="high" risk="low"><description>Label change.</description><pros>Accurate.</pros><cons>None.</cons></approach></approaches>
      <decision status="decided" chosen="A1">In the consolidated report replace "v3.2.0" with "4.0.0" in T8 and T9 only; v3.1.0 baseline comparisons unchanged; T12a "not 3.2.0" and A4/ORCH orchestrator "&gt;= 3.2.0" references kept. Approved 2026-10-08.</decision>
    </topic>

    <topic id="ORCH-W" title="Orchestrator report destination and write grants">
      <summary>Where the two orchestrator reports are written.</summary>
      <research>Precedent: TODO_fmri-first-level-proc_20260812_132545.md and HARMONIZE_*.md written into this repo root by orchestrator brainstorms. Paths user-confirmed.</research>
      <approaches>
        <approach id="A" label="TODO files in each orchestrator root" feasibility="high" risk="low"><description>Session-bound brainstorm grants.</description><pros>Each project acts independently; line refs re-verified.</pros><cons>Two grant prompts.</cons></approach>
        <approach id="B" label="Embed in final report only" feasibility="high" risk="med"><description>No grants now.</description><pros>Simple.</pros><cons>Line refs not re-verified; orchestrators need read access here.</cons></approach>
      </approaches>
      <decision status="decided" chosen="A">
        Write TODO_ABCD_fmri_orchestrator_S3_{YYYYMMDD_HHMMSS}.md into <local_path>/ABCD_fmri_orchestrator_S3
        and TODO_fmri-proc-orchestrator_{YYYYMMDD_HHMMSS}.md into <local_path>/fmri-proc-orchestrator
        (paths user-confirmed); markdown per the 2026-08-12 TODO precedent; per item: source lock, current state file:line, required change,
        lands only after v4.0.0 is published. Sequence: final report, then two session-bound grants (each approved via the hook prompt):
        ~/.claude/scripts/grants.sh grant --path &lt;root&gt; --skill brainstorm --operations read,write --tools Read,Grep,Glob,Write (no
        --persist), then read-only re-verification of cited orchestrator file:line references, then the TODO files, then the exit sequence.
        Approved 2026-10-08.
      </decision>
    </topic>

    <topic id="AUD-PASS1" title="Pre-Report Audit pass 1 (this session)">
      <summary>All this session's decisions explicitly approved; orchestrator root paths (taken from the 2026-10-07 grant commands) confirmed by the user.</summary>
      <research>Verify-before-flag against session record.</research>
      <approaches><approach id="A1" label="Confirm paths" feasibility="high" risk="low"><description>User confirmation.</description><pros>No unapproved assumption.</pros><cons>None.</cons></approach></approaches>
      <decision status="decided" chosen="A1">Paths confirmed correct by the user 2026-10-08. The only pending verification (orchestrator file:line references) is scheduled at TODO-write time under ORCH-W.</decision>
    </topic>

    <topic id="AUD-S" title="Audit pass 2: field declarations for the smoothing stages">
      <summary>T11-c listed smoothing stages by name only; rest_conn residuals-concat path left per-run residuals unavailable for per-run blurring.</summary>
      <research>PV: 1 verified, 2 concerns (minor, folded in).</research>
      <approaches><approach id="A1" label="Full declarations; rest blur via sub-brick selection of the concatenated residual" feasibility="high" risk="low"><description>Covers both rest paths.</description><pros>Declared-or-exempt and read-proxy tests satisfiable.</pros><cons>None material.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        User condition (binding): smoothing stages exist only when smoothing.enabled is true and feed only voxel-level outputs (voxelwise
        activation, voxelwise beta series and residuals, seed-to-voxel maps); parcel extraction, raw ptseries, parcellated connectivity and
        seed series never consume smoothed data; contract test: no parcel-level stage declares a smoothing stage upstream.
        (1) task-act-smooth / task-conn-smooth: declare smoothing.enabled, smoothing.fwhm, scan_path, scan_paths, run_lengths, run_labels,
        scale_to_psc; upstream = that type's prep stage; mask = max &gt; min in every run on the unscaled input; 3dBlurToFWHM -FWHM fwhm -ACF
        -mask per run (Mode B via sub-brick selectors, both task types); per-run PSC of the smoothed copy when scale_to_psc is true.
        (2) task-act-glm-smooth: declares everything task-act-glm declares (incl. the shared always-run derived files: onsets, censor,
        prepared motion; not recomputed) plus smoothing.*; upstream task-act-smooth; produces only _s{N}mm voxelwise outputs.
        (3) task-conn-beta-series-smooth: declares everything task-conn-beta-series declares plus smoothing.*; upstream task-conn-smooth and
        task-conn-design-matrix (shared design matrix and survival table); produces only _s{N}mm voxelwise outputs.
        (4) rest-conn-smooth-residuals: declares smoothing.*, scan_paths, run_lengths, run_labels; upstream rest-conn-concat or
        rest-conn-residuals-concat (whichever the config uses); per surviving run, sub-brick selection of the concatenated residual via the
        run-label offset map, blur per run (mask from the unscaled input scans, same criterion), 3dTcat into the _s{N}mm sibling of the
        concatenated residual; keep_run_res_dtseries true -&gt; per-run _s{N}mm siblings kept, else not.
        (5) P4-1 run_labels rule kept literally; its enumerated list adds the five smoothing stages. Tests: changing only fwhm reruns exactly
        the smoothing stages and their downstream; rest_conn with keep_run_res_dtseries false and smoothing on produces the smoothed
        concatenated residual; sub-brick-selector blurring equals per-file blurring (rest and task Mode B). Approved 2026-10-08.
      </decision>
    </topic>

    <topic id="AUD-Q" title="Audit pass 2: qc_summary key schema">
      <summary>Many new QC quantities lacked locked names; names must be locked before /implement (plan discipline: zero user decisions in plans).</summary>
      <research>Existing keys: task_act_first_level.py ~720-727, task_conn_first_level.py ~782-818, rest_conn_first_level.py 702-735. First draft PV: 1 verified, 2 concerns (1 critical: per_run_dof positional; 1 major: deferral to plan violates plan discipline); revised draft PV: 1 verified, 2 concerns (2 major, folded in).</research>
      <approaches><approach id="A1" label="Full schema locked now" feasibility="high" risk="low"><description>Complete key table.</description><pros>Drift-testable contract.</pros><cons>Two breaking changes.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        Unchanged: analysis_type, fd_threshold, censor_prev_tr, n_trs_total, n_trs_censored, pct_censored (all types); bandpass (rest); dof
        (task, matrix-derived per T5); contrast_labels (task_conn); per_condition_trial_counts and per_condition_surviving_trials (task; dicts
        keyed by condition label, documented intentional legacy form, label-keyed so A1-compliant).
        Changed (breaking, CHANGELOG): per_run_censoring (rest) [{run, n_trs_total, n_trs_censored, pct_censored}] with run = run label;
        per_run_dof (rest) [{run, dof, bandpass_dim, dof_null_reason}] with dof_null_reason in {run_failed, dof_below_1} or null.
        Already locked: excluded_runs [{run, reason}]; reused_stages [stage labels]; retired_outputs [paths]; provenance {package_version,
        schema_version, afni_version, python_version, numpy_version, pandas_version}.
        New: failed_runs (rest) [{run, error}]; pcorr_rank_checks (conn types when pcorr) [{condition (task_conn only), n_rois, rank,
        n_timepoints, skipped}]; null_rois (parcellated) [{condition (task_conn only), output, rois}]; null_seed_conditions (task_conn
        seed-to-voxel) [{condition}]; zero_variance_target_voxels (seed-to-voxel) [{output, n_voxels}]; trials (task) [{run, condition, onset,
        estimability, survived, reason, beta_series_position}] with reason null if survived else one of out_of_run_range, run_excluded,
        no_in_run_support, fully_censored (new name, user-approved) and beta_series_position 0-based for task_conn surviving trials else null;
        per_condition_run_counts (task) [{condition, run, n_trials, n_surviving}]; psc_per_run (PSC on) [{run, n_mask_voxels,
        n_guarded_voxels, pct_guarded_voxels, n_capped_voxels, pct_capped_voxels, n_nonpositive_mean_voxels, pct_nonpositive_mean_voxels}];
        roi_coverage (parcel outputs) [{run, roi, n_voxels (atlas count, constant across runs), nonzero_fraction (per run, series entering the
        model)}]; low_baseline (parcel outputs) [{run, roi, low_baseline_fraction, median_baseline_ratio}] or null + low_baseline_null_reason;
        smoothing_per_run (smoothing on) [{run, fwhm_target_mm, acf_fwhm_input_mm, acf_fwhm_output_mm, mask_n_voxels, mask_fov_fraction}].
        Conventions: snake_case; lists of records with identity fields (run = run label, roi = template label, condition, output = filename),
        never position-keyed; undefined values null with sibling &lt;key&gt;_null_reason. INPUT_SPEC tabulates every key path with type,
        meaning and analysis types; drift contract test (c): emitted key paths per analysis type on synthetic fixtures (dotted, list elements as
        []) equal the INPUT_SPEC table. Approved 2026-10-08.
      </decision>
    </topic>

    <topic id="AUD3-R" title="Audit pass 3: excluded_runs reason vocabulary">
      <summary>A1 locked excluded_runs without reason values.</summary>
      <research>Exclusion paths: T4 floor, T6d RUN_SKIPPED, T6e RUN_FAILED.</research>
      <approaches><approach id="A1" label="Closed three-value vocabulary" feasibility="high" risk="low"><description>Shared with dof_null_reason.</description><pros>Consistent.</pros><cons>None.</cons></approach></approaches>
      <decision status="decided" chosen="A1">excluded_runs lists every supplied run that does not enter the concatenated model; reason in {insufficient_uncensored_trs (T4), dof_below_1 (T6d), run_failed (T6e; details in failed_runs)}; last two shared with per_run_dof.dof_null_reason; test: each exclusion path yields its reason. Approved 2026-10-08.</decision>
    </topic>

    <topic id="AUD3-O" title="Audit pass 3: orchestrator contract-change sections">
      <summary>ORCH lists covered only line-traced items; several 4.0.0 contract changes reach both orchestrators.</summary>
      <research>Derived from all locks.</research>
      <approaches><approach id="A1" label="Contract-change section per TODO; review-required only" feasibility="high" risk="low"><description>No prescribed fixes for newly found consumers.</description><pros>Respects orchestrator scope authority.</pros><cons>Orchestrators must decide fixes.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        (1) Each TODO file gets a section "fmri-first-level-proc 4.0.0 contract changes" listing every change, grouped: config (closed schema,
        override validation, run_labels required, smoothing and roi_zero_handling blocks); outputs (output_files final-only with PSC, mean,
        censor and motion in intermediate_files, making ABCD's F5 *_psc filter redundant; _s{N}mm outputs; ledger-scoped remove_previous);
        qc_summary (per_run_censoring and per_run_dof breaking; matrix-derived dof; f_j &gt; 0 survival changes per_condition_surviving_trials;
        new keys); exit codes and warnings (unparseable AFNI output exit 4 instead of 1; template data max exit 2 instead of 1; TRIALS_FEW and
        EVENTS_LEGACY removed; new codes UNVALIDATED_VERSION, LEDGER_ENTRY_UNREADABLE, RETIREMENT_FAILED, NULL_ROI, SEED_NULL,
        PCORR_RANK_DEFICIENT, RUN_FAILED); numerics (rest polort/DOF, parcellated zero handling, task_conn floor 3, floor onset mapping,
        unscaled rest raw ptseries). (2) Per change, consumer sites located read-only at write time (ORCH-W verification read). (3) Each entry
        records file:line or "no consumer found". (4) Consumer found -&gt; "review required" only, no prescribed fix. (5) Existing ORCH items keep
        their prescribed changes. Approved 2026-10-08.
      </decision>
    </topic>

    <topic id="AUD4-CAP" title="Audit pass 4 (4-pass cap) surfaced P4a, P4b, P4c">
      <summary>Verify-before-flag confirmed all three undecided; _s{N}mm placement (immediately before the extension, e.g. _concat_bucket_stats_s6mm.nii.gz) confirmed decided from the 2026-10-06 approved examples.</summary>
      <research>Lock texts and transcripts.</research>
      <approaches><approach id="A1" label="Resolve now, one at a time" feasibility="high" risk="low"><description>User choice at the cap.</description><pros>No open audit items.</pros><cons>None.</cons></approach></approaches>
      <decision status="decided" chosen="A1">User chose "resolve now, one at a time" 2026-10-08.</decision>
    </topic>

    <topic id="P4a" title="Producing stage for the min-outlier EPI (PENDING: resume here)">
      <summary>min_outlier_epi is a locked final output (T11b), per run (T3), but no ledgered stage or always-run step produces it; v3.1.0 calls gen_min_outlier_epi directly (task_act_first_level.py:628, rest_conn_first_level.py:664; 3dToutcount -automask -fraction -quiet, np.argmin, 3dbucket; first_level_utils.py:1375-1444).</summary>
      <research>
        First draft (file for every supplied run incl. excluded runs; expected-path set by supplied labels) PV: 0 verified, 3 concerns.
        PV-1 (concerns): major, conflicts with G2(2) expected-path set (surviving labels); major, conflicts with A1(7) test "exclude run3 -&gt;
        no run3 outputs"; minor, not flagged as amendment. PROTOCOL FAILURE: PV-1 prefixed its return with prose and wrapped the JSON in a
        markdown fence (contract violation); its JSON content was well-formed and its majors are independently duplicated by PV-2.
        PV-2 (concerns): same two majors; minor, execution order unspecified (v3.1.0 mutates scan_path to the PSC output right after this call).
        PV-3 (concerns): minor, rest call site labels by position (run{i+1}, rest_conn_first_level.py:664); minor, Mode A/B equivalence of this
        command chain untested (covered by the proposed test).
      </research>
      <approaches>
        <approach id="A1-revised" label="Dedicated ledgered stage; surviving runs only" feasibility="high" risk="low">
          <description>
            Revised P4a (as presented to the user, awaiting verification): (1) stages {type}-min-outlier-epi (task-act, task-conn, rest-conn)
            declare scan_path, scan_paths, run_lengths, run_labels, plus the surviving run-label list from the always-run run-exclusion step (a
            derived value); the stage runs after that step; reads only the supplied unscaled scans from the run()-entry config copy, never prep
            outputs (Mode A each file; Mode B sub-brick selectors); per surviving run: 3dToutcount -automask -fraction -quiet, first minimum,
            3dbucket. (2) Naming: single-run task keeps {pre}_min_outlier_epi.nii.gz; multi-run task and rest (any K) use
            {pre}_run{N}_min_outlier_epi.nii.gz with N = run label; final outputs; excluded runs get no file (consistent with A1(7) and G2);
            rest call site uses the label. (3) Selected TR index and outlier fraction logged at INFO; no qc_summary key. (4) Tests: Mode A and
            Mode B identical files; labels [1,3,4] -&gt; run1/run3/run4; excluding run 3 -&gt; no run3 file and a stale one is retired; changing
            only scale_to_psc or smoothing does not rerun the stage.
          </description>
          <pros>Consistent with A1(7), G2(2), T3; decoupled from PSC and smoothing changes.</pros>
          <cons>Stage reruns when the surviving-run set changes (cheap).</cons>
        </approach>
      </approaches>
      <decision status="open" chosen="none">
        PENDING USER DECISION (resume exactly here): Agent Return Validation Gate recovery for the P4a verification. Question as asked: "The
        revision is material. I recommend recovery option (i), retry: dispatch three fresh verifiers on the revised P4a. That also settles
        PV-1's failed slot. The other options are (ii) retry with stricter instructions, (iii) drop PV-1 as UNVERIFIED, or (iv) abort. Proceed
        with (i)?" After the verification returns, present revised P4a with verdicts for approval.
      </decision>
    </topic>

    <topic id="P4b" title="Names for always-run steps (PENDING)">
      <summary>G3/G4 staging dirs (.staging_{out_file_pre}_{step}/), staged records, and C2's {out_file_pre}_{step}.REML_cmd rename require step labels, but only ledgered stages have names (T11 table). Always-run steps that write files: onset files, censor/motion prep, T5 preflight design matrix, T7a estimability dry run, rest DOF surrogate dry run (temporary input), qc_summary.</summary>
      <research>Not yet drafted for verification.</research>
      <approaches><approach id="A1" label="To be proposed" feasibility="high" risk="low"><description>Closed list of {type}-{name} labels; requires 3-agent PV.</description><pros>n/a</pros><cons>n/a</cons></approach></approaches>
      <decision status="open" chosen="none">Not yet presented. Next after P4a.</decision>
    </topic>

    <topic id="P4c" title="_s{N}mm decimal formatting (PENDING)">
      <summary>Placement decided (immediately before the extension). Rendering of a non-integer FWHM (e.g. 6.50 as _s6p5mm vs _s6p50mm; 6.0 as _s6mm) unspecified; SMOOTH-ARCH gives only _s6mm and _s6p5mm.</summary>
      <research>Formatting only; no PV planned.</research>
      <approaches><approach id="A1" label="To be proposed" feasibility="high" risk="low"><description>Formatting rule.</description><pros>n/a</pros><cons>n/a</cons></approach></approaches>
      <decision status="open" chosen="none">Not yet presented. Next after P4b.</decision>
    </topic>

    <topic id="AMEND-S" title="Amendment ledger additions from this session">
      <summary>Every place this session's locks rewrite earlier locks; the final report must apply these in addition to the 2026-10-08 AMEND topic and the 2026-10-06 amendments section.</summary>
      <research>Derived from this session's locks.</research>
      <approaches><approach id="A1" label="Rewrite earlier text in the final report" feasibility="high" risk="low"><description>Not annotated; rewritten.</description><pros>Single source of truth for /implement.</pros><cons>None.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        T3: rationale replaced (C3). T6d: null-bandpass clause deleted (C5); simultaneous DOF already superseded by T11-polort. T6e: 3dNetCorr
        clauses replaced by C1. T8, T9: "v3.2.0" -&gt; "4.0.0" (C6). T10(2) cwd=out_dir and "REML_cmd remain in out_dir" superseded by C2.
        T11-optA: write sequence, existence/gzip checks and remove_previous text superseded per C4(1); new leftover-staging rule for all steps.
        T11-psc: 25% gate rationale per KI-005(1). T11-lowbase: doc figures removed per KI-005(4); field emission conditional per C3(3) option B.
        SMOOTH-ARCH: seed Z computed with 3dcalc clip, not 3dTcorr1D -Fisher (C1(5)); smoothing-stage declarations per AUD-S; automask ban
        rationale per KI-005(3). T11-c: smoothing-stage rows per AUD-S. P4-1: enumerated list extended per AUD-S(5). A1(4): excluded_runs
        reason vocabulary per AUD3-R. G3: validation-failure exception classes per C4(2-3). ORCH (2026-10-08): extended by ORCH-R and AUD3-O.
        runtime.py binary list per C1(6).
      </decision>
    </topic>
  </topics>

  <action_items>
    <item priority="P0" target_mode="brainstorm" description="Resume /brainstorm at topic P4a: ask the pending Validation Gate recovery question (recommend option (i): 3 fresh PV agents on revised P4a), then P4b (3-agent PV), then P4c, then generate the FINAL consolidated report (T1-T11 + 2026-10-06 locks + 2026-10-08 locks + this report's locks, with AMEND, 2026-10-06 amendments and AMEND-S applied; consolidated enumerated doc-item list per T12d(2) incl. ToolVersionError docstring fix to minimum-version wording; CHANGELOG entries from all locks incl. this session's breaking/exit-code changes), then ORCH-W grants, read-only orchestrator line verification, the two TODO files (incl. AUD3-O sections), then the exit sequence." />
    <item priority="P0" target_mode="implement" description="After the final report: implement v4.0.0 per the consolidated spec." />
    <item priority="P1" target_mode="test" description="Design and run tests enumerated in each lock; drift contract tests per T12d(3) plus AUD-Q test (c)." />
  </action_items>

  <next_steps>Next session: /resume-project, then /brainstorm with this report as input, resuming exactly at the P4a recovery question. Then P4b, P4c, final report, orchestrator TODO files, exit sequence; then /implement plan.</next_steps>
</brainstorm_report>
