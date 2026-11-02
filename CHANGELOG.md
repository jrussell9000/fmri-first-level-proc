# Changelog

All notable changes to this fork of fmri-first-level-proc. Versions follow
[Semantic Versioning](https://semver.org/). Issue numbers refer to
`jrussell9000/fmri-first-level-proc`.

## [4.0.1] — 2026-11-02

### Changed

- **Python version mismatch is now a warning** (#3). A Python minor version that
  differs from the `tools.lock.yaml` pin emits a medium-severity
  `PYTHON_VERSION_MISMATCH` warning and the run continues. In 4.0.0 it exited 4,
  which made every run fail on interpreters that `requires-python` allows (3.12,
  3.13). The AFNI pin is still enforced strictly.

### Fixed

- `docs/input_specification.md` no longer says the lockfile is read from the
  repository root.

## [4.0.0] — 2026-11-01

Major because the module layout changed with no compatibility shims, and because
reruns into an `out_dir` holding outputs from a different config now fail instead
of silently reusing them. The CLI name, its existing flags, exit codes, config
schema and output filenames are unchanged.

### Breaking

- **Module layout.** The package moved to `src/fmri_first_level_proc/`, and
  `first_level_utils.py` was split up. Old import paths no longer exist:

  | Old | New |
  |---|---|
  | `run_first_level` | `cli` |
  | `first_level_config` | `config` |
  | `task_act_first_level`, `task_conn_first_level`, `rest_conn_first_level` | `pipelines.task_act`, `pipelines.task_conn`, `pipelines.rest_conn` |
  | `first_level_utils` | `design`, `preprocessing`, `templates`, `connectivity`, `afni`, `reporting`, `fileutils` |

  The public API in `fmri_first_level_proc/__init__.py` (`load_and_validate`,
  `ResolvedConfig`, `DISPATCH`, `setup_logging`, `FirstLevelResult`, the warning
  helpers, `ToolVersionError`) is unchanged.
- **Stale-output guard.** Each block writes `{out_file_pre}_manifest.json`. If a
  rerun finds a manifest from a different configuration, it fails with
  `ConfigError` (exit 2). Pass `--force` to delete that block's previous outputs and
  rerun. See "Run Manifest" in `docs/input_specification.md`.
- **Version pinning is now active for installed packages.** `tools.lock.yaml` ships
  as package data. Previously it was looked up at the repository root, so it was
  never found after a normal `pip install`, and the check was skipped. AFNI and
  Python mismatches now exit 4.
- **AFNI pin is now `26.3.07`** (was `26.0.09`).
- **Removed** `checkpoint.py`. It was never wired into the pipelines, and its
  artifact patterns matched none of the outputs. Also removed the unused argparse
  helpers from the old per-script CLIs (`dir_path_exists`, `file_path_exists`,
  `valid_string_list`, `valid_stat_type`, `valid_ave_type`, `valid_conn_type`).

### Fixed

- **Zstat stat buckets crashed `task_act`** (#4). `3dinfo -subbrick_info` quotes
  labels, so the T-to-Z temp filename contained a quote and `3dcalc` rejected it
  (exit 4). Labels now come from `3dinfo -label` via `parse_bucket_labels`. As a
  result:
  - index keys and parcellated CSV row labels are the plain condition and contrast
    labels;
  - contrast labels lose 3dDeconvolve's `_GLT` suffix;
  - `Fstat` and `R^2` buckets now match; they never did before;
  - multi-basis conditions are labelled `name#k`.
- **`fishZ` + `pcorr` wrote regression betas** (#1). The 3dNetCorr `PCB` section
  holds partial-correlation regression coefficients, not a Fisher Z. The matrix is
  now `arctanh(PC)`, with AFNI's |z| ≤ 4 cap. A `.netcc` file missing the required
  section now raises instead of writing an empty matrix.
- **Sequenced `rest_conn` failed on `.txt` 1D inputs.** AFNI reads transposed 1D
  data only from `.1D` paths, and the tissue-derivative files are written as `.txt`.
  Non-`.1D` inputs are now copied to `.1D` first.
- **Deprecated `DataFrame.rename(inplace=True)` removed** (#2).
- **Invalid `num_cores`** now raises `ConfigError` (exit 2) instead of crashing with
  an uncaught `ValueError` (exit 1).

### Added

- **`num_cores: auto`.** Resolves to the first of: `OMP_NUM_THREADS` (capped at the
  cgroup CPU limit); the cgroup CPU limit; the schedulable CPUs.
- **CPU budget.** `num_cores` is exported to every AFNI call as `OMP_NUM_THREADS`.
  Before, OpenMP-enabled AFNI programs started one thread per host core, which
  oversubscribes CPU-limited containers.
- **Parallel independent work within the budget:** per-run residuals and
  min-outlier EPI/PSC scaling in `rest_conn`, and per-condition pbseries and
  3dNetCorr in `task_conn`.
- **`--force`** CLI flag (see Breaking).
- **`python -m fmri_first_level_proc`.**
- **Tests**, from none to 114:
  - unit tests;
  - a fake-AFNI harness that runs every pipeline end to end;
  - an opt-in real-AFNI suite (`pytest -m afni`, image `tests/docker/Dockerfile`)
    that pins every AFNI output format the package parses and runs every pipeline
    on synthetic data.

### Changed

- **Fewer `3dinfo` calls.** Template and scan validation makes one combined
  `3dinfo` call per file instead of four, cached per file. A `task_act` run with a
  template goes from 16 calls to 2.
- **Standard-library path handling.** `os.path` and `glob` were replaced with
  `pathlib`. AFNI commands are logged with `shlex` quoting, and
  `validate_custom_hrf` runs in a temporary directory.
- **Packaging.**
  - The version is defined once, in `__version__`.
  - Documentation moved to `docs/`, example configs to `examples/`.
  - A conventional `.gitignore` replaces the whitelist, which hid new files from
    tools.
- **pytest treats warnings as errors.**

## [3.1.0]

Upstream release (`tjkeding/fmri-first-level-proc`) plus fork fixes, as pinned by
cloudpipe at `31d716a`.
