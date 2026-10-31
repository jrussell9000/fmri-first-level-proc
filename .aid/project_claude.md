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
├── tools.lock.yaml                   # AFNI and Python version pins for reproducibility
├── fmri_first_level_proc/            # Python package
│   ├── __init__.py                   # Package init with public API exports
│   ├── bids.py                       # BIDS derivative path construction, dataset description, input discovery
│   ├── checkpoint.py                 # Processing DAG: append-only JSONL ledger, config-hash invalidation
│   ├── exceptions.py                 # FmriFirstLevelError hierarchy (7 subclasses)
│   ├── first_level_utils.py          # Shared utilities (logging, AFNI wrappers, ROI extraction, connectivity)
│   ├── first_level_config.py         # YAML config loader and validator (3-stage pipeline, ResolvedConfig)
│   ├── run_first_level.py            # Config-driven dispatch runner (CLI entry point)
│   ├── runtime.py                    # AFNI binary preflight and version-lock validation
│   ├── task_act_first_level.py       # Task activation analysis pipeline
│   ├── task_conn_first_level.py      # Task beta series / connectivity pipeline
│   └── rest_conn_first_level.py      # Resting-state residual / connectivity pipeline
├── environment.yaml                  # Conda environment specification
├── example_config.yaml               # Example YAML config for the package
├── example_subj.timing.csv           # Example task timing file
├── AID_LOG.md                        # AI Development Log (AID Framework disclosure)
├── .aid/                             # AID Framework audit trail
│   ├── project_claude.md             # Sanitized project configuration
│   └── reports/                      # Structured development reports
```

## Project Impact:
*   Meant as a free-standing, pip-installable Python package to make first-level processing of fMRI data easy to access, implement, and document
*   Users should not need to make changes to the package, so it should be robust enough to handle the vast majority of typical use cases
*   Will be called within a broader preprocessing pipeline so inputs and outputs can be standardized rigorously
