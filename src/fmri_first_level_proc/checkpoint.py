#!/usr/bin/env python3

# ============================================================================
# CHECKPOINT / RESUME LEDGER
# Append-only JSONL ledger recording per-stage completion state.
# Supports DAG-aware resume: identifies which stages must re-run based on
# missing entries or config hash invalidation, with downstream cascade.
#
# Author: Taylor J. Keding, Ph.D.
# ============================================================================

import dataclasses
import datetime
import glob
import hashlib
import json
import os


# ---------------------------------------------------------------------------
# Ledger entry
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class LedgerEntry:
    """Single DAG stage completion record written to the JSONL ledger."""

    stage_id: str
    scope_key: str
    status: str               # 'completed' | 'reconstructed'
    timestamp_utc: str        # ISO 8601
    wall_clock_s: float
    config_hash: str | None
    qc_summary: dict
    output_files: list[str]


# ---------------------------------------------------------------------------
# DAG stage lists
# ---------------------------------------------------------------------------

DAG_TASK_ACT: list[str] = [
    "TA.prep",
    "TA.glm",
    "TA.extract",
    "TA.qc",
]

DAG_TASK_CONN: list[str] = [
    "TC.prep",
    "TC.design",
    "TC.beta",
    "TC.conn",
    "TC.qc",
]

DAG_REST_CONN_PER_RUN: list[str] = [
    "RC.prep.{n}",
    "RC.resid.{n}",
]

DAG_REST_CONN_POST: list[str] = [
    "RC.concat",
    "RC.conn",
    "RC.qc",
]


# ---------------------------------------------------------------------------
# Ledger I/O
# ---------------------------------------------------------------------------

def append_ledger_entry(ledger_path: str, entry: LedgerEntry) -> None:
    """Append one LedgerEntry as a JSON line to the ledger file.

    Uses OS-level fsync after each write to guarantee durability. The ledger
    file is created if it does not already exist.

    Parameters
    ----------
    ledger_path:
        Absolute path to the JSONL ledger file.
    entry:
        Populated LedgerEntry to serialize and append.
    """
    line = json.dumps(dataclasses.asdict(entry))
    with open(ledger_path, "a") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def read_ledger(ledger_path: str) -> dict[tuple[str, str], LedgerEntry]:
    """Parse the JSONL ledger and return the latest entry per (stage_id, scope_key).

    Last-writer-wins: if the same (stage_id, scope_key) pair appears multiple
    times, the final occurrence in the file is authoritative. Returns an empty
    dict when the file is absent rather than raising.

    Parameters
    ----------
    ledger_path:
        Absolute path to the JSONL ledger file.

    Returns
    -------
    dict mapping (stage_id, scope_key) to the most-recently-written LedgerEntry.
    """
    if not os.path.isfile(ledger_path):
        return {}

    result: dict[tuple[str, str], LedgerEntry] = {}
    with open(ledger_path) as fh:
        for raw_line in fh:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                record = json.loads(raw_line)
                entry = LedgerEntry(**record)
                result[(entry.stage_id, entry.scope_key)] = entry
            except (json.JSONDecodeError, TypeError):
                # Corrupted line: skip and continue to recover as much as possible.
                continue

    return result


# ---------------------------------------------------------------------------
# DAG resolution
# ---------------------------------------------------------------------------

def resolve_rerun_set(
    ledger: dict[tuple[str, str], LedgerEntry],
    dag: list[str],
    scope_key: str,
    current_config_hash: str,
) -> list[str]:
    """Determine which DAG stages must run for a given scope_key.

    Walk the DAG in topological order. A stage is added to the rerun set when:
    (a) no completed ledger entry exists for (stage_id, scope_key), or
    (b) the recorded config_hash does not match current_config_hash.

    Once any stage is invalidated, all downstream stages in the DAG are also
    invalidated regardless of their individual ledger state (cascade rule).

    Parameters
    ----------
    ledger:
        Mapping returned by read_ledger().
    dag:
        Ordered list of stage_id strings for this analysis type.
    scope_key:
        Identifies the subject/run/session being evaluated.
    current_config_hash:
        SHA-256 hex digest of the current config produced by compute_config_hash().

    Returns
    -------
    Ordered list of stage_ids that must be executed.
    """
    rerun: list[str] = []
    cascade_active = False

    for stage_id in dag:
        if cascade_active:
            rerun.append(stage_id)
            continue

        key = (stage_id, scope_key)
        entry = ledger.get(key)

        if entry is None:
            # Stage has never completed.
            rerun.append(stage_id)
            cascade_active = True
            continue

        if entry.config_hash != current_config_hash:
            # Config changed: this stage and all downstream stages must re-run.
            rerun.append(stage_id)
            cascade_active = True
            continue

    return rerun


# ---------------------------------------------------------------------------
# Reconstruction from artifacts
# ---------------------------------------------------------------------------

# Artifact glob patterns used to infer stage completion from output files.
# Each tuple is (stage_id, glob_pattern_relative_to_output_dir).
_TASK_ACT_ARTIFACT_PATTERNS: list[tuple[str, str]] = [
    ("TA.prep",    "*_censor.1D"),
    ("TA.glm",     "*_stats.HEAD"),
    ("TA.extract", "*_activation*.txt"),
    ("TA.qc",      "*_qc_summary.json"),
]

_TASK_CONN_ARTIFACT_PATTERNS: list[tuple[str, str]] = [
    ("TC.prep",   "*_censor.1D"),
    ("TC.design", "*_onset_*.1D"),
    ("TC.beta",   "*_beta*.HEAD"),
    ("TC.conn",   "*_connectivity*.txt"),
    ("TC.qc",     "*_qc_summary.json"),
]

_REST_CONN_POST_ARTIFACT_PATTERNS: list[tuple[str, str]] = [
    ("RC.concat", "*_concat*.dtseries.nii"),
    ("RC.conn",   "*_connectivity*.txt"),
    ("RC.qc",     "*_qc_summary.json"),
]


def auto_reconstruct_ledger(
    output_dir: str,
    analysis_type: str,
    scope_key: str,
) -> list[LedgerEntry]:
    """Infer ledger entries from existing output artifacts in output_dir.

    Scans for known artifact patterns associated with each DAG stage and
    creates 'reconstructed' LedgerEntry records for stages whose primary
    artifacts are present. Per-run rest_conn stages (RC.prep.{n},
    RC.resid.{n}) are inferred from per-run subdirectory structure.

    Parameters
    ----------
    output_dir:
        Directory that was the target of a prior pipeline run.
    analysis_type:
        One of 'task_act', 'task_conn', or 'rest_conn'.
    scope_key:
        Scope identifier to embed in reconstructed entries.

    Returns
    -------
    List of LedgerEntry objects with status='reconstructed'. Caller is
    responsible for writing these to the ledger via append_ledger_entry().
    """
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    entries: list[LedgerEntry] = []

    def _found_files(pattern: str) -> list[str]:
        return sorted(glob.glob(os.path.join(output_dir, pattern)))

    if analysis_type == "task_act":
        patterns = _TASK_ACT_ARTIFACT_PATTERNS
    elif analysis_type == "task_conn":
        patterns = _TASK_CONN_ARTIFACT_PATTERNS
    elif analysis_type == "rest_conn":
        patterns = _REST_CONN_POST_ARTIFACT_PATTERNS
    else:
        return entries

    # Shared: post-concat and final stages.
    for stage_id, pattern in patterns:
        matched = _found_files(pattern)
        if matched:
            entries.append(LedgerEntry(
                stage_id=stage_id,
                scope_key=scope_key,
                status="reconstructed",
                timestamp_utc=timestamp,
                wall_clock_s=0.0,
                config_hash=None,
                qc_summary={},
                output_files=matched,
            ))

    # Per-run rest_conn stages: detect run subdirectories.
    if analysis_type == "rest_conn":
        run_dirs = sorted(
            d for d in glob.glob(os.path.join(output_dir, "run-*"))
            if os.path.isdir(d)
        )
        for run_dir in run_dirs:
            run_label = os.path.basename(run_dir)
            # RC.prep.{n}: censor file present in run directory.
            prep_files = sorted(glob.glob(os.path.join(run_dir, "*_censor.1D")))
            if prep_files:
                entries.append(LedgerEntry(
                    stage_id=f"RC.prep.{run_label}",
                    scope_key=scope_key,
                    status="reconstructed",
                    timestamp_utc=timestamp,
                    wall_clock_s=0.0,
                    config_hash=None,
                    qc_summary={},
                    output_files=prep_files,
                ))
            # RC.resid.{n}: residual dtseries present in run directory.
            resid_files = sorted(
                glob.glob(os.path.join(run_dir, "*_resid*.dtseries.nii"))
                + glob.glob(os.path.join(run_dir, "*_res*.HEAD"))
            )
            if resid_files:
                entries.append(LedgerEntry(
                    stage_id=f"RC.resid.{run_label}",
                    scope_key=scope_key,
                    status="reconstructed",
                    timestamp_utc=timestamp,
                    wall_clock_s=0.0,
                    config_hash=None,
                    qc_summary={},
                    output_files=resid_files,
                ))

    return entries


# ---------------------------------------------------------------------------
# Config hashing
# ---------------------------------------------------------------------------

def compute_config_hash(config) -> str:
    """Compute a deterministic SHA-256 digest of a config dataclass instance.

    Serializes the config via dataclasses.asdict() with sorted keys, encodes
    as UTF-8, and returns the hex digest. Identical configs always produce the
    same digest; any field change produces a distinct digest.

    Parameters
    ----------
    config:
        Any dataclass instance representing a pipeline configuration.

    Returns
    -------
    64-character lowercase SHA-256 hex digest string.
    """
    canonical = json.dumps(dataclasses.asdict(config), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
