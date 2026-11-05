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
| Masking the BOLD | None; uses it as shipped | Each rest run by its brain mask; n-back runs by the intersection of theirs | Differs, unreviewed. The shipped BOLD is already zero outside each run's own mask (6 of 6 runs checked), so only the n-back intersection changes any voxel |
| WM regressor | FastSurfer `label-WM_mask`, nearest-neighbour to the BOLD grid | WM probseg with dilated GM removed, block mean to the BOLD grid, above 0.99 | Differs, unreviewed. On one session: about 87,000 voxels against 12,200, and correlation with the global signal 0.85-0.94 against 0.36-0.58 |
| CSF regressor | FastSurfer `label-CSF_mask`, nearest-neighbour to the BOLD grid | CSF probseg within that mask, block mean, first of 0.99, 0.9, 0.5 leaving 100 voxels | Differs, unreviewed. On one session: 2,626 voxels against 896, all inside the orchestrator's, signal correlation 0.93-0.98. Together, the WM and CSF choices give a final rest matrix correlation of 0.97 |
| Global signal | Mean within the run's brain mask, computed from the BOLD | The confounds file's `global_signal` | Differs, unreviewed. On one session the two correlate at 0.997 or better |
| Non-finite motion | Excludes the run, `motion_non_finite` | Same | Adopted |
| Rotation-unit check | Recomputes FD and compares it with the file's | None | Differs, unreviewed |
| Pre-analysis QC | tSNR and carpet plots | None | Differs, unreviewed |

## Analysis settings

Only settings that differ are listed. Each comes from `abcd/data/proc_config_final.yaml` and
the orchestrator's `example_proc_config.yaml`. `nback_act` `hrf_model` (`GAM`), `rest_conn`
`censor_prev_tr` (`true`), `use_sequenced_bandpass` (`false`, with `bandpass: [0.01, 0.1]`),
`nback_conn` `cond_beta_labels` (no `instruction`) and its 29 connectivity contrasts match the
orchestrator.

| Setting | Orchestrator | `abcd/` | Status |
|---|---|---|---|
| `rest_conn` `keep_run_res_dtseries` | `true` | `false` | Differs, unreviewed |
| `remove_previous` | `true` | `false` | Differs, by design: each session runs in an empty directory |
| `global.num_cores` | `1` | `auto`, from the pod's CPU request | Differs, by design |

## Deployment

| Step | Orchestrator | `abcd/` | Status |
|---|---|---|---|
| Reading and writing S3 | Downloads, uploads and verifies | Local files only; cloudpipe does this | Differs, by design |
| Completion marker | `_COMPLETE`, written by the orchestrator | `_complete.json`, written by cloudpipe | Differs, by design |
| Queueing | `run_orchestrator.py` | Prefect and Argo, in cloudpipe | Differs, by design |
| Session exit status | 0 complete, 2 known cause, 1 unexplained | 0 finished, 1 failed; each analysis records its own status | Differs, by design |
