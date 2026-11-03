<implement_report>
  <meta project="fmri-first-level-proc" mode="implement" submodule="build" timestamp="2026-10-12T15:35:09Z" />
  <spec_ref>fmri-first-level-proc_implement_plan_20261012_152847.md</spec_ref>
  <changes_applied>
    <change id="C1" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/connectivity.py" lines_changed="5" />
      </files_modified>
      <notes>parcellated() now calls ["1ddot", "-dem", series_path]. The module docstring and the parcellated() docstring now state that the result is Pearson correlation from demeaned columns. No deviations from the spec.</notes>
    </change>
    <change id="C2" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/runtime.py" lines_changed="6" />
      </files_modified>
      <notes>The combined guard in load_lockfile() is now two checks. The first is a type check that raises ToolUnavailableError ("top level must be a mapping, got {type}"). The second is the version check, with its original message unchanged. No deviations from the spec.</notes>
    </change>
    <change id="C3" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/nuisance.py" lines_changed="16" />
      </files_modified>
      <notes>The simultaneous-backend DOF dry run in rest_nuisance() now recognises 3dTproject's "total number of fixed regressors (N) is too many for M retained time points" abort text. It computes DOF as M - N, and the existing dof_below_1 exclusion path then excludes the run. Any other unparseable output still raises ToolExecutionError with the original message. A one-line comment explains the abort case. No deviations from the spec.</notes>
    </change>
  </changes_applied>
  <summary>
    <total_changes>3</total_changes>
    <completed>3</completed>
    <skipped>0</skipped>
    <blocked>0</blocked>
  </summary>
  <next_steps>Recommended: run /test to validate all changes. Expected test effects: tests/test_connectivity.py::TestParcellatedDemeanBug (2 tests) and tests/test_runtime.py::TestLoadLockfile::test_non_dict_top_level_raises should now pass unchanged. tests/test_nuisance.py::test_over_regressed_run_crashes_instead_of_graceful_exclusion pins the old crash, so it will now fail. /test should rewrite it to assert graceful exclusion: excluded reason dof_below_1 with per_run_dof dof == -8 when another run survives, and ModelError when the over-regressed run is the only run. All three edited modules were syntax-checked with py_compile only; no tests were run during the build.</next_steps>
</implement_report>
