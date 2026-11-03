<implement_plan>
  <meta project="fmri-first-level-proc" mode="implement" submodule="plan" timestamp="2026-11-02T14:26:25Z" />
  <input_reports>
    <report path="fmri-first-level-proc_boundary_audit_20261102_133114.md" mode="orchestrator_audit" key_items="27" />
  </input_reports>

  <locked_decisions>
    <decision id="L1" source="A7">rest_conn uses the first column of every CSF/WM/GS file, through a per-run prepared single-column copy, matching task_act/task_conn and INPUT_SPECIFICATION.</decision>
    <decision id="L2" source="A3">BIDS discovery matches subject, task and desc entities exactly. BIDS discovery mode is active when derivatives_dirs (global or block) AND subject are set; in that mode task is required (ConfigError when absent). Blocks with explicit paths and no subject are unaffected.</decision>
    <decision id="L3" source="C1">task_conn connectivity.contrasts with calc_conn null raise ConfigError at validation.</decision>
    <decision id="L4" source="D1">--dry-run validates the config and the inputs (run sets, header TR, grids, motion/tissue rows, columns and finiteness, events parsing, onset validation, duplicate trials, template properties), read-only; nothing is written to out_dir beyond out_dir creation during validation (existing behavior).</decision>
    <decision id="L5" source="D3">Per-block isolation in the CLI. Each analyses entry is validated, resolved and run independently; a failing block stops at its first error and the remaining blocks proceed. Global-level errors (unreadable YAML, top-level schema, global keys, global.tr, global.template_path) stop the whole run. Cross-block conflicts fail every involved block.</decision>
    <decision id="L6" source="D3 / harmonization">Block outcome is recorded inside the existing {pre}_qc_summary.json through one additive key, run_status = {status: "success"|"warning"|"failed", error: null | {type, message, exit_code, step}}. Success: normal summary plus run_status. Failure after out_dir and out_file_pre are valid: a summary containing only analysis_type, run_status and (when known) provenance; no partial metric keys. No new file types. Python API unchanged: run() raises the same exceptions; FirstLevelResult unchanged; load_and_validate keeps raise-on-first-error semantics. Read-only check of fmri-proc-orchestrator, fmri-preproc and fmri-bids-recon found no closed-schema QC consumer (fmri-proc-orchestrator reads qc_summary with dict.get).</decision>
    <decision id="L7" source="D3">CLI exit code: the exit code of the first failing block in config order; with no failing block, 3 when any high-severity warning was raised, otherwise 0. Applies to --dry-run as well.</decision>
    <decision id="L8" source="observed during planning">In BIDS discovery mode, subject, session and task must be strings (ConfigError suggesting quoting, e.g. subject: "01").</decision>
  </locked_decisions>

  <assumptions>
    <assumption>Required keys whose value is null are treated as missing (ConfigError "Missing required key").</assumption>
    <assumption>Optional boolean keys accept true, false or null (null = documented default); any other value is a ConfigError.</assumption>
    <assumption>File-name-safe pattern for every prefix and condition label: ^[A-Za-z0-9][A-Za-z0-9._-]*$ (FILENAME_TOKEN_RE). This admits BIDS-style prefixes such as sub-01_ses-A_task-nback and all labels used in example_config.yaml.</assumption>
    <assumption>Any exact duplicate (run, condition, onset) among valid events rows is an InputError, whether or not the condition is modeled.</assumption>
    <assumption>Unresolved required inputs raise ConfigError when BIDS discovery mode was not active and InputError when it was (both exit 2).</assumption>
    <assumption>A task_conn connectivity contrast skipped because a referenced condition produced no output emits CONTRAST_DROPPED (existing medium code) rather than a new warning code.</assumption>
    <assumption>B5 (task_conn rerun GuardError) was not reproduced; the fix (expected set derived from the connectivity stage's listed outputs) is correct independently of reproduction and is covered by /test.</assumption>
  </assumptions>

  <changes>

    <change id="C1" priority="P1" source_item="D3, L7">
      <file path="fmri_first_level_proc/exceptions.py" action="modify" />
      <description>Centralize the exception-to-exit-code mapping so the CLI and run_status use one table.</description>
      <spec>Add module-level function exit_code(exc) -> int: ConfigError, InputError -> 2; ModelError -> 5; ToolUnavailableError, ToolVersionError, ToolExecutionError -> 4; subprocess.CalledProcessError -> 4; GuardError -> 1; any other Exception -> 1. Import subprocess locally inside the function. Docstring lists the table.</spec>
      <dependencies>none</dependencies>
      <risk>low - pure function.</risk>
      <rollback>Remove the function.</rollback>
    </change>

    <change id="C2" priority="P0" source_item="A5, A6, A9, B3, B4, C3, C6, C7, C8, cosmetic">
      <file path="fmri_first_level_proc/first_level_config.py" action="modify" />
      <description>Add structural and value-type validation so malformed configs raise ConfigError (exit 2) instead of escaping as TypeError/AttributeError or being silently accepted.</description>
      <spec>
1. Constants: FILENAME_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$"); BOOL_FIELDS per type, covering censor_prev_tr, remove_previous, scale_to_psc, include_motion_derivs (task), use_tissue_derivs, use_sequenced_bandpass and keep_run_res_dtseries (rest), and the nested booleans extraction.extract_resids, extraction.extract_raw_ptseries, extraction.extract_pbseries, extraction.extract_ptseries, connectivity.pcorr, connectivity.fishZ; global force_diff_atlas.
2. load_config: after safe_load, raise ConfigError unless the root is a dict.
3. validate_config pass 1: raise ConfigError (aggregated) for an analyses entry that is not a dict, reported as "analyses[{idx}]: must be a mapping". For GLOBAL_ONLY_KEYS inside a block, emit only the "belongs in the global section" message (skip the duplicate "unknown" message for those keys).
4. Helper _finite_number(value, where) -> float: ConfigError when value is bool, not int/float, or not math.isfinite. Apply to global.tr (> 0), fd_threshold (> 0), each bandpass entry and each notch_filter_band entry, before the existing range checks.
5. _check_required_block_keys: iterate required keys in sorted order; a key present with value None counts as missing.
6. Strict booleans: for each BOOL_FIELDS key present with a non-None value that is not bool, ConfigError naming the key. Global force_diff_atlas likewise. resolve_config stores keep_run_res_dtseries as bool (null -> True).
7. Nested containers: extraction, connectivity, contrasts (task_act) and connectivity.contrasts (task_conn), when present and not None, must be dicts; otherwise ConfigError. In _validate_contrasts: labels without functions -> ConfigError; functions and labels must be lists of strings.
8. Paths: in _validate_paths, each singular path value must be a non-empty str or None; each plural value must be a list whose entries are all non-empty str (None entries rejected). ConfigError on type violations; InputError for nonexistent files (unchanged).
9. Prefixes: out_file_pre must match FILENAME_TOKEN_RE. extract_out_file_pre and conn_out_file_pre must match FILENAME_TOKEN_RE whenever present and non-None. extract_out_file_pre is required (present and valid) when any of stat_buckets, extract_raw_ptseries, extract_resids (task_act), extract_pbseries (task_conn) or extract_ptseries (rest_conn) is enabled. conn_out_file_pre is required (present and valid) when calc_conn is set. Replace the existing presence-only checks.
10. Condition labels: cond_labels (task_act) and cond_beta_labels (task_conn) must be non-empty lists of unique strings matching FILENAME_TOKEN_RE; ConfigError lists offenders and notes that numeric condition codes must be quoted.
11. motion_deriv_degree: int (not bool) >= 1. global.num_cores: int (not bool) >= 1 when present.
12. derivatives_dirs (global and block): None or a non-empty list of non-empty strings; a bare string is a ConfigError with the hint "use a YAML list".
      </spec>
      <dependencies>none</dependencies>
      <risk>medium - tightens validation; configs that relied on lenient coercion now fail with ConfigError. Acceptable for an unreleased major version.</risk>
      <rollback>Revert first_level_config.py.</rollback>
    </change>

    <change id="C3" priority="P1" source_item="C1, D1, L3">
      <file path="fmri_first_level_proc/first_level_config.py" action="modify" />
      <description>Parse contrasts during resolution so grammar and condition-reference errors surface at validation and --dry-run; reject task_conn contrasts without connectivity.</description>
      <spec>In resolve_config after contrast fields are populated: task_act with contrast_functions -> call valid_contrast_functions(contrast_functions, contrast_labels, cond_labels, logger). task_conn: when connectivity.contrasts.functions is set and calc_conn is None, raise ConfigError("[label] connectivity.contrasts requires connectivity.calc_conn; set calc_conn or remove the contrasts."); when calc_conn is set, call valid_contrast_functions with cond_beta_labels. The pipeline-level calls remain (they produce the parsed structures used downstream).</spec>
      <dependencies>C2</dependencies>
      <risk>low - same parser, earlier call.</risk>
      <rollback>Remove the resolve-time calls.</rollback>
    </change>

    <change id="C4" priority="P0" source_item="A3, C4, L2">
      <file path="fmri_first_level_proc/bids.py" action="modify" />
      <description>Exact entity matching in discovery and logger-independent collision warnings.</description>
      <spec>
1. Add ENTITY_RE = re.compile(r"(?:^|_)([a-zA-Z]+)-([a-zA-Z0-9]+)(?=_|\.)") and helper _entities(basename) -> dict.
2. _glob_bids_files(func_dir, subject, task, desc, suffix, ext): glob os.path.join(func_dir, f"sub-{subject}_*_{suffix}{ext}"); keep a file only when its entities have sub == subject exactly, task == task exactly (when task is not None) and desc == desc exactly (when desc is not None; when desc is None, as for events files, the desc entity is not checked). Return the filtered list.
3. discover_inputs: emit DISCOVERY_COLLISION through graded_warning(logger or logging.getLogger(__name__), ...) so the record is accumulated without a caller logger.
4. Module docstring states exact entity matching.
      </spec>
      <dependencies>none</dependencies>
      <risk>medium - narrows discovery; previously overmatched files are no longer picked up (intended).</risk>
      <rollback>Revert bids.py.</rollback>
    </change>

    <change id="C5" priority="P0" source_item="A2, A9, B1, L2, L8">
      <file path="fmri_first_level_proc/first_level_config.py" action="modify" />
      <description>Discovery-mode requirements, run-label alignment of discovered slots, and mandatory-input enforcement after merging.</description>
      <spec>
1. In resolve_config, discovery_mode = derivatives_dirs is not None and subject is not None. When discovery_mode: subject, session (when present) and task must be non-empty str (ConfigError suggesting quoting); task is required (ConfigError "BIDS discovery mode requires 'task'"). When derivatives_dirs is set and subject is absent, keep the existing logged message.
2. Track discovered_slots = set of slot names filled from discovery, with their label lists from DiscoveredInputs.run_labels.
3. New order after merge: _resolve_run_labels -> _align_discovered_slots -> _resolve_task_mode_checks (task) -> _check_required_slots -> extraction/connectivity template checks.
4. _align_discovered_slots(cfg, discovered, discovered_slots, label): when cfg.run_labels is None, return (handled by _check_required_slots). For each discovered slot: labels [None] is accepted only when len(cfg.run_labels) == 1; otherwise require set(labels) == set(cfg.run_labels), else InputError naming the slot, the missing and the extra run labels and the source directory; then reorder the slot list to cfg.run_labels order.
5. _check_required_slots(cfg, discovery_mode, derivatives_dirs, label): task Mode A requires scan_paths, task_timing_paths, motion_paths; task with neither scan_path nor scan_paths reports scan_paths missing; task Mode B requires scan_path, task_timing_path, motion_path; rest requires scan_paths, motion_paths, CSF_paths, WM_paths. Collect all missing slots; raise InputError (discovery_mode) naming the slots and the derivatives_dirs searched, else ConfigError naming the slots. Also raise the same error class when cfg.run_labels is None after resolution.
      </spec>
      <dependencies>C2, C4</dependencies>
      <risk>medium - changes resolution order; covered by the new tests requested from /test.</risk>
      <rollback>Revert the resolve_config section.</rollback>
    </change>

    <change id="C6" priority="P0" source_item="A1">
      <file path="fmri_first_level_proc/first_level_config.py" action="modify" />
      <description>Reject a non-null singular CSF_path/WM_path in task Mode A, where it would be silently ignored.</description>
      <spec>In _resolve_task_mode_checks: when cfg.scan_paths is not None and cfg.CSF_path or cfg.WM_path is not None, raise ConfigError("[label] Mode A (scan_paths) uses per-run tissue lists; replace CSF_path/WM_path with CSF_paths/WM_paths (one entry per run).").</spec>
      <dependencies>C5</dependencies>
      <risk>low.</risk>
      <rollback>Remove the check.</rollback>
    </change>

    <change id="C7" priority="P1" source_item="D2, D3, L5">
      <file path="fmri_first_level_proc/first_level_config.py" action="modify" />
      <file path="fmri_first_level_proc/__init__.py" action="modify" />
      <description>Per-block validation API for the CLI, and normalized cross-block output-collision checks.</description>
      <spec>
1. Refactor validate_config into _validate_global(raw, logger) (top-level schema, global keys, global.tr, global.template_path, derivatives_dirs type), _schema_pass1_block(idx, block) -> list[str], and _validate_block_values(idx, block, global_cfg, logger) (current pass-2 body for one block). validate_config keeps its current contract: aggregated pass-1 errors across all blocks in one ConfigError, then per-block pass 2 in order.
2. Cross-block check _cross_block_conflicts(resolved) operating on resolved configs: for each block, prefixes = {out_file_pre, extract_out_file_pre, conn_out_file_pre} minus None, keyed by os.path.normpath(out_dir). Two different blocks conflict when they share an out_dir and any prefix. Returns {block_index: message}. Remove the raw-string duplicate pair check.
3. load_and_validate (unchanged semantics): validate_config, resolve each block in order (first error raises), then raise ConfigError on the first cross-block conflict.
4. New public load_and_validate_blocks(config_path, logger=None, **overrides) -> list[BlockResolution]. BlockResolution is a dataclass(index: int, name: str|None, analysis_type: str|None, config: ResolvedConfig|None, error: Exception|None, raw_out_dir: str|None, raw_out_file_pre: str|None). Global errors (load_config, _validate_global) raise. Each block runs pass 1 (aggregated per block), pass 2 and resolve inside try/except FmriFirstLevelError; the error is stored on its BlockResolution. Cross-block conflicts mark every involved block with ConfigError.
5. __init__.py: export load_and_validate_blocks and BlockResolution in __all__.
      </spec>
      <dependencies>C2, C3, C5, C6</dependencies>
      <risk>medium - refactor of the validator; load_and_validate behavior preserved apart from the normalized collision check.</risk>
      <rollback>Revert first_level_config.py and __init__.py.</rollback>
    </change>

    <change id="C8" priority="P0" source_item="A4, D1">
      <file path="fmri_first_level_proc/runsets.py" action="modify" />
      <description>Motion column-count and finite-value checks for motion and tissue inputs during run-set construction, so both runs and --dry-run catch them before any step executes.</description>
      <spec>In _run_consistency_checks: use_cols = (12 if include_motion_derivs else 6) for task, 6 * motion_deriv_degree for rest. After loading each motion table: shape[1] < use_cols -> InputError (same text as nuisance); not np.isfinite(m[:, :use_cols]).all() -> InputError naming the file and the first five 1-based rows containing non-finite values. For each tissue table: not np.isfinite(column 0).all() -> InputError likewise. Apply to Mode A, Mode B and rest branches. The checks in nuisance.py remain.</spec>
      <dependencies>none</dependencies>
      <risk>low.</risk>
      <rollback>Remove the added checks.</rollback>
    </change>

    <change id="C9" priority="P0" source_item="B2, C5, C7">
      <file path="fmri_first_level_proc/events.py" action="modify" />
      <description>Events-level validation of durations, condition types and duplicate trials.</description>
      <spec>
1. read_events_file: after the finiteness check, rows with duration < 0 -> InputError listing 1-based data rows. Convert trial_type with df["trial_type"] = df["trial_type"].astype(str) before the required-condition check, so Mode A and Mode B compare strings identically.
2. build_event_table: after rows are assembled (both modes) and before returning, find duplicate (run, condition, onset) among rows; raise InputError listing up to ten duplicates as (events_file, run, condition, onset), with context {"duplicates": [...]}. Runs before the timing-violation return, so duplicates are reported even without violations.
3. Module docstring mentions both checks.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - the estimability GuardError remains as an invariant guard.</risk>
      <rollback>Revert events.py.</rollback>
    </change>

    <change id="C10" priority="P1" source_item="C7">
      <file path="fmri_first_level_proc/task_conn_first_level.py" action="modify" />
      <description>Validate events-derived nuisance condition names that become file names.</description>
      <spec>After non_beta_conditions is computed: any name not matching FILENAME_TOKEN_RE (import from first_level_config) -> InputError naming the condition values and the events files, and stating that nuisance conditions are written to onset files named by condition.</spec>
      <dependencies>C2</dependencies>
      <risk>low.</risk>
      <rollback>Remove the check.</rollback>
    </change>

    <change id="C11" priority="P0" source_item="A7, L1">
      <file path="fmri_first_level_proc/names.py" action="modify" />
      <file path="fmri_first_level_proc/nuisance.py" action="modify" />
      <file path="fmri_first_level_proc/rest_conn_first_level.py" action="modify" />
      <description>rest_conn regresses the first column of each tissue file through per-run prepared copies.</description>
      <spec>
1. names.tissue_prepared(pre, tissue, label=None): label None -> existing concat name; otherwise f"{pre}_run{label}_{tissue}_prepared.1D". Add one-line docstring.
2. nuisance.rest_nuisance: per supplied run, write first-column copies for CSF, WM and GS (when supplied) to names.tissue_prepared(pre, T, lbl) with format_table; use these paths in the DOF dry run (simultaneous -ort list) and as sources for the temporary derivative files. List them as intermediate py_text outputs (expected_text) for S_pre runs only. Return state["tissue_prepared"] = {lbl: {"CSF": rel, "WM": rel, "GS": rel|None}}.
3. rest_conn_first_level: _tissue_paths_for(lbl) returns out_dir paths of the prepared files from nuisance state. Both residual-stage branches use the prepared files in derived_files in place of the raw CSF/WM/GS paths; derived_values keep the raw paths for provenance. rest_expected adds the prepared tissue names for S_pre runs.
4. INPUT_SPECIFICATION and nuisance module docstring: first column used for all analysis types.
      </spec>
      <dependencies>none</dependencies>
      <risk>medium - rest stage hashes change (derived_files), so existing rest outputs rerun once; numerically identical for single-column inputs.</risk>
      <rollback>Revert the three files.</rollback>
    </change>

    <change id="C12" priority="P1" source_item="A8, B5, C2">
      <file path="fmri_first_level_proc/task_conn_first_level.py" action="modify" />
      <description>Warn on skipped connectivity contrasts; derive expected connectivity outputs and QC contrast_labels from what the connectivity stage actually listed.</description>
      <spec>
1. In the connectivity stage, where a contrast is skipped because a referenced condition has no output: graded_warning(logger, "medium", "CONTRAST_DROPPED", f"Connectivity contrast '{label}' skipped: condition(s) {missing} produced no connectivity output.", user_facing=True).
2. task_conn_expected gains parameter conn_listed (set of relpaths listed by the task-conn-connectivity stage, from ctx.stage_outputs, empty when the stage did not run). Connectivity entries (unsmoothed and smoothed, conditions and contrasts) in the expected set are exactly conn_listed; the per-condition and per-contrast enumeration for connectivity outputs is removed.
3. The task-conn-qc fragment sets contrast_labels to the configured contrast labels whose sanitized connectivity output (unsmoothed name) is in conn_listed, preserving order; the key is omitted when none were produced.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - reuse path reads stage_outputs, which exist for both executed and reused stages.</risk>
      <rollback>Revert the edits.</rollback>
    </change>

    <change id="C13" priority="P1" source_item="L6">
      <file path="fmri_first_level_proc/qc.py" action="modify" />
      <file path="fmri_first_level_proc/engine.py" action="modify" />
      <description>Additive run_status key in qc_summary for success and failure, with a failure writer and step tracking.</description>
      <spec>
1. qc.QC_KEYS: insert "run_status": QCKeySpec("value", (), ("{t}-qc",), ALL) immediately after "analysis_type".
2. engine: dataclass RunTracker(step: str|None = None, versions: dict|None = None). RunContext.__init__ accepts tracker=None and stores it; run_step and run_stage set tracker.step = label at entry when a tracker is present; finish sets tracker.step = f"{type_label}-qc" before writing.
3. RunContext.finish: compute status from warnings before the qc step and add run_status = {"status": status, "error": None} to the {t}-qc fragment passed to merge_fragments.
4. engine.write_failure_qc(out_dir, pre, analysis_type, exc, step, versions, logger): when os.path.isdir(out_dir), pre matches FILENAME_TOKEN_RE and analysis_type is valid, build fragment {"analysis_type": analysis_type, "run_status": {"status": "failed", "error": {"type": type(exc).__name__, "message": str(exc), "exit_code": exceptions.exit_code(exc), "step": step}}} plus "provenance": versions when versions is not None; merge with qc.merge_fragments([(f"{t}-qc", frag)], analysis_type); write qc_json_text to a temporary file in out_dir and os.replace onto names.qc_summary(pre). Any OSError while writing is logged with logger.error and swallowed.
5. engine.run_with_status(analysis_type, config, logger, body): tracker = RunTracker(); try: return body(config, logger, tracker); except Exception as exc: write_failure_qc(config.out_dir, config.out_file_pre, analysis_type, exc, tracker.step, tracker.versions, logger); raise. KeyboardInterrupt and SystemExit are not caught (BaseException).
      </spec>
      <dependencies>C1</dependencies>
      <risk>medium - touches every successful qc_summary (one added key) and the failure path.</risk>
      <rollback>Revert qc.py and engine.py.</rollback>
    </change>

    <change id="C14" priority="P1" source_item="L6">
      <file path="fmri_first_level_proc/task_act_first_level.py" action="modify" />
      <file path="fmri_first_level_proc/task_conn_first_level.py" action="modify" />
      <file path="fmri_first_level_proc/rest_conn_first_level.py" action="modify" />
      <description>Route each pipeline run() through run_with_status.</description>
      <spec>Rename each current run body to _run(config, logger, tracker). run(config, logger=None) keeps its signature and docstring, sets up logging as today, then returns engine.run_with_status("task_act"|"task_conn"|"rest_conn", config, logger, _run). Inside _run: after runtime_check set tracker.versions = versions; set tracker.step = f"{type_label}-contrast-validation" before contrast parsing (task types), f"{type_label}-path-checks" before the rest path-list guard, f"{type_label}-run-sets" before build_runsets, f"{type_label}-template-check" before roi.check_template; pass tracker=tracker to RunContext.</spec>
      <dependencies>C13</dependencies>
      <risk>low - behavior identical apart from the failure write.</risk>
      <rollback>Inline _run back into run().</rollback>
    </change>

    <change id="C15" priority="P1" source_item="D1, L4">
      <file path="fmri_first_level_proc/inputs.py" action="create" />
      <description>Read-only input checks for --dry-run, reusing the run-time validators.</description>
      <spec>Module docstring. check_inputs(config, logger) -> None: runsets = build_runsets(config, config.analysis_type, logger) (covers volume counts, header TR, grids, motion/tissue rows, columns, finiteness); rest_conn additionally applies the same path-list length guard as rest run(); task types call events.build_event_table(config, runsets, required) (required = cond_labels or cond_beta_labels) and, when check.violations is non-empty, raise InputError(events.timing_error_message(record, "not written in --dry-run")) with the timing record as context; when the block uses the template (same template_used expressions as the pipelines), call roi.check_template with the pipeline's conn_types. No file is written.</spec>
      <dependencies>C8, C9</dependencies>
      <risk>low.</risk>
      <rollback>Delete the module.</rollback>
    </change>

    <change id="C16" priority="P1" source_item="D1, D3, L4, L5, L6, L7, cosmetic">
      <file path="fmri_first_level_proc/run_first_level.py" action="modify" />
      <description>Per-block CLI execution, dry-run input checks, failure recording for config-invalid blocks, and the first-failing-block exit code.</description>
      <spec>
1. main(): runtime_check once (global failure exits via exit_code). blocks = load_and_validate_blocks(args.config, logger) (global ConfigError/InputError exit 2). --analyses indices validated against len(blocks) and filtered; the plan lists each block with its original index, name, type, out_dir, out_file_pre and "INVALID: {type}: {message}" for blocks with errors.
2. For each selected block in order: when error is set, log it with the block index (logger.error), record exit_code(error), and call engine.write_failure_qc(raw_out_dir, raw_out_file_pre, analysis_type, error, "config-validation", None, logger) unless --dry-run. Otherwise, --dry-run: call inputs.check_inputs(config, logger) in try/except Exception, recording failures the same way without writing; normal run: DISPATCH[type](config, logger) in try/except Exception, recording exit_code(exc) and logging "Analysis [index] '{name}' failed: {type}: {message}"; on success extend all_warnings.
3. Final summary log lists each block's index, name and outcome. Exit: the first failing block's code in config order; else 3 when any high-severity warning; else 0. --dry-run applies the same rule (no warnings collected, so 0 when all blocks pass).
4. Module docstring: exit-code section updated to the per-block rule.
      </spec>
      <dependencies>C1, C7, C13, C14, C15</dependencies>
      <risk>medium - CLI control flow changes; Python API unaffected.</risk>
      <rollback>Revert run_first_level.py.</rollback>
    </change>

    <change id="C17" priority="P1" source_item="E1-E5 and all behavior changes above">
      <file path="INPUT_SPECIFICATION.md" action="modify" />
      <file path="README.md" action="modify" />
      <file path="CHANGELOG.md" action="modify" />
      <file path="example_config.yaml" action="modify" />
      <description>Bring user documentation in line with the new behavior and correct the five inaccuracies the audit found.</description>
      <spec>INPUT_SPECIFICATION: validation order and error classes (structural/type checks, null-as-missing, strict booleans, finite numerics, FILENAME_TOKEN_RE for prefixes and condition labels, required extract/conn prefixes, derivatives_dirs list type, contrasts parsed at validation, contrasts with calc_conn null rejected, Mode A singular tissue rejected, unresolved required inputs with ConfigError/InputError rule, cross-block prefix collisions); BIDS discovery mode definition, task requirement, string entities, exact entity matching, run-label alignment; events negative durations and duplicate trials as InputError, trial_type compared as strings; motion/tissue finiteness and column checks at run-set construction; first tissue column for all types including rest prepared files {pre}_run{N}_{T}_prepared.1D; run_status QC key with success and failure schema and the failure-summary contents; CLI per-block isolation, --dry-run scope and the first-failing-block exit rule; new API load_and_validate_blocks and BlockResolution; DISCOVERY_COLLISION independent of logger; CONTRAST_DROPPED for skipped connectivity contrasts and contrast_labels reflecting produced contrasts. README: CLI, exit codes, dry-run and multi-block behavior, programmatic exports. CHANGELOG 4.0.0: Added/Changed/Fixed entries for each item. example_config.yaml: comments for required prefixes, discovery-mode task requirement and quoting of numeric IDs.</spec>
      <dependencies>C1-C16</dependencies>
      <risk>low.</risk>
      <rollback>Revert the documentation files.</rollback>
    </change>

  </changes>

  <execution_order>C1, C2, C3, C4, C5, C6, C7, C8, C9, C10, C11, C12, C13, C14, C15, C16, C17</execution_order>

  <testing_note>No tests are run in this skill. /test should add: a specification-driven error-path matrix through load_and_validate, load_and_validate_blocks and main() with real inputs (each ConfigError/InputError rule above, exit codes per block, dry-run behavior); discovery-through-resolve tests (exact matching, task requirement, string entities, label alignment and mismatch errors, mandatory slots); events duplicates and negative durations; non-finite motion/tissue; rest multi-column tissue numerics (identical results for single-column input, first column used for multi-column input); run_status on success and on failure (including no partial metrics); task_conn skipped-contrast warning, expected-set and contrast_labels on rerun with a newly null condition.</testing_note>
</implement_plan>
