<implement_plan>
  <meta project="fmri-first-level-proc" mode="implement" submodule="plan" timestamp="2026-10-26T17:32:41Z" />
  <input_reports>
    <report path="fmri-first-level-proc_brainstorm_20261026_133954.md" mode="brainstorm" key_items="5" />
  </input_reports>

  <assumptions_and_resolutions>
    <item>Single-stage rest path (keep_run_res_dtseries false) failed-run propagation: resolved by the user (2026-10-26) to populate failed_runs_record after ctx.run_stage from the stage's QC fragment (latest_qc["failed_runs"]), not from inside the stage function, so fresh and ledger-reused executions yield identical excluded_runs.</item>
    <item>The points-left abort branch is evaluated first in the dry-run parser. Justification: an aborted 3dTproject run cannot emit a "D.O.F. left" line, and the orchestrator's real-data evidence shows the points-left check precedes the fixed-regressor check, so ordering cannot change any currently-parsed outcome.</item>
    <item>n_stopband_null_reason is moved from the trailing unconditional assignment into each simultaneous-backend branch; values for the two pre-existing branches are unchanged (None).</item>
    <item>The captured minimum-frame count is used only in the log message, never as a decision input (per the "do not hard-code the minimum" directive).</item>
    <item>task_conn_expected gains a required positional parameter non_beta_conditions; it has exactly one caller (task_conn_first_level.py:1038), where non_beta_conditions (defined at line 338) is already in scope. No test calls the function directly.</item>
    <item>The brainstorm's test items (U6 tests, U7 test, CENSOR_HIGH test hardening) and documentation items are not part of this implement pass; they go to /test and the deferred /document pass respectively.</item>
  </assumptions_and_resolutions>

  <changes>
    <change id="C1" priority="P0" source_item="U6 (7)">
      <file path="fmri_first_level_proc/nuisance.py" action="modify" />
      <description>Import GuardError for the new dry-run invariant guards.</description>
      <spec>Line 39: change `from .exceptions import InputError, ModelError, ToolExecutionError` to `from .exceptions import GuardError, InputError, ModelError, ToolExecutionError`.</spec>
      <dependencies>none</dependencies>
      <risk>low - import only.</risk>
      <rollback>Revert the import line.</rollback>
    </change>

    <change id="C2" priority="P0" source_item="U6 (1)-(6)">
      <file path="fmri_first_level_proc/nuisance.py" action="modify" />
      <description>rest_nuisance simultaneous-backend DOF dry-run parser: recognize the 3dTproject "only N points left after censoring" abort and convert it into a synthetic DOF below 1 so the existing dof_below_1 exclusion handles the run, instead of raising ToolExecutionError.</description>
      <spec>
In rest_nuisance, simultaneous-backend block (currently lines 576-602):

1. After the existing `over_match = re.search(...)` statement, add:
```python
            # 3dTproject aborts before regression when censoring leaves fewer
            # than its minimum retained frames; no DOF or stopband count is
            # reported, so DOF is reconstructed from the fixed regressors.
            left_match = re.search(
                r"only (\d+) points left after censoring -- cannot continue "
                r"\(need at least (\d+)\)",
                text,
            )
```
2. Replace the if/elif/else chain and the trailing assignments with:
```python
            if left_match:
                n_left = int(left_match.group(1))
                n_min = int(left_match.group(2))
                if n_left != n_uncensored:
                    raise GuardError(
                        f"3dTproject DOF dry run for run {lbl}: reported "
                        f"{n_left} points left after censoring, but the censor "
                        f"vector retains {n_uncensored}."
                    )
                dof = n_uncensored - n_orts - (polort + 1)
                if dof >= 1:
                    raise GuardError(
                        f"3dTproject DOF dry run for run {lbl}: censoring abort "
                        f"(points left {n_left}, minimum {n_min}) produced "
                        f"reconstructed DOF={dof} >= 1."
                    )
                logger.info(
                    "Run %s: 3dTproject dry run aborted (%d points left after "
                    "censoring, minimum %d); reconstructed DOF=%d.",
                    lbl, n_left, n_min, dof,
                )
                n_stopband = None
                n_stopband_null_reason = "dry_run_aborted_censoring"
            elif k_match and dof_match:
                n_stopband = int(k_match.group(1))
                dof = int(dof_match.group(1))
                n_stopband_null_reason = None
            elif k_match and over_match:
                n_stopband = int(k_match.group(1))
                dof = int(over_match.group(2)) - int(over_match.group(1))
                n_stopband_null_reason = None
            else:
                raise ToolExecutionError(  # unchanged message
                    ...
                )
            bandpass_dim = None
            bandpass_dim_null_reason = "simultaneous_backend"
            n_stopband_regressors = n_stopband
```
The former line `n_stopband_null_reason = None` after `n_stopband_regressors = n_stopband` is removed (now assigned per branch). The ToolExecutionError message text is unchanged. Nothing downstream changes: `run_dof[lbl] = dof`, the dof &lt; 1 RUN_SKIPPED/dof_below_1 exclusion, the per_run_dof record (which now carries n_stopband_regressors=None and n_stopband_regressors_null_reason="dry_run_aborted_censoring" for aborted runs), and the "Every run has DOF &lt; 1" ModelError all apply as-is. The sequenced backend is untouched.
      </spec>
      <dependencies>C1</dependencies>
      <risk>low - additive parse branch; existing branches keep identical outputs. Sign of the reconstructed DOF is guaranteed by config floors (n_orts &gt;= 8, polort + 1 &gt;= 2, branch fires only at n_uncensored &lt;= minimum - 1) and enforced by a GuardError.</risk>
      <rollback>Restore the original three-branch chain and the trailing `n_stopband_null_reason = None`.</rollback>
    </change>

    <change id="C3" priority="P0" source_item="U7 (1)-(3)">
      <file path="fmri_first_level_proc/nuisance.py" action="modify" />
      <description>rest_nuisance QC fragment: compute n_trs_total, n_trs_censored and pct_censored over S_pre (matching fd_summary/enorm_summary and task_nuisance), evaluate CENSOR_HIGH on that value with the task_nuisance message wording. per_run_censoring keeps every supplied run.</description>
      <spec>
Replace the block currently at lines 719-734 (from `# QC fragment` through the three total keys) with:
```python
    # QC fragment (totals over S_pre; per_run_censoring covers every supplied run)
    s_pre_set = set(s_pre_labels)
    total_vols = sum(runsets.run(lbl).n_vols for lbl in s_pre_labels)
    n_censored = sum(
        r["n_trs_censored"] for r in per_run_censoring if r["run"] in s_pre_set
    )
    pct_censored = round(100.0 * n_censored / total_vols, 2) if total_vols > 0 else 0.0

    if pct_censored > CENSOR_HIGH_PCT:
        graded_warning(
            logger, "high", "CENSOR_HIGH",
            f"{pct_censored}% of TRs censored (threshold: {CENSOR_HIGH_PCT}%).",
            user_facing=True,
        )

    qc_frag = {
        "n_trs_total": total_vols,
        "n_trs_censored": n_censored,
        "pct_censored": pct_censored,
```
The remaining qc_frag keys (fd_summary, enorm_summary, per_run_censoring, per_run_dof) and the state dict are unchanged. Variables total_all, censored_all and pct_all are removed (verify no other reference remains in the function). Severity, code and threshold of CENSOR_HIGH are unchanged; excluded runs keep their own RUN_SKIPPED warnings.
      </spec>
      <dependencies>none (independent of C2 in code; the U7 test depends on C2)</dependencies>
      <risk>low - changes reported QC values only when some supplied run is DOF-excluded; no decision logic in this package or the orchestrator consumes these keys.</risk>
      <rollback>Restore the all-supplied-run totals and the "across all supplied runs" message.</rollback>
    </change>

    <change id="C4" priority="P2" source_item="F1">
      <file path="fmri_first_level_proc/task_act_first_level.py" action="modify" />
      <description>Correct the stat_bucket_parcellations docstring, which still claims to write index JSONs (now written by write_stat_indexes).</description>
      <spec>Line 301: change `"""Write parcellated CSVs and index JSONs for each extracted stat bucket.` to `"""Write parcellated CSVs for each extracted stat bucket.` No other edit.</spec>
      <dependencies>none</dependencies>
      <risk>low - docstring only.</risk>
      <rollback>Revert the line.</rollback>
    </change>

    <change id="C5" priority="P1" source_item="F4">
      <file path="fmri_first_level_proc/task_conn_first_level.py" action="modify" />
      <description>Add the per-condition nuisance onset files to task_conn's expected-output set so ctx.finish's retirement sweep treats them consistently with the beta onset file.</description>
      <spec>
1. Signature (line 101): `def task_conn_expected(config, runsets, surviving_conditions, non_beta_conditions):`
2. Replace the onset block (lines 153-154) with:
```python
    # Onset files (nuisance + beta)
    for cond in non_beta_conditions:
        expected.add(names.onset_file(pre, cond))
    expected.add(names.beta_onsets(pre))
```
3. Call site (line 1038): `expected = task_conn_expected(config, runsets, surviving_conditions, non_beta_conditions)`.
non_beta_conditions is the list computed at line 338 (model conditions over S_pre excluding cond_beta_labels), the same list _onsets_step iterates to write the files, so expected and written sets agree by construction. The docstring is unchanged except that no new section is needed.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - single caller; expected-set additions match files the onsets step already writes and registers.</risk>
      <rollback>Remove the parameter, the loop, and the call-site argument.</rollback>
    </change>

    <change id="C6" priority="P1" source_item="F3 (placement per user decision 2026-10-26)">
      <file path="fmri_first_level_proc/rest_conn_first_level.py" action="modify" />
      <description>Single-stage rest residual path (keep_run_res_dtseries false): runs that fail regression appear in the stage's failed_runs QC key but never reach failed_runs_record, so they are missing from excluded_runs (reason run_failed), unlike the per-run-stage path. Populate failed_runs_record from the stage's QC fragment after ctx.run_stage so fresh and ledger-reused executions agree.</description>
      <spec>
In the `else:` branch (single-stage path), after the existing loop that sets `latest_qc` (currently lines 729-732) and before the `s_final_labels = getattr(...)` line, add:
```python
        for f in (latest_qc or {}).get("failed_runs", []):
            failed_runs_record.append({"run": f["run"], "error": f["error"]})
```
`failed_runs_record` is the list initialized at line 496 in the same function scope (no closure or nonlocal needed, since this code is outside _concat_mode_stage). latest_qc is populated on both fresh execution (engine.py:630) and reuse (engine.py:570). The final assembly at lines 991-993 then includes these runs in excluded_runs with reason run_failed. No change to _concat_mode_stage itself, to the failed_runs QC key, or to the S_final derivation.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - additive to the QC excluded_runs list; failed runs are already absent from S_final. rest_expected (line 290) accepts excluded_runs but never reads it (verified: its body uses only s_pre and s_final), so the expected set is unchanged.</risk>
      <rollback>Remove the two added lines.</rollback>
    </change>
  </changes>

  <execution_order>C1, C2, C3, C4, C5, C6</execution_order>

  <testing_note>No tests are run in this skill. Tests for C2 and C3 (two-run partial abort, all-runs abort ModelError, per_run_dof null reason, S_pre-scoped totals) and the unconditional CENSOR_HIGH assertion are specified in the input report for /test. C4-C6 have no new tests specified; C6 is exercised by the existing test_rest_conn_pipeline.py end-to-end tests, which do not currently assert excluded_runs for a failed single-stage run.</testing_note>
</implement_plan>
