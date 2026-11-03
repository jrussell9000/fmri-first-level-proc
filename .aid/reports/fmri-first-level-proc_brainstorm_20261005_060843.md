<brainstorm_report>
  <meta project="fmri-first-level-proc" mode="brainstorm" timestamp="2026-10-05T10:08:43Z" status="interim-pause" />
  <context_files>
    <file path="ABCD_fmri_orchestrator_S3_cr_20261001_142121.md" relevance="CR report from the sibling orchestrator; source of findings F3-F10 and D3/D4 discussed below. Orchestrator-only items excluded from this report per the original invocation scope; items requiring an upstream-facing change are tracked as ORCH O1-O5 for a separate orchestrator-workspace report." />
  </context_files>

  <note>
    This report is an interim pause point, not a close-out. T1 through T10 are fully locked. T11 is partially
    locked (sub-decisions T11-optA, T11-perstage, T11-table, T11-raw) with three items still open (T11-b,
    T11-c, and the T11-raw doc-additions question). T11b and T12 have not yet been discussed. The session
    resumes directly into T11's open items on the next /brainstorm invocation.
  </note>

  <topics>

    <topic id="T1" title="Multi-run input API (task_act / task_conn)">
      <summary>Dual input pathway for multi-run acquisitions: Mode A (explicit per-run path lists, acquisition
      order, equal length) and Mode B (singular paths + optional run_lengths; omitted run_lengths preserves
      v3.1.0 single-run behavior).</summary>
      <decision status="decided" chosen="dual-mode">
        Reject mixing singular/plural fields, run_lengths with scan_paths, length mismatches, and missing
        files. ResolvedConfig gains plural fields plus run_lengths; a canonical normalized run list is built
        at resolve time. Run-structure checks (summed run_lengths vs. scan volumes and motion/tissue row
        counts; per-run row counts in Mode A; identical TR and grid via 3dinfo) run at pipeline entry and
        raise InputError. BIDS discovery: task types discover all runs and pair by the run- entity across
        input slots, raising InputError on mismatch; the same pairing is applied to rest_conn.
      </decision>
    </topic>

    <topic id="T2" title="Run-boundary model specification">
      <summary>How run boundaries are expressed to 3dDeconvolve/3dLSS and how onset timing is interpreted
      per run.</summary>
      <decision status="decided" chosen="concat-plus-local-times">
        build_decon_base_command takes run_lengths; K&gt;1 appends -concat with 0-based cumulative run-start
        indices; K=1 omits -concat. -local_times is always explicit; every onset file (task_act
        -stim_times/-stim_times_AM1; task_conn nuisance and -stim_times_IM beta files) carries one row per
        run, with a lone '*' for empty runs. Mode A onsets are run-local from the first volume of that run's
        scan; Mode B onsets are relative to the concatenated series and are assigned to a run by cumulative
        start/length, then normalized into one internal event table with a run-index column (reused by
        T6/T7). Run-local onsets outside [0, run end) are excluded with a graded warning; Mode B onsets past
        total duration raise InputError. An existing onset file whose non-empty row count does not match
        n_runs raises InputError naming the file. task_conn beta IM files order rows by beta_cond_order then
        chronologically within condition; the writer builds a single ordered (run, condition, trial)
        sequence from which both the file and the gen_beta_series sub-brick lookup derive, replacing the
        prior contiguous total_used counter. Single-run indices are unchanged from v3.1.0.
      </decision>
    </topic>

    <topic id="T3" title="Per-run PSC scaling, min-outlier EPI, run-intersection mask">
      <summary>Extends PSC scaling, min-outlier-EPI selection, and masking to the multi-run case.</summary>
      <decision status="decided" chosen="per-run-psc-plus-intersection-mask">
        When PSC is on: per-run 3dTstat -mean + 3dcalc min(200,a/b*100)*step(a)*step(b) (Mode B via
        scan[s_k..e_k] sub-brick selectors, verified bit-identical to per-file scaling); writes
        {pre}_run{k}_mean.nii.gz and {pre}_run{k}_psc.nii.gz, then 3dTcat in acquisition order into
        {pre}_psc.nii.gz as the model input. For K&gt;1 regardless of PSC: per-run 3dTstat -max/-min on the
        series entering the model; a run-intersection mask {pre}_run_intersect_mask.nii.gz keeps a voxel iff
        max_k &gt; min_k (exact) in every run, combined via one 3dcalc of ispositive products, passed as
        -mask to 3dDeconvolve and 3dLSS (a mean-positive criterion was rejected because the data are
        demeaned). Mode A always 3dTcats the unscaled runs into {pre}_concat_scan.nii.gz as the raw ROI
        source (and as the model input when PSC is off); in Mode B the supplied scan serves this role.
        Min-outlier EPI is computed per run (label run{k}) for K&gt;1. K=1 commands and filenames are
        unchanged from v3.1.0 (no -mask). Accounting of the PSC intermediates in output_files was deferred
        to T11 (see T11b below).
      </decision>
    </topic>

    <topic id="T4" title="Run-aware censoring, derivatives, and run exclusion">
      <summary>Extends censoring, motion derivatives, and the uncensored-TR sufficiency floor to the
      multi-run case.</summary>
      <decision status="decided" chosen="single-censor-file-plus-exclusion-floor">
        A single censor file is built via 1d_tool.py -censor_motion -set_run_lengths (Mode A concatenates
        per-run motion files row-wise first; -censor_prev_TR retained). CSF/WM derivatives are computed
        within-run with the first TR of each run zeroed. User-supplied motion derivative columns (7-12) pass
        through, documented as required to be within-run; Mode B additionally gets a medium graded warning
        if any derivative column at a run-start row equals the nonzero cross-boundary base-parameter
        difference. Per-run censored counts/percentages are logged alongside the total. Pre-concatenation,
        a run with uncensored TRs &lt;= p+1 (p = 1+floor(D_max/150), D_max = longest supplied run; same p as
        T5) is excluded: its scan/motion/tissue/censor rows and events are removed, run_lengths is
        recomputed, and a high-severity graded warning names the run; if no run remains, this raises
        ModelError (not GuardError). K=1 behavior is identical to v3.1.0.
      </decision>
    </topic>

    <topic id="T5" title="DOF accounting (design-matrix-derived, off-by-one fix)">
      <summary>Replaces analytic regressor-counting DOF with DOF read from the actual fitted design
      matrix.</summary>
      <decision status="decided" chosen="matrix-derived-dof">
        task_act: after onset files are written, a dry run of the package's own 3dDeconvolve command
        (-input replaced by -nodata total_TRs TR, plus -x1D {pre}_preflight_dmat.x1D -x1D_stop, retaining
        -concat, -local_times, -polort A, -censor, -ortvec, all -stim_times* and HRF strings) gives
        DOF = rows - columns. task_conn: gen_design_matrix() is moved before the DOF check; IM columns are
        identified via x1D StimLabels/StimBots/StimTops for label beta_stims; per-trial LSS DOF =
        rows - (non-IM columns + 2); CENSOR_HIGH remains sourced from the censor file. DOF&lt;1 raises
        ModelError; a nonzero dry-run exit raises ToolExecutionError via the centralized AFNI wrapper
        (command, description, stderr). QC reports the matrix-derived DOF; the old analytic
        n_regressors code is removed from both pipelines. rest_conn's compute_dof is unchanged by this
        topic (see T6d). Applies at K=1 too (QC DOF now differs from v3.1.0 for multi-column HRFs).
        Accounting of {pre}_preflight_dmat.x1D was deferred to T11.
      </decision>
    </topic>

    <topic id="T5b" title="task_conn rejection of multi-column custom HRFs">
      <summary>task_conn's 3dLSS/beta-series machinery assumes one basis column per trial; a multi-column
      custom HRF silently breaks that assumption.</summary>
      <decision status="decided" chosen="reject-multi-column-custom-hrf">
        validate_custom_hrf returns the column count from its existing -nodata dry-run x1D (-polort -1, one
        stimulus; counted via np.loadtxt data columns, not header parsing); the single call site
        (first_level_config.py:485) is updated. Config validation raises ConfigError when task_conn is paired
        with hrf_model 'custom' and a column count != 1, naming custom_hrf and the count and listing
        single-column alternatives (GAM, BLOCK, SPMG1, or a single-column custom basis such as TWOGAMpw).
        task_act is unchanged (it does not use 3dLSS). Documented in INPUT_SPECIFICATION.md and README.md as
        a release-note behavior change: v3.1.0-accepted task_conn configs using a multi-column custom HRF are
        now rejected. Noted but separately tracked: 3dLSS already treats each basis column of a TENT-style
        IM model as a distinct trial, and gen_beta_series already assumes one sub-brick per trial; this is a
        pre-existing v3.1.0 issue, not newly introduced here.
      </decision>
    </topic>

    <topic id="T6" title="Trial-survival indexing under run-local timing">
      <summary>Onset-to-volume mapping and trial-survival determination must be run-aware once T1/T2
      introduce multi-run timing.</summary>
      <decision status="decided" chosen="run-aware-tr-index">
        A shared helper tr_index(t, tr) = floor(t/tr + 1e-6) (tolerance in TR units) replaces int(round(onset
        /tr)) for every onset-to-volume mapping. check_trial_survival operates on the internal event table
        (run index + run-local onset) built after T2's out-of-range removal and T4's run exclusion, with
        runs renumbered. The censor row is s_k + tr_index(local_onset, tr). Per the T2 amendment, Mode B run
        assignment uses tr_index(onset, tr) against cumulative run-start/length rather than a seconds
        comparison. An out-of-range censor row raises GuardError. Applies at K=1 as well; this changes
        rounding behavior versus v3.1.0 (documented: onsets in the later half of a TR now map to the
        containing volume, shifting ~49.8% of jittered onsets by one volume relative to the old round()).
      </decision>
    </topic>

    <topic id="T6b" title="Trial-count warnings and survival floors">
      <summary>Supersedes T6's advisory low-trial-count warning thresholds with a single, non-configurable
      floor per analysis type.</summary>
      <decision status="decided" chosen="remove-advisory-thresholds-raise-task-conn-floor">
        All advisory low-trial warnings are removed (TRIALS_FEW and its threshold constant in task_act and
        task_conn; the n==2/n&lt;5 messages in check_trial_survival; the n==1/n==2 messages in the timing
        reader, keeping only the n==0 "cannot create onset file" message). check_trial_survival becomes
        threshold-free, returning counts and logging at INFO (plus T6's per-run counts); each pipeline emits
        a single drop warning stating its actual floor. Named module constants
        _MIN_SURVIVING_TRIALS: task_act = 2 (unchanged), task_conn = 3 (raised from 2, since n=2 gives a
        deterministic r = +/-1 correlation); not user-configurable. This floor is independent of T7's
        beta-series composition. Documented in T12 scope: both floors and their rationale, the absence of an
        advisory threshold, and that qc_summary's per_condition_trial_counts/per_condition_surviving_trials
        are the basis for any group-level exclusion or modeling decision.
      </decision>
    </topic>

    <topic id="T6c" title="Partial-correlation rank gate; fishZ/pcorr statistic correction">
      <summary>Guards 3dNetCorr -part_corr against rank-deficient ROI sets and corrects a diagonal/label
      mismatch in the fishZ+pcorr output.</summary>
      <decision status="decided" chosen="roi-stats-rank-gate-plus-diagonal-fix">
        Before any -part_corr call (task_conn per condition, rest_conn), a shared helper extracts parcellated
        time series via 3dROIstats -quiet -float_format '%.9g', centers columns, and computes numerical rank
        as the count of singular values exceeding sv_max * max(n, m) * eps(float32). If rank &lt; m, the
        pcorr matrix for that inset is skipped with a high graded warning PCORR_RANK_DEFICIENT (reporting m,
        rank, n); task_conn continues with other conditions (ModelError only if none yield a matrix);
        rest_conn raises ModelError. qc_summary records m and rank per inset. Separately, fishZ+pcorr now
        writes atanh(PC) clipped to |r| &lt;= 0.999329 with diagonal 4 (not the AFNI PCB value), and the PC
        matrix diagonal is written as +1 rather than AFNI's native -1 (documented as an intentional package
        override). A ConfigError is raised if pcorr is requested with calc_conn seed_to_voxel, naming the
        parcellated-pcorr-only restriction. T12 release notes: PCB mislabel fix, the fact that
        seed_to_voxel's "_pcorr" output was previously plain correlation, and the diagonal -1 -&gt; +1 change.
      </decision>
      <research>Statistical grounding is the numerical-rank criterion (singular-value threshold scaled by
      matrix dimension and float32 machine epsilon) standard to detecting rank deficiency before partial
      correlation / precision-matrix estimation.</research>
    </topic>

    <topic id="T6d" title="rest_conn bandpass-aware per-run DOF">
      <summary>rest_conn's existing DOF formula does not account for the effective rank reduction imposed by
      bandpass filtering, in either processing backend.</summary>
      <decision status="decided" chosen="dry-run-parsed-bandpass-dof">
        Simultaneous backend: a 3dTproject dry run on a one-row 1D surrogate of run length (-polort -1 -dt TR
        -bandpass lo hi) parses "K stopband regressors" (printed regardless of censor mode, verified
        identical across ZERO/KILL/NTRP); DOF = n_uncensored - (K+1) - n_orts. Sequenced backend: a
        3dBandpass dry run parses "passband indexes=a..b"; passband dimension = 2(b-a+1), with index 0
        counted once if present and Nyquist never included (empirically verified across 5 run lengths); DOF
        = min(passband_dim, n_uncensored) - n_orts, documented as an upper bound. DOF &lt; 1 raises the
        existing RUN_SKIPPED high warning; a null bandpass setting keeps the current formula. A dry-run parse
        failure raises ToolExecutionError (command, description, stderr). qc_summary gains corrected
        per_run_dof plus the per-run bandpass dimension. README:10 and INPUT_SPEC:295's "eliminates the DOF
        cost" claim are removed, replaced by a statement that filtered data span only the passband
        dimensions (Davey et al., 2013) and a description of what the sequenced path actually provides:
        interpolation before filtering (Carp, 2013) and band-matched nuisance regressors (Hallquist et al.,
        2013). T12 gets a release note for the per_run_dof change. Neither backend's actual filtering
        changes.
      </decision>
      <research>Davey, Grayden, Egan &amp; Johnston (2013), "Filtering induces correlation in fMRI resting
      state data" (NeuroImage) for the passband-dimension-as-effective-rank argument; Carp (2013) on
      interpolation-before-filtering; Hallquist, Hwang &amp; Luna (2013) on band-matched nuisance
      regression ("RETROICOR-type" motion/filter mismatch).</research>
    </topic>

    <topic id="T6e" title="Swallowed AFNI failures and null-ROI handling">
      <summary>Several AFNI failure modes (3dNetCorr errors, missing expected outputs, null/all-zero ROI
      masks) were previously silent or produced unusable output without an explicit error.</summary>
      <decision status="decided" chosen="propagate-plus-nan-token-plus-graded-warnings">
        seed_to_voxel_conn and parcellated_conn propagate 3dNetCorr ToolExecutionError (exit 4; command,
        description, stderr), and raise ToolExecutionError naming the file/command if an expected output is
        missing after a successful call. Null (all-zero) ROIs in parcellated non-pcorr connectivity are
        detected via the T6c 3dROIstats extraction; 3dNetCorr runs with -allow_roi_zeros and a 'NaN' token is
        written for those ROIs' rows/columns (including the diagonal), mapped by label from the netcc header;
        a high graded warning NULL_ROI lists the affected labels, recorded in qc_summary. Parcellated pcorr
        relies on the T6c rank gate instead. Seed-to-voxel null detection uses 3dmaskave -quiet -mask
        all-zero; task_conn emits a high SEED_NULL warning and skips that condition (ModelError only if no
        condition yields a map); rest_conn raises ModelError. rest_conn per-run backend failures emit a high
        RUN_FAILED graded warning with the exception message, continue processing remaining runs, and list
        failed runs in qc_summary. Connectivity outputs (condition matrices, seed maps, contrast outputs) are
        now registered in FirstLevelResult.output_files for task_conn and rest_conn. Bare except/pass blocks
        around censor-stat extraction in all three pipelines are replaced with InputError naming the censor
        file. _get_subbrik_stat_aux raises GuardError from a caught ToolExecutionError, preserving its
        message and exit code.
      </decision>
    </topic>

    <topic id="T7a" title="Multi-run 3dLSS and trial estimability (task_conn)">
      <summary>Defines multi-run 3dLSS fitting and replaces the prior onset-volume-survival criterion with
      a formal estimability criterion.</summary>
      <decision status="decided" chosen="option-a-estimability-only">
        Multi-run 3dLSS is a single fit on the concatenated series using the T2 -concat x1D (verified to
        need no additional options). Onset-volume survival in task_act and task_conn is replaced by one
        3dDeconvolve dry run per analysis (-nodata total_TRs TR, the analysis's -concat/-local_times,
        -polort -1, each condition's onset file via -stim_times_IM with its HRF including married timing,
        -x1D_uncensored, -x1D_stop, no -censor). Estimability is f_j = (sum over uncensored TRs of x_jt^2) /
        (sum over all TRs of x_jt^2), with the numerator computed in Python by applying the analysis censor
        vector to the uncensored-matrix columns; IM columns map to trials by file order (run row, then
        within-row). A trial survives iff f_j &gt; 0 (no threshold above zero was adopted; a proposed 0.5
        cutoff was withdrawn by the user as not supported by precedent in the literature). If the
        denominator is 0, f_j = 0 with reason no_in_run_support. T6b's floors (task_act 2, task_conn 3) count
        trials with f_j &gt; 0. All trials remain 3dLSS regressors in task_conn; the beta series used
        downstream is composed only from surviving sub-bricks, and a GuardError is raised if a selected
        sub-brick has a non-finite value. qc_summary records per trial: run, condition, run-local onset, f_j,
        survived, reason, plus per-condition totals/survivors and per-condition-per-run counts at INFO. T6
        items 3/5/7 (onset-volume censor-row lookup, the onset survival criterion, and the out-of-range
        GuardError) are superseded; T6's floor(t/TR + 1e-6) helper is retained for Mode B run assignment
        (T2 item 3). Documented: f_j and the estimability criterion, and the v3.1.0 behavior change that
        fully censored trials previously entered the beta series as NaN values that downstream tools read as
        0.
      </decision>
      <research>Empirical evidence gathered under AFNI 26.0.09: a fully censored IM column produces an
      "all zeros" 3dDeconvolve warning and a NaN 3dLSS sub-brick; 3dROIstats/3dBrickStat read NaN as 0;
      LSS beta SD scales approximately as 1/sqrt(f_j) (measured 0.44/0.572/0.69/1.154/4.21 at f = 1/0.603/
      0.397/0.152/0.011), motivating f_j &gt; 0 as a minimum-estimability (not minimum-precision) gate.</research>
    </topic>

    <topic id="T7b" title="Multi-run beta-series pooling (task_conn)">
      <summary>Whether and how to adjust for run-level offsets when pooling a condition's surviving trial
      betas across runs before connectivity estimation.</summary>
      <decision status="decided" chosen="pool-without-run-wise-adjustment">
        Each condition's surviving trial betas are pooled across runs (ordered run then onset) and correlated
        (3dNetCorr / seed-to-voxel) with no run-wise demeaning or standardization, and no config option is
        added for it. qc_summary gains per-trial run index and beta-series position (from T7a) plus
        per-condition-per-run surviving counts. Documentation states: (1) pooling without per-run adjustment
        means run-level offsets (from habituation/arousal-driven amplitude shifts, or shared
        estimation-induced within-run offsets) contribute to the pooled correlation; (2) run-wise centering
        was not applied because its supporting evidence is from MVPA classification, and extrapolation to
        beta-series correlation is untested; (3) a downstream user applying run-wise centering needs at least
        2 trials per condition per run (a single trial centers to 0 and must be dropped).
      </decision>
      <research>Lee &amp; Kable (2018), PLoS ONE 13:e0207083: "currently preferred estimation procedures impart
      spurious positive correlations between the means of different category activity estimates within the
      same scanner run," direct motivation for flagging the pooling choice rather than silently centering.
      Roberts et al. (2016), NeuroImage 135:1-15, on Simpson's-paradox-type effects in functional
      connectivity. Abdulrahman &amp; Henson (2016), NeuroImage 125:756-766, checked but silent on this specific
      question; literature state assessed as speculative rather than settled.</research>
    </topic>

    <topic id="T8" title="Frozen primary output filenames">
      <summary>Freezes the package's primary output filenames as named constants and documents the
      multi-trial sub-brick ordering of the beta-series file.</summary>
      <decision status="decided" chosen="freeze-as-module-constants">
        Primary filenames are unchanged for both single- and multi-run analyses in v3.2.0 (the "_concat_"
        infix is kept even at K=1): task_act {out_file_pre}_concat_bucket_stats.nii.gz; task_conn
        {out_file_pre}_concat_LSS.nii.gz; rest_conn {out_file_pre}_concat_residual_dtseries.nii.gz. Each
        template is defined once as a module-level constant, with all construction sites in all three
        pipelines using it. Contract tests check the exact strings and their presence in
        FirstLevelResult.output_files on success. README, INPUT_SPEC, and module OUTPUTS docstrings state
        that these names are a stable interface and that renaming/relocating one is a breaking (major
        version) change; they are intentionally not BIDS-named (bids.build_bids_output_path is unused here,
        with removal deferred to a future /clean pass). {out_file_pre}_concat_LSS.nii.gz is documented as
        one sub-brick per trial in combined beta-onset file order (run row by run row, beta_cond_order
        within row, timing-file order within condition), with NaN sub-bricks for trials with no retained
        response; T7a's per-trial qc_summary records identify which sub-bricks were actually used downstream.
        Implementation consequence: gen_beta_series's contiguous total_used counter is replaced by the
        per-trial column index from the T7a trial table, since conditions are no longer contiguous across
        run rows. The skip-if-exists stale-output issue surfaced during this topic was moved into T11's
        scope.
      </decision>
    </topic>

    <topic id="T9" title="Closed config schema (unknown-key and global-only-key rejection)">
      <summary>Closes the YAML config schema so unrecognized or misplaced keys are rejected as a single
      aggregate error rather than silently ignored.</summary>
      <decision status="decided" chosen="closed-schema-dedicated-first-pass">
        A closed key schema is defined at every level (top, global block, per-type analysis block including
        v3.2.0's multi-run keys plus subject/session/task/derivatives_dirs, and nested
        paths/extraction/connectivity/contrasts/connectivity.contrasts blocks). Unknown-key checking is a
        dedicated first validation pass that collects every unknown key (dotted path plus block label, e.g.
        "analyses[0] (nback).extraction.extract_labels") into a single ConfigError (exit 2); a key valid for
        a different analysis type is reported as invalid for the configured type; a missing or invalid
        'type' is reported in the same aggregate error, and that block's remaining keys are skipped (all
        downstream checks remain fail-fast otherwise). Legacy extract/extract_labels/extract_stat keys
        produce a message naming stat_buckets (their v3.1.0 replacement) explicitly. Any GLOBAL_ONLY_KEYS
        key appearing inside a block is now a ConfigError (previously a warning). load_and_validate merges
        **overrides into raw blocks before validate_config, so overrides receive the same key/path/value
        validation as the base config. Allowed-key sets are module constants in first_level_config.py,
        enforced by an AST-based test over that module only (pipelines read ResolvedConfig attributes, not
        raw dict keys): the test collects .get('k')/['k'] reads grouped by receiver variable, plus keys
        consumed from loops over constant tuples, and checks set equality against the allowed sets in both
        directions; reads on an unrecognized receiver name fail the test. Other new tests: example_config.yaml
        still validates; each legacy key is rejected with its migration message; an unknown nested key is
        rejected; an override supplying a nonexistent path raises InputError. A path key explicitly set to
        null still counts as "absent" for T1's singular/plural mixing rule (it remains a recognized key under
        the closed schema). INPUT_SPECIFICATION documents the closed schema; release notes list the
        unknown-key rejection, the GLOBAL_ONLY_KEYS-in-block upgrade to ConfigError, the override validation
        change, and the null-as-absent clarification as behavior changes.
      </decision>
    </topic>

    <topic id="T10" title="Absolute paths at resolve time; AFNI subprocess cwd">
      <summary>Eliminates ambiguity from relative paths and from 3dDeconvolve/related tools writing into the
      process's current working directory rather than out_dir.</summary>
      <decision status="decided" chosen="abspath-at-resolve-plus-explicit-cwd">
        resolve_config converts every path field (paths.*, out_dir, template_path, derivatives_dirs, custom
        files) to os.path.abspath against the process CWD at load time (no symlink resolution). run_afni_
        command gains a cwd parameter (default None = inherit), passed to subprocess.run; every pipeline
        3dDeconvolve call (task_act GLM, task_conn's -x1D_stop design-matrix build, the T5 preflight dry run,
        the T7a estimability dry run) now runs with cwd=out_dir; custom_hrf validation runs inside a
        tempfile.TemporaryDirectory used as cwd (verified load-bearing for the .REML_cmd file it produces).
        AFNI_USE_ERROR_FILE=NO is set in the environment for these calls, and clean_deconvolve_err plus its
        two call sites are deleted. On success, any 3dDeconvolve stderr "*+ WARNING" block (with continuation
        lines) is logged to the analysis logger at WARNING, with no graded-warning code attached. .REML_cmd
        files remain in out_dir, accounted for under T11. README/INPUT_SPECIFICATION document that relative
        paths are resolved against the process CWD at load time and that the package writes nothing into the
        process CWD. Empirically verified under AFNI 26.0.09: of the package's AFNI calls, only 3dDeconvolve
        writes to CWD by default; this motivated passing cwd for that call rather than a broader mitigation.
      </decision>
    </topic>

    <topic id="T11" title="Checkpoint/ledger wiring (F4) and PSC-intermediate accounting (F5)">
      <summary>Wires the package's existing but unused checkpoint.py ledger into all three pipelines so that
      interrupted runs resume safely and a configuration change reruns only the stages it actually affects,
      replacing per-step os.path.exists skip checks and the ledger's existing whole-config-hash/cascade
      design.</summary>

      <decision status="decided" chosen="option-a-per-stage-hash-wiring">
        T11-optA (wiring shape): the ledger file {out_dir}/{out_file_pre}_ledger.jsonl becomes the sole skip
        gate; every os.path.exists skip branch in the three pipeline modules is removed. Not ledgered, and
        run on every invocation regardless of ledger state: stimulus parsing, onset-file writing,
        censor/motion preparation, run exclusion, the T5 preflight and T7a dry-run design matrices, trial
        survival, DOF checks, template validation, and qc_summary.json. Each stage writes its outputs into
        out_dir/.staging_&lt;stage&gt;/ (AFNI subprocess cwd set there), verifies every expected output exists,
        runs a full gzip decompress check on any .gz output, moves everything into out_dir via os.replace,
        and appends a ledger entry with fsync; a leftover staging directory for that stage is deleted before
        it runs. A ledger entry is invalid (triggers a rerun) if any of its recorded outputs is missing.
        auto_reconstruct_ledger and its artifact-glob patterns are deleted. remove_previous becomes
        ledger-scoped: it deletes only this analysis's ledger, listed files, and staging directories, and a
        failed deletion raises. qc_summary.json gains a reused_stages list, with each skip also logged at
        INFO. Cross-analysis raw_ptseries reuse (documented at INPUT_SPEC:237) is dropped; README:16 and the
        surrounding docs are corrected to describe the ledger mechanism accurately.

        T11-perstage (hash definition): each stage's hash is SHA-256 of canonical JSON containing the stage
        label; for every field the stage declares, the pair (ResolvedConfig value from a deepcopy taken at
        run() entry, value at stage entry); the SHA-256 of the stage's declared derived files; its declared
        derived values; and its declared upstream stages' hashes. A stage reruns if it has no ledger entry,
        its hash differs from the recorded one, one of its outputs is missing, or any declared upstream
        stage runs in this invocation. This replaces both the whole-config compute_config_hash and the
        linear downstream cascade. Mutated scan/censor/motion paths are set from the T8 frozen-name constants
        whether or not the prep stage was skipped. QC generation stays always-run (never ledgered). Two new
        tests are required: every ResolvedConfig field must be declared by some stage or listed as exempt,
        and an attribute-read proxy must confirm each stage function reads no field outside its declared set
        plus the exempt set plus censor_path.

        T11-table (per-pipeline stage declarations, all rows approved by the user): task_act stages are
        task-act-prep (scan_path, scan_paths, run_lengths, scale_to_psc; no upstream), task-act-raw-ptseries
        (extract_raw_ptseries, extract_out_file_pre, template_path, average_type, scan_path, scan_paths;
        upstream prep), task-act-glm (scan_path, scan_paths, run_lengths, tr, hrf_model, custom_hrf,
        cond_labels, contrast_functions, contrast_labels, task_timing_path(s), motion_path(s),
        include_motion_derivs, fd_threshold, censor_prev_tr, CSF_path(s), WM_path(s), use_tissue_derivs,
        plus derived onset files/censor file/prepared motion file; upstream prep), and task-act-extract
        (stat_buckets, extract_resids, extract_out_file_pre, average_type, template_path; upstream glm).
        task_conn mirrors this with task-conn-prep (identical to task-act-prep), task-conn-raw-ptseries
        (identical fields, upstream prep), task-conn-design-matrix (the GLM field set with cond_beta_labels
        replacing cond_labels and no contrast fields, plus derived nuisance/beta onset files, censor file,
        prepared motion file; upstream prep), task-conn-beta-series (cond_beta_labels, scan_path, plus the
        T7a per-trial survival table; upstream design-matrix), task-conn-pbseries (extract_pbseries,
        extract_out_file_pre, average_type, template_path; upstream beta-series), and task-conn-connectivity
        (calc_conn, conn_out_file_pre, pcorr, fishZ, template_path, contrast_functions, contrast_labels;
        upstream beta-series). task_conn's always-run/ledgered execution order is: always-run steps, prep,
        design-matrix, the DOF check plus T7a dry run, then the remaining ledgered stages. rest_conn stages
        are rest-conn-prep (scan_paths, scale_to_psc; no upstream), rest-conn-raw-ptseries (extract_raw_
        ptseries, extract_out_file_pre, template_path, average_type, scan_paths; upstream prep),
        rest-conn-residuals-run{n} (the n-th element of scan_paths/motion_paths/CSF_paths/WM_paths/GS_paths
        with null kept as null, plus tr, bandpass, notch_filter_band, motion_deriv_degree, fd_threshold,
        censor_prev_tr, use_tissue_derivs, use_sequenced_bandpass, keep_run_res_dtseries, and derived run-n
        censor/prepared motion/notch-filtered motion; upstream prep), rest-conn-concat (tr,
        keep_run_res_dtseries, plus the derived concatenated run-index list; upstream all
        residuals-run{n} present), rest-conn-residuals-concat (used only when keep_run_res_dtseries is false,
        replacing the residuals-run{n}/concat pair with one stage declaring the union of their fields and
        derived inputs; upstream prep; per-run regression happens inside its staging directory and only the
        concatenated file is moved to out_dir), rest-conn-ptseries (extract_ptseries, extract_out_file_pre,
        average_type, template_path; upstream concat or residuals-concat), and rest-conn-connectivity
        (calc_conn, conn_out_file_pre, pcorr, fishZ, template_path; upstream concat or residuals-concat).
        Exempt fields (declared by no stage, never hashed): num_cores, remove_previous, schema_version,
        analysis_type, analysis_name, out_dir, out_file_pre, derivatives_dirs, force_diff_atlas. Documented:
        editing a motion file triggers reruns because its bytes are hashed into the censor/motion-dependent
        stages; editing scan, tissue, or template file contents does not trigger a rerun (content is not
        hashed by design, per T11-optA's scope).

        T11-raw (raw-ptseries extraction symmetry and PSC variant): resolves the pending item that rest_conn
        extracted raw ptseries after PSC scaling while task_act/task_conn extracted before it. All three
        types now extract from the supplied scans before PSC, writing the unscaled series at the existing
        frozen name ({extract_out_file_pre}_raw_ptseries.csv; rest_conn: _run{N}_raw_ptseries.csv). When
        extract_raw_ptseries AND scale_to_psc are both true, a second file is also written:
        {extract_out_file_pre}_raw_psc_ptseries.csv (rest_conn: _run{N}_raw_psc_ptseries.csv), the ROI
        average of the voxelwise PSC series already produced by the prep stage (for multi-run task inputs,
        per-run PSC concatenated per T3). When scale_to_psc is false, only the unscaled file is written, with
        no extra PSC computation performed. The raw-ptseries stage in all three tables above additionally
        declares scale_to_psc as a field, with upstream = prep. Proposal verification (3 independent agents)
        returned concerns from all three, none rated the design inappropriate: (major, PV-3) the rest_conn
        unscaled filename is unchanged from v3.1.0 even though its content changes when scale_to_psc
        defaults to true, risking silent breakage for anything that parses by filename rather than release
        notes; (minor, PV-1/PV-2) the voxelwise PSC zero-guard and 200% cap should be disclosed as a
        potential source of ROI-average bias at parcel/brain-mask edges, since zeroed voxels still count in
        the ROI mean; (minor, all three) computing PSC solely for extraction when scale_to_psc is false would
        add AFNI cost, resolved moot by the user's choice to extract PSC only when scale_to_psc is true.
      </decision>

      <decision status="open" chosen="none">
        T11-b: validate_template currently writes out_dir/&lt;template_basename&gt;_resampled.nii.gz unscoped
        by out_file_pre, guarded by its own independent os.path.exists staleness check, and is not accounted
        for in the ledger at all. Whether/how to bring this into the T11-table scheme (own stage? folded into
        prep? left as a special-cased always-run step with its own staleness logic?) was observed during T11
        discussion but not yet decided.
      </decision>

      <decision status="open" chosen="none">
        T11-c: a final consolidated confirmation of the full T11 wiring (T11-optA + T11-perstage + T11-table
        + T11-raw + the resolution of T11-b) has not yet been presented back to the user as a single
        integrated design for sign-off.
      </decision>

      <decision status="open" chosen="none">
        T11-raw doc additions: whether the three documentation items that accompany T11-raw (disclosing the
        PSC zero-guard/200% cap's effect on ROI averages; a release note marking the rest_conn raw-ptseries
        filename's semantic change as breaking; an orchestrator-report item O5 for the same change) are in
        scope for v3.2.0. Asked of the user; not yet answered.
      </decision>
    </topic>

  </topics>

  <action_items>
    <item priority="P0" target_mode="brainstorm" description="Resume T11 by resolving T11-b (validate_template scoping/ledgering), obtaining the T11-raw doc-additions answer, and producing the T11-c consolidated confirmation." />
    <item priority="P1" target_mode="brainstorm" description="T11b (F5): separate intermediate outputs from final outputs in FirstLevelResult.output_files; not yet discussed." />
    <item priority="P1" target_mode="brainstorm" description="T12: v3.2.0 release scope, schema_version bump, docs, release notes, and legacy-CSV handling; not yet discussed." />
    <item priority="P1" target_mode="brainstorm" description="After the fmri-first-level-proc report is complete, write a separate orchestrator-side report (items ORCH O1-O4 already locked, O5 pending T11-raw's doc-additions answer) to the ABCD_fmri_orchestrator_S3 workspace; request a write grant from the user before that write." />
  </action_items>

  <next_steps>Resume /brainstorm directly on T11's three open items (T11-b, T11-c, T11-raw doc additions), then proceed to T11b and T12. The Pre-Report Audit, final report, and orchestrator-side report are deferred until T11 and T12 close.</next_steps>
</brainstorm_report>
