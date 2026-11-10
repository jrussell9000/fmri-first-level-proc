# This fork

This is a fork of [tjkeding/fmri-first-level-proc](https://github.com/tjkeding/fmri-first-level-proc).
It runs upstream's analysis core unchanged and adds `fmri_first_level_proc/abcd/`, which stages
one ABCD session of [cloudpipe](https://github.com/jrussell9000/cloudpipe) func derivatives and
runs the core on it. Every difference from upstream is one of the commits or files listed here,
and CI fails if that stops being true.

**Upstream base:** `e40d1bc6f519b9a61996a594b395fef4ec9c9fd2`

**Fork version:** `4.0.0+cp.10`, in `pyproject.toml`. The part before the `+` is upstream's
version and the rest counts fork releases on it. `__version__` in `__init__.py` stays upstream's
value, so an analysis's QC reports the version of the core that ran it, and
`fmri-first-level-abcd` records the fork version in its result.

## Differences from upstream

### Upstream files changed

The core's Python modules are not on this list. `.github/scripts/check_fork_ledger.py` compares
the table with `git diff` from the upstream base, so a change to any other upstream file fails CI
until it is listed here with its reason.

<!-- ledger:start -->
| Status | File | Why |
|---|---|---|
| M | `.gitignore` | Upstream ignores everything by default, so the fork's paths need whitelisting |
| M | `pyproject.toml` | The fork version, the `abcd` extra, its two scripts, its package data and the `afni` test marker |
| D | `.aid/reports/fmri-first-level-proc_publish_20260911_160000.md` | It names a participant, and this fork holds no subject-keyed data |
| M | `fmri_first_level_proc/tools.lock.yaml` | `validated` names the versions cloudpipe's image runs and CI tests: AFNI 26.3.07, numpy 2.5.4, pandas 3.1.1. Minimums are upstream's |
<!-- ledger:end -->

### Files added

Everything else in the fork is a new file under one of these paths:

<!-- added:start -->
- `.github/`
- `FORK.md`
- `docs/`
- `fmri_first_level_proc/abcd/`
- `tests/`
<!-- added:end -->

### Commits

Each commit is one decision and can be read or reverted alone. The table covers the rebuild;
`git log <upstream base>..HEAD` lists everything since, and "Fork releases" below describes it.

| Commit | Change |
|---|---|
| `e41eb7b` | Add `abcd/` staging on the upstream core |
| `c94674c` | Keep n-back runs as separate files |
| `305f200` | Pool 0-back cues into `target_0back` |
| `9307dda` | Add the orchestrator comparison |
| `c5cf62e` | Adopt GAM for `nback_act`, previous-frame censoring for rest, and no `instruction` betas |
| `f2fa2bc` | Record masking and frame-count findings in the comparison |
| `812467a` | Adopt the 29 `nback_conn` contrasts |
| `a47175c` | Exclude rest runs with non-finite motion |
| `0c751a9` | Exclude any run with non-finite motion, and state the bandpass method |
| `5cf3572` | Record WM, CSF and global signal measurements in the comparison |
| `57cc57f` | Compute the rest global signal from the BOLD |
| `cafe83f` | Remove the upstream report listed above |

This page, CI and the version are the commit after these.

### Compared with upstream's orchestrator

Upstream runs its core through
[ABCD_fmri_orchestrator_S3](https://github.com/tjkeding/ABCD_fmri_orchestrator_S3). `abcd/` does
that work here and shares no code with it. [docs/orchestrator_comparison.md](docs/orchestrator_comparison.md)
records every difference, why it exists, and the orchestrator commit it was compared against.

## Following upstream

`.github/workflows/upstream-watch.yml` runs each Monday and fails when upstream or the
orchestrator has moved past the commits recorded in this repository. Its summary lists the new
commits. GitHub turns off a scheduled workflow after 60 days without repository activity, so
re-enable it if the Actions tab says it is off.

To take upstream's changes:

```bash
git remote add upstream https://github.com/tjkeding/fmri-first-level-proc.git  # once
git fetch upstream main
git log --oneline <upstream base>..upstream/main
git merge upstream/main
```

Then set **Upstream base** above to the merged commit, and take a new fork version, such as
`4.1.0+cp.1`. Merge rather than rebase, so the commits listed above keep their ids. Upstream's
tests are not published, so `tests/` covers only the fork's code; run the real-AFNI tests and
compare one session's results before releasing.

For the orchestrator, read its new commits, update the tables in the comparison, and change the
commit named there.

## Reversing it

- **One decision:** `git revert <commit>`, using the table above.
- **The whole fork:** delete the paths under "Files added", and restore the upstream files with
  `git checkout <upstream base> -- .gitignore pyproject.toml`. What remains is upstream's core.
  The removed report stays removed unless you restore it by its path.

## The older fork

Branch `legacy-5.0` holds the fork as it was before it was rebuilt on upstream's 4.0 core: a
refactored core with the `src/` layout. Tags `v4.1.0`, `v4.2.0` and `v5.0.0` belong to that line.
They are not ancestors of `main`, and `v5.0.0` is older than `4.0.0+cp.1` despite its number.

## Fork releases

### 4.0.0+cp.10

Rest's WM and CSF regressors are read from the confounds TSV's `white_matter` and `csf` columns,
less the trimmed rows, instead of being computed here with `3dresample`, `3dcalc` and `3dmaskave`.
cloudpipe's func preproc now writes those columns with the same definition: FastSurfer's label
masks, AFNI's nearest neighbour to the BOLD grid, within the run's brain mask, and the BOLD's mean
there (cloudpipe change `add-tissue-confound-columns`). On 16 real rest runs they matched this
code's regressors voxel for voxel, with values within 4.8e-6, which is 3dmaskave's 6-digit
rounding. The columns carry full float32 precision, so outputs differ from cp.9 at about 1e-6 and
no more.

- A session whose rest TSVs lack the columns skips `rest_conn` as `no-tissue-confounds`. It replaces
  `no-tissue-masks`, and staging no longer reads the label masks. There is no fallback: every
  published TSV has the columns.
- A column that is `n/a` (an empty mask) excludes its run as `tissue_mask_empty`, as before.
- The result no longer records `mask_voxels` on rest runs. FuncQC records the masks instead.

### 4.0.0+cp.9

A session published without its tissue maps (func preproc's export of them is non-fatal) now skips
`rest_conn` as `no-tissue-masks` and still runs n-back. Before, the missing `label-{WM,CSF}_mask`
was a session failure. Found in cloudpipe's final cohort slice: 42 sessions of 14 subjects.

### 4.0.0+cp.8

`3dDeconvolve` refusing `nback_conn`'s design matrix for too few frames ("Insufficient data (153)
for estimating 174 parameters") now fails only `nback_conn`, as `too-few-frames-for-model`, like
the `3dLSS` case in cp.7. Before, the session failed. Found in cloudpipe's final cohort slice.

### 4.0.0+cp.7

Two cases that failed whole sessions in cloudpipe's cohort waves now lose only what they must.

- **n-back runs with misplaced events are excluded as `unexpected-event-timing`.** A run's task events
  span more than 276 s, first to last onset, where ABCD 7.0's median is 267.1 s and 99% fall within
  266.5–269.8 s. That covers 256 of 58,589 runs, from evenly stretched blocks or pauses not in the
  design. Above about 290 s (about 214 runs) the core rejected them as past the run's end, and the
  whole session failed; between 276 and 290 s (42) they would have been modelled with wrong timing.
  The session keeps its other run and its rest. The check follows the stray-cue repair, so the 95
  stray-cue runs, which span about 310 s only until their cue moves back, are not excluded.
  (Corrected on 2026-11-07: the first count, 351, measured spans before that repair.)
- **`3dLSS` with more design columns than frames fails only `nback_conn`.** Heavy censoring can
  leave too few frames for the trial-by-trial design. The core reports this as a tool failure (exit
  4), and the session failed. It is now recorded as that analysis `failed`, with reason
  `too-few-frames-for-model`, like a model failure, and the session's other analyses publish.

### 4.0.0+cp.6

`tools.lock.yaml`'s `validated` versions are now the ones cloudpipe's image runs and the fork's CI
tests: AFNI 26.3.07, numpy 2.5.4 and pandas 3.1.1, from 26.0.09, 2.4.2 and 3.0.1. Every analysis
logged an `UNVALIDATED_VERSION` warning for each. The minimums are unchanged, so an older install
still fails, and a different version still warns. Analyses are unchanged.

### 4.0.0+cp.5

Each run now passes the orchestrator's rotation-unit check before staging. Power FD is
recomputed from the motion columns with rotations in degrees, and must match the confounds'
`framewise_displacement` within 1e-6 mm, or the run is excluded as `producer_fd_inconsistent`.
Each staged run records `motion_units_check`. Every one of 141 sampled ABCD runs passed, so
analyses are unchanged today. The check guards against a future input with rotations in radians.

### 4.0.0+cp.4

The Schaefer 400 + Tian S4 atlas now ships with `abcd/`, in `abcd/data/atlas/`, with its label
table and licences, and `--atlas` defaults to it. The file is byte-identical to Tian's published
copy and to the one cloudpipe used, so analyses are unchanged.

### 4.0.0+cp.3

The result JSON says why rest runs were lost, and analyses are unchanged.

- **A failed `rest_conn` marks every staged rest run** with `excluded_by_analysis`, using the reason
  its error names. Before, the runs looked used, because the core's failure record drops the
  per-run list.
- **A failed analysis carries its `error`** (type, message and step).
- **`excluded_by_analysis` is matched by run label.** It was matched by position, so a rest run
  that staging excluded shifted the reason onto the wrong run.

### 4.0.0+cp.2

Rest now matches the orchestrator's denoising, and n-back analyses are unaffected.

- **No global signal regression,** as in the orchestrator's config. A rest run can have 2 more
  censored frames before it is lost, because the regressor and its derivative are gone.
- **WM and CSF from FastSurfer's label masks,** as the orchestrator builds them, replacing the
  probseg-based masks. On 268 baseline sessions the probseg masks did not meet the comparison's
  pre-specified rule (`benchmarks/rest_masks/` on branch `rest-mask-comparison`). Rest no longer
  reads the probseg, so `--probseg-state` and the `probseg_state` result field are gone, and a
  run whose mask is empty is excluded as `tissue_mask_empty`.

Rest connectivity matrices change.

### 4.0.0+cp.1

The first release on upstream's 4.0 core, at the upstream base above. The commits table lists its
contents.

Compared with `legacy-5.0`, output names and QC follow upstream's 4.0 schema, including
`{pre}_qc_summary.json` and run exclusions recorded as `excluded_runs`. n-back runs stay separate,
and staging takes the analysis settings in `abcd/data/proc_config_final.yaml`.
