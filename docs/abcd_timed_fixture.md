# ABCD-timed test fixture

`tests/abcd_timed.py` writes one synthetic session, and `tests/test_abcd_timed.py` runs the
production blocks from `abcd/data/proc_config_final.yaml` on it. The older fixture in
`tests/test_real_afni.py` uses TR 2 s, 120 frames and white noise, with motion too small to
censor. At that timing `3dTproject` accepts about 26% censoring per run, so it could not show
the run loss described below.

```bash
docker build -t fflp-afni:26.3.07 tests/docker
docker run --rm -v "$PWD":/src:ro -w /tmp fflp-afni:26.3.07 \
    pytest /src/tests/test_abcd_timed.py -m afni -p no:cacheprovider
```

## What it contains

Inputs match what `abcd/staging.py` hands the framework. They come from cloudpipe's
`derivatives/func` in `abcd-v7`, not from fMRIPrep. Motion is ABCD's own `3dvolreg` output:
translations in mm and rotations in degrees.

| Item | Value | Source |
|---|---|---|
| TR | 0.8 s | NIfTI headers |
| Rest | 4 runs of 375 frames on every make | 383 less 8. GE: 380 less 5, or 391 less 16 |
| n-back | 2 runs of 362 frames | Siemens and Philips: 370 less 8 |
| n-back, GE | 2 runs of 363 frames | 367 less 4, or 378 less 15 |
| n-back blocks | 8 per run, one per load and stimulus | Events files |
| Trials | 10 per block, 1.9 s long, 2.5 s apart, starting 3.0 s after a 2.89 s cue | Events files |
| Cue onsets | 0, 28, 71.1, 99.1, 142.2, 170.2, 213.2, 241.3 s | Events files, median |
| Temporal SNR | 75 voxelwise | One rest run per make: 83.6, 48.9, 78.8 |
| AR(1) | 0.4 | Same runs. Lag-1 autocorrelation: 0.17, 0.50, 0.43 |
| Shared drift | +-0.88% end to end | 90th percentile of `global_signal`, 1422 rest runs |
| ROI drift | +-0.61% from shared | 90th percentile, 12 rest runs, 12 mm blocks |
| Motion step between n-back runs | Norm 1.09 | Real median 1.26, 163 sessions |
| Motion | Drift, respiration near 0.37 Hz, and jerks | Sized to give the censoring below |
| Grid | 10 x 10 x 8 voxels, 3 ROIs | Reduced for CI |

A test ties the n-back counts to the constants in `abcd/staging.py`, so they cannot drift apart.

Signal is known. ROIs 1 and 2 correlate at 0.5 at rest. ROI 2 alone responds to load.
On this 3-ROI grid the grid mean would mostly be ROI signal, so the global signal regressor
comes from a separate whole-brain fluctuation, which is added to every voxel.

## Run loss this fixture reproduces

`3dTproject` fails when bandpass columns and regressors exceed the frames left after
censoring. `rest_conn` logs that, drops the run and reports success. The limit is 31 censored
frames for 375 frames, 18 regressors, `-polort 2` and 0.01-0.1 Hz: 8.3% of the run.

`abcd-v7` has almost no first-level outputs yet, so this is a prediction. It applies 4.2.0's
enorm censoring, production notch and threshold, and its limit of 33 censored frames at
`-polort -1`, to a random sample of baseline rest confounds, on 2026-11-03. On the one v7
subject with outputs, predicted censoring matched QC in all 4 runs. These numbers predate
5.0.0's Power FD and `-polort 2`, and have not been measured under them.

| Measure | Value |
|---|---|
| Sessions sampled | 385 |
| Sessions that would lose at least one run | 222 (57.7%) |
| Sessions that would lose every run, which fails loudly | 55 |
| Runs lost | 486 of 1422 (34.2%) |
| Per-run censoring: median, 75th, 90th percentile | 3.2%, 17.1%, 40.0% |

Under Power FD, the fixture's motion model censors 12 to 15 frames on a typical run and 46 to
58 on a high-motion run, across 5 seeds.

## Known defects

Tests marked `known_defect` state correct behaviour and are strict xfails. A fix turns its test
into a failure until the marker is removed, so a fixed defect cannot stay marked.

## Data handling

No subject identifiers or subject-level data belong in this repository. Keep only summary
values here, under the ABCD data use agreement. The two block orders are task design.
