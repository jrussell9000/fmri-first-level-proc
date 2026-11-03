# fmri-first-level-proc

A YAML-driven Python framework for first-level (within-participant) fMRI analysis built on AFNI: task activation, task connectivity (beta series), and resting-state connectivity.

## Analyses

- **Task activation (`task_act`):** GLM with `3dDeconvolve` (`GAM`, `BLOCK`, `dmBLOCK`, `SPMG1` or custom AFNI HRFs), linear contrasts, stat-bucket extraction (`Coef`, `Tstat`, `Fstat`, `R^2`, `Zstat`) with label-keyed index files, and parcel-level statistics.
- **Task connectivity (`task_conn`):** trial-level beta series with `3dLSS`, parcel beta series, parcellated or seed-to-voxel connectivity, and connectivity contrasts. Non-beta conditions are modeled as nuisance regressors.
- **Resting-state connectivity (`rest_conn`):** per-run nuisance regression and bandpass filtering with `3dTproject`, concatenated residuals, parcel time series and connectivity. An optional sequenced backend interpolates censored frames, filters BOLD and nuisance regressors at the same passband and then regresses, following Power et al. (2014) and Hallquist et al. (2013), as benchmarked in Ciric et al. (2017), with linear NTRP rather than spectral interpolation.

## Key Features

- **Motion censoring:** Power et al. (2012) framewise displacement (50 mm sphere; a TR is censored when FD exceeds `fd_threshold`), optional previous-TR censoring and a respiration notch filter for rest. AFNI enorm is reported for reference only.
- **Multi-run inputs:** per-run files (Mode A) or one concatenated file with `run_lengths` (Mode B), with integer run labels. Runs with too few uncensored TRs (task) or DOF < 1 (rest) are excluded and the remaining runs proceed.
- **Trial estimability:** per-trial regressor-energy estimability determines trial survival; conditions below the floor (2 for `task_act`, 3 for `task_conn`) are dropped together with dependent contrasts.
- **Optional voxelwise smoothing:** `3dBlurToFWHM` to a target FWHM within a data-derived mask, written as `_s{N}mm` siblings; parcel-level outputs are always unsmoothed.
- **Percent signal change scaling, ROI zero handling, template resampling and ROI QC** (coverage and low-baseline records).
- **Stage reuse:** an append-only ledger per analysis. Each stage reruns only when its inputs, settings, upstream stages or tool versions change; QC and warnings are replayed on reuse; obsolete outputs are retired.
- **Structured QC and warnings:** a schema-validated `{out_file_pre}_qc_summary.json` and graded warnings from a closed code table.
- **BIDS input discovery** from one or more derivatives directories, with exact entity matching and alignment of every discovered file by run label.
- **Closed config schema and strict values:** unknown, misplaced or removed keys are reported together before anything runs; types, finite numbers, file-name-safe prefixes and labels, and required inputs are checked during validation.
- **Per-block isolation:** each analysis block in a config is validated and run independently, and its outcome (including the reason for a failure) is recorded in its QC summary under `run_status`.

## Prerequisites

- Python >= 3.12
- [AFNI](https://afni.nimh.nih.gov/pub/dist/doc/htmldoc/background_install/main_toc.html) >= 26.0.09, on `PATH`
- Python dependencies (installed automatically): `numpy>=2.4.2`, `pandas>=3.0.1`, `pyyaml`, `packaging`

A conda specification is provided in `environment.yaml` (AFNI is installed separately).

## Installation

```bash
pip install git+https://github.com/tjkeding/fmri-first-level-proc.git
```

## Quick Start

1. Copy `example_config.yaml` and set your paths, conditions and options.
2. Validate the config and the input files of every block, and print the analysis plan:
   ```bash
   fmri-first-level-proc --config my_config.yaml --dry-run
   ```
3. Run:
   ```bash
   fmri-first-level-proc --config my_config.yaml
   ```

Output prefixes and condition labels must be file-name-safe (letters, digits, `.`, `_`, `-`). With BIDS discovery (`derivatives_dirs` plus `subject`), `task` is required and IDs must be quoted strings (`subject: "01"`). Motion files must be headerless with translations first (`tx ty tz rx ry rz`, mm and degrees). Event files may use BIDS (`onset`, `duration`, `trial_type`) or CONDITION (`CONDITION`, `ONSET`, `DURATION`) columns, tab- or comma-delimited. See [INPUT_SPECIFICATION.md](./INPUT_SPECIFICATION.md) for every input contract.

## Primary Outputs

| Analysis | Primary output (stable name) |
|---|---|
| `task_act` | `{out_file_pre}_concat_bucket_stats.nii.gz` |
| `task_conn` | `{out_file_pre}_concat_LSS.nii.gz` |
| `rest_conn` | `{out_file_pre}_concat_residual_dtseries.nii.gz` |

Every statistical bucket and beta series has an index file identifying each sub-brick by AFNI label or trial; resolve sub-bricks by key rather than by position.

## CLI Reference

The CLI entry point is `fmri-first-level-proc`.

| Flag | Description |
|---|---|
| `--config` | Path to the YAML config file (required) |
| `--dry-run` | Validate the config and each block's input files (volumes, header TR, grids, motion and tissue files, events and onsets, template) without executing or writing |
| `--analyses` | Run only the given 0-based block indices, e.g. `--analyses 0 2` |
| `--log-file` | Also write logs to this file |

Each block is validated and run independently: a block with an invalid config, invalid inputs or a runtime failure stops at its first error, and the remaining blocks still run.

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | All analyses completed with no high-severity warnings |
| 1 | Pipeline invariant violation (`GuardError`) or unexpected error; indicates a bug |
| 2 | Configuration or input error (`ConfigError`, `InputError`) |
| 3 | All analyses completed but one or more high-severity warnings were raised |
| 4 | External tool unavailable, below the minimum version, or failed (`ToolUnavailableError`, `ToolVersionError`, `ToolExecutionError`) |
| 5 | Model estimation failure (`ModelError`): insufficient DOF, no estimable condition, every run excluded |

With several blocks, the exit code is that of the first failing block in config order; with no failing block it is 3 when any high-severity warning was raised, otherwise 0.

## Exception Hierarchy

All pipeline exceptions inherit from `FmriFirstLevelError`, which carries an optional `context` dict:

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

## Programmatic Usage

```python
from fmri_first_level_proc import load_and_validate, setup_logging, DISPATCH, get_warnings

logger = setup_logging("my_analysis")
configs = load_and_validate("my_config.yaml", logger)

for config in configs:
    result = DISPATCH[config.analysis_type](config, logger)
    print(config.analysis_name, result.status, len(result.output_files))

high = [w for w in get_warnings() if w["severity"] == "high"]
```

`load_and_validate()` returns a list of `ResolvedConfig` objects (one per block) and raises on the first invalid block; `load_and_validate_blocks()` returns one `BlockResolution` per block (its resolved config or its error). Keyword overrides are merged into every block before validation. Each pipeline `run()` returns a `FirstLevelResult` with `status`, `output_dir`, `warnings`, `qc_summary`, `output_files` and `intermediate_files`; on failure it raises, after recording the error in the block's `qc_summary.json` (`run_status`).

Public exports: `load_and_validate`, `load_and_validate_blocks`, `BlockResolution`, `ResolvedConfig`, `setup_logging`, `FirstLevelResult`, `graded_warning`, `get_warnings`, `clear_warnings`, `DISPATCH`, `ToolVersionError`, `__version__`.

## Runtime Validation

At startup the package verifies that its 19 AFNI binaries are reachable and checks AFNI, Python, numpy and pandas against the lockfile packaged with it (`fmri_first_level_proc/tools.lock.yaml`). A version below the recorded minimum raises `ToolVersionError` (exit code 4); a version that differs from the validated version emits an `UNVALIDATED_VERSION` warning. Installed versions are recorded in each QC summary and in every stage hash, so a version change reruns all stages.

## Stage Reuse and Reruns

Re-running a config reuses completed stages. A stage reruns when it has no completion record, when its hash changes (its config fields, the content of its derived inputs such as censor, motion, onset, tissue and template files, its upstream stages or tool versions), when a recorded output is missing, when an upstream stage ran, or when its last run had failed runs. Scan files are hashed by path, not content: after replacing a scan in place, set `remove_previous: true` (which removes only this analysis's ledger-recorded outputs) or use a new `out_dir`. `qc_summary.json` lists the reused stages.

## Detailed Documentation

- [INPUT_SPECIFICATION.md](./INPUT_SPECIFICATION.md): complete config schema, file formats, outputs, identifiers, QC schema, warnings and stage reuse
- [example_config.yaml](./example_config.yaml): annotated example of all three analysis types
- [CHANGELOG.md](./CHANGELOG.md): release notes, including breaking changes in 4.0.0

## References

- Ciric, R., et al. (2017). Benchmarking of participant-level confound regression strategies for the control of motion artifact in studies of functional connectivity. *NeuroImage*, 154, 174-187.
- Hallquist, M. N., Hwang, K., & Luna, B. (2013). The nuisance of nuisance regression. *NeuroImage*, 82, 208-225.
- Power, J. D., et al. (2012). Spurious but systematic correlations in functional connectivity MRI networks arise from subject motion. *NeuroImage*, 59(3), 2142-2154.
- Power, J. D., et al. (2014). Methods to detect, characterize, and remove motion artifact in resting state fMRI. *NeuroImage*, 84, 320-341.
