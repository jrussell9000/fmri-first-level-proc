"""Run fmri_first_level_proc on one ABCD session held in a local directory.

The directory holds a session of cloudpipe-style func derivatives, one file per
object, with these names:

  _complete.json   its `runs` keys name the session's runs; nothing else does
  {subj}_{ses}_{task}_{run}_space-MNI152NLin2009cAsym_bold.nii.gz
  {subj}_{ses}_{task}_{run}_space-MNI152NLin2009cAsym_brainmask.nii.gz
  {subj}_{ses}_{task}_{run}_desc-confounds_timeseries.tsv  (rest: with `white_matter`, `csf`)
  {subj}_{ses}_task-nback_{run}_events.tsv

Rest trims the frames its confounds flag as non-steady-state. n-back trims what its
events' `dummy` row states, because ABCD's onsets count from the first non-dummy volume
plus that row's length (see nback_trim), and uses only runs with valid E-Prime timing
(see validity.py). Motion is written translations first in degrees with first
derivatives, n-back cues are relabelled and `dummy` dropped, and every run stays a
separate file with its run-local events.

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

from ..engine import SHARE_DIR_ENV
from ..names import concat_scan, psc_concat

MARKER = "_complete.json"
SPACE = "space-MNI152NLin2009cAsym"
# Rest's nuisance tissues -> their confounds columns. cloudpipe's func preproc computes them
# as the orchestrator does (FastSurfer's 1 mm label masks), since 4.0.0+cp.10 read from there.
TISSUE_COLUMNS = {"WM": "white_matter", "CSF": "csf"}
PROC_TEMPLATE = Path(__file__).resolve().parent / "data" / "proc_config_final.yaml"
# Schaefer 400 + Tian S4 in MNI152NLin2009cAsym at 2 mm; data/atlas/README.md has its source,
# licences and citations.
PACKAGED_ATLAS = (
    Path(__file__).resolve().parent
    / "data"
    / "atlas"
    / "Schaefer2018_400Parcels_7Networks_order_Tian_Subcortex_S4_3T_MNI152NLin2009cAsym_2mm.nii.gz"
)

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
# The task's events, first to last onset, span a fixed schedule: on all 58,589 ABCD 7.0 runs
# the median is 267.1 s and 99% lie in 266.5-269.8 s. After the stray-cue repair, 256 runs
# span more, from evenly stretched blocks or pauses not in the design, so every onset after
# the first is misplaced. Above 290 s (about 214 runs) the core rejects the events as past the
# run's end; between 276 and 290 s (42) nothing would notice. 276 s is about 9 s past the
# median (operator, 2026-11-07). The repair runs first: a stray cue alone spans ~310 s.
NBACK_MAX_EVENT_SPAN_S = 276.0
# CLI exit codes (README). 5 is data-determined and does not fail the session; 1/2/4 do.
EXIT_OK, EXIT_HIGH_WARNINGS, EXIT_TOOL, EXIT_MODEL = 0, 3, 4, 5
# Tool failures that the data decide, not faults: the trial-by-trial design has more columns
# than censoring left frames, caught by 3dDeconvolve when it builds the matrix or by 3dLSS
# when it fits it. The core reports either as exit 4; each is recorded as that analysis
# failed, like exit 5, so the session's other analyses still publish.
DATA_LIMITED_TOOL_ERRORS = {
    "Matrix has too many columns": "too-few-frames-for-model",  # 3dLSS
    # 3dDeconvolve: "Insufficient data (153) for estimating 174 parameters"
    "Insufficient data": "too-few-frames-for-model",
}


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


# ---------------------------------------------------------------------------
# Pure staging steps
# ---------------------------------------------------------------------------


def nss_count(confounds: pd.DataFrame) -> int:
    """Frames to trim: the number of non_steady_state_outlier_* columns."""
    return sum(1 for c in confounds.columns if c.startswith("non_steady_state_outlier"))


FD_HEAD_RADIUS_MM = 50.0
FD_CONSISTENCY_ATOL_MM = 1e-6


def motion_units_check(confounds: pd.DataFrame) -> str:
    """ABCD_fmri_orchestrator_S3's _check_producer_fd_consistency (5855f3f): Power FD recomputed
    from the six motion columns, rotations taken as degrees on a 50 mm head, must match the
    file's framewise_displacement within 1e-6 mm. Rotations in radians miss by far more.

    Returns "producer_fd_consistent", or "not_checkable" when the FD column is absent or no
    frame is finite in both. A mismatch excludes the run as `producer_fd_inconsistent`.
    """
    if "framewise_displacement" not in confounds.columns:
        return "not_checkable"
    produced = pd.to_numeric(confounds["framewise_displacement"], errors="coerce").to_numpy(dtype=float)
    deltas = np.abs(np.diff(confounds[MOTION_BASE].to_numpy(dtype=float), axis=0))
    deltas[:, 3:] *= np.pi / 180.0 * FD_HEAD_RADIUS_MM
    recomputed = np.concatenate([[np.nan], deltas.sum(axis=1)])
    comparable = np.isfinite(produced) & np.isfinite(recomputed)
    if not comparable.any():
        return "not_checkable"
    if not np.allclose(recomputed[comparable], produced[comparable], atol=FD_CONSISTENCY_ATOL_MM, rtol=0):
        raise RunExcluded("producer_fd_inconsistent")
    return "producer_fd_consistent"


def motion_matrix(confounds: pd.DataFrame, n_remove: int) -> np.ndarray:
    """(T - n_remove, 12): base motion translations first, then first derivatives.

    ABCD's rotations are already degrees, unlike standard fMRIPrep's radians: its
    framewise_displacement equals sum|d trans| + (pi/180)*50*sum|d rot| on these columns,
    which motion_units_check confirms for each run first, as the orchestrator does.

    Derivatives are taken on the untrimmed series (row 1 = 0) and trimmed with it,
    as the retired orchestrator did. A non-finite value left after trimming excludes
    the run, as ABCD_fmri_orchestrator_S3 does.
    """
    missing = [c for c in MOTION_BASE if c not in confounds.columns]
    if missing:
        raise SessionError(f"confounds lack motion columns {missing}")
    motion_units_check(confounds)
    base = confounds[MOTION_BASE].to_numpy(dtype=float)
    deriv = np.vstack([np.zeros((1, 6)), np.diff(base, axis=0)])
    out = np.hstack([base, deriv])[n_remove:]
    if not np.isfinite(out).all():
        raise RunExcluded("motion_non_finite")
    return out


_NBACK = re.compile(r"^(\d+)_back_(.+)$")


def fix_nback_cue_labels(events: pd.DataFrame, column: str = "trial_type") -> pd.DataFrame:
    """Relabel `cue` rows from the block that follows: 0-back -> `target_0back`, pooled
    across stimuli, any other level -> `instruction`. As ABCD_fmri_orchestrator_S3's
    fix_nback_cue_labels (v4.0.0)."""
    out = events.copy()
    labels = [str(v).strip().strip('"') for v in out[column]]
    for i, label in enumerate(labels):
        if label.lower() != "cue":
            continue
        match = next((m for m in map(_NBACK.match, labels[i + 1 :]) if m), None)
        if match is None:
            raise SessionError(f"cue at row {i} has no following n-back trial")
        labels[i] = "target_0back" if match.group(1) == "0" else "instruction"
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


def check_event_span(events: pd.DataFrame) -> None:
    """Exclude a run whose task events, first to last onset, span more than the task's
    schedule allows (NBACK_MAX_EVENT_SPAN_S): its onsets are misplaced, whether or not
    they still fall inside the scan."""
    onsets = events.loc[_labels(events) != "dummy", "onset"].astype(float)
    if len(onsets) > 1 and onsets.max() - onsets.min() > NBACK_MAX_EVENT_SPAN_S:
        raise RunExcluded("unexpected-event-timing")


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
        if "run_labels" in paths:  # a block-level key
            block["run_labels"] = paths.pop("run_labels")
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


def classify_exit(code: int, error_message: str | None = None) -> dict:
    """One analysis's CLI exit -> its result entry; raises for session failures. A tool
    failure (exit 4) whose error is in DATA_LIMITED_TOOL_ERRORS counts as that analysis
    failed, with the reason, as a model failure does."""
    if code in (EXIT_OK, EXIT_HIGH_WARNINGS):
        return {"status": "completed", "exit_code": code, "high_warnings": code == 3}
    if code == EXIT_MODEL:
        return {"status": "failed", "exit_code": code, "high_warnings": False}
    if code == EXIT_TOOL:
        reason = next((r for text, r in DATA_LIMITED_TOOL_ERRORS.items() if text in (error_message or "")), None)
        if reason:
            return {"status": "failed", "exit_code": code, "high_warnings": False, "reason": reason}
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
    motion = motion_matrix(confounds, run.n_remove)
    run.extra["motion_units_check"] = motion_units_check(confounds)  # it passed, or the run is out
    # Uncompressed: every analysis reads it several times, and gzip would cost a full
    # decompression each time. It stays in the work dir and is never published.
    run.bold = work / f"{run.rid}_bold.nii"
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
    np.savetxt(run.motion, motion, fmt="%.10g", delimiter="\t")
    if run.raw_events is not None:
        run.events, run.dropped_events = stage_events(run.raw_events, run.onset_shift)


def intersect_masks(paths: list[Path], dest: Path) -> Path:
    imgs = [nib.load(str(p)) for p in paths]
    data = np.logical_and.reduce([np.asarray(i.dataobj) > 0 for i in imgs])
    nib.save(nib.Nifti1Image(data.astype(np.uint8), imgs[0].affine), str(dest))
    return dest


def tissue_regressor(confounds: pd.DataFrame, column: str, n_remove: int, dest: Path) -> Path:
    """The run's WM or CSF regressor: its confounds column less the first n_remove rows,
    one value per line. The column is the orchestrator's compute_tissue_mask_regressor
    (the 1 mm label, nearest neighbour to the BOLD grid, within the run's brain mask, the
    BOLD's mean there), computed by cloudpipe's func preproc on every frame, so trimming it
    equals computing it on the trimmed BOLD. n/a means the mask was empty: the run is
    excluded."""
    values = confounds[column].to_numpy(dtype=float)[n_remove:]
    if not len(values) or not np.isfinite(values).all():
        raise RunExcluded("tissue_mask_empty")
    dest.write_text("".join(f"{float(v)!r}\n" for v in values))  # numpy 2's repr names the type
    return dest


@dataclass
class Session:
    subj: str
    ses: str
    input_dir: Path
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
                check_event_span(run.raw_events)  # after the cue repair, which can shorten it
                motion_matrix(confounds, run.n_remove)  # here, so the run leaves the mask too
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
        # n-back runs enter one model, so each is masked by the used runs' intersection;
        # each rest run is denoised alone and keeps its own mask.
        mask = None
        used = [r for r in runs if not r.excluded]
        if task == "nback" and used:
            mask = intersect_masks(
                [raws[r.rid]["brainmask"] for r in used], self.work / "nback_mask.nii.gz"
            )
        for run in used:
            try:
                stage_run(run, raws[run.rid], tr, mask or raws[run.rid]["brainmask"], self.work)
            except RunExcluded as exc:
                run.excluded = str(exc)
                log("run-excluded", run=run.rid, reason=run.excluded)
            except (SessionError, subprocess.CalledProcessError, ValueError, KeyError) as exc:
                # A cue with no following trial lands here: a shape repair_stray_cue left.
                run.excluded, run.failed = f"{type(exc).__name__}: {exc}", True
                log("run-excluded", run=run.rid, reason=run.excluded)
        return runs, raws

    def nback_paths(self, runs: list[Run]) -> dict | None:
        ok = [r for r in runs if not r.excluded]
        if not ok:
            return None
        timings = []
        for run in ok:
            timing = self.work / f"{run.rid}_events.tsv"
            run.events.to_csv(timing, sep="\t", index=False)
            timings.append(str(timing))
        return {
            "scan_paths": [str(r.bold) for r in ok],
            "task_timing_paths": timings,
            "motion_paths": [str(r.motion) for r in ok],
            "run_labels": [run_label(r.rid) for r in ok],
            "CSF_paths": None,
            "WM_paths": None,
        }

    def rest_paths(self, runs: list[Run], raws: dict) -> tuple[dict | None, str | None]:
        if not any(not r.excluded for r in runs):
            return None, "no-rest-runs"
        # WM and CSF come from the confounds TSV's own `white_matter` and `csf` columns,
        # which cloudpipe's func preproc writes with the orchestrator's definition (D17):
        # FastSurfer's label masks, nearest neighbour to the BOLD grid, within the run's
        # brain mask. A session whose TSVs predate the columns has no regressor, so rest
        # is skipped and n-back still runs. A column that is n/a means its mask was
        # empty, and only that run is excluded.
        tables = {
            r.rid: pd.read_csv(raws[r.rid]["confounds"], sep="\t", na_values=["n/a"])
            for r in runs
            if not r.excluded
        }
        if not all(set(TISSUE_COLUMNS.values()) <= set(t.columns) for t in tables.values()):
            return None, "no-tissue-confounds"
        regressors: dict[str, dict[str, str]] = {}
        for run in runs:
            if run.excluded:
                continue
            try:
                regressors[run.rid] = {
                    tissue: str(tissue_regressor(tables[run.rid], column, run.n_remove,
                                                 self.work / f"{run.rid}_{tissue.lower()}.1D"))
                    for tissue, column in TISSUE_COLUMNS.items()
                }  # fmt: skip
            except RunExcluded as exc:
                run.excluded = str(exc)
                log("run-excluded", run=run.rid, reason=run.excluded)
        ok = [r for r in runs if not r.excluded]
        if not ok:
            return None, "no-rest-runs"
        return {
            "scan_paths": [str(r.bold) for r in ok],
            "motion_paths": [str(r.motion) for r in ok],
            "CSF_paths": [regressors[r.rid]["CSF"] for r in ok],
            "WM_paths": [regressors[r.rid]["WM"] for r in ok],
            "run_labels": [run_label(r.rid) for r in ok],
        }, None


def _result(sess: Session, analyses: dict, runs: list[Run]) -> dict:
    return {
        "package_version": package_version(),
        "analyses": analyses,
        "runs": {
            r.rid: (
                {"excluded": r.excluded, **r.extra}
                if r.excluded
                else {
                    "n_remove": r.n_remove,
                    "n_frames": r.n_frames,
                    "dropped_events": r.dropped_events,
                    **r.extra,  # n-back: any cue move
                }
            )
            for r in runs
        },
    }


# rest_conn exits 5 only when no run is left (the core's ModelErrors in nuisance.py). Its
# failure QC keeps the error but not the per-run records, so the reason comes from the
# message; anything unrecognised is `analysis_failed`.
REST_FAILURE_REASONS = (
    ("Every run has DOF < 1", "dof_below_1"),
    ("No run has enough uncensored TRs", "insufficient_uncensored_trs"),
)


def analysis_qc(block: dict) -> dict:
    path = Path(block["out_dir"]) / f"{block['out_file_pre']}_qc_summary.json"
    return json.loads(path.read_text()) if path.is_file() else {}


def analysis_error(qc: dict) -> dict:
    """A failed analysis's error, from its failure QC: type, message and step."""
    error = qc.get("run_status", {}).get("error", {})
    return {k: error.get(k) for k in ("type", "message", "step")}


def note_runs_excluded_by_analysis(block: dict, runs: list[Run], status: str) -> None:
    """Record on each staged rest run whether rest_conn left it out, and why. The core
    reports runs by label, the `run_labels` rest_paths passed."""
    staged = {run_label(r.rid): r for r in runs if not r.excluded}
    qc = analysis_qc(block)
    if status == "completed":
        for record in qc.get("excluded_runs", []):
            staged[record["run"]].extra["excluded_by_analysis"] = record["reason"]
        return
    message = analysis_error(qc)["message"] or ""
    reason = next((r for prefix, r in REST_FAILURE_REASONS if message.startswith(prefix)), "analysis_failed")
    for run in staged.values():
        run.extra["excluded_by_analysis"] = reason


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
    nback = sess.nback_paths(nback_runs)
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
    # nback_conn takes nback_act's template, prep, min-outlier EPI, raw ptseries and
    # ROI QC instead of computing them again: the same code on the same staged runs.
    os.environ[SHARE_DIR_ENV] = str(sess.work / "shared_stages")
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
        error = analysis_error(analysis_qc(block)) if code not in (EXIT_OK, EXIT_HIGH_WARNINGS) else None
        analyses[name] = classify_exit(code, error and error["message"])
        if analyses[name]["status"] == "failed":
            analyses[name]["error"] = error
        log("analysis-end", analysis=name, **analyses[name])
        if name == "rest_conn":
            note_runs_excluded_by_analysis(block, rest_runs, analyses[name]["status"])

    # Only after every analysis: nback_conn takes nback_act's prep, these included.
    for block in cfg["analyses"]:
        removed = remove_concatenations(block)
        if removed:
            analyses[block["name"]]["removed"] = removed

    return _result(sess, analyses, all_runs)


def remove_concatenations(block: dict) -> list[str]:
    """Delete an analysis's concatenated series from its out_dir; the names removed.

    `{pre}_psc` is the published `{pre}_run{N}_psc` files end to end, and
    `{pre}_concat_scan` the staged runs end to end, which staging rebuilds exactly from
    the func derivatives; the PSC runs and their `_mean` volumes also give back the raw
    runs (raw = psc * mean / 100) wherever PSC was neither capped at 200 nor zeroed.
    The analysis's ledger still records them, as outputs of the run that made them."""
    out_dir, pre = Path(block["out_dir"]), block["out_file_pre"]
    removed = []
    for rel in (psc_concat(pre), concat_scan(pre)):
        if (out_dir / rel).is_file():
            (out_dir / rel).unlink()
            removed.append(rel)
    return removed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--subj", required=True, help="sub-... as it appears in the file names")
    ap.add_argument("--ses", required=True, help="ses-... as it appears in the file names")
    ap.add_argument("--input-dir", type=Path, required=True, help="the session's files")
    ap.add_argument("--workdir", type=Path, required=True, help="staged inputs go here")
    ap.add_argument("--out-dir", type=Path, required=True, help="analysis outputs go here")
    ap.add_argument(
        "--atlas",
        default=str(PACKAGED_ATLAS),
        help="the parcellation, the config's template_path (default: the packaged Schaefer 400 + Tian S4)",
    )
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
    sess = Session(args.subj, args.ses, args.input_dir, args.workdir, validity)
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
