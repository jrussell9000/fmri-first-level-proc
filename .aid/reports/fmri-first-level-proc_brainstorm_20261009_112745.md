<brainstorm_report>
  <meta project="fmri-first-level-proc" mode="brainstorm" timestamp="2026-10-09T11:27:45-04:00" status="final" release="4.0.0" />

  <scope_note>
    FINAL consolidated specification for fmri-first-level-proc 4.0.0. It supersedes the interim reports
    fmri-first-level-proc_brainstorm_20261005_060843.md, _20261006_191039.md, _20261008_063017.md and _20261008_111047.md
    (brainstorm_history). Every amendment recorded in those reports and in the 2026-10-08/09 session has been applied by
    rewriting the affected text; no topic below is superseded by a later topic. All decisions are user-approved. Notation:
    {pre} = out_file_pre; {type} in {task-act, task-conn, rest-conn}; "run" = integer run label (A1); S_pre, S_final,
    K_supplied, K_model defined in topic RUNSETS. v3.1.0 is the comparison baseline throughout.
  </scope_note>

  <context_files>
    <file path="fmri_first_level_proc/first_level_utils.py" relevance="Shared utilities; validate_template L1197-1300; gen_min_outlier_epi L1375-1444; write_qc_summary L1513-1537; graded_warning L254; seed_to_voxel_conn/parcellated_conn L1788-2029; validate_onset_file_format L480-507 (deleted)" />
    <file path="fmri_first_level_proc/task_act_first_level.py" relevance="task_act pipeline; tissue derivatives L201-208; GLM -bucket L243; min-outlier L628; COND_DROPPED L669; QC L720-727; docstring L510 stale EXTRACT_DROPPED" />
    <file path="fmri_first_level_proc/task_conn_first_level.py" relevance="task_conn pipeline; derivatives in gen_design_matrix L235-242; -x1D_stop -nobucket L274-275; COND_DROPPED L731" />
    <file path="fmri_first_level_proc/rest_conn_first_level.py" relevance="rest pipeline; dead bandpass guard L169; per-run censor/motion/DOF L387-429; residual loop L434-445; combined all-runs error L453-457; QC L702-737" />
    <file path="fmri_first_level_proc/first_level_config.py" relevance="GLOBAL_ONLY_KEYS L77; yaml.safe_load L194; schema_version L619; discovery merge L759-807" />
    <file path="fmri_first_level_proc/runtime.py" relevance="_AFNI_BINARIES L15-31; lockfile handling L208-217" />
    <file path="fmri_first_level_proc/bids.py" relevance="discover_inputs (lexical sort L92, slot tables L156-172, matches[0] L202, DISCOVERY_COLLISION L190); unused output helpers removed" />
    <file path="fmri_first_level_proc/checkpoint.py" relevance="Existing unused ledger module rewired by T11" />
    <file path="fmri_first_level_proc/exceptions.py" relevance="Exception hierarchy; context attribute; ToolVersionError docstring wording" />
    <file path="fmri_first_level_proc/run_first_level.py" relevance="CLI; exit-code mapping L27-31, L203-216; deprecated alias removed" />
    <file path="ABCD_fmri_orchestrator_S3 (sibling project)" relevance="Orchestrator items, topic ORCH" />
    <file path="fmri-proc-orchestrator (sibling project)" relevance="Orchestrator items, topic ORCH" />
  </context_files>

  <topics>

    <!-- ======================= INPUTS AND RUN STRUCTURE ======================= -->

    <topic id="T1" title="Multi-run input API (task_act, task_conn)">
      <summary>Dual input pathway for multi-run acquisitions.</summary>
      <approaches><approach id="A1" label="Mode A per-run lists / Mode B singular paths plus run_lengths" feasibility="high" risk="low"><description>Explicit per-run inputs or one concatenated series with run lengths.</description><pros>Covers both orchestrator styles.</pros><cons>Two modes to test.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        Mode A: explicit per-run path lists in acquisition order, equal length across slots. Mode B: singular paths plus run_lengths.
        run_labels is required in both modes, including K_supplied = 1 (A1). Rejected (ConfigError): mixing singular/plural fields,
        run_lengths with per-run lists, length mismatches; missing files raise InputError. ResolvedConfig gains plural fields,
        run_lengths and run_labels; a canonical normalized run list is built at resolve time. Run-structure checks at pipeline entry
        (summed run_lengths vs scan volumes and motion/tissue row counts; per-run row counts in Mode A; identical TR and grid via
        3dinfo) raise InputError. BIDS discovery pairing, ordering and mode interaction are specified by P2-2, P3-1 and P4-2; T1 mode
        checks run on the merged explicit+discovered configuration (P4-2(B2)).
      </decision>
    </topic>

    <topic id="A1" title="Run identity by label value">
      <summary>Runs keep their true label values; gaps stay visible; never renumbered, never list position.</summary>
      <approaches><approach id="A1" label="Integer label identity, label required" feasibility="high" risk="low"><description>Labels from run_labels, BIDS run- entity, or Mode A basename; no default.</description><pros>No silent mislabeling.</pros><cons>Single-run configs must supply a label.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        (1) Run identity = integer value of the run label, written unpadded as run{N} in filenames, QC, excluded_runs, ledger scope
        keys, stage labels and warnings; never list position, never renumbered; concatenation offsets, -concat and -local_times rows
        come from an internal label-to-offset map over the runs entering the model. (2) Label source precedence: closed-schema
        run_labels (unique non-negative ints aligned with scan_paths in Mode A or run_lengths in Mode B; length 1 for a single scan) &gt;
        BIDS discovery run- entity &gt; Mode A run- entity parsed from the scan basename ((^|_)run-(\d+)(_|\.)); Mode B labels only from
        run_labels; no label (including K_supplied = 1) -&gt; ConfigError. (3) Duplicate labels -&gt; ConfigError; Mode A per-run input filename
        run- entity != label -&gt; InputError. (4) qc_summary excluded_runs [{run, reason}] (vocabulary per AUD3-R). (5) run_labels in
        INPUT_SPEC (drift test) and CHANGELOG breaking. (6) Tests: labels [1,3,4] -&gt; run1/run3/run4 and QC labels {1,3,4}; run 3
        excluded under T4 (task) or dof_below_1 (rest) -&gt; no run3 files of any class and stale run3 files retired; run 3 excluded as
        run_failed -&gt; no run3 final outputs, its retained intermediates listed, failed_runs entry present (P4d); label/filename mismatch
        InputError; duplicates ConfigError; unlabeled single run ConfigError; BIDS labels used; condition below floor retires stale
        outputs including onset files; unchanged config: expected-path set equals the output lists.
      </decision>
    </topic>

    <topic id="P2-2" title="BIDS discovery run handling (per-run slots)">
      <approaches><approach id="A1" label="Integer ordering, explicit labels, InputError on ambiguity" feasibility="high" risk="low"><description>No inferred default label.</description><pros>Consistent with A1.</pros><cons>Single unlabeled runs need run_labels.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        Applies to per-run slots only (scan, motion/confounds, events, CSF, WM, GS). (1) Discovered runs ordered by integer run- value,
        never lexical sort (fixes bids.py:92). (2) Slot files without a run- entity: label from run_labels, which must have exactly one
        entry; run_labels absent -&gt; ConfigError naming run_labels; no default label is ever inferred. (3) InputError listing the
        conflicting files when a slot mixes files with and without run-, has two or more unlabeled files, or has two files with the same
        label. (4) run_labels set and discovered files carry run-: run_labels must equal the discovered labels in integer order, else
        InputError. (5) INPUT_SPEC and README. (6) Tests: run-1/run-2/run-10 ordered 1,2,10; single unlabeled + run_labels [1] -&gt; run1;
        single unlabeled without run_labels -&gt; ConfigError; each ambiguity case -&gt; InputError; run_labels disagreeing -&gt; InputError.
      </decision>
    </topic>

    <topic id="P3-1" title="Cross-slot run agreement">
      <approaches><approach id="A1" label="Per-run label-set agreement" feasibility="high" risk="low"><description>All populated per-run slots carry the scan label set.</description><pros>Catches explicit/discovered mismatches.</pros><cons>GS all-or-none.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        Cross-directory precedence for per-run slots unchanged from v3.0.0 (first directory in derivatives_dirs wins; medium
        DISCOVERY_COLLISION). Mode A only: after explicit and discovered values merge slot by slot, every populated per-run slot must
        carry exactly the scan slot's run-label set, else InputError naming the slot and missing/extra labels; optional GS all-or-none.
        Tests: explicit scans runs 1,3 + discovered motion 1,2,3 -&gt; InputError naming motion and label 2; GS subset -&gt; InputError.
      </decision>
    </topic>

    <topic id="P4-2" title="Template excluded from discovery; discovery with Mode B">
      <approaches><approach id="A1" label="Global-only template; merge-then-validate" feasibility="high" risk="low"><description>Discovery covers per-run slots only.</description><pros>Matches global template semantics.</pros><cons>Mode B gets no per-run discovery.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        (A) Remove the template slot from BIDS discovery (dseg entry in both slot tables, DiscoveredInputs.template_path,
        first_level_config.py:782-783, discover_inputs and DiscoveredInputs docstrings bids.py:29-34, INPUT_SPECIFICATION.md:449);
        template_path only from the global config key (GLOBAL_ONLY_KEYS); CHANGELOG breaking; test: a dseg file in a subject func dir is
        never picked up. (B1) discover_inputs returns per-run lists for every per-run slot in all analysis types, never matches[0]; a
        single run is a length-1 list; CHANGELOG breaking. (B2) Merge explicit and discovered values first, then run the T1 mode checks
        and the Tier-3 mandatory-slot check on the merged result; violation -&gt; ConfigError naming the conflicting fields with the remedy
        (all per-run inputs explicit as single files in Mode B, or remove run_lengths and singular fields so discovery supplies per-run
        files in Mode A). (B3) P3-1 cross-slot agreement in Mode A only; Mode B identity only from run_labels aligned with run_lengths.
        (B4) INPUT_SPEC and README: Mode B gets no per-run discovery. (B5) Tests: explicit Mode B scan + discovered motion -&gt;
        ConfigError naming both; run_lengths with all paths left to discovery -&gt; ConfigError; Mode B all explicit + derivatives_dirs
        succeeds; single discovered run -&gt; length-1 list.
      </decision>
    </topic>

    <topic id="RUNSETS" title="Run sets S_pre and S_final; counts K_supplied and K_model">
      <summary>Single definitions used by every run-scoped rule in this report.</summary>
      <approaches><approach id="A1" label="Two derived run sets, two counts" feasibility="high" risk="low"><description>Computed once, declared by consuming stages.</description><pros>No ambiguous "surviving runs".</pros><cons>More declared derived values.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        (1) S_pre = supplied run labels minus pre-model exclusions (task: insufficient_uncensored_trs, T4; rest: dof_below_1, T6d),
        computed once in the {type}-nuisance step. S_final = S_pre minus run_failed (rest only; equals S_pre for task types), computed
        once from the residual-stage results (per-run mode: failed rest-conn-residuals-run{N}; concat mode: failed runs inside
        rest-conn-residuals-concat). Single source; contract test that no other code path derives either set.
        (2) Stages declaring S_pre as a derived value and processing only S_pre runs: task-act-prep, task-conn-prep (per-run PSC mean/psc,
        Mode A concat_scan, per-run max/min and the run-intersection mask), task-act-smooth, task-conn-smooth, task-act-raw-ptseries,
        task-conn-raw-ptseries, task-act-glm, task-act-glm-smooth, task-conn-design-matrix, task-conn-beta-series,
        task-conn-beta-series-smooth, rest-conn-prep, rest-conn-residuals-concat, task roi-qc. rest-conn-residuals-run{N} exist only for
        N in S_pre (DAG topology: runs attempted).
        (3) Stages declaring S_final: rest-conn-raw-ptseries (runs after the residual stages), rest-conn-concat (per-run mode),
        {type}-min-outlier-epi, rest-conn-smooth-residuals (its run-label offset map is built from S_final), rest-conn-roi-qc. A change in
        either set changes the declaring stages' hashes.
        (4) K_supplied = len(run_labels), known from config before data are read; governs filename form only: task_act/task_conn K=1
        names unchanged from v3.1.0 and the single-run name {pre}_min_outlier_epi.nii.gz iff K_supplied = 1; K_supplied &gt; 1 uses
        label-bearing {pre}_run{N}_* names even if one run survives; rest_conn per-run names carry the label at any K.
        (5) K_model = |S_pre| (task types only) governs model structure: -concat iff K_model &gt; 1 (T2); per-run 3dTstat -max/-min,
        {pre}_run_intersect_mask.nii.gz and -mask for 3dDeconvolve and 3dLSS iff K_model &gt; 1 (T3); a stale mask is retired by G2.
        rest_conn has no K-dependent model-structure rule (3dTproject per run, then 3dTcat).
        (6) INPUT_SPEC defines all four terms. (7) Tests: task runs 1-3 with run 3 excluded by T4 -&gt; every per-run and concatenated
        artifact contains runs 1,2 only; editing only the motion file so run 3 becomes newly excluded -&gt; prep, smooth, raw-ptseries and
        model stages rerun and stale run3 files retire; task_act labels [1,2] with run 2 excluded -&gt; no -concat, no -mask, no mask file,
        {pre}_run1_min_outlier_epi.nii.gz, voxelwise outputs equal a run-1-only config apart from filenames; run 2 later surviving -&gt;
        mask and -concat appear and prep and model stages rerun; K_supplied = 1 -&gt; v3.1.0 names and commands; rest dof_below_1 run -&gt; no
        prep files; rest run_failed -&gt; no raw ptseries, prep volumes listed as intermediates; single-source contract test.
      </decision>
    </topic>

    <topic id="T2" title="Run-boundary model specification and onset validation">
      <summary>Run boundaries for 3dDeconvolve/3dLSS, onset interpretation, and hard validation of onset ranges.</summary>
      <approaches><approach id="A1" label="-concat plus -local_times; out-of-range onsets fatal" feasibility="high" risk="low"><description>Explicit per-run timing; misaligned timing files stop the run with a diagnostic record.</description><pros>No silent use of misaligned timing.</pros><cons>Truncated acquisitions need trimmed events files.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        (1) build_decon_base_command takes run_lengths of the S_pre runs; K_model &gt; 1 appends -concat with 0-based cumulative run-start
        indices; K_model = 1 omits -concat. -local_times is always explicit; every onset file (task_act -stim_times/-stim_times_AM1;
        task_conn nuisance and -stim_times_IM beta files) carries one row per model run, with a lone '*' for empty runs. Mode A onsets are
        run-local from the first volume of that run's scan; Mode B onsets are relative to the concatenated series and assigned to a run
        by tr_index against cumulative run start/length, then normalized into one internal event table keyed by run label.
        (2) Onset validation (task_act and task_conn), performed by the always-run step {type}-events, the first always-run step, over
        every supplied run before nuisance processing: an onset is valid iff 0 &lt;= onset &lt; run end (Mode A: run end = n_vols x TR of
        that run; Mode B: bound = total concatenated duration). Event durations extending past the run end are not violations. All
        violations across every events file, run and condition are collected; any violation raises InputError (exit 2).
        (3) Before raising, {type}-events writes {pre}_timing_errors.json through the G3 protocol (staged record, final class):
        {analysis_type, input_mode, tr, violations: [{events_file, run, run_null_reason, condition, onset_s, violation}],
        runs: [{run, events_file, n_vols, run_end_s, n_onsets, min_onset_s, max_onset_s, n_negative, n_at_or_after_run_end}]} with
        violation in {negative, at_or_after_run_end}; runs[] covers every supplied run including clean runs; Mode B violations carry
        run = null and run_null_reason = outside_concatenated_series; values only, no inferred cause. The InputError message states the
        run labels, violation counts, the record path, and that in-range onsets of the same file may also be wrong;
        FmriFirstLevelError.context carries the record content. After a corrected successful run the step's path set is empty, a new
        staged record is appended and G2 retires the record file.
        (4) An existing onset file whose non-empty row count does not match the number of model runs raises InputError naming the file.
        task_conn beta IM files order rows by beta_cond_order, then chronologically within condition; one ordered (run, condition, trial)
        sequence drives both the file and the gen_beta_series sub-brick lookup (replaces the contiguous total_used counter).
        (5) INPUT_SPEC: the rule, the record schema, known causes (timing referenced before dummy-scan removal, wrong events file paired
        with a scan, unit mismatch ms/s or TR/s, crossed run order, truncated acquisition with complete task timing), the remedy
        (correct or trim the events file and rerun), and the truncation trade-off. (6) Tests: negative onset -&gt; InputError and record;
        onset == run end -&gt; violation; onset just below run end with a duration past it -&gt; no violation; violations in two runs and two
        conditions all listed; clean runs in runs[]; Mode B onset past total duration -&gt; record with run null; record exists before the
        raise; no nuisance file promoted on failure; corrected rerun retires the record; context equals record content.
      </decision>
    </topic>

    <topic id="T3" title="Per-run PSC scaling, run-intersection mask">
      <approaches><approach id="A1" label="Per-run PSC plus intersection mask" feasibility="high" risk="low"><description>Per-run scaling; non-constant-voxel mask across model runs.</description><pros>Run-specific baselines respected.</pros><cons>More intermediates.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        When scale_to_psc is true: per S_pre run 3dTstat -mean + 3dcalc min(200,a/b*100)*step(a)*step(b) (Mode B via scan[s_k..e_k]
        sub-brick selectors, verified bit-identical to per-file scaling); writes {pre}_run{N}_mean.nii.gz and {pre}_run{N}_psc.nii.gz,
        then 3dTcat in acquisition order into {pre}_psc.nii.gz as the model input. For K_model &gt; 1 regardless of PSC: per-run 3dTstat
        -max/-min on the series entering the model; {pre}_run_intersect_mask.nii.gz keeps a voxel iff max &gt; min (exact) in every S_pre
        run, combined via one 3dcalc of ispositive products, passed as -mask to 3dDeconvolve and 3dLSS. Rationale: max &gt; min keeps exactly
        the voxels with non-constant signal in every run and holds for PSC-scaled, unscaled positive-baseline and demeaned input (demeaned
        input accepted only with scale_to_psc false); a mean-positive criterion would drop every voxel of demeaned input. Mode A always
        3dTcats the unscaled S_pre runs into {pre}_concat_scan.nii.gz as the raw ROI source (and model input when PSC is off); in Mode B
        the supplied scan serves this role. K_model = 1: commands unchanged from v3.1.0 (no -mask). Filename form follows K_supplied
        (RUNSETS(4)). Min-outlier EPI: topic P4a.
      </decision>
    </topic>

    <topic id="T4" title="Run-aware censoring, derivatives, run exclusion (task types)">
      <approaches><approach id="A1" label="Single censor file plus exclusion floor" feasibility="high" risk="low"><description>1d_tool with run lengths; per-run floor.</description><pros>Run-aware.</pros><cons>None material.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        Performed in the always-run {type}-nuisance step (task_act, task_conn). A censor series over all supplied runs is built in the
        step's staging dir via 1d_tool.py -censor_motion -set_run_lengths (Mode A concatenates per-run motion files row-wise first;
        -censor_prev_TR retained). Task_act CSF/WM derivatives are computed in task-act-nuisance, within run with the first TR of each
        run zeroed (task_conn computes them in task-conn-design-matrix, same rule). User-supplied motion derivative columns (7-12) pass
        through, documented as required to be within-run; Mode B emits DERIV_RUN_BOUNDARY (medium) if any derivative column at a run-start
        row equals the nonzero cross-boundary base-parameter difference. Per-run censored counts and percentages are logged. A run with
        uncensored TRs &lt;= p+1 (p = 1+floor(D_max/150), D_max = longest supplied run; same p as T5) is excluded: its scan, motion, tissue
        and censor rows and its events are removed, run_lengths recomputed, RUN_INSUFFICIENT_TRS (high) names the run and its
        uncensored count, excluded_runs records insufficient_uncensored_trs. If no run remains: ModelError (exit 5). The step promotes the
        censor .1D with its 1d_tool side files, the prepared motion file and (task_act) the derivative files for S_pre runs only. The
        T4 floor does not apply to rest_conn. K_supplied = 1 behavior is identical to v3.1.0.
      </decision>
    </topic>

    <topic id="T5" title="DOF accounting (design-matrix-derived)">
      <approaches><approach id="A1" label="Matrix-derived DOF" feasibility="high" risk="low"><description>DOF from the actual design matrix.</description><pros>Exact.</pros><cons>Dry runs.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        task_act (always-run task-act-preflight, after task-act-onsets): dry run of the package's own 3dDeconvolve command (-input replaced
        by -nodata total_TRs TR, -x1D {pre}_preflight_dmat.x1D -x1D_stop, retaining -concat, -local_times, -polort A, -censor, -ortvec,
        all -stim_times* and HRF strings); DOF = rows - columns. task_conn (always-run task-conn-estimability, after the ledgered
        task-conn-design-matrix): IM columns identified via x1D StimLabels/StimBots/StimTops for label beta_stims; per-trial LSS DOF =
        rows - (non-IM columns + 2); CENSOR_HIGH sourced from the censor file. DOF &lt; 1 -&gt; ModelError; nonzero dry-run exit -&gt;
        ToolExecutionError via the centralized AFNI wrapper (command, description, stderr). QC reports the matrix-derived dof; the old
        analytic n_regressors code is removed. Applies at K=1 (QC DOF differs from v3.1.0 for multi-column HRFs). The preflight design
        matrix and any REML_cmd are intermediates (C2).
      </decision>
    </topic>

    <topic id="T5b" title="task_conn rejection of multi-column custom HRFs">
      <approaches><approach id="A1" label="ConfigError" feasibility="high" risk="low"><description>One basis column per trial required.</description><pros>No silent breakage.</pros><cons>Behavior change.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        validate_custom_hrf returns the column count from its -nodata dry-run x1D (-polort -1, one stimulus; counted via np.loadtxt data
        columns); call site first_level_config.py:485 updated. task_conn with hrf_model 'custom' and a column count != 1 -&gt; ConfigError
        naming custom_hrf and the count, listing single-column alternatives (GAM, BLOCK, SPMG1, TWOGAMpw). task_act unchanged. Documented
        in INPUT_SPEC and README; CHANGELOG behavior change. Pre-existing note: 3dLSS treats each basis column of a TENT-style IM model as
        a trial; gen_beta_series assumes one sub-brick per trial.
      </decision>
    </topic>

    <topic id="T6" title="Onset-to-volume mapping">
      <approaches><approach id="A1" label="tr_index floor helper" feasibility="high" risk="low"><description>Shared floor mapping.</description><pros>Volume containing the onset.</pros><cons>Rounding change.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        Shared helper tr_index(t, tr) = floor(t/tr + 1e-6) replaces int(round(onset/tr)) for every onset-to-volume mapping, including
        Mode B run assignment against cumulative run start/length. The internal event table stores run labels and run-local onsets.
        Trial survival is defined by T7a (estimability), which supersedes the onset-volume survival criterion. Documented: onsets in the
        later half of a TR now map to the containing volume (about 49.8% of jittered onsets shift by one volume relative to round()).
      </decision>
    </topic>

    <topic id="T6b" title="Trial survival floors">
      <approaches><approach id="A1" label="Fixed floors, no advisory thresholds" feasibility="high" risk="low"><description>One drop warning per pipeline.</description><pros>Simple.</pros><cons>Not configurable.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        Advisory low-trial warnings removed (TRIALS_FEW and its constant in task_act and task_conn; the n==2/n&lt;5 messages; the n==1/n==2
        timing-reader messages, keeping only the n==0 "cannot create onset file" message). Survival counting is threshold-free and logged
        at INFO; each pipeline emits COND_DROPPED (medium) stating its floor. Constants _MIN_SURVIVING_TRIALS: task_act 2, task_conn 3
        (n=2 gives deterministic r = +/-1); not configurable; floors count trials with f_j &gt; 0 (T7a). Documented: both floors and
        rationale; qc_summary trial counts are the basis for group-level exclusion decisions.
      </decision>
    </topic>

    <topic id="T6c" title="Partial-correlation rank gate; fishZ/pcorr corrections">
      <research>Numerical-rank criterion (singular values above sv_max * max(n, m) * eps(float32)) standard before precision-matrix estimation.</research>
      <approaches><approach id="A1" label="Rank gate plus diagonal fixes" feasibility="high" risk="low"><description>Skip rank-deficient sets.</description><pros>No invalid pcorr.</pros><cons>Matrices skipped.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        Before partial correlation (task_conn per condition, rest_conn), the parcellated series extracted by 3dROIstats (T11-nz) are
        column-centered and numerical rank is computed as the count of singular values exceeding sv_max * max(n, m) * eps(float32). Rank
        &lt; m -&gt; that pcorr matrix is skipped with PCORR_RANK_DEFICIENT (high) reporting m, rank, n; task_conn continues (ModelError only
        if no condition yields a matrix); rest_conn raises ModelError; qc_summary pcorr_rank_checks. Partial correlation is computed from
        the inverse of the 1ddot correlation matrix. fishZ+pcorr writes atanh(PC) clipped to |r| &lt;= 0.999329 with diagonal 4; the PC
        diagonal is +1 (documented package convention). ConfigError if pcorr is requested with calc_conn seed_to_voxel. CHANGELOG: PCB
        mislabel fix; seed_to_voxel "_pcorr" was previously plain correlation; diagonal -1 -&gt; +1.
      </decision>
    </topic>

    <topic id="T6d" title="rest_conn per-run DOF and exclusion">
      <research>Davey, Grayden, Egan and Johnston (2013), NeuroImage, filtering induces correlation (passband dimension as effective rank); Carp (2013) interpolation before filtering; Hallquist, Hwang and Luna (2013) band-matched nuisance regression. AFNI 26.0.09 check (2026-10-09): a 3dTproject dry run with -polort 2 -censor -ort -bandpass prints "Block #0: 300 time points -- 257 stopband regressors" and "294 retained time points MINUS 272 regressors ==&gt; 22 D.O.F. left".</research>
      <approaches><approach id="A1" label="Dry-run parsed DOF" feasibility="high" risk="low"><description>Backend-specific dry runs.</description><pros>Bandpass-aware.</pros><cons>Extra dry runs.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        In the always-run rest-conn-nuisance step, for every supplied run: simultaneous backend DOF parsed from the "N D.O.F. left" line of
        a 3dTproject dry run on a one-row 1D surrogate of run length with the actual polort, censor, orts and bandpass (surrogate inputs
        and outputs temporary, never promoted); the same output's "(\d+) stopband regressors" line gives n_stopband_regressors. Sequenced
        backend: 3dBandpass dry run parses "passband indexes=a..b"; passband dimension = 2(b-a+1), index 0 counted once if present,
        Nyquist never included; DOF = min(passband_dim, n_uncensored) - n_orts (documented upper bound). bandpass is always required
        (0 &lt;= low &lt; high); the dead guard at rest_conn_first_level.py:169 is deleted (simultaneous 3dTproject always gets -bandpass).
        DOF &lt; 1 excludes the run with RUN_SKIPPED (high) and excluded_runs reason dof_below_1; the numeric DOF is retained. A dry-run
        parse failure raises ToolExecutionError (command, description, stderr). README:10 and INPUT_SPEC:295 "eliminates the DOF cost"
        claims replaced by the passband statement (Davey et al., 2013) and a description of what the sequenced path provides
        (interpolation before filtering, Carp 2013; band-matched nuisance regressors, Hallquist et al. 2013). Neither backend's filtering
        changes. Tests: bandpass absent/null -&gt; ConfigError; simultaneous 3dTproject command always contains -bandpass.
      </decision>
    </topic>

    <topic id="C1" title="Connectivity failure and null handling (replaces v3.1.0 3dNetCorr rules)">
      <approaches><approach id="A1" label="Zero-variance null definition; explicit Z clip" feasibility="high" risk="low"><description>Rules on the 3dROIstats/1ddot/3dTcorr1D backends.</description><pros>Same contract, valid tools.</pros><cons>None material.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        (1) Nonzero exit of 3dROIstats, 1ddot, 3dTcorr1D or 3dcalc in seed_to_voxel_conn/parcellated_conn raises ToolExecutionError via
        the centralized wrapper; delete both warn-and-return blocks (first_level_utils.py:1847-1851, 2008-2012), format_netcorr_mat and
        netcc/INDIV handling. (2) Missing/invalid outputs caught by G3 validation (NIfTI decompress + grid; N x N matrices; 3dROIstats
        table rows = time points, columns = ROI labels). (3) Null series = extracted parcel or seed series (same 3dROIstats extraction,
        under roi_zero_handling) with zero temporal variance. (4) Parcellated r/Fisher Z: drop null-ROI columns before 1ddot; NaN in each
        null ROI's row and column including the diagonal, placed by label; NULL_ROI (high) + qc_summary null_rois; partial correlation keeps
        the T6c rank gate on the full set (null ROI -&gt; PCORR_RANK_DEFICIENT). (5) Seed-to-voxel: null seed -&gt; SEED_NULL (high); task_conn
        skips the condition (ModelError only if none yields a map); rest_conn ModelError; r via 3dTcorr1D -pearson; Z = atanh(r) in 3dcalc
        with |r| &lt;= 0.999329 (|Z| &lt;= 4); -Fisher not used; zero-variance target voxels written as 0 with in-mask count per map in
        qc_summary zero_variance_target_voxels. (6) Connectivity outputs (condition matrices, seed maps, contrast outputs) registered as
        final outputs. Bare except/pass around censor-stat extraction in all three pipelines replaced with InputError naming the censor
        file. _get_subbrik_stat_aux raises GuardError from a caught ToolExecutionError, preserving message and exit code. (7) Tests: null
        ROI NaN at correct labels and other entries equal the matrix without it; null seed skip (task_conn) / ModelError (rest_conn);
        mocked failure of each tool propagates ToolExecutionError; single-voxel seed inside the target gives Z = 4; zero-variance target
        voxel gives 0 and is counted.
      </decision>
    </topic>

    <topic id="T7a" title="Multi-run 3dLSS and trial estimability (task types)">
      <research>AFNI 26.0.09: a fully censored IM column gives an "all zeros" warning and a NaN 3dLSS sub-brick; 3dROIstats/3dBrickStat read NaN as 0; LSS beta SD scales about as 1/sqrt(f_j).</research>
      <approaches><approach id="A1" label="Estimability-only survival" feasibility="high" risk="low"><description>f_j &gt; 0.</description><pros>Formal criterion.</pros><cons>Dry run per analysis.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        Multi-run 3dLSS is a single fit on the concatenated S_pre series using the -concat x1D. Survival is computed in the always-run
        {type}-estimability step by one 3dDeconvolve dry run per analysis (-nodata total_TRs TR, the analysis's -concat/-local_times,
        -polort -1, each condition's onset file via -stim_times_IM with its HRF including married timing, -x1D_uncensored, -x1D_stop, no
        -censor). task_act: the dry run reads temporary per-condition onset copies for all conditions written in the step's staging dir and
        never promoted; task_conn: it reads the promoted onset files from task-conn-onsets. f_j = (sum over uncensored TRs of x_jt^2) /
        (sum over all TRs of x_jt^2), numerator in Python from the censor vector; IM columns map to trials by file order. A trial
        survives iff f_j &gt; 0; denominator 0 -&gt; f_j = 0 with reason no_in_run_support. Floors per T6b. task_conn keeps all trials as 3dLSS
        regressors; the downstream beta series uses surviving sub-bricks only; GuardError if a selected sub-brick is non-finite. The step
        promotes {pre}_estimability_dmat.x1D and any REML_cmd as intermediates. qc_summary trials per AUD-Q. Documented: f_j criterion;
        v3.1.0 fully censored trials entered the beta series as NaN read as 0 downstream.
      </decision>
    </topic>

    <topic id="T7b" title="Multi-run beta-series pooling (task_conn)">
      <research>Lee and Kable (2018), PLoS ONE 13:e0207083 (spurious within-run correlations between condition means); Roberts et al. (2016), NeuroImage 135:1-15 (Simpson's-paradox effects); Abdulrahman and Henson (2016), NeuroImage 125:756-766 (silent on this question).</research>
      <approaches><approach id="A1" label="Pool without run-wise adjustment" feasibility="high" risk="med"><description>No centering option.</description><pros>No untested transform.</pros><cons>Run offsets contribute.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        Each condition's surviving trial betas are pooled across runs (ordered run then onset) and correlated (parcellated via 3dROIstats
        extraction and 1ddot; seed-to-voxel via 3dTcorr1D) with no run-wise demeaning or standardization and no config option. Documented:
        (1) run-level offsets contribute to the pooled correlation; (2) run-wise centering not applied because its evidence is from MVPA
        classification; (3) downstream run-wise centering needs at least 2 trials per condition per run.
      </decision>
    </topic>

    <topic id="T8" title="Frozen primary output filenames">
      <approaches><approach id="A1" label="Module constants" feasibility="high" risk="low"><description>Stable interface.</description><pros>Contract-testable.</pros><cons>None.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        Primary filenames unchanged for single- and multi-run analyses in 4.0.0 ("_concat_" infix kept at K=1): task_act
        {pre}_concat_bucket_stats.nii.gz; task_conn {pre}_concat_LSS.nii.gz; rest_conn {pre}_concat_residual_dtseries.nii.gz. Each defined
        once as a module constant used by every construction site. Contract tests: exact strings and presence in output_files on success.
        README, INPUT_SPEC and module OUTPUTS docstrings: stable interface; renaming is a major-version change; intentionally not
        BIDS-named. Frozen names always hold unsmoothed outputs; smoothed siblings add _s{N}mm (SMOOTH-ARCH). {pre}_concat_LSS.nii.gz:
        one sub-brick per trial in combined beta-onset file order (run row by run row, beta_cond_order within row, timing-file order within
        condition), NaN sub-bricks for trials with no retained response; trials qc identifies used sub-bricks. gen_beta_series uses the
        per-trial column index from the T7a trial table. The unused BIDS output helpers are removed (P2-1).
      </decision>
    </topic>

    <topic id="T9" title="Closed config schema">
      <approaches><approach id="A1" label="Dedicated unknown-key pass" feasibility="high" risk="low"><description>Aggregate ConfigError.</description><pros>No silent typos.</pros><cons>Breaking.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        Closed key schema at every level (top, global block, per-type analysis block including the 4.0.0 keys run_labels,
        smoothing.{enabled,fwhm}, roi_zero_handling and subject/session/task/derivatives_dirs, and nested
        paths/extraction/connectivity/contrasts/connectivity.contrasts blocks). A dedicated first validation pass collects every unknown
        key (dotted path plus block label) into one ConfigError (exit 2); a key valid for another type is reported as invalid for the
        configured type; missing/invalid 'type' reported in the same error and that block's remaining keys skipped. Legacy
        extract/extract_labels/extract_stat produce a message naming stat_buckets. GLOBAL_ONLY_KEYS inside a block -&gt; ConfigError.
        load_and_validate merges **overrides into raw blocks before validate_config. Allowed-key sets are module constants enforced by an
        AST-based test over first_level_config.py (set equality both directions; unrecognized receivers fail). Tests: example_config.yaml
        validates; legacy keys rejected with migration message; unknown nested key rejected; override with nonexistent path -&gt;
        InputError. A path key set to null counts as absent for T1's mixing rule. Introspectable per-type allowed-key set (T12d(4)).
        INPUT_SPEC documents the closed schema; CHANGELOG lists the behavior changes.
      </decision>
    </topic>

    <topic id="T10" title="Absolute paths at resolve time">
      <approaches><approach id="A1" label="abspath at resolve" feasibility="high" risk="low"><description>No CWD ambiguity.</description><pros>Deterministic.</pros><cons>None.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        resolve_config converts every path field (paths.*, out_dir, template_path, derivatives_dirs, custom files) to os.path.abspath
        against the process CWD at load time (no symlink resolution). run_afni_command gains a cwd parameter (default None). AFNI working
        directories per C2. AFNI_USE_ERROR_FILE=NO is set for 3dDeconvolve calls; clean_deconvolve_err and its two call sites deleted; on
        success any 3dDeconvolve stderr "*+ WARNING" block is logged at WARNING with no code. README/INPUT_SPEC: relative paths resolve
        against the process CWD at load time; the package writes nothing into the process CWD.
      </decision>
    </topic>

    <topic id="C2" title="AFNI working directory and .REML_cmd files">
      <research>AFNI 26.0.09: only 3dDeconvolve writes into cwd (3dDeconvolve.err, suppressed by AFNI_USE_ERROR_FILE=NO; 3dDeconvolve.REML_cmd with -nobucket; Decon.REML_cmd with no bucket option).</research>
      <approaches><approach id="A1" label="Staging cwd everywhere; prefix-rename REML_cmd" feasibility="high" risk="low"><description>Uniform with G3/G4.</description><pros>Naming invariant holds.</pros><cons>Staging paths in provenance text.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        (1) Every file-writing AFNI call (ledgered stages and always-run steps, including task_act GLM, task_conn design matrix, T5
        preflight and T7a dry runs) runs with cwd = its step's staging dir .staging_{pre}_{step}/ and prefixes into it; files reach out_dir
        only via G3; custom_hrf validation keeps its TemporaryDirectory. (2) .REML_cmd: prefixed ones promoted as intermediate; unprefixed
        (3dDeconvolve.REML_cmd, Decon.REML_cmd) renamed in staging to {pre}_{step}.REML_cmd (e.g. {pre}_task-act-preflight.REML_cmd) and
        promoted as intermediate; validation = non-empty UTF-8 text containing "3dREMLfit"; more than one unprefixed REML_cmd in one staging
        dir -&gt; GuardError. (3) INPUT_SPEC: REML_cmd text and NIfTI AFNI history record staging paths (provenance only). (4) Tests: mocked
        calls receive their step staging cwd; process cwd gains no files; design-matrix REML_cmd lands as
        {pre}_task-conn-design-matrix.REML_cmd in intermediate_files; two unprefixed REML_cmd -&gt; GuardError.
      </decision>
    </topic>

    <!-- ======================= STEPS, STAGES, LEDGER ======================= -->

    <topic id="STEPS" title="Always-run steps: labels, order, file ownership">
      <approaches><approach id="A1" label="Closed label list for file-writing always-run steps" feasibility="high" risk="low"><description>{type}-{name} labels.</description><pros>Staging, records and REML names well defined.</pros><cons>None material.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        Labels are given only to always-run steps that write files; non-writing always-run operations (survival arithmetic, non-resampling
        template checks, version checks) have no label and no staging dir.
        task_act order: task-act-events (stimulus parsing and T2 onset validation; writes {pre}_timing_errors.json only on failure) -&gt;
        task-act-nuisance (T4; promotes censor + 1d_tool side files, prepared motion, CSF/WM derivative files for S_pre) -&gt;
        task-act-estimability (T7a with temporary onset copies; floor 2; promotes {pre}_estimability_dmat.x1D and REML_cmd) -&gt;
        task-act-onsets (final onset files {pre}_concat_{cond}_onsets.txt for surviving conditions only, byte-identical to the temporary
        copies) -&gt; task-act-preflight (T5; {pre}_preflight_dmat.x1D and REML_cmd) -&gt; ledgered stages -&gt; task-act-qc (last).
        task_conn order: task-conn-events -&gt; task-conn-nuisance (derivatives stay in task-conn-design-matrix) -&gt; task-conn-onsets
        (nuisance and beta onset files, all conditions) -&gt; task-conn-prep and task-conn-design-matrix (ledgered) -&gt;
        task-conn-estimability (T5 LSS DOF and T7a on the promoted onsets; floor 3; estimability_dmat and REML_cmd) -&gt; remaining
        ledgered stages -&gt; task-conn-qc (last).
        rest_conn order: rest-conn-nuisance (per supplied run: optional notch-filtered motion, censor via 1d_tool, prepared motion; T6d
        dry runs; dof_below_1 exclusion; promotes notch .1D, censor .1D + side files and prepared motion for S_pre only) -&gt; ledgered stages
        -&gt; rest-conn-qc (last). rest_conn has no events step and no T4 floor.
        Contract tests: always-run and ledgered labels disjoint and unique; every staging dir name derives from exactly one label; every
        promoted path belongs to exactly one step. Tests: condition below floor -&gt; no onset file and stale one retired; temporary and
        final onsets byte-identical; derivative file written once and identical for glm and glm-smooth; rest dof_below_1 and task T4
        exclusion promote no nuisance files for the excluded run.
      </decision>
    </topic>

    <topic id="T11-ledger" title="Ledger wiring, write sequence, hashing (T11-optA, T11-perstage, C4)">
      <approaches><approach id="A1" label="Per-stage hashed ledger as sole reuse gate" feasibility="high" risk="low"><description>Replaces os.path.exists skips and whole-config hashing.</description><pros>Safe resume; minimal reruns.</pros><cons>Implementation size.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        (1) Ledger {out_dir}/{pre}_ledger.jsonl (ledger_format 2). Completion entries are the sole reuse gate; every os.path.exists skip
        branch is removed; auto_reconstruct_ledger and its artifact globs are deleted. Write sequence for every file is G3. A step's own
        leftover staging dir is deleted before that step (ledgered or always-run) runs. A completion entry with a missing recorded output
        is invalid. remove_previous per G3(5).
        (2) Stage hash = SHA-256 of canonical JSON of: the stage label; for every declared field the pair (ResolvedConfig value from a
        deepcopy taken at run() entry, value at stage entry); the SHA-256 of declared derived files; declared derived values (e.g. S_pre,
        S_final, resolved template path); declared upstream stage hashes; the five tool versions (T12f(3)). A stage reruns if (a) it has no
        valid completion entry, (b) its hash differs from the recorded one, (c) one of its recorded outputs is missing, (d) any declared
        upstream stage runs in this invocation, or (e) its latest completion entry records non-empty qc.failed_runs (AUD5-6). Replaces
        compute_config_hash and the linear cascade. Mutated scan/censor/motion paths are set from frozen-name constants whether or not prep
        was skipped. qc_summary is never ledgered.
        (3) Every completion entry carries outputs [{path, class}], ledger_format 2, qc and warnings (AUD5-5); missing qc or warnings, or an
        unparseable or unknown-format line -&gt; LEDGER_ENTRY_UNREADABLE (medium) naming line numbers and the stage reruns.
        (4) Coverage tests: every ResolvedConfig field is declared by some stage or listed as exempt; an attribute-read proxy confirms each
        stage reads no field outside its declared set plus the exempt set plus censor_path. Exempt fields: num_cores, remove_previous,
        schema_version, analysis_type, analysis_name, out_dir, out_file_pre, derivatives_dirs, force_diff_atlas. run_labels is not exempt.
        (5) Documented: editing a motion file reruns censor/motion-dependent stages (bytes hashed); editing a template file reruns template
        consumers (P7-1); editing scan or tissue file contents does not trigger reruns (path only). Cross-analysis raw-ptseries reuse
        (INPUT_SPEC:237) is dropped; README:16 corrected. qc_summary gains reused_stages, each skip logged at INFO.
        (6) Exceptions: AFNI-written file validation failure -&gt; ToolExecutionError naming file, command + description and the failed check
        (expected vs found); first_level_utils.py:1355, 1362 (3dROIstats) and 1427, 1430 (3dToutcount) reclassified GuardError -&gt;
        ToolExecutionError (exit 1 -&gt; 4); Python-written file missing or not byte-equal -&gt; GuardError naming the file; in both cases nothing
        is recorded or moved; OSError in write/replace/fsync/delete propagates unwrapped (exit 1); first_level_utils.py:1236 non-numeric
        template data max GuardError -&gt; InputError (exit 2). INPUT_SPEC exit-code table states all mappings. Tests: each class gives its
        exception and exit code; injected OSError at os.replace exits 1 with no completion entry; completion entry with a missing output
        reruns; leftover always-run staging deleted before its step; unparseable 3dROIstats/3dToutcount -&gt; ToolExecutionError.
      </decision>
    </topic>

    <topic id="T11-table" title="Ledgered stage declarations">
      <approaches><approach id="A1" label="Per-pipeline stage table" feasibility="high" risk="low"><description>Fields, derived inputs, upstream.</description><pros>Exact rerun scope.</pros><cons>Maintenance.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        Common: {type}-template (P7-1) exists iff any configured output reads template_path; {type}-roi-qc (AUD6-1) under the same
        condition; {type}-min-outlier-epi (P4a); smoothing stages exist only when smoothing.enabled (SMOOTH-ARCH). Every stage declaring
        scan_path, scan_paths or run_lengths also declares run_labels (including smoothing stages, min-outlier and roi-qc). Every stage that
        aggregates over parcels declares roi_zero_handling.
        task_act: task-act-template (template_path, template SHA-256, scan grid; derived resolved template path); task-act-prep (scan_path,
        scan_paths, run_lengths, run_labels, scale_to_psc, S_pre); task-act-raw-ptseries (extract_raw_ptseries, extract_out_file_pre,
        template_path, average_type, roi_zero_handling, scan_path, scan_paths, run_labels, scale_to_psc, S_pre; upstream prep, template);
        task-act-min-outlier-epi (scan_path, scan_paths, run_lengths, run_labels, S_final; no upstream); task-act-glm (scan_path,
        scan_paths, run_lengths, run_labels, tr, hrf_model, custom_hrf, cond_labels, contrast_functions, contrast_labels,
        task_timing_path(s), motion_path(s), include_motion_derivs, fd_threshold, censor_prev_tr, CSF_path(s), WM_path(s),
        use_tissue_derivs, S_pre, plus derived onset files, censor file, prepared motion file and CSF/WM derivative files from the
        always-run steps; upstream prep); task-act-extract (stat_buckets, extract_resids, extract_out_file_pre, average_type,
        roi_zero_handling, template_path; upstream glm, template); task-act-roi-qc; task-act-smooth; task-act-glm-smooth.
        task_conn: task-conn-template; task-conn-prep (as task-act-prep); task-conn-raw-ptseries (as task_act); task-conn-min-outlier-epi;
        task-conn-design-matrix (the GLM field set with cond_beta_labels replacing cond_labels and no contrast fields, run_labels, S_pre,
        derived nuisance/beta onset files, censor file, prepared motion file; computes tissue derivatives; upstream prep);
        task-conn-beta-series (cond_beta_labels, scan_path, run_labels, S_pre, T7a per-trial survival table; upstream design-matrix);
        task-conn-pbseries (extract_pbseries, extract_out_file_pre, average_type, roi_zero_handling, template_path; upstream beta-series,
        template); task-conn-connectivity (calc_conn, conn_out_file_pre, pcorr, fishZ, template_path, roi_zero_handling,
        contrast_functions, contrast_labels; upstream beta-series and template, plus task-conn-beta-series-smooth for seed-to-voxel maps
        when smoothing is enabled); task-conn-roi-qc; task-conn-smooth; task-conn-beta-series-smooth.
        rest_conn: rest-conn-template; rest-conn-prep (scan_paths, scale_to_psc, run_labels, S_pre); rest-conn-residuals-run{N} (N = label
        in S_pre; the label value plus that label's scan/motion/CSF/WM/GS entries with null kept as null, tr, bandpass, notch_filter_band,
        motion_deriv_degree, fd_threshold, censor_prev_tr, use_tissue_derivs, use_sequenced_bandpass, keep_run_res_dtseries, derived run-N
        censor, prepared motion and notch-filtered motion, derived polort and DOF-surrogate inputs; upstream prep); rest-conn-concat (tr,
        keep_run_res_dtseries, S_final; upstream the residuals-run{N} stages); rest-conn-residuals-concat (used only when
        keep_run_res_dtseries is false, replacing the residuals-run{N}/concat pair; declares the union of their fields and derived inputs
        and S_pre; per-run regression inside its staging dir, only the concatenated file promoted; upstream prep); rest-conn-raw-ptseries
        (extract_raw_ptseries, extract_out_file_pre, template_path, average_type, roi_zero_handling, scan_paths, run_labels, scale_to_psc,
        S_final; upstream prep, template; runs after the residual stages); rest-conn-min-outlier-epi (S_final; after the residual
        stages); rest-conn-ptseries (extract_ptseries, extract_out_file_pre, average_type, roi_zero_handling, template_path; upstream
        concat or residuals-concat, template); rest-conn-connectivity (calc_conn, conn_out_file_pre, pcorr, fishZ, template_path,
        roi_zero_handling; upstream concat or residuals-concat and template, plus rest-conn-smooth-residuals for seed-to-voxel maps when
        smoothing is enabled); rest-conn-roi-qc (S_final); rest-conn-smooth-residuals.
        Test (P4-1): change only run_labels -&gt; declaring stages rerun, run{N} names for the new labels, old-label files retired.
      </decision>
    </topic>

    <topic id="T11-b" title="Template stage (resampling and content hash)">
      <approaches><approach id="A1" label="Template stage present whenever a template is used" feasibility="high" risk="low"><description>Content hash always in the DAG.</description><pros>Template edits always propagate.</pros><cons>A stage that may write no file.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        (1) {type}-template is in the DAG iff any configured output reads template_path. (2) It declares template_path, the template file
        SHA-256 (the only content hash besides motion bytes) and the scan grid; runs 3dinfo -same_grid (first value); grids differ -&gt;
        3dresample -master scan -rmode NN -overwrite -input template and promotes {pre}_{template}_resampled.nii.gz as intermediate; grids
        match -&gt; promotes no file; in both cases its completion entry records the resolved template path as a declared derived value.
        Non-resampling template checks (atlas space, integer ROI content, conn_type label-count rules) stay always-run; the v3.1.0
        staleness branch is removed. (3) Every template consumer (raw-ptseries, parcel extraction stages, parcellated and seed-to-voxel
        connectivity, roi-qc) declares {type}-template upstream and reads the resolved path. (4) A stale resampled file is retired by G2
        when grids come to match. (5) Tests: same-grid template content edit -&gt; template stage and every consumer rerun; mismatched grid
        -&gt; resampled file listed as intermediate and used; grid becomes matched -&gt; resampled file retired and consumers rerun with
        template_path; no template-reading output -&gt; no template stage.
      </decision>
    </topic>

    <topic id="T11-raw" title="Raw-ptseries extraction">
      <approaches><approach id="A1" label="Unscaled from supplied scans; PSC variant when scaling" feasibility="high" risk="low"><description>Symmetric across types.</description><pros>Consistent semantics.</pros><cons>rest filename semantics change.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        All three types extract raw ptseries from the supplied unscaled scans (task: S_pre runs; rest: S_final runs), writing
        {extract_out_file_pre}_raw_ptseries.csv (rest: {extract_out_file_pre}_run{N}_raw_ptseries.csv). When extract_raw_ptseries and
        scale_to_psc are both true, also {extract_out_file_pre}_raw_psc_ptseries.csv (rest: _run{N}_raw_psc_ptseries.csv), the ROI average of
        the prep stage's voxelwise PSC series (multi-run task: per-run PSC concatenated per T3). scale_to_psc false -&gt; unscaled only;
        extract_raw_ptseries false -&gt; nothing. Aggregation per T11-nz. Model-derived extractions are unaffected. Documentation per
        T11-rawdoc.
      </decision>
    </topic>

    <topic id="T11-demean" title="Demeaning/detrending finding">
      <approaches><approach id="A1" label="Finding" feasibility="high" risk="low"><description>Audit result.</description><pros>Grounds T3/T11-psc.</pros><cons>None.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        The package never demeans before PSC or raw extraction; mean/baseline is handled inside model fits (task -polort A; rest
        3dTproject/3dBandpass). Upstream sources (fmri-preproc, fmri-proc-orchestrator, ABCD/fMRIPrep) supply brain-masked, non-demeaned,
        non-detrended positive-baseline BOLD. The ABCD N=30 test runs are outdated and are not referenced.
      </decision>
    </topic>

    <topic id="T11-polort" title="rest_conn detrending per context">
      <research>3dTproject help ("no sense to use pp greater than 2" when bandpassing; "-polort -1 is not advised (if data mean != 0)"); quadratic trends not spanned by sinusoids; 3dBandpass detrends by default; Ciric et al. (2017) detrend linear+quadratic. Synthetic AFNI 26.0.09 (true r = 0): simultaneous polort -1 with bandpass gave mean pair r +0.045/+0.244 vs -0.004 at polort 2; lowpass-only +0.589 vs +0.008; sequenced -nodetrend +0.072/+0.352 with edge amplitude ratio up to 2.35.</research>
      <approaches><approach id="A1" label="Per-context polort" feasibility="high" risk="low"><description>Detrend where filtering does not.</description><pros>Removes spurious correlation.</pros><cons>Numerical change.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        Simultaneous 3dTproject: -polort 2 if bandpass[0] &gt; 0; -polort 1+floor(D/150) per run if bandpass[0] = 0. Sequenced: remove
        -nodetrend from both 3dBandpass calls (rest_conn L258 and bandpass_filter_1d_afni); keep -polort -1 in NTRP and final regression.
        Task pipelines and motion notch unchanged. DOF per T6d. Docs: remove rest_conn L40-41 stale claims; document per-context polort and
        rationale. CHANGELOG: rest residuals and per_run_dof change in both backends.
      </decision>
    </topic>

    <topic id="T11-psc" title="Percent-signal-change scaling">
      <research>afni_proc.py default scale block (cap 200); voxelwise scaling preferred for inhomogeneous baselines; r invariant to per-voxel scaling. E1 (reviewed evidence, KI-005): masked voxels with mean &lt;= 0 max 1.33% over 24 real runs.</research>
      <approaches><approach id="A1" label="Voxelwise AFNI formula with demeaned-input gate" feasibility="high" risk="low"><description>Unchanged expression.</description><pros>Standard.</pros><cons>Partial offsets not detected.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        Voxelwise PSC is the only scaling; expression min(200,a/b*100)*step(a)*step(b) unchanged. In the prep stage, when scale_to_psc is
        true: InputError if at least 25% of a run's masked voxels (AUD5-4) have temporal mean &lt;= 0 (documented basis: half the expected
        fraction under demeaning, where about 50% of voxel means fall at or below zero; no dataset percentages in package docs).
        qc_summary psc_per_run. INPUT_SPEC documents expression, guards, cap, QC fields and the accepted limitations (25% is a margin
        convention; partial offsets and already-scaled input are not detected; no warning tier below 25%, guarded counts reported).
      </decision>
    </topic>

    <topic id="T11-nz" title="Zero handling in parcel aggregation">
      <research>v3.1.0: 3dROIstats -nz vs zero-including 3dNetCorr averaging differed up to 0.65 in r with 1% scattered zeros. 1ddot reproduces 3dNetCorr r within 4e-5; partial correlation within 5e-5; capped atanh within 4.4e-5.</research>
      <approaches><approach id="A1" label="roi_zero_handling, default exclude" feasibility="high" risk="low"><description>One aggregation backend.</description><pros>Consistent.</pros><cons>Breaking.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        Per-analysis roi_zero_handling: exclude (default) or include, with average_type mean or median, applied to every parcel-level
        aggregation (stat_buckets, residuals, raw and raw-PSC ptseries, beta series, rest ptseries, seed series, parcellated connectivity).
        All aggregation via 3dROIstats (exclude: -nz{mean|median} -nomeanout; include: default mean or -median). Parcellated connectivity:
        1ddot on extracted series (r and inverse), partial correlation from the inverse after the T6c gate, Fisher Z capped at 4, C1 null
        handling. qc_summary roi_coverage. CHANGELOG breaking (cites the 0.65 r discrepancy as the fixed bug). Contract tests on synthetic
        data in include mode vs 3dNetCorr, absolute tolerance 1e-3, for r, partial correlation and Fisher Z (cap 4) matrices and
        seed-to-voxel r and Z maps (-ts_wb_corr/-ts_wb_Z), Z compared where |r| &lt; 0.999329 and the cap checked separately. 3dNetCorr is a
        test-only dependency.
      </decision>
    </topic>

    <topic id="T11-lowbase" title="Low-baseline voxels in parcel averages">
      <approaches><approach id="A1" label="Plain aggregation plus QC" feasibility="high" risk="low"><description>No weighting or exclusion.</description><pros>Transparent.</pros><cons>Low-baseline voxels remain in means.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        Model at the voxel level, then aggregate with plain mean/median (no ratio-of-means, weighting, exclusion threshold or parcel-level
        modeling). qc_summary low_baseline per AUD6-5 with definitions per AUD5-4. INPUT_SPEC: voxelwise PSC amplifies noise in inverse
        proportion to a voxel's baseline; median is the robust alternative; 20% is a reporting convention; no dataset percentages.
      </decision>
    </topic>

    <topic id="T11-rawdoc" title="Documentation and notices for T11-raw">
      <approaches><approach id="A1" label="Reconciled docs" feasibility="high" risk="low"><description>Spec, release note, orchestrator item.</description><pros>No silent semantic change.</pros><cons>None.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        INPUT_SPEC defines _raw_psc_ptseries via T11-psc, T11-nz and T11-lowbase (README one-line pointer), including disclosure that
        guard-zeroed and capped voxels count in ROI means. CHANGELOG breaking: rest_conn _run{N}_raw_ptseries.csv is now unscaled under
        default scale_to_psc. Orchestrator item O5.
      </decision>
    </topic>

    <topic id="T11b" title="Final vs intermediate outputs">
      <approaches><approach id="A1" label="output_files + intermediate_files" feasibility="high" risk="low"><description>Two disjoint lists.</description><pros>Minimal API change.</pros><cons>Reclassification is breaking.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        output_files = final products only; FirstLevelResult.intermediate_files: list[str] for every other file the analysis leaves on disk.
        Staging dirs and in-stage temporary files are in neither list. FINAL: {pre}_qc_summary.json; {pre}_timing_errors.json (while it
        exists); min_outlier_epi (all); raw_ptseries and raw_psc_ptseries (rest per run); task_act concat_bucket_stats, concat_bucket_resids,
        bucket_stats_index.json, {ext}_{stat}_bucket.nii.gz, {ext}_{stat}_index.json, {ext}_{stat}_parcellated.csv, {ext}_resids.csv;
        task_conn concat_LSS.nii.gz, concat_LSS.1d, concat_bseries_{cond}.nii.gz, concat_bseries_dmat.x1D, {ext}_pbseries_{cond}.csv,
        {conn}_{cond}_{corr|fishZ|pcorr|pcorr_fishZ}_mat.txt and .nii.gz plus contrasts; rest_conn concat_residual_dtseries,
        run{N}_residual_dtseries (keep_run_res_dtseries), {ext}_residual_ptseries.csv, {conn}_* connectivity; _s{N}mm siblings inherit the
        class. INTERMEDIATE: ledger.jsonl; psc and mean volumes; concat_scan; run_intersect_mask; resampled template; smoothing mask;
        smoothed per-run inputs; onset txt; beta_onsets; preflight_dmat; estimability_dmat; REML_cmd files; censor .1D and 1d_tool side
        files; motion_prepared; notch/interp/bp .1D; derivative txt; connectivity-feed series; {pre}_sequenced_intermediates/run{N}/ when
        kept. Catch-all: an unlisted AFNI side file is intermediate, except a design matrix of a final model output is final. Contract
        test: every analysis-produced file in out_dir (recursive walk) appears in exactly one list; lists disjoint; CLI log file excluded.
        CHANGELOG/INPUT_SPEC: PSC/mean/censor/motion reclassification is breaking; INPUT_SPEC:490-531 rewritten; INPUT_SPEC:501 uses the code
        name _{stat}_parcellated.csv. Orchestrators decide whether to count min_outlier_epi.
      </decision>
    </topic>

    <topic id="SMOOTH" title="Spatial smoothing inside the package (SMOOTH-ARCH, AUD-S, P4c, AUD5-8)">
      <research>SPM, FEAT, afni_proc.py and nilearn smooth before the first-level GLM; fMRIPrep does not smooth; XCP-D never parcellates smoothed data; Alakorkko et al. (2017) and XCP-D advise against parcellating smoothed data; Friedman et al. (2006), NeuroImage 32:1656-1668, smoothness equalization; Cox et al. (2017) ACF model; CONN extracts ROI series from unsmoothed volumes. AFNI 3dBlurToFWHM help: "results (measured via 3dFWHMx) are within 10% of the goal"; 3dFWHMx help: -detrend not needed for errts series.</research>
      <approaches><approach id="A1" label="First-level voxelwise-only smoothing" feasibility="high" risk="low"><description>3dBlurToFWHM -ACF with a data-derived mask.</description><pros>Smoothness equalization; parcel outputs never smoothed.</pros><cons>Extra stages.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        (1) Principles: parcel-level extraction (including seed series), raw ptseries and parcellated connectivity never consume smoothed
        data; smoothing feeds only voxelwise activation maps, voxelwise beta series and residuals, and seed-to-voxel target maps; contract
        test: no parcel-level stage declares a smoothing stage upstream. Orchestrators drop smoothing.
        (2) Config block smoothing: {enabled, fwhm}; fwhm required when enabled. Validation (ConfigError naming smoothing.fwhm and the value),
        in order: not bool; YAML int or float, not string; finite; &gt; 0; at most two decimals via
        Decimal(repr(float(v))).as_tuple().exponent &gt;= -2 (one-line code comment: relies on shortest round-trip repr). No upper bound
        (INPUT_SPEC: value used as given). ResolvedConfig stores fwhm as float (6 and 6.0 give identical hashes and filenames).
        (3) Naming: canonical string format(Decimal(repr(fwhm)).normalize(), "f"); token "_s" + canonical with "." -&gt; "p" + "mm",
        immediately before the extension (e.g. {pre}_concat_bucket_stats_s6mm.nii.gz, _s6p5mm). Frozen T8 names always hold unsmoothed
        outputs; smoothed outputs exist only when enabled. The same canonical string is passed to 3dBlurToFWHM -FWHM and logged.
        (4) Method: 3dBlurToFWHM -FWHM fwhm -ACF -mask per run; mask = voxels with max &gt; min in every run of the stage's run set on the
        unscaled input (task: S_pre; rest: S_final); never automask (input arrives brain-masked, so its nonzero support is the correct
        mask; an intensity-threshold mask can only remove in-brain voxels; 3dBlurToFWHM zeros outside its mask).
        (5) Stages: task-act-smooth / task-conn-smooth declare smoothing.enabled, smoothing.fwhm, scan_path, scan_paths, run_lengths,
        run_labels, scale_to_psc, S_pre; upstream prep; blur the unscaled S_pre runs (Mode B via sub-brick selectors), then per-run PSC of
        the smoothed copy when scale_to_psc is true (emits no psc_per_run). task-act-glm-smooth declares everything task-act-glm declares
        (shared always-run derived files, not recomputed) plus smoothing.*; upstream task-act-smooth; produces only _s{N}mm voxelwise
        outputs. task-conn-beta-series-smooth declares everything task-conn-beta-series declares plus smoothing.*; upstream task-conn-smooth
        and task-conn-design-matrix (shared design matrix and survival table); produces only _s{N}mm voxelwise outputs.
        rest-conn-smooth-residuals declares smoothing.*, scan_paths, run_lengths, run_labels, S_final; upstream rest-conn-concat or
        rest-conn-residuals-concat; per S_final run, sub-brick selection of the concatenated residual via the S_final run-label offset map,
        blur per run (residual is the blurmaster), 3dTcat into the _s{N}mm sibling; keep_run_res_dtseries true -&gt; per-run _s{N}mm siblings
        kept. Seed-to-voxel: seed series from unsmoothed data via 3dROIstats; r against the target (smoothed when enabled) per C1(5).
        (6) QC per run per smoothing stage: 3dFWHMx -mask &lt;stage smoothing mask&gt; -acf NULL on the series passed to 3dBlurToFWHM
        (acf_fwhm_input_mm) and on its output (acf_fwhm_output_mm); value = fourth number of the ACF line (combined FWHM); classic line
        unused; -detrend for task smoothing stages, omitted for rest-conn-smooth-residuals; nonzero exit or unparseable ACF line -&gt;
        ToolExecutionError; side files in-stage temporary. SMOOTH_FWHM_OFF_TARGET (medium) if output outside +/-10% of target;
        SMOOTH_INPUT_ABOVE_TARGET (medium) if input above target. INPUT_SPEC: ACF estimates are less reliable for short runs and small masks.
        (7) Tests: fwhm formatting 6-&gt;_s6mm, 6.0-&gt;_s6mm, 6.5-&gt;_s6p5mm, YAML 6.50-&gt;_s6p5mm, 6.25-&gt;_s6p25mm, 0.5-&gt;_s0p5mm, 10-&gt;_s10mm,
        12.0-&gt;_s12mm; ConfigError for 6.125, 0, -1, true, "6", .nan, .inf; 6 vs 6.0 identical smoothing-stage hashes; changing only fwhm
        reruns exactly the smoothing stages and their downstream; rest with keep_run_res_dtseries false and smoothing on produces the
        smoothed concatenated residual; sub-brick-selector blurring equals per-file blurring (rest and task Mode B); after 3dBlurToFWHM
        -mask no in-mask voxel is zero and no out-of-mask voxel is nonzero; 3dFWHMx parser takes the fourth ACF value; within/outside 10%
        warning behavior; mocked 3dFWHMx failure -&gt; ToolExecutionError; rest stage command has no -detrend, task stage commands do; rest
        smoothing mask with a run_failed run uses S_final only.
      </decision>
    </topic>

    <topic id="P4a" title="Min-outlier EPI stage">
      <approaches><approach id="A1" label="Dedicated ledgered stage, final run set" feasibility="high" risk="low"><description>Reads supplied unscaled scans.</description><pros>Decoupled from PSC and smoothing.</pros><cons>Reruns when the run set changes.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        (1) {type}-min-outlier-epi declares scan_path, scan_paths, run_lengths, run_labels and S_final; runs after the last
        exclusion-producing step (task: after {type}-nuisance; rest: after the residual stages); reads only the supplied unscaled scans from
        the run()-entry config copy (Mode A files; Mode B sub-brick selectors); per S_final run: 3dToutcount -automask -fraction -quiet,
        first minimum, 3dbucket. (2) Naming: K_supplied = 1 task -&gt; {pre}_min_outlier_epi.nii.gz; K_supplied &gt; 1 task and all rest -&gt;
        {pre}_run{N}_min_outlier_epi.nii.gz (N = label); final outputs; excluded runs get no file. (3) Selected TR index and outlier
        fraction logged at INFO; no qc_summary key. (4) Tests: Mode A and Mode B identical files; labels [1,3,4] -&gt; run1/run3/run4;
        exclusion for each reason (including mocked run_failed) -&gt; no file and a stale one retired; changing only scale_to_psc or
        smoothing does not rerun the stage.
      </decision>
    </topic>

    <topic id="P4d" title="Files left by excluded runs">
      <approaches><approach id="A1" label="Per-reason rule" feasibility="high" risk="low"><description>Excluded runs never have finals.</description><pros>Diagnosable failures.</pros><cons>None material.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        (1) No excluded run has final outputs, for any reason. (2) insufficient_uncensored_trs (task) and dof_below_1 (rest): no files of
        any class (guaranteed by the nuisance steps promoting S_pre only and by S_pre-declaring stages processing S_pre only). (3) run_failed
        (rest only): intermediates promoted before the failure (notch .1D, censor .1D + side files, prepared motion from rest-conn-nuisance;
        mean/psc volumes from rest-conn-prep) are retained and listed in intermediate_files; the failed stage promotes nothing (no staged
        record, no completion entry); in per-run mode its staging dir .staging_{pre}_rest-conn-residuals-run{N}/ is left for diagnosis, is in
        neither list, and is deleted before the stage next runs (C4) or by remove_previous; in concat mode diagnosis relies on
        failed_runs.error and the log (AUD5-6); failed_runs records the error. (4) Expected paths per AUD6-2. (5) INPUT_SPEC states the
        per-reason rule. (6) Tests: mocked residuals-run3 failure -&gt; intermediates listed, no run3 finals (including no min-outlier EPI),
        failed_runs entry, staging dir present after run(); a later run() without the failure deletes the leftover staging dir, reruns
        that stage and produces run3 finals. (7) All S_pre runs fail -&gt; ToolExecutionError (exit 4) per AUD5-3.
      </decision>
    </topic>

    <topic id="AUD5-3" title="rest_conn errors when no run survives">
      <approaches><approach id="A1" label="Cause-specific exceptions" feasibility="high" risk="low"><description>ModelError vs ToolExecutionError.</description><pros>Actionable exit codes.</pros><cons>Exit-code change.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        (1) S_pre empty (every run dof_below_1): rest-conn-nuisance raises ModelError (exit 5) after evaluating all runs, naming each run
        label with its computed DOF; no residual stage runs; no nuisance file promoted; mirrors T4. (2) S_pre non-empty and S_final empty:
        ToolExecutionError (exit 4); message also lists dof_below_1 runs. Precedence: S_pre empty first. (3) Replaces the v3.1.0 combined
        error (rest_conn_first_level.py:453-457); CHANGELOG breaking exit 4 -&gt; 5 for the all-DOF case. (4) Exception context carries
        excluded_runs [{run, reason}]. (5) Neither case writes output lists or qc_summary; leftovers handled by the next run() via G2/C4 or
        by remove_previous. (6) Tests: all DOF &lt; 1 -&gt; exit 5, no residual stage, no nuisance promoted, context lists every run as
        dof_below_1; one dof_below_1 and the rest run_failed -&gt; exit 4 with both reasons in message and context; one run surviving -&gt; no
        error.
      </decision>
    </topic>

    <topic id="AUD5-6" title="Run failure inside rest-conn-residuals-concat">
      <approaches><approach id="A1" label="Continue, record, never reuse with failures" feasibility="high" risk="low"><description>Retry parity with per-run mode.</description><pros>Transient failures retried.</pros><cons>Concat-mode rerun repeats all runs.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        (1) A per-run backend failure inside the stage: RUN_FAILED (high), failed_runs {run, error} with command, purpose and stderr,
        processing continues; 3dTcat concatenates S_final runs only; the failed run's in-stage files are discarded with the staging dir.
        (2) If at least one run succeeds, the stage promotes the concatenated residual and writes its completion entry with qc.failed_runs
        and the RUN_FAILED warnings. (3) Such an entry is never reused (rerun trigger (e), T11-ledger); in per-run mode a failed stage has no
        completion entry; both modes retry every invocation. (4) failed_runs and RUN_FAILED are always produced by the current invocation:
        stages that executed and failed in this invocation contribute qc and warnings from their in-memory result under the AUD5-5 merge
        rule. (5) Concat mode S_final = S_pre minus the stage's failed runs. (6) All runs fail -&gt; ToolExecutionError (exit 4), no completion
        entry. (7) Tests: concat mode mocked run 3 failure -&gt; residual and smoothing offset map contain runs 1,2, failed_runs entry,
        excluded_runs run_failed, status warning; next invocation without the failure reruns and includes run 3; persistent failure reruns
        with the same result; keep_run_res_dtseries true vs false give identical excluded_runs, failed_runs and status; all fail -&gt; exit 4.
      </decision>
    </topic>

    <!-- ======================= RESTART SAFETY ======================= -->

    <topic id="G1" title="Result lists assembled from the ledger">
      <approaches><approach id="A1" label="Ledger-derived assembly" feasibility="high" risk="low"><description>Identical lists for reuse and rerun.</description><pros>Complete on partial reruns.</pros><cons>Format bump.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        (1) Completion entries carry outputs [{path, class: final|intermediate}] and ledger_format 2. (2) At the end of a successful run()
        (ordering per AUD6-3): output_files/intermediate_files = union over every current-DAG stage of the outputs of its valid completion
        entry whose recorded hash equals the stage's hash in this invocation (executed or reused now; a stage that executed and failed now
        contributes nothing even if an older entry exists) + always-run outputs from each current step's latest staged record validated
        this run (G3(6)) + the ledger file as intermediate + {pre}_qc_summary.json from its planned path (AUD6-3). (3) Never assembled from
        executed code paths. (4) Unreadable entries per T11-ledger(3). (5) Tests: full-reuse rerun identical lists; partial rerun
        (downstream-only change) identical lists; old-format ledger line -&gt; warning + rerun.
      </decision>
    </topic>

    <topic id="G2" title="Retirement sweep for orphaned outputs">
      <approaches><approach id="A1" label="Ledger-history sweep with expected-path cross-check" feasibility="high" risk="med"><description>Delete only recorded, unlisted, unexpected paths.</description><pros>Never touches user files.</pros><cons>Full-history reader.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        Sweep at the end of every successful run() (ordering per AUD6-3). (1) Full-history ledger reader (staged and completion records);
        last-writer-wins read kept for reuse. (2) Independent cross-check: expected-path set from the current config and this invocation's
        run sets and surviving conditions (no ledger): each expected per-run path is generated from the run set of the step or stage that
        produces it (S_pre: nuisance steps, prep, task smooth and raw-ptseries; S_final: rest residual stages and every S_final-declaring
        stage); expected task_act onset files for surviving conditions only; contrasts with a dropped condition not expected; the resampled
        template expected only when produced; every expected path existing on disk must be in the lists, else GuardError before any
        deletion. (3) Delete only paths in this analysis's ledger history AND not in current lists AND not expected; T8 frozen names never
        deleted; each deletion logged at INFO, listed in retired_outputs and recorded in the ledger. (4) Deletion failure -&gt;
        RETIREMENT_FAILED (high), retried next run. (5) Tests: fwhm 6 -&gt; 8 retires _s6mm; smoothing disabled retires all smoothed; condition
        removed retires its outputs; user file never touched; reused outputs never retired; partial rest per-run rerun keeps other runs;
        omitted current path raises before deletion; rest run 3 succeeds then fails -&gt; stale run3_residual_dtseries retired, retained
        intermediates listed, no GuardError, old completion entry unused.
      </decision>
    </topic>

    <topic id="G3" title="Uniform write protocol">
      <approaches><approach id="A1" label="Stage, validate, record, replace, complete" feasibility="high" risk="low"><description>Every file through staging.</description><pros>Crash-safe.</pros><cons>Validation cost.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        (1) Every file (ledgered stages and always-run steps): write into .staging_{pre}_{step}/ -&gt; validate -&gt; append+fsync staged record
        {record_type: staged, step, outputs: [{path, class}], ledger_format: 2} -&gt; os.replace into out_dir -&gt; ledgered stages then append
        the completion entry. (2) Validation by producer: .nii.gz full gzip decompress + 3dinfo grid check vs scan grid (and nvols where
        known); Python-written text (onsets, CSVs, JSON incl. qc_summary and timing_errors) read back byte-equal; AFNI-written text (censor
        and enorm .1D, .x1D, 1ddot/3dROIstats outputs) parsed with the package reader + row/column checks (censor rows = total TRs; matrices
        N x N); REML_cmd per C2. validate_onset_file_format (first_level_utils.py:480-507) deleted. Failure classes per T11-ledger(6).
        (3) Always-run steps append a staged record only when their path set differs from the latest (including an empty set); cleanup
        tracking, not content integrity. (4) write_qc_summary stops swallowing OSError (first_level_utils.py:1536-1537). (5) remove_previous
        deletes every existing path in any staged or completion record of the full history plus all own staging dirs, ledger file last;
        recorded paths that no longer exist are skipped; failed deletion raises. (6) Always-run list paths come from each current step's
        latest staged record validated this run; a listed path missing or in more than one step -&gt; GuardError. (7) The G2 sweep reads the
        full history. (8) Tests: crash after staged record before move; crash after move before completion then config change retires;
        validation failure leaves no record or file; truncated .gz/.1D/.csv/.x1D raise; wrong-grid NIfTI raises; unchanged rerun appends no
        always-run records; A-&gt;B-&gt;A lists; remove_previous complete and user file untouched; interrupted remove_previous completes; qc write
        failure raises.
      </decision>
    </topic>

    <topic id="G4" title="Refuse to run over unrecorded files; naming invariant">
      <approaches><approach id="A1" label="InputError; never auto-delete" feasibility="high" risk="low"><description>Detect pre-4.0.0 outputs.</description><pros>No silent mixing.</pros><cons>Migration step.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        (1) At run() start, before remove_previous and any write, if this analysis's ledger is absent: collect out_dir entries (recursive
        into matching dirs) starting with {pre}_, {extract_out_file_pre}_ or {conn_out_file_pre}_, plus the pre-4.0.0 unprefixed names
        ({template}_resampled.nii.gz per configured template; _sequenced_intermediates/), excluding the CLI log file and paths recorded in
        other ledger_format-2 ledgers in out_dir; any remaining -&gt; InputError before any write (count, first 20 paths, statement that no
        ledger records them; remove_previous cannot remove them; use an empty out_dir or remove the listed paths). (2) Naming invariant:
        every package-created path in out_dir starts with an analysis prefix, except staging dirs .staging_{pre}_{step}/;
        {pre}_sequenced_intermediates/run{N}/; staging cleanup and remove_previous touch only their own analysis. (3) CHANGELOG, README,
        INPUT_SPEC. (4) Tests: 3.1.0-style dir (including only-unprefixed-template and only-_sequenced_intermediates) -&gt; InputError, nothing
        written; empty dir runs; shared out_dir with string-prefix-overlapping prefixes no error and no cross interference; prefixed log /
        unprefixed user file no error; naming contract test.
      </decision>
    </topic>

    <!-- ======================= QC SUMMARY ======================= -->

    <topic id="AUD5-5" title="QC values and warnings of reused stages">
      <approaches><approach id="A1" label="Persist qc and warnings in completion entries" feasibility="high" risk="low"><description>Replay on reuse.</description><pros>Fresh and reused runs report identically.</pros><cons>First 4.0.0 run against an old ledger reruns all stages.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        (1) Every completion entry carries qc (the qc_summary fragments the stage computed) and warnings [{code, severity, message}]; none -&gt;
        {} and []. (2) qc_summary = always-run QC merged with the qc fragments of the current-hash valid completion entry of every
        current-DAG stage (G1(2)) plus in-memory fragments of stages that executed and failed now (AUD5-6). (3) Merge by key type:
        list-of-records keys combine records from all contributing stages (including per-run instances), sorted by identity fields (run
        label ascending, then condition, output or roi); identical identity -&gt; GuardError; a scalar or object key from more than one stage
        -&gt; GuardError; the INPUT_SPEC qc table records each key's type and producer (AUD6-1). (4) Reused stages' warnings are re-emitted
        unchanged into the accumulator (warnings and status identical to a fresh run), logged at their original level prefixed
        "[reused stage &lt;label&gt;]". (5) Missing qc or warnings -&gt; LEDGER_ENTRY_UNREADABLE and rerun. (6) Tests: full-reuse rerun gives
        qc_summary identical except reused_stages, identical warnings and status; partial rerun keeps reused-upstream QC identical; a reused
        stage that emitted high NULL_ROI keeps status warning; per-run failed_runs and psc_per_run merge in run-label order; duplicate
        identity -&gt; GuardError; scalar key from two stages -&gt; GuardError.
      </decision>
    </topic>

    <topic id="AUD-Q" title="qc_summary key schema, producers and run coverage">
      <approaches><approach id="A1" label="Full schema locked" feasibility="high" risk="low"><description>Complete key table with producers.</description><pros>Drift-testable.</pros><cons>Breaking changes.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        Conventions: snake_case; lists of records with identity fields (run = run label, roi = template label, condition, output =
        filename), never position-keyed; an undefined value is null with sibling &lt;key&gt;_null_reason; a group of fields that are always null
        together shares one &lt;group&gt;_null_reason (used only for such groups); keys absent when their producer is absent. Each key has exactly
        one producer; INPUT_SPEC tabulates every key path with type, meaning, analysis types, producer and run coverage; drift contract test
        (emitted key paths on synthetic fixtures equal the table) and producer contract test.
        Producer {type}-qc: analysis_type, fd_threshold, censor_prev_tr, bandpass (rest), bandpass_backend (rest; simultaneous or
        sequenced), contrast_labels (task_conn), reused_stages, retired_outputs, provenance {package_version, schema_version, afni_version,
        python_version, numpy_version, pandas_version}, excluded_runs [{run, reason}] (from the single-source run sets).
        Producer {type}-nuisance: n_trs_total, n_trs_censored, pct_censored (task: the model censor series, S_pre runs; rest: summed over
        every supplied run; CENSOR_HIGH evaluated on these); rest: per_run_censoring [{run, n_trs_total, n_trs_censored, pct_censored}] and
        per_run_dof [{run, dof, bandpass_dim, bandpass_dim_null_reason, n_stopband_regressors, n_stopband_regressors_null_reason}], both for
        every supplied rest run; dof is always the computed value (below 1 for dof_below_1 runs; pre-regression value for run_failed runs);
        sequenced backend: bandpass_dim = T6d passband dimension, n_stopband_regressors null with reason sequenced_backend; simultaneous:
        n_stopband_regressors = parsed K, bandpass_dim null with reason simultaneous_backend; an excluded run's dof describes that run alone.
        Producer task-act-preflight / task-conn-estimability: dof (task, matrix-derived).
        Producer {type}-estimability: trials [{run, condition, onset, estimability, survived, reason, beta_series_position}] for every
        supplied run, reason null if survived else one of run_excluded, no_in_run_support, fully_censored, beta_series_position 0-based for
        task_conn surviving trials else null; per_condition_trial_counts and per_condition_surviving_trials (dicts keyed by condition label,
        documented legacy form); per_condition_run_counts [{condition, run, n_trials, n_surviving}].
        Producer {type}-prep: psc_per_run (PSC on; S_pre) [{run, n_mask_voxels, n_guarded_voxels, pct_guarded_voxels, n_capped_voxels,
        pct_capped_voxels, n_nonpositive_mean_voxels, pct_nonpositive_mean_voxels}], unsmoothed only.
        Producer smoothing stages: smoothing_per_run [{run, fwhm_target_mm, acf_fwhm_input_mm, acf_fwhm_output_mm, mask_n_voxels,
        mask_fov_fraction}] over the stage's run set.
        Producer residual stages: failed_runs (rest) [{run, error}].
        Producer {type}-connectivity: pcorr_rank_checks [{condition (task_conn only), n_rois, rank, n_timepoints, skipped}]; null_rois
        [{condition (task_conn only), output, rois}]; null_seed_conditions [{condition}] (task_conn); zero_variance_target_voxels [{output,
        n_voxels}].
        Producer {type}-roi-qc: roi_coverage [{run, roi, n_voxels (atlas count), nonzero_fraction (series entering the model)}];
        low_baseline [{run, roi, low_baseline_fraction, median_baseline_ratio, low_baseline_null_reason}] per AUD6-5; run coverage: the
        roi-qc run set.
        CHANGELOG breaking: per_run_censoring and per_run_dof shapes; low_baseline record form; trials reason vocabulary; new keys.
      </decision>
    </topic>

    <topic id="AUD3-R" title="Exclusion reason vocabulary">
      <approaches><approach id="A1" label="Closed three-value vocabulary" feasibility="high" risk="low"><description>excluded_runs reasons.</description><pros>Consistent.</pros><cons>None.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        excluded_runs lists every supplied run that does not enter the final model; reason in {insufficient_uncensored_trs (task, T4),
        dof_below_1 (rest, T6d), run_failed (rest, T6e/AUD5-6; details in failed_runs)}; exclusion reasons appear only in excluded_runs. Test:
        each exclusion path yields its reason.
      </decision>
    </topic>

    <topic id="AUD5-4" title="Masked voxels and brain-mask median">
      <approaches><approach id="A1" label="Per-run non-constant set" feasibility="high" risk="low"><description>Same criterion as T3/smoothing; no automask.</description><pros>Consistent with the automask ban.</pros><cons>Assumes brain-masked input.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        (1) Masked voxels of a run = voxels with max &gt; min over that run's unscaled supplied series (per-run non-constant set), not the T3
        run-intersection mask; used by the T11-psc sentinel, the AUD6-5 null rule and psc_per_run. (2) Brain-mask median of a run = median of
        the voxelwise temporal mean (3dTstat -mean, unscaled) over that run's masked voxels; {pre}_run{N}_mean reused when present. (3) Per
        parcel per run: low_baseline_fraction = fraction of the ROI's masked voxels with temporal mean below 0.2 x brain-mask median;
        median_baseline_ratio = median of those voxels' temporal means / brain-mask median. (4) QC-only mean volumes are in-stage temporary
        files; no new AFNI binary; INPUT_SPEC states both definitions and that they assume brain-masked input. (5) Tests: constant-zero
        voxels excluded from n_mask_voxels; reused mean volume gives values identical to in-stage computation; runs with differing
        non-constant sets use their own sets.
      </decision>
    </topic>

    <topic id="AUD6-1" title="roi-qc stage">
      <approaches><approach id="A1" label="Dedicated ledgered stage" feasibility="high" risk="low"><description>Single producer for roi_coverage and low_baseline.</description><pros>No merge collisions.</pros><cons>One more stage.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        {type}-roi-qc exists iff any configured output reads template_path (including the seed-to-voxel binary seed mask, label 1); declares
        template_path, roi_zero_handling, scan_path, scan_paths, run_lengths, run_labels, scale_to_psc and its run set (task: S_pre; rest:
        S_final); upstream {type}-template and {type}-prep (rest: runs after the residual stages); writes no files; nonzero_fraction on the
        series entering the model (PSC series when scale_to_psc is true; INPUT_SPEC: describes the model-input series, not each output's
        zero pattern); low_baseline on the unscaled series. Tests: producer contract; absent without a template-reading output; reruns on
        roi_zero_handling or run-set change, reused otherwise; full task_conn configuration (smoothing, parcellated pcorr, seed-to-voxel)
        yields no merge GuardError.
      </decision>
    </topic>

    <topic id="AUD6-5" title="low_baseline null semantics">
      <approaches><approach id="A1" label="Record-level nulls" feasibility="high" risk="low"><description>Per (run, roi) reason.</description><pros>Mixed runs representable.</pros><cons>Breaking vs v3 docs.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        (1) When {type}-roi-qc exists, low_baseline is a list with one record per (run in the roi-qc run set, template label); no top-level
        null. (2) Record {run, roi, low_baseline_fraction, median_baseline_ratio, low_baseline_null_reason}; the two values are always null
        together; reason null when values are present, else nonpositive_baseline (that run fails the 25% sentinel, evaluated regardless of
        scale_to_psc) or no_masked_voxels (the ROI has no masked voxels in that run); when both apply nonpositive_baseline is recorded
        (run-level cause precedes). (3) INPUT_SPEC: shared reason field for always-co-null groups only; the two causes are independent and
        can co-occur. (4) With scale_to_psc true a failing sentinel is an InputError (T11-psc), so nonpositive_baseline occurs only with
        scale_to_psc false. (5) Tests: PSC off, run 1 positive-baseline and run 2 demeaned -&gt; run 1 records valued, run 2 records null with
        nonpositive_baseline; an ROI constant in one run -&gt; no_masked_voxels; record count = runs x labels; demeaned input with PSC off -&gt;
        T3 mask keeps every non-constant voxel; drift test.
      </decision>
    </topic>

    <topic id="AUD6-3" title="End-of-run order">
      <approaches><approach id="A1" label="Lists, cross-check, sweep, qc last" feasibility="high" risk="low"><description>qc path pre-registered.</description><pros>retired_outputs in the same run's qc.</pros><cons>One planned-path exception.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        (1) After every ledgered stage and every always-run step except {type}-qc: assemble the lists per G1, including
        {pre}_qc_summary.json as final from its planned path (exception to G3(6), {type}-qc only). (2) G2 cross-check. (3) G2 sweep; collect
        retired_outputs; failures emit RETIREMENT_FAILED. (4) {type}-qc builds qc_summary (reused_stages, retired_outputs, merged fragments)
        and writes it through G3; a write failure raises (G3(4)) and completed retirements stand. (5) Status from the accumulator; return
        FirstLevelResult with the lists from (1). (6) Failure exits (P4d(7), AUD5-3, T2(2), T4 ModelError) skip (1)-(5) and write no lists or
        qc_summary. (7) Tests: first run into an empty out_dir lists qc_summary and the cross-check passes; rerun with an existing
        qc_summary passes; a retirement appears in the same run's retired_outputs; injected qc write failure after a retirement raises and
        the retirement stays recorded.
      </decision>
    </topic>

    <topic id="WARN" title="Graded warning vocabulary">
      <approaches><approach id="A1" label="Closed code table" feasibility="high" risk="low"><description>Codes, severities, producers.</description><pros>Orchestrators can filter reliably.</pros><cons>Table maintenance.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        INPUT_SPEC closed table {code, severity, producer, condition}. Retained: CENSOR_HIGH (high), COND_DROPPED (medium, T6b floor drop),
        CONTRAST_DROPPED (medium), GS_MISSING (low), RUN_SKIPPED (high, rest dof_below_1), DISCOVERY_COLLISION (medium). 4.0.0:
        UNVALIDATED_VERSION (medium), LEDGER_ENTRY_UNREADABLE (medium), RETIREMENT_FAILED (high), NULL_ROI (high), SEED_NULL (high),
        PCORR_RANK_DEFICIENT (high), RUN_FAILED (high), RUN_INSUFFICIENT_TRS (high; one per T4-excluded run with label and uncensored count),
        DERIV_RUN_BOUNDARY (medium), SMOOTH_FWHM_OFF_TARGET (medium; per run per smoothing stage), SMOOTH_INPUT_ABOVE_TARGET (medium; per
        run per smoothing stage). Removed (CHANGELOG only): TRIALS_FEW, EVENTS_LEGACY, CLI_DEPRECATED, LOCKFILE_ABSENT. AST-based contract
        test: code and severity literals passed to graded_warning (positional and keyword forms) equal the table. Status is 'warning' iff
        any high warning was accumulated in this run(), including re-emitted reused-stage warnings. Tests: each new code emitted by its
        trigger with its severity; a T4 exclusion sets status warning. 3dDeconvolve stderr warnings are logged without a code (T10).
      </decision>
    </topic>

    <!-- ======================= EVIDENCE REVIEW ======================= -->

    <topic id="KI-005" title="Review of empirical checks that fed locked decisions">
      <research>E1 real-data PSC audit (24 runs); E2 AFNI 26.0.09 synthetic equivalence of 1ddot/3dTcorr1D vs 3dNetCorr; E3 synthetic automask dropout; E4 one-run low-baseline figures.</research>
      <approaches><approach id="A1" label="Retain locks; re-ground evidence" feasibility="high" risk="low"><description>Analytic justification, standing tests, qualitative docs.</description><pros>Docs do not rest on unreviewed figures.</pros><cons>No replication of E1/E4.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        T11-psc gate kept with the analytic basis (no dataset percentages in docs); T11-nz and seed-to-voxel backends kept with the KI-005
        contract tests (T11-nz); automask ban kept on analytic grounds with the 3dBlurToFWHM mask integration test (SMOOTH); T11-lowbase
        kept with qualitative INPUT_SPEC text; no re-runs.
      </decision>
    </topic>

    <!-- ======================= RELEASE ======================= -->

    <topic id="T12a" title="Release version">
      <approaches><approach id="A1" label="4.0.0" feasibility="high" risk="low"><description>SemVer major.</description><pros>Correct for breaking changes.</pros><cons>Orchestrators re-pin.</cons></approach></approaches>
      <decision status="decided" chosen="A1">Release 4.0.0 (not 3.2.0); __version__ and pyproject version = 4.0.0. Numerical-output changes listed in CHANGELOG as result-changing.</decision>
    </topic>

    <topic id="T12b" title="schema_version policy">
      <approaches><approach id="A1" label="MAJOR.MINOR.0 of last schema change" feasibility="high" risk="low"><description>Deterministic.</description><pros>Clear.</pros><cons>Fixture updates.</cons></approach></approaches>
      <decision status="decided" chosen="A1">schema_version = '4.0.0'. Policy: MAJOR.MINOR.0 of the package release in which the config schema (ResolvedConfig fields and YAML validation rules) last changed; removal/rename/meaning change/validation tightening ship only in a package major; additions bump minor; patch always 0. Stated in the ResolvedConfig docstring (replacing 'additive-growth') and INPUT_SPEC. Update first_level_config.py:619 and fixtures (conftest.py:96,142,185; test_exceptions.py; test_runtime.py; test_checkpoint.py).</decision>
    </topic>

    <topic id="T12c" title="CHANGELOG">
      <approaches><approach id="A1" label="Keep a Changelog 1.1.0" feasibility="high" risk="low"><description>Root CHANGELOG.md.</description><pros>Standard.</pros><cons>None.</cons></approach></approaches>
      <decision status="decided" chosen="A1">CHANGELOG.md at repo root, Keep a Changelog 1.1.0 (newest first, ISO dates, Added/Changed/Deprecated/Removed/Fixed/Security), whitelisted in .gitignore; empty [Unreleased] at top; the 4.0.0 entry opens with "Breaking changes and migration" and "Changes that affect numerical results"; no back-fill, one line pointing to tags v2.3.0-v3.1.0; the 4.0.0 section is reused verbatim as the GitHub v4.0.0 release body. Entry content: topic CHANGELOG below.</decision>
    </topic>

    <topic id="T12d" title="Documentation process and drift tests">
      <approaches><approach id="A1" label="Code-adjacent docs in /implement; prose docs in /document" feasibility="high" risk="low"><description>Split by proximity to code.</description><pros>Docs match behavior.</pros><cons>Needs the doc-item list.</cons></approach></approaches>
      <decision status="decided" chosen="A1">(1) Module OUTPUTS docstrings, function docstrings, example_config.yaml and tools.lock.yaml updated in the same /implement change as the behavior. (2) README, INPUT_SPEC and CHANGELOG written in one /document pass after the 4.0.0 suite passes, from topic DOC-ITEMS. (3) Drift contract tests: (a) per analysis type, INPUT_SPEC key rows == closed-schema accepted keys including nested dotted names (INPUT_SPEC restructured so every key has a row; YAML blocks illustrative only); (b) every T8 frozen-name constant and T11b final-output pattern appears verbatim in INPUT_SPEC Output Files; (c) qc_summary key paths (AUD-Q); (d) warning code table (WARN). (4) Introspectable per-type allowed-key set; filenames as T8 constants; tests written after these land.</decision>
    </topic>

    <topic id="T12e" title="Events file formats">
      <research>fmri-proc-orchestrator writes tab BIDS *_adjusted_events.tsv (seam2.py:191-248); ABCD writes per-run tab BIDS {run_prefix}_timing.tsv (orchestrate_first_level.py:678); ABCD pre-v4.0 sessions have comma CONDITION *_timing.csv.</research>
      <approaches><approach id="A1" label="Format-agnostic reader indefinitely" feasibility="high" risk="low"><description>Both schemes and delimiters.</description><pros>No deprecation stub.</pros><cons>Two schemes to test.</cons></approach></approaches>
      <decision status="decided" chosen="A1">(1) Delimiter by trial-parse of the header with tab and comma; accept the one yielding a recognized column set; both/neither -&gt; InputError naming the file and the columns found under each. (2) BIDS onset/duration/trial_type takes precedence, else CONDITION/ONSET/DURATION mapped to BIDS. (3) Remove the EVENTS_LEGACY warning and the 4.0.0 removal promise; no 'legacy/deprecated' wording in docstrings, README, INPUT_SPEC (including cond_labels/cond_beta_labels rows) or example_config comments; schemes and delimiters documented as orthogonal and equally supported. (4) BIDS discovery unchanged (*_events.tsv only); explicit task_timing_path any combination. (5) Keep example_subj.timing.csv. (6) CHANGELOG: removal withdrawn (non-breaking). EVENTS_LEGACY tests updated at /test.</decision>
    </topic>

    <topic id="T12f" title="Version provenance and enforcement">
      <research>AFNI forum receipt t/7286 verified.</research>
      <approaches><approach id="A1" label="Minimum versions + validated version + warning" feasibility="high" risk="med"><description>Installable across environments.</description><pros>Flexible.</pros><cons>AFNI numerics may drift above minimum; mitigated by warning and provenance.</cons></approach></approaches>
      <decision status="decided" chosen="A1">(1) The AFNI version probe always runs; undeterminable AFNI version is fatal (T12h). (2) qc_summary provenance block (AUD-Q). (3) All five versions (package, AFNI, Python, numpy, pandas) in every stage hash and every ledger entry; any change reruns all. (4) Enforcement by MINIMUM versions for AFNI, Python, numpy and pandas (supersedes the 2026-08-18 exact AFNI pin). (5) tools.lock.yaml (lockfile_version 2.0.0) records per tool {minimum (ToolVersionError if below), validated (version the suite passed on)}; installed != validated -&gt; UNVALIDATED_VERSION (medium) and recorded in provenance. (6) Python minimum 3.12, validated 3.14; numpy/pandas minimum = validated = versions installed when the 4.0.0 suite passes; no upper bounds. (7) Add 'packaging' to dependencies, used only for numpy/pandas PEP 440 comparison via packaging.version.Version (AFNI via _parse_afni_version int tuple; Python via sys.version_info). (8) Contract test: tools.lock.yaml, pyproject.toml and environment.yaml state identical minimums. (9) Docs: upgrade invalidates the ledger; numerics-changing releases must bump the package version.</decision>
    </topic>

    <topic id="T12g" title="Runtime check function and lockfile packaging">
      <approaches><approach id="A1" label="Packaged lockfile + single runtime check" feasibility="high" risk="low"><description>One check per run().</description><pros>Works under pip install.</pros><cons>Reverses v3.0.0 placement.</cons></approach></approaches>
      <decision status="decided" chosen="A1">(1) Lockfile moves to fmri_first_level_proc/tools.lock.yaml as package data (pyproject), read via importlib.resources, .gitignore whitelist updated; deliberately reverses v3.0.0 T2/A1. (2) One runtime-check function: reads the lockfile, runs preflight_tool_environments (binary list per BINARIES), probes AFNI/Python/numpy/pandas; only probes cached per process; minimum enforcement and UNVALIDATED_VERSION re-evaluated every run() (the warning accumulator is cleared per run()). (3) Called from every pipeline run() and CLI main(); sole source for provenance and hash version components. (4) Cache-reset hook for tests. (5) Per-worker re-probe accepted.</decision>
    </topic>

    <topic id="T12h" title="Remove version-check bypasses">
      <approaches><approach id="A1" label="Remove both bypasses" feasibility="high" risk="low"><description>Checks always enforced.</description><pros>No stubs.</pros><cons>Tests must mock the AFNI probe.</cons></approach></approaches>
      <decision status="decided" chosen="A1">(1) Delete PLACEHOLDER handling; add AFNI-pin format validation mirroring the Python-pin check (runtime.py:208-217) -&gt; ToolUnavailableError. (2) Delete the absent-lockfile bypass and LOCKFILE_ABSENT; missing/unparseable lockfile -&gt; ToolUnavailableError naming the resource path; sequenced after T12g(1); CHANGELOG breaking. (3) AFNI version undeterminable always fatal; no null afni_version or 'unknown' hash token. (4) Delete bypass tests; refactor tests using afni='PLACEHOLDER' as an isolation sentinel to mock the AFNI probe; add tests: non-version AFNI value, missing lockfile, unprobeable AFNI -&gt; ToolUnavailableError.</decision>
    </topic>

    <topic id="BINARIES" title="AFNI binary preflight list">
      <approaches><approach id="A1" label="List equals programs invoked" feasibility="high" risk="low"><description>Contract-tested.</description><pros>No drift.</pros><cons>None.</cons></approach></approaches>
      <decision status="decided" chosen="A1">_AFNI_BINARIES = 3dDeconvolve, 3dTproject, 3dTstat, 3dBandpass, 3dROIstats, 3dresample, 3dinfo, 3dToutcount, 3dbucket, 3dcalc, 3dLSS, 3dTcat, 1d_tool.py, 1dtranspose, 3dAttribute, 1ddot, 3dTcorr1D, 3dBlurToFWHM, 3dFWHMx (3dNetCorr removed; test-only dependency; no 3dAutomask). Contract test: the list equals the set of programs passed to run_afni_command.</decision>
    </topic>

    <topic id="A2" title="Remove the run-first-level CLI alias">
      <approaches><approach id="A1" label="Remove in 4.0.0" feasibility="high" risk="low"><description>Single console script.</description><pros>No deprecated code.</pros><cons>Breaking for alias users.</cons></approach></approaches>
      <decision status="decided" chosen="A1">(1) Delete the pyproject [project.scripts] run-first-level entry; delete run_first_level.py _main_deprecated (L219-221), the CLI_DEPRECATED branch (L131-136) and main()'s cli_name parameter; update docstrings L39-41, L105-106; remove alias text README:47, INPUT_SPEC:607; example_config.yaml:6-8 -&gt; fmri-first-level-proc. (2) CHANGELOG breaking. (3) Tests: exactly one entry fmri-first-level-proc -&gt; fmri_first_level_proc.run_first_level:main; neither CLI_DEPRECATED nor run-first-level occurs in package source, README, INPUT_SPEC or example_config.yaml. Historical .aid/ reports untouched.</decision>
    </topic>

    <topic id="A3" title="environment.yaml and pyproject.toml dependencies">
      <approaches><approach id="A1" label="Align with lockfile minimums" feasibility="high" risk="low"><description>Contract-tested parity.</description><pros>No drift.</pros><cons>None.</cons></approach></approaches>
      <decision status="decided" chosen="A1">(1) environment.yaml: python&gt;=3.12; numpy/pandas &gt;= lockfile minimums; add packaging; keep pyyaml; keep the AFNI-installed-separately comment. (2) pyproject.toml: numpy/pandas &gt;= lockfile minimums; add packaging; keep pyyaml; requires-python &gt;=3.12; packaging and pyyaml carry no minimum. (3) Extend the T12f contract test: package-name sets in pyproject deps and environment.yaml deps equal (excluding python, pip).</decision>
    </topic>

    <topic id="P2-1" title="Remove unused BIDS output helpers">
      <approaches><approach id="A1" label="Delete in 4.0.0" feasibility="high" risk="low"><description>No dead code.</description><pros>Clean.</pros><cons>None.</cons></approach></approaches>
      <decision status="decided" chosen="A1">(1) Delete from bids.py build_bids_output_path(), write_dataset_description(), _ENTITY_ORDER, the json import and bids.py's sanitize_filename_label import (still used by task_conn_first_level.py:492), and their module-docstring text; keep discover_inputs and private helpers; delete TestBuildBidsOutputPath and TestWriteDatasetDescription and imports left unused in tests/test_bids.py. (2) CHANGELOG Removed. (3) Test: fmri_first_level_proc.bids has neither attribute.</decision>
    </topic>

    <topic id="CHANGELOG" title="CHANGELOG 4.0.0 entry content">
      <approaches><approach id="A1" label="Enumerated entries" feasibility="high" risk="low"><description>From all locks.</description><pros>Complete.</pros><cons>None.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        Breaking changes and migration: closed config schema (unknown keys, GLOBAL_ONLY_KEYS in a block, overrides validated, null-as-absent);
        run_labels required (including single runs), Mode A label/filename mismatch InputError, BIDS discovery per-run lists with integer
        ordering and no default labels, template removed from discovery, merge-then-validate mode checks; output_files final-only plus
        intermediate_files (PSC, mean, censor and motion files reclassified); remove_previous ledger-scoped; cross-analysis raw-ptseries reuse
        removed; refusal to run over unrecorded pre-4.0.0 outputs; naming changes ({pre}_sequenced_intermediates, prefixed resampled template,
        staging dirs, prefixed REML_cmd, label-bearing per-run names when K_supplied &gt; 1, rest per-run names labeled at K=1, per-run
        min-outlier EPI names); smoothing moved into the package (orchestrators must drop smoothing); lockfile 2.0.0 minimums, packaged
        lockfile, version-check bypasses removed, Python &gt;= 3.12, packaging dependency; run-first-level alias removed; BIDS output helpers
        removed; task_conn multi-column custom HRF rejected; pcorr with seed_to_voxel ConfigError; qc_summary per_run_censoring and per_run_dof
        shapes, low_baseline record form, trials reason vocabulary; exit-code changes (unparseable AFNI output 1 -&gt; 4; non-numeric template
        data max 1 -&gt; 2; rest all runs dof_below_1 4 -&gt; 5); out-of-range onsets now InputError with {pre}_timing_errors.json; warning codes
        TRIALS_FEW, EVENTS_LEGACY, CLI_DEPRECATED, LOCKFILE_ABSENT removed; ledger_format 2 (an existing out_dir from v3.1.0 is refused).
        Changes that affect numerical results: rest_conn per-context polort and sequenced detrending; rest DOF from dry runs in both backends;
        parcellated zero handling default exclude with the 3dROIstats + 1ddot backend (fixes the v3.1.0 r discrepancy up to 0.65); rest_conn
        raw ptseries unscaled under default scale_to_psc; tr_index floor mapping; estimability (f_j &gt; 0) survival replaces onset-volume
        survival; task_conn survival floor 3; fishZ+pcorr atanh clip with diagonal 4 and PC diagonal +1; seed Z via clipped atanh (|Z| &lt;= 4);
        matrix-derived DOF; run-intersection mask for multi-run task models; run exclusion (T4, T6d).
        Added: run_labels; smoothing block with _s{N}mm outputs and smoothing QC; roi_zero_handling; intermediate_files; ledger-based resume
        and retirement of orphaned outputs; provenance block and new qc_summary keys (bandpass_backend, failed_runs, pcorr_rank_checks,
        null_rois, null_seed_conditions, zero_variance_target_voxels, trials, per_condition_run_counts, psc_per_run, roi_coverage,
        low_baseline, smoothing_per_run, excluded_runs, reused_stages, retired_outputs); {pre}_timing_errors.json; new warning codes; multi-run
        input modes; exception context on run-exclusion and timing errors.
        Fixed: PCB mislabel; seed_to_voxel "_pcorr" was plain correlation; lexical run ordering (run-10); swallowed AFNI failures and bare
        except blocks; write_qc_summary OSError swallowing; 3dDeconvolve writes into the process CWD; stale resampled-template reuse.
        Changed (non-breaking): events-format removal withdrawn (T12e).
      </decision>
    </topic>

    <topic id="DOC-ITEMS" title="Consolidated documentation items (T12d(2))">
      <approaches><approach id="A1" label="Enumerated list for /document" feasibility="high" risk="low"><description>Single checklist.</description><pros>Nothing lost.</pros><cons>None.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        README: (1) one-line pointers for T11-raw/raw_psc, smoothing and run_labels; (2) remove README:10 DOF claim (T6d) and README:16
        resume description (T11-ledger(5)); (3) remove alias text README:47 (A2); (4) relative-path and process-CWD statement (T10); (5) Mode B
        has no per-run discovery (P4-2); (6) BIDS run handling (P2-2); (7) T5b HRF note; (8) G4 migration note.
        INPUT_SPECIFICATION: (9) every config key in a table row incl. nested dotted names, closed schema, run_labels, smoothing,
        roi_zero_handling, schema_version policy (T9, T12b, T12d(3a)); (10) input modes, run identity, discovery rules, Mode B no discovery
        (T1, A1, P2-2, P3-1, P4-2); remove template text at INPUT_SPEC:449; (11) RUNSETS definitions (S_pre, S_final, K_supplied, K_model);
        (12) onset validation rule, timing_errors record schema, known causes, remedy and truncation trade-off (T2); (13) PSC expression,
        guards, cap, sentinel basis and limitations, masked-voxel and brain-mask-median definitions, brain-masked input assumption (T11-psc,
        AUD5-4, KI-005); (14) T3 mask criterion and demeaned-input rule; (15) zero handling and aggregation (T11-nz) and raw_psc definition
        with guard-zero disclosure (T11-rawdoc); (16) low-baseline trade-off text (T11-lowbase); (17) smoothing: principles, validation,
        naming, mask, ACF QC reliability caveat, warnings (SMOOTH); (18) rest DOF per backend, bandpass required, per-context polort,
        replace INPUT_SPEC:295 claim (T6d, T11-polort); remove rest_conn L40-41 stale claims (module docstring, /implement); (19) T6b floors
        and rationale; T7a f_j and the v3.1.0 NaN behavior; T7b pooling statements; T6 rounding change; (20) Output Files: every T8 constant
        and T11b final pattern verbatim, final vs intermediate tables (rewrite INPUT_SPEC:490-531; INPUT_SPEC:501 -&gt; _{stat}_parcellated.csv),
        timing_errors.json; (21) qc_summary key table with type, meaning, analysis types, producer and run coverage, null conventions
        (AUD-Q, AUD6-5); (22) per-reason excluded-run file rule (P4d) and concat-mode diagnosis (AUD5-6); (23) exit-code table (T11-ledger(6),
        AUD5-3, T2); (24) warning code table (WARN); (25) ledger behavior: what triggers reruns (motion bytes, template content, not scan/
        tissue content), upgrade invalidates ledger (T11-ledger(5), T12f); remove INPUT_SPEC:237 cross-analysis reuse; (26) REML_cmd and AFNI
        history staging paths (C2); (27) events formats orthogonal, no legacy wording incl. cond_labels/cond_beta_labels rows (T12e); (28)
        version policy (T12f); (29) remove alias text INPUT_SPEC:607 (A2); (30) G4 refusal and migration.
        Code-adjacent (/implement, T12d(1)): (31) ToolVersionError docstring: "does not match the lockfile pin" -&gt; minimum-version wording;
        (32) remove the stale EXTRACT_DROPPED reference (task_act_first_level.py:510); (33) module OUTPUTS docstrings for all new and
        reclassified outputs; (34) ResolvedConfig docstring schema_version policy; (35) DiscoveredInputs and discover_inputs docstrings
        (bids.py:29-34); (36) run_first_level.py docstrings L39-41, L105-106; (37) example_config.yaml (alias name, smoothing,
        roi_zero_handling, run_labels, no legacy wording); (38) tools.lock.yaml 2.0.0; (39) write_qc_summary and G3 docstrings (cleanup
        tracking, not content integrity).
        CHANGELOG: topic CHANGELOG.
      </decision>
    </topic>

    <!-- ======================= ORCHESTRATORS ======================= -->

    <topic id="ORCH" title="Orchestrator TODO items">
      <research>Both orchestrators read under session-bound grants (2026-10-07). Neither sets derivatives_dirs; neither imports fmri_first_level_proc.bids. File:line references are re-verified read-only at TODO-write time (ORCH-W).</research>
      <approaches><approach id="A1" label="Two TODO files" feasibility="high" risk="low"><description>One per orchestrator root.</description><pros>Each project acts independently.</pros><cons>Lands after the 4.0.0 publish.</cons></approach></approaches>
      <decision status="decided" chosen="A1">
        All items land only after 4.0.0 is published.
        ABCD_fmri_orchestrator_S3: (O1, T9) renderer orchestrator_utils.py:3019-3023 replaces task-block paths wholesale, discarding template
        CSF_path/WM_path and never supplying per-run CSF_paths/WM_paths; supply per-run task tissue paths or reject templates that set them.
        (O2, T9) example_proc_config.yaml/proc_config_final.yaml task blocks mix scan_paths with CSF_path/WM_path: null; remove for clarity.
        (O3, T9) add a test rendering a config through load_and_validate; the F3a legacy-key check becomes redundant but harmless. (O4,
        T10) make generated config paths absolute, then remove os.chdir(session_out) (orchestrate_first_level.py 817-821, 913). (O5,
        T11-rawdoc) rest_conn _run{N}_raw_ptseries.csv keeps its name but holds unscaled values under default scale_to_psc. (SMOOTH) remove
        smoothing from code and config; collect _s{N}mm outputs when enabled; the smoothing block lives in the first-level config template
        (proc_config_final.yaml). (G4) stop relying on remove_previous=True wholesale clear (orchestrator_utils.py:2945-2947, 3009); clear
        first_level_out/{analysis} itself when a clean slate is needed and update the docstring; migration note that a reused 3.1.0 out_dir
        raises InputError. (A1) pass run_labels explicitly (run_label at orchestrator_utils.py:1355 embeds run-{n}). (A4) MIN_UPSTREAM_VERSION
        = '4.0.0' (orchestrator_utils.py:1160) + docstring L1168; every 'fmri_first_level_proc &gt;= 3.2.0' reference -&gt; 4.0.0
        (orchestrator_utils.py:1737, 1823, 2624, 2938; README:67, 197, 209, 215, 296, 377; INPUT_SPEC:56, 172, 211, 301, 461, 557, 577, 724;
        example_orchestrator_config.yaml:64); test on the constant; environment.yaml:30 -&gt;
        git+https://github.com/tjkeding/fmri-first-level-proc.git@v4.0.0; verify_upstream_version also rejects versions &gt;= 5.0.0. (T12e,
        AI-011) correct the CSV-removal statement at README:262 and INPUT_SPEC:424 (removal withdrawn). (T11b, AI-011) min_outlier_epi is a
        final output (per-run labeled names when more than one run is supplied); whether to count it is the orchestrator's call.
        fmri-proc-orchestrator: (O5) as above. (SMOOTH) remove smoothing (retires the 3dmerge -doall bug); collect _s{N}mm outputs. (G4)
        qc.py:99-104 first-glob-match -&gt; per-analysis qc_summary from FirstLevelResult.output_files; reconcile hard-coded
        derivatives/fmri-first-level-proc (pipeline.py:273) with the user-configured out_dir; migration note. (A1) seam2.py _adapt_task
        concatenates without run_lengths/labels -&gt; send per-run lists, or Mode B + run_lengths + run_labels; remove the run=1 default at
        bids.py:65; pipeline.py:240-241 adapter_result has no consumer found: confirm the adapter-to-first-level wiring. (A4)
        pyproject.toml:14 -&gt; fmri-first-level-proc&gt;=4.0.0,&lt;5; tools.lock.yaml -&gt; lockfile 2.0.0 {minimum, validated}.
        Both TODO files carry a section "fmri-first-level-proc 4.0.0 contract changes" (AUD3-O): grouped config (closed schema, override
        validation, run_labels required, smoothing and roi_zero_handling blocks); outputs (output_files final-only with PSC, mean, censor and
        motion in intermediate_files, making ABCD's F5 *_psc filter redundant; _s{N}mm outputs; ledger-scoped remove_previous; per-run
        labeled names; {pre}_timing_errors.json); qc_summary (per_run_censoring, per_run_dof and low_baseline shapes; bandpass_backend;
        matrix-derived dof; f_j &gt; 0 survival; trials reasons; new keys); exit codes and warnings (unparseable AFNI output exit 4; template data
        max exit 2; rest all runs dof_below_1 exit 5; out-of-range onsets InputError exit 2 with the timing record; TRIALS_FEW and
        EVENTS_LEGACY removed; new codes UNVALIDATED_VERSION, LEDGER_ENTRY_UNREADABLE, RETIREMENT_FAILED, NULL_ROI, SEED_NULL,
        PCORR_RANK_DEFICIENT, RUN_FAILED, RUN_INSUFFICIENT_TRS, DERIV_RUN_BOUNDARY, SMOOTH_FWHM_OFF_TARGET, SMOOTH_INPUT_ABOVE_TARGET);
        numerics (rest polort/DOF, parcellated zero handling, task_conn floor 3, floor onset mapping, unscaled rest raw ptseries). Per change,
        consumer sites located read-only at write time; each entry records file:line or "no consumer found"; a found consumer is marked
        "review required" with no prescribed fix; the items above keep their prescribed changes.
      </decision>
    </topic>

    <topic id="ORCH-W" title="Orchestrator TODO destination and grants">
      <approaches><approach id="A1" label="TODO files in each orchestrator root" feasibility="high" risk="low"><description>Session-bound brainstorm grants.</description><pros>Line refs re-verified.</pros><cons>Two grant prompts.</cons></approach></approaches>
      <decision status="decided" chosen="A1">Write TODO_ABCD_fmri_orchestrator_S3_{YYYYMMDD_HHMMSS}.md into the ABCD_fmri_orchestrator_S3 root and TODO_fmri-proc-orchestrator_{YYYYMMDD_HHMMSS}.md into the fmri-proc-orchestrator root (user-confirmed paths); markdown per the 2026-08-12 TODO precedent; per item: source lock, current state file:line, required change, lands only after 4.0.0 is published. Sequence: this report, then two session-bound grants (grants.sh grant --path &lt;root&gt; --skill brainstorm --operations read,write --tools Read,Grep,Glob,Write, each approved via the hook prompt), read-only re-verification of cited file:line references, the TODO files, then the exit sequence.</decision>
    </topic>

  </topics>

  <action_items>
    <item priority="P0" target_mode="brainstorm" description="ORCH-W: request the two session-bound grants, re-verify orchestrator file:line references read-only, write the two TODO files (including the 4.0.0 contract-change sections), then run the brainstorm exit sequence." />
    <item priority="P0" target_mode="implement" description="Implement fmri-first-level-proc 4.0.0 from this report (all topics), including code-adjacent docs per T12d(1) and DOC-ITEMS 31-39." />
    <item priority="P1" target_mode="test" description="Design and run every test enumerated in each topic plus the drift and contract tests (T12d(3a-d), coverage tests T11-ledger(4), BINARIES, WARN, STEPS, AUD-Q producer, RUNSETS single source)." />
    <item priority="P1" target_mode="document" description="After the 4.0.0 suite passes: write README, INPUT_SPECIFICATION and CHANGELOG from DOC-ITEMS 1-30 and topic CHANGELOG." />
  </action_items>

  <next_steps>Finish ORCH-W in this session, then /implement plan from this report, /test, /document, publish v4.0.0, then the orchestrator TODO items.</next_steps>
</brainstorm_report>
