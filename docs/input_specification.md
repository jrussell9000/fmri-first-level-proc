# Input Specification

Complete reference for all inputs accepted by `fmri-first-level-proc`. This document covers the YAML config structure, every parameter and its allowed values, the exact format requirements for each input file, all output files, runtime validation, and exit codes.

---

## Table of Contents

- [YAML Config Structure](#yaml-config-structure)
- [Global Settings](#global-settings)
- [Analysis Block: Common Fields](#analysis-block-common-fields)
- [Analysis Block: task\_act](#analysis-block-task_act)
- [Analysis Block: task\_conn](#analysis-block-task_conn)
- [Analysis Block: rest\_conn](#analysis-block-rest_conn)
- [Spatial Smoothing](#spatial-smoothing)
- [Input File Formats](#input-file-formats)
  - [Scan File](#scan-file)
  - [Task Timing File](#task-timing-file)
  - [Motion Regressor File](#motion-regressor-file)
  - [Censor File (Generated Internally)](#censor-file-generated-internally)
  - [Tissue Regressor Files (CSF, WM, GS)](#tissue-regressor-files-csf-wm-gs)
  - [ROI Template File](#roi-template-file)
  - [Tools Lockfile](#tools-lockfile)
- [BIDS Input Discovery](#bids-input-discovery)
- [Output Files](#output-files)
- [Quality Control](#quality-control)
- [Runtime Validation](#runtime-validation)
- [Exit Codes](#exit-codes)
- [CLI Flags](#cli-flags)
- [Exception Hierarchy](#exception-hierarchy)

---

## YAML Config Structure

The schema is closed. A key this document doesn't define is a `ConfigError` at any level, and all such keys are reported together. Other rules:

- A required key set to `null` counts as missing, except a boolean, where `null` means the default. Booleans accept only `true`, `false` or `null`.
- `tr`, `fd_threshold`, `bandpass`, `notch_filter_band` and `smoothing.fwhm` must be finite numbers. `motion_deriv_degree` must be an integer >= 1.
- `out_file_pre`, `extract_out_file_pre`, `conn_out_file_pre` and condition labels must be file-name-safe (`^[A-Za-z0-9][A-Za-z0-9._-]*$`). Condition labels must be unique strings, so quote numeric codes.
- Contrast labels must stay unique after file-name sanitization. `connectivity.contrasts` need `calc_conn`.
- `extract_resids` needs `stat_buckets` and `extract_out_file_pre`. `calc_conn` needs `conn_out_file_pre`.
- Keys valid only in `global` (`tr`, `num_cores`, `template_path`, `force_diff_atlas`) are errors in an analysis block.

The config file has two top-level keys:

```yaml
global:
  # Global settings (applied uniformly to all blocks)

analyses:
  - # Analysis block 1
  - # Analysis block 2
  # ...
```

- `global` (dict, optional): settings that apply to every analysis block. Cannot be overridden per-block.
- `analyses` (list, required): one or more analysis block dicts. Blocks execute in order (top to bottom).

---

## Global Settings

| Key | Type | Default | Description |
|---|---|---|---|
| `num_cores` | int or `"auto"` | `1` | CPU budget per analysis block. Passed to `3dDeconvolve -jobs`, exported to every AFNI call as `OMP_NUM_THREADS`, and split across independent per-run (`rest_conn`) and per-condition (`task_conn` extraction/connectivity) steps that run concurrently. `"auto"` resolves at load time, in order: `OMP_NUM_THREADS` if it is a positive integer (e.g. a Kubernetes downward-API projection of the pod's CPU request), capped at the cgroup CPU limit; else the cgroup CPU limit (`cpu.max`, rounded down, minimum 1); else the CPUs schedulable for the process. The resolved value and its source are logged. |
| `tr` | float | (required) | Repetition time in seconds. Applies to all scans across all analysis blocks. |
| `template_path` | str or null | `null` | Path to a shared ROI template NIfTI file (`.nii.gz`). Required if any block uses extraction or connectivity. See [ROI Template File](#roi-template-file). |
| `force_diff_atlas` | bool | `false` | Allow atlas space/orientation mismatch between scan and template. Use with caution. |
| `derivatives_dirs` | list of str or null | `null` | Ordered list of BIDS derivatives directories for input discovery. See [BIDS Input Discovery](#bids-input-discovery). Can also be set per-block. |

These keys are **global-only** (except `derivatives_dirs`, which can also be set per-block; block-level overrides global). If `num_cores`, `tr`, `template_path`, or `force_diff_atlas` appear inside an analysis block, the block value is ignored and a warning is logged.

---

## Analysis Block: Common Fields

Every analysis block must contain these fields:

| Key | Type | Required | Description |
|---|---|---|---|
| `name` | str | No | Human-readable label for the block. Defaults to `analyses[<index>]`. |
| `type` | str | Yes | One of: `task_act`, `task_conn`, `rest_conn`. |
| `paths` | dict | Conditional | Input file paths. Required unless BIDS discovery is active (`derivatives_dirs` is set). Required sub-keys vary by type (see below). |
| `out_dir` | str | Yes | Output directory. Created automatically if it does not exist. |
| `out_file_pre` | str | Yes | Output filename prefix for all generated files. |
| `remove_previous` | bool | No | `true` = delete all files in `out_dir` before running. Default: `false`. |
| `average_type` | str | Yes | `"mean"` or `"median"`. Controls parcel-level averaging during extraction. |
| `fd_threshold` | float | Yes | Power et al. (2012) framewise displacement threshold in mm for motion censoring. TRs with FD above this value are censored. See [Censor File](#censor-file-generated-internally). |
| `censor_prev_tr` | bool | No | `true` = also censor the TR immediately before each high-motion TR. Default: `false`. |
| `scale_to_psc` | bool | No | `true` = scale BOLD to percent signal change before regression. Default: `true`. PSC scaling computes voxelwise temporal mean, divides each time series by its mean, and multiplies by 100 (with a 200% ceiling and zero-guard). Available for all three analysis types. |
| `derivatives_dirs` | list of str or null | No | Per-block override for BIDS derivatives directories. |
| `roi_zero_handling` | str | No | `"exclude"` = leave zero-valued voxels out of within-ROI averages (`3dROIstats -nzmean`/`-nzmedian`). `"include"` = average every ROI voxel. Default: `"exclude"`. Seed time series for smoothed seed maps always exclude zeros. |
| `smoothing` | dict or null | No | `{enabled: bool, fwhm: float}`. Writes smoothed siblings of the voxelwise outputs. See [Spatial Smoothing](#spatial-smoothing). Default: disabled. |

Two blocks may share an `out_dir` only when none of their output prefixes (`out_file_pre`, `extract_out_file_pre`, `conn_out_file_pre`) coincide. Directories are compared after normalization, so `out`, `./out` and its absolute path are one directory. A collision is a `ConfigError`. One block may reuse a prefix for its own outputs.

---

## Spatial Smoothing

Applies to all three analysis types.

```yaml
smoothing:
  enabled: true
  fwhm: 6          # mm; > 0, finite, at most two decimal places
```

- Smoothing uses `3dBlurToFWHM -ACF -FWHM fwhm` within a data-derived mask, `{out_file_pre}_smoothing_mask.nii.gz`: the intersection of each run's non-constant voxels. Automask is never used.
- **`task_act`, `task_conn`:** each run of the unscaled scan is blurred, PSC-scaled by its own mean when `scale_to_psc` is true, and concatenated. This input feeds a second model: a GLM with the same contrasts, or 3dLSS with the same design matrix. Input and output ACF FWHM are measured with `3dFWHMx -detrend`.
- **`rest_conn`:** each run's residuals are blurred and re-concatenated. ACF FWHM is measured without detrending. Smoothed per-run residuals are kept when `keep_run_res_dtseries` is true.
- **Never smoothed:** every parcel-level output (parcellated stat CSVs, residual and raw ptseries, pbseries, parcellated connectivity). Their unsmoothed versions are still written.
- **Seed-to-voxel:** the smoothed sibling uses the unsmoothed seed time series and the smoothed target, through `3dTcorr1D`, because `3dNetCorr` takes both from one dataset. With an unsmoothed target the two programs agree to within 0.001. Partial correlation does not change a single seed's map.
- **File names:** smoothed outputs insert `_s{N}mm` before the extension, with `.` in the FWHM written as `p`: `6` gives `_s6mm`, `4.5` gives `_s4p5mm`.
- **QC:** `smoothing_per_run` records, and medium-severity warnings `SMOOTH_FWHM_OFF_TARGET` (achieved FWHM more than 10% from target), `SMOOTH_INPUT_ABOVE_TARGET` (input FWHM already above target) and `SMOOTH_ACF_FIT_FAILED` (`3dFWHMx` could not fit the ACF, so the FWHM values are null). On spatially white data, `3dBlurToFWHM -ACF` can fail the same way and leave a run unsmoothed.

---

## Analysis Block: `task_act`

First-level GLM via AFNI `3dDeconvolve`.

### Required Fields

| Key | Type | Description |
|---|---|---|
| `cond_labels` | list of str | Condition labels. Must match entries in the `trial_type` column of the timing file (BIDS) or `CONDITION` column (legacy CSV). |
| `hrf_model` | str | HRF model. One of: `GAM`, `BLOCK`, `dmBLOCK`, `SPMG1`, `custom`. |
| `include_motion_derivs` | bool | `false` = 6 motion columns. `true` = 12 motion columns (6 base + 6 temporal derivatives). |

### Required Paths

| Key | Type | Description |
|---|---|---|
| `paths.scan_path` | str | Path to preprocessed, run-concatenated NIfTI scan. See [Scan File](#scan-file). |
| `paths.task_timing_path` | str | Path to task timing file. See [Task Timing File](#task-timing-file). |
| `paths.motion_path` | str | Path to motion regressor file. See [Motion Regressor File](#motion-regressor-file). |

All required paths may be omitted when BIDS discovery is active (`derivatives_dirs` is set); see [BIDS Input Discovery](#bids-input-discovery).

Give `paths.run_lengths` for any scan that concatenates more than one run. See [Scan File](#scan-file).

### Optional Paths

| Key | Type | Default | Description |
|---|---|---|---|
| `paths.CSF_path` | str or null | `null` | Mean CSF BOLD signal per TR. See [Tissue Regressor Files](#tissue-regressor-files-csf-wm-gs). |
| `paths.WM_path` | str or null | `null` | Mean WM BOLD signal per TR. See [Tissue Regressor Files](#tissue-regressor-files-csf-wm-gs). |

### Optional Fields

| Key | Type | Default | Description |
|---|---|---|---|
| `custom_hrf` | str or null | `null` | Custom AFNI HRF model string (e.g. `"TENT(0,14,8)"`). Required when `hrf_model: custom`. |
| `use_tissue_derivs` | bool | `false` | `true` = include first temporal derivatives of tissue signals (CSF, WM) as additional nuisance regressors. Only computed for tissue paths that are not null. |
| `contrasts` | dict or null | `null` | Linear contrast specification. See below. |
| `extraction` | dict or null | `null` | Stat-bucket extraction. See below. |

### Contrasts

```yaml
contrasts:
  functions:          # list of str or null; null = contrasts disabled
    - "1*stimFear-1*stimNeu"
    - "1*stimSad-1*stimNeu"
  labels:             # list of str; must be same length as functions
    - "Fear-Neutral"
    - "Sad-Neutral"
```

- `functions`: list of AFNI-style contrast equations using condition labels. Set to `null` to disable.
- `labels`: human-readable names for each contrast. Same length as `functions`.

### Extraction (stat_buckets API)

```yaml
extraction:
  stat_buckets: ["Tstat", "Zstat"]     # list of stat types; valid: "Coef", "Tstat", "Fstat", "R^2", "Zstat"; null = disabled
  extract_out_file_pre: "subj001"      # str; output filename prefix for extracted values
  extract_resids: false                # bool; true = also extract residuals
  extract_raw_ptseries: false          # bool; true = extract pre-regression parcellated time series
```

When `stat_buckets` is set (non-null, non-empty list), for each stat type:
1. All matching sub-bricks are discovered in the 3dDeconvolve bucket dataset.
2. Matched sub-bricks are extracted into a multi-sub-brick NIfTI: `{extract_out_file_pre}_{StatType}_bucket.nii.gz`.
3. A JSON index mapping condition/contrast labels to sub-brick indices is written: `{extract_out_file_pre}_{StatType}_index.json`.
4. When `template_path` is available (not null and not `"WB"`), a parcellated CSV is written (rows = conditions/contrasts, columns = ROIs).

For `"Zstat"`: Tstat sub-bricks are located, converted to Z-scores via AFNI's `fitt_t2z()`, then assembled into the Z bucket.

Requires `extract_out_file_pre`. Requires `template_path` in global settings when parcellated CSVs are desired. Requires `average_type` when `template_path` is set.

A master sub-brick index for the full bucket stats dataset is always generated: `{out_file_pre}_concat_bucket_stats_index.json`.

When `extract_raw_ptseries: true`, `extract_out_file_pre` and `template_path` are required. Extracts ROI-level time series from the raw (pre-regression) scan. Output: `{extract_out_file_pre}_raw_ptseries.csv`. Uses skip-if-exists logic.

---

## Analysis Block: `task_conn`

Beta series estimation via AFNI `3dDeconvolve` + `3dLSS`.

### Required Fields

| Key | Type | Description |
|---|---|---|
| `cond_beta_labels` | list of str | Conditions for trial-level beta series estimation. Must match entries in the `trial_type` column of the timing file (BIDS) or `CONDITION` column (legacy CSV). |
| `hrf_model` | str | HRF model. One of: `GAM`, `BLOCK`, `dmBLOCK`, `SPMG1`, `custom`. |
| `include_motion_derivs` | bool | `false` = 6 motion columns. `true` = 12 motion columns. |

### Required Paths

Same as `task_act`: `scan_path`, `task_timing_path`, `motion_path`. All may be omitted when BIDS discovery is active.

### Optional Paths

Same as `task_act`: `CSF_path`, `WM_path`.

### Optional Fields

| Key | Type | Default | Description |
|---|---|---|---|
| `custom_hrf` | str or null | `null` | Custom AFNI HRF model string. Required when `hrf_model: custom`. |
| `use_tissue_derivs` | bool | `false` | `true` = include first temporal derivatives of tissue signals (CSF, WM) as additional nuisance regressors. Only computed for tissue paths that are not null. |
| `extraction` | dict or null | `null` | Parcel beta series extraction. See below. |
| `connectivity` | dict or null | `null` | Functional connectivity computation (including optional connectivity contrasts). See below. |

### Contrasts (Connectivity)

Linear contrasts applied to condition-level connectivity outputs (post-connectivity). These compute weighted linear combinations of condition-specific connectivity matrices (parcellated) or seed-to-voxel maps. Contrasts are specified as a sub-block within `connectivity`:

```yaml
connectivity:
  calc_conn: "parcellated"
  conn_out_file_pre: "subj001_Shen368"
  pcorr: false
  fishZ: true
  contrasts:
    functions:          # list of str or null; null = contrasts disabled
      - "1*stimFear-1*stimNeu"
      - "1*stimSad-1*stimNeu"
    labels:             # list of str; must be same length as functions
      - "Fear-Neutral"
      - "Sad-Neutral"
```

- `functions`: list of contrast equations using condition labels from `cond_beta_labels`. Set to `null` to disable.
- `labels`: human-readable names for each contrast. Same length as `functions`. Labels are sanitized for filesystem safety (spaces/slashes replaced with underscores).

**Requirements:**
- Connectivity must be enabled (`calc_conn` must not be null). If contrasts are specified without connectivity, a warning is logged and contrasts are skipped.
- Each condition referenced in a contrast equation must be present in `cond_beta_labels` and must have a valid connectivity output file on disk.
- If a contrast references a condition with a missing connectivity output, that contrast is skipped with an error log (other contrasts still proceed).

**Implementation details:**
- **Parcellated:** Contrast matrices are computed via element-wise weighted linear combination of condition matrices (loaded with `numpy.loadtxt`, tab-delimited). All matrices must have identical dimensions.
- **Seed-to-voxel:** Contrasts are computed via AFNI `3dcalc` with single-letter identifiers (a-z), supporting up to 26 unique conditions per contrast expression.

**Output naming:** Same convention as condition-level connectivity outputs, with the sanitized contrast label replacing the condition name. For example, with `conn_out_file_pre: "subj001_Shen368"`, `fishZ: true`, `calc_conn: "parcellated"`:
- `subj001_Shen368_Fear-Neutral_fishZ_mat.txt`

### Extraction

```yaml
extraction:
  extract_pbseries: true           # bool; true = extract parcel beta series
  extract_out_file_pre: "subj001"  # str; required when extract_pbseries is true
  extract_raw_ptseries: false      # bool; true = extract pre-regression parcellated time series
```

Requires `template_path` in global settings. When `extract_raw_ptseries: true`, `extract_out_file_pre` and `template_path` are required. Output: `{extract_out_file_pre}_raw_ptseries.csv`. Skip-if-exists logic prevents redundant extraction when both task_act and task_conn are configured with the same scan/template.

### Connectivity

```yaml
connectivity:
  calc_conn: "parcellated"         # str or null; null = disabled; "seed_to_voxel" or "parcellated"
  conn_out_file_pre: "subj001"     # str; output filename prefix
  pcorr: false                     # bool; true = partial correlation
  fishZ: true                      # bool; true = Fisher Z-transform
  contrasts:                       # dict or null; connectivity contrasts (see above)
    functions:
      - "1*stimFear-1*stimNeu"
    labels:
      - "Fear-Neutral"
```

Requires `template_path` in global settings. For `seed_to_voxel`, the template must be a binary mask (single ROI). For `parcellated`, the template must contain >= 2 integer-labeled ROIs.

<a id="parcellated-matrix-contents"></a>**Parcellated matrix contents** (from 3dNetCorr's `.netcc`; the same applies to `rest_conn`):

| `pcorr` | `fishZ` | Matrix written |
|---|---|---|
| false | false | `CC`: Pearson correlation |
| false | true | `FZ`: AFNI's Fisher Z of `CC` (arctanh, \|z\| capped at 4.0; diagonal 4.0) |
| true | false | `PC`: partial correlation (AFNI's diagonal is -1) |
| true | true | Fisher Z of `PC`, computed by the package with the same cap as AFNI's `FZ` (diagonal -4.0). AFNI writes no Fisher-Z partial correlation; its `PCB` section holds asymmetric regression coefficients and is not used. |

Diagonals carry no connectivity information.

---

## Analysis Block: `rest_conn`

Residual time series via AFNI `3dTproject` with bandpass filtering. Processes each run individually, then concatenates.

### Required Fields

| Key | Type | Description |
|---|---|---|
| `bandpass` | list of 2 floats | Bandpass filter bounds in Hz: `[low, high]`. Must satisfy `0 <= low < high`. |
| `motion_deriv_degree` | int (>= 1) | Number of derivative orders. Total motion columns = `6 * motion_deriv_degree`. E.g. `2` = 12 columns (6 base + 6 first derivatives). |

### Required Paths

All path keys are **lists** with one entry per run. All lists must be the **same length**.

| Key | Type | Description |
|---|---|---|
| `paths.scan_paths` | list of str | Preprocessed NIfTI scan per run. See [Scan File](#scan-file). |
| `paths.motion_paths` | list of str | Motion regressor file per run. See [Motion Regressor File](#motion-regressor-file). |
| `paths.CSF_paths` | list of str | Mean CSF BOLD signal per TR, per run. See [Tissue Regressor Files](#tissue-regressor-files-csf-wm-gs). |
| `paths.WM_paths` | list of str | Mean WM BOLD signal per TR, per run. See [Tissue Regressor Files](#tissue-regressor-files-csf-wm-gs). |

All required paths may be omitted when BIDS discovery is active.

### Optional Paths

| Key | Type | Default | Description |
|---|---|---|---|
| `paths.GS_paths` | list of str or null | `null` | Mean global BOLD signal per TR, per run. Enables global signal regression. Must be same length as other path lists. |

### Optional Fields

| Key | Type | Default | Description |
|---|---|---|---|
| `notch_filter_band` | list of 2 floats or null | `null` | Respiration artifact notch filter Hz band: `[low, high]`. Must satisfy `0 < low < high`. Applied to motion regressors before censor file generation. Set to `null` to disable. |
| `keep_run_res_dtseries` | bool | `true` | `true` = retain per-run residual dtseries files. `false` = delete after concatenation. |
| `use_tissue_derivs` | bool | `false` | `true` = include first temporal derivatives of tissue signals (CSF, WM, and GS when enabled) as additional nuisance regressors. |
| `use_sequenced_bandpass` | bool | `false` | `true` = use the sequenced denoising path (Ciric et al. 2017): BOLD and nuisance regressors are NTRP-interpolated at censored TRs and bandpass-filtered separately before final nuisance regression. Eliminates the DOF cost of bandpass-implied regressors in the regression model. 3dBandpass detrends (quadratic) BOLD and regressors alike; the simultaneous path uses `3dTproject -polort` instead (2 when `bandpass[0] > 0`, else `1 + floor(run duration / 150 s)`). Requires `bandpass` to be set; ignored if `bandpass` is null. Intermediate files are written to `{out_dir}/_sequenced_intermediates/run{N}/`; removed after each run unless `keep_run_res_dtseries: true` or on failure. |
| `extraction` | dict or null | `null` | Parcel time series extraction. See below. |
| `connectivity` | dict or null | `null` | Functional connectivity computation. See below. |

### Extraction

```yaml
extraction:
  extract_ptseries: true           # bool; true = extract parcel time series
  extract_out_file_pre: "subj001"  # str; required when extract_ptseries is true
  extract_raw_ptseries: false      # bool; true = extract pre-regression parcellated time series per run
```

Requires `template_path` in global settings. When `extract_raw_ptseries: true`, `extract_out_file_pre` and `template_path` are required. Output: `{extract_out_file_pre}_run{N}_raw_ptseries.csv` (one file per run).

### Connectivity

Same structure as `task_conn`:

```yaml
connectivity:
  calc_conn: "parcellated"         # str or null; null = disabled; "seed_to_voxel" or "parcellated"
  conn_out_file_pre: "subj001"     # str; output filename prefix
  pcorr: false                     # bool; true = partial correlation
  fishZ: true                      # bool; true = Fisher Z-transform
```

---

## Input File Formats

### Scan File

- **Format:** NIfTI (`.nii` or `.nii.gz`)
- **Content:** Preprocessed BOLD fMRI data (4D: x, y, z, time)
- **Space:** Must be in a standard atlas space (e.g. MNI). AFNI `3dinfo` is used to check space, orientation, and grid spacing against the ROI template.
- **Task analyses (`task_act`, `task_conn`):** A single file containing all runs concatenated along the time dimension. Set `paths.run_lengths` to the TRs per run, in order (for example `[370, 370]`). Without it the scan is modelled as **one run**. With it:
  - each run gets its own polynomial baseline (`3dDeconvolve -concat`, `-polort A`);
  - each run is PSC-scaled by its own mean;
  - FD and tissue derivatives are 0 at each run's first TR.

  `run_lengths` must sum to the number of motion rows (`InputError` otherwise). Onsets stay relative to the start of the concatenated scan (`-global_times`).
- **Resting-state (`rest_conn`):** One file per run (not concatenated; the pipeline concatenates residuals internally).

### Task Timing File

The pipeline accepts two formats, detected by inspecting the file header (content-authoritative detection). BIDS format is preferred; legacy CSV format is deprecated and will be removed in v4.0.0.

**BIDS format** (preferred): Tab-separated values (`.tsv`).

| Column | Type | Description |
|---|---|---|
| `onset` | float | Trial onset time in seconds, relative to the start of the concatenated scan. |
| `duration` | float | Trial duration in seconds. |
| `trial_type` | str | Trial condition label. Must match entries in `cond_labels` (task_act) or `cond_beta_labels` (task_conn). |

Optional BIDS columns (e.g. `amplitude`) are preserved but only `onset`, `duration`, and `trial_type` are used.

**Legacy CSV format** (deprecated): Comma-separated values (`.csv`).

| Column | Type | Description |
|---|---|---|
| `CONDITION` | str | Trial condition label. Mapped internally to `trial_type`. |
| `ONSET` | float | Trial onset time in seconds. |
| `DURATION` | float | Trial duration in seconds. |
| `AMP` | float (optional) | Amplitude modulator. Used by `dmBLOCK` and amplitude-modulated HRF models. |

**Detection logic:** The file extension determines the delimiter (`.tsv` = tab; `.csv`/other = comma). Then the header columns are inspected: if `onset`, `duration`, `trial_type` are present (case-insensitive), the file is treated as BIDS format. If `CONDITION`, `ONSET`, `DURATION` are present (case-insensitive), it is treated as legacy CSV and a deprecation warning is emitted. All internal processing uses BIDS column names (`onset`, `duration`, `trial_type`) regardless of input format.

**Common rules:**
- **Row ordering:** Rows are sorted by `onset` internally; input order does not matter.
- **Durations and duplicates:** A negative or non-finite duration, or two rows with the same condition and onset, raises `InputError`. `trial_type` values are compared as strings.
- **Onset validation:** Every row is checked, including conditions that aren't modelled. A negative or non-finite onset, or one at or after the end of the scan, raises `InputError`. A run also writes `{out_file_pre}_timing_errors.json`: `{analysis_type, tr, n_trs, run_end_s, violations: [{condition, onset_s, violation}]}`, where `violation` is `negative`, `at_or_after_run_end` or `non_finite`.
- **Condition coverage:** Every label in `cond_labels`/`cond_beta_labels` must appear at least once. A warning is logged for conditions with fewer than 3 trials.
- **Extra conditions:** The timing file may contain conditions not listed in `cond_labels`/`cond_beta_labels`; they are ignored.

### Motion Regressor File

- **Format:** Plain text, whitespace-delimited (spaces or tabs), no header row, no row names
- **Reader:** `numpy.loadtxt(path)`
- **Rows:** One row per TR (timepoint). Must match the scan length (enforced by AFNI).
- **Columns:** 6 base motion parameters (3 translation + 3 rotation), optionally followed by temporal derivatives.
  - **Column order (required):** `[tx, ty, tz, rx, ry, rz, ...]` -- translations first (columns 1-3), rotations second (columns 4-6). This is the only supported column order. When derivatives are appended, they follow the same `[trans, rot]` pattern (e.g., columns 7-12 are the first temporal derivatives of columns 1-6).
  - **Units (required):** Translations in **millimeters (mm)**, rotations in **degrees**. The pipeline does no unit conversion. Rotations **must** be in degrees -- passing radians underweights the rotational contribution to FD by approximately 57x. Standard fMRIPrep output is radians, so check your `rot_*` columns: a correct file's `framewise_displacement` equals the sum of absolute translation differences plus `(pi/180) * 50` times the sum of absolute rotation differences. ABCD's confounds already hold degrees.
  - **Non-finite values** in the first 6 columns raise `InputError`.
  - `task_act` / `task_conn` with `include_motion_derivs: false` -> minimum 6 columns used
  - `task_act` / `task_conn` with `include_motion_derivs: true` -> minimum 12 columns used
  - `rest_conn` with `motion_deriv_degree: N` -> minimum `6 * N` columns used
- **Truncation:** If the file contains more columns than needed, extra columns are silently truncated to the required count. A log message is emitted when this occurs.
- **Prepared file:** The pipeline writes a validated, truncated copy to `out_dir` as `{out_file_pre}_concat_motion_prepared.1D` (task) or `{out_file_pre}_run{N}_motion_prepared.1D` (rest_conn). The prepared file is tab-delimited with 8 decimal places.

### Censor File (Generated Internally)

Censor files are **not** user-provided inputs. They are generated automatically by the pipeline from the motion regressor file using `fd_threshold` and `censor_prev_tr`. The pipeline computes Power et al. (2012) framewise displacement (FD), and censors a TR when FD > `fd_threshold`. FD sums the absolute backward differences of the first 6 motion columns, with rotations converted to arc length on a 50 mm sphere. It is not interchangeable with AFNI's enorm (`1d_tool.py -censor_motion`): 0.873 x enorm <= FD <= 2.30 x enorm.

- **Naming:** `{out_file_pre}_concat_censor.1D` (task_act, task_conn) or `{out_file_pre}_run{N}_censor.1D` (rest_conn, one per run).
- **Format:** Plain text, single column of binary values (`1` = include, `0` = censor). One row per TR.
- **Usage:** Passed directly to AFNI (`3dDeconvolve -censor` or `3dTproject -censor`).
- **FD series:** Written beside the censor file as `{out_file_pre}_concat_fd.1D` or `{out_file_pre}_run{N}_fd.1D`.

### Tissue Regressor Files (CSF, WM, GS)

Applies to: `CSF_path`/`CSF_paths`, `WM_path`/`WM_paths`, `GS_paths`

- **Format:** Plain text, no header row, no row names
- **Rows:** One row per TR (timepoint). Must match the scan length.
- **Columns:** Single column containing the mean BOLD signal for that tissue compartment at each TR.
- **Reader:** Passed directly to AFNI (`3dDeconvolve -ortvec` or `3dTproject -ort`). When `use_tissue_derivs: true`, files are also read by Python (`numpy.loadtxt`) to compute first temporal derivatives.
- **Derivative files:** When `use_tissue_derivs: true`, derivative files are written to `out_dir` as `{out_file_pre}_{tissue}_deriv.txt` (task) or `{out_file_pre}_run{N}_{tissue}_deriv.txt` (rest_conn). Derivatives use backward differencing with zero-padding to preserve length.
- **Required vs. optional:**
  - `task_act`, `task_conn`: CSF and WM are optional (`null` to skip)
  - `rest_conn`: CSF and WM are **required**; GS is optional (`null` to skip global signal regression)

### ROI Template File

- **Format:** NIfTI (`.nii` or `.nii.gz`)
- **Content:** 3D volume with integer-valued ROI labels
- **Space:** Should match the scan's atlas space and orientation. If there is a grid mismatch, the pipeline will resample the template via `3dresample` to match the scan grid. A space/orientation mismatch causes an error unless `force_diff_atlas: true`.
- **Label constraints:**
  - Must contain only integer values (no floating-point ROI labels)
  - Must contain at least one non-zero voxel
  - For `seed_to_voxel` connectivity: must be a binary mask (max label = 1)
  - For `parcellated` connectivity or extraction: must have >= 2 distinct ROI labels

### Tools Lockfile

- **File:** `src/fmri_first_level_proc/data/tools.lock.yaml` (shipped as package data)
- **Format:** YAML
- **Purpose:** Pins expected versions of external tools and the Python runtime for reproducibility.
- **Schema:**
  ```yaml
  lockfile_version: "1.0.0"
  python: "3.14.3"          # validated interpreter; major.minor compared, mismatch warns
  binaries:
    AFNI: "26.3.07"         # exact match enforced; "PLACEHOLDER" to skip
  ```
- **Behavior:** The pipeline reads the lockfile at startup from the installed package. See [Version Lock Validation](#2-version-lock-validation).

---

## BIDS Input Discovery

When `derivatives_dirs` is set (in `global` or in a specific analysis block), the pipeline can automatically discover preprocessed input files from BIDS derivatives directories. This reduces per-subject path boilerplate.

**Activation:** Set `derivatives_dirs` to an ordered list of BIDS derivatives root directories. When active, the `paths` block in each analysis becomes optional: any path slot not explicitly provided is filled by BIDS discovery.

**Discovery rules:**
- Directories are searched in list order. For each slot, the first directory that yields matches wins.
- If a slot matches in more than one directory, a `DISCOVERY_COLLISION` warning (severity `medium`) is emitted.
- Slots with no matches in any directory are returned as `None`; mandatory-slot enforcement happens during config resolution.

**Required block keys when discovery is active:** The block must include a `subject` key (BIDS subject label without the `sub-` prefix). Optional: `session` (without `ses-` prefix), `task` (without `task-` prefix).

**Slot definitions:**

| Slot | BIDS desc | BIDS suffix | Extension | Mandatory |
|------|-----------|-------------|-----------|-----------|
| scan_path/paths | preproc | bold | .nii.gz | all types |
| motion_path/paths | confounds | regressors | .tsv | all types |
| task_timing_path | -- | events | .tsv | task_act, task_conn |
| CSF_path/paths | CSF | timeseries | .1D | rest_conn |
| WM_path/paths | WM | timeseries | .1D | rest_conn |
| GS_paths | GS | timeseries | .1D | optional |
| template_path | -- | dseg | .nii.gz | optional |

---

## Output Files

All outputs are written to `out_dir` using the `out_file_pre` prefix. Every analysis type writes a QC summary JSON and a run manifest.

### Run Manifest

**File:** `{out_file_pre}_manifest.json`

Records each run of a block: a SHA-256 hash of the output-affecting config (every `ResolvedConfig` field except `num_cores`, `remove_previous`, and `analysis_name`), the package version, start/finish times, `status` (`started`, `failed` with an `error` message, or `completed`), the files this block created (`owned_files`, relative to `out_dir`), and on completion the result (`status`, `output_files`, `warnings`, `qc_summary`). It doubles as a machine-readable result record for workflow engines.

On rerun:

| Previous manifest | Behavior |
|---|---|
| none | Run normally. |
| `completed`, same config, all `output_files` present | Skip the block and return the recorded result. |
| `completed`, same config, some outputs missing | Rerun; stages regenerate missing files. |
| `started` / `failed`, same config | A previous attempt crashed: delete the files it created (possibly partial), then rerun. |
| different config | Fail with `ConfigError` (exit 2). With `--force`, delete this block's previous outputs and rerun. |
| any, with `remove_previous: true` | Ignored; `out_dir` is cleared as before. |

Ownership is tracked per block, so blocks that share an `out_dir` are never touched by each other's cleanup. Blocks sharing an `out_dir` must not run concurrently.

### QC Summary JSON

**File:** `{out_file_pre}_qc_summary.json`

Schema varies by analysis type:

**All types:**
| Key | Type | Description |
|---|---|---|
| `analysis_type` | str | `"task_act"`, `"task_conn"`, or `"rest_conn"` |
| `fd_threshold` | float | FD threshold used for censoring |
| `censor_metric` | str | `"power_fd"` |
| `censor_prev_tr` | bool | Whether previous-TR censoring was enabled |
| `n_trs_total` | int | Total number of TRs |
| `n_trs_censored` | int | Number of censored TRs |
| `pct_censored` | float | Percentage of TRs censored |
| `psc_per_run` | list of dict | When `scale_to_psc` is true, per run: `run`, `n_mask_voxels`, and the count and percentage of guarded voxels (minimum or mean <= 0), capped voxels (maximum above twice the mean) and non-positive-mean voxels |
| `smoothing_per_run` | list of dict | With smoothing, per run: `run`, `fwhm_target_mm`, `acf_fwhm_input_mm`, `acf_fwhm_output_mm`, `mask_n_voxels`, `mask_fov_fraction` |

**task_act and task_conn additionally include:**
| Key | Type | Description |
|---|---|---|
| `hrf_model` | str | HRF model used (or `"custom (MODEL)"` if custom) |
| `dof` | int or null | Estimated degrees of freedom |
| `trials` | list of dict | One record per measured trial: `run`, `condition`, `onset`, `duration`, `estimability`, `survived` |
| `per_condition_trial_counts` | dict | Total trial count per condition |
| `per_condition_surviving_trials` | dict | Trials surviving censoring per condition |
| `contrast_labels` | list of str or absent | (task_conn only) Labels of connectivity contrasts computed, if any |

**rest_conn additionally includes:**
| Key | Type | Description |
|---|---|---|
| `per_run_dof` | list of int | Degrees of freedom per run |
| `per_run_censoring` | list of dict | Per-run stats: `n_trs_total`, `n_trs_censored`, `pct_censored` |

### Task Activation (`task_act`)

- `{out_file_pre}_min_outlier_epi.nii.gz` -- single-volume EPI frame with the lowest voxelwise outlier fraction (mandatory)
- `{out_file_pre}_psc.nii.gz` -- PSC-scaled 4D scan (when `scale_to_psc: true`)
- `{out_file_pre}_mean.nii.gz` -- voxelwise temporal mean (when `scale_to_psc: true`); `{out_file_pre}_run{N}_mean.nii.gz` per run with multi-run `run_lengths`
- `{out_file_pre}_concat_bucket_stats.nii.gz` -- AFNI bucket dataset with condition betas, t-stats, and contrasts
- `{out_file_pre}_concat_bucket_stats_index.json` -- JSON mapping every sub-brick label to its 0-based index
- `{out_file_pre}_concat_censor.1D` -- generated censor file
- `{out_file_pre}_concat_motion_prepared.1D` -- validated/truncated motion regressors
- `{out_file_pre}_concat_{label}_onsets.txt` -- per-condition AFNI onset files
- `{out_file_pre}_qc_summary.json` -- QC summary
- `{extract_out_file_pre}_{StatType}_bucket.nii.gz` (if `stat_buckets` enabled) -- multi-sub-brick NIfTI per stat type
- `{extract_out_file_pre}_{StatType}_index.json` (if `stat_buckets` enabled) -- JSON mapping condition/contrast labels to sub-brick indices per stat type
- `{extract_out_file_pre}_{StatType}_{average_type}_ptseries.csv` (if `stat_buckets` enabled and `template_path` set) -- parcellated CSV per stat type
- `{extract_out_file_pre}_raw_ptseries.csv` (if `extract_raw_ptseries: true`) -- pre-regression parcellated time series

### Task Connectivity (`task_conn`)

- `{out_file_pre}_min_outlier_epi.nii.gz` -- single-volume EPI frame with the lowest voxelwise outlier fraction (mandatory)
- `{out_file_pre}_psc.nii.gz` -- PSC-scaled 4D scan (when `scale_to_psc: true`)
- `{out_file_pre}_mean.nii.gz` -- voxelwise temporal mean (when `scale_to_psc: true`); `{out_file_pre}_run{N}_mean.nii.gz` per run with multi-run `run_lengths`
- `{out_file_pre}_concat_bseries_{condition}.nii.gz` -- per-condition trial-level beta series from 3dLSS
- `{out_file_pre}_concat_LSS_index.json` -- one record per 3dLSS sub-brick, in order: `{lss_index, beta_series_position, run, onset, condition, survived}`
- `{out_file_pre}_concat_bseries_{condition}_index.json` -- one record per beta-series sub-brick, surviving trials only: `{lss_index, beta_series_position, run, onset}`
- `{out_file_pre}_concat_censor.1D` -- generated censor file
- `{out_file_pre}_concat_motion_prepared.1D` -- validated/truncated motion regressors
- `{out_file_pre}_qc_summary.json` -- QC summary
- Extracted parcel beta series (if `extraction` enabled): CSV files
- `{extract_out_file_pre}_raw_ptseries.csv` (if `extract_raw_ptseries: true`) -- pre-regression parcellated time series
- Connectivity matrices (if `connectivity` enabled): tab-delimited text files
- Connectivity contrast outputs (if `contrasts` enabled with connectivity): contrast-level matrices (parcellated) or NIfTI maps (seed-to-voxel), using same naming convention as condition outputs with the sanitized contrast label

### Resting-State Connectivity (`rest_conn`)

- `{out_file_pre}_run{N}_min_outlier_epi.nii.gz` -- per-run single-volume EPI frame with the lowest voxelwise outlier fraction (mandatory)
- `{out_file_pre}_run{N}_psc.nii.gz` -- per-run PSC-scaled 4D scan (when `scale_to_psc: true`)
- `{out_file_pre}_run{N}_mean.nii.gz` -- per-run voxelwise temporal mean (when `scale_to_psc: true`)
- `{out_file_pre}_run{N}_residual_dtseries.nii.gz` -- per-run residual time series from 3dTproject
- `{out_file_pre}_concat_residual_dtseries.nii.gz` -- concatenated residual time series
- `{out_file_pre}_run{N}_censor.1D` -- per-run generated censor files
- `{out_file_pre}_run{N}_motion_prepared.1D` -- per-run validated/truncated motion regressors
- `{out_file_pre}_qc_summary.json` -- QC summary
- Extracted parcel time series (if `extraction` enabled): CSV files
- `{extract_out_file_pre}_run{N}_raw_ptseries.csv` (if `extract_raw_ptseries: true`) -- per-run pre-regression parcellated time series
- Connectivity matrices (if `connectivity` enabled): tab-delimited text files
- `{out_dir}/_sequenced_intermediates/run{N}/` (if `use_sequenced_bandpass: true`) -- per-run intermediate files (NTRP-interpolated BOLD, bandpass-filtered BOLD, NTRP-interpolated and bandpass-filtered nuisance regressors). Removed after each run unless `keep_run_res_dtseries: true`; preserved on failure regardless of flag.

---

## Quality Control

The pipeline performs automatic QC checks during execution. All checks are logged and key metrics are recorded in the QC summary JSON.

### PSC Input Check

PSC divides by each voxel's temporal mean, so scaled series sit near 100. A run in which 25% or more of non-constant voxels have a temporal mean <= 0 looks demeaned, and raises `InputError`. Use `scale_to_psc: false` for such data.

### Censor Warnings

- **>= 30% TRs censored:** A warning is logged indicating substantial motion artifact.
- **>= 50% TRs censored:** A strong warning is logged indicating the data may be unreliable.

### Trial Survival (`task_act`, `task_conn`)

After censoring, each trial's estimability is the share of its squared regressor on uncensored TRs, pooled over basis columns, from an uncensored `3dDeconvolve -nodata -stim_times_IM` design. A trial survives when this is above 0, so it is lost only when censoring removes its whole response. No higher minimum applies: a surviving trial with little of its response left stays in the analysis, and its beta is noisier by roughly 1 / estimability. In `task_conn`, a trial that doesn't survive stays in the 3dLSS model but leaves the beta series, and the LSS index records `survived: false` and `beta_series_position: null`.

- **< 2 surviving trials:** The condition is automatically dropped from the analysis with a warning. The pipeline continues with the remaining conditions. Any contrasts or extractions that depend on the dropped condition will also be skipped.
- **Exactly 2 surviving trials:** A warning is logged. The estimate for this condition will have very low power, but the analysis proceeds.

### Degrees of Freedom Pre-Flight Check

Before running the main AFNI regression, the pipeline computes estimated degrees of freedom:

`DOF = (uncensored TRs) - (number of regressors)`

For `task_conn`, DOF comes from the design matrix 3dLSS uses: its uncensored rows, minus its non-beta columns, minus 2 for each fit's trial regressor and the sum of the other trials.

Regressors include polynomial baselines: `-polort A` for task analyses (degree `1 + floor(longest run duration / 150 s)`, with degree + 1 regressors per run), and the simultaneous `rest_conn` backend's `-polort` per run.

- **DOF < 1:** The analysis aborts with a `ModelError` (exit code 5). This prevents AFNI from producing statistically invalid output. Consider relaxing the FD threshold or reducing model complexity.

---

## Runtime Validation

The pipeline performs two validation checks at startup, before any analysis blocks execute:

### 1. AFNI Binary Preflight

All 19 required AFNI binaries are checked for reachability. Discovery order for the AFNI home directory: (1) explicit `afni_home` parameter (programmatic API only), (2) parent directory of `shutil.which('afni')`, (3) `~/abin`. Unreachable binaries are accumulated and a single `ToolUnavailableError` (exit code 4) is raised listing all missing tools.

Required binaries: `3dDeconvolve`, `3dTproject`, `3dTstat`, `3dBandpass`, `3dROIstats`, `3dNetCorr`, `3dresample`, `3dinfo`, `3dToutcount`, `3dbucket`, `3dcalc`, `3dLSS`, `3dTcat`, `1dtranspose`, `3dBlurToFWHM`, `3dFWHMx`, `3dMean`, `3dBrickStat`, `3dTcorr1D`.

### 2. Version Lock Validation

Using the `tools.lock.yaml` shipped inside the installed package:
- **AFNI:** Runs `afni -ver`, parses the version string, and enforces strict exact-match comparison against the lockfile pin. `"PLACEHOLDER"` in the lockfile skips the check.
- **Python:** Compares `sys.version_info` major.minor against the lockfile's `python` field (patch ignored). A mismatch is advisory: it emits a medium-severity `PYTHON_VERSION_MISMATCH` warning and the run continues. `requires-python` in `pyproject.toml` defines which interpreters are supported; the pin records the version results were validated on. Deployments that need an exact interpreter should pin it in their environment (e.g. the container image).

An AFNI mismatch raises `ToolVersionError` (exit code 4). If the lockfile is missing from the installation, a low-severity `LOCKFILE_ABSENT` warning is emitted and version pinning is skipped.

---

## Exit Codes

| Code | Exception(s) | Meaning |
|------|-------------|---------|
| 0 | (none) | All analyses completed with no high-severity warnings |
| 1 | `GuardError` | Pipeline invariant violation; indicates a bug |
| 2 | `ConfigError`, `InputError` | Configuration or input error |
| 3 | (none; warning check) | All analyses completed but one or more high-severity warnings were raised |
| 4 | `ToolUnavailableError`, `ToolVersionError`, `ToolExecutionError` | External tool unavailable, version mismatch, or execution failure |
| 5 | `ModelError` | Model estimation failure: singularity, insufficient DOF, no surviving trials |

---

## CLI Flags

```
fmri-first-level-proc --config <path> [options]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--config` | str | (required) | Path to the YAML config file. |
| `--dry-run` | flag | off | Validate the config and input files, and print the analysis plan, without executing any analyses. Checks each scan's volume count and header TR, motion and tissue rows, columns and values, `run_lengths`, contrast grammar and condition references, timing-file conditions and onsets, and the template's atlas space. Writes no timing-error file. A run applies the same checks before its first step. |
| `--analyses` | list of int | all | Run only specific analysis block indices (0-based). E.g. `--analyses 0 2` runs the first and third blocks. |
| `--log-file` | str | none | Path to a log file. When set, logs are written to both console and file. |
| `--force` | flag | off | If a block's `out_dir` holds outputs from a different configuration (see [Run Manifest](#run-manifest)), delete that block's previous outputs and rerun instead of failing with a `ConfigError`. |

The legacy `run-first-level` command is a deprecated alias for `fmri-first-level-proc`. It emits a `CLI_DEPRECATED` warning before delegating.

---

## Exception Hierarchy

All pipeline exceptions inherit from `FmriFirstLevelError`, which carries an optional `context` dict for structured error metadata:

```
FmriFirstLevelError(Exception)
├── ConfigError          # Invalid config: missing required fields, incompatible options, schema violations
├── InputError           # Input file missing, malformed, wrong dimensions, or unreadable
├── ToolUnavailableError # External tool binary not found on PATH
├── ToolVersionError     # External tool binary found but version does not match lockfile pin
├── ToolExecutionError   # External tool command returned non-zero or failed to produce expected output
├── ModelError           # Data quality prevents model estimation: singularity, insufficient DOF, no surviving trials
└── GuardError           # Pipeline invariant violation: unexpected state indicating a bug
```
