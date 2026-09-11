<brainstorm_report>
  <meta project="fmri_first_level_proc" mode="brainstorm" timestamp="2026-08-13T12:56:01Z" />
  <context_files>
    <file path="fmri_first_level_proc_cr_20260813_083501.md" relevance="Upstream CR report containing 10 findings (F1-F10) that motivated this brainstorm session" />
    <file path="fmri_first_level_proc/first_level_utils.py" relevance="Contains run_afni_command (L1078-1126), compute_dof (L1454-1492), build_hrf_string, and downstream CalledProcessError catch sites" />
    <file path="fmri_first_level_proc/run_first_level.py" relevance="CLI entry point with lockfile path resolution (_LOCKFILE_PATH at L94) and exit code mapping" />
    <file path="fmri_first_level_proc/task_act_first_level.py" relevance="Task activation pipeline with CalledProcessError catch sites and DOF preflight (L710-720)" />
    <file path="fmri_first_level_proc/task_conn_first_level.py" relevance="Task connectivity pipeline lacking CalledProcessError wrapping and DOF preflight (L752)" />
    <file path="fmri_first_level_proc/rest_conn_first_level.py" relevance="Resting-state pipeline with broad except Exception catches and unused import" />
    <file path="fmri_first_level_proc/runtime.py" relevance="Contains probe_tool_versions with broad except Exception at L172" />
    <file path="fmri_first_level_proc/exceptions.py" relevance="FmriFirstLevelError hierarchy (6 subclasses)" />
    <file path="tests/test_error_paths.py" relevance="Error propagation tests with CalledProcessError mocks requiring post-T1 updates" />
    <file path="tests/test_roi_extraction.py" relevance="ROI extraction test with CalledProcessError mock requiring post-T1 update" />
  </context_files>
  <topics>
    <topic id="T1" title="run_afni_command exception contract: centralized ToolExecutionError wrapping">
      <summary>The v3.0.0 exception hierarchy requires all AFNI subprocess failures to surface as ToolExecutionError for correct exit-code mapping (exit 4). Currently, run_afni_command (first_level_utils.py L1119-1126) catches subprocess.CalledProcessError, logs it, and re-raises the raw CalledProcessError. This means callers that do not independently wrap the exception (e.g., all of task_conn_first_level.py) leak CalledProcessError to the top level, producing an unhandled-exception crash (exit 1) instead of exit 4.</summary>
      <research>No external research required. The fix is a straightforward application of the project's own exception hierarchy design.</research>
      <approaches>
        <approach id="A1" label="Centralized wrapping in run_afni_command" feasibility="high" risk="low">
          <description>Change run_afni_command's except handler (L1119-1126) to raise ToolExecutionError(msg) from e instead of bare raise. The ToolExecutionError message must include the command name, description parameter, and stderr content so that downstream consumers and log output retain full diagnostic information. This eliminates the entire class of CalledProcessError leakage bugs because every AFNI subprocess call flows through run_afni_command.</description>
          <pros>Single-site fix eliminates the bug class; all three pipelines (task_act, task_conn, rest_conn) automatically benefit; consistent exit-code mapping without per-caller discipline.</pros>
          <cons>Cascade effect on existing CalledProcessError catch sites (see implementation scope below).</cons>
        </approach>
        <approach id="A2" label="Per-caller wrapping" feasibility="high" risk="high">
          <description>Add try/except CalledProcessError wrappers at each call site that currently lacks one (primarily in task_conn_first_level.py).</description>
          <pros>No cascade effect on existing catch sites.</pros>
          <cons>Error-prone (every new call site must remember to wrap); does not prevent future regressions; the CR already identified this as the root cause of the current bug.</cons>
        </approach>
      </approaches>
      <decision status="decided" chosen="A1">Centralized wrapping in run_afni_command. The user approved with the explicit requirement that ToolExecutionError messages preserve full diagnostic detail (which command, why it failed, stderr output).

Implementation scope (cascade from changing run_afni_command's raise type):

Source code, catch-update sites (CalledProcessError to ToolExecutionError, 5 sites with soft-failure semantics that must not break):
- get_3dinfo_properties (first_level_utils.py L1152)
- seed_to_voxel_conn (first_level_utils.py L1754)
- parcellated_conn (first_level_utils.py L1915)
- _get_subbrik_stat_aux / extract_effects 3dAttribute (task_act_first_level.py L328)
- extract_effects 3dcalc existence-check pass (task_act_first_level.py L449)

Source code, redundant-wrapping sites (try/except can be simplified or removed, 5 sites):
- validate_template 3dresample (first_level_utils.py L1261)
- extract_roi_stats (first_level_utils.py L1303)
- run_first_level 3dDeconvolve catch (task_act_first_level.py L268-271)
- extract_effects T-to-Z 3dcalc (task_act_first_level.py L430)
- extract_effects bucket 3dinfo (task_act_first_level.py L383)

Test updates (mocks raising CalledProcessError to simulate AFNI failure should raise ToolExecutionError post-T1):
- test_error_paths.py L45 (task_act mock side_effect)
- test_error_paths.py L75 (task_conn mock side_effect) and L89 (assertion: CalledProcessError to ToolExecutionError)
- test_error_paths.py L104 (rest_conn mock side_effect, for consistency; test still passes either way due to broad except Exception in rest_conn)
- test_roi_extraction.py L89 (extract_roi_stats mock side_effect)

run_first_level.py exception handler (L194-203): must add a catch for subprocess.CalledProcessError (or generic Exception) as a safety net for any CalledProcessError that bypasses run_afni_command (e.g., direct subprocess calls not routed through the wrapper).</decision>
    </topic>
    <topic id="T2" title="Lockfile path resolution for pip-installed packages">
      <summary>_LOCKFILE_PATH in run_first_level.py (L94) uses Path(__file__).parent.parent / "tools.lock.yaml", which resolves to the repository root during development but breaks when pip-installed (the parent of the installed package directory is site-packages, not the repo root). This affects probe_tool_versions() in runtime.py, which reads the lockfile for optional AFNI version pinning.</summary>
      <research>No external research required. The fix distinguishes between two independent AFNI checks: (1) preflight_tool_environments() verifies AFNI binaries exist on PATH (always runs, no lockfile needed), and (2) probe_tool_versions() performs optional version pinning against tools.lock.yaml (gracefully skippable when lockfile is absent).</research>
      <approaches>
        <approach id="A1" label="Graceful skip when lockfile absent" feasibility="high" risk="low">
          <description>Add an os.path.exists check before reading the lockfile. When the lockfile is absent (pip-installed context), emit a low-severity graded_warning ("tools.lock.yaml not found; skipping version pinning") and skip probe_tool_versions(). The AFNI existence check (preflight_tool_environments) is unaffected and always runs.</description>
          <pros>Simple, safe, correct behavior in both development and pip-installed contexts; no new dependencies or packaging complexity.</pros>
          <cons>Version pinning is silently disabled in pip-installed mode (mitigated by the graded_warning).</cons>
        </approach>
        <approach id="A2" label="Bundle lockfile as package_data" feasibility="high" risk="medium">
          <description>Include tools.lock.yaml in pyproject.toml package_data and resolve via importlib.resources.</description>
          <pros>Version pinning works in pip-installed context.</pros>
          <cons>Adds packaging complexity; lockfile values are frozen at install time, which may not match the user's actual AFNI installation.</cons>
        </approach>
        <approach id="A3" label="CLI flag --tools-lock" feasibility="high" risk="low-medium">
          <description>Add a CLI flag (--tools-lock PATH) to run_first_level.py allowing explicit lockfile path specification at invocation time.</description>
          <pros>Fully explicit; works in any installation context.</pros>
          <cons>Adds CLI complexity for a feature most users will never need; version pinning is already optional.</cons>
        </approach>
      </approaches>
      <decision status="decided" chosen="A1">Graceful skip with graded_warning. The user confirmed after clarification that the skip applies only to version pinning (probe_tool_versions), not to the AFNI existence check (preflight_tool_environments), which always runs regardless of lockfile presence.</decision>
    </topic>
    <topic id="T3" title="DOF preflight: account for AFNI polort A polynomial regressors">
      <summary>The DOF preflight checks in task_act_first_level.py (L710-720) and task_conn_first_level.py (L752) count explicit regressors (conditions, motion, censor) but omit AFNI's implicit polynomial baseline regressors. When polort is set to its default value of "A" (automatic), AFNI adds 1 + floor(duration_seconds / 150) polynomial regressors per run. Omitting these from the DOF count produces an overestimate of available degrees of freedom, which could allow an underpowered model to pass the preflight check and then fail inside 3dDeconvolve with a less informative error.</summary>
      <research>No external research required. The polort A formula is documented in AFNI's 3dDeconvolve help and is a well-established convention.</research>
      <approaches>
        <approach id="A1" label="Add polort A estimate to DOF calculation" feasibility="high" risk="low">
          <description>Compute n_poly = 1 + int((n_trs * config.tr) / 150.0) and add it to the regressor count before checking DOF. Apply to both task_act (L710) and task_conn (L752). rest_conn uses polort -1 (no polynomials) when bandpass filtering is active, so its DOF check is already accurate.</description>
          <pros>Correct DOF estimate; early informative failure instead of cryptic 3dDeconvolve crash.</pros>
          <cons>The estimate is conservative (assumes polort A; if user overrides polort to a fixed value, the estimate may not match). This is acceptable because the preflight is a guard, not a contract.</cons>
        </approach>
        <approach id="A2" label="Document as known lower bound" feasibility="high" risk="low">
          <description>Leave the DOF calculation as-is and document in the docstring that the preflight count is a lower bound that does not include AFNI's implicit polynomial regressors.</description>
          <pros>Zero code change; no risk of introducing a regression.</pros>
          <cons>Does not fix the actual problem: an underpowered model can still pass the preflight and crash inside 3dDeconvolve with a less informative error.</cons>
        </approach>
      </approaches>
      <decision status="decided" chosen="A1">Add polort A estimate. Formula: n_poly = 1 + int((n_trs * config.tr) / 150.0). Apply at task_act L710 and task_conn L752.</decision>
    </topic>
    <topic id="T4" title="Mechanical cleanup bundle (7 items)">
      <summary>Seven CR findings (F3, F4, F5, F6, F8, F9, F10) requiring no design decisions, organized as six mechanical implementation items and bundled for /implement as a single batch.</summary>
      <research>No external research required.</research>
      <approaches>
        <approach id="A1" label="Batch all 7 items to /implement" feasibility="high" risk="low">
          <description>
1. Stale docstrings referencing legacy column names (CONDITION/ONSET/DURATION instead of BIDS trial_type/onset/duration): task_act_first_level.py L166, L184; task_conn_first_level.py L148, L173.
2. ValueError to ConfigError in build_hrf_string (first_level_utils.py L481, L491): these are configuration validation errors, not generic value errors.
3. Stale "Raises SystemExit" in compute_matrix_contrast docstring (first_level_utils.py L1656-1657): should reference InputError per v3.0.0.
4. Stale version headers (6 files): first_level_utils.py L8, task_act_first_level.py L10, rest_conn_first_level.py L11, task_conn_first_level.py L12, run_first_level.py L15, checkpoint.py L10 (all say 2.5.0, should say 3.0.0).
5. Unused import time in rest_conn_first_level.py L79.
6. Narrow except Exception to specific exceptions: rest_conn_first_level.py L173 (_generate_run_residual_simultaneous) and L329 (_generate_run_residual_sequenced) should catch ToolExecutionError (post-T1); runtime.py L172 (probe_tool_versions) should catch the specific exception types expected from AFNI version parsing.
          </description>
          <pros>Clears all remaining CR findings in a single /implement pass.</pros>
          <cons>None; all items are mechanical with unambiguous correct outcomes.</cons>
        </approach>
      </approaches>
      <decision status="decided" chosen="A1">Batch all 7 items to /implement.</decision>
    </topic>
  </topics>
  <action_items>
    <item priority="P0" target_mode="implement" description="T1: Change run_afni_command (first_level_utils.py L1119-1126) to raise ToolExecutionError(msg) from e. Update 5 downstream CalledProcessError catch sites to catch ToolExecutionError. Simplify or remove 5 redundant wrapping sites. Update 4 test mock references (test_error_paths.py L45, L75/L89, L104; test_roi_extraction.py L89). Add CalledProcessError/Exception safety net in run_first_level.py exception handler." />
    <item priority="P0" target_mode="implement" description="T2: Add os.path.exists guard before lockfile read in run_first_level.py. Emit low-severity graded_warning when lockfile is absent. No change to preflight_tool_environments." />
    <item priority="P1" target_mode="implement" description="T3: Add polort A polynomial regressor estimate (n_poly = 1 + int((n_trs * config.tr) / 150.0)) to DOF preflight in task_act_first_level.py L710 and task_conn_first_level.py L752." />
    <item priority="P1" target_mode="implement" description="T4: Mechanical bundle (7 CR findings, 6 items) — update 4 stale docstrings (BIDS column names), convert ValueError to ConfigError in build_hrf_string (2 sites), fix stale SystemExit docstring in compute_matrix_contrast, update 6 stale version headers to 3.0.0, remove unused import time, narrow 3 broad except Exception catches." />
    <item priority="P1" target_mode="test" description="Post-implement: run /test run_suite to verify all 635+ tests pass after T1-T4 changes." />
  </action_items>
  <next_steps>Invoke /implement with this brainstorm report to execute T1-T4. T1 and T2 are P0 (correctness bugs); T3 and T4 are P1 (robustness and hygiene). Follow with /test run_suite to verify no regressions.</next_steps>
</brainstorm_report>
