# ABCD staging

`fmri_first_level_proc.abcd` prepares one ABCD session for first-level analysis and runs
it. It is optional and separate from the framework: nothing in the core imports it, and
it needs the `abcd` extra.

```bash
pip install "fmri-first-level-proc[abcd] @ git+https://github.com/jrussell9000/fmri-first-level-proc.git"
```

## Running it

```bash
fmri-first-level-abcd \
    --subj sub-XXXX --ses ses-00A \
    --input-dir /data/sub-XXXX/ses-00A \
    --probseg-state fixed \
    --workdir /scratch/stage \
    --out-dir /scratch/out \
    --atlas /path/to/parcellation.nii.gz \
    --run-validity /path/to/first_level_run_validity.csv \
    --result /scratch/result.json
```

It works only on local files and never contacts a remote store. It needs AFNI and the
`fmri-first-level-proc` CLI on `PATH`.

| Exit | Meaning |
|---|---|
| 0 | Every analysis finished, and the result JSON is written. An analysis may be recorded `failed` (a data-determined model failure, CLI exit 5) or skipped. If rules leave nothing to run, the output directory holds only `{subj}_{ses}_first_level_skipped.json`. |
| 1 | The session failed, and no result is written. |

## Inputs

`--input-dir` holds one session of [cloudpipe](https://github.com/jrussell9000/cloudpipe)
func derivatives, or any files with the same names:

| File | Used for |
|---|---|
| `_complete.json` | Its `runs` keys name the session's runs |
| `{subj}_{ses}_{task}_{run}_space-MNI152NLin2009cAsym_bold.nii.gz` | BOLD |
| `{subj}_{ses}_{task}_{run}_space-MNI152NLin2009cAsym_brainmask.nii.gz` | Brain mask |
| `{subj}_{ses}_{task}_{run}_desc-confounds_timeseries.tsv` | Motion, `global_signal`, `non_steady_state_outlier_*` |
| `{subj}_{ses}_task-nback_{run}_events.tsv` | n-back timing |
| `{subj}_{ses}_space-MNI152NLin2009cAsym_res-1_label-{GM,WM,CSF}_probseg.nii.gz` | Rest tissue masks |
| `{subj}_{ses}_space-MNI152NLin2009cAsym_res-1_label-CSF_mask.nii.gz` | Ventricle restriction |

`--probseg-state` must be `fixed` for rest to run. Any other value skips rest and records
the reason; the two tissue rows above are needed only for `fixed`.

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
  trimming. ABCD's confounds already hold degrees, so rotations pass through unconverted. An
  isolated NaN becomes 999, so that on n-back FD censoring removes that TR. A rest run with
  one is excluded as `motion_non_finite`, because the notch filter would spread the 999 over
  the whole run.
- **n-back events:** a 0-back cue becomes `target_0back`, pooled across stimuli, and a
  2-back cue becomes `instruction`. `dummy` rows are dropped. A session has only 2 cues per
  stimulus, too few to model or correlate alone. In `nback_conn`, `target_0back` and
  `instruction` are nuisance regressors, and the `ave_*` contrasts average 0-back and
  2-back only.
- **n-back runs** stay separate files, each with its own run-local events and motion and
  its `run_labels` entry (the framework's Mode A), so each run gets its own baseline and PSC
  mean. All are masked by the intersection of their brain masks, because they enter one
  model. A run that fails staging is excluded and recorded, and the rest continue.
- **Rest WM mask:** as fMRIPrep builds `white_matter`: dilated grey matter removed, moved
  to the BOLD grid as partial-volume fractions, brain-masked, kept above 0.99.
- **Rest CSF mask:** restricted to the ventricles with FastSurfer's `label-CSF_mask`, then
  kept above the first of 0.99, 0.9 and 0.5 that leaves at least 100 voxels. This departs
  from fMRIPrep, and is likely specific to ABCD.
- **Rest global signal:** the confounds' `global_signal`, trimmed.
- **Analyses:** fills `abcd/data/proc_config_final.yaml` (or `--template`) and runs each
  block through the `fmri-first-level-proc` CLI, once per block.

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

`package_version`, `probseg_state`, `analyses` (name to status, exit code and warning flag,
or skip reason) and `runs` (run to `n_remove`, `n_frames`, `dropped_events`, plus the
mask voxel counts and `csf_threshold` on rest, or `excluded`). A repaired cue adds
`cue_moved_to` and `cue_moved_from` to the two runs. A rest run that staged but that
`rest_conn` left out adds `excluded_by_analysis`, with the reason from `excluded_runs` in
the QC summary. `rest_conn` is recorded `failed` when the data leave no run.
