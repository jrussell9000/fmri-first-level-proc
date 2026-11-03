# Changelog

All notable changes to `fmri-first-level-proc` are documented in this file. Versions follow semantic versioning: breaking changes to the config schema, outputs or behavior ship only in a major release. Releases up to 3.1.0 are recorded in the repository's tagged commits.

## [4.0.0] - Unreleased

A major release: a stage-based execution engine with a per-analysis ledger, multi-run inputs, a closed config schema, Power et al. (2012) framewise displacement censoring, trial estimability, and a module-level reorganization of the package. Configs, outputs and QC summaries written for 3.1.0 are not compatible. See [INPUT_SPECIFICATION.md](./INPUT_SPECIFICATION.md) for the full 4.0.0 contract.

### Breaking changes

- **Censoring metric.** Censoring now uses Power et al. (2012) framewise displacement on a 50 mm sphere (a TR is censored when FD > `fd_threshold`) instead of AFNI enorm via `1d_tool.py -censor_motion`. The metrics are not interchangeable (0.873 x enorm <= FD <= 2.30 x enorm), so `fd_threshold` values must be re-chosen. Enorm is still computed and reported for reference (`{prefix}_enorm.1D`, `enorm_summary`), and the FD series is written to `{prefix}_fd.1D`.
- **Motion file contract.** The first six columns must be `[tx, ty, tz, rx, ry, rz]` in mm and degrees; AFNI `3dvolreg` rotations-first output must be reordered and fMRIPrep radians converted.
- **Closed config schema.** Unknown keys at any level are rejected, and all violations are reported in one `ConfigError`. The global-only keys `tr`, `num_cores`, `template_path` and `force_diff_atlas` placed in an analysis block are now a `ConfigError` (previously a warning, and the block value was ignored). `global.tr` is required.
- **Run model.** Task analyses take per-run lists (Mode A, new) or one concatenated file with `run_lengths` and `run_labels` (Mode B; both now required). Mode B models run boundaries with per-run baselines (`3dDeconvolve -concat`); 3.1.0 modeled a single task file as one run. Runs are identified by integer labels (`run{N}` in file names and QC records), not list positions. Scan header TR must equal `tr`, all runs must share a grid, and motion and tissue files must have one row per volume (`InputError` otherwise).
- **Trial survival.** A trial survives when its regressor energy on uncensored TRs is positive (pooled over basis columns for multi-column HRFs). The surviving-trial floor is 2 for `task_act` and 3 for `task_conn`.
- **Stat-bucket indexes.** Keys in `{ext}_{stat}_index.json` are the exact `3dinfo -label` sub-brick labels (including `Full_Fstat` and `Full_R^2`); `Zstat` keys are the matching `Tstat` label with `Tstat` replaced by `Zstat`.
- **Contrast labels.** Duplicate contrast labels, or labels that collide after file-name sanitization, are a `ConfigError`.
- **`remove_previous`.** Removes only files recorded in this analysis's ledger (previously every file in `out_dir`).
- **Pre-existing outputs.** An `out_dir` holding files with this analysis's prefixes that no ledger records (for example 3.1.0 outputs) is refused with `InputError`.
- **Reruns.** The global config-hash invalidation and cascade rerun is replaced by per-stage hashes with five rerun triggers (see [Stage reuse](./INPUT_SPECIFICATION.md#stage-reuse-and-reruns)).
- **Output names.** File names are defined centrally. Changes from 3.1.0 include: tissue derivatives are `.1D` files named `{pre}_concat_{tissue}_deriv.1D` or `{pre}_run{N}_{tissue}_deriv.1D` (previously `{pre}_{tissue}_deriv.txt`); the resampled template is prefixed, `{pre}_{template}_resampled.nii.gz`; sequenced-backend intermediates are under `{pre}_sequenced_intermediates/run{N}/`; and per-run names use the run label. Three primary outputs have frozen names: `{pre}_concat_bucket_stats.nii.gz`, `{pre}_concat_LSS.nii.gz` and `{pre}_concat_residual_dtseries.nii.gz`.
- **QC summary schema.** `{pre}_qc_summary.json` follows a fixed key schema; `per_run_dof` is now a list of records, and many keys were added (see Added).
- **Connectivity backend.** Parcellated connectivity uses `3dROIstats` and `1ddot -dem`, and seed-to-voxel uses `3dTcorr1D`, replacing `3dNetCorr`. Fisher Z clips |r| at 0.999329, and zero-variance ROIs are written as `NaN` rows and columns. Values can differ from 3.1.0; `1ddot` prints five decimals, so r is rounded at about 10^-5.
- **rest_conn baseline.** The simultaneous backend uses `-polort 2` when the bandpass lower bound is above 0, else `1 + floor(n_vols * tr / 150)`, per run (previously `-polort -1` with bandpass).
- **Lockfile and versions.** The tools lockfile ships inside the package (`fmri_first_level_proc/tools.lock.yaml`, `lockfile_version` 2.0.0) with `minimum` and `validated` versions for AFNI, Python, numpy and pandas. A version below `minimum` raises `ToolVersionError`; a version different from `validated` emits `UNVALIDATED_VERSION`. The previous optional repository-root lockfile with exact-match pins is gone. New minimum dependencies: `numpy>=2.4.2`, `pandas>=3.0.1`, and `packaging`.
- **Warnings.** `graded_warning` accepts only codes from the closed warning table, each with a fixed severity (`GuardError` otherwise).
- **Strict config values.** A required key set to `null` counts as missing, except boolean keys (`null` means the default) and `bandpass` (which reports its own "bandpass is required" error). Boolean keys accept only `true`, `false` or `null`. `tr`, `fd_threshold`, `bandpass` and `notch_filter_band` must be finite numbers; `num_cores` and `motion_deriv_degree` must be integers `>= 1`. `out_file_pre`, `extract_out_file_pre`, `conn_out_file_pre` and condition labels must be file-name-safe tokens (`^[A-Za-z0-9][A-Za-z0-9._-]*$`); condition label lists must be unique strings (quote numeric codes). `extract_out_file_pre` is required for every enabled extraction (including `extract_resids`). `derivatives_dirs` must be a list. Nested sections must be mappings, and path values non-empty strings.
- **Mode A tissue paths.** A non-null singular `CSF_path`/`WM_path` with `scan_paths` is a `ConfigError` (it was silently ignored).
- **task_conn contrasts.** `connectivity.contrasts` with `calc_conn: null` is a `ConfigError`.
- **BIDS discovery mode** (`derivatives_dirs` and `subject` set) requires `task`, and `subject`, `session` and `task` must be strings. Entities are matched exactly, and discovered per-run files are aligned to the analysis run labels; mismatched run sets raise `InputError`.
- **Events.** Negative durations and duplicate trials (same run, condition and onset) raise `InputError`. Duplicate trials previously surfaced as a `GuardError` after the estimability dry run.
- **CLI.** Analysis blocks are validated and run independently, and `--dry-run` also checks input files. The exit code is that of the first failing block in config order.
- **Programmatic API.** Only the names exported in `__all__` and the three `run_*` entry points are public. Helper functions formerly in `first_level_utils` were removed or moved to the new modules (`bids`, `checkpoint`, `connectivity`, `engine`, `estimability`, `events`, `names`, `nuisance`, `prep`, `qc`, `roi`, `runsets`, `smoothing`).

### Added

- Stage execution engine: staging directories, output validation, atomic promotion, an append-only ledger (`{pre}_ledger.jsonl`, format 2), stage reuse with QC and warning replay, and a retirement sweep of obsolete outputs.
- Content hashing of derived inputs (censor, motion, onset, tissue and template files, and the scan grid) in stage hashes.
- Pre-model run exclusion with continued processing: task runs with too few uncensored TRs (`RUN_INSUFFICIENT_TRS`), and rest runs with DOF < 1 (`RUN_SKIPPED`), including runs for which `3dTproject` aborts because too few points remain after censoring.
- Per-run regression failure isolation in `rest_conn` (`RUN_FAILED`, `failed_runs`).
- Matrix-derived degrees of freedom for `task_act` and `task_conn`, and dry-run DOF for both `rest_conn` backends.
- Voxelwise spatial smoothing (`smoothing.enabled`, `smoothing.fwhm`) with `3dBlurToFWHM -ACF`, a data-derived mask, ACF FWHM QC and `_s{N}mm` output siblings, including a smoothed `task_act` GLM with the same contrasts.
- `roi_zero_handling` (`exclude` or `include`).
- Template resampling onto the scan grid when the grids differ.
- Trial-level QC records and `task_conn` index files: `{pre}_concat_LSS_index.json` (every 3dLSS sub-brick) and `{pre}_concat_bseries_{cond}_index.json` (every beta-series sub-brick).
- Onset validation (negative onsets, onsets at or after run end) with `{pre}_timing_errors.json`.
- Mode A required-condition check over the union of all supplied runs.
- PSC sentinel: `InputError` when 25% or more of non-constant voxels have a non-positive mean (demeaned input), and per-run PSC QC.
- QC keys: `censor_metric`, `fd_radius_mm`, `fd_summary`, `enorm_summary`, `bandpass`, `bandpass_backend`, `trials`, `per_condition_run_counts`, `excluded_runs`, `failed_runs`, `psc_per_run`, `smoothing_per_run`, `pcorr_rank_checks`, `null_rois`, `null_seed_conditions`, `zero_variance_target_voxels`, `roi_coverage`, `low_baseline`, `reused_stages`, `retired_outputs`, `provenance`.
- Warning codes: `RUN_INSUFFICIENT_TRS`, `RUN_FAILED`, `NULL_ROI`, `SEED_NULL`, `PCORR_RANK_DEFICIENT`, `RETIREMENT_FAILED`, `LEDGER_ENTRY_UNREADABLE`, `UNVALIDATED_VERSION`, `DERIV_RUN_BOUNDARY`, `SMOOTH_FWHM_OFF_TARGET`, `SMOOTH_INPUT_ABOVE_TARGET`.
- `FirstLevelResult.output_files` and `FirstLevelResult.intermediate_files` (final and intermediate files, disjoint).
- `ResolvedConfig.schema_version` and `ResolvedConfig.input_mode`.
- QC key `run_status` (`{status, error}`) in every `{pre}_qc_summary.json`. A failed run writes a summary with `analysis_type`, `run_status` (exception type, message, exit code and step) and `provenance`, then re-raises.
- `load_and_validate_blocks` and `BlockResolution` for per-block validation, and `exceptions.exit_code`.
- Required-input check after explicit paths and discovery are merged (`ConfigError` without discovery, `InputError` with discovery).
- Run-set checks of motion column counts and finite motion and tissue values.
- Cross-block output-collision check: blocks sharing a normalized `out_dir` may not share any output prefix.
- Contrast parsing during config resolution, so `--dry-run` reports contrast errors.

### Changed

- `CENSOR_HIGH` is one high-severity warning when more than 50% of model-run TRs are censored, for every analysis type. The 30% warning tier is gone.
- `rest_conn` censoring totals (`n_trs_total`, `n_trs_censored`, `pct_censored`) and `CENSOR_HIGH` cover the runs entering regression rather than every supplied run; `per_run_censoring` still lists every supplied run.
- The CONDITION events scheme (`CONDITION`, `ONSET`, `DURATION`) is fully supported alongside BIDS, in tab- or comma-delimited files, with no deprecation warning. Non-finite onsets or durations (including BIDS `n/a`) raise `InputError`.
- `task_conn` nuisance conditions (conditions not in `cond_beta_labels`) are taken only from runs entering the model.
- Run-intersection and smoothing masks support any number of runs.
- `notch_filter_band` affects only the motion used to compute FD; the regression receives the unfiltered motion columns.
- rest_conn regresses the first column of each CSF/WM/GS file through per-run prepared copies (`{pre}_run{N}_{tissue}_prepared.1D`), as task analyses do; results are unchanged for single-column files.
- Events `trial_type` values are compared as strings in both input modes.
- A task_conn connectivity contrast skipped because a referenced condition produced no output emits `CONTRAST_DROPPED`, and QC `contrast_labels` lists only contrasts that produced outputs.
- `DISCOVERY_COLLISION` is recorded even when no logger is passed.

### Fixed

- Missing required inputs (empty `paths`, discovery skipped or finding nothing) raised an unexpected `TypeError` (exit 1); they now raise `ConfigError` or `InputError` (exit 2).
- Non-finite motion values were not censored and failed late inside AFNI; they now raise `InputError` before any step.
- `extract_resids` without `extract_out_file_pre` wrote `None_resids.csv`; it is now a `ConfigError`.
- A string `derivatives_dirs` was iterated per character.
- A task_conn rerun in which a previously produced connectivity output was no longer produced could stop with a `GuardError`; expected connectivity outputs now follow what the stage produced.
- `stat_buckets` extraction: `Fstat` and `R^2` matched no sub-brick and were skipped; `Zstat` extraction failed; sub-bricks of multi-basis HRFs collapsed onto one index key; and index keys carried a leading apostrophe. Sub-bricks are now selected from `3dinfo -label` by exact label suffix, and each `Tstat` sub-brick's DOF is read from a single `3dAttribute BRICK_STATAUX` call.

### Removed

- The `run-first-level` console script (deprecated in 3.1.0); `fmri-first-level-proc` is the only entry point.
- The legacy extraction keys `extract`, `extract_labels` and `extract_stat`, which now raise `ConfigError` naming `stat_buckets`.
- The `first_level_utils` argparse helpers `dir_path_exists`, `file_path_exists`, `valid_string_list`, `valid_stat_type`, `valid_ave_type` and `valid_conn_type`.
- The `orient` and `spacing` keys of `get_3dinfo_properties`, which now returns only `space` and `dmax` and accepts an optional `keys` filter.
- BIDS discovery of `template_path`; the template is a global config key only.
- The warning codes `CLI_DEPRECATED`, `LOCKFILE_ABSENT`, `TRIALS_FEW` and `EVENTS_LEGACY`.
- The `3dNetCorr` runtime dependency.
