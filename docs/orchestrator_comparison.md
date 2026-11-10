# `abcd/` compared with ABCD_fmri_orchestrator_S3

Upstream runs this framework through a separate repository,
[ABCD_fmri_orchestrator_S3](https://github.com/tjkeding/ABCD_fmri_orchestrator_S3). This fork
does that work in `fmri_first_level_proc.abcd` instead. The two share no code, so changes to
the orchestrator do not reach this fork by merging. This page is how they are followed.

**Compared against:** orchestrator `5855f3f` (v4.0.0, 2026-11-04), by reading its code and
`example_proc_config.yaml`. Neither has been run against the other on the same session.

## Keeping this current

When the orchestrator changes, read the changes and update the tables and the commit above:

```bash
gh api repos/tjkeding/ABCD_fmri_orchestrator_S3/compare/5855f3f...main \
    --jq '.commits[] | .sha[:7] + " " + .commit.message'
```

## Status values

- **Same:** both do this the same way.
- **Adopted:** this fork changed to match the orchestrator.
- **Differs, measured:** this fork differs because of a fault measured in ABCD data.
- **Differs, by design:** a deliberate difference that follows from how this fork is deployed.
- **Differs, reviewed:** compared and kept by decision, without proof that either is better.
- **Differs, unreviewed:** the difference exists, and nobody has yet decided which is better.

## Staging

| Step | Orchestrator | `abcd/` | Status |
|---|---|---|---|
| Run layout for n-back | Separate files per run | Same | Adopted |
| 0-back cues | One condition, `target_0back` | Same | Adopted |
| 2-back cues | `instruction` | Same | Same |
| Rest frame trim | Count of `non_steady_state_outlier_*` columns | Same | Same |
| Motion derivatives | Taken before the trim | Same | Same |
| n-back frame trim and onset shift | Non-steady-state count, for both | The run's `dummy` row, or the count when that row is 0 | Differs, measured: the count is out of date on GE and lost each GE run's first cue |
| Which n-back runs are used | All with valid event files | Only runs the validity table allows | Differs, measured: ABCD ships events for runs with irregular trigger timing |
| A run's first cue filed at the end of the previous run | Not repaired | Moved back to its run | Differs, measured |
| A run with no task events | Excluded as `unexpected_error`, so the session exits 1 and is retried | Excluded, `no-task-events`, and the session finishes | Differs, measured: a settled answer needs no retry |
| A run with the wrong frame count for its scanner | Not found in the code by search | Excluded, `unexpected-frame-count` | Differs, measured |
| A run whose events span more than the task's schedule | Used. Past the run's end, the core's `InputError` fails the analysis | Excluded, `unexpected-event-timing`, above 276 s | Differs, measured: 256 of 58,589 ABCD 7.0 runs after the stray-cue repair, about 214 of them past the run's end. Between 276 and 290 s (42 runs) the misplaced onsets would be modelled with no warning |
| `3dDeconvolve` or `3dLSS` given more design columns than frames | Tool failure (exit 4), and the session exits 1 | That analysis is recorded `failed` with `too-few-frames-for-model`; the others publish | Differs, by design: the data decide it, as a model failure does |
| Masking the BOLD | None; uses it as shipped | Each rest run by its brain mask; n-back runs by the intersection of theirs | Differs, unreviewed. The shipped BOLD is already zero outside each run's own mask (6 of 6 runs checked), so only the n-back intersection changes any voxel |
| WM and CSF regressors | FastSurfer `label-WM_mask` and `label-CSF_mask`, nearest-neighbour to the BOLD grid, within the run's brain mask; an empty mask excludes the run, `tissue_mask_empty` | Same definition. Since `4.0.0+cp.10` the values come from the confounds TSV's `white_matter` and `csf` columns, which cloudpipe's func preproc computes this way on every frame, rather than from `3dmaskave` here. They agree to 3dmaskave's 6-digit precision (16 real rest runs, worst 4.8e-6) | Adopted in `4.0.0+cp.2`, which retired probseg-based masks (fMRIPrep's WM, ventricle-restricted CSF). Compared on 268 baseline sessions with GSR off ([`rest-mask-comparison`](https://github.com/jrussell9000/fmri-first-level-proc/tree/rest-mask-comparison/benchmarks/rest_masks)), the probseg masks did not meet the rule fixed beforehand: split-half ICC was higher, but the QC-FC interval was too wide to show motion no worse, and fingerprinting, mean z and network contrast all pointed to retained global signal |
| Global signal regression | Off: `GS_paths: null` in its config | Off | Adopted. It was on here until `4.0.0+cp.2` |
| Non-finite motion | Excludes the run, `motion_non_finite` | Same | Adopted |
| Rotation-unit check | Power FD recomputed with rotations in degrees must match the file's `framewise_displacement` within 1e-6 mm, or the run is excluded, `producer_fd_inconsistent` | Same | Adopted in `4.0.0+cp.5`. On 141 sampled ABCD runs (94 rest, 47 n-back, 3 makes) every run passed, with the largest difference 2e-15 mm, so it excludes nothing today |
| Pre-analysis QC | tSNR and carpet plots | None | Differs, unreviewed |

## Analysis settings

Only settings that differ are listed. Each comes from `abcd/data/proc_config_final.yaml` and
the orchestrator's `example_proc_config.yaml`. `nback_act` `hrf_model` (`GAM`), `rest_conn`
`censor_prev_tr` (`true`), `use_sequenced_bandpass` (`false`, with `bandpass: [0.01, 0.1]`),
`nback_conn` `cond_beta_labels` (no `instruction`) and its 29 connectivity contrasts match the
orchestrator.

| Setting | Orchestrator | `abcd/` | Status |
|---|---|---|---|
| `rest_conn` `keep_run_res_dtseries` | `true` | `false` | Differs, reviewed: kept by decision on 2026-11-06. `false` still keeps the concatenated residual series, voxel and parcel, with zeros at censored frames; `true` adds only per-run copies, about 0.8 GB per session |
| `remove_previous` | `true` | `false` | Differs, by design: each session runs in an empty directory |
| `global.num_cores` | `1` | `auto`, from the pod's CPU request | Differs, by design |

## Deployment

| Step | Orchestrator | `abcd/` | Status |
|---|---|---|---|
| Reading and writing S3 | Downloads, uploads and verifies | Local files only; cloudpipe does this | Differs, by design |
| Completion marker | `_COMPLETE`, written by the orchestrator | `_complete.json`, written by cloudpipe | Differs, by design |
| Queueing | `run_orchestrator.py` | Prefect and Argo, in cloudpipe | Differs, by design |
| Session exit status | 0 complete, 2 known cause, 1 unexplained | 0 finished, 1 failed; each analysis records its own status | Differs, by design |
