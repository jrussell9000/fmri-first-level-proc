<brainstorm_report>
  <meta project="fmri-first-level-proc" mode="brainstorm" timestamp="2026-10-16T19:37:30Z" scope="upstream response to ABCD_fmri_orchestrator_S3_brainstorm_upstream_20261015_150913.md" companion="ABCD_fmri_orchestrator_S3/fmri-first-level-proc_brainstorm_downstream_20261016_193730.md (orchestrator-side findings O1-O5)" />

  <context_files>
    <file path="ABCD_fmri_orchestrator_S3_brainstorm_upstream_20261015_150913.md" relevance="Inbound orchestrator report (U1-U5, D1-D3). Every factual claim and line reference was verified against branch v4.0.0-build." />
    <file path="fmri_first_level_proc/nuisance.py" relevance="Censoring (_censor 49-94, 1d_tool.py -censor_motion), task_nuisance QC (296-322), rest notch (381-406), rest DOF dry-run regressor count (355-361)." />
    <file path="fmri_first_level_proc/events.py" relevance="Mode A per-file required-condition check (130-135, called at 206); timing violations fatal; onset_file_text writes '*' for empty runs (476-478)." />
    <file path="fmri_first_level_proc/task_act_first_level.py" relevance="Unsmoothed GLM -gltsym (781-788) and bucket index (804-808); smoothed GLM without contrasts or indexes (964-1018); stat_bucket_parcellations writes index plus CSV together (262-300); apply_floor drops conditions with no surviving trials (569-579)." />
    <file path="fmri_first_level_proc/task_conn_first_level.py" relevance="non_beta_conditions from all supplied runs (337-339) while onsets and design use S_pre (347-352, 446-460)." />
    <file path="fmri_first_level_proc/rest_conn_first_level.py" relevance="Per-run GS derivative (544-552) vs concat mode omission (661-670)." />
    <file path="fmri_first_level_proc/names.py" relevance="censor_prefix/censor/censor_side_files (154-166); bucket_stats_index and stat_index without token (229-238); with_token (73-84)." />
    <file path="fmri_first_level_proc/qc.py" relevance="Closed QC_KEYS schema (44-70)." />
    <file path="INPUT_SPECIFICATION.md" relevance="fd_threshold (79), remove_previous (77), extra-conditions statement (364), motion file contract (366-378), censor file (380-382), Tools Lockfile (412-424), Version Lock Validation (570-584)." />
    <file path="ABCD_fmri_orchestrator_S3/orchestrate_first_level.py, orchestrator_utils.py, proc_config_abcd-v7.yaml, orch_config_abcd-v7.yaml" relevance="Read directly for harmonization: imports, names.* helpers, lockfile schema, closed config schema keys and QC key consumption all match upstream v4. Orchestrator-side findings are in the companion report." />
  </context_files>

  <topics>
    <topic id="T1" title="U1 Power FD censoring supersedes CR F11 Option A">
      <summary>The 2026-10-11 CR (F11) chose documentation-only: keep AFNI enorm. The orchestrator's U1 switches censoring to Power et al. (2012) FD. Field-consensus censoring thresholds are FD in mm.</summary>
      <research>Hagler et al. 2019 (NeuroImage 202:116091), receipt-verified by the orchestrator: task "Time points with FD greater than 0.9 mm are censored"; rest "Frames with displacement (FD) greater than 0.3 mm are excluded from the regression".</research>
      <decision status="decided" chosen="U1 as written">Adopt U1 exactly as specified in the orchestrator report (both metrics computed from the same motion series, rest after notch filtering; censor on Power FD with rotations degrees x pi/180 x 50, difference 0 at each run's first TR; censor_prev_tr applies to FD; no censor_metric config key; both metrics recorded; nuisance.py docstring and INPUT_SPECIFICATION updated; U1 test list). This supersedes CR F11 Option A. Implementation details are fixed by T4(i) and A1.</decision>
    </topic>

    <topic id="T2" title="Motion column order and rotation units under FD">
      <summary>Enorm is invariant to column order and weights all six columns equally; FD weights rotations by 0.8727 and translations by 1, so order and units become load-bearing.</summary>
      <research>Local AFNI 3dvolreg -help: -1Dfile writes "roll pitch yaw dS dL dP" (rotations first, degrees). Swapping blocks biases FD by roughly -13% to +15%. fMRIPrep-style confounds conventionally carry rotations in radians (FSL MCFLIRT convention); passing radians as degrees shrinks the FD rotation term about 57x. The orchestrator selects trans_x..rot_z by name (order correct) from the cloudpipe desc-confounds_timeseries.tsv and applies no unit conversion. Proposal verification 3/3 verified.</research>
      <decision status="decided" chosen="A: fixed contract plus documentation; orchestrator cross-check">(a) Keep the fixed motion contract ([tx, ty, tz, rx, ry, rz], mm and degrees), no new config key. Document in INPUT_SPECIFICATION and the nuisance.py module docstring that AFNI 3dvolreg -1Dfile/-dfile output must be reordered to translations-first and that fMRIPrep confounds rotations (radians) must be converted to degrees, stating the FD error caused by each mistake (order: about -13% to +15%; radians: rotation term about 57x too small). (b) The rotation-unit verification belongs to the orchestrator (companion O1).</decision>
    </topic>

    <topic id="T3" title="U3 smoothed task_act contrasts and indexes">
      <summary>The smoothed GLM omits -gltsym and writes neither the bucket index nor per-stat index JSONs, so smoothed buckets silently carry fewer sub-bricks.</summary>
      <research>Proposal verification: 2 verified, 1 concerns (minor; folded in below).</research>
      <decision status="decided" chosen="A1 extended">(1) Build the -gltsym/-glt_label sequence in one helper from the estimability-filtered contrast list (ctx._kept_contrasts, config.contrast_labels) and call it from both the unsmoothed and smoothed GLM stages. (2) Add an optional token argument (default "") to names.bucket_stats_index and names.stat_index, giving {pre}_concat_bucket_stats_index{token}.json and {ext}_{stat}_index{token}.json; unsmoothed names unchanged. (3) The smoothed GLM writes the tokened bucket index via generate_bucket_stats_index; the smoothed stat-bucket extraction writes a tokened per-stat index JSON per extracted bucket. Split index writing out of stat_bucket_parcellations into its own function used by both paths; smoothed buckets still get no parcellated CSV. (4) Add both tokened names to the task_act expected-output set; documentation of all smoothed outputs goes to U5. (5) Tests: smoothed and unsmoothed bucket sub-brick label lists identical; each smoothed index JSON equal to its unsmoothed counterpart; each smoothed stat bucket has the same volume count as its unsmoothed counterpart.</decision>
    </topic>

    <topic id="T4" title="U2, U4, U5, D1-D3 adopted, with additions">
      <summary>All verified against code. U2 is safe downstream: conditions with no surviving trials are already dropped with their contrasts by apply_floor. U4 also fixes an off-by-one between the concat-mode DOF dry run (which counts the GS derivative) and the fitted model.</summary>
      <research>1d_tool.py -help: -censor_motion censors when enorm >= LIMIT (inclusive); derivative of a run's first TR is 0. Metric bounds: for weights w = (1,1,1,c,c,c), c = 0.8727, FD/enorm lies in [c, sqrt(3+3c^2)] = [0.873, 2.299]; numerically confirmed (2 million random vectors: 0.955 to 2.298; single 1-degree rotation gives enorm 1.0, FD 0.873). Proposal verification: 1 verified, 2 concerns; both concerns disputed (iv) by treating FD and enorm as norms of one vector, which does not hold because enorm leaves rotations unweighted; the user adjudicated in favor of the stated bounds.</research>
      <decision status="decided" chosen="Adopt as written plus (i)-(iv)">Adopt U2, U4, U5, D1, D2, D3 as written in the orchestrator report, plus: (i) censor a TR when FD > fd_threshold (strict, following ABCD DAIRC wording; deliberately differs from 1d_tool.py's >=); censor_prev_tr censors only the immediately preceding TR, never across a run boundary since FD is 0 at each run's first TR. (ii) U4 test: in rest concat mode the DOF recorded from the dry run equals the residual DOF of the model actually fitted. U4 writes the concat-mode GS derivative to {subdir}/GS_deriv.1D, mirroring the existing CSF/WM pattern. (iii) U5 additionally corrects INPUT_SPECIFICATION:364 (unlisted timing-file conditions are ignored by task_act but modeled as nuisance regressors by task_conn) and documents all smoothed task_act outputs (blurred runs, smoothed bucket and residuals, smoothed stat buckets, both tokened indexes). (iv) The metric relation is 0.873 x enorm &lt;= FD &lt;= 2.30 x enorm (replaces the report's 2.45).</decision>
    </topic>

    <topic id="T5" title="task_conn nuisance conditions confined to excluded runs (new finding)">
      <summary>non_beta_conditions is built from all supplied runs while onset files and the design use S_pre; a nuisance condition whose events all lie in excluded runs gets an all-'*' onset file and an all-zero -stim_times regressor; the package passes neither -allzero_OK nor -GOFORIT. U2's union rule makes run-confined conditions more likely. ABCD risk is low (target_0back and instruction occur in both n-back runs).</summary>
      <research>Proposal verification: 2 verified, 1 concerns (minor; folded in).</research>
      <decision status="decided" chosen="Restrict to modeled runs">(1) non_beta_conditions = event_table.for_runs(s_pre).conditions() minus cond_beta_labels, computed once and used for onset files, -num_stimts and the beta regressor index. (2) When a supplied-run nuisance condition is omitted this way, emit a logger.warning naming the condition and the excluded runs (ordinary logging; no new graded-warning code). (3) Real-AFNI test: two supplied runs, a non-beta condition only in a run excluded before modeling; assert the analysis completes, no onset file or design column exists for that condition, and the beta series equals that from the same data with the condition removed from the timing files. (4) Ships in v4.0.0 with U2.</decision>
    </topic>

    <topic id="T6" title="Report back to the ABCD orchestrator">
      <summary>Orchestrator code was read directly. Its imports, names.* helpers, lockfile schema, closed-schema config keys and QC consumption match upstream v4. Five items go back.</summary>
      <research>Proposal verification 3/3 verified (minor concerns folded in).</research>
      <decision status="decided" chosen="Companion report O1-O5">Deliver O1-O5 as a separate scope="downstream" companion report written to the ABCD_fmri_orchestrator_S3 project root (user-selected delivery).</decision>
    </topic>

    <topic id="A1" title="U1 output filenames and QC keys">
      <summary>U1 required both metrics as per-TR series and QC summaries but named neither.</summary>
      <research>No code in either project reads _CENSORTR.txt or _enorm.1D; the orchestrator reads only pct_censored and uploads result.output_files. Proposal verification 3/3 verified.</research>
      <decision status="decided" chosen="Spec as below">(1) Keep {pfx}_censor.1D; the censor vector comes from Python thresholding on FD and 1d_tool.py -censor_motion is no longer called. (2) Keep {pfx}_enorm.1D, computed with 1d_tool.py -set_run_lengths ... -derivative -collapse_cols euclidean_norm. (3) Add {pfx}_fd.1D: per-TR Power FD (50 mm, 0 at each run's first TR; rest uses notch-filtered motion when notch_filter_band is set). (4) Drop {pfx}_CENSORTR.txt; names.censor_side_files returns [enorm, fd]. (5) QC keys: censor_metric = "power_fd" and fd_radius_mm = 50 (from {t}-qc, all types); fd_summary and enorm_summary, each {mean, median, max} over all TRs of the model runs including censored TRs (from {t}-nuisance, all types); rest per_run_censoring records gain fd_mean, fd_max, enorm_mean, enorm_max.</decision>
    </topic>
  </topics>

  <action_items>
    <item priority="P0" target_mode="implement" description="U1 per T1, T4(i), A1 (Power FD censoring, enorm and FD series, QC keys, CENSORTR removal) with the U1 test list and A1 output/QC assertions." />
    <item priority="P0" target_mode="implement" description="U2 (union-of-runs required conditions, Mode A) with its tests for task_act and task_conn." />
    <item priority="P0" target_mode="implement" description="U3 per T3 items 1-5." />
    <item priority="P0" target_mode="implement" description="U4 per T4(ii): concat-mode GS derivative, both-modes nuisance-column test, recorded-vs-fitted DOF test." />
    <item priority="P0" target_mode="implement" description="T5 items 1-3: task_conn nuisance conditions restricted to modeled runs, warning log line, real-AFNI test." />
    <item priority="P0" target_mode="implement" description="nuisance.py module docstring updated for U1 and T2(a)." />
    <item priority="P1" target_mode="document" description="U5 as written plus T2(a) motion-order/units documentation, T4(iii) corrections, A1 filenames and QC keys, T3 smoothed outputs." />
    <item priority="P0" target_mode="none" description="Tag upstream v4.0.0 only after all P0 items land, the full suite passes and /document completes; supersedes cross-session AI-016." />
    <item priority="P2" target_mode="none" description="Open GitHub issues for D1, D2 and D3." />
  </action_items>

  <next_steps>/implement plan against this report (U1-U4, T5, A1, docstrings), then /implement build, then /test, then /document for U5 and the documentation items, then commit, merge, tag and publish v4.0.0. The orchestrator works the companion report's O1-O5 in parallel; O1 must be resolved before production FD censoring is trusted.</next_steps>
</brainstorm_report>
