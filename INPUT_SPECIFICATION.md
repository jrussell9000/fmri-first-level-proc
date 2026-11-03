# Input Specification

Complete reference for `fmri-first-level-proc` 4.0.0: the YAML config schema, every parameter and its constraints, the run model, input file formats, censoring and estimability rules, every output file and its identifiers, the QC summary schema, warning codes, stage reuse, runtime validation, exit codes, and the programmatic API. Config schema version: `4.0.0` (`ResolvedConfig.schema_version`).

---

## Table of Contents

- [YAML Config Structure](#yaml-config-structure)
- [Global Settings](#global-settings)
- [Run Model: Mode A, Mode B, and Run Sets](#run-model-mode-a-mode-b-and-run-sets)
- [Analysis Block: Common Fields](#analysis-block-common-fields)
- [Analysis Block: task\_act](#analysis-block-task_act)
- [Analysis Block: task\_conn](#analysis-block-task_conn)
- [Analysis Block: rest\_conn](#analysis-block-rest_conn)
- [Spatial Smoothing](#spatial-smoothing)
- [Input File Formats](#input-file-formats)
- [Censoring and Run Exclusion](#censoring-and-run-exclusion)
- [Trial Estimability and Condition Floors](#trial-estimability-and-condition-floors)
- [Degrees of Freedom](#degrees-of-freedom)
- [Percent Signal Change Scaling](#percent-signal-change-scaling)
- [Parcel Extraction and ROI QC](#parcel-extraction-and-roi-qc)
- [Functional Connectivity](#functional-connectivity)
- [BIDS Input Discovery](#bids-input-discovery)
- [Output Files](#output-files)
- [Sub-brick Identifiers](#sub-brick-identifiers)
- [QC Summary JSON](#qc-summary-json)
- [Warning Codes](#warning-codes)
- [Stage Reuse and Reruns](#stage-reuse-and-reruns)
- [Runtime Validation](#runtime-validation)
- [Exit Codes](#exit-codes)
- [CLI Flags](#cli-flags)
- [Programmatic API](#programmatic-api)
- [Exception Hierarchy](#exception-hierarchy)
- [Known Limitations](#known-limitations)
- [References](#references)

---

## YAML Config Structure

```yaml
global:
  # settings applied to every analysis block

analyses:
  - # analysis block 1
  - # analysis block 2
```

- `global` (dict, optional): settings shared by every block.
- `analyses` (list, required, non-empty): analysis blocks, executed in file order.

**Closed schema.** Every key at every level is checked against the allowed key set for its analysis type before any value is validated. All unknown keys, all global-only keys placed inside a block, and all legacy keys are collected and reported together in a single `ConfigError` ("Config schema violations"). After that pass, value validation is fail-fast (the first violation raises).

**Legacy keys removed in 4.0.0.** `extraction.extract`, `extraction.extract_labels` and `extraction.extract_stat` raise `ConfigError` directing the user to `extraction.stat_buckets`.

**Validation order.** (1) closed-schema key check (the YAML root and every `analyses` entry must be mappings); (2) global values: `global.tr`, `num_cores`, `force_diff_atlas`, `template_path`, `derivatives_dirs`; (3) per block: required keys, section types, booleans, path types and existence, enums, `fd_threshold`, `out_file_pre`, condition labels, HRF, `rest_conn` parameters, contrasts, extraction, connectivity, smoothing, `run_lengths`, `run_labels`, and creation of `out_dir`; (4) resolution: global merge, BIDS discovery, run-label resolution, alignment of discovered files, Mode A/B checks, required inputs, contrast parsing, template requirements; (5) cross-block output collisions.

**Value rules applied in every block.**
- A required key set to `null` counts as missing, except boolean keys (`null` means the documented default, e.g. `include_motion_derivs: null` is `false`) and `bandpass` (`null` raises the `rest_conn` message "bandpass is required").
- Boolean keys accept `true`, `false` or `null` (`null` means the documented default); any other value (including the string `"false"`) is a `ConfigError`.
- Numeric keys (`tr`, `fd_threshold`, `bandpass`, `notch_filter_band`, `smoothing.fwhm`) must be finite numbers; booleans, `.nan` and `.inf` are rejected. `num_cores` and `motion_deriv_degree` must be integers `>= 1`.
- `extraction`, `connectivity`, `smoothing`, `contrasts` and `connectivity.contrasts` must be mappings when present.
- Path values must be non-empty strings; path lists must be non-empty and contain only non-empty strings.
- **File-name-safe tokens.** `out_file_pre`, `extract_out_file_pre`, `conn_out_file_pre` and every condition label must match `^[A-Za-z0-9][A-Za-z0-9._-]*$` (letters, digits, `.`, `_`, `-`, starting with a letter or digit), because they become parts of file names.

**Error classes.** Nonexistent files named in the config raise `InputError`; required inputs still unresolved after BIDS discovery raise `InputError` (see [BIDS Input Discovery](#bids-input-discovery)); every other validation or resolution failure, including required inputs missing without discovery, raises `ConfigError`.

**Cross-block collisions.** Two blocks may share an `out_dir` only when none of their output prefixes (`out_file_pre`, `extract_out_file_pre`, `conn_out_file_pre`) coincide. Directories are compared after normalization (`out`, `./out` and the absolute path are the same directory). A collision is a `ConfigError` for every block involved. A single block may reuse one prefix for its own extraction and connectivity outputs.

**Per-block validation.** `load_and_validate` raises on the first invalid block. The CLI uses `load_and_validate_blocks`, which validates and resolves every block independently (see [CLI Flags](#cli-flags) and [Programmatic API](#programmatic-api)).

---

## Global Settings

| Key | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `tr` | float | (required) | finite, `> 0` | Repetition time in seconds for every scan in every block. Each scan's NIfTI header TR must match it within 1e-4 s (see [Run Model](#structural-checks-before-any-processing)). |
| `num_cores` | int | `1` | integer `>= 1` | Passed to AFNI as `-jobs` for `3dDeconvolve`. |
| `template_path` | str or null | `null` | File must exist | ROI template (`.nii` or `.nii.gz`). Required by every extraction and connectivity feature. See [ROI Template File](#roi-template-file). |
| `force_diff_atlas` | bool | `false` | | Downgrade a template/scan atlas-space mismatch from `InputError` to a logged warning. |
| `derivatives_dirs` | list of str or null | `null` | YAML list, not a bare string | Ordered BIDS derivatives roots for input discovery. Also allowed per block (block value overrides global). See [BIDS Input Discovery](#bids-input-discovery). |

`tr`, `num_cores`, `template_path` and `force_diff_atlas` are **global-only**: placing any of them inside an analysis block is a `ConfigError`.

---

## Run Model: Mode A, Mode B, and Run Sets

Runs are identified by **integer run labels**, never by list position. Labels appear in file names as `run{N}` and in every per-run QC record.

### Task analyses (`task_act`, `task_conn`)

Exactly one input mode per block; mixing a singular slot and its plural counterpart is a `ConfigError`.

| | Mode A (per-run files) | Mode B (single concatenated file) |
|---|---|---|
| Scan | `paths.scan_paths` (list) | `paths.scan_path` (str) |
| Events | `paths.task_timing_paths` (list) | `paths.task_timing_path` (str) |
| Motion | `paths.motion_paths` (list) | `paths.motion_path` (str) |
| CSF / WM (optional) | `paths.CSF_paths`, `paths.WM_paths` (lists) | `paths.CSF_path`, `paths.WM_path` (str or null) |
| `run_lengths` | not allowed | **required**: volumes per run, acquisition order; must sum to the scan's volume count |
| `run_labels` | optional; inferred from the `run-N` BIDS entity of each scan file name when omitted | **required**; same length as `run_lengths` |
| Event onset times | relative to the start of each run | relative to the start of the concatenated series |

In Mode A, every per-run list must have the same length as `scan_paths`. Tissue regressors in Mode A must be given as per-run lists (`CSF_paths`, `WM_paths`); a non-null singular `CSF_path` or `WM_path` alongside `scan_paths` is a `ConfigError` (a singular value of `null` is allowed and means "no tissue regressor").

**Required inputs** are checked after explicit paths and BIDS discovery are merged: Mode A needs `scan_paths`, `task_timing_paths` and `motion_paths`; Mode B needs `scan_path`, `task_timing_path` and `motion_path`. All missing slots are reported together.

### `rest_conn`

Always per-run lists (`scan_paths`, `motion_paths`, `CSF_paths`, `WM_paths`, optional `GS_paths`), all of equal length (a length mismatch is a `ConfigError`). `scan_paths`, `motion_paths`, `CSF_paths` and `WM_paths` are required inputs, checked after discovery. `run_labels` is optional and inferred from `run-N` when omitted; `run_lengths` is not accepted.

### `run_labels` and `run_lengths` constraints

- `run_labels`: non-empty list of unique non-negative integers.
- `run_lengths`: non-empty list of positive integers (task Mode B only).
- Inference from file names uses the BIDS entity `run-N` (pattern `(^|_)run-(\d+)(_|\.)`). A file without it, or duplicate inferred labels, raises `ConfigError`.

### Run sets

| Set | Definition |
|---|---|
| `K_supplied` | All runs supplied, in acquisition order. |
| `S_pre` | Supplied runs minus pre-model exclusions (task: too few uncensored TRs; rest: DOF < 1). |
| `K_model` | Number of runs in `S_pre`. |
| `S_final` | `S_pre` minus runs that fail during model estimation (rest only; task `S_final` = `S_pre`). |

Single-run naming: when exactly one run is supplied to a task analysis, per-run files carry no `run{N}` token (for example `{pre}_min_outlier_epi.nii.gz`); with more than one supplied run they carry `run{N}`. `rest_conn` per-run files always carry `run{N}`.

### Structural checks (before any processing)

- Every scan's header TR equals `global.tr` within 1e-4 s, otherwise `InputError` (fix the header with `3drefit -TR` or correct `tr`).
- Every run is on the same grid as the first run (`3dinfo -same_grid`), otherwise `InputError`.
- Motion and tissue files have exactly one row per volume (per run in Mode A and rest; total volumes in Mode B), otherwise `InputError`.
- Motion files have at least the number of columns the model uses (6 or 12 for task analyses, `6 * motion_deriv_degree` for rest), otherwise `InputError`.
- The motion columns used and the first column of every tissue file contain only finite values; `NaN` or `inf` raises `InputError` naming the first affected rows.

These checks run before any step executes and are also run by `--dry-run`.

---

## Analysis Block: Common Fields

| Key | Type | Required | Default | Description |
|---|---|---|---|---|
| `type` | str | yes | | `task_act`, `task_conn` or `rest_conn`. |
| `name` | str | no | (none) | Label used in log and error messages; messages fall back to `analyses[{index}]`. |
| `paths` | dict | yes, unless BIDS discovery is active | | Input file paths; keys depend on type and mode. |
| `out_dir` | str | yes | | Output directory; created during validation if absent. |
| `out_file_pre` | str | yes | | Prefix for every analysis output; a file-name-safe token. Must not collide with another block's prefixes in the same `out_dir`. |
| `average_type` | str | yes | | `"mean"` or `"median"`: the within-ROI statistic for every parcel-level output. |
| `fd_threshold` | float | yes | | Power et al. (2012) framewise displacement threshold in mm (50 mm sphere). A TR is censored when FD `>` `fd_threshold` (strict). Must be `> 0`. See [Censoring](#censoring-and-run-exclusion). |
| `censor_prev_tr` | bool | no | `false` | Also censor the TR immediately preceding each high-motion TR (within the same run). |
| `remove_previous` | bool | no | `false` | Before running, delete every file recorded in this analysis's ledger, its staging directories and the ledger itself. Files not recorded by the ledger are never touched. See [Stage Reuse](#stage-reuse-and-reruns). |
| `scale_to_psc` | bool | no | `true` | Scale each run to percent of its voxelwise temporal mean before modeling. See [Percent Signal Change Scaling](#percent-signal-change-scaling). |
| `roi_zero_handling` | str | no | `"exclude"` | `"exclude"`: zero-valued voxels are excluded from within-ROI averages (`3dROIstats -nzmean`/`-nzmedian`). `"include"`: all ROI voxels are averaged. |
| `run_labels` | list of int | conditional | | See [Run Model](#run-model-mode-a-mode-b-and-run-sets). |
| `smoothing` | dict | no | disabled | `{enabled: bool, fwhm: float}`. See [Spatial Smoothing](#spatial-smoothing). |
| `extraction` | dict or null | no | `null` | Type-specific parcel extraction settings. |
| `derivatives_dirs` | list of str or null | no | global value | Per-block BIDS discovery roots. |
| `subject`, `session`, `task` | str | `subject` and `task` in BIDS discovery mode | | BIDS entities (without `sub-`/`ses-`/`task-` prefixes) used only for discovery. In discovery mode they must be strings: quote numeric IDs (`subject: "01"`). |

---

## Analysis Block: `task_act`

First-level GLM with AFNI `3dDeconvolve` (`-polort A`, `-local_times`, `-TR_times`, `-concat` for multiple runs, `-censor`, motion and tissue `-ortvec`s, `-tout -fout -rout`).

### Required fields

| Key | Type | Description |
|---|---|---|
| `cond_labels` | list of str | Unique, file-name-safe condition names to model (quote numeric codes, e.g. `"1"`). Each must occur in the events data (Mode A: in at least one supplied run; Mode B: in the file). |
| `hrf_model` | str | `GAM`, `BLOCK`, `dmBLOCK`, `SPMG1` or `custom`. |
| `include_motion_derivs` | bool | `false`: first 6 motion columns; `true`: first 12 columns (6 parameters plus 6 temporal derivatives supplied in the file). |

Plus the common required fields and the Mode A or Mode B paths (scan, events, motion).

### Optional fields

| Key | Type | Default | Description |
|---|---|---|---|
| `custom_hrf` | str or null | `null` | AFNI model string, required when `hrf_model: custom`. Must equal one of `GAM`, `BLOCK`, `dmBLOCK`, `SPMG`, `TWOGAMpw`, `TENT`, `TENTzero`, `CSPLIN`, `CSPLINzero`, or start with one of them followed by `(` (for example `TENT(0,14,8)`), and must pass a `3dDeconvolve -nodata` dry run. |
| `use_tissue_derivs` | bool | `false` | Add the within-run first temporal derivative of each supplied tissue regressor (CSF, WM). |
| `contrasts` | dict or null | `null` | `{functions: [...], labels: [...]}`. |
| `extraction` | dict or null | `null` | See below. |
| CSF/WM paths | | `null` | Optional tissue regressors (Mode A lists or Mode B single files). |

### HRF models

| `hrf_model` | AFNI model string | Duration handling |
|---|---|---|
| `GAM` | `GAM(8.6,.547,d)` | `d` = mean event duration of that condition (1.0 s if none) |
| `BLOCK` | `BLOCK(d,1)` | `d` = mean event duration of that condition |
| `dmBLOCK` | `dmBLOCK(0)` | per-event duration via married timing (`onset*duration`, `-stim_times_AM1`) |
| `SPMG1` | `SPMG1` | durations ignored |
| `custom` | `custom_hrf` verbatim | as defined by the string; multi-column bases (e.g. `TENT`) are supported |

### Contrasts

```yaml
contrasts:
  functions:
    - "1*stimFear-1*stimNeu"
    - "0.5*stimFear+0.5*stimSad-1*stimNeu"
  labels:
    - "Fear-Neutral"
    - "Emotional-Neutral"
```

- Grammar (spaces ignored): `coef*COND[+|-coef*COND...]`; every term needs an explicit numeric coefficient (`stimA-stimB` is rejected). Condition names in contrasts must match `\w+` (letters, digits, underscore) and must be in `cond_labels`. A zero coefficient is accepted with a logged warning.
- `functions` and `labels` must be lists of strings of equal length; `functions` without `labels`, or `labels` without `functions`, is a `ConfigError`.
- Contrasts are parsed during config resolution, so grammar errors and unknown conditions are reported by validation and `--dry-run`.
- **Label integrity:** duplicate labels, and distinct labels that collide after filename sanitization (characters outside `[A-Za-z0-9_.-]` become `_`, repeats collapse, leading/trailing `_` stripped), raise `ConfigError`.
- Contrasts are passed as `-gltsym` with `-glt_label k` numbered 1..K in list order. A contrast that references a condition dropped by the survival floor is itself dropped (`CONTRAST_DROPPED`).
- The `-glt_label` number is an argument index, not a sub-brick index. Locate contrast outputs by label (see [Sub-brick Identifiers](#sub-brick-identifiers)).

### Extraction

```yaml
extraction:
  stat_buckets: ["Coef", "Tstat", "Fstat", "R^2", "Zstat"]   # or null
  extract_out_file_pre: "subj001_Shen368"
  extract_resids: false
  extract_raw_ptseries: false
```

| Key | Type | Default | Description |
|---|---|---|---|
| `stat_buckets` | list or null | `null` | Non-empty subset of `Coef`, `Tstat`, `Fstat`, `R^2`, `Zstat`. For each type: a multi-sub-brick NIfTI, an index JSON and a parcellated CSV. Requires `extract_out_file_pre`. |
| `extract_out_file_pre` | str | | File-name-safe prefix for extraction outputs. Required (`ConfigError` otherwise) when `stat_buckets`, `extract_resids` or `extract_raw_ptseries` is set. |
| `extract_resids` | bool | `false` | Parcellate the GLM residual time series into `{ext}_resids.csv`. |
| `extract_raw_ptseries` | bool | `false` | Parcellate the pre-regression series (unscaled, and also PSC-scaled when `scale_to_psc` is true). |

Every extraction feature requires `global.template_path` (`ConfigError` otherwise). For `Zstat`, each matching `Tstat` sub-brick is converted with `fitt_t2z(t, dof)` using that sub-brick's own DOF from `BRICK_STATAUX`. A stat type with no matching sub-brick is skipped with a log warning.

### Events not listed in `cond_labels`

Rows of conditions not listed in `cond_labels` are not modeled in `task_act`; their responses remain in the baseline and residuals. They are still subject to onset timing validation.

---

## Analysis Block: `task_conn`

Trial-level beta series with `3dDeconvolve -x1D_stop` (design matrix) and `3dLSS` (least-squares-separate estimation), then optional parcel extraction and connectivity.

### Required fields

| Key | Type | Description |
|---|---|---|
| `cond_beta_labels` | list of str | Unique, file-name-safe conditions whose trials receive individual betas. |
| `hrf_model` | str | As for `task_act`, with the restrictions below. |
| `include_motion_derivs` | bool | As for `task_act`. |

Plus the common required fields and the Mode A or Mode B paths.

### HRF restrictions

- `dmBLOCK`, or any custom string that requires married timing, is rejected (`3dLSS` requires `-stim_times_IM`).
- `custom_hrf` must produce exactly one design-matrix column per trial.
- Beta trials use one HRF whose duration (for `GAM`/`BLOCK`) is the mean duration over all beta trials.

### Nuisance conditions

Every condition present in the modeled runs' events that is not in `cond_beta_labels` is modeled as a separate nuisance regressor (`-stim_times`, its own mean duration). A nuisance condition that occurs only in runs excluded before modeling is not modeled (logged warning). Nuisance condition names come from the events files and name their onset files, so they must also be file-name-safe tokens (`InputError` otherwise).

### Beta ordering

Beta conditions are ordered by first appearance (run acquisition order, then onset). 3dLSS sub-bricks follow the beta onset file: for each modeled run, for each beta condition in that order, trials by onset. Each condition's beta-series file contains only its surviving trials, ordered by 3dLSS sub-brick index. Both mappings are written to index JSONs (see [Sub-brick Identifiers](#sub-brick-identifiers)).

### Optional fields

| Key | Type | Default | Description |
|---|---|---|---|
| `custom_hrf` | str or null | `null` | As for `task_act`, single-column only. |
| `use_tissue_derivs` | bool | `false` | Within-run first derivatives of the supplied CSF/WM regressors. |
| `extraction` | dict or null | `null` | See below. |
| `connectivity` | dict or null | `null` | See below. |

### Extraction

```yaml
extraction:
  extract_pbseries: true
  extract_out_file_pre: "subj001_Shen368"
  extract_raw_ptseries: false
```

- `extract_pbseries`: parcellate each surviving condition's beta series into `{ext}_pbseries_{cond}.csv`. Requires `extract_out_file_pre`.
- `extract_raw_ptseries`: as for `task_act`. Requires `extract_out_file_pre`.
- Both require `global.template_path`.

### Connectivity

```yaml
connectivity:
  calc_conn: "parcellated"        # "parcellated" | "seed_to_voxel" | null
  conn_out_file_pre: "subj001_Shen368"
  pcorr: false
  fishZ: true
  contrasts:
    functions: ["1*stimFear-1*stimNeu"]
    labels: ["Fear-Neutral"]
```

| Key | Type | Default | Description |
|---|---|---|---|
| `calc_conn` | str or null | `null` | `parcellated` (ROI-by-ROI matrix per condition) or `seed_to_voxel` (single-ROI seed map per condition). Requires `global.template_path`. |
| `conn_out_file_pre` | str | | File-name-safe prefix; required when `calc_conn` is set. |
| `pcorr` | bool | `false` | Partial correlation (`parcellated` only; `ConfigError` with `seed_to_voxel`). |
| `fishZ` | bool | `false` | Fisher Z (`atanh`) with `|r|` clipped at 0.999329. |
| `contrasts` | dict or null | `null` | Linear combinations of condition-level connectivity outputs; same grammar and label-integrity rules as `task_act` contrasts, over `cond_beta_labels`. |

Connectivity contrasts with `calc_conn: null` are a `ConfigError`. A contrast is computed only when every condition it references produced a connectivity output; otherwise it is skipped with a `CONTRAST_DROPPED` warning, and the QC `contrast_labels` list contains only the contrasts that produced outputs. Parcellated contrasts are element-wise weighted sums of the condition matrices (NaN propagates); seed-to-voxel contrasts use `3dcalc` and accept at most 26 inputs. Outputs use the sanitized contrast label in place of the condition name.

---

## Analysis Block: `rest_conn`

Per-run nuisance regression and bandpass filtering, then concatenation of residuals (`3dTcat`), optional parcel extraction and connectivity.

### Required fields

| Key | Type | Description |
|---|---|---|
| `bandpass` | list of 2 numbers | `[low, high]` Hz with `0 <= low < high`. |
| `motion_deriv_degree` | int `>= 1` | Number of motion column blocks used: `6 * motion_deriv_degree` columns (for example `2` = 6 parameters plus 6 first derivatives, supplied in the file). |

Plus the common required fields and `paths.scan_paths`, `paths.motion_paths`, `paths.CSF_paths`, `paths.WM_paths` (equal-length lists; CSF and WM are mandatory for `rest_conn`).

### Optional fields

| Key | Type | Default | Description |
|---|---|---|---|
| `paths.GS_paths` | list or null | `null` | Global-signal regressor per run; enables global signal regression. Absent: low-severity `GS_MISSING`. |
| `notch_filter_band` | list of 2 numbers or null | `null` | `[low, high]` Hz, `0 < low < high`. Applied (`3dTproject -stopband`) to the six motion parameters used to compute FD for censoring only; the motion regressors in the model are the unfiltered columns. |
| `use_tissue_derivs` | bool | `false` | Within-run first derivatives of CSF, WM and (when supplied) GS. |
| `use_sequenced_bandpass` | bool | `false` | Selects the sequenced backend (see below). |
| `keep_run_res_dtseries` | bool | `true` | Selects the residual mode (see below). |
| `extraction` | dict or null | `null` | `{extract_ptseries, extract_out_file_pre, extract_raw_ptseries}`. |
| `connectivity` | dict or null | `null` | `{calc_conn, conn_out_file_pre, pcorr, fishZ}` (no contrasts). |

### Regression backends

- **Simultaneous** (`use_sequenced_bandpass: false`, default): one `3dTproject` per run with `-censor` (`-cenmode ZERO`), motion, CSF, WM, optional GS and derivative `-ort`s, `-bandpass low high`, and `-polort P` where `P = 2` when `low > 0`, else `P = 1 + floor(n_vols * tr / 150)`.
- **Sequenced** (`use_sequenced_bandpass: true`): censored TRs are NTRP-interpolated (`3dTproject -cenmode NTRP -polort -1`), the BOLD series and every nuisance regressor are filtered at the same passband (`3dBandpass`, default quadratic detrend), regressed without `-bandpass` (`-polort -1`), and censored TRs are re-zeroed. This follows Power et al. (2014) and Hallquist et al. (2013), as benchmarked in Ciric et al. (2017), with linear NTRP rather than spectral interpolation. DOF is the passband dimension rather than the frame count minus stopband regressors.

### Residual modes (`keep_run_res_dtseries`)

| | `true` (default) | `false` |
|---|---|---|
| Stages | `rest-conn-residuals-run{N}` per `S_pre` run, then `rest-conn-concat` | single `rest-conn-residuals-concat` stage |
| Per-run residuals | `{pre}_run{N}_residual_dtseries.nii.gz` kept as final outputs | never written to `out_dir` |
| Per-run prepared tissue regressors | `{pre}_run{N}_{tissue}_prepared.1D` (written by the always-run nuisance step) | same |
| Per-run tissue derivatives | `{pre}_run{N}_{tissue}_deriv.1D` kept as intermediates | kept in staging only |
| Sequenced intermediates | `{out_dir}/{out_file_pre}_sequenced_intermediates/run{N}/` (`bold_interp.nii.gz`, `bold_bp.nii.gz`, `regressed.nii.gz`), ledgered as intermediates | kept in staging only |

In both modes, a run whose regression fails (`ToolExecutionError`) is recorded under `failed_runs`, listed in `excluded_runs` with reason `run_failed`, emits the `RUN_FAILED` warning, and is left out of the concatenation; if every run fails, the analysis fails. A failed stage promotes nothing.

### Extraction and connectivity

- `extract_ptseries`: parcellate the concatenated (unsmoothed) residual into `{ext}_residual_ptseries.csv`.
- `extract_raw_ptseries`: parcellate each `S_final` run's source scan (and its PSC-scaled series when `scale_to_psc` is true).
- Connectivity is computed once on the concatenated residual. A rank-deficient partial correlation or a null seed raises `ModelError`.

---

## Spatial Smoothing

Applies to all three types.

```yaml
smoothing:
  enabled: true
  fwhm: 6          # mm; > 0, finite, at most two decimal places
```

- `fwhm` is required when `enabled` is true and must not be a boolean.
- Smoothing uses `3dBlurToFWHM -ACF -FWHM fwhm` within a data-derived mask: the intersection of non-constant voxels (max != min) across the relevant runs. Automask is never used.
- **task_act / task_conn:** each `S_pre` run's unscaled series is blurred, then PSC-scaled when `scale_to_psc` is true, then concatenated when more than one run was supplied. The smoothed model input feeds a second model (`task-act-glm-smooth` with the same contrasts, or `task-conn-beta-series-smooth`). Input and output ACF FWHM are measured with `3dFWHMx -detrend`.
- **rest_conn:** each run segment of the concatenated residual is blurred and the smoothed runs are re-concatenated. ACF FWHM is measured without detrending. Smoothed per-run residuals are final outputs when `keep_run_res_dtseries` is true, intermediates otherwise.
- **Never smoothed:** every parcel-level output (stat parcellations, residual and raw ptseries, pbseries, parcellated connectivity). Seed-to-voxel smoothed siblings use the unsmoothed seed time series and the smoothed target.
- Smoothed outputs are siblings of the unsmoothed outputs with the token `_s{N}mm` inserted before the extension, where `N` is the canonical FWHM with `.` written as `p`: `6` gives `_s6mm`, `4.5` gives `_s4p5mm`, `2.25` gives `_s2p25mm`.
- QC: `smoothing_per_run` records; warnings `SMOOTH_FWHM_OFF_TARGET` (achieved FWHM more than 10% from target) and `SMOOTH_INPUT_ABOVE_TARGET` (input FWHM already above target).

---

## Input File Formats

### Scan File

- NIfTI (`.nii` or `.nii.gz`), 4D, preprocessed BOLD in a standard space.
- Assumed brain-masked (non-brain voxels zero or constant); ROI QC and masks rely on this.
- Header TR must equal `global.tr`. All runs must share one grid.
- Task Mode A and `rest_conn`: one file per run. Task Mode B: one file holding all runs back to back, described by `run_lengths`.
- Scans enter stage hashes by path, not content (see [Stage Reuse](#stage-reuse-and-reruns)).

### Task Timing (Events) File

Two column schemes, each tab- or comma-delimited, detected from the header (not the extension):

| Scheme | Columns (case-insensitive) |
|---|---|
| BIDS | `onset`, `duration`, `trial_type` |
| CONDITION | `CONDITION`, `ONSET`, `DURATION` (`CONDITION` is mapped to `trial_type`) |

- The header is parsed with both delimiters; exactly one delimiter must yield a recognized header. Recognized under both or neither delimiter raises `InputError` listing the columns found under each. Within one delimiter, BIDS takes precedence if both schemes appear.
- Only onset, duration and condition are read; every other column (including an `AMP` column) is ignored. `dmBLOCK` uses married `onset*duration`, not amplitudes.
- `onset` and `duration` must be finite numbers in every row. BIDS `n/a`, empty cells and infinite values raise `InputError` naming the column and rows; nothing is imputed. Negative durations raise `InputError`. Use `0` duration for impulse events.
- `trial_type` (or `CONDITION`) values are read as strings in both input modes, so a numeric code such as `1` matches the condition label `"1"`.
- **Onset reference:** Mode A onsets are seconds from the start of their run. Mode B onsets are seconds from the start of the concatenated series; each event is assigned to the run containing volume `floor(onset / tr)` and converted to run-local time.
- **Onset validation:** every row (including conditions not modeled) is checked. A negative onset, or an onset at or after the run end (Mode A: `n_vols * tr` of that run; Mode B: total duration), is a violation. Any violation writes `{pre}_timing_errors.json` (final output) and raises `InputError`.
- **Required conditions:** Mode A requires each modeled label to occur in at least one supplied run (union of valid events across runs). Mode B requires each to occur in the file.
- Trials must be unique per (run, condition, onset): duplicate rows raise `InputError` listing up to ten duplicates (context `duplicates`).
- Rows are ordered internally by onset; input order does not matter.
- Condition labels appear verbatim in output file names (onset files, beta series), which is why they must be file-name-safe tokens.

`{pre}_timing_errors.json` schema: `{analysis_type, input_mode, tr, violations: [{events_file, run, run_null_reason, condition, onset_s, violation}], runs: [{run, events_file, n_vols, run_end_s, n_onsets, min_onset_s, max_onset_s, n_negative, n_at_or_after_run_end}]}`. `violation` is `negative` or `at_or_after_run_end`; in Mode B, out-of-series events have `run: null` and `run_null_reason: "outside_concatenated_series"`.

### Motion Regressor File

- Plain text, whitespace-delimited, numeric, **no header**, one row per volume.
- **Column contract:** the first six columns are `[tx, ty, tz, rx, ry, rz]`: translations in **mm**, rotations in **degrees**. FD is computed from these six columns.
  - AFNI `3dvolreg -1Dfile`/`-dfile` output (roll, pitch, yaw, dS, dL, dP) is rotations-first and must be reordered translations-first; otherwise FD is biased by roughly -13% to +15%.
  - fMRIPrep confounds (rotations in radians, with a header) must be converted to degrees and written headerless.
- Columns used as regressors: `task_*` 6 or 12 (`include_motion_derivs`); `rest_conn` `6 * motion_deriv_degree`. Fewer columns raise `InputError`; extra columns are ignored. The columns used must contain only finite values (`NaN`/`inf` raise `InputError`).
- Derivative columns (columns 7 onward) must be supplied in the file and computed within run. In Mode B with `include_motion_derivs`, derivative values that appear to span run boundaries emit the `DERIV_RUN_BOUNDARY` warning (medium).
- The model receives a prepared copy (tab-delimited, 8 decimals): `{pre}_concat_motion_prepared.1D` (task, `S_pre` rows) or `{pre}_run{N}_motion_prepared.1D` (rest).

### Tissue Regressor Files (CSF, WM, GS)

- Plain text, no header, one row per volume; only the first column is used, for every analysis type, and it must contain only finite values.
- `task_*`: CSF and WM optional; prepared copies `{pre}_concat_{tissue}_prepared.1D` cover `S_pre` rows. `rest_conn`: CSF and WM required, GS optional; per-run prepared single-column copies `{pre}_run{N}_{tissue}_prepared.1D` are the regressors (and the content-hashed stage inputs).
- With `use_tissue_derivs`, the within-run first difference (first TR of each run set to 0) is added: `{pre}_concat_{tissue}_deriv.1D` (task) or `{pre}_run{N}_{tissue}_deriv.1D` (rest).

### ROI Template File

- NIfTI with integer ROI labels; its maximum value (`3dinfo -dmax`) must be a positive integer.
- `parcellated` connectivity requires at least two ROIs; `seed_to_voxel` requires a single-ROI mask (maximum label 1). Violations raise `ConfigError`.
- Atlas space (`3dinfo -space`) must match the scan's, otherwise `InputError` unless `force_diff_atlas: true`.
- When the template grid differs from the scan grid, it is resampled with `3dresample -rmode NN -master <first scan>` to `{pre}_{template_stem}_resampled.nii.gz`.
- Parcel CSV columns are `ROI_{label}` in ascending label order.

### Tools Lockfile (packaged)

`fmri_first_level_proc/tools.lock.yaml` ships inside the package (always present after `pip install`):

```yaml
lockfile_version: "2.0.0"
tools:
  afni:   {minimum: "26.0.09", validated: "26.0.09"}
  python: {minimum: "3.12",    validated: "3.14"}
  numpy:  {minimum: "2.4.2",   validated: "2.4.2"}
  pandas: {minimum: "3.0.1",   validated: "3.0.1"}
```

See [Runtime Validation](#runtime-validation) for the policy. It is not a user input; a missing or malformed lockfile raises `ToolUnavailableError`.

---

## Censoring and Run Exclusion

**Metric.** Power et al. (2012) framewise displacement on a 50 mm sphere: `FD_t = sum_i |d_i(t)|` over the six parameters, where `d(t)` is the backward difference and rotations are converted to mm as `degrees * pi/180 * 50`. FD is 0 at each run's first TR. A TR is censored when `FD > fd_threshold`. With `censor_prev_tr`, the preceding TR within the same run is also censored.

AFNI enorm (Euclidean norm of the backward difference, rotations unweighted in degrees) is computed for reference only and never drives censoring. For translating thresholds, `0.873 x enorm <= FD <= 2.30 x enorm`; the two metrics are not interchangeable.

**rest_conn notch filter.** When `notch_filter_band` is set, FD is computed from the notch-filtered six parameters.

**Censor files.** Binary single-column text (`1` keep, `0` censor), one row per model volume: `{pre}_concat_censor.1D` (task, over `S_pre`) or `{pre}_run{N}_censor.1D` (rest). Side files: `_fd.1D` (FD series) and `_enorm.1D` (enorm series) with the same prefix.

**Task run exclusion.** All supplied runs are first censored together. A run is excluded (`RUN_INSUFFICIENT_TRS`, reason `insufficient_uncensored_trs`) when its uncensored TR count is `<= p + 1`, with `p = 1 + floor(max_run_duration_s / 150)`. Censoring is then recomputed over `S_pre`. If no run remains, `ModelError`.

**Rest run exclusion.** Each run's DOF is computed by a dry run (see [Degrees of Freedom](#degrees-of-freedom)); a run with DOF `< 1` is excluded (`RUN_SKIPPED`, reason `dof_below_1`) and the remaining runs proceed. If every run is excluded, `ModelError`.

**High censoring.** `CENSOR_HIGH` (high severity) when more than 50% of the model runs' TRs are censored (strictly greater).

---

## Trial Estimability and Condition Floors

A `3dDeconvolve -nodata` dry run with `-stim_times_IM` gives each trial its own regressor (m basis columns per trial for multi-column HRFs). Trial j's estimability is the pooled energy ratio

`f_j = sum over its m columns and uncensored TRs of x^2 / sum over its m columns and all TRs of x^2`

(identical to the single-column ratio when m = 1). A trial survives when `f_j > 0`. Non-surviving reasons: `fully_censored`, `no_in_run_support` (all-zero columns), `run_excluded` (run not in `S_pre`). The column order is checked at runtime against onset-file order (`GuardError` on mismatch).

| Analysis | Minimum surviving trials per condition |
|---|---|
| `task_act` | 2 |
| `task_conn` | 3 (minimum for a non-degenerate beta-series correlation) |

A condition below its floor is dropped (`COND_DROPPED`), and so is every contrast that references it (`CONTRAST_DROPPED`). If no condition remains, `ModelError`. Per-trial and per-condition records are written to the QC summary.

---

## Degrees of Freedom

| Analysis | Definition | Failure |
|---|---|---|
| `task_act` | Preflight `3dDeconvolve -nodata -censor` design matrix with the final regressors: rows minus columns. | DOF `< 1`: `ModelError` |
| `task_conn` | Design matrix rows minus (non-IM columns + 2). | DOF `< 1`: `ModelError` |
| `rest_conn` simultaneous | Per-run `3dTproject` dry run on a surrogate series with the real censor file, regressors, polort and bandpass; DOF parsed from `D.O.F. left`, or reconstructed as retained points minus fixed regressors when 3dTproject aborts with "too many fixed regressors". | DOF `< 1`: run excluded |
| `rest_conn` sequenced | `min(passband_dim, n_uncensored) - n_orts`, with the passband dimension parsed from `3dBandpass` (nFFT and passband indexes). | DOF `< 1`: run excluded |

When censoring leaves fewer frames than `3dTproject`'s minimum, the simultaneous dry run aborts ("only N points left after censoring"). The run is then excluded as `dof_below_1` with a reconstructed DOF of `n_uncensored - n_orts - (polort + 1)`. This value is an upper bound on the true DOF because the stopband-regressor count is not reported; the record carries `n_stopband_regressors: null` with `n_stopband_regressors_null_reason: "dry_run_aborted_censoring"`.

---

## Percent Signal Change Scaling

When `scale_to_psc` is true, each run is scaled independently:

`psc = min(200, x / mean_t(x) * 100)` voxelwise, set to 0 where `x <= 0` or the temporal mean `<= 0`.

The scaled series are near 100 (percent of each voxel's own run mean), not centered at 0. A run in which 25% or more of non-constant voxels have a temporal mean `<= 0` (demeaned input) raises `InputError`; use `scale_to_psc: false` for demeaned data. Per-run counts of guarded voxels (min or mean `<= 0`), capped voxels (max above twice the mean) and non-positive-mean voxels are recorded in `psc_per_run`.

---

## Parcel Extraction and ROI QC

- Parcel values come from `3dROIstats` over the (possibly resampled) template, using `average_type` and `roi_zero_handling`.
- CSV layout: columns `ROI_{label}` (ascending label), one row per volume or sub-brick. Raw ptseries, residual ptseries and pbseries CSVs have no index column. `{ext}_resids.csv` has a leading unnamed 0-based row-index column. Stat parcellation CSVs have an index column `condition` holding the sub-brick key (see [Sub-brick Identifiers](#sub-brick-identifiers)).
- **ROI QC** (when a template is used): for each model run and ROI, `roi_coverage.nonzero_fraction` is the fraction of the ROI's template voxels whose model-input series is not identically zero. `low_baseline.low_baseline_fraction` is the fraction of the ROI's non-constant voxels whose temporal mean is below 0.2 x the brain-mask median (median over non-constant voxels of the mean volume). `median_baseline_ratio` is the ROI's median masked mean divided by that brain-mask median. Null reasons: `nonpositive_baseline` (25% or more of masked voxels with mean `<= 0`, or brain-mask median `<= 0`) and `no_masked_voxels`.

---

## Functional Connectivity

### Parcellated

1. Parcel time series via `3dROIstats` (respecting `average_type`, `roi_zero_handling`).
2. ROIs with zero variance are null: their rows and columns are `NaN` (`NULL_ROI`, `null_rois` record). If every ROI is null, `ToolExecutionError`.
3. Pearson correlation via `1ddot -dem` on the non-null ROIs.
4. `pcorr`: partial correlation from the inverse correlation matrix (`-inv_ij / sqrt(inv_ii * inv_jj)`, diagonal 1), gated by a rank check on the demeaned series. A rank-deficient case is skipped for that condition (`PCORR_RANK_DEFICIENT`) in `task_conn`, and raises `ModelError` in `rest_conn`.
5. `fishZ`: `atanh(clip(r, -0.999329, 0.999329))`.
6. Output: tab-delimited text, no header, values with 8 decimals or `NaN`, rows and columns in ascending ROI label order.

`1ddot` prints five decimals, so r carries rounding error of about 0.5 x 10^-5, partial correlation at most about 10^-5, and Fisher Z at most the input bound divided by `1 - 0.999329^2` at the clip. These are far below the sampling error of r at typical first-level series lengths.

### Seed-to-voxel

The seed series is the single ROI's average (via `3dROIstats`). A zero-variance seed is null (`SEED_NULL`; `task_conn`: the condition is skipped and recorded in `null_seed_conditions`; `rest_conn`: `ModelError`). The map is `3dTcorr1D -pearson` against every voxel; zero-variance target voxels are set to 0 and counted (`zero_variance_target_voxels`); `fishZ` applies the clipped `atanh`.

If no `task_conn` condition yields an output, `ModelError`.

### Output names

`{conn_pre}[_{condition}]{suffix}`, where `condition` is the condition (task_conn) or the sanitized contrast label, and is absent for `rest_conn`:

| `calc_conn` | `pcorr` | `fishZ` | Suffix |
|---|---|---|---|
| parcellated | false | false | `_corr_mat.txt` |
| parcellated | false | true | `_fishZ_mat.txt` |
| parcellated | true | false | `_pcorr_mat.txt` |
| parcellated | true | true | `_pcorr_fishZ_mat.txt` |
| seed_to_voxel | (not allowed) | false | `_corr.nii.gz` |
| seed_to_voxel | (not allowed) | true | `_fishZ.nii.gz` |

---

## BIDS Input Discovery

**BIDS discovery mode** is active when `derivatives_dirs` is set (global or per block) and the block has a `subject` key. Without `subject`, discovery is skipped with a logged warning and every input must be given under `paths`. Blocks without `derivatives_dirs` are not affected by any rule in this section.

In discovery mode:
- `task` is required (`ConfigError` otherwise), and `subject`, `session` and `task` must be strings (`ConfigError` suggesting quoting, e.g. `subject: "01"`, since YAML reads `01` as the integer 1).
- Searched directory: `{deriv}/sub-{subject}[/ses-{session}]/func/`.
- Matching is by exact BIDS entities: files `sub-{subject}_*_{suffix}{ext}` whose `sub` entity equals `subject`, whose `task` entity equals `task` (`task-rest` does not match `task-restpre`) and, for slots with a `desc`, whose `desc` entity equals it.
- Directories are searched in list order; the first that yields matches wins for each slot. Matches in a later directory emit the `DISCOVERY_COLLISION` warning (medium), whether or not a logger is passed.
- Explicit paths always take precedence over discovered ones, slot by slot.
- Discovered files are ordered by their `run-N` entity. Mixing labeled and unlabeled files, duplicate labels, or more than one unlabeled file raises `InputError`.
- **Run alignment.** Every discovered per-run slot is aligned to the analysis run labels (explicit `run_labels`, or the `run-N` entities of the scans): its set of run labels must equal the analysis runs, otherwise `InputError` names the slot, the missing runs and the extra runs. Files are then ordered by run label, never paired by position. A single unlabeled discovered file is accepted only for a one-run analysis.
- **Required inputs** still unresolved after discovery raise `InputError` naming the slots and the directories searched.
- Task discovery fills the Mode A (plural) slots. `template_path` is never discovered.

| Slot | `desc` | suffix | extension | Types |
|---|---|---|---|---|
| `scan_paths` | `preproc` | `bold` | `.nii.gz` | all |
| `motion_paths` | `confounds` | `regressors` | `.tsv` | all |
| `CSF_paths` | `CSF` | `timeseries` | `.1D` | all (required for rest) |
| `WM_paths` | `WM` | `timeseries` | `.1D` | all (required for rest) |
| `task_timing_paths` | | `events` | `.tsv` | `task_act`, `task_conn` |
| `GS_paths` | `GS` | `timeseries` | `.1D` | `rest_conn` |

A discovered motion file must satisfy the [Motion Regressor File](#motion-regressor-file) contract (headerless, translations first, degrees); a headered file fails to parse (`InputError`).

---

## Output Files

### Conventions

- Every package-created path in `out_dir` starts with one of the analysis prefixes: `out_file_pre` (`{pre}`), `extract_out_file_pre` (`{ext}`) or `conn_out_file_pre` (`{conn_pre}`). The only exceptions are staging directories `.staging_{pre}_{stage}`, which exist only while a stage runs or after it fails.
- Files are classified **final** (products) or **intermediate** (needed for reuse, provenance or QC). `FirstLevelResult.output_files` and `.intermediate_files` list them separately.
- **Frozen primary outputs** (stable names, never retired): `task_act` `{pre}_concat_bucket_stats.nii.gz`, `task_conn` `{pre}_concat_LSS.nii.gz`, `rest_conn` `{pre}_concat_residual_dtseries.nii.gz`.
- `{N}` is the integer run label; `{tok}` is the smoothing token (`_s{N}mm`), present only on smoothed siblings.

### Common to all types

| File | Class | Notes |
|---|---|---|
| `{pre}_qc_summary.json` | final | See [QC Summary JSON](#qc-summary-json). |
| `{pre}_ledger.jsonl` | intermediate | Stage ledger (format 2). |
| `{pre}_timing_errors.json` | final | Task only; written only when onset validation fails. |
| `{pre}[_run{N}]_min_outlier_epi.nii.gz` | final | One per `S_final` run: the volume with the lowest `3dToutcount -automask -fraction`. |
| `{pre}[_run{N}]_mean.nii.gz`, `{pre}[_run{N}]_psc.nii.gz` | intermediate | With `scale_to_psc`. |
| `{pre}_{template_stem}_resampled.nii.gz` | intermediate | When the template grid differs from the scan grid. |
| `{pre}_smoothing_mask.nii.gz` | intermediate | With smoothing. |
| `{pre}_{stage}.REML_cmd` | intermediate | REML command files written by `3dDeconvolve`, renamed with the stage label. |
| censor, `_fd.1D`, `_enorm.1D`, motion prepared, tissue prepared/derivative | intermediate | See [Input File Formats](#input-file-formats) and [Censoring](#censoring-and-run-exclusion). |

### `task_act`

| File | Class |
|---|---|
| `{pre}_concat_bucket_stats{tok}.nii.gz` (frozen when unsmoothed) | final |
| `{pre}_concat_bucket_resids{tok}.nii.gz` | final |
| `{pre}_concat_bucket_stats_index{tok}.json` | final |
| `{ext}_{stat}_bucket{tok}.nii.gz`, `{ext}_{stat}_index{tok}.json` | final |
| `{ext}_{stat}_parcellated.csv` (unsmoothed only) | final |
| `{ext}_resids.csv` | final |
| `{ext}_raw_ptseries.csv`, `{ext}_raw_psc_ptseries.csv` (with `scale_to_psc`) | final |
| `{pre}_concat_{cond}_onsets.txt` | intermediate |
| `{pre}_preflight_dmat.x1D`, `{pre}_estimability_dmat.x1D` | intermediate |
| `{pre}_psc.nii.gz` (multi-run concatenated PSC), `{pre}_concat_scan.nii.gz` (Mode A, multi-run), `{pre}_run_intersect_mask.nii.gz` (`K_model > 1`) | intermediate |
| `{pre}[_run{N}]_blur{tok}.nii.gz`, smoothed PSC and concatenated model inputs | intermediate |

### `task_conn`

| File | Class |
|---|---|
| `{pre}_concat_LSS{tok}.nii.gz` (frozen when unsmoothed) | final |
| `{pre}_concat_LSS.1d` (`3dLSS -save1D`) | final |
| `{pre}_concat_bseries_dmat.x1D` (LSS design matrix) | final |
| `{pre}_concat_LSS_index{tok}.json` | final |
| `{pre}_concat_bseries_{cond}{tok}.nii.gz`, `{pre}_concat_bseries_{cond}_index{tok}.json` | final |
| `{ext}_pbseries_{cond}.csv` | final |
| `{ext}_raw_ptseries.csv`, `{ext}_raw_psc_ptseries.csv` | final |
| Connectivity matrices or maps per condition and contrast (seed maps also `{tok}`) | final |
| `{pre}_concat_{cond}_onsets.txt` (nuisance conditions), `{pre}_concat_beta_onsets.txt` | intermediate |
| `{pre}_estimability_dmat.x1D`, model-input intermediates as for `task_act` | intermediate |

### `rest_conn`

| File | Class |
|---|---|
| `{pre}_concat_residual_dtseries{tok}.nii.gz` (frozen when unsmoothed) | final |
| `{pre}_run{N}_residual_dtseries{tok}.nii.gz` | final when `keep_run_res_dtseries` is true (smoothed siblings intermediate otherwise; unsmoothed per-run residuals not written otherwise) |
| `{ext}_residual_ptseries.csv` | final |
| `{ext}_run{N}_raw_ptseries.csv`, `{ext}_run{N}_raw_psc_ptseries.csv` | final |
| `{conn_pre}{suffix}` (seed map also `{tok}`) | final |
| `{pre}_run{N}_notch_motion.1D` (with notch filter), per-run censor/side/motion files, `{pre}_run{N}_{tissue}_prepared.1D` | intermediate |
| `{pre}_sequenced_intermediates/run{N}/` (sequenced backend, per-run mode) | intermediate |

---

## Sub-brick Identifiers

Every multi-volume statistical output has an identifier file. Never assume that a sub-brick index equals a regressor or contrast position, or the `-glt_label` number; always resolve by key.

### `task_act`

- **`{pre}_concat_bucket_stats_index{tok}.json`**: object mapping every sub-brick label of the bucket (exactly as `3dinfo -label` reports it) to its 0-based index. This is the authoritative list of what AFNI wrote, for example `Full_Fstat`, `Full_R^2`, `stimA#0_Coef`, `stimA#0_Tstat`, `stimA_Fstat`, `stimA_R^2`, `Fear-Neutral_GLT#0_Coef`. Multi-basis HRFs produce one `#k` sub-brick per basis function.
- **`{ext}_{stat}_index{tok}.json`**: object mapping each extracted sub-brick's key to its 0-based position in `{ext}_{stat}_bucket{tok}.nii.gz`. The key is the exact bucket label; a label belongs to stat type `S` when it ends with `_S`. `Fstat` includes `Full_Fstat` and `R^2` includes `Full_R^2`. For `Zstat`, the key is the matching `Tstat` label with the trailing `Tstat` replaced by `Zstat` (for example `stimA#0_Zstat`).
- **`{ext}_{stat}_parcellated.csv`**: one row per extracted sub-brick in bucket order; index column `condition` holds the same key.

### `task_conn`

- **`{pre}_concat_LSS_index{tok}.json`**: list with one record per 3dLSS sub-brick, in sub-brick order: `{lss_index, condition, run, onset, survived, beta_series_position}`. `onset` is run-local seconds. `beta_series_position` is null for non-surviving trials.
- **`{pre}_concat_bseries_{cond}_index{tok}.json`**: list with one record per sub-brick of that condition's beta series: `{beta_series_position, lss_index, run, onset}`. `beta_series_position` k is sub-brick k.
- **`{ext}_pbseries_{cond}.csv`**: row k corresponds to beta-series sub-brick k.
- The QC `trials` records carry the same `lss_index` and `beta_series_position` fields.

---

## QC Summary JSON

`{pre}_qc_summary.json` merges fragments from each step and stage, in the key order below. Record lists are sorted by their identity fields. `NaN` is never written (null is used instead).

**Run status.** Every summary carries `run_status`:
- After a successful run: the full summary with `run_status: {status: "success" | "warning", error: null}` (`"warning"` when a high-severity warning was raised, matching `FirstLevelResult.status`).
- After a failed run (any exception once `out_dir` and `out_file_pre` are valid): a summary containing only `analysis_type`, `run_status` and, when the runtime check had completed, `provenance`, with `run_status: {status: "failed", error: {type, message, exit_code, step}}`. `type` is the exception class, `exit_code` the CLI code for it and `step` the step or stage that was running (for example `task-act-run-sets`, `task-act-glm`, `config-validation`), or null. No partial QC metrics are written, and the failed run replaces any earlier summary. The exception is still raised (the Python API is unchanged).
- A block whose `out_dir` or `out_file_pre` is itself invalid cannot record its failure; it is reported only in the log and the exit code.

| Key | Types | Kind (identity) | Content |
|---|---|---|---|
| `analysis_type` | all | value | `task_act`, `task_conn` or `rest_conn` |
| `run_status` | all | value | `{status, error}`; see above |
| `hrf_model` | task | value | Model name, or `"custom (STRING)"` |
| `fd_threshold` | all | value | Threshold used (mm, Power FD) |
| `censor_prev_tr` | all | value | bool |
| `censor_metric` | all | value | `"power_fd"` |
| `fd_radius_mm` | all | value | `50` |
| `bandpass` | rest | value | `[low, high]` |
| `bandpass_backend` | rest | value | `"simultaneous"` or `"sequenced"` |
| `contrast_labels` | task_conn | value | Connectivity contrast labels that produced outputs (absent when none) |
| `n_trs_total`, `n_trs_censored`, `pct_censored` | all | value | Totals over the model runs (`S_pre`) |
| `fd_summary`, `enorm_summary` | all | value | `{mean, median, max}` over `S_pre` TRs (4 decimals) |
| `per_run_censoring` | rest | records (`run`) | Every supplied run: `{run, n_trs_total, n_trs_censored, pct_censored, fd_mean, fd_max, enorm_mean, enorm_max}` |
| `per_run_dof` | rest | records (`run`) | Every supplied run: `{run, dof, bandpass_dim, bandpass_dim_null_reason, n_stopband_regressors, n_stopband_regressors_null_reason}`; null reasons `simultaneous_backend`, `sequenced_backend`, `dry_run_aborted_censoring` |
| `dof` | task | value | See [Degrees of Freedom](#degrees-of-freedom) |
| `trials` | task | records (`run`, `condition`, `onset`) | `{run, condition, onset, estimability, survived, reason, beta_series_position}` plus `lss_index` for task_conn |
| `per_condition_trial_counts`, `per_condition_surviving_trials` | task | value | `{condition: count}` |
| `per_condition_run_counts` | task | records (`run`, `condition`) | `{run, condition, n_trials, n_surviving}` |
| `excluded_runs` | all | records (`run`) | `{run, reason}`; reasons `insufficient_uncensored_trs`, `dof_below_1`, `run_failed` |
| `failed_runs` | rest | records (`run`) | `{run, error}` |
| `psc_per_run` | all | records (`run`) | `{run, n_mask_voxels, n_guarded_voxels, pct_guarded_voxels, n_capped_voxels, pct_capped_voxels, n_nonpositive_mean_voxels, pct_nonpositive_mean_voxels}` |
| `smoothing_per_run` | all | records (`run`) | `{run, fwhm_target_mm, acf_fwhm_input_mm, acf_fwhm_output_mm, mask_n_voxels, mask_fov_fraction}` |
| `pcorr_rank_checks` | task_conn, rest | records (`condition`) | `{condition, n_rois, rank, n_timepoints, skipped}` (`condition` is `"rest"` for rest_conn) |
| `null_rois` | task_conn, rest | records (`condition`, `output`) | `{condition, output, rois}` |
| `null_seed_conditions` | task_conn | records (`condition`) | `{condition}` |
| `zero_variance_target_voxels` | task_conn, rest | records (`output`) | `{output, n_voxels}` |
| `roi_coverage` | all | records (`run`, `roi`) | `{run, roi, n_voxels, nonzero_fraction}` |
| `low_baseline` | all | records (`run`, `roi`) | `{run, roi, low_baseline_fraction, median_baseline_ratio, low_baseline_null_reason}` |
| `reused_stages` | all | value | Labels of ledgered stages reused in this invocation |
| `retired_outputs` | all | value | Paths deleted by the retirement sweep in this invocation |
| `provenance` | all | value | `{package_version, afni_version, python_version, numpy_version, pandas_version}` |

**Scope notes (rest_conn).** `n_trs_total`, `n_trs_censored`, `pct_censored`, `fd_summary` and `enorm_summary` cover the runs entering regression (`S_pre`, i.e. not excluded for `dof_below_1`). Runs that later fail regression remain in these totals and are listed under `failed_runs`. `per_run_censoring` and `per_run_dof` cover every supplied run. Task totals and summaries likewise cover `S_pre`.

---

## Warning Codes

Warnings are graded records `{severity, code, message, user_facing}` from a closed table. `user_facing` warnings are logged at WARNING level; the others at INFO level, which reaches the console handler and, with `--log-file`, the log file. Any high-severity warning sets `FirstLevelResult.status` to `"warning"` and the CLI exit code to 3.

| Code | Severity | Meaning |
|---|---|---|
| `CENSOR_HIGH` | high | More than 50% of model-run TRs censored. |
| `RUN_INSUFFICIENT_TRS` | high | Task run excluded: too few uncensored TRs. |
| `RUN_SKIPPED` | high | Rest run excluded: DOF < 1. |
| `RUN_FAILED` | high | Rest run regression failed; run left out of the concatenation. |
| `NULL_ROI` | high | Zero-variance ROI(s) in a parcellated matrix (NaN rows and columns). |
| `SEED_NULL` | high | Zero-variance seed series. |
| `PCORR_RANK_DEFICIENT` | high | Partial correlation skipped: rank below the ROI count. |
| `RETIREMENT_FAILED` | high | An obsolete output could not be deleted (retried next run). |
| `COND_DROPPED` | medium | Condition below its surviving-trial floor. |
| `CONTRAST_DROPPED` | medium | Contrast references a condition dropped by the survival floor, or (task_conn connectivity) a condition that produced no connectivity output. |
| `DISCOVERY_COLLISION` | medium | A discovery slot matched in more than one derivatives directory. |
| `UNVALIDATED_VERSION` | medium | Installed AFNI/Python/numpy/pandas differs from the validated version. |
| `LEDGER_ENTRY_UNREADABLE` | medium | Unreadable ledger lines; affected stages rerun. |
| `DERIV_RUN_BOUNDARY` | medium | Mode B motion derivative columns appear to span run boundaries. |
| `SMOOTH_FWHM_OFF_TARGET` | medium | Achieved FWHM more than 10% from target. |
| `SMOOTH_INPUT_ABOVE_TARGET` | medium | Input FWHM already above target. |
| `GS_MISSING` | low | `rest_conn` without `GS_paths` (not user-facing). |

API: `get_warnings()` returns a copy of the accumulated records, `clear_warnings()` empties the accumulator (each pipeline `run()` clears it at entry).

---

## Stage Reuse and Reruns

Each analysis keeps an append-only ledger `{pre}_ledger.jsonl` (format 2) with **staged** records (outputs about to be promoted), **completion** records (stage hash, outputs, QC fragment, warnings, versions, wall-clock time) and **retired** records.

**Execution.** Every step or stage writes into `.staging_{pre}_{label}`. Its outputs are validated (existence, readable NIfTI, grid match, volume counts, row/column counts, exact text for Python-written files) and promoted to `out_dir` with an atomic rename. On failure the exception propagates, nothing from that stage is promoted, and the staging directory is left for inspection.

**Always-run steps** (events, nuisance, onsets, estimability, preflight) execute on every invocation and regenerate their intermediate files (censor, motion, onset files).

**Ledgered stages** (template, prep, model, extraction, smoothing, connectivity, ROI QC) are reused unless one of five triggers holds:

1. no valid completion record exists for the stage;
2. the stage hash changed: the hash covers the stage's declared config fields, the SHA-256 content of its declared input files, derived values (such as the model run set, trial survival selection and template grid), the hashes of its upstream stages, and the package, AFNI, Python, numpy and pandas versions;
3. an output recorded by the last completion is missing from `out_dir`;
4. an upstream stage executed (was not reused) in this invocation;
5. the last completion recorded failed runs.

On reuse, the stage's QC fragment and warnings are replayed (warnings re-logged with a `[reused stage ...]` prefix) and the stage appears in `reused_stages`.

**Content-hashed inputs.** Censor and prepared motion files (so motion file content and `fd_threshold` changes propagate), onset files (events content), prepared tissue regressor files (task and rest) and rest notch-filtered motion, and the template file together with the scan grid.

**Path-only inputs.** Scan files enter stage hashes by path, not content. Replacing a scan's contents in place at the same path is not detected; use `remove_previous: true` or a new `out_dir`. Any version change of the package, AFNI, Python, numpy or pandas reruns every ledgered stage.

**`remove_previous`.** Deletes every path recorded in this analysis's ledger, its staging directories and the ledger, then starts fresh. Files of other analyses (other ledgers) and unrecorded files are untouched.

**Unrecorded files.** When an analysis has no ledger yet, `out_dir` must not contain files starting with any of its prefixes (`{pre}_`, `{ext}_`, `{conn_pre}_`), the pre-4.0.0 unprefixed resampled template, or a `_sequenced_intermediates` directory, unless another ledger in `out_dir` records them (the active log file is exempt). Otherwise `InputError` lists them (for example, outputs of an earlier package version): use an empty `out_dir` or remove the listed paths.

**Retirement.** At the end of a run, paths recorded by the ledger but neither produced nor expected in this invocation (for example, outputs of a dropped condition, or a task_conn connectivity output whose condition or contrast produced nothing this time) are deleted and logged in a retired record and in `retired_outputs`. Frozen primary outputs are never retired.

Several analyses may share an `out_dir` when none of their output prefixes coincide (see [Cross-block collisions](#yaml-config-structure)); each ledger tracks only its own outputs.

---

## Runtime Validation

Run by the CLI before config loading and at the start of every pipeline `run()` (probes are cached per process; version comparisons are re-evaluated each time).

### AFNI binaries

All 19 binaries must be reachable: `3dDeconvolve`, `3dTproject`, `3dTstat`, `3dBandpass`, `3dROIstats`, `3dresample`, `3dinfo`, `3dToutcount`, `3dbucket`, `3dcalc`, `3dLSS`, `3dTcat`, `1d_tool.py`, `1dtranspose`, `3dAttribute`, `1ddot`, `3dTcorr1D`, `3dBlurToFWHM`, `3dFWHMx`. For this reachability check, AFNI home is resolved from (1) the `afni_home` argument (programmatic only), (2) the directory of `afni` on `PATH`, (3) `~/abin`. All missing binaries are reported in one `ToolUnavailableError`. Commands themselves (including the `afni -ver` probe) are executed by name, so AFNI must be on `PATH`.

### Version policy (packaged lockfile)

| Check | Below `minimum` | Differs from `validated` |
|---|---|---|
| AFNI (`afni -ver`, compared as an integer triple) | `ToolVersionError` | `UNVALIDATED_VERSION` (medium) |
| Python (major.minor) | `ToolVersionError` | `UNVALIDATED_VERSION` |
| numpy, pandas (PEP 440) | `ToolVersionError` | `UNVALIDATED_VERSION` |

The resolved versions are recorded in `provenance` and in every stage hash.

---

## Exit Codes

| Code | Cause |
|---|---|
| 0 | All analyses completed with no high-severity warnings. |
| 1 | `GuardError` (pipeline invariant violation; indicates a bug) or any unexpected exception. |
| 2 | `ConfigError`, `InputError`. |
| 3 | All analyses completed, but at least one high-severity warning was raised. |
| 4 | `ToolUnavailableError`, `ToolVersionError`, `ToolExecutionError`, or an unwrapped subprocess failure. |
| 5 | `ModelError` (insufficient DOF, no estimable condition, every run excluded, null connectivity). |

**Multi-block runs.** The CLI validates, checks and runs each analysis block independently: a failing block stops at its first error, its failure is recorded in its `qc_summary.json` (`run_status`) when its `out_dir` and `out_file_pre` are valid, and the remaining blocks proceed. The exit code is the code of the **first failing block in config order**; with no failing block it is 3 when any high-severity warning was raised, otherwise 0. Global problems (unreadable YAML, top-level or global section errors, the runtime check) stop the run before any block. The same mapping is available as `fmri_first_level_proc.exceptions.exit_code(exc)`.

---

## CLI Flags

```
fmri-first-level-proc --config <path> [--dry-run] [--analyses I [I ...]] [--log-file <path>]
```

| Flag | Default | Description |
|---|---|---|
| `--config` | (required) | YAML config file. |
| `--dry-run` | off | Validate the config and, for every valid block, its input files: run-set construction (volume counts, header TR, grids, motion and tissue rows, columns and finite values), the rest_conn path-list lengths, events parsing with onset validation and duplicate-trial detection, and template properties. Prints the plan and a per-block summary; executes and writes nothing (the timing-error record is not written). Exit code follows the multi-block rule. |
| `--analyses` | all | 0-based block indices (as numbered in the config) to run (out-of-range index: exit 2). |
| `--log-file` | none | Also write logs (DEBUG level) to this file. |

`fmri-first-level-proc` is the only console script.

---

## Programmatic API

```python
from fmri_first_level_proc import load_and_validate, setup_logging, DISPATCH

logger = setup_logging("my_analysis", log_file="run.log")
configs = load_and_validate("study.yaml", logger, subject="01", session="A")
for cfg in configs:
    result = DISPATCH[cfg.analysis_type](cfg, logger)
```

- `load_and_validate(config_path, logger=None, **overrides)`: load, validate and resolve; keyword overrides are merged into every raw analysis block before validation (for example to inject `subject`, `out_dir` or `out_file_pre` per participant). Returns `list[ResolvedConfig]` in file order; the first invalid block raises.
- `load_and_validate_blocks(config_path, logger=None, **overrides)`: the per-block form used by the CLI. Global problems raise; otherwise returns one `BlockResolution(index, name, analysis_type, config, error, raw_out_dir, raw_out_file_pre)` per block, with exactly one of `config` (a `ResolvedConfig`) and `error` (the exception) set.
- Each pipeline `run()` raises on failure as before; before raising, it records the failure in `{pre}_qc_summary.json` (`run_status`, see [QC Summary JSON](#qc-summary-json)).
- `ResolvedConfig`: flat dataclass for one block; `input_mode` property (`"A"` or `"B"`); `schema_version` = `"4.0.0"`. Schema-version policy: removal, rename, change of meaning or tightened validation ship only in a package major release; additions bump the minor version; patch is always 0.
- `DISPATCH`: `{"task_act": ..., "task_conn": ..., "rest_conn": ...}` mapping to each pipeline's `run(config, logger=None)`. Also importable as `run_task_act`, `run_task_conn`, `run_rest_conn`.
- `FirstLevelResult`: `status` (`"success"` or `"warning"`), `output_dir` (`Path`), `warnings` (list of records), `qc_summary` (dict, same content as the JSON), `output_files` and `intermediate_files` (absolute paths, disjoint).
- `graded_warning`, `get_warnings`, `clear_warnings`, `setup_logging`, `BlockResolution`, `ToolVersionError`, `__version__` are also exported.

---

## Exception Hierarchy

All exceptions derive from `FmriFirstLevelError(message, context=None)`, whose `context` dict carries structured metadata (for example `excluded_runs`, `missing_conditions`, the timing record, or `unrecorded_paths`).

```
FmriFirstLevelError
├── ConfigError          # schema violations, invalid values, incompatible options
├── InputError           # missing, malformed or inconsistent input files
├── ToolUnavailableError # AFNI binary or packaged lockfile unavailable
├── ToolVersionError     # installed version below the lockfile minimum
├── ToolExecutionError   # external command failed or produced invalid output
├── ModelError           # data quality prevents estimation
└── GuardError           # internal invariant violation (bug)
```

Wrapped AFNI failures always state the command, the caller's description and AFNI's stderr.

---

## Known Limitations

- Scan content is hashed by path only (see [Stage Reuse](#stage-reuse-and-reruns)).
- Inputs are assumed brain-masked; ROI QC and smoothing masks rely on constant or zero non-brain voxels.
- PSC scaling requires positive-baseline input.
- Motion files must be translations-first, in mm and degrees; FD is otherwise biased.
- Mode B event onsets are in concatenated-series time; Mode A onsets are run-local.
- `task_act` does not model events of conditions absent from `cond_labels`.
- `task_conn` rejects married-timing HRFs and multi-column custom HRFs.
- Condition labels must be file-name-safe tokens; those used in contrasts must also match `\w+` (no `.` or `-`).
- Seed-to-voxel contrasts accept at most 26 condition maps.
- Parcellated correlations inherit the five-decimal precision of `1ddot`.

---

## References

- Ciric, R., Wolf, D. H., Power, J. D., et al. (2017). Benchmarking of participant-level confound regression strategies for the control of motion artifact in studies of functional connectivity. *NeuroImage*, 154, 174-187. PMID 28302591.
- Hallquist, M. N., Hwang, K., & Luna, B. (2013). The nuisance of nuisance regression: spectral misspecification in a common approach to resting-state fMRI preprocessing reintroduces noise and obscures functional connectivity. *NeuroImage*, 82, 208-225. PMID 23747457.
- Power, J. D., Barnes, K. A., Snyder, A. Z., Schlaggar, B. L., & Petersen, S. E. (2012). Spurious but systematic correlations in functional connectivity MRI networks arise from subject motion. *NeuroImage*, 59(3), 2142-2154. PMID 22019881.
- Power, J. D., Mitra, A., Laumann, T. O., Snyder, A. Z., Schlaggar, B. L., & Petersen, S. E. (2014). Methods to detect, characterize, and remove motion artifact in resting state fMRI. *NeuroImage*, 84, 320-341. PMID 23994314.
