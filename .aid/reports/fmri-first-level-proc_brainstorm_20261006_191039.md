<brainstorm_report>
  <meta project="fmri-first-level-proc" mode="brainstorm" timestamp="2026-10-06T19:10:39Z" status="interim-pause" />
  <context_files>
    <file path="brainstorm_history/fmri-first-level-proc_brainstorm_20261005_060843.md" relevance="Prior interim report (T1-T10 locked, T11 partial). Its T1-T10 decisions carry forward unchanged except where amended below." />
    <file path="ABCD_fmri_orchestrator_S3_cr_20261001_142121.md" relevance="Source CR for the v3.2.0 scope." />
    <file path="fmri_first_level_proc/first_level_utils.py; rest_conn_first_level.py; task_act_first_level.py; task_conn_first_level.py; first_level_config.py" relevance="Code audited for PSC, polort, aggregation, seed-to-voxel, template validation." />
    <file path="ABCD_fmri_orchestrator_S3; fmri-proc-orchestrator; fmri-preproc (read-only, user-granted)" relevance="Upstream audit: inputs are brain-masked, non-demeaned, non-detrended positive-baseline BOLD; smoothing lived only in the orchestrators." />
  </context_files>

  <note>
    Interim pause, not a close-out. T1-T11 (all sub-items) are locked. Remaining: T11b, T12, then the Pre-Report
    Audit, the final report, and two orchestrator-side reports. T1-T10 text is not repeated here; see the prior
    report. Amendments to earlier topics are listed under "Amendments to prior locks".
  </note>

  <topics>
    <topic id="T11-raw" title="Raw-ptseries extraction (confirmed)">
      <decision status="decided" chosen="as-locked-20261005">
        extract_raw_ptseries true + scale_to_psc true: write unscaled _raw_ptseries.csv and _raw_psc_ptseries.csv;
        scale_to_psc false: unscaled only; extract_raw_ptseries false: nothing. Model-derived extractions
        (stat_buckets, beta series, connectivity) are unaffected.
      </decision>
    </topic>

    <topic id="T11-demean" title="Demeaning/detrending audit">
      <decision status="decided" chosen="finding">
        The package never demeans before PSC or raw extraction; mean/baseline is handled only inside model fits
        (task: 3dDeconvolve -polort A; rest: 3dTproject/3dBandpass). All three upstream sources (fmri-preproc,
        fmri-proc-orchestrator, ABCD/fMRIPrep) supply masked, non-demeaned, non-detrended positive-baseline BOLD
        with drift intact. The ABCD N=30 test runs are outdated and must not be referenced.
      </decision>
    </topic>

    <topic id="T11-polort" title="rest_conn detrending per context">
      <research>3dTproject help ("no sense to use pp greater than 2" when bandpassing; "-polort -1 is not advised
      (if data mean != 0)"); AFNI developer guidance that quadratic trends are not spanned by sinusoids (R4);
      3dBandpass removes mean/Nyquist and by default quadratic-detrends; Ciric et al. 2017 detrend linear+quadratic
      in all pipelines (R5). Empirical (AFNI 26.0.09, synthetic, true r = 0): simultaneous polort -1 with bandpass
      gave mean pair r +0.045/+0.244 (drift 1x/3x) vs -0.004 at polort 2; lowpass-only [0, 0.1] gave +0.589 vs
      +0.008; sequenced 3dBandpass -nodetrend gave +0.072/+0.352 and edge amplitude ratio up to 2.35 vs about 0
      and 1.0 with default detrend; polort 2 adequate at 320-1200 s runs. v2.3.1 rationale ("bandpass subsumes
      polynomial detrending") is empirically false.</research>
      <decision status="decided" chosen="per-context-polort">
        Simultaneous 3dTproject: -polort 2 if bandpass[0] > 0; -polort 1+floor(D/150) per run if bandpass[0] = 0.
        Sequenced: remove -nodetrend from both 3dBandpass calls (rest_conn L258 and bandpass_filter_1d_afni); keep
        -polort -1 in NTRP and final regression calls. Task pipelines and motion notch unchanged. DOF: simultaneous
        from a one-row-surrogate 3dTproject dry run (actual polort, censor, orts, bandpass) parsing
        "N D.O.F. left" (supersedes T6d's K+1 formula; surrogate verified identical to full data); sequenced T6d
        formula unchanged (impulse-rank test: detrend does not change passband rank). Docs: remove rest_conn
        L40-41 stale claims; document per-context polort and rationale. Release note: rest_conn residuals and
        per_run_dof change in both backends. bandpass null is unreachable (validator requires it).
      </decision>
    </topic>

    <topic id="SMOOTH-ARCH" title="Spatial smoothing moves into fmri-first-level-proc">
      <research>Field placement (R8): SPM, FEAT, afni_proc.py, nilearn smooth before the first-level GLM; fMRIPrep
      deliberately does not smooth; XCP-D never parcellates smoothed data. R7: Alakorkko et al. 2017 (EJN) and
      XCP-D advise against parcellating smoothed data. R6: Friedman et al. 2006 (NeuroImage 32:1656-1668)
      smoothness equalization reduces inter-scanner variability; Cox et al. 2017 ACF model. R9: CONN extracts ROI
      series from unsmoothed volumes by default. Empirical: 3dBlurToFWHM -ACF reached 8.10/7.81 mm (target 8)
      from 3.4/7.0 mm inputs vs about 11 mm with classic stopping; 3dmerge -doall on pre-masked data leaked into
      14,328 out-of-mask voxels; 3dAutomask dropped a 652-voxel low-signal region; unsmoothed seed was never worse
      than smoothed seed in simulation.</research>
      <decision status="decided" chosen="first-level-voxelwise-only">
        Principles (user): parcel-level extraction (including seed time series) never uses smoothed data;
        smoothing only for voxelwise maps; smoothing lives in fmri-first-level-proc, not the orchestrators.
        Method: 3dBlurToFWHM -FWHM target -ACF -mask, per run; mask derived from data (voxels with temporal
        max > min in every run, on unscaled input; never automask); QC per run: input/output ACF FWHM, mask voxel
        count and FOV fraction, graded warning outside +/-10% or input above target.
        Config: per-analysis block smoothing: {enabled, fwhm}; fwhm required when enabled; in T9 closed schema;
        orchestrators drop smoothing entirely.
        Naming: frozen T8 names always hold unsmoothed outputs; smoothed voxelwise outputs carry _s{int}mm or
        _s{int}p{dec}mm (e.g. _s6mm, _s6p5mm) and exist only when enabled.
        task_act: blur unscaled input before per-run PSC; smoothed GLM produces only _s{N}mm voxelwise outputs;
        unsmoothed GLM produces frozen-name outputs and all parcel outputs.
        task_conn: same pattern with one shared design matrix and survival table and two 3dLSS fits; Mode B
        blurring via sub-brick selectors then 3dTcat.
        rest_conn: denoise once unsmoothed; blur each run's residuals (residual is the blurmaster); concat.
        Seed-to-voxel (all types): seed series from unsmoothed data via 3dROIstats on the seed mask (see T11-nz),
        correlated with 3dTcorr1D -pearson [-Fisher] against the target (smoothed when enabled); verified equal to
        3dNetCorr -ts_wb_corr/-ts_wb_Z within 1.8e-4, Z capped at 4.
      </decision>
    </topic>

    <topic id="T11-psc" title="Percent-signal-change scaling">
      <research>R1: expression is afni_proc.py's default scale block ("be sure no negatives creep in"; cap
      -scale_max_val default 200). R2: voxelwise scaling preferred for spatially inhomogeneous baselines; SPM
      grand-mean scaling only approximates percent change; r is invariant to per-voxel scaling. Real fmri-preproc
      data: guards fire only in voxels with baselines 3-8% of the median and PSC SD 43-52% (typical about 3%);
      guarded values deviate less (1.9 SD) than unguarded (2.9 SD); interior baseline 95th/5th ratio about 5;
      mean-at-or-below-zero voxels max 1.33% over 24 runs.</research>
      <decision status="decided" chosen="keep-voxelwise-afni-formula">
        Voxelwise PSC is the only scaling; expression min(200,a/b*100)*step(a)*step(b) unchanged. InputError if
        at least 25% of masked voxels in a run have temporal mean at or below 0 (demeaned input). qc_summary per
        run: count/% of voxels with any guarded time point, any capped time point, and mean at or below 0.
        INPUT_SPEC documents expression, guards, cap, and QC fields.
      </decision>
    </topic>

    <topic id="T11-nz" title="User-selectable zero handling in parcel aggregation">
      <research>v3.1.0 inconsistency: ROI extraction used 3dROIstats -nz (per time point) while 3dNetCorr averaged
      with zeros included (up to 0.65 difference in r with 1% scattered zeros). 1ddot reproduces 3dNetCorr's
      correlation matrix within 4e-5; precision-matrix partial correlation within 5e-5; capped atanh within
      4.4e-5.</research>
      <decision status="decided" chosen="roi_zero_handling-exclude-default">
        Per-analysis roi_zero_handling: exclude (default) or include, with average_type mean or median, applied to
        every parcel-level aggregation (stat_buckets, residuals, raw and raw-PSC ptseries, beta series, rest
        ptseries, seed series, parcellated connectivity). All aggregation via 3dROIstats (exclude:
        -nz{mean|median} -nomeanout; include: default mean or -median). Parcellated connectivity: 1ddot on the
        extracted series (r and inverse), partial correlation from the inverse after the T6c rank gate, Fisher Z
        capped at 4, T6e null-ROI NaN handling and output format retained. qc_summary per ROI: voxel count (from
        atlas) and nonzero fraction. Release note: breaking change to parcellated connectivity. Contract tests
        against 3dNetCorr in include mode.
      </decision>
    </topic>

    <topic id="T11-lowbase" title="Low-baseline voxels in parcel averages">
      <decision status="decided" chosen="A-plain-aggregation">
        Model at the voxel level, then aggregate with plain mean/median (no ratio-of-means, no weighting, no
        exclusion threshold, no parcel-level modeling). qc_summary per parcel per run: low_baseline_fraction
        (voxels with temporal mean below 20% of the brain-mask median; reporting cutoff only) and
        median_baseline_ratio. INPUT_SPEC documents the trade-off (low-baseline voxels, about 6% of the mask with
        about 74 times the PSC variance, remain in plain means; median is the robust alternative).
      </decision>
    </topic>

    <topic id="T11-rawdoc" title="Documentation and notices for T11-raw">
      <decision status="decided" chosen="reconciled">
        INPUT_SPEC defines _raw_psc_ptseries via T11-psc, T11-nz, and T11-lowbase (README: one-line pointer).
        Breaking release note: rest_conn _run{N}_raw_ptseries.csv is now unscaled under default scale_to_psc.
        Orchestrator items split into two reports (see action items).
      </decision>
    </topic>

    <topic id="T11-b" title="Template resampling">
      <decision status="decided" chosen="ledgered-resample-once">
        Resample decision via 3dinfo -same_grid (first value). Resampling is a ledgered stage (type)-template
        declaring template_path, template file SHA-256 (sole exception to T11-optA's no-content-hash rule), and
        scan grid; 3dresample -master scan -rmode NN -overwrite -input template; output
        {out_file_pre}_{template}_resampled.nii.gz registered as an intermediate. Old staleness branch removed.
        Non-resampling template checks stay always-run.
      </decision>
    </topic>

    <topic id="T11-c" title="Consolidated T11 wiring">
      <decision status="decided" chosen="signed-off">
        Ledger as sole skip gate with per-stage hashing (T11-optA, T11-perstage). Always-run: stimulus parsing,
        onsets, censor/motion prep, run exclusion, T5/T7a dry runs, survival, DOF checks, template checks,
        qc_summary. Ledgered stages per type: template, prep, raw-ptseries, smooth (when enabled; none for rest),
        unsmoothed model (task_act glm; task_conn design-matrix then beta-series; rest residuals-run{n} then concat
        or residuals-concat), smoothed model (when enabled: glm-smooth, beta-series-smooth, smooth-residuals),
        parcel extraction (upstream unsmoothed model and template), connectivity (parcellated: unsmoothed model
        and template; seed-to-voxel: unsmoothed model plus smoothed model when enabled). New declared fields:
        smoothing.*, roi_zero_handling, derived polort and DOF-surrogate inputs. Exempt list and the two coverage
        tests unchanged.
      </decision>
    </topic>
  </topics>

  <amendments>
    <item ref="T6c/T6e">Parcellated connectivity now via 3dROIstats plus 1ddot rather than 3dNetCorr; rank gate,
    NaN handling, diagonal conventions retained (T11-nz).</item>
    <item ref="T6d">Simultaneous-backend DOF now parsed from the "D.O.F. left" line (T11-polort).</item>
    <item ref="T8">Frozen names always unsmoothed; smoothed outputs add _s{N}mm (SMOOTH-ARCH).</item>
    <item ref="T9">Closed schema gains smoothing.{enabled,fwhm} and roi_zero_handling.</item>
  </amendments>

  <action_items>
    <item priority="P0" target_mode="brainstorm" description="T11b: separate intermediate vs final outputs in FirstLevelResult.output_files (now includes resampled templates, _nosmooth-free naming, staging, s{N}mm outputs)." />
    <item priority="P0" target_mode="brainstorm" description="T12: v3.2.0 release scope, version number, schema_version, release-note format (many breaking changes accumulated), docs, legacy-CSV handling." />
    <item priority="P1" target_mode="brainstorm" description="Pre-Report Audit and final brainstorm report after T11b and T12." />
    <item priority="P1" target_mode="none" description="Write ABCD orchestrator report (O1-O5, remove smoothing, collect s{N}mm outputs) and a new fmri-proc-orchestrator report (remove smoothing, retiring the 3dmerge -doall bug; collect s{N}mm; O5); request write grants first." />
    <item priority="P2" target_mode="brainstorm" description="User may wish to review empirical checks run this session without prior approval (real-data PSC audit, AFNI equivalence checks, automask/censoring smoothing tests) whose results fed locked decisions." />
  </action_items>
  <next_steps>Resume /brainstorm at T11b, then T12, then the Pre-Report Audit and final report.</next_steps>
</brainstorm_report>
