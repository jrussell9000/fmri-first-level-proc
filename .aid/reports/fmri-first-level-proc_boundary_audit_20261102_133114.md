# Input-Boundary Audit: fmri-first-level-proc 4.0.0 (branch v4.0.0-build)

Date: 2026-11-02. Method: orchestrator-level full read of the code path from YAML to pipeline entry; no execution, no sub-agents. Every finding below cites the code that produces it. "Confirmed (code)" means the behavior follows directly from the cited lines; "Plausible" means it depends on AFNI or engine behavior that was not executed and needs a reproduction before a fix is designed.

## Scope

Read in full: `first_level_config.py`, `bids.py`, `runsets.py` (construction and consistency checks), `events.py`, `nuisance.py`, `run_first_level.py`, `engine.py` (`start`, `_refuse_unrecorded`, `_remove_previous`, `finish`), the `run()` entry and model-assembly sections of `task_act_first_level.py`, `task_conn_first_level.py` and `rest_conn_first_level.py`, `roi.check_template`, `estimability` (trial records, floors), `first_level_utils` (`load_numeric_table`, `write_tissue_derivative`, `valid_contrast_functions`, `get_3dinfo_properties`).

Not audited (inside the pipelines, beyond the input boundary): `prep.py` (PSC), `smoothing.py`, `connectivity.py`, ROI extraction and ROI QC internals, `checkpoint.py` parsing, engine stage hashing and reuse internals, rest residual stages beyond argument assembly, the task_conn beta-series middle, DOF helpers in `estimability.py`, `runtime.py`.

## A. Silent wrong results (highest priority)

| ID | Finding | Evidence | Status |
|---|---|---|---|
| A1 | Mode A task block with a non-null singular `CSF_path`/`WM_path`: the tissue regressor is silently dropped. Config only rejects singular+plural for the same slot; nuisance reads only the plural list in Mode A. | `first_level_config.py:1116-1130`; `nuisance.py:323-326` | Confirmed (code) |
| A2 | BIDS discovery aligns slots by sorted position, never by run label. Equal-count slots with different labels (e.g. scans run-1,2 and motion run-1,3) are paired silently; mixing explicit `scan_paths` with discovered lists is aligned by position too. `DiscoveredInputs.run_labels` is computed but never read. | `bids.py:215-219`; `first_level_config.py:1062-1085` (no label use); `_resolve_task_mode_checks` checks lengths only (`1159-1168`) | Confirmed (code) |
| A3 | Discovery glob `_task-{task}*` matches task-name prefixes (`task-rest` also matches `task-restpre`), and `task: null` matches every task in the func directory, so runs of different tasks can be combined when their run labels differ. | `bids.py:67-76` | Confirmed (code) |
| A4 | Non-finite motion values: `np.loadtxt` accepts `nan`/`inf`; FD becomes NaN and `NaN > fd_threshold` is False, so those TRs are kept; NaN reaches the regressors; the run then fails at QC serialization (`allow_nan=False`, a ValueError, exit 1) after the full pipeline ran. Tissue files likewise unchecked. | `first_level_utils.py:416-420`; `nuisance.py:128-136`; `qc.py:218` | Censoring part confirmed (code); downstream AFNI behavior plausible |
| A5 | `fd_threshold`, `tr`, `bandpass` and `notch_filter_band` accept NaN (and inf): every check is `<= 0` style, which NaN passes. NaN `fd_threshold` disables censoring; NaN `tr` passes the header-TR check (`abs(x - nan) > 1e-4` is False). | `first_level_config.py:453-461, 502-509, 684-712`; `runsets.py:319` | Confirmed (code) |
| A6 | Output prefixes are not validated. `extract_resids: true` without `extract_out_file_pre` writes `None_resids.csv`; an explicit `null` for `extract_out_file_pre` or `conn_out_file_pre` passes the presence-only checks and yields `None_*` files. With `stat_buckets` and a null extraction prefix, `template_used` is false, so the atlas-space check and template resampling are skipped while extraction still runs with the unresampled template. Empty or path-separator prefixes are also accepted. | `first_level_config.py:777-840` (key presence only); `task_act_first_level.py:486-490, 820-866`; `names.py:243-244` | Confirmed (code) |
| A7 | rest_conn passes each CSF/WM/GS file directly to `3dTproject -ort`, so every column becomes a regressor, while the DOF reconstruction (`n_orts`, one per tissue) and the tissue derivative (first column only) assume one column. task analyses use the first column only. | `rest_conn_first_level.py:115-121`; `nuisance.py:452-454, 537-563`; `first_level_utils.py:496-504` vs `nuisance.py:331` | Confirmed (code) |
| A8 | QC `contrast_labels` (task_conn) lists every kept contrast, including contrasts skipped because a referenced condition produced no connectivity output. | `task_conn_first_level.py:936-941, 1010-1011` | Confirmed (code) |
| A9 | `derivatives_dirs` given as a string is iterated per character; discovery searches single-character roots, finds nothing, and the run then crashes (see B1). | `first_level_config.py:913, 944`; `bids.py:194` | Confirmed (code) |

## B. Wrong exit code or unhelpful crash for a user-input error

| ID | Finding | Evidence | Status |
|---|---|---|---|
| B1 | Required inputs are never enforced after explicit paths and discovery are merged (v3.1.0 had mandatory-slot `InputError` checks). Reachable when `paths` is empty, discovery finds nothing, discovery is skipped for a missing `subject` (validation already exempted `paths`), or Mode A omits a list. Results: `list(None)` TypeError (`runsets.py:246`), `None[pos]` TypeError (`runsets.py:339`, `events.py:202`), `len(None)` TypeError (`rest_conn_first_level.py:379`), all exit 1. Mode B missing motion or events gives exit 2 but with misleading text ("Cannot read motion file 'None'", "header recognized under neither delimiter"). | `first_level_config.py:584-599, 1046-1097`; cited sites | Confirmed (code) |
| B2 | Duplicate events rows (same condition, run, onset) raise `GuardError` (exit 1, documented as a package bug), and only after the 3dDeconvolve estimability dry run. | `estimability.py:363-373`; `events.py` has no duplicate check | Confirmed (code) |
| B3 | Required keys present with a `null` value pass the presence check, then fail later: `out_dir: null` gives TypeError in `os.path.abspath`; `fd_threshold: null` gives TypeError in `float`; `cond_labels`/`hrf_model`/`average_type: null` fail inside the pipeline. | `first_level_config.py:597-599, 933-937` | Confirmed (code) |
| B4 | Structural type errors raise AttributeError/TypeError (exit 1): non-mapping YAML root; an `analyses` entry that is not a mapping; `connectivity` given as a list; `None` or non-string entries in path lists (validation skips `None` in task lists, then `os.path.abspath(None)` fails). | `first_level_config.py:293-307, 363-370, 615-617, 758, 824, 923-926` | Confirmed (code) |
| B5 | task_conn rerun in which a condition or contrast that produced an output last time is now null or skipped: the old file is in `out_dir`, is in `expected`, and is not listed, so `finish` raises `GuardError` ("Expected output exists but is not listed"). | `task_conn_first_level.py:169-178, 892-941`; `engine.py:676-683` | Plausible (needs reproduction) |

## C. Silent ignores and missing warnings

| ID | Finding | Evidence |
|---|---|---|
| C1 | task_conn `connectivity.contrasts` with `calc_conn: null` are not parsed and are ignored with no warning. | `task_conn_first_level.py:261-266` |
| C2 | task_conn contrasts whose conditions lack a connectivity output are skipped with no warning (and see A8). | `task_conn_first_level.py:940-941` |
| C3 | task_act `contrasts.labels` without `functions`, and `contrasts` or `extraction` that are not mappings, are ignored silently. | `first_level_config.py:744-756, 780-781, 969-980` |
| C4 | `DISCOVERY_COLLISION` is emitted only when a logger is passed, so programmatic calls without a logger lose a graded warning. | `bids.py:202` |
| C5 | Negative event durations are accepted (only finiteness is checked). | `events.py:96-122` |
| C6 | Booleans are coerced with `bool()`, so a quoted `"false"` is True; `keep_run_res_dtseries` is stored uncoerced. | `first_level_config.py:939-943, 965-966, 1031-1032` |
| C7 | `cond_labels`/`cond_beta_labels` are not type-checked: a string is iterated per character, YAML integers never match string conditions, duplicates are accepted, and a label containing `/` crashes when the onset file is written. The Mode B required-condition check compares against pandas-typed `trial_type` values (numeric codes fail) while Mode A compares strings, so the same events data passes in Mode A and fails in Mode B. | `first_level_config.py:958, 989`; `events.py:125-130` vs `211, 260-261`; `task_act_first_level.py:540, 636` |
| C8 | `motion_deriv_degree` truncates floats (`int(2.9) == 2`); `num_cores` is unvalidated. | `first_level_config.py:676-682, 907-908, 1028` |

## D. Detection gaps

| ID | Finding | Evidence |
|---|---|---|
| D1 | `--dry-run` validates schema and file existence only. Contrast grammar and condition references are parsed in each pipeline's `run()`, and events, motion column counts, header TR and grids are checked only at run time, so a dry run passes configs that fail immediately. | `run_first_level.py:141-143`; `task_act_first_level.py:467-474`; `task_conn_first_level.py:261-266` |
| D2 | Duplicate `(out_dir, out_file_pre)` detection compares raw strings (`out`, `./out`, `/abs/out`, `out/` are distinct). `extract_out_file_pre`/`conn_out_file_pre` collisions between blocks sharing an `out_dir` are not checked; two task blocks with the same extraction prefix both write `{ext}_raw_ptseries.csv`, and the second is not refused because the first's ledger records the file. | `first_level_config.py:563-574`; `engine.py:212-244` |
| D3 | CLI: the first failing block aborts all later blocks. This may be intended, but it is undocumented. | `run_first_level.py:148-185` |

Cosmetic: global-only keys inside a block are reported twice (unknown key and global-only key); the first missing required key reported depends on set iteration order; with `--analyses` the plan is renumbered from 0.

## E. Documentation corrections required (INPUT_SPECIFICATION.md as written today)

1. "Missing files named in the config raise `InputError`; all other validation failures raise `ConfigError`": not true for unresolved required inputs (B1) or structural type errors (B4).
2. Tissue files "the first column is used": true for task analyses only (A7).
3. "Trials must be unique per (condition, run, onset); duplicates raise an error": the error is `GuardError`, exit 1 (B2).
4. "A singular `CSF_path`/`WM_path` of `null` may accompany Mode A lists": a non-null singular value is silently ignored (A1).
5. `DISCOVERY_COLLISION` requires a logger (C4).

## F. Why the 682-test suite did not catch these

- No test calls `resolve_config` with `derivatives_dirs`; the discovery merge, slot alignment and missing-slot paths are untested (only `discover_inputs` is unit-tested).
- CLI exit codes are tested by monkeypatching `load_and_validate` to raise each exception type; no test drives a real malformed input through `main()`, so inputs that escape as TypeError are invisible.
- No tests for null or absent prefix values, duplicate events rows, non-finite motion or tissue values, multi-column rest tissue files, Mode A with singular tissue paths, or contrast skips.
- The suite was built from change lists and gap surveys of changed code, not from the input contract.

## G. Recommended next steps

1. Reproduce the two plausible items (A4 downstream, B5) and one representative confirmed item per class with small real-AFNI cases before designing fixes (requires approval).
2. `/implement plan` from this report. The likely shape: one resolve-time completeness and type layer (mandatory slots after discovery; prefix values non-empty, file-name-safe strings; path entries strings; strict booleans; finite numerics; label lists of unique strings), discovery alignment by run label with exact task match, rejection of singular tissue paths in Mode A, single-column (or first-column) rest tissue handling, events-level duplicate and negative-duration `InputError`, finite-value checks on motion and tissue, contrast parsing at validation time plus warnings for ignored or skipped contrasts, `expected` derived from produced outputs in task_conn, normalized out-pair and cross-block prefix collision checks.
3. `/test`: a specification-driven error-path matrix that drives each documented rule through `load_and_validate` and `main()` with real inputs, plus discovery-through-resolve tests.
4. A second boundary pass over the modules listed under "Not audited" before publication.
