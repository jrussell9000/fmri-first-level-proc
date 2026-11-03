<implement_plan>
  <meta project="fmri_first_level_proc" mode="implement" submodule="plan" timestamp="2026-08-13T13:19:30Z" />
  <input_reports>
    <report path="fmri_first_level_proc_brainstorm_20260813_125601.md" mode="brainstorm" key_items="4" />
  </input_reports>
  <changes>
    <change id="C1" priority="P0" source_item="T1 + T4 (partial)">
      <file path="fmri_first_level_proc/first_level_utils.py" action="modify" />
      <description>Centralize ToolExecutionError wrapping in run_afni_command and update all CalledProcessError catch sites within this file. Also apply T4 mechanical fixes (ValueError to ConfigError, stale docstring, version header).</description>
      <spec>
1. run_afni_command (L1078-1126):
   - L1098-1101: Change docstring "Raises" section from "subprocess.CalledProcessError" to "ToolExecutionError" with description "If the command exits with non-zero status. Message includes the command, description, and stderr."
   - L1119-1126: Replace `except subprocess.CalledProcessError as e:` block. Keep the existing msg construction (L1120-1123) and logger.error(msg) call (L1124-1125). Change `raise` (L1126) to `raise ToolExecutionError(msg) from e`.

2. Catch-update sites (CalledProcessError to ToolExecutionError, preserve soft-failure semantics):
   - L1152: `except subprocess.CalledProcessError:` to `except ToolExecutionError:`
   - L1754: `except subprocess.CalledProcessError:` to `except ToolExecutionError:`
   - L1915: `except subprocess.CalledProcessError:` to `except ToolExecutionError:`

3. Redundant-wrapping sites (run_afni_command now raises ToolExecutionError directly; these try/except blocks can be simplified to let the ToolExecutionError propagate):
   - L1254-1262 (validate_template): Remove the try/except block. Keep the run_afni_command call at L1255-1260 unguarded. The ToolExecutionError from run_afni_command already contains the command, description, and stderr. Delete the `except subprocess.CalledProcessError as e: raise ToolExecutionError(...)` at L1261-1262.
   - L1294-1304 (extract_roi_stats): Remove the try/except block. Keep the run_afni_command call at L1295-1302 unguarded. Delete the `except subprocess.CalledProcessError as e: raise ToolExecutionError(...)` at L1303-1304.

4. T4 mechanical fixes in this file:
   - L8: Change "Version: 2.5.0" to "Version: 3.0.0"
   - L481: Change `raise ValueError("custom_hrf is required when hrf_model='custom'")` to `raise ConfigError("custom_hrf is required when hrf_model='custom'")`
   - L491: Change `raise ValueError(f"Unknown hrf_model: {hrf_model}")` to `raise ConfigError(f"Unknown hrf_model: {hrf_model}")`
   - L1655-1656: Change docstring from "SystemExit" to "InputError" (the Raises section of compute_matrix_contrast)
      </spec>
      <dependencies>none</dependencies>
      <risk>low - all changes are mechanical substitutions with clear before/after states</risk>
      <rollback>git checkout fmri_first_level_proc/first_level_utils.py</rollback>
    </change>

    <change id="C2" priority="P0" source_item="T1 cascade + T3 + T4 (partial)">
      <file path="fmri_first_level_proc/task_act_first_level.py" action="modify" />
      <description>Update CalledProcessError catch sites (cascade from C1), add polort A to DOF preflight, fix stale docstrings and version header.</description>
      <spec>
1. Catch-update sites (CalledProcessError to ToolExecutionError):
   - L328: `except subprocess.CalledProcessError:` to `except ToolExecutionError:`
   - L449: `except subprocess.CalledProcessError:` to `except ToolExecutionError:`

2. Redundant-wrapping sites (remove try/except, let ToolExecutionError propagate):
   - L266-271 (run_first_level 3dDeconvolve): Remove the try/except block wrapping run_afni_command at L266-271. Keep the run_afni_command call at L267 unguarded. Delete the `except subprocess.CalledProcessError as e: raise ToolExecutionError(...)` at L268-271.
   - L376-386 (extract_effects 3dinfo): Remove the try/except block. Keep the run_afni_command call at L377-382 unguarded. Delete `except subprocess.CalledProcessError: raise ToolExecutionError(...)` at L383-386.
   - L428-433 (extract_effects T-to-Z 3dcalc): Remove the try/except block. Keep the run_afni_command call at L429 unguarded. Delete `except subprocess.CalledProcessError as e: raise ToolExecutionError(...)` at L430-433.

3. DOF preflight polort A (T3): After all tissue regressor counting (L711-L719) and BEFORE the compute_dof call at L720, insert:
   ```python
   censor_data_preflight = np.loadtxt(config.censor_path)
   n_trs = len(censor_data_preflight)
   n_poly = 1 + int((n_trs * config.tr) / 150.0)
   n_regressors += n_poly
   ```
   ResolvedConfig does not carry an n_trs attribute; total TRs must be derived from the censor file length. np is already imported in this file. The variable name `censor_data_preflight` avoids shadowing the `censor_data` variable at L730 (QC section).

4. T4 mechanical fixes:
   - L10: Change "Version: 2.5.0" to "Version: 3.0.0"
   - L166: Change "Sorted timing data with CONDITION, ONSET, DURATION columns." to "Sorted timing data with trial_type, onset, duration columns (BIDS naming)."
   - L182: Change "Sorted timing data with CONDITION, ONSET, DURATION columns." to "Sorted timing data with trial_type, onset, duration columns (BIDS naming)."
      </spec>
      <dependencies>C1 (logically; operationally independent since different file)</dependencies>
      <risk>low - mechanical substitutions plus one 2-line insert for polort A</risk>
      <rollback>git checkout fmri_first_level_proc/task_act_first_level.py</rollback>
    </change>

    <change id="C3" priority="P1" source_item="T3 + T4 (partial)">
      <file path="fmri_first_level_proc/task_conn_first_level.py" action="modify" />
      <description>Add polort A to DOF preflight, fix stale docstrings and version header.</description>
      <spec>
1. DOF preflight polort A (T3): After all tissue regressor counting (L753-L761) and before L762 (`dof = compute_dof(...)`), insert:
   ```python
   censor_data_preflight = np.loadtxt(config.censor_path)
   n_trs = len(censor_data_preflight)
   n_poly = 1 + int((n_trs * config.tr) / 150.0)
   n_regressors += n_poly
   ```
   Same pattern as C2: ResolvedConfig has no n_trs attribute; derive from censor file. np is already imported.

2. T4 mechanical fixes:
   - L12: Change "Version: 2.5.0" to "Version: 3.0.0"
   - L149: Change "Sorted timing data with CONDITION, ONSET, DURATION columns." to "Sorted timing data with trial_type, onset, duration columns (BIDS naming)."
   - L171: Change "Sorted timing data with CONDITION, ONSET, DURATION columns." to "Sorted timing data with trial_type, onset, duration columns (BIDS naming)."
      </spec>
      <dependencies>none</dependencies>
      <risk>low - same pattern as C2 polort A insertion</risk>
      <rollback>git checkout fmri_first_level_proc/task_conn_first_level.py</rollback>
    </change>

    <change id="C4" priority="P1" source_item="T4 (partial)">
      <file path="fmri_first_level_proc/rest_conn_first_level.py" action="modify" />
      <description>Remove unused import, update version header, narrow broad except Exception catches to specific exception types.</description>
      <spec>
1. L79: Delete `import time` line entirely.
2. L11: Change "Version: 2.5.0" to "Version: 3.0.0"
3. L173 (_generate_run_residual_simultaneous): Change `except Exception as e:` to `except ToolExecutionError as e:`. The only call inside the try block is run_afni_command, which post-C1 raises ToolExecutionError exclusively.
4. L329 (_generate_run_residual_sequenced): Change `except Exception as e:` to `except (ToolExecutionError, OSError) as e:`. The try block contains multiple run_afni_command calls (ToolExecutionError), censor_interpolate_1d_afni and bandpass_filter_1d_afni (which internally call run_afni_command, so ToolExecutionError), and filesystem operations like os.makedirs (OSError).
      </spec>
      <dependencies>C1 (logically; operationally independent)</dependencies>
      <risk>low - narrowing exceptions is safe because the enclosing gen_residual_ts already handles per-run None returns and raises ToolExecutionError when all runs fail</risk>
      <rollback>git checkout fmri_first_level_proc/rest_conn_first_level.py</rollback>
    </change>

    <change id="C5" priority="P0" source_item="T1 safety net + T2 + T4 (partial)">
      <file path="fmri_first_level_proc/run_first_level.py" action="modify" />
      <description>Add lockfile existence guard (T2), add subprocess.CalledProcessError and generic Exception safety net to the exception handler chain (T1), update version header (T4).</description>
      <spec>
1. L15: Change "Version: 2.5.0" to "Version: 3.0.0"

2. T2 lockfile guard: Replace L138 (`probe_tool_versions(str(_LOCKFILE_PATH), logger=logger)`) with:
   ```python
   if _LOCKFILE_PATH.exists():
       probe_tool_versions(str(_LOCKFILE_PATH), logger=logger)
   else:
       graded_warning(
           logger, 'low', 'LOCKFILE_ABSENT',
           f"tools.lock.yaml not found at {_LOCKFILE_PATH}; skipping AFNI version pinning.",
           user_facing=True,
       )
   ```
   The preflight_tool_environments() call at L137 is unchanged (always runs).

3. T1 safety net: After the GuardError handler at L202-203, add two additional except clauses:
   ```python
   except subprocess.CalledProcessError as e:
       logger.error("Unexpected subprocess failure: %s", e)
       sys.exit(4)
   except Exception as e:
       logger.critical("Unexpected error: %s", e)
       sys.exit(1)
   ```
   This requires adding `import subprocess` at the top of the file (after `import sys` at L65). The CalledProcessError catch (exit 4) handles any direct subprocess calls not routed through run_afni_command. The generic Exception catch (exit 1) is the final safety net.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - additive changes only</risk>
      <rollback>git checkout fmri_first_level_proc/run_first_level.py</rollback>
    </change>

    <change id="C6" priority="P1" source_item="T4 (partial)">
      <file path="fmri_first_level_proc/runtime.py" action="modify" />
      <description>Narrow broad except Exception in probe_tool_versions to specific exception types.</description>
      <spec>
L172: Change `except Exception as exc:` to `except (subprocess.SubprocessError, OSError) as exc:`. The try block at L162-171 calls subprocess.run() with timeout=30, which can raise:
- subprocess.TimeoutExpired (subclass of SubprocessError)
- FileNotFoundError (subclass of OSError, if afni binary missing)
- PermissionError (subclass of OSError, if afni binary not executable)
The SubprocessError + OSError union covers all realistic failure modes without catching programming bugs (TypeError, AttributeError).
      </spec>
      <dependencies>none</dependencies>
      <risk>low - narrowing a catch in a non-critical version-checking function</risk>
      <rollback>git checkout fmri_first_level_proc/runtime.py</rollback>
    </change>

    <change id="C7" priority="P1" source_item="T4 (partial)">
      <file path="fmri_first_level_proc/checkpoint.py" action="modify" />
      <description>Update stale version header.</description>
      <spec>
L10: Change "Version: 2.5.0" to "Version: 3.0.0"
      </spec>
      <dependencies>none</dependencies>
      <risk>low - single-line text change</risk>
      <rollback>git checkout fmri_first_level_proc/checkpoint.py</rollback>
    </change>

    <change id="C8" priority="P0" source_item="T1 test cascade">
      <file path="tests/test_error_paths.py" action="modify" />
      <file path="tests/test_roi_extraction.py" action="modify" />
      <description>Update test mocks to raise ToolExecutionError instead of CalledProcessError (reflecting the post-C1 contract of run_afni_command), and update assertions accordingly.</description>
      <spec>
test_error_paths.py:
1. L45: Change `raise subprocess.CalledProcessError(1, command)` to `raise ToolExecutionError(f"AFNI command failed: {' '.join(command)}")`. This simulates run_afni_command's post-C1 behavior.
2. L69: Update docstring from "should raise CalledProcessError" to "should raise ToolExecutionError".
3. L75: Change `raise subprocess.CalledProcessError(1, command)` to `raise ToolExecutionError(f"AFNI command failed: {' '.join(command)}")`.
4. L89: Change `with pytest.raises(subprocess.CalledProcessError):` to `with pytest.raises(ToolExecutionError):`.
5. L104: Change `raise subprocess.CalledProcessError(1, command)` to `raise ToolExecutionError(f"AFNI command failed: {' '.join(command)}")`.

test_roi_extraction.py:
1. L89: Change `raise subprocess.CalledProcessError(1, "3dROIstats")` to `raise ToolExecutionError("AFNI command failed: 3dROIstats")`. Also add import: `from fmri_first_level_proc.exceptions import ToolExecutionError` at the top of the file (check existing imports first to avoid duplicates).
      </spec>
      <dependencies>C1 (logically; operationally independent)</dependencies>
      <risk>low - updating test expectations to match the new contract</risk>
      <rollback>git checkout tests/test_error_paths.py tests/test_roi_extraction.py</rollback>
    </change>
  </changes>
  <execution_order>C1, C2, C3, C4, C5, C6, C7, C8 (all independent at the file level; can be dispatched in parallel)</execution_order>
</implement_plan>
