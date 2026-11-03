<implement_plan>
  <meta project="fmri-first-level-proc" mode="implement" submodule="plan" timestamp="2026-10-12T15:28:47Z" />
  <input_reports>
    <report path="fmri-first-level-proc_test_20261012_151045.md" mode="test" key_items="3" />
  </input_reports>
  <assumptions_and_decisions>
    <item>Severity correction to the input report: its first action item describes the missing 1ddot -dem flag as affecting "every parcellated-connectivity result produced by the package to date". That is incorrect. The published v3.1.0 (tag v3.1.0) computed connectivity with 3dNetCorr, verified with git show v3.1.0. The defect exists only in unreleased v4.0.0 code on branch v4.0.0-build, so no released results are affected. Priority stays P0 because it blocks the v4.0.0 release.</item>
    <item>The rest_nuisance detection logic rests on an empirical probe the user approved, run on AFNI 26.0.09 with the same n=20 over-regressed configuration as tests/test_nuisance.py::test_over_regressed_run_crashes_instead_of_graceful_exclusion. 3dTproject exits with code 1 and prints no "D.O.F. left" line. Before aborting, its stderr contains "+ Block #0: 20 time points -- 17 stopband regressors" and "** ERROR: total number of fixed regressors (28) is too many for 20 retained time points!". The existing stopband regex already matches the first line. DOF is defined as retained time points minus total fixed regressors (20 - 28 = -8), the same quantity 3dTproject reports as "D.O.F. left" when it succeeds.</item>
    <item>The 1ddot -dem change needs no parser change. 1ddot -dem output keeps both the "++ Correlation Matrix:" and "++ Correlation Matrix Inverse:" blocks in the format parse_1ddot already reads. The REAL_1DDOT_OUTPUT fixture in tests/test_connectivity.py was regenerated with -dem in the preceding /test session, and its parser tests pass against it.</item>
  </assumptions_and_decisions>
  <changes>
    <change id="C1" priority="P0" source_item="test report action_item 1 (connectivity.py parcellated -dem)">
      <file path="fmri_first_level_proc/connectivity.py" action="modify" />
      <description>parcellated() calls 1ddot without -dem, so it computes the cosine similarity of non-demeaned ROI series instead of Pearson correlation. A shared baseline inflates independent ROIs to r=1.0. Adding -dem makes 1ddot remove each column's mean before computing the correlation matrix and its inverse, which gives Pearson correlation and correct partial correlation from the inverse.</description>
      <spec>
        1. In parcellated(), change the run_afni_command argument list from ["1ddot", series_path] to ["1ddot", "-dem", series_path]. Leave capture_output, description, logger and cwd unchanged.
        2. In the module docstring, change the line "Parcellated connectivity uses 3dROIstats + 1ddot with rank gate, partial" so that it states 1ddot runs with -dem (demeaned columns, so the matrix is Pearson correlation). Keep the rest of that docstring paragraph as is.
        3. In parcellated()'s docstring, change "Compute parcellated connectivity via 3dROIstats + 1ddot." to "Compute parcellated (Pearson) connectivity via 3dROIstats + 1ddot -dem."
        No other logic changes: rank_check already demeans independently, and parse_1ddot already handles -dem output.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - one-token argument addition. parse_1ddot is already verified against real 1ddot -dem output.</risk>
      <rollback>Remove "-dem" from the argument list and revert the two docstring lines.</rollback>
    </change>
    <change id="C2" priority="P1" source_item="test report action_item 2 (runtime.py load_lockfile non-dict guard)">
      <file path="fmri_first_level_proc/runtime.py" action="modify" />
      <description>load_lockfile() joins the type check and the version check in one condition, then calls lock.get() in the error message. When the YAML top level is not a mapping (for example a list), building that message raises AttributeError instead of the documented ToolUnavailableError.</description>
      <spec>
        In load_lockfile(), replace the single "Structural validation" block
          if not isinstance(lock, dict) or lock.get("lockfile_version") != "2.0.0": raise ToolUnavailableError(... lock.get('lockfile_version') ...)
        with two sequential checks:
          (a) if not isinstance(lock, dict): raise ToolUnavailableError(f"Packaged lockfile '{LOCKFILE_RESOURCE}' top level must be a mapping, got {type(lock).__name__}.")
          (b) if lock.get("lockfile_version") != "2.0.0": raise ToolUnavailableError(f"Packaged lockfile lockfile_version must be '2.0.0', got {lock.get('lockfile_version')!r}.")
        Message (b) stays word-for-word identical to the current message. All later validation (tools mapping, per-tool fields) is unchanged.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - splits an existing guard. The error type and message on the valid-dict path are unchanged.</risk>
      <rollback>Restore the single combined condition.</rollback>
    </change>
    <change id="C3" priority="P1" source_item="test report action_item 3 (nuisance.py rest_nuisance over-regressed DOF dry run)">
      <file path="fmri_first_level_proc/nuisance.py" action="modify" />
      <description>In the simultaneous backend, rest_nuisance() raises ToolExecutionError whenever the 3dTproject DOF dry run prints no "D.O.F. left" line. When fixed regressors reach or exceed the retained time points, 3dTproject aborts and prints no DOF line. That is exactly the DOF &lt; 1 case the function is meant to handle by excluding the run (reason dof_below_1, RUN_SKIPPED warning). Instead, one short or over-regressed run currently halts the whole multi-run analysis.</description>
      <spec>
        In rest_nuisance(), simultaneous-backend branch (the block after cp = run_afni_capture(dry_cmd, ...)):
        1. Keep the existing k_match = re.search(r"(\d+)\s+stopband regressors", text) and dof_match = re.search(r"==>\s*(-?\d+)\s+D\.O\.F\. left", text).
        2. Add over_match = re.search(r"total number of fixed regressors \((\d+)\) is too many for (\d+) retained time points", text).
        3. Replace the current single guard (if not k_match or not dof_match: raise ToolExecutionError(...)) with:
           - if k_match and dof_match: n_stopband = int(k_match.group(1)); dof = int(dof_match.group(1))  (current behavior)
           - elif k_match and over_match: n_stopband = int(k_match.group(1)); dof = int(over_match.group(2)) - int(over_match.group(1))
           - else: raise ToolExecutionError with the current message text unchanged ("3dTproject DOF dry run for run {lbl}: could not parse stopband regressors or DOF from output. Return code: {cp.returncode}. stderr: {...}").
        4. The assignments that follow (bandpass_dim = None, bandpass_dim_null_reason = "simultaneous_backend", n_stopband_regressors = n_stopband, n_stopband_null_reason = None) are unchanged and apply to both success branches.
        5. Nothing changes downstream. run_dof[lbl] = dof, the "if dof &lt; 1" exclusion (RUN_SKIPPED warning, excluded reason "dof_below_1"), the per_run_dof QC record (which now carries the negative DOF, e.g. -8), and the ModelError when every run is excluded all behave as before. The computed dof from the over-regression branch is always &lt;= 0, so the run is always excluded.
        6. Add one short comment above over_match explaining that 3dTproject aborts with no DOF line when fixed regressors &gt;= retained time points, and that this text is what lets the DOF be computed for that case.
        The sequenced backend (3dBandpass probe) is untouched.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - adds one recognized failure path. Every other failure, such as an unreadable input or a malformed command, still raises ToolExecutionError with the same message. The regex text comes from verified AFNI 26.0.09 output, and the package pins AFNI 26.0.09 in its lockfile.</risk>
      <rollback>Restore the single "if not k_match or not dof_match: raise" guard and remove over_match.</rollback>
    </change>
  </changes>
  <execution_order>C1, C2, C3</execution_order>
  <downstream_test_impact>
    After the build, /test has to re-express tests/test_nuisance.py::test_over_regressed_run_crashes_instead_of_graceful_exclusion. That test currently pins the crash with pytest.raises(ToolExecutionError) and will start failing once the crash is gone. Its replacement should assert the intended contract: the outcome is (excluded = [{"run": 1, "reason": "dof_below_1"}] with per_run_dof[0]["dof"] == -8) for a two-run configuration where the other run survives, or a ModelError when the over-regressed run is the only run. tests/test_connectivity.py::TestParcellatedDemeanBug (2 tests) and tests/test_runtime.py::TestLoadLockfile::test_non_dict_top_level_raises should pass after the build with no test edits.
  </downstream_test_impact>
</implement_plan>
