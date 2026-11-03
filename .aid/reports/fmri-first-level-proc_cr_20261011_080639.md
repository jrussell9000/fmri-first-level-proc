<cr_report>
  <meta project="fmri-first-level-proc" mode="cr" timestamp="2026-10-11T08:06:39-04:00" />
  <scope>
    Critical review of the v4.0.0 build (branch v4.0.0-build, uncommitted) against the locked design
    (fmri-first-level-proc_brainstorm_20261009_112745.md) and tech spec (fmri-first-level-proc_implement_plan_20261009_120006.md),
    using the build report fmri-first-level-proc_implement_build_20261009_140031.md as input. Files reviewed:
    task_act_first_level.py, task_conn_first_level.py, rest_conn_first_level.py, runsets.py, prep.py, estimability.py, events.py,
    nuisance.py, connectivity.py, roi.py, smoothing.py, names.py, bids.py, first_level_utils.py, first_level_config.py,
    INPUT_SPECIFICATION.md, example_config.yaml. Methods reviewed: trial-to-column mapping and 3dLSS beta-series extraction,
    per-run volume selection, model-input routing, smoothing routing, seed-to-voxel seed sourcing, trial estimability, TR handling,
    events parsing, motion censoring metric, ROI QC, 1ddot-based parcellated connectivity, and the build's verification coverage.
  </scope>
  <research_conducted>
    One literature/specification research topic (R1, user-approved): BIDS events.tsv semantics for onset/duration "n/a" and tool
    handling. Key result: BIDS stable specification, Task events: duration "Must always be either zero or positive (or n/a if
    unavailable)"; "A duration value of zero implies that the delta function or event is so short as to be effectively modeled as an
    impulse" (https://bids-specification.readthedocs.io/en/stable/modality-agnostic-files/events.html). FSL FEAT custom 3-column EV
    files require numeric durations. No authoritative documentation was located for nilearn, fitlins or AFNI timing_tool.py handling of
    an "n/a" duration (lit_state: emerging). Empirical checks against AFNI 26.0.09 in the session scratchpad: model-input routing for
    Mode B with PSC off (F4); -stim_times_IM column layout for a 5-column TENT basis (F6); -stim_times_IM column order for out-of-order
    rows (F7); stimulus placement under header TR versus -TR_times (F8); pandas parsing of "n/a" (F14). Every recommendation was
    independently checked by three blind proposal-verification agents; verdicts and folded-in concerns are recorded per finding.
  </research_conducted>
  <findings>
    <finding id="F1" severity="critical" category="validity">
      <location file="fmri_first_level_proc/task_conn_first_level.py" lines="637-645, 804-812" />
      <description>Per-condition beta series are extracted from the single 3dLSS output using beta_series_position, a per-condition
        counter that restarts at 0 for each condition (estimability.py 261-264), whereas 3dLSS sub-bricks follow the global IM column
        order of the combined beta onset file.</description>
      <evidence>In the two-condition smoke test both bseries files were built from sub-bricks 0,1,2,3 of an 8-sub-brick 3dLSS output,
        so the second condition's series contained the first condition's betas. Non-surviving trials shift indices even with one
        condition.</evidence>
      <literature>3dLSS help: LSS estimation from a -stim_times_IM matrix, one sub-brick per IM column (Mumford et al., 2012).
        Verification 2/3 verified, 1 concerns (3dREMLfit drops all-zero columns; 3dLSS behavior unconfirmed).</literature>
      <impact>Every downstream task_conn output (beta series, parcel series, connectivity matrices/maps, contrasts) is wrong whenever
        there are two or more beta conditions or any trial is dropped; no error is raised.</impact>
      <recommendation>Thread each trial's global IM column index through build_trials; index 3dLSS by sorted global indices in both the
        unsmoothed and smoothed stages; set beta_series_position as the rank among the condition's selected indices; GuardError if the
        3dLSS sub-brick count differs from the beta_stims IM column count, or on duplicate (condition, run, onset) keys.</recommendation>
    </finding>
    <finding id="F2" severity="critical" category="validity">
      <location file="fmri_first_level_proc/runsets.py" lines="52-58" />
      <description>RunInfo.spec returns the bare source path whenever start == 0; in Mode B the first run starts at 0 inside the
        concatenated file, so every per-run consumer receives all runs' volumes for run 1. The class docstring requires start == 0 and
        whole-file.</description>
      <evidence>Consumers: prep.py 175-183 and 228; task_act 884, 895, 901, 1021, 1026; task_conn 728, 739, 745, 945, 950. The Mode B
        smoke test used a single run spanning the whole file, the one case that masks the defect.</evidence>
      <literature>Verification 3/3 verified.</literature>
      <impact>Mode B multi-run with PSC on (the shipped example) fails the volume-count check; ROI QC and the PSC-off run-intersection
        mask are silently computed over the whole series; smoothing writes a whole-series "run 1".</impact>
      <recommendation>Add an explicit RunInfo.whole_file field set by build_runsets (true for Mode A task and rest, false for Mode B);
        spec returns the bare path only when whole_file is true, otherwise the explicit selector including start 0.</recommendation>
    </finding>
    <finding id="F3" severity="major" category="robustness">
      <location file="fmri_first_level_proc/prep.py" lines="187, 202, 309-329" />
      <description>task_model_input returns the concatenated model-input path whenever K_supplied > 1, but task_prep writes that file
        only when more than one run also survives pre-model exclusion.</description>
      <evidence>Two supplied runs with one excluded (RUN_INSUFFICIENT_TRS) direct the GLM, design matrix, 3dLSS and raw parcel
        extraction to a file that is never written (Mode A PSC on/off; Mode B PSC on).</evidence>
      <literature>Verification 3/3 verified.</literature>
      <impact>The designed continue-on-exclusion path aborts with ToolExecutionError.</impact>
      <recommendation>Drop the surviving-run condition at both task_prep write sites; whenever K_supplied > 1, 3dTcat the surviving
        runs, including a single survivor; task_model_input unchanged.</recommendation>
    </finding>
    <finding id="F4" severity="critical" category="validity">
      <location file="fmri_first_level_proc/prep.py" lines="325-329" />
      <description>In Mode B with scale_to_psc false, task_model_input ignores the smoothing token and returns the unsmoothed scan, so
        task-act-glm-smooth and task-conn-beta-series-smooth refit unsmoothed data while the smoothing stage's output is unused.</description>
      <evidence>Direct call with token _s6mm returned scan.nii.gz for K_supplied 1 and 2 and a selector with one run excluded; the
        smoothing stage writes sub_blur_s6mm.nii.gz or sub_concat_scan_s6mm.nii.gz.</evidence>
      <literature>Verification 3/3 verified.</literature>
      <impact>All _s{N}mm outputs in that configuration are unsmoothed results labelled smoothed; smoothing_per_run QC reports the
        blurred file's FWHM, lending false validation; group voxelwise inference would assume smoothness the maps do not have.</impact>
      <recommendation>With PSC off and a non-empty token, return blurred_run(pre, None, token) for K_supplied 1 and
        blurred_concat(pre, token, False) for K_supplied > 1 regardless of input mode.</recommendation>
    </finding>
    <finding id="F5" severity="major" category="scientific_rigor">
      <location file="fmri_first_level_proc/task_conn_first_level.py" lines="884-896, 906-928" />
      <description>Smoothed seed-to-voxel maps extract the seed from smoothed data in task_conn and rest_conn
        (rest_conn_first_level.py 927-938), contrary to locked SMOOTH decisions (1) and (5); task_conn never produces smoothed
        seed-map contrasts and omits them from task_conn_expected.</description>
      <evidence>seed_to_voxel(io, smoothed_bseries, smoothed_bseries, ...) and seed_to_voxel(io, smoothed_path, smoothed_path, ...);
        the contrast loop iterates only unsmoothed produced_paths.</evidence>
      <literature>Locked design cites Alakorkko et al. (2017) and XCP-D against parcellating smoothed data; CONN extracts ROI series
        from unsmoothed volumes. Verification 3/3 verified.</literature>
      <impact>Seed signal mixes out-of-ROI voxels; smoothed and unsmoothed maps differ in both target smoothness and seed definition;
        smoothed contrasts are silently absent.</impact>
      <recommendation>Smoothed maps use seed input = unsmoothed series and target = _s{N}mm series; track smoothed per-condition map
        paths in their own dict (replacing the os.path.exists skip), compute seed_contrast over them and add their names to
        task_conn_expected.</recommendation>
    </finding>
    <finding id="F6" severity="major" category="validity">
      <location file="fmri_first_level_proc/task_act_first_level.py" lines="528-540" />
      <description>task_act accepts multi-column custom HRFs, but the estimability step pairs trials with IM columns via zip, assuming
        one column per trial; the locked T7a definition covers only the single-column case.</description>
      <evidence>AFNI 26.0.09, 3 trials with TENT(0,8,5): 15 IM columns grouped trial-major (0-4, 5-9, 10-14); zip assigned trials 2
        and 3 to trial 1's basis columns 1 and 2 and discarded 12 values.</evidence>
      <literature>Verification 1/3 verified, 2 concerns (layout validated only for TENT; zero-trial guard; pooling is a design
        extension).</literature>
      <impact>Under censoring, trial survival, qc trial counts and the minimum-trial floor (condition and contrast dropping) are
        computed from the wrong trials, silently.</impact>
      <recommendation>Option A (user-selected): block mapping trial j to columns j*m to j*m+m-1 with GuardError if m is not a positive
        integer, zero-trial conditions skipped before division, explicit length check replacing zip; pooled energy ratio across the
        trial's m columns (identical to T7a at m = 1); document as a T7a extension.</recommendation>
    </finding>
    <finding id="F7" severity="minor" category="robustness">
      <location file="fmri_first_level_proc/events.py" lines="378-404" />
      <description>task_conn beta onset rows are condition-grouped and therefore out of chronological order; trial mapping relies on
        3dDeconvolve creating IM columns in file order, which AFNI does not document.</description>
      <evidence>AFNI 26.0.09, rows "2 30 60 16 44" and "10 4": IM columns follow file order, not sorted time. No current
        defect. Runtime allows any AFNI at or above the minimum with only an UNVALIDATED_VERSION warning.</evidence>
      <literature>Verification 2/3 verified, 1 concerns (major: version-pinned test alone does not protect other AFNI versions).</literature>
      <impact>A future AFNI that sorts onsets would silently interchange trials across conditions.</impact>
      <recommendation>No ordering change; add a runtime GuardError in both estimability steps when, within a run, an earlier onset's
        column block starts later than a later onset's (all-zero trials skipped), naming the AFNI version.</recommendation>
    </finding>
    <finding id="F8" severity="major" category="validity">
      <location file="fmri_first_level_proc/runsets.py" lines="335-349" />
      <description>config.tr is never compared with the scan header TR (Mode B has no TR check at all). The task GLM and 3dLSS place
        events using the header TR, while estimability, censoring, onset validation, DOF and rest -dt/3dTcat -TR use config.tr.</description>
      <evidence>AFNI 26.0.09: header TR 2.0 with -TR_times 1.0 placed an event at 10 s on row 6 (header placement). 3dDeconvolve help:
        -TR_times sets only the -iresp/-sresp step; -force_TR advises fixing the input with 3drefit.</evidence>
      <literature>Verification 2/3 verified, 1 concerns (Mode B coverage; per-run direct comparison).</literature>
      <impact>On mismatch, model timing and survival/censoring/QC disagree; rest bandpass cutoffs are mis-scaled and 3dTcat -TR
        overwrites the header, hiding the discrepancy.</impact>
      <recommendation>Compare every run's header TR directly with config.tr (Mode A/rest per run; Mode B on scan_path); abs difference
        above 1e-4 raises InputError naming the file, both values and the remedies (correct tr or 3drefit -TR); no -force_TR.</recommendation>
    </finding>
    <finding id="F9" severity="minor" category="reproducibility">
      <location file="fmri_first_level_proc/roi.py" lines="487-541" />
      <description>roi_qc runs two 3dcalc and two 3dROIstats calls inside the per-ROI loop although none depend on the ROI.</description>
      <evidence>Each 3dROIstats call already reports all ROIs; only one value is read per iteration. Results are correct.</evidence>
      <literature>Verification 3/3 verified.</literature>
      <impact>About 1,600 redundant AFNI invocations per run for a 400-parcel atlas.</impact>
      <recommendation>Compute once per run and read per-ROI values (mirroring roi_coverage); skip when sentinel_fail or no ROI has
        masked voxels; records unchanged.</recommendation>
    </finding>
    <finding id="F10" severity="minor" category="robustness">
      <location file="fmri_first_level_proc/events.py" lines="54-80" />
      <description>A header recognized under both tab and comma silently uses the BIDS reading, whereas the spec requires InputError;
        neither error path lists the columns found.</description>
      <evidence>Tech spec lines 638-644. The spec's "BIDS takes precedence" sentence was ambiguous; the user selected Reading A.</evidence>
      <literature>Verification 3/3 concerns (major: spec ambiguity, resolved by the user).</literature>
      <impact>Low; pathological headers only, but delimiter choice is silent.</impact>
      <recommendation>Reading A: both or neither recognized raises InputError listing the file and the stripped columns per delimiter
        ("unparseable" where a parse threw); BIDS precedence only for a single-delimiter header holding both schemes. BIDS and
        CONDITION schemes remain valid in both .tsv and .csv.</recommendation>
    </finding>
    <finding id="F11" severity="major" category="scientific_rigor">
      <location file="INPUT_SPECIFICATION.md" lines="79, 380, 467" />
      <description>The censoring metric is documented as framewise displacement (FD) in mm, but 1d_tool.py -censor_motion computes
        the Euclidean norm (enorm) of the per-TR backward difference of the six parameters (zeroed at run starts, rotations in supplied
        units).</description>
      <evidence>nuisance.py 53-61; 1d_tool.py help: -censor_motion implies -derivative and -collapse_cols euclidean_norm.</evidence>
      <literature>Power et al. (2012), NeuroImage 59:2142-2154: FD is the L1 sum of absolute differences with rotations converted on a
        50 mm sphere. Verification 3/3 verified.</literature>
      <impact>Because L2 does not exceed L1, literature or consortium FD thresholds censor fewer TRs than intended; methods text
        reporting "FD" misdescribes the procedure.</impact>
      <recommendation>Option A (user-selected): documentation only; computation and fd_threshold key unchanged; every description
        names enorm with its definition and an AFNI citation, states it is not Power FD and that thresholds are not interchangeable.</recommendation>
    </finding>
    <finding id="F12" severity="note" category="validity">
      <location file="fmri_first_level_proc/connectivity.py" lines="212-246" />
      <description>Parcellated r and partial correlation are parsed from 1ddot's fixed-decimal printed matrices (locked T6c).</description>
      <evidence>Reported (not verbatim-confirmed) %9.5f format. Bounds at d decimals: r about 0.5x10^-d, partial correlation about
        10^-d (inverse diagonal at least 1), Fisher Z at most the input bound divided by (1 - 0.999329^2).</evidence>
      <literature>Verification 3/3 concerns (Fisher Z bound under pcorr was understated by 2x; truncation; per-block decimals).</literature>
      <impact>Negligible relative to sampling SE of r (0.03-0.1 at n = 100-1000).</impact>
      <recommendation>No production change; record the observed precision in the module docstring.</recommendation>
    </finding>
    <finding id="F13" severity="major" category="reproducibility">
      <location file="fmri-first-level-proc_implement_build_20261009_140031.md" lines="207" />
      <description>Build verification asserted completion, file existence, ledger reuse and qc key presence only, on single-run inputs
        without templates, run exclusion or unequal trial counts. Several paths were never exercised. The build report's statement
        that the 1ddot parser was verified against captured real AFNI output could not be substantiated (no capture located).</description>
      <evidence>F1-F8 and F14 all passed the build's checks.</evidence>
      <literature>Verification 3/3 verified.</literature>
      <impact>Silent value-level defects reach review; residual risk in unexercised paths.</impact>
      <recommendation>Value-level, real-AFNI tests on small synthetic data against independent references with explicit tolerances
        for every unexercised path; correct the build report sentence.</recommendation>
    </finding>
    <finding id="F14" severity="major" category="robustness">
      <location file="fmri_first_level_proc/events.py" lines="99-106" />
      <description>pandas parses "n/a" and empty cells as NaN and astype(float) succeeds, so missing onsets/durations pass silently.</description>
      <evidence>pandas 3.0.1: duration "n/a" gives float64 NaN with no exception. Effects: GAM/BLOCK mean_dur skips NaN (computed from
        a subset of trials); dmBLOCK married tokens "onset*nan"; NaN onsets pass the out-of-range check (NaN comparisons are false);
        NaN in QC records.</evidence>
      <literature>R1: BIDS permits n/a meaning unknown, distinct from 0 (impulse); FEAT requires numeric durations. Verification 1/3
        verified, 2 concerns (per-column remedy; check placement; SPMG1 trade-off).</literature>
      <impact>Silent bias in HRF duration, malformed timing files, and events with unknown timing entering the model.</impact>
      <recommendation>Option A (user-selected): separate post-conversion check; NaN or inf onset/duration raises InputError under every
        HRF naming file, column and rows, stating n/a is valid BIDS meaning unknown; per-column remedy (onset: supply true onset;
        duration: supply true duration or 0 for impulse events); never impute; document in INPUT_SPEC.</recommendation>
    </finding>
    <finding id="F15" severity="note" category="generalizability">
      <location file="fmri_first_level_proc/bids.py" lines="181" />
      <description>Discovery matches *_desc-confounds_regressors.tsv as the motion file, a name shared with legacy fMRIPrep confounds
        (headered, non-motion leading columns, rotations in radians).</description>
      <evidence>load_numeric_table uses np.loadtxt, so a headered fMRIPrep file raises InputError; a headerless radians file with the
        same name would pass and underweight rotations about 57x in censoring. Upstream format belongs to the orchestrator contract.</evidence>
      <literature>INPUT_SPECIFICATION.md line 371 already requires degrees.</literature>
      <impact>Low; depends on upstream file contents.</impact>
      <recommendation>Option A (user-selected): document in the discovery table that the matched file must be headerless with motion in
        the first six columns (mm, degrees) and that fMRIPrep confounds files are incompatible.</recommendation>
    </finding>
  </findings>
  <summary>
    <critical_count>3</critical_count>
    <major_count>7</major_count>
    <minor_count>3</minor_count>
    <overall_assessment>needs_revision</overall_assessment>
  </summary>
  <action_items>
    <item priority="P0" target_mode="implement" finding_ref="F1" description="Global IM-column indexing for 3dLSS beta-series extraction (both stages), beta_series_position as rank among selected indices, GuardErrors on sub-brick count mismatch and duplicate (condition, run, onset)" />
    <item priority="P0" target_mode="implement" finding_ref="F2" description="RunInfo.whole_file field; spec returns explicit selector unless whole_file" />
    <item priority="P0" target_mode="implement" finding_ref="F4" description="task_model_input returns the smoothed file for PSC-off with a token regardless of input mode" />
    <item priority="P1" target_mode="implement" finding_ref="F3" description="task_prep writes the concatenated model input whenever K_supplied > 1, including a single surviving run" />
    <item priority="P1" target_mode="implement" finding_ref="F5" description="Smoothed seed-to-voxel: unsmoothed seed, smoothed target; smoothed contrast siblings and expected names" />
    <item priority="P1" target_mode="implement" finding_ref="F6" description="Block column-to-trial mapping and pooled estimability for multi-column HRFs; guards; INPUT_SPEC T7a extension" />
    <item priority="P1" target_mode="implement" finding_ref="F8" description="Per-run header TR versus config.tr InputError for all modes" />
    <item priority="P1" target_mode="implement" finding_ref="F14" description="Reject NaN/inf onset and duration with specific per-column InputError; INPUT_SPEC" />
    <item priority="P1" target_mode="implement" finding_ref="F11" description="Correct censoring-metric documentation to AFNI enorm in INPUT_SPEC, example_config, README, nuisance.py docstrings" />
    <item priority="P2" target_mode="implement" finding_ref="F7" description="Runtime IM column-order GuardError in both estimability steps" />
    <item priority="P2" target_mode="implement" finding_ref="F9" description="Hoist ROI-invariant AFNI calls out of the roi_qc per-ROI loop" />
    <item priority="P2" target_mode="implement" finding_ref="F10" description="Both/neither delimiter InputError with per-delimiter columns; BIDS precedence only within a single delimiter" />
    <item priority="P2" target_mode="implement" finding_ref="F12" description="Record observed 1ddot print precision in connectivity.py docstring" />
    <item priority="P2" target_mode="implement" finding_ref="F13" description="Correct the build report sentence on 1ddot capture verification" />
    <item priority="P2" target_mode="implement" finding_ref="F15" description="INPUT_SPEC discovery table: motion file headerless, first six columns mm/degrees; fMRIPrep confounds incompatible" />
    <item priority="P0" target_mode="test" finding_ref="F13" description="Value-level real-AFNI tests on small synthetic data with independent references and explicit tolerances: connectivity (parcellated, seed, null ROI/seed, rank-deficient pcorr) in task_conn and rest_conn; roi-qc in all pipelines; extract_pbseries/ptseries/raw_ptseries; task_conn contrasts smoothed and unsmoothed; BIDS discovery and collision; multi-run Mode A/B; pre-model exclusion" />
    <item priority="P0" target_mode="test" finding_ref="F1" description="Interleaved two-condition sub-brick equality; fully censored trial to establish 3dLSS all-zero column behavior" />
    <item priority="P0" target_mode="test" finding_ref="F2" description="Mode B two-run task_act and task_conn, PSC on: completion, run-1 PSC and smoothed volume counts, run-1 mean over its own volumes" />
    <item priority="P0" target_mode="test" finding_ref="F4" description="Mode B PSC-off token path equals smoothing-stage write path (K_supplied 1, 2, one excluded); smoothed outputs differ voxelwise from unsmoothed" />
    <item priority="P1" target_mode="test" finding_ref="F3" description="One-of-two excluded for task_act and task_conn in Mode A PSC on/off and Mode B PSC on (Mode B PSC off as regression guard)" />
    <item priority="P1" target_mode="test" finding_ref="F5" description="Smoothed-map seed equals unsmoothed-map seed; every kept contrast has an _s{N}mm sibling" />
    <item priority="P1" target_mode="test" finding_ref="F6" description="IM column-layout contract for TENT, CSPLIN, SPMG2, SPMG3 on AFNI 26.0.09; three-trial TENT case censoring only trial 2" />
    <item priority="P1" target_mode="test" finding_ref="F7" description="Interleaved-row AFNI contract test failing loudly on other AFNI versions; onset file versus column_order order; guard fires on permuted columns" />
    <item priority="P1" target_mode="test" finding_ref="F8" description="Header TR 2.0 versus config 1.0 raises for task_act A/B, task_conn A/B, rest_conn; matching passes" />
    <item priority="P1" target_mode="test" finding_ref="F14" description="n/a and empty cells in onset and duration for BIDS tsv, BIDS csv and CONDITION scheme; other non-numeric tokens keep existing error" />
    <item priority="P2" target_mode="test" finding_ref="F9" description="roi_qc records identical to current; mocked AFNI call count independent of ROI count" />
    <item priority="P2" target_mode="test" finding_ref="F10" description="Neither, single-delimiter dual-scheme, both-delimiter cases; positive parses for BIDS and CONDITION in tsv and csv" />
    <item priority="P2" target_mode="test" finding_ref="F11" description="Targeted assertion that the INPUT_SPEC fd_threshold row names enorm" />
    <item priority="P2" target_mode="test" finding_ref="F12" description="Real 1ddot versus float64 numpy: per-block decimals, tolerances r 10^-d, pcorr 2x10^-d, Fisher Z input bound over (1 - 0.999329^2), fail if fewer than 3 decimals" />
    <item priority="P2" target_mode="test" finding_ref="F15" description="Headered confounds TSV raises InputError" />
  </action_items>
</cr_report>
