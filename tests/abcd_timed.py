"""Synthetic session with real ABCD timing, motion scale and noise, on a small grid.

Timing bugs depend on TR, frame counts and censoring, not on voxel count, so only the
spatial grid is reduced. Every signal is known, so tests can assert recovery of the truth.

The values below were measured from ABCD release data. Only summary values are kept here:
no subject identifiers or subject-level data are in this file. docs/abcd_timed_fixture.md
says how each one was measured.
"""

from dataclasses import dataclass, field
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

import nibabel as nib

TR = 0.8
GRID = (10, 10, 8)
VOXEL_MM = 2.4
REST_RUNS = 4
REST_FRAMES = 375  # Every make: 383 less 8, or on GE 380 less 5 and 391 less 16
NBACK_RUNS = 2
# abcd/staging.py excludes any n-back run that keeps a different count from these.
NBACK_FRAMES = 362  # Siemens and Philips: 370 less 8
NBACK_FRAMES_GE = 363  # GE: 367 less 4, or 378 less 15

# Staged-time cue onsets: 2 blocks, 15 s fixation, repeated.
CUE_ONSETS = (0.0, 28.0, 71.1, 99.1, 142.2, 170.2, 213.2, 241.3)
CUE_DURATION = 2.89
CUE_TO_TRIAL = 3.0
TRIALS_PER_BLOCK = 10
TRIAL_SOA = 2.5
TRIAL_DURATION = 1.9
# Two of the task's eight block orders.
BLOCK_ORDERS = (
    ("2_back_place", "0_back_negface", "0_back_place", "2_back_posface",
     "0_back_neutface", "2_back_negface", "0_back_posface", "2_back_neutface"),
    ("2_back_neutface", "0_back_place", "2_back_posface", "0_back_neutface",
     "2_back_negface", "0_back_posface", "2_back_place", "0_back_negface"),
)  # fmt: skip
STIMULI = ("negface", "posface", "neutface", "place")

# ROI labels on the parcellation.
NULL_ROI, ACTIVE_ROI, CONTROL_ROI = 1, 2, 3
FD_THRESHOLD = 0.4  # proc_config_final.yaml, rest_conn
AFNI_MAX_CENSORED = 31  # Largest count 3dTproject accepts for 375 frames, 18 regressors, 0.01-0.1 Hz
TYPICAL_JERKS = (6, 6, 6, 6)  # 2 censored frames each: 3.2%, the median real rest run
TSNR = 75.0
AR1 = 0.4
REAL_DRIFT_P90 = (0.88, 0.61)  # +-% end to end: shared, and ROI deviation from shared


@dataclass
class Truth:
    """Known values the tests assert against."""

    rest_r: dict = field(default_factory=lambda: {(1, 2): 0.5, (1, 3): 0.0, (2, 3): 0.0})
    load_effect_psc: dict = field(default_factory=lambda: {NULL_ROI: 0.0, ACTIVE_ROI: 0.8, CONTROL_ROI: 0.0})


def _parcellation():
    parc = np.full(GRID, NULL_ROI, dtype=np.int16)
    parc[3:7] = ACTIVE_ROI
    parc[7:] = CONTROL_ROI
    return parc


def _save(path, data):
    affine = np.diag([-VOXEL_MM, -VOXEL_MM, VOXEL_MM, 1.0])
    img = nib.Nifti1Image(np.asarray(data), affine)
    if np.ndim(data) == 4:
        img.header.set_zooms((VOXEL_MM, VOXEL_MM, VOXEL_MM, TR))
        img.header.set_xyzt_units("mm", "sec")
    nib.save(img, str(path))
    return Path(path)


def ar1_noise(n_frames, sd, rho, rng):
    """(x, y, z, T) AR(1) noise, with the requested marginal sd."""
    shocks = rng.normal(0, sd * np.sqrt(1 - rho**2), (*GRID, n_frames))
    out = np.empty_like(shocks)
    out[..., 0] = rng.normal(0, sd, GRID)
    for t in range(1, n_frames):
        out[..., t] = rho * out[..., t - 1] + shocks[..., t]
    return out


def band_signal(n_frames, rng, low=0.01, high=0.1):
    """Unit-variance signal holding power only inside [low, high] Hz."""
    freqs = np.fft.rfftfreq(n_frames, TR)
    spectrum = (rng.normal(size=freqs.size) + 1j * rng.normal(size=freqs.size)) * ((freqs >= low) & (freqs <= high))
    signal = np.fft.irfft(spectrum, n_frames)
    return (signal - signal.mean()) / signal.std()


def motion(n_frames, n_jerks, rng, offset=None):
    """(T, 12) translations in mm, rotations in degrees, then first derivatives.

    Slow drift plus a respiratory oscillation inside the notch band, at the size seen in
    real rest runs. Each jerk is a transient that crosses FD_THRESHOLD after notch filtering.
    """
    base = np.cumsum(rng.normal(0, 0.006, (n_frames, 6)), axis=0)
    phase = 2 * np.pi * 0.37 * TR * np.arange(n_frames) + np.cumsum(rng.normal(0, 0.05, n_frames))
    base[:, 2] += 0.06 * np.sin(phase)
    base[:, 1] += 0.05 * np.sin(phase + 0.7)
    # Jerks stay apart, so each one censors its own frames.
    places = np.arange(12, n_frames - 12, 12)
    for t in rng.choice(places, size=n_jerks, replace=False):
        base[t : t + 3, :3] += rng.choice([-1, 1], 3) * 0.9
    if offset is not None:
        base += offset
    deriv = np.vstack([np.zeros(6), np.diff(base, axis=0)])
    return np.hstack([base, deriv])


def nback_events(frames=NBACK_FRAMES):
    """Events as abcd/staging.py hands them to the framework, in concatenated time."""
    rows = []
    for run, order in enumerate(BLOCK_ORDERS):
        start = run * frames * TR
        for cue, condition in zip(CUE_ONSETS, order, strict=True):
            # A 0-back cue shows the block's stimulus; a 2-back cue is only an instruction.
            load, stimulus = condition.split("_back_")
            rows.append((start + cue, CUE_DURATION, stimulus if load == "0" else "instruction"))
            first = cue + CUE_TO_TRIAL
            rows += [(start + first + i * TRIAL_SOA, TRIAL_DURATION, condition) for i in range(TRIALS_PER_BLOCK)]
    return pd.DataFrame(rows, columns=["onset", "duration", "trial_type"]).sort_values("onset", ignore_index=True)


def block_regressors(events, n_frames, workdir):
    """{condition: regressor} from 3dDeconvolve's own dmBLOCK model, so effects match the design exactly."""
    workdir = Path(workdir)
    conditions = sorted(events.trial_type.unique())
    cmd = ["3dDeconvolve", "-nodata", str(n_frames), str(TR), "-polort", "-1", "-num_stimts", str(len(conditions))]
    for k, condition in enumerate(conditions, start=1):
        rows = events[events.trial_type == condition]
        path = workdir / f"{condition}.times"
        path.write_text(" ".join(f"{o:.3f}:{d:.3f}" for o, d in zip(rows.onset, rows.duration, strict=True)) + "\n")
        cmd += ["-stim_times_AM1", str(k), str(path), "dmBLOCK", "-stim_label", str(k), condition]
    x1d = workdir / "truth.x1D"
    cmd += ["-x1D", str(x1d), "-x1D_stop", "-local_times"]
    subprocess.run(cmd, check=True, capture_output=True, cwd=workdir)
    matrix = np.loadtxt(x1d, comments="#", ndmin=2)
    return dict(zip(conditions, matrix.T, strict=True))


@dataclass
class Session:
    """Paths to one synthetic session."""

    root: Path
    parcellation: Path
    nback: dict
    nback_ge: dict
    rest: dict
    rest_high_motion: dict
    rest_drift: dict
    nback_null: dict
    truth: Truth


def _write_rest(root, tag, parc, rng, *, tsnr, rho, jerks, drift=None):
    runs = {"scan_paths": [], "motion_paths": [], "CSF_paths": [], "WM_paths": [], "GS_paths": []}
    for run in range(REST_RUNS):
        shared = band_signal(REST_FRAMES, rng)
        own = [band_signal(REST_FRAMES, rng) for _ in range(3)]
        # ROIs 1 and 2 share half their variance, so they correlate at 0.5 before noise.
        rois = {1: (shared + own[0]) / np.sqrt(2), 2: (shared + own[1]) / np.sqrt(2), 3: own[2]}
        psc = ar1_noise(REST_FRAMES, 100.0 / tsnr, rho, rng)
        for label, signal in rois.items():
            psc[parc == label] += 0.6 * signal
        # A whole-brain fluctuation the global signal regressor can remove. On a 3-ROI grid the
        # grid mean would mostly be ROI signal, so the regressor comes from this series instead.
        global_psc = 1.3 * band_signal(REST_FRAMES, rng, low=0.0, high=0.3)
        psc += global_psc
        if drift:
            # Linear drift, end to end: shared across the brain, plus a part that differs by ROI.
            ramp = np.linspace(-1, 1, REST_FRAMES)
            global_psc = global_psc + drift[0] * ramp
            psc += drift[0] * ramp[None, None, None, :]
            for label, sign in ((1, 1), (2, -1), (3, 1)):
                psc[parc == label] += sign * drift[1] * ramp
        data = 1000.0 * (1 + 0.01 * run) * (1 + psc / 100.0)
        stem = root / f"{tag}_run{run + 1}"
        runs["scan_paths"].append(str(_save(f"{stem}.nii.gz", data.astype(np.float32))))
        path = f"{stem}_motion.txt"
        np.savetxt(path, motion(REST_FRAMES, jerks[run], rng), fmt="%.6f")
        runs["motion_paths"].append(path)
        for key, series in (("CSF_paths", rng.normal(1000, 5, REST_FRAMES)),
                            ("WM_paths", rng.normal(1000, 5, REST_FRAMES)),
                            ("GS_paths", 1000.0 * (1 + 0.01 * run) * (1 + global_psc / 100.0))):  # fmt: skip
            path = f"{stem}_{key[:-6]}.txt"
            np.savetxt(path, series, fmt="%.6f")
            runs[key].append(path)
    return runs


def _write_nback(root, tag, parc, rng, *, tsnr, rho, effects, frames=NBACK_FRAMES):
    n_total = NBACK_RUNS * frames
    events = nback_events(frames)
    regressors = block_regressors(events, n_total, root)
    psc = ar1_noise(n_total, 100.0 / tsnr, rho, rng)
    for condition, regressor in regressors.items():
        for label, by_load in effects.items():
            beta = by_load.get(condition[:6], by_load.get("other", 0.0))
            psc[parc == label] += beta * regressor
    # Run 2 sits at a different baseline, as separately acquired runs do.
    gain = np.r_[np.full(frames, 1.0), np.full(frames, 1.02)]
    data = 1000.0 * gain * (1 + psc / 100.0)
    scan = _save(root / f"{tag}.nii.gz", data.astype(np.float32))
    events_path = root / f"{tag}_events.tsv"
    events.to_csv(events_path, sep="\t", index=False, float_format="%.3f")
    # ABCD's 3dvolreg parameters step between runs. This step's norm, 1.09, is near the real median.
    moves = np.vstack([motion(frames, 2, rng),
                       motion(frames, 2, rng, offset=np.array([0.8, 0.5, -0.4, 0.3, -0.2, 0.1]))])  # fmt: skip
    motion_path = root / f"{tag}_motion.txt"
    np.savetxt(motion_path, moves, fmt="%.6f")
    return {"scan_path": str(scan), "task_timing_path": str(events_path), "motion_path": str(motion_path),
            "CSF_path": None, "WM_path": None, "run_lengths": [frames] * NBACK_RUNS}  # fmt: skip


def build_session(root, seed=20261103, tsnr=TSNR, rho=AR1):
    """Write every dataset the tests use. Takes a few seconds."""
    root = Path(root)
    rng = np.random.default_rng(seed)
    parc = _parcellation()
    parcellation = _save(root / "parc.nii.gz", parc)
    load = {"0_back": 0.2, "2_back": 1.0}
    effects = {ACTIVE_ROI: load, NULL_ROI: {}, CONTROL_ROI: {}}
    return Session(
        root=root,
        parcellation=parcellation,
        nback=_write_nback(root, "nback", parc, rng, tsnr=tsnr, rho=rho, effects=effects),
        nback_null=_write_nback(root, "nback_null", parc, rng, tsnr=tsnr, rho=rho, effects={}),
        nback_ge=_write_nback(root, "nback_ge", parc, rng, tsnr=tsnr, rho=rho, effects=effects, frames=NBACK_FRAMES_GE),
        rest=_write_rest(root, "rest", parc, rng, tsnr=tsnr, rho=rho, jerks=TYPICAL_JERKS),
        # Run 3 passes AFNI's limit but sits below the 50% the package warns at.
        rest_high_motion=_write_rest(root, "rest_high", parc, rng, tsnr=tsnr, rho=rho, jerks=(6, 6, 20, 6)),
        rest_drift=_write_rest(root, "rest_drift", parc, rng, tsnr=tsnr, rho=rho, jerks=TYPICAL_JERKS, drift=REAL_DRIFT_P90),
        truth=Truth(),
    )
