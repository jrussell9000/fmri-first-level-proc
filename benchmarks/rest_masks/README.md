# Rest mask comparison

Decides which WM and CSF masks `rest_conn` uses, with no global signal regression (GSR), before
ABCD first-level runs at scale.

## The question

The orchestrator takes WM and CSF from FastSurfer's labels. WM is about 87,000 voxels. `abcd/` took
them from probseg: WM with dilated grey matter removed, about 12,600 voxels, and CSF restricted to
the ventricles. With GSR on, on one session, the choice barely mattered (r 0.975, mean |dz| 0.047).
With GSR off, as the orchestrator runs it, it mattered 3 times as much (r 0.937, mean |dz| 0.152,
mean z 0.106 against 0.251). The orchestrator's WM signal tracks the global signal closely, so it
acts like partial GSR. Which keeps less noise and more signal is unknown.

## Arms

All arms share one staging of each session and the production rest block.

| Arm | WM and CSF | GSR | Role |
|---|---|---|---|
| `taylor_off` | FastSurfer labels, as the orchestrator | Off | **Reference**, the default by the rule "stay consistent with upstream" |
| `ours_off` | Probseg, as `abcd/` | Off | **Candidate** |
| `ours_on` | Probseg, as `abcd/` | On | Positive control, not a choice: GSR is known to weaken motion's global effect |

## Sample

A simple random sample of 444 `ses-00A` sessions, with seed 20261103, skipping the first 200 in
that order, which were the older comparison's margin sessions and supplied this smoke test. It
keeps the real spread of motion. Sessions without a `fixed` probseg state are recorded as skipped.

## Measures

Every arm uses the runs that all three arms kept, so arms differ only in regressors.

| Measure | Sessions used | Role |
|---|---|---|
| Median edgewise ICC(3,1) between halves | At least 2 runs and 150 frames per half | **Primary, reliability** |
| Median absolute QC-FC, controlling scanner make | At least 150 frames | **Primary, link to motion** |
| Absolute partial correlation of mean edge z with mean FD, controlling make | At least 150 frames | **Primary, global link to motion** |
| Within-network minus between-network mean z, cortex only | At least 150 frames | Secondary, signal |
| Fingerprint accuracy | As ICC | Secondary |
| Share of edges with QC-FC p below 0.05, and passing FDR | As QC-FC | Secondary |
| QC-FC distance dependence | As QC-FC | Secondary |
| Mean z, percent negative edges, runs kept | As QC-FC | Descriptive |

Intervals are paired 95% percentile bootstraps over subjects, 1000 draws, with QC-FC and ICC on a
fixed subset of 20000 edges. Point estimates use every edge.

## Decision rule

Fixed before any arm runs on this sample. `analyze.py` applies it as written.

`ours_off` replaces `taylor_off` only if all four hold:

1. **Reliability not worse:** the ICC difference's lower bound is above minus the ICC margin.
2. **Motion link not worse:** the QC-FC difference's upper bound is below the QC-FC margin.
3. **Global motion link not clearly worse:** the difference's lower bound is at or below 0.
4. **Reliability better:** the ICC difference's lower bound is above 0.

Otherwise `taylor_off` stands. A tie goes to upstream, so the candidate has to earn the difference.

**The positive control.** If `ours_on` doesn't weaken the global link to motion against `ours_off`
(the interval's upper bound is not below 0), these measures can't discriminate. The report says
so, and the result only supports the default.

**Secondary measures** don't enter the rule. They are reported, and they can make a reader doubt a
result. In particular, more global signal can raise ICC through a consistent artifact, which is why
rule 3 exists.

## Margins

The ICC (0.0071) and QC-FC (0.0020) margins in `margins_v7.json` were fixed on 2026-11-03 for the
older denoising comparison, on separate sessions, at about one interval half-width for 300 usable
sessions. They are reused unchanged, so they can't be fitted to this result. They were measured on
the older core and settings, which is a limit.

## Limits

- Baseline sessions only. The result is assumed to hold at later visits, where motion is lower.
- Neither reliability nor QC-FC measures validity. No behaviour or known-effect test is included.
- QC-FC near chance can't separate arms edge by edge: median |r| by chance is about 0.04 at 270
  sessions. The global measure exists for that reason.
- Sessions that lose all runs are absent. They can't affect any arm.
- Age and sex are not covariates. Scanner make is the only one.
- The image is `4.0.0+cp.1`. `run_session.py` sets each arm's global signal itself, so its GSR
  default has no effect.

## Running it

Subject-level data stays out of this repository. `sessions.csv` and each session's series live only
in `scratch/`, which S3 expires after 7 days. Analyze within that window, and keep only `report.json`.

```bash
TAG=v7-masks
python draw_sample.py --n 444 --skip 200 --seed 20261103 --out /tmp/sessions.csv
aws s3 cp /tmp/sessions.csv s3://abcd-v7/scratch/rest-masks/$TAG/sessions.csv
aws s3 cp run_session.py s3://abcd-v7/scratch/rest-masks/$TAG/code/run_session.py
argo -n argo-workflows submit workflow.yaml -p n-sessions=444 -p tag=$TAG
aws s3 sync s3://abcd-v7/scratch/rest-masks/$TAG/sessions/ /tmp/sessions/
LABELS=../../fmri_first_level_proc/abcd/data/atlas/Schaefer2018_400Parcels_7Networks_order_Tian_Subcortex_S4_label.txt
python analyze.py --sessions-dir /tmp/sessions --margins margins_v7.json --networks $LABELS --out report.json
```

**Correction, 2026-11-06.** The first analysis read network names from CBIG's Schaefer-only table
in list order, so each name sat on the parcel 54 places before its own: the atlas numbers Tian's
54 subcortical parcels first. That scrambled the secondary network contrast, which is outside the
rule. With names taken from the atlas's own label table, every other figure in the report is
unchanged. The network contrast is 0.262 for `taylor_off`, 0.242 for `ours_off` and 0.276 for
`ours_on`; it was reported as 0.106, 0.093 and 0.111. The order is the same, and the decision does
not change.

A rerun skips sessions that already have a saved result.

## Validation so far

| Check | Result |
|---|---|
| Metrics and the rule | Known-answer tests in `test_metrics.py` |
| 3 sessions on the cluster, arm64, outside the sample | All arms ran; off arms kept the same runs with equal DOF, and GSR took 2 DOF |
| Whole analysis path | Ran on noisy copies of those sessions. Not a result |

Those 3 sessions took 43, 26 and 43 CPU-minutes, or 13 to 21 minutes each at 2 CPUs. For 444
sessions, expect about 300 CPU-hours and 5 to 6 hours at 25 pods.
