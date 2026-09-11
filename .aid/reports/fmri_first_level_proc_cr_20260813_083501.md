<cr_report>
  <meta project="fmri_first_level_proc" mode="cr" timestamp="2026-08-13T12:35:01Z" />
  <scope>
    Full v3.0.0 diff review (from scratch). 12 Python source files read in their entirety:
    - fmri_first_level_proc/exceptions.py (30 lines, new)
    - fmri_first_level_proc/runtime.py (190 lines, new)
    - fmri_first_level_proc/bids.py (336 lines, new)
    - fmri_first_level_proc/checkpoint.py (338 lines, new)
    - fmri_first_level_proc/run_first_level.py (213 lines, modified)
    - fmri_first_level_proc/__init__.py (26 lines, modified)
    - fmri_first_level_proc/first_level_config.py (858 lines, modified)
    - fmri_first_level_proc/first_level_utils.py (1935 lines, modified)
    - fmri_first_level_proc/task_act_first_level.py (789 lines, modified)
    - fmri_first_level_proc/task_conn_first_level.py (846 lines, modified)
    - fmri_first_level_proc/rest_conn_first_level.py (789 lines, modified)
    - pyproject.toml (42 lines, modified)

    Review dimensions: assumptions, validity, robustness, generalizability, reproducibility, inferential_calibration, scientific_rigor. All seven dimensions examined across all files.
  </scope>
  <research_conducted>No research agent dispatch required. Findings are grounded in code-level analysis of the v3.0.0 exception hierarchy migration, config pipeline refactor, and BIDS column naming propagation. The underlying statistical methods (3dDeconvolve GLM, 3dLSS beta series, 3dTproject nuisance regression, 3dNetCorr connectivity, T-to-Z conversion via fitt_t2z, bandpass filtering, NTRP interpolation) are unchanged from v2.5.0 and were validated in prior reviews. No new methodological claims introduced in v3.0.0 require literature verification.</research_conducted>
  <findings>
    <finding id="F1" severity="major" category="robustness">
      <location file="fmri_first_level_proc/task_conn_first_level.py" lines="275,327,363,552" />
      <description>Incomplete CalledProcessError wrapping in the v3.0.0 exception hierarchy migration. task_conn_first_level.py has four sites where run_afni_command() is called without wrapping subprocess.CalledProcessError in ToolExecutionError: gen_design_matrix (L275, 3dDeconvolve), gen_beta_series (L327, 3dLSS; L363, 3dcalc), and gen_conn_contrasts (L552, 3dcalc). By contrast, task_act_first_level.py correctly wraps CalledProcessError at L268-271, and rest_conn_first_level.py handles it via broad Exception catch with per-run None return + aggregate ToolExecutionError.</description>
      <evidence>run_first_level.py L194-203 maps ToolExecutionError to exit code 4 (tool errors). There is no handler for subprocess.CalledProcessError. An unwrapped CalledProcessError from task_conn produces Python's default unhandled-exception exit code 1, which the v3.0.0 exit code contract reserves for GuardError ("pipeline invariant violation; indicates a bug"). The test suite explicitly documents this inconsistency: test_error_paths.py L89 asserts `pytest.raises(subprocess.CalledProcessError)` for task_conn, while L65 asserts `pytest.raises(ToolExecutionError)` for task_act.</evidence>
      <literature>N/A (code architecture finding, not methodological).</literature>
      <impact>When 3dDeconvolve, 3dLSS, or 3dcalc fails within the task_conn pipeline, the CLI exit code is 1 (GuardError semantics) instead of the intended 4 (tool error semantics). Upstream orchestrators (e.g., fmri-proc-orchestrator) that use exit codes for failure classification and retry logic will misclassify AFNI tool failures as internal pipeline bugs, potentially triggering incorrect recovery actions. The misclassification is silent (no wrong results are produced), but it violates the exit code contract documented in run_first_level.py L24-31.</impact>
      <recommendation>Wrap CalledProcessError in ToolExecutionError at all four sites in task_conn_first_level.py, following the pattern at task_act_first_level.py L268-271. Update test_error_paths.py L89 to assert ToolExecutionError instead of CalledProcessError. This is a straightforward mechanical change at each site:
        ```python
        try:
            run_afni_command(cmd, ...)
        except subprocess.CalledProcessError as e:
            raise ToolExecutionError(f"description: {e}") from e
        ```
      </recommendation>
    </finding>

    <finding id="F2" severity="major" category="robustness">
      <location file="fmri_first_level_proc/run_first_level.py" lines="94" />
      <description>_LOCKFILE_PATH resolves relative to the Python source file location via Path(__file__).parent.parent / "tools.lock.yaml". This resolves to the repository root during development (package directory's parent is the repo root), but when the package is pip-installed from GitHub, __file__ points into site-packages/ and .parent.parent resolves to the site-packages directory itself, where tools.lock.yaml does not exist.</description>
      <evidence>L94: `_LOCKFILE_PATH: Path = Path(__file__).parent.parent / "tools.lock.yaml"`. The package is pip-installable (`pip install git+https://github.com/tjkeding/fmri-first-level-proc.git`). After pip install, __file__ is e.g. `/path/to/site-packages/fmri_first_level_proc/run_first_level.py`, making .parent.parent = `/path/to/site-packages/`, which does not contain tools.lock.yaml. The probe_tool_versions call at L138 receives this nonexistent path. runtime.py's probe_tool_versions opens the file; if the file is absent, it will raise FileNotFoundError, which is unhandled by the exit code mapping (no handler for FileNotFoundError or OSError).</evidence>
      <literature>N/A.</literature>
      <impact>First-time users who pip-install the package and run the CLI will get an unhandled FileNotFoundError at startup, producing a Python traceback and exit code 1. The lockfile mechanism is new in v3.0.0 and has not yet been exercised in the pip-installed deployment path.</impact>
      <recommendation>Two options: (a) make probe_tool_versions skip gracefully when the lockfile path does not exist (emit a graded_warning and continue without version pinning), or (b) make the lockfile path configurable via CLI flag (--tools-lock) with a default that checks the repo root first and falls back to skipping. Option (a) is lower-risk for v3.0.0 release and maintains the principle that the lockfile is optional infrastructure.</recommendation>
    </finding>

    <finding id="F3" severity="minor" category="reproducibility">
      <location file="fmri_first_level_proc/task_act_first_level.py" lines="166,184" />
      <description>Stale docstrings in task_act_first_level.py's read_stim_data (L166: "Sorted timing data with CONDITION, ONSET, DURATION columns") and write_stim_onset_files (L184: same). The functions now consume DataFrames with BIDS column names (trial_type, onset, duration), not the legacy uppercase names. The v3.0.0 BIDS column rename was applied to the code but these docstrings were not updated.</description>
      <evidence>read_and_validate_stim_data() (first_level_utils.py L497-594) returns DataFrames with lowercase BIDS column names. All downstream access in task_act uses 'trial_type', 'onset', 'duration' (e.g., L241, L346, L584). The docstrings at L166 and L184 still reference the legacy names.</evidence>
      <literature>N/A.</literature>
      <impact>Maintainers or contributors who read the docstrings and construct DataFrames with uppercase column names (as happened in the test suite, causing 37 failures fixed earlier this session) will encounter KeyError at runtime. The discrepancy between documented and actual column names is the exact class of error that caused the v3.0.0 test failures.</impact>
      <recommendation>Update docstrings in task_act read_stim_data (L166) and write_stim_onset_files (L184) to reference "trial_type, onset, duration" (BIDS names). Same update needed in task_conn_first_level.py read_stim_data (L148) and write_stim_onset_files (L173).</recommendation>
    </finding>

    <finding id="F4" severity="minor" category="validity">
      <location file="fmri_first_level_proc/first_level_utils.py" lines="481,491" />
      <description>build_hrf_string() raises ValueError for two error conditions: missing custom_hrf (L481) and unknown hrf_model (L491). These are configuration validation errors that should raise ConfigError per the v3.0.0 exception hierarchy. ValueError is not caught by run_first_level.py's exit code mapping (L194-203), so these conditions produce an unhandled exception and exit code 1 (GuardError semantics) instead of exit code 2 (ConfigError semantics).</description>
      <evidence>L481: `raise ValueError("custom_hrf is required when hrf_model='custom'")`. L491: `raise ValueError(f"Unknown hrf_model: {hrf_model}")`. Neither ValueError is in the except chain at run_first_level.py L194-203. In practice, validate_config catches most invalid HRF models before build_hrf_string is reached, but a direct programmatic caller could hit these paths.</evidence>
      <literature>N/A.</literature>
      <impact>Low in practice (config validation catches most cases upstream), but violates the principle that all error conditions in the package should map to the FmriFirstLevelError hierarchy for clean exit code classification.</impact>
      <recommendation>Replace ValueError with ConfigError at L481 and L491. Import ConfigError if not already imported in the relevant scope.</recommendation>
    </finding>

    <finding id="F5" severity="minor" category="reproducibility">
      <location file="fmri_first_level_proc/first_level_utils.py" lines="1656-1657" />
      <description>compute_matrix_contrast() docstring states "Raises: SystemExit" but the function now raises InputError (L1663, L1670-1672). This is a stale docstring from the pre-v3.0.0 sys.exit migration.</description>
      <evidence>L1663: `raise InputError(...)`. L1670-1672: `raise InputError(...)`. The "SystemExit" reference in the docstring is a leftover from the 123-site sys.exit migration.</evidence>
      <literature>N/A.</literature>
      <impact>Misleading for API consumers who read the docstring and handle SystemExit instead of InputError.</impact>
      <recommendation>Update the docstring Raises section to reference InputError.</recommendation>
    </finding>

    <finding id="F6" severity="minor" category="robustness">
      <location file="fmri_first_level_proc/runtime.py" lines="172" />
      <description>probe_tool_versions() uses a broad `except Exception` when reading the tools.lock.yaml file and running version checks. This catches all exceptions (including KeyboardInterrupt on some Python versions, AttributeError from malformed config, etc.) and treats them uniformly as non-critical warnings.</description>
      <evidence>runtime.py L172: broad except clause catches everything. The intent (version checking is non-critical and should not abort the pipeline) is reasonable, but the breadth of the catch masks programming errors and unexpected states.</evidence>
      <literature>N/A.</literature>
      <impact>Programming errors in the version-checking logic (e.g., typos in dictionary keys, incorrect regex patterns) would be silently swallowed rather than surfacing as development-time failures. Low production impact since the feature is new and lightly exercised.</impact>
      <recommendation>Narrow the except clause to catch (FileNotFoundError, yaml.YAMLError, subprocess.CalledProcessError, KeyError, ValueError) explicitly, allowing programming errors (AttributeError, TypeError) to propagate.</recommendation>
    </finding>

    <finding id="F7" severity="minor" category="inferential_calibration">
      <location file="fmri_first_level_proc/task_act_first_level.py" lines="710-720" />
      <description>The preflight DOF check for task_act and task_conn does not count the polynomial detrending regressors added by 3dDeconvolve's `-polort A` (automatic polynomial order). 3dDeconvolve with `-polort A` adds `1 + floor(duration_seconds / 150)` polynomial basis functions (Legendre polynomials for constant, linear, and potentially quadratic/cubic trends). These regressors consume DOF but are not counted in the preflight estimate. The same gap exists in task_conn_first_level.py at L752.</description>
      <evidence>task_act L710: `n_regressors = use_cols + len(config.cond_labels)`. build_decon_base_command uses `-polort A` (L1036). For a typical single-run fMRI acquisition (TR=0.8s, 400 TRs, 320s duration): polort A adds floor(1 + 320/150) = 3 polynomial regressors. rest_conn correctly uses `-polort -1` (no polynomials), so its DOF check is accurate.</evidence>
      <literature>AFNI documentation for 3dDeconvolve `-polort`: "If you use '-polort A', the program will choose the order based on the duration of the input data. The default is: 1 + int(duration/150) where duration = number_of_TRs * TR_length."</literature>
      <impact>The preflight DOF check may pass when the actual model has DOF closer to exhaustion than reported. For typical datasets (200+ uncensored TRs), the 2-4 missing polynomial regressors are negligible. For short runs or high-censoring scenarios near the DOF boundary, the preflight check could pass when AFNI itself will fail, producing a confusing error message from AFNI rather than the pipeline's structured ModelError. AFNI's own internal DOF check is the actual safety net; this is a defense-in-depth gap.</impact>
      <recommendation>Add the polort A regressor estimate to the DOF calculation: `n_regressors += 1 + int((n_uncensored_trs * config.tr) / 150.0)`. Requires reading the censor file before computing n_regressors (currently done in the same scope). Alternatively, document the preflight check as a conservative lower bound (it currently undercounts, making it optimistic rather than conservative). Note: the task_conn comment at L751 already says "conservative lower bound" but this refers to the per-trial vs. per-condition counting, not the missing polort regressors.</recommendation>
    </finding>

    <finding id="F8" severity="minor" category="robustness">
      <location file="fmri_first_level_proc/rest_conn_first_level.py" lines="173-175" />
      <description>_generate_run_residual_simultaneous() catches broad `Exception` (L173) and returns None, which causes gen_residual_ts to skip the failed run and continue with remaining runs. While the design intent (per-run failure isolation) is sound, the broad catch discards the exception type, making it impossible for the caller to distinguish AFNI tool failures (CalledProcessError) from I/O errors (OSError), data corruption (ValueError), or programming bugs (TypeError, AttributeError).</description>
      <evidence>L173: `except Exception as e:`. The same pattern appears in _generate_run_residual_sequenced at L329. The error message is logged (L174), but the exception type is not preserved in the return value or in any structured record. gen_residual_ts only knows "this run failed" not "why."</evidence>
      <literature>N/A.</literature>
      <impact>Debugging pipeline failures in multi-run resting-state processing requires reading the log output to determine failure cause. QC summary data does not record per-run failure reasons. For the upstream orchestrator, all per-run failures look identical regardless of whether the cause is an AFNI installation issue (actionable at the infrastructure level) or a data-specific problem (actionable at the subject level).</impact>
      <recommendation>Narrow the catch to (subprocess.CalledProcessError, OSError) and let programming errors (TypeError, AttributeError, etc.) propagate. Alternatively, preserve the exception type in the QC data or graded_warning for the skipped run.</recommendation>
    </finding>

    <finding id="F9" severity="minor" category="reproducibility">
      <location file="fmri_first_level_proc/first_level_utils.py" lines="8" />
      <description>Stale "Version: 2.5.0" header in file comments across all pipeline files. The package version in __init__.py and pyproject.toml is 3.0.0, but the file-level version headers were not updated during the refactor. Affected files: first_level_utils.py (L8), task_act_first_level.py (L10), task_conn_first_level.py (L13), rest_conn_first_level.py (L13), run_first_level.py (L15), checkpoint.py (L10).</description>
      <evidence>__init__.py L4: `__version__ = "3.0.0"`. pyproject.toml: `version = "3.0.0"`. All six pipeline files: "Version: 2.5.0".</evidence>
      <literature>N/A.</literature>
      <impact>Users inspecting individual source files see a version number that does not match the package version. This creates ambiguity about whether a given file has been updated for v3.0.0 or is still at v2.5.0, especially when files are viewed outside of git context (e.g., in site-packages after pip install).</impact>
      <recommendation>Update all file-level "Version:" headers to 3.0.0. Consider whether per-file version headers add value alongside the authoritative __init__.py __version__; if not, removing them eliminates future synchronization burden.</recommendation>
    </finding>

    <finding id="F10" severity="note" category="reproducibility">
      <location file="fmri_first_level_proc/rest_conn_first_level.py" lines="79" />
      <description>Unused `import time` at L79. The `time` module is not referenced anywhere in rest_conn_first_level.py. This import was likely present for timing/profiling during development.</description>
      <evidence>grep for `time.` in rest_conn_first_level.py returns only the import line. run_first_level.py correctly uses `import time` for elapsed-time logging.</evidence>
      <literature>N/A.</literature>
      <impact>No functional impact. Minor code cleanliness issue.</impact>
      <recommendation>Remove `import time` from rest_conn_first_level.py L79.</recommendation>
    </finding>
  </findings>
  <summary>
    <critical_count>0</critical_count>
    <major_count>2</major_count>
    <minor_count>7</minor_count>
    <overall_assessment>conditionally_defensible</overall_assessment>
    <assessment_rationale>The v3.0.0 refactoring is architecturally sound: the exception hierarchy, config pipeline, and BIDS column naming are well-designed and consistently applied across the majority of the codebase. The two major findings (F1: incomplete CalledProcessError wrapping in task_conn; F2: lockfile path resolution for pip-installed packages) are both deployment-affecting but mechanically fixable. Neither produces incorrect statistical results. The underlying fMRI analysis methods (3dDeconvolve GLM, 3dLSS beta series, 3dTproject nuisance regression, simultaneous and sequenced bandpass, 3dNetCorr connectivity, Fisher Z-transform, T-to-Z conversion, NTRP interpolation) are unchanged from v2.5.0 and remain methodologically defensible. The "conditionally_defensible" assessment reflects the two major findings that should be addressed before tagging v3.0.0; the codebase is not "needs_revision" because the statistical pipeline itself is correct and the findings are confined to error-handling and deployment infrastructure.</assessment_rationale>
  </summary>
  <action_items>
    <item priority="P1" target_mode="implement" finding_ref="F1" description="Wrap subprocess.CalledProcessError in ToolExecutionError at all four unwrapped call sites in task_conn_first_level.py (gen_design_matrix L275, gen_beta_series L327 and L363, gen_conn_contrasts L552). Update test_error_paths.py L89 to assert ToolExecutionError." />
    <item priority="P1" target_mode="implement" finding_ref="F2" description="Make probe_tool_versions skip gracefully when the lockfile path does not exist (emit graded_warning, continue without version pinning). This prevents an unhandled FileNotFoundError when the package is pip-installed." />
    <item priority="P2" target_mode="implement" finding_ref="F3" description="Update stale docstrings in task_act read_stim_data/write_stim_onset_files and task_conn read_stim_data/write_stim_onset_files to reference BIDS column names (trial_type, onset, duration)." />
    <item priority="P2" target_mode="implement" finding_ref="F4" description="Replace ValueError with ConfigError in build_hrf_string (first_level_utils.py L481, L491)." />
    <item priority="P2" target_mode="implement" finding_ref="F5" description="Update compute_matrix_contrast docstring Raises section from SystemExit to InputError." />
    <item priority="P2" target_mode="implement" finding_ref="F6" description="Narrow runtime.py probe_tool_versions except clause from Exception to (FileNotFoundError, yaml.YAMLError, subprocess.CalledProcessError, KeyError, ValueError)." />
    <item priority="P2" target_mode="implement" finding_ref="F7" description="Add polort A regressor estimate to the task_act and task_conn preflight DOF calculations. Formula: n_regressors += 1 + int((n_uncensored_trs * config.tr) / 150.0)." />
    <item priority="P2" target_mode="implement" finding_ref="F8" description="Narrow rest_conn _generate_run_residual_simultaneous and _generate_run_residual_sequenced except clauses from Exception to (subprocess.CalledProcessError, OSError)." />
    <item priority="P2" target_mode="implement" finding_ref="F9" description="Update all file-level Version: headers from 2.5.0 to 3.0.0 (6 files)." />
    <item priority="P2" target_mode="implement" finding_ref="F10" description="Remove unused import time from rest_conn_first_level.py L79." />
  </action_items>
</cr_report>
