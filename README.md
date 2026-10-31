# fmri-first-level-proc

A YAML-driven Python framework for first-level fMRI analysis (Task Activation, Task Connectivity, and Resting-State Connectivity) built on AFNI.

## Key Features

- **Three Analysis Pipelines:**
  - **Task Activation (`task_act`):** GLM via `3dDeconvolve`. Supports multiple HRF models, linear contrasts, optional percent signal change (PSC) scaling, stat-bucket extraction, and parcel-level statistics.
  - **Task Connectivity (`task_conn`):** Beta series estimation via `3dLSS`. Supports parcel beta series extraction, functional connectivity, connectivity contrasts, and PSC scaling.
  - **Resting-State Connectivity (`rest_conn`):** Residual time series via `3dTproject` with bandpass filtering. Supports parcel time series extraction, functional connectivity, PSC scaling, and an optional sequenced denoising path (separate BOLD and nuisance bandpass filtering per Ciric et al. 2017) that eliminates the DOF cost of bandpass-implied regressors.
- **Config-Driven:** Define complex multi-analysis batches in a single YAML file.
- **BIDS Input Discovery:** Optionally discover preprocessed input files from one or more BIDS derivatives directories, reducing per-subject path boilerplate.
- **Robustness:** Automated QC, motion censoring (degrees-only convention; column order `[tx, ty, tz, rx, ry, rz]`), trial survival checks, DOF pre-flight verification, and mandatory minimum-outlier EPI frame extraction for alignment QC.
- **Runtime Validation:** Preflight binary reachability checks for all required AFNI tools. Optional version pinning via `tools.lock.yaml` for AFNI and Python, with graceful fallback when the lockfile is absent.
- **Warning Accumulator:** Graded warning system (`low`/`medium`/`high` severity) with structured records accessible via the `get_warnings()`/`clear_warnings()` API. High-severity warnings trigger exit code 3.
- **Processing DAG:** Append-only JSONL checkpoint ledger with config-hash invalidation and cascade rerun for resumable pipelines.
- **Exception Hierarchy:** Typed exceptions (`ConfigError`, `InputError`, `ToolUnavailableError`, `ToolVersionError`, `ToolExecutionError`, `ModelError`, `GuardError`) map to distinct exit codes for programmatic error handling.
- **Pre-Regression Extraction:** Optional `extract_raw_ptseries` toggle to capture parcellated time series before nuisance regression.
- **Parallel Processing:** Native AFNI multi-core support.

## Prerequisites

- Python >= 3.12
- [AFNI](https://afni.nimh.nih.gov/pub/dist/doc/htmldoc/background_install/main_toc.html) (must be on your PATH)
- Dependencies: `numpy`, `pandas`, `pyyaml`

## Installation

```bash
pip install git+https://github.com/tjkeding/fmri-first-level-proc.git
```

## Quick Start

1.  **Configure:** Copy and edit `example_config.yaml` to define your analyses and paths.
2.  **Dry-Run:** Validate your configuration and view the execution plan:
    ```bash
    fmri-first-level-proc --config my_config.yaml --dry-run
    ```
3.  **Execute:** Run the full pipeline:
    ```bash
    fmri-first-level-proc --config my_config.yaml
    ```

## CLI Reference

The primary CLI entry point is `fmri-first-level-proc`. The legacy `run-first-level` command is a deprecated alias that emits a warning before delegating.

| Flag | Description |
|---|---|
| `--config` | Path to YAML config file (required) |
| `--dry-run` | Validate config and print plan without executing |
| `--analyses` | Run only specific block indices (0-based), e.g. `--analyses 0 2` |
| `--log-file` | Write logs to file in addition to console |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All analyses completed with no high-severity warnings |
| 1 | Pipeline invariant violation (`GuardError`); indicates a bug |
| 2 | Configuration or input error (`ConfigError`, `InputError`) |
| 3 | All analyses completed but one or more high-severity warnings were raised |
| 4 | External tool unavailable, version mismatch, or execution failure (`ToolUnavailableError`, `ToolVersionError`, `ToolExecutionError`) |
| 5 | Model estimation failure (`ModelError`): singularity, insufficient DOF, etc. |

## Exception Hierarchy

All pipeline exceptions inherit from `FmriFirstLevelError`, which carries an optional `context` dict for structured error metadata:

```
FmriFirstLevelError
├── ConfigError          # Invalid config: missing fields, schema violations
├── InputError           # Input file missing, malformed, or unreadable
├── ToolUnavailableError # AFNI binary not found on PATH
├── ToolVersionError     # AFNI/Python version does not match lockfile pin
├── ToolExecutionError   # AFNI command returned non-zero or missing output
├── ModelError           # Singularity, insufficient DOF, no surviving trials
└── GuardError           # Pipeline invariant violation (bug)
```

## Programmatic Usage

The pipeline is designed to be used both as a CLI tool and a Python library.

### Config-Driven API

```python
from fmri_first_level_proc import load_and_validate, setup_logging, DISPATCH

logger = setup_logging("my_analysis")
configs = load_and_validate("my_config.yaml", logger)

for config in configs:
    result = DISPATCH[config.analysis_type](config, logger)
    print(f"{config.analysis_name}: {result.status}, warnings={len(result.warnings)}")
```

`load_and_validate()` returns a `list[ResolvedConfig]`, where each element is a fully validated, resolved configuration dataclass for one analysis block. `DISPATCH` maps analysis type strings (`"task_act"`, `"task_conn"`, `"rest_conn"`) to the corresponding pipeline `run()` function. Each `run()` returns a `FirstLevelResult` dataclass.

### Warning Accumulator API

```python
from fmri_first_level_proc import get_warnings, clear_warnings

clear_warnings()
# ... run pipeline(s) ...
warnings = get_warnings()
high_severity = [w for w in warnings if w["severity"] == "high"]
```

### Public Exports

The package exposes these names in `__init__.py`:

- `load_and_validate`, `ResolvedConfig` (config pipeline)
- `setup_logging` (structured logging)
- `FirstLevelResult` (pipeline result dataclass)
- `graded_warning`, `get_warnings`, `clear_warnings` (warning accumulator)
- `DISPATCH` (analysis type to pipeline function mapping)
- `ToolVersionError` (for callers that catch version mismatches)

## Runtime Validation

When `tools.lock.yaml` is present at the repository root, the pipeline validates installed AFNI and Python versions against the pinned values at startup. Version mismatches raise `ToolVersionError` (exit code 4). When the lockfile is absent (e.g., pip-installed users), a low-severity warning is emitted and version pinning is skipped.

## Detailed Documentation

For exhaustive details on YAML parameters, input file formats, output file naming, and QC rules, see:
- [**INPUT_SPECIFICATION.md**](./INPUT_SPECIFICATION.md)
- [**example_config.yaml**](./example_config.yaml)
