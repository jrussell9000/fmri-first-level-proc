# Changelog

All notable changes to this fork of fmri-first-level-proc. Versions follow
[Semantic Versioning](https://semver.org/). Issue numbers refer to
`jrussell9000/fmri-first-level-proc`.

## [5.0.0] — 2026-11-03

Major because results change for every analysis type, so existing outputs need a rerun.
Ported by hand from upstream's v4.0.0 rewrite (`tjkeding/fmri-first-level-proc@77221b2`): its
engine, schema, connectivity backend and module layout are not. New `ResolvedConfig` fields change
each block's config hash, so a rerun into an `out_dir` written by 4.x fails with `ConfigError` until
you pass `--force`.

### Breaking

- **Censoring uses Power et al. (2012) framewise displacement**, on a 50 mm sphere, instead of
  AFNI enorm through `1d_tool.py -censor_motion`. The metrics are not interchangeable
  (0.873 x enorm <= FD <= 2.30 x enorm), so the same `fd_threshold` censors differently. If you
  chose a threshold against enorm, choose it again. The FD series is written to
  `{pre}_{label}_fd.1D`, and QC records `censor_metric`. `1d_tool.py` is no longer required.
- **`rest_conn` detrends.** The simultaneous backend uses `3dTproject -polort 2` when
  `bandpass[0] > 0`, else `1 + floor(run duration / 150 s)`, instead of `-polort -1`. The
  sequenced backend drops `3dBandpass -nodetrend`, so BOLD and regressors get its quadratic
  detrend. Sinusoids don't span quadratic trends, so these stayed in the residuals.

- **Trial survival uses regressor energy, not the onset TR.** A trial survives when any of its
  squared regressor falls on uncensored TRs, pooled over basis columns. Before, censoring only the
  near-silent onset TR lost a trial, and censoring the whole response after it kept one. In
  `task_conn`, a trial that doesn't survive now leaves the beta series; before, it stayed as an
  all-zero map. There is no higher minimum, so low-energy trials stay and are noisier.
- **Runs validate their input files first**, and `--dry-run` applies the same checks: each scan's
  volume count and header TR, motion and tissue rows, columns and values, `run_lengths`, conditions,
  onsets and the template's atlas space. Inputs that used to reach AFNI, or a wrong TR that went
  unnoticed, are now `InputError` (exit 2).
- **Onsets outside the scan** raise `InputError`, for every row of the timing file, and a run
  writes `{pre}_timing_errors.json`.
- **PSC refuses demeaned input**: `InputError` when 25% or more of non-constant voxels have a
  temporal mean <= 0.
- **Output prefixes can't repeat across blocks** that share an `out_dir`, now including the
  extraction and connectivity prefixes, with directories compared after normalization.
- **Contrast errors** are reported at config validation, so `--dry-run` catches them.
- `3dBlurToFWHM`, `3dFWHMx`, `3dMean`, `3dBrickStat` and `3dTcorr1D` are required binaries.

### Added

- **Voxelwise smoothing** (`smoothing: {enabled, fwhm}`) for all analysis types, off by default:
  `3dBlurToFWHM -ACF` in a data-derived mask, writing `_s{N}mm` siblings, including a second
  `task_act` GLM and `task_conn` 3dLSS. Parcel-level outputs are never smoothed. Smoothed seed maps
  use the unsmoothed seed series, through `3dTcorr1D`.
- **`roi_zero_handling`** (`exclude`, the existing behaviour, or `include`).
- **QC:** `trials`, `psc_per_run` and `smoothing_per_run`.
- **Beta-series indexes:** `{pre}_concat_LSS_index.json` and `{pre}_concat_bseries_{cond}_index.json`
  map each sub-brick to its trial.
- **`paths.run_lengths`** for `task_act` and `task_conn`: the TRs per run of a concatenated scan.
  Each run gets its own `-polort A` baseline (`3dDeconvolve -concat`) and PSC mean, written to
  `{pre}_run{N}_mean.nii.gz`. FD and tissue derivatives are 0 at each run's first TR, and
  onsets stay global (`-global_times`). Without the key a scan is still one run.

### Fixed

- **Concatenated n-back was modelled as one run.** ABCD staging now passes `run_lengths`. Before,
  one polynomial spanned both runs, the step between their baselines went unmodelled, one PSC
  mean covered both, and the jump between runs could censor run 2's first TR.
- **The DOF pre-flight check undercounted polynomials.** `-polort A` adds degree + 1 regressors
  per run, with the degree taken from the longest run. It counted one fewer, for one run.
- **Non-finite motion values** now raise `InputError`. NaN compares False against the threshold,
  so those TRs would not be censored.

## [4.2.0] — 2026-11-03

ABCD staging only: these change n-back results on GE sessions and on any session a rule
now excludes or repairs. The framework's core is unchanged.

### Changed

- **n-back trims by each run's `dummy` row**, not its NSS count. Hagler et al. 2019's GE
  discard of 5 and 16 frames is out of date; ABCD now discards 4 and 15. The older count
  lost each GE run's first cue, and in about half of two-run GE sessions a bare 0-back
  condition then fell below 2 trials. Rest still trims its NSS count.
- **`--run-validity` is required.** Only n-back runs the table marks usable are staged.
- **A session whose rules exclude everything now finishes**, recording why, rather than
  failing, so a queue doesn't resubmit it.

### Added

- **`fmri-first-level-abcd-validity`** builds the per-run table from ABCD's E-Prime valid-run
  count and run-level results.
- **Exclusions**, each recorded per run: `unexpected-frame-count` (a wrong scanner label or a
  short run), `predates-ge-timing-correction`, `unexpected-dummy`, `no-dummy-row`,
  `no-task-events`, and the table's reasons.

### Fixed

- **A run with no task events** stayed in the concatenated BOLD, modelled as baseline.
- **A short run's events** could spill into the next run's time.
- **Zero-`dummy` runs**, whose onsets carry no pad, were modelled 6.4 s early and lost 3 events.
- **A next run's first cue misfiled at the end of a run** excluded that whole run. The cue now
  moves back to its run.

## [4.1.0] — 2026-11-02

### Added

- **`fmri_first_level_proc.abcd`** and the **`fmri-first-level-abcd`** CLI: stage one ABCD
  session from a local directory and run its analyses, with `proc_config_final.yaml`
  as the template. Moved from cloudpipe's `stage_first_level.py`, with its rules and
  tests unchanged. It works only on local files. The core does not import it, and it
  needs the new `abcd` extra (`nibabel`, `scipy`). See `docs/abcd_staging.md`.

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
