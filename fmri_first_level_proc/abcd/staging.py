"""Run fmri_first_level_proc on one ABCD session held in a local directory.

The directory holds a session of cloudpipe-style func derivatives, one file per
object, with these names:

  _complete.json   its `runs` keys name the session's runs; nothing else does
  {subj}_{ses}_{task}_{run}_space-MNI152NLin2009cAsym_bold.nii.gz
  {subj}_{ses}_{task}_{run}_space-MNI152NLin2009cAsym_brainmask.nii.gz
  {subj}_{ses}_{task}_{run}_desc-confounds_timeseries.tsv
  {subj}_{ses}_task-nback_{run}_events.tsv
  {subj}_{ses}_space-MNI152NLin2009cAsym_res-1_label-{GM,WM,CSF}_probseg.nii.gz  (rest only)
  {subj}_{ses}_space-MNI152NLin2009cAsym_res-1_label-CSF_mask.nii.gz             (rest only)

Rest trims the frames its confounds flag as non-steady-state. n-back trims what its
events' `dummy` row states, because ABCD's onsets count from the first non-dummy volume
plus that row's length (see nback_trim), and uses only runs with valid E-Prime timing
(see validity.py). Motion is written translations first in degrees with first
derivatives, n-back cues are relabelled and `dummy` dropped, n-back runs are concatenated
with their lengths recorded for the task analyses, and rest runs stay separate.

Exit codes: 0 every analysis finished (some may be recorded `failed` with exit 5, or
skipped) and the result JSON is written; 1 a session failure, no result written.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path

import nibabel as nib
import numpy as np
import pandas as pd
import yaml
from scipy.ndimage import binary_dilation

MARKER = "_complete.json"
SPACE = "space-MNI152NLin2009cAsym"
SPACE_RES1 = f"{SPACE}_res-1"
TISSUES = ("GM", "WM", "CSF")
PROC_TEMPLATE = Path(__file__).resolve().parent / "data" / "proc_config_final.yaml"

# Per analysis in proc_config_final.yaml: its task and the post-ID parts of its
# prefixes (`sub-{ID}_{ses}_{post_id}`). Carried over unchanged from the retired
# orch_config_final.yaml `analyses` block.
ANALYSES = {
    "nback_act": {"task": "nback", "out": "nback", "extract": "nback_SchaeferTian"},
    "nback_conn": {
        "task": "nback",
        "out": "nback",
        "extract": "nback_SchaeferTian",
        "conn": "nback_SchaeferTian",
    },
    "rest_conn": {
        "task": "rest",
        "out": "rest",
        "extract": "rest_SchaeferTian",
        "conn": "rest_SchaeferTian",
    },
}

MOTION_BASE = ["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"]
EXCLUDE_CONDITIONS = ("dummy",)
# n-back timing. ABCD's GE discard moved from Hagler et al. 2019's 5 and 16 frames to 4 and
# 15 (ABCD 6.0 release notes), and each event file's `dummy` row states what applies to it.
# Only GE has an NSS count of 5 or 16. A complete run then keeps these many frames.
GE_NSS_COUNTS = (5, 16)
KEPT_FRAMES, KEPT_FRAMES_GE = 362, 363
# A cue starts this long before its block's first stimulus.
CUE_LEAD_SECONDS = 3.0
# Rest CSF/WM masks follow fMRIPrep's `acompcor_masks` + `acc_msk_bin`
# (nipreps/fmriprep, fmriprep/utils/confounds.py and workflows/bold/confounds.py,
# partial-volume route): GM > 0.05 dilated by a radius-3 ball at 1 mm is removed
# from WM only; both maps go to the BOLD grid, are brain-masked, and binarized at
# > 0.99. fMRIPrep resamples with ANTs Gaussian interpolation; this uses the exact
# 2x2x2 block mean, which is the one deliberate difference.
GM_PV_THRESHOLD = 0.05
GM_DILATION_RADIUS = 3
PROBSEG_THRESHOLD = 0.99  # WM
# CSF departs from fMRIPrep (operator, 2026-11-01): it is restricted to the ventricles
# by multiplying the CSF probseg by FastSurfer's 1 mm label-CSF_mask before the block
# mean, so the regressor is not brain-edge CSF. If > 0.99 leaves fewer than
# CSF_MIN_VOXELS, the threshold steps down the ladder; below the last rung rest is
# skipped. Calibrated on 150 sessions (100 baseline): > 0.99 gave 430-3,551 voxels,
# 1st percentile 529, so the floor of 100 fires only on a broken session.
CSF_THRESHOLD_LADDER = (0.99, 0.9, 0.5)
CSF_MIN_VOXELS = 100
# CLI exit codes (README). 5 is data-determined and does not fail the session; 1/2/4 do.
EXIT_OK, EXIT_HIGH_WARNINGS, EXIT_MODEL = 0, 3, 5


class SessionError(RuntimeError):
    """The session cannot be staged or run; no result is written."""


class RunExcluded(SessionError):
    """A rule excludes this run. The message is the reason the result records."""


def log(event: str, **fields) -> None:
    print(f"[first-level] {json.dumps({'event': event, **fields}, default=str)}", flush=True)


def run_cmd(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run an AFNI command, raising on failure. Module-level so tests can replace it."""
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kwargs)


def run_cli(cmd: list[str], cwd: str) -> int:
    """Run one fmri-first-level-proc analysis; its exit code. Output streams to the
    pod log. Module-level so tests can replace it."""
    return subprocess.run(cmd, cwd=cwd).returncode


def _cgroup_cpu_limit(root: Path = Path("/sys/fs/cgroup")) -> int | None:
    """Whole CPUs the cgroup quota allows (v2 cpu.max, else v1 CFS), or None if unlimited."""
    try:
        quota, period = (root / "cpu.max").read_text().split()[:2]
        return None if quota == "max" else max(1, int(quota) // int(period))
    except (OSError, ValueError):
        pass
    try:
        quota = int((root / "cpu" / "cpu.cfs_quota_us").read_text())
        period = int((root / "cpu" / "cpu.cfs_period_us").read_text())
        return max(1, quota // period) if quota > 0 and period > 0 else None
    except (OSError, ValueError):
        return None


def available_cpus() -> int:
    """The template's `num_cores: auto`: OMP_NUM_THREADS (the pod's CPU request) capped at
    the cgroup limit, else that limit, else the CPUs this process may run on."""
    limit = _cgroup_cpu_limit()
    omp = os.environ.get("OMP_NUM_THREADS", "").strip()
    if omp.isdigit() and int(omp) > 0:
        return min(int(omp), limit) if limit else int(omp)
    return limit or len(os.sched_getaffinity(0)) or 1


def run_label(rid: str) -> int:
    """task-nback_run-02 -> 2, the run identity the framework reports."""
    match = re.search(r"_run-(\d+)$", rid)
    if match is None:
        raise SessionError(f"{rid}: no run number")
    return int(match.group(1))


def package_version() -> str | None:
    try:
        return metadata.version("fmri-first-level-proc")
    except metadata.PackageNotFoundError:
        return None


def probseg_names(subj: str, ses: str) -> list[str]:
    return [f"{subj}_{ses}_{SPACE_RES1}_label-{t}_probseg.nii.gz" for t in TISSUES]


# ---------------------------------------------------------------------------
# Pure staging steps
# ---------------------------------------------------------------------------


def nss_count(confounds: pd.DataFrame) -> int:
    """Frames to trim: the number of non_steady_state_outlier_* columns."""
    return sum(1 for c in confounds.columns if c.startswith("non_steady_state_outlier"))


def motion_matrix(confounds: pd.DataFrame, n_remove: int) -> np.ndarray:
    """(T - n_remove, 12): base motion translations first, then first derivatives.

    ABCD's rotations are already degrees, unlike standard fMRIPrep's radians: its n-back
    framewise_displacement equals sum|d trans| + (pi/180)*50*sum|d rot| on these columns.

    Derivatives are taken on the untrimmed series (row 1 = 0) and trimmed with it,
    as the retired orchestrator did. NaN becomes 999.0 after trimming so the
    FD threshold censors that TR.
    """
    missing = [c for c in MOTION_BASE if c not in confounds.columns]
    if missing:
        raise SessionError(f"confounds lack motion columns {missing}")
    base = confounds[MOTION_BASE].to_numpy(dtype=float)
    if np.isnan(base).all(axis=0).any():
        dead = [c for c, d in zip(MOTION_BASE, np.isnan(base).all(axis=0), strict=True) if d]
        raise SessionError(f"motion columns entirely NaN: {dead}")
    deriv = np.vstack([np.zeros((1, 6)), np.diff(base, axis=0)])
    out = np.hstack([base, deriv])[n_remove:]
    return np.where(np.isnan(out), 999.0, out)


def global_signal(confounds: pd.DataFrame, n_remove: int) -> np.ndarray:
    """The rest GSR regressor: the confounds' `global_signal` (mean within the brain
    mask), trimmed. The retired orchestrator passed this as GS_paths for every rest
    run, overriding the template's `GS_paths: null`, so rest has always used GSR."""
    if "global_signal" not in confounds.columns:
        raise SessionError("confounds lack global_signal")
    gs = confounds["global_signal"].to_numpy(dtype=float)[n_remove:]
    if np.isnan(gs).any():
        raise SessionError("global_signal has NaN")
    return gs


_NBACK = re.compile(r"^(\d+)_back_(.+)$")


def fix_nback_cue_labels(events: pd.DataFrame, column: str = "trial_type") -> pd.DataFrame:
    """Relabel `cue` rows from the block that follows: 0-back -> the bare condition
    (`posface`), any other level -> `instruction`. Ported from the retired
    orchestrator's fix_nback_cue_labels, behaviour unchanged."""
    out = events.copy()
    labels = [str(v).strip().strip('"') for v in out[column]]
    for i, label in enumerate(labels):
        if label.lower() != "cue":
            continue
        match = next((m for m in map(_NBACK.match, labels[i + 1 :]) if m), None)
        if match is None:
            raise SessionError(f"cue at row {i} has no following n-back trial")
        level, condition = match.groups()
        labels[i] = condition if level == "0" else "instruction"
    out[column] = labels
    return out


def _labels(events: pd.DataFrame) -> pd.Series:
    return events["trial_type"].astype(str).str.strip().str.strip('"')


def nback_trim(events: pd.DataFrame, n_nss: int, frames: int, tr: float) -> tuple[int, float]:
    """(frames to trim, seconds to subtract from onsets) for one n-back run, or RunExcluded.

    ABCD's converter writes `onset = time since the first non-dummy volume + the dummy
    row's duration`, so subtracting that duration is right in every run, including runs
    whose `dummy` is 0 and whose onsets carry no pad (a task-response test put those 6.4 s
    later than normal runs). The frames follow the `dummy` row, or the NSS count when it
    is 0. A file with any other shape has an unknown clock, so the run is excluded.
    """
    labels = _labels(events)
    if labels.isin(EXCLUDE_CONDITIONS).all():
        raise RunExcluded("no-task-events")
    rows = events.loc[labels == "dummy", "duration"]
    if rows.empty:
        raise RunExcluded("no-dummy-row")
    seconds = float(rows.iloc[0])
    dummy_frames = round(seconds / tr)
    if abs(seconds / tr - dummy_frames) > 1e-3:
        raise RunExcluded("unexpected-dummy")
    is_ge = n_nss in GE_NSS_COUNTS
    if dummy_frames == 0:
        n_remove = n_nss
    elif is_ge and dummy_frames == n_nss:
        # Every other GE run logs one frame fewer: an uncorrected file, up to 0.8 s off.
        raise RunExcluded("predates-ge-timing-correction")
    elif dummy_frames in (n_nss, n_nss - 1):
        n_remove = dummy_frames
    else:
        raise RunExcluded("unexpected-dummy")
    # A wrong scanner label leaves `dummy` disagreeing with the file, and a short run's
    # events pass its end and would spill into the next run's time.
    if frames - n_remove != (KEPT_FRAMES_GE if is_ge else KEPT_FRAMES):
        raise RunExcluded("unexpected-frame-count")
    return n_remove, seconds


def repair_stray_cue(
    first: pd.DataFrame, second: pd.DataFrame, first_frames: int, tr: float
) -> tuple[pd.DataFrame, pd.DataFrame, bool]:
    """Return a next run's first cue from the end of this run, where ABCD's converter can
    put it: it starts a moment before that run's reference time, so it counts as this run's.

    Moves the cue only when this run's last cue has no following trial and starts after
    this run's last frame, and the next run's first trial precedes its first cue. Any
    other shape is left alone, and fix_nback_cue_labels then excludes the run.
    """
    labels = _labels(first)
    cues = first.index[labels.str.lower() == "cue"]
    if not len(cues):
        return first, second, False
    last = cues[-1]
    has_trial_after = labels.loc[last:].str.match(_NBACK).any()
    if has_trial_after or float(first.at[last, "onset"]) <= first_frames * tr:
        return first, second, False
    next_labels = _labels(second)
    trials = second.loc[next_labels.str.match(_NBACK), "onset"].astype(float)
    if trials.empty:
        return first, second, False
    next_cues = second.loc[next_labels.str.lower() == "cue", "onset"].astype(float)
    if not next_cues.empty and next_cues.min() < trials.min():
        return first, second, False
    moved = first.loc[[last]].copy()
    moved["onset"] = trials.min() - CUE_LEAD_SECONDS
    second = pd.concat([second, moved], ignore_index=True)
    second["onset"] = second["onset"].astype(float)
    return (
        first.drop(index=last).reset_index(drop=True),
        second.sort_values("onset", kind="stable").reset_index(drop=True),
        True,
    )


def load_validity(path: Path, subj: str, ses: str) -> dict[str, tuple[bool, str]]:
    """{run id: (use, reason)} for one session, from the table validity.py builds."""
    out = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["subject_id"] == subj and row["session"] == ses:
                out[row["run"]] = (row["use"] == "1", row["reason"])
    return out


def stage_events(events: pd.DataFrame, shift: float) -> tuple[pd.DataFrame, int]:
    """BIDS onset/duration/trial_type: cues relabelled, `dummy` dropped, onsets
    shifted by `shift` seconds. Returns (events, events dropped for a negative onset)."""
    ev = fix_nback_cue_labels(events)
    ev = ev[~ev["trial_type"].isin(EXCLUDE_CONDITIONS)].copy()
    ev["onset"] = ev["onset"].astype(float) - shift
    negative = ev["onset"] < 0
    ev = ev[~negative]
    ev = ev[["onset", "duration", "trial_type"]].sort_values("onset", kind="stable")
    return ev.reset_index(drop=True), int(negative.sum())


def concat_events(runs: list[tuple[pd.DataFrame, int]], tr: float) -> pd.DataFrame:
    """Concatenate per-run events, offsetting each by the earlier runs' trimmed
    length. `runs` is [(events, n_frames_after_trim), ...] in run order."""
    parts, offset = [], 0.0
    for ev, n_frames in runs:
        shifted = ev.copy()
        shifted["onset"] = shifted["onset"] + offset
        parts.append(shifted)
        offset += n_frames * tr
    return pd.concat(parts, ignore_index=True)


def block_mean_to_grid(prob: nib.Nifti1Image, ref: nib.Nifti1Image) -> np.ndarray:
    """Each `ref` voxel's mean over the 2x2x2 `prob` voxels it covers exactly.

    Both images must be axis-aligned, and `ref`'s voxel edges must fall on
    `prob`'s at a 2:1 ratio. On cloudpipe's grids the 2 mm centres sit half a
    millimetre off the 1 mm centres, so each 2 mm voxel covers exactly 8 whole 1 mm
    voxels. Anything else is refused rather than interpolated. Voxels outside
    `prob`'s field of view count as 0.
    """
    pa, ra = prob.affine, ref.affine
    for a, name in ((pa, "probseg"), (ra, "reference")):
        if not np.allclose(a[:3, :3], np.diag(np.diag(a[:3, :3])), atol=1e-4):
            raise SessionError(f"{name} grid is not axis-aligned")
    # ref voxel index -> prob continuous index, per axis: p = scale * r + shift
    to_prob = np.linalg.inv(pa) @ ra
    scale, shift = np.diag(to_prob)[:3], to_prob[:3, 3]
    if not np.allclose(np.abs(scale), 2.0, atol=1e-4):
        raise SessionError(f"grids are not 2:1 (scale {scale.round(4).tolist()})")
    # A 2:1 voxel covers prob centres at p-0.5 and p+0.5; both must be integers.
    frac = (shift - 0.5) % 1.0
    if not np.all(np.minimum(frac, 1.0 - frac) < 1e-3):
        raise SessionError(f"voxel edges do not nest (offset {shift.round(4).tolist()})")

    data = np.asarray(prob.dataobj, dtype=np.float32)
    total = np.zeros(ref.shape[:3], dtype=np.float32)
    grids = [np.arange(n) for n in ref.shape[:3]]
    for dx in (-0.5, 0.5):
        for dy in (-0.5, 0.5):
            for dz in (-0.5, 0.5):
                idx = [
                    np.rint(scale[k] * grids[k] + shift[k] + d).astype(int)
                    for k, d in enumerate((dx, dy, dz))
                ]
                ok = [(i >= 0) & (i < n) for i, n in zip(idx, data.shape[:3], strict=True)]
                block = np.zeros(ref.shape[:3], dtype=np.float32)
                ix = np.ix_(*(i[o] for i, o in zip(idx, ok, strict=True)))
                block[np.ix_(*(np.flatnonzero(o) for o in ok))] = data[ix]
                total += block
    return total / 8.0


def ball(radius: int) -> np.ndarray:
    """skimage.morphology.ball(radius): voxels with x² + y² + z² <= radius²."""
    r = np.arange(-radius, radius + 1)
    x, y, z = np.meshgrid(r, r, r, indexing="ij")
    return x**2 + y**2 + z**2 <= radius**2


def dilated_gm(gm: nib.Nifti1Image) -> np.ndarray:
    """fMRIPrep's GM exclusion: GM partial volume > 0.05, dilated by ball(3), on
    the probseg's own 1 mm grid."""
    gm_data = np.asarray(gm.dataobj, dtype=np.float32) > GM_PV_THRESHOLD
    return binary_dilation(gm_data, structure=ball(GM_DILATION_RADIUS))


def tissue_masks_from_probseg(
    gm: nib.Nifti1Image,
    wm: nib.Nifti1Image,
    csf: nib.Nifti1Image,
    csf_label: nib.Nifti1Image,
    brainmask: nib.Nifti1Image,
    *,
    gm_exclusion: np.ndarray | None = None,
) -> tuple[dict[str, np.ndarray], str | None, float | None]:
    """WM and CSF masks on `brainmask`'s grid, or a skip reason.

    WM, as fMRIPrep builds `white_matter`: zero the WM partial volume wherever
    dilated GM is, block-mean onto the BOLD grid, brain-mask, keep > 0.99.

    CSF, ventricle-restricted: the CSF partial volume times FastSurfer's 1 mm
    `label-CSF_mask`, block-meaned and brain-masked, kept above the first threshold
    in CSF_THRESHOLD_LADDER that leaves at least CSF_MIN_VOXELS voxels.

    Returns (masks, None, csf_threshold), or ({}, reason, None) with reason
    "empty-WM-mask" or "csf-mask-too-small". `gm_exclusion` lets a caller reuse
    one session's dilated GM across runs.
    """
    if not (np.allclose(csf_label.affine, csf.affine) and csf_label.shape == csf.shape):
        raise SessionError("label-CSF_mask and CSF probseg are not on one grid")
    if gm_exclusion is None:
        gm_exclusion = dilated_gm(gm)
    brain = np.asarray(brainmask.dataobj) > 0

    wm_data = np.asarray(wm.dataobj, dtype=np.float32).copy()
    wm_data[gm_exclusion] = 0.0
    wm_frac = block_mean_to_grid(nib.Nifti1Image(wm_data, wm.affine), brainmask)
    wm_mask = (wm_frac > PROBSEG_THRESHOLD) & brain
    if not wm_mask.any():
        return {}, "empty-WM-mask", None

    ventricles = np.asarray(csf.dataobj, dtype=np.float32) * (np.asarray(csf_label.dataobj) > 0)
    csf_frac = block_mean_to_grid(nib.Nifti1Image(ventricles, csf.affine), brainmask)
    for threshold in CSF_THRESHOLD_LADDER:
        csf_mask = (csf_frac > threshold) & brain
        if csf_mask.sum() >= CSF_MIN_VOXELS:
            return {"WM": wm_mask, "CSF": csf_mask}, None, threshold
    return {}, "csf-mask-too-small", None


def analysis_prefixes(subj: str, ses: str, name: str) -> dict[str, str]:
    spec = ANALYSES[name]
    base = f"{subj}_{ses}"
    out = {"out_file_pre": f"{base}_{spec['out']}", "extract": f"{base}_{spec['extract']}"}
    if "conn" in spec:
        out["conn"] = f"{base}_{spec['conn']}"
    return out


def fill_config(
    template: dict, subj: str, ses: str, staged: dict[str, dict], out_root: Path, atlas: str
) -> dict:
    """The template with its atlas and subject-specific fields filled; every analysis
    setting is left as the template has it. `staged` maps analysis name -> its `paths`
    block. Analyses absent from `staged` are dropped (rest skipped, a task with no runs)."""
    cfg = copy.deepcopy(template)
    unknown = [b["name"] for b in cfg["analyses"] if b["name"] not in ANALYSES]
    if unknown:
        raise SessionError(f"proc template analyses with no prefix rule: {unknown}")
    cfg["global"]["template_path"] = atlas
    if cfg["global"].get("num_cores") == "auto":
        cfg["global"]["num_cores"] = available_cpus()
    blocks = []
    for block in cfg["analyses"]:
        name = block["name"]
        if name not in staged:
            continue
        pre = analysis_prefixes(subj, ses, name)
        paths = dict(staged[name])  # the n-back analyses share one staged dict
        for key in ("run_lengths", "run_labels"):  # block-level keys, not paths
            if key in paths:
                block[key] = paths.pop(key)
        block["paths"] = paths
        block["out_dir"] = str(out_root / name)
        block["out_file_pre"] = pre["out_file_pre"]
        if block.get("extraction"):
            block["extraction"]["extract_out_file_pre"] = pre["extract"]
        if block.get("connectivity") and "conn" in pre:
            block["connectivity"]["conn_out_file_pre"] = pre["conn"]
        blocks.append(block)
    cfg["analyses"] = blocks
    return cfg


def classify_exit(code: int) -> dict:
    """One analysis's CLI exit -> its result entry; raises for session failures."""
    if code in (EXIT_OK, EXIT_HIGH_WARNINGS):
        return {"status": "completed", "exit_code": code, "high_warnings": code == 3}
    if code == EXIT_MODEL:
        return {"status": "failed", "exit_code": code, "high_warnings": False}
    raise SessionError(f"fmri-first-level-proc exited {code}")


# ---------------------------------------------------------------------------
# File and AFNI steps
# ---------------------------------------------------------------------------


@dataclass
class Run:
    rid: str  # task-nback_run-01
    task: str  # nback
    n_remove: int = 0
    n_frames: int = 0
    bold: Path | None = None
    motion: Path | None = None
    gs: Path | None = None  # rest only: the trimmed global_signal confound
    events: pd.DataFrame | None = None
    brainmask: Path | None = None
    dropped_events: int = 0
    excluded: str | None = None
    extra: dict = field(default_factory=dict)
    raw_events: pd.DataFrame | None = None  # n-back: as read, with any cue repair applied
    onset_shift: float = 0.0  # n-back: seconds nback_trim says to subtract
    failed: bool = False  # staging raised, so `excluded` may be a fault, not a rule


def _bold_frames_and_tr(path: Path) -> tuple[int, float]:
    img = nib.load(str(path))
    return int(img.shape[3]), float(img.header.get_zooms()[3])


def stage_run(run: Run, raw: dict[str, Path], tr: float, mask: Path, work: Path) -> None:
    """Trim + mask the BOLD, write motion, stage events. Mutates `run`. An n-back run
    arrives with n_remove set by screen_nback_runs; a rest run counts its NSS columns."""
    confounds = pd.read_csv(raw["confounds"], sep="\t")
    if run.task == "rest":
        run.n_remove = nss_count(confounds)
    frames, bold_tr = _bold_frames_and_tr(raw["bold"])
    if abs(bold_tr - tr) > 1e-3:
        raise SessionError(f"{run.rid}: BOLD TR {bold_tr} != config TR {tr}")
    if len(confounds) != frames:
        raise SessionError(f"{run.rid}: {len(confounds)} confound rows, {frames} frames")
    run.n_frames = frames - run.n_remove
    if run.n_frames < 2:
        raise SessionError(f"{run.rid}: trimming {run.n_remove} frames leaves {run.n_frames}")
    run.bold = work / f"{run.rid}_bold.nii.gz"
    run_cmd(
        [
            "3dcalc",
            "-a",
            f"{raw['bold']}[{run.n_remove}..$]",
            "-b",
            str(mask),
            "-expr",
            "a*step(b)",
            "-datum",
            "float",
            "-prefix",
            str(run.bold),
        ]
    )
    run.motion = work / f"{run.rid}_motion.1D"
    np.savetxt(run.motion, motion_matrix(confounds, run.n_remove), fmt="%.10g", delimiter="\t")
    if run.task == "rest":
        run.gs = work / f"{run.rid}_gs.1D"
        np.savetxt(run.gs, global_signal(confounds, run.n_remove), fmt="%.10g")
    if run.raw_events is not None:
        run.events, run.dropped_events = stage_events(run.raw_events, run.onset_shift)


def intersect_masks(paths: list[Path], dest: Path) -> Path:
    imgs = [nib.load(str(p)) for p in paths]
    data = np.logical_and.reduce([np.asarray(i.dataobj) > 0 for i in imgs])
    nib.save(nib.Nifti1Image(data.astype(np.uint8), imgs[0].affine), str(dest))
    return dest


def maskave(bold: Path, mask: np.ndarray, ref: nib.Nifti1Image, dest: Path) -> Path:
    mask_path = dest.with_suffix(".mask.nii.gz")
    nib.save(nib.Nifti1Image(mask.astype(np.uint8), ref.affine), str(mask_path))
    result = run_cmd(["3dmaskave", "-quiet", "-mask", str(mask_path), str(bold)])
    dest.write_text(result.stdout)
    return dest


@dataclass
class Session:
    subj: str
    ses: str
    input_dir: Path
    probseg_state: str
    work: Path
    validity: dict[str, tuple[bool, str]] = field(default_factory=dict)

    def path(self, name: str) -> Path:
        path = self.input_dir / name
        if not path.is_file():
            raise SessionError(f"missing input {name}")
        return path

    def read_marker(self) -> dict:
        path = self.input_dir / MARKER
        if not path.is_file():
            raise SessionError(f"no func {MARKER} for {self.subj} {self.ses}")
        return json.loads(path.read_text())

    def runs_by_task(self, marker: dict) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for rid in sorted(marker.get("runs") or {}):
            task = rid.split("_", 1)[0].removeprefix("task-")
            out.setdefault(task, []).append(rid)
        return out

    def raw_inputs(self, rid: str, task: str) -> dict[str, Path]:
        stem = f"{self.subj}_{self.ses}_{rid}"
        names = {
            "bold": f"{stem}_{SPACE}_bold.nii.gz",
            "brainmask": f"{stem}_{SPACE}_brainmask.nii.gz",
            "confounds": f"{stem}_desc-confounds_timeseries.tsv",
        }
        if task == "nback":
            names["events"] = f"{stem}_events.tsv"
        return {k: self.path(n) for k, n in names.items()}

    def screen_nback_runs(self, runs: list[Run], raws: dict, tr: float) -> None:
        """Apply the n-back rules before any AFNI work: run validity, the cue repair, and
        each run's trim. A run a rule excludes is marked `excluded` with its reason."""
        frames = {}
        for run in runs:
            run.raw_events = pd.read_csv(raws[run.rid]["events"], sep="\t")
            frames[run.rid] = _bold_frames_and_tr(raws[run.rid]["bold"])[0]
        for this, following in zip(runs, runs[1:], strict=False):
            this.raw_events, following.raw_events, moved = repair_stray_cue(
                this.raw_events, following.raw_events, frames[this.rid], tr
            )
            if moved:
                this.extra["cue_moved_to"] = following.rid
                following.extra["cue_moved_from"] = this.rid
                log("cue-moved", run=this.rid, to=following.rid)
        for run in runs:
            try:
                use, reason = self.validity.get(run.rid, (False, "no-validity-row"))
                if not use:
                    raise RunExcluded(reason)
                confounds = pd.read_csv(raws[run.rid]["confounds"], sep="\t")
                run.n_remove, run.onset_shift = nback_trim(
                    run.raw_events, nss_count(confounds), frames[run.rid], tr
                )
            except RunExcluded as exc:
                run.excluded = str(exc)
                log("run-excluded", run=run.rid, reason=run.excluded)

    def stage_task(self, task: str, rids: list[str], tr: float) -> tuple[list[Run], dict]:
        """Stage every run of `task`; returns (runs, raws). Failed runs are kept,
        marked `excluded`, so the result records them."""
        runs = [Run(rid=rid, task=task) for rid in rids]
        raws = {r.rid: self.raw_inputs(r.rid, task) for r in runs}
        if task == "nback":
            self.screen_nback_runs(runs, raws, tr)
        # n-back runs are concatenated, so each is masked by the used runs' intersection;
        # rest runs stay separate and keep their own mask.
        mask = None
        used = [r for r in runs if not r.excluded]
        if task == "nback" and used:
            mask = intersect_masks(
                [raws[r.rid]["brainmask"] for r in used], self.work / "nback_mask.nii.gz"
            )
        for run in used:
            try:
                stage_run(run, raws[run.rid], tr, mask or raws[run.rid]["brainmask"], self.work)
            except (SessionError, subprocess.CalledProcessError, ValueError, KeyError) as exc:
                # A cue with no following trial lands here: a shape repair_stray_cue left.
                run.excluded, run.failed = f"{type(exc).__name__}: {exc}", True
                log("run-excluded", run=run.rid, reason=run.excluded)
        return runs, raws

    def nback_paths(self, runs: list[Run], tr: float) -> dict | None:
        ok = [r for r in runs if not r.excluded]
        if not ok:
            return None
        bold = self.work / "nback_concat_bold.nii.gz"
        if len(ok) == 1:
            bold = ok[0].bold
        else:
            run_cmd(["3dTcat", "-prefix", str(bold), *[str(r.bold) for r in ok]])
        motion = self.work / "nback_concat_motion.1D"
        np.savetxt(
            motion,
            np.vstack([np.loadtxt(r.motion, ndmin=2) for r in ok]),
            fmt="%.10g",
            delimiter="\t",
        )
        events = self.work / "nback_concat_events.tsv"
        concat_events([(r.events, r.n_frames) for r in ok], tr).to_csv(
            events, sep="\t", index=False
        )
        return {
            "scan_path": str(bold),
            "task_timing_path": str(events),
            "motion_path": str(motion),
            "run_lengths": [r.n_frames for r in ok],
            "run_labels": [run_label(r.rid) for r in ok],
            "CSF_path": None,
            "WM_path": None,
        }

    def rest_paths(self, runs: list[Run], raws: dict) -> tuple[dict | None, str | None]:
        ok = [r for r in runs if not r.excluded]
        if not ok:
            return None, "no-rest-runs"
        if self.probseg_state != "fixed":
            return None, f"probseg-{self.probseg_state}"
        prob = {}
        for name in probseg_names(self.subj, self.ses):
            tissue = name.rsplit("_label-", 1)[1].split("_", 1)[0]
            prob[tissue] = nib.load(str(self.path(name)))
        # FastSurfer's ventricle-dominated CSF label restricts the CSF regressor. It
        # never had the probseg defect, so it needs no probseg-state check of its own.
        label = f"{self.subj}_{self.ses}_{SPACE_RES1}_label-CSF_mask.nii.gz"
        csf_label = nib.load(str(self.path(label)))
        gm_exclusion = dilated_gm(prob["GM"])  # once: the probseg is per session
        csf, wm = [], []
        for run in ok:  # per session, but each run has its own brain mask
            ref = nib.load(str(raws[run.rid]["brainmask"]))
            masks, reason, csf_threshold = tissue_masks_from_probseg(
                prob["GM"], prob["WM"], prob["CSF"], csf_label, ref, gm_exclusion=gm_exclusion
            )
            if reason:
                return None, reason
            run.extra = {
                "mask_voxels": {t: int(m.sum()) for t, m in masks.items()},
                "csf_threshold": csf_threshold,  # the ladder rung used; 0.99 normally
            }
            wm.append(str(maskave(run.bold, masks["WM"], ref, self.work / f"{run.rid}_wm.1D")))
            csf.append(str(maskave(run.bold, masks["CSF"], ref, self.work / f"{run.rid}_csf.1D")))
        return {
            "scan_paths": [str(r.bold) for r in ok],
            "motion_paths": [str(r.motion) for r in ok],
            "CSF_paths": csf,
            "WM_paths": wm,
            "GS_paths": [str(r.gs) for r in ok],  # see global_signal(): GSR as before
            "run_labels": [run_label(r.rid) for r in ok],
        }, None


def _result(sess: Session, analyses: dict, runs: list[Run]) -> dict:
    return {
        "package_version": package_version(),
        "probseg_state": sess.probseg_state,
        "analyses": analyses,
        "runs": {
            r.rid: (
                {"excluded": r.excluded, **r.extra}
                if r.excluded
                else {
                    "n_remove": r.n_remove,
                    "n_frames": r.n_frames,
                    "dropped_events": r.dropped_events,
                    **r.extra,  # n-back: any cue move; rest: mask_voxels and csf_threshold
                }
            )
            for r in runs
        },
    }


def note_runs_excluded_by_analysis(block: dict, runs: list[Run]) -> None:
    """Record on each rest run whether rest_conn's QC says it left the analysis."""
    qc = Path(block["out_dir"]) / f"{block['out_file_pre']}_qc_summary.json"
    staged = [r for r in runs if not r.excluded]  # the order rest_paths passed them in
    for record in json.loads(qc.read_text()).get("excluded_runs", []):
        staged[record["run"] - 1].extra["excluded_by_analysis"] = record["reason"]


def run_session(sess: Session, template: dict, out_root: Path, atlas: str) -> dict:
    """Stage, run and return the session's result. Raises SessionError."""
    marker = sess.read_marker()
    sess.work.mkdir(parents=True, exist_ok=True)
    tr = float(template["global"]["tr"])
    by_task = sess.runs_by_task(marker)
    all_runs: list[Run] = []
    staged: dict[str, dict] = {}
    skipped: dict[str, str] = {}

    nback_runs, _ = sess.stage_task("nback", by_task.get("nback", []), tr)
    all_runs += nback_runs
    nback = sess.nback_paths(nback_runs, tr)
    for name in ("nback_act", "nback_conn"):
        if nback:
            staged[name] = nback
        else:
            skipped[name] = "no-nback-runs"

    rest_runs, rest_raws = sess.stage_task("rest", by_task.get("rest", []), tr)
    all_runs += rest_runs
    rest, reason = sess.rest_paths(rest_runs, rest_raws)
    if rest:
        staged["rest_conn"] = rest
    else:
        skipped["rest_conn"] = reason

    if not staged:
        # Rules excluded everything, or the session has nothing eligible: a settled answer,
        # so it finishes and says why, and a queue need not resubmit it. A run that failed
        # staging is different: it may be a fault.
        failed = [r.rid for r in all_runs if r.failed]
        if failed or not all_runs:
            raise SessionError(f"nothing to run: {skipped}; failed runs: {failed}")
        analyses = {name: {"status": "skipped", "reason": why} for name, why in skipped.items()}
        result = _result(sess, analyses, all_runs)
        out_root.mkdir(parents=True, exist_ok=True)
        (out_root / f"{sess.subj}_{sess.ses}_first_level_skipped.json").write_text(json.dumps(result))
        log("session-skipped", skipped=skipped)
        return result

    cfg = fill_config(template, sess.subj, sess.ses, staged, out_root, atlas)
    # The CLI uses num_cores for its own work; AFNI takes this from the environment.
    os.environ["OMP_NUM_THREADS"] = str(cfg["global"]["num_cores"])
    out_root.mkdir(parents=True, exist_ok=True)
    config_path = out_root / f"{sess.subj}_{sess.ses}_first_level_config.yaml"
    config_path.write_text(yaml.safe_dump(cfg, sort_keys=False))

    analyses = {name: {"status": "skipped", "reason": why} for name, why in skipped.items()}
    for i, block in enumerate(cfg["analyses"]):
        name = block["name"]
        Path(block["out_dir"]).mkdir(parents=True, exist_ok=True)
        cmd = [
            "fmri-first-level-proc",
            "--config",
            str(config_path),
            "--analyses",
            str(i),
            "--log-file",
            str(Path(block["out_dir"]) / f"{name}_log.txt"),
        ]
        log("analysis-start", analysis=name)
        # Run from the out_dir: 3dDeconvolve writes 3dDeconvolve.err to the cwd.
        code = run_cli(cmd, cwd=block["out_dir"])
        analyses[name] = classify_exit(code)
        log("analysis-end", analysis=name, **analyses[name])
        if name == "rest_conn" and analyses[name]["status"] == "completed":
            note_runs_excluded_by_analysis(block, rest_runs)

    return _result(sess, analyses, all_runs)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--subj", required=True, help="sub-... as it appears in the file names")
    ap.add_argument("--ses", required=True, help="ses-... as it appears in the file names")
    ap.add_argument("--input-dir", type=Path, required=True, help="the session's files")
    ap.add_argument(
        "--probseg-state",
        required=True,
        help="`fixed` runs rest; anything else skips rest and records the reason",
    )
    ap.add_argument("--workdir", type=Path, required=True, help="staged inputs go here")
    ap.add_argument("--out-dir", type=Path, required=True, help="analysis outputs go here")
    ap.add_argument("--atlas", required=True, help="the parcellation, the config's template_path")
    ap.add_argument("--result", type=Path, required=True, help="write the result JSON here")
    ap.add_argument(
        "--run-validity",
        type=Path,
        required=True,
        help="the per-run table `fmri-first-level-abcd-validity` builds",
    )
    ap.add_argument("--template", type=Path, default=PROC_TEMPLATE)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    validity = load_validity(args.run_validity, args.subj, args.ses)
    sess = Session(args.subj, args.ses, args.input_dir, args.probseg_state, args.workdir, validity)
    template = yaml.safe_load(args.template.read_text())
    try:
        result = run_session(sess, template, args.out_dir, args.atlas)
    except SessionError as exc:
        log("session-failed", error=str(exc))
        return 1
    args.result.write_text(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
