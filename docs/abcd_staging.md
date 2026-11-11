# ABCD staging

`fmri_first_level_proc.abcd` prepares one ABCD session for first-level analysis and runs
it. It is optional and separate from the framework: nothing in the core imports it, and
it needs the `abcd` extra.

This page is the record of the staging rules. Cloudpipe's own spec covers only how it
deploys the CLI: which sessions it passes, publishing, and the queue. A change to a rule here
is a fork release, listed in [`FORK.md`](../FORK.md).

```bash
pip install "fmri-first-level-proc[abcd] @ git+https://github.com/jrussell9000/fmri-first-level-proc.git"
```

## Running it

```bash
fmri-first-level-abcd \
    --subj sub-XXXX --ses ses-00A \
    --input-dir /data/sub-XXXX/ses-00A \
    --workdir /scratch/stage \
    --out-dir /scratch/out \
    --run-validity /path/to/first_level_run_validity.csv \
    --result /scratch/result.json
```

`--atlas` defaults to the packaged Schaefer 400 + Tian S4 parcellation in
MNI152NLin2009cAsym at 2 mm. [`abcd/data/atlas/README.md`](../fmri_first_level_proc/abcd/data/atlas/README.md)
gives its source, its licences and the two papers to cite. Its subcortical parcels come first
(values 1–54), so parcel-by-parcel outputs list the subcortex before the cortex.

It works only on local files and never contacts a remote store. It needs AFNI and the
`fmri-first-level-proc` CLI on `PATH`.

| Exit | Meaning |
|---|---|
| 0 | Every analysis finished, and the result JSON is written. An analysis may be recorded `failed` (a data-determined model failure, CLI exit 5, or a tool failure the data decide, such as `3dDeconvolve` or `3dLSS` given more design columns than frames, recorded with `reason: too-few-frames-for-model`) or skipped. If rules leave nothing to run, the output directory holds only `{subj}_{ses}_first_level_skipped.json`. |
| 1 | The session failed, and no result is written. |

## Inputs

`--input-dir` holds one session of [cloudpipe](https://github.com/jrussell9000/cloudpipe)
func derivatives, or any files with the same names:

| File | Used for |
|---|---|
| `_complete.json` | Its `runs` keys name the session's runs |
| `{subj}_{ses}_{task}_{run}_space-MNI152NLin2009cAsym_bold.nii.gz` | BOLD |
| `{subj}_{ses}_{task}_{run}_space-MNI152NLin2009cAsym_brainmask.nii.gz` | Brain mask |
| `{subj}_{ses}_{task}_{run}_desc-confounds_timeseries.tsv` | Motion, `non_steady_state_outlier_*`, and on rest `white_matter` and `csf`. A session whose rest TSVs lack those two is skipped as `no-tissue-confounds`, and n-back still runs |
| `{subj}_{ses}_task-nback_{run}_events.tsv` | n-back timing |

## What it does

- **Rest trimming:** removes the frames flagged by the confounds'
  `non_steady_state_outlier_*` columns from the BOLD and motion.
- **n-back trimming:** ABCD's onsets count from the first non-dummy volume plus the length
  of the file's `dummy` row, so the stager subtracts that length from every onset. It trims
  that many frames, or the NSS count when the row's length is 0, whose onsets carry no pad.
  An event that then starts before 0 is dropped and counted.
- **n-back exclusions:** see below. A run that is excluded leaves the brain-mask
  intersection too.
- **Cue repair:** ABCD's converter can put a run's first cue at the end of the previous run,
  when it starts a moment before the run's reference time. If a run's last cue has no
  following trial and starts after the run's last frame, and the next run's first trial
  precedes its first cue, the cue moves back to 3.0 s before that trial.
- **Motion:** translations first, in degrees, with first derivatives taken before
  trimming. ABCD's confounds already hold degrees, so rotations pass through unconverted. As
  the orchestrator does, each run first confirms that: Power FD recomputed with rotations in
  degrees on a 50 mm head must match the confounds' `framewise_displacement` within 1e-6 mm,
  or the run is excluded as `producer_fd_inconsistent`. A non-finite value left after trimming
  excludes the run as `motion_non_finite`.
- **n-back events:** a 0-back cue becomes `target_0back`, pooled across stimuli, and a
  2-back cue becomes `instruction`. `dummy` rows are dropped. A session has only 2 cues per
  stimulus, too few to model or correlate alone. In `nback_conn`, `target_0back` and
  `instruction` are nuisance regressors, and the `ave_*` contrasts average 0-back and
  2-back only.
- **n-back runs** stay separate files, each with its own run-local events and motion and
  its `run_labels` entry (the framework's Mode A), so each run gets its own baseline and PSC
  mean. All are masked by the intersection of their brain masks, because they enter one
  model. A run that fails staging is excluded and recorded, and the rest continue.
- **Staged runs** are written to `{workdir}/{task}_{run}_bold.nii`, uncompressed: every
  analysis reads each one several times, and gzip would cost a full decompression each time.
  They are about 1.6 GB each. A compressed copy of each is kept in `staged/` (see "Runs are
  kept, concatenations are not").
- **Rest WM and CSF:** the confounds TSV's `white_matter` and `csf` columns, less the
  trimmed rows. cloudpipe's func preproc writes them as the orchestrator builds its
  regressors: FastSurfer's 1 mm `label-WM_mask` and `label-CSF_mask` go to the BOLD grid
  by AFNI's nearest neighbour and are intersected with the run's brain mask, and each
  column is the BOLD's mean there on every frame. A column that is `n/a` (its mask was
  empty) excludes the run as `tissue_mask_empty`. Until `4.0.0+cp.10` staging computed the
  same regressors itself with `3dresample`, `3dcalc` and `3dmaskave`. The columns agree
  with those to 3dmaskave's 6 significant digits, and carry float32 precision.
- **Rest global signal:** not regressed, as in the orchestrator's config. The core logs
  `GS_MISSING`, a low-severity warning, for each rest analysis.
- **Rest denoising:** as the orchestrator `5855f3f`, set in the packaged config's rest
  block: censoring at `fd_threshold` 0.4 mm with `censor_prev_tr: true`, bandpass
  0.01–0.1 Hz with `use_sequenced_bandpass: false`, and mean WM and CSF signals, not
  aCompCor. A run left with DOF below 1 is lost as `dof_below_1`, and a session that
  loses every rest run records `rest_conn` `failed`.
- **Analyses:** fills `abcd/data/proc_config_final.yaml` (or `--template`) and runs each
  block through the `fmri-first-level-proc` CLI, once per block, so one analysis's failure
  cannot stop the others. The setup fields `out_dir`, `out_file_pre`, `extract_out_file_pre`
  and `conn_out_file_pre` are set to `{subj}_{ses}_{post_id}`. Every analysis setting is
  left as the template has it.
- **Shared stages:** staging sets `FFLP_STAGE_SHARE_DIR` to `{workdir}/shared_stages`, so
  `nback_conn` takes `nback_act`'s template, prep, min-outlier EPI, raw ptseries and ROI QC
  (hard links into its own `out_dir`, with their QC and warnings) instead of computing them
  again. Both analyses run the same code on the same staged runs, and the core shares a
  stage only when its share key matches: its inputs, settings, upstream stages, output
  prefix and tool versions. Each analysis's outputs and ledger are as if it had run alone.

## Analysis exits

Each analysis's CLI exit becomes its entry in the result JSON:

| CLI exit | Recorded as |
|---|---|
| 0 | `completed` |
| 3 | `completed`, with `high_warnings: true` |
| 5 (`ModelError`: singular design, DOF below 1, no surviving trials) | `failed`. The data decide it, and a retry would reproduce it, so the session still publishes |
| 4, with an error in `DATA_LIMITED_TOOL_ERRORS` (`3dLSS` "Matrix has too many columns", `3dDeconvolve` "Insufficient data") | `failed`, with `reason: too-few-frames-for-model`, for the same reason |
| Any other (1 a bug, 2 a config or input error staging caused, 4 any other tool failure) | The session fails: the CLI exits 1 and writes no result |

## n-back exclusions

| Reason | Meaning |
|---|---|
| Table reasons, below | E-Prime timing is invalid or can't be attributed to the run |
| `no-validity-row` | The table has no row for the run |
| `no-task-events` | The events file holds only a `dummy` row |
| `no-dummy-row` | No `dummy` row states the discard |
| `unexpected-dummy` | The `dummy` isn't a whole number of frames, or isn't 0, the NSS count or one below it |
| `predates-ge-timing-correction` | A GE run logs its full NSS count, unlike every other GE run; its onsets may be up to 0.8 s off |
| `unexpected-frame-count` | The run wouldn't keep 363 frames (NSS count of 5 or 16, GE) or 362 (otherwise): a wrong scanner label, or a short run |
| `unexpected-event-timing` | The task events, first to last onset, span more than 276 s. Across ABCD 7.0 the median is 267.1 s and 99% fall in 266.5–269.8 s. A longer span means evenly stretched blocks or pauses not in the design, so the onsets are misplaced. Above about 290 s they also pass the run's end |

## Run-validity table

ABCD excludes runs with irregular trigger timing from its own analyses, but still ships
their events. The table says which n-back runs to use. It is built from data under your
ABCD data use agreement and is keyed by subject ID, so it must never be committed here:

```bash
fmri-first-level-abcd-validity \
    --mr-qc-nback mr_y_qc__raw__tfmri__nback.tsv \
    --results-r01 mr_y_tfmri__nback__0b__r01__aseg.tsv \
    --results-r02 mr_y_tfmri__nback__0b__r02__aseg.tsv \
    --runs runs.csv \
    --out first_level_run_validity.csv
```

`--runs` is a CSV of `subject_id,session,run`, one row per n-back run, with `run` as
`task-nback_run-01`. An optional `--hold` CSV of `subject_id,session,reason` holds out
named sessions.

| `mr_y_qc__raw__tfmri__nback__eprime__run__valid_count` | Treatment | Reason |
|---|---|---|
| 2 or more | Use every run. Run-level results are ignored, because they can also be missing for QC reasons | |
| 1, with results for one run | Use that run | `other-run-has-valid-timing` on the others |
| 1, with no results | Hold out | `valid-run-unidentified` |
| 0 | Hold out | `no-valid-timing-runs` |
| Missing | Hold out | `no-valid-count` |

It doesn't use `mr_y_qc__incl__tfmri__nback_indicator`, which also reflects motion,
behaviour and manual QC, choices an analyst may want to make differently. It says nothing
about rest, so a held-out session still runs its rest analysis.

## Result JSON

`package_version`, `analyses` (name to status, exit code and warning flag, or skip reason)
and `runs` (run to `n_remove`, `n_frames`, `dropped_events`, `motion_units_check`
(`producer_fd_consistent`, or `not_checkable` with no usable FD column), or `excluded`).
Rest no longer records mask voxel counts here (`mask_voxels`, until `4.0.0+cp.10`): the
masks are built by cloudpipe's func preproc, and its FuncQC records them per run
(`wm_mask_voxels`, `csf_mask_voxels`). A repaired cue adds
`cue_moved_to` and `cue_moved_from` to the two runs. A failed analysis adds `error`: the
`type`, `message` and `step` from its QC summary's `run_status`. An n-back analysis adds
`removed`, the concatenated series deleted from its `out_dir`; `nback_conn` adds
`deduplicated`, the files it shared with `nback_act` and that only `nback_act` keeps; and
each staged run adds `staged_bold`, its kept copy (see below).

## Runs are kept, concatenations are not

Since `4.0.0+cp.11`, a session keeps each run's series and not the concatenations made
from them. After every analysis has finished, staging:

- deletes each n-back analysis's `{pre}_psc.nii` and `{pre}_concat_scan.nii`. The first is
  the `{pre}_run{N}_psc.nii.gz` files end to end, which stay; the second is the staged
  runs end to end. The analysis's ledger still lists them, as outputs of the run that
  made them.
- writes each staged run, the trimmed and masked raw series every analysis started from,
  to `staged/{subj}_{ses}_{task}_{run}_bold.nii.gz` under the output directory, gzipped
  once at the default level (level 1 measured no faster). A run that failed staging is
  not kept.
- (since `4.0.0+cp.12`) deletes each of `nback_conn`'s intermediates that is a hard link
  of `nback_act`'s file, put there by a shared stage: the PSC runs, their means, the
  run-intersection mask and the resampled atlas. Read them from `nback_act/`.
  `nback_conn`'s `final` outputs stay, and so does any file it computed itself.

The PSC runs with their `{pre}_run{N}_mean.nii.gz` also give back the raw runs,
`raw = psc * mean / 100`, except where PSC was capped at 200 or zeroed (a non-positive
value or mean): on a real session that is about 0.06% of values, at the brain's edge.
95.4% of the rest come back bit for bit and all within 1.2e-7 relative.

A rest run that staged but that `rest_conn` left out adds `excluded_by_analysis`. When
`rest_conn` completes, the reason comes from `excluded_runs` in the QC summary, matched by run
label. It is recorded `failed` when the data leave no run, and the core's failure record then
keeps the error but not the per-run records. So every staged rest run gets the reason the
error names: `dof_below_1`, `insufficient_uncensored_trs`, or `analysis_failed` for any other
message.
