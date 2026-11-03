<implement_report>
  <meta project="fmri_first_level_proc" mode="implement" submodule="build" timestamp="2026-08-13T13:45:00Z" />
  <spec_ref>fmri_first_level_proc_implement_plan_20260813_131930.md</spec_ref>
  <changes_applied>
    <change id="C1" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_utils.py" lines_changed="18" />
      </files_modified>
      <notes>Centralized ToolExecutionError wrapping in run_afni_command; updated 3 catch-update sites (CalledProcessError to ToolExecutionError); removed 2 redundant try/except blocks (validate_template, extract_roi_stats); changed 2 ValueError raises to ConfigError in build_hrf_string; updated stale SystemExit docstring in compute_matrix_contrast; updated version header to 3.0.0.</notes>
    </change>

    <change id="C2" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_act_first_level.py" lines_changed="16" />
      </files_modified>
      <notes>Updated 2 catch-update sites; removed 3 redundant try/except blocks (3dDeconvolve, 3dinfo, T-to-Z 3dcalc); inserted polort A polynomial regressor estimate (4 lines) before compute_dof call; updated 2 stale docstrings to BIDS column naming; updated version header to 3.0.0.</notes>
    </change>

    <change id="C3" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_conn_first_level.py" lines_changed="7" />
      </files_modified>
      <notes>Inserted polort A polynomial regressor estimate before compute_dof call; updated 2 stale docstrings to BIDS column naming; updated version header to 3.0.0.</notes>
    </change>

    <change id="C4" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/rest_conn_first_level.py" lines_changed="4" />
      </files_modified>
      <notes>Removed unused import time; updated version header to 3.0.0; narrowed except Exception to ToolExecutionError in _generate_run_residual_simultaneous; narrowed except Exception to (ToolExecutionError, OSError) in _generate_run_residual_sequenced. The cleanup block's except Exception (shutil.rmtree) was left unchanged per spec.</notes>
    </change>

    <change id="C5" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/run_first_level.py" lines_changed="12" />
      </files_modified>
      <notes>Updated version header to 3.0.0; added import subprocess; replaced unconditional probe_tool_versions call with _LOCKFILE_PATH.exists() guard and graded_warning on absence; added subprocess.CalledProcessError safety net (exit 4) and generic Exception safety net (exit 1) after the GuardError handler.</notes>
    </change>

    <change id="C6" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/runtime.py" lines_changed="1" />
      </files_modified>
      <notes>Narrowed except Exception to (subprocess.SubprocessError, OSError) in probe_tool_versions.</notes>
    </change>

    <change id="C7" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/checkpoint.py" lines_changed="1" />
      </files_modified>
      <notes>Updated version header from 2.5.0 to 3.0.0.</notes>
    </change>

    <change id="C8" status="done" user_decision="n/a">
      <files_modified>
        <file path="tests/test_error_paths.py" lines_changed="6" />
        <file path="tests/test_roi_extraction.py" lines_changed="1" />
      </files_modified>
      <notes>Updated 3 mock side_effects from raising subprocess.CalledProcessError to ToolExecutionError (test_error_paths.py L45, L75, L104); updated task_conn docstring and assertion from CalledProcessError to ToolExecutionError (L69, L89); updated 1 mock side_effect in test_roi_extraction.py (L89). ToolExecutionError was already imported in both test files.</notes>
    </change>
  </changes_applied>
  <summary>
    <total_changes>8</total_changes>
    <completed>8</completed>
    <skipped>0</skipped>
    <blocked>0</blocked>
  </summary>
  <next_steps>Recommended: run /test run_suite to validate all changes across the full 635+ test suite.</next_steps>
</implement_report>
