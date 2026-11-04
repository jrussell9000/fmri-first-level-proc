# Rest denoising comparison

Decides how `rest_conn` should handle ABCD rest data before v7 first-level runs at scale.

## The question

At TR 0.8 s, the production bandpass removes about 319 of a run's 375 dimensions. With 18
nuisance regressors, `3dTproject` then accepts only 33 censored frames, and `rest_conn`
silently drops any run above that. On a sample of v7 motion, that would lose 34.2% of runs.

Fix the silent drop whichever arm wins. This comparison decides only the denoising method.

## Arms

Each arm starts from the `rest_conn` block in `abcd/data/proc_config_final.yaml`, and all arms
share one staging of each session.

| Arm | Change from production | Expected trade-off |
|---|---|---|
| `bandpass` | None. The reference | Loses high-motion runs |
| `sequenced` | `use_sequenced_bandpass: true` | Should keep runs, but interpolates censored frames |
| `highpass` | `bandpass: [0.01, 99]` | Keeps runs and most DOF, and keeps noise above 0.1 Hz |
| `anchor_9p` | `motion_deriv_degree: 1`, `use_tissue_derivs: false` | Keeps more runs, with 9 regressors, and may keep more noise |

## Sample

A simple random sample of 444 complete v7 `ses-00A` sessions, with seed 20261103, after the
200 margin sessions. In the margin run, 135 of 200 sessions were usable, so 444 should give
about 300. Sessions
without a `fixed` probseg state are recorded as skipped. A simple random sample keeps the real
distribution of motion, which is what the decision has to hold for.

## Measures

Runs are alternated into two halves. A half needs at least 150 uncensored frames. Fisher z
connectivity is computed on each half's uncensored frames, with each run demeaned.

| Measure | Purpose |
|---|---|
| Median edgewise ICC(3,1) between halves | **Primary, reliability** |
| Median absolute QC-FC, controlling scanner make | **Primary, link to motion** |
| Fingerprint accuracy between halves | Secondary |
| Share of edges with FDR-significant QC-FC | Secondary |
| QC-FC distance dependence | Secondary |
| Runs kept, sessions losing a run, frames kept | Descriptive |

QC-FC uses each session's mean FD from cloudpipe's `framewise_displacement`, over the runs
the arm kept. Intervals are paired percentile bootstraps over subjects, using 1000 draws on a
fixed subset of 20000 edges. Point estimates use every edge.

**Two populations:**

- `common_runs`: only runs that every arm kept. All arms use identical data, so this isolates
  the method.
- `all_data`: each arm uses every run it kept, in sessions every arm can split. This shows what
  the extra runs add.

## Decision rule

An arm replaces `bandpass` only if all four hold. `analyze.py` applies this rule as written.

1. On `common_runs`, the ICC difference's lower bound is above minus the ICC margin.
2. On `common_runs`, the QC-FC difference's upper bound is below the QC-FC margin.
3. On `all_data`, the ICC difference's lower bound is above 0.
4. On `all_data`, the QC-FC difference's upper bound is below the all-data QC-FC margin.

Rule 4 exists because rule 2 sees only runs `bandpass` survived. An arm's rescued high-motion
runs appear only in `all_data`.

If several arms pass, prefer the highest `all_data` ICC. If none passes, keep `bandpass` and
report each lost run as a warning.

## Margins

These are the final values, in `margins_v7.json`. They may not change now that test arms run.

| Margin | Value | Half-width of the paired interval, rescaled to |
|---|---|---|
| ICC | 0.0071 | 300 usable sessions |
| QC-FC, `common_runs` | 0.0020 | 300 usable sessions |
| QC-FC, `all_data` | 0.0024 | 200 usable sessions |

**How they came about.** The procedure first set each margin to the larger of the
production-to-9P spread and that half-width, on 200 sessions that are not in the test. Of those,
135 were usable. `sequenced` and `highpass` never ran on them. That gave an ICC margin of 0.075,
because 9P's ICC was higher by that much. A gain in one direction does not justify allowing the
same loss in another, so the operator approved using resolution alone before any test arm ran.

**What this means.** Each margin is about one interval half-width, so an arm passes rules 1, 2
and 4 only if its point estimate is about equal to or better than production. The rule is
deliberately strict for a change to a production method.

**9P as a test arm.** These margins hold no spread, so they are not circular for 9P. Still, the
margin run's result prompted adding 9P, so its test is a replication on separate subjects.

## Limits

- Sessions that any arm cannot split are absent from the ICC and QC-FC measures. Retention
  reports them.
- In the margin run, median absolute QC-FC was close to chance, about 0.059, and no edge passed
  FDR. QC-FC may discriminate little between arms.
- `common_runs` favours low motion, because it holds only runs `bandpass` survives.
- Neither reliability nor QC-FC measures validity. A consistent artifact can raise ICC, so read
  ICC and QC-FC together.
- Age and sex are not covariates. Scanner make is the only one.

## Running it

Subject-level data stays out of this repository. `sessions.csv` and each session's series hold
identifiable or subject-level data, so they live only in `scratch/`, which S3 expires after
7 days. Analyze within that window, and keep only `report.json`.

```bash
# Margins first
TAG=v7-anchor
python draw_sample.py --n 200 --seed 20261103 --out /tmp/anchor.csv
aws s3 cp /tmp/anchor.csv s3://abcd-v7/scratch/rest-denoising/$TAG/sessions.csv
aws s3 cp run_session.py s3://abcd-v7/scratch/rest-denoising/$TAG/code/run_session.py
argo -n argo-workflows submit workflow.yaml -p n-sessions=200 -p tag=$TAG -p arms=bandpass,anchor_9p
aws s3 sync s3://abcd-v7/scratch/rest-denoising/$TAG/sessions/ /tmp/anchor/
python anchors.py --sessions-dir /tmp/anchor --out margins_v7.json

# Then the test
TAG=v7-test
python draw_sample.py --n 444 --skip 200 --seed 20261103 --out /tmp/sessions.csv
aws s3 cp /tmp/sessions.csv s3://abcd-v7/scratch/rest-denoising/$TAG/sessions.csv
aws s3 cp run_session.py s3://abcd-v7/scratch/rest-denoising/$TAG/code/run_session.py
argo -n argo-workflows submit workflow.yaml -p n-sessions=444 -p tag=$TAG
aws s3 sync s3://abcd-v7/scratch/rest-denoising/$TAG/sessions/ /tmp/sessions/
python analyze.py --sessions-dir /tmp/sessions --margins margins_v7.json --out report.json
```

A rerun skips sessions that already have a saved result.

## Validation so far

| Check | Result |
|---|---|
| Metrics | Known-answer tests in `tests/test_rest_denoising_metrics.py` |
| Two real sessions, local amd64 | All arms ran. A run with 119 censored frames was lost only under `bandpass`, with exit 0 |
| One real session, cluster arm64 | Same runs kept and same censoring. Largest parcel series difference from amd64: 0.00013 |
| Spot reclaim | The first pod was deleted, and the retry finished the session |

Group metrics have run only on synthetic data, because two sessions are too few.

The margin run's 200 pods all succeeded on the first attempt: 80.3 CPU-hours and 1 hour 42
minutes, with no eviction at the 10 GiB and 40 GiB requests. Peak memory and disk were not
measured. For 444 sessions with four arms, expect about 400 CPU-hours and 9 hours at 25 pods.
