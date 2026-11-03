# CLAUDE.md

## Project Overview:
This is a general purpose framework for doing first-level (within-participant post-processing including regression) analyses for fMRI data. Activation first-levels are available for task-based fMRI data and functional connectivity first-levels are available for both task-based and resting-state fMRI data. Written in Python and heavily utilizes AFNI.

This package is pip-installable from GitHub:
```
pip install git+https://github.com/tjkeding/fmri-first-level-proc.git
```

## Project Structure:
```
fmri_first_level_proc/               # Repository root
├── pyproject.toml                    # pip-installable packaging config
├── .gitignore                        # Ignored files when pushing to GitHub
├── README.md                         # GitHub README.md (primarily for future users)
├── INPUT_SPECIFICATION.md            # GitHub input spec file (primarily for future LLMs)
├── CHANGELOG.md                      # Release notes
├── fmri_first_level_proc/            # Python package
│   ├── __init__.py                   # Package init with public API exports
│   ├── bids.py                       # BIDS output path construction, dataset description, input discovery
│   ├── checkpoint.py                 # Append-only JSONL ledger (staged, completion, retired records)
│   ├── connectivity.py               # Parcellated (1ddot -dem) and seed-to-voxel (3dTcorr1D) connectivity
│   ├── engine.py                     # RunContext, StepIO, StageSpec, Output, Outcome; stage reuse and promotion
│   ├── estimability.py               # Trial estimability (pooled energy ratio), beta selection, survival
│   ├── events.py                     # BIDS/CONDITION timing parsing, build_event_table (Mode A/B)
│   ├── exceptions.py                 # FmriFirstLevelError hierarchy (7 subclasses)
│   ├── first_level_utils.py          # Shared utilities (logging, warnings, AFNI wrappers)
│   ├── first_level_config.py         # YAML config loader and validator (closed schema, ResolvedConfig)
│   ├── inputs.py                     # Read-only input checks for --dry-run
│   ├── names.py                      # Centralized output/intermediate path construction
│   ├── nuisance.py                   # Censoring (Power FD), task and rest nuisance regressors
│   ├── prep.py                       # PSC scaling, task model input routing, rest prep routing
│   ├── qc.py                         # QCKeySpec schema, merge_fragments, cross-producer dedup
│   ├── roi.py                        # ROI extraction/stats, template handling/resampling, roi_qc
│   ├── run_first_level.py            # Config-driven dispatch runner (CLI entry point)
│   ├── runsets.py                    # RunInfo/RunSets run-identity state machine
│   ├── runtime.py                    # AFNI binary preflight and version-lock validation
│   ├── smoothing.py                  # Voxelwise spatial smoothing (3dBlurToFWHM), data-derived mask
│   ├── task_act_first_level.py       # Task activation analysis pipeline
│   ├── task_conn_first_level.py      # Task beta series / connectivity pipeline
│   ├── rest_conn_first_level.py      # Resting-state residual / connectivity pipeline
│   └── tools.lock.yaml               # Packaged version lockfile (AFNI, Python, numpy, pandas)
├── environment.yaml                  # Conda environment specification
├── example_config.yaml               # Example YAML config for the package
├── AID_LOG.md                        # AI Development Log (AID Framework disclosure)
├── .aid/                             # AID Framework audit trail
│   ├── project_claude.md             # Sanitized project configuration
│   └── reports/                      # Structured development reports
```

## Project Impact:
*   Meant as a free-standing, pip-installable Python package to make first-level processing of fMRI data easy to access, implement, and document
*   Users should not need to make changes to the package, so it should be robust enough to handle the vast majority of typical use cases
*   Will be called within a broader preprocessing pipeline so inputs and outputs can be standardized rigorously
