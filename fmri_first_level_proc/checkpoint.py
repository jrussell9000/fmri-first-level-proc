"""Append-only JSONL ledger for stage-level processing state.

Three record types:

- **staged**: written after outputs are validated and before they are promoted
  (os.replace) from the staging directory into out_dir.  Staged records track
  what a step intends to place in out_dir; they are cleanup tracking only and
  never evidence of content integrity.

- **completion**: written after promotion succeeds for a ledgered stage.
  Completion entries are the sole reuse gate: a stage is reused only when a
  valid completion entry exists with a matching stage hash and all listed
  output paths still exist on disk.

- **retired**: written after outputs from prior invocations are deleted by the
  retirement sweep at the end of a run.

All records are serialized as one JSON object per line (keys sorted,
separators ``(",", ":")``), always containing ``"record_type"`` and
``"ledger_format": 2``.
"""

import dataclasses
import datetime
import hashlib
import json
import os


LEDGER_FORMAT = 2


# ---------------------------------------------------------------------------
# Record dataclasses
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class OutputRecord:
    """One output path (relative to out_dir) and its class."""
    path: str
    cls: str  # "final" | "intermediate"


@dataclasses.dataclass
class StagedRecord:
    """Outputs a stage is about to promote, written before promotion."""
    step: str
    outputs: list  # list of OutputRecord
    timestamp_utc: str


@dataclasses.dataclass
class CompletionRecord:
    """Successful stage completion: hash, outputs, QC fragment, warnings, versions."""
    step: str
    stage_hash: str
    outputs: list  # list of OutputRecord
    qc: dict
    warnings: list  # list of {code, severity, message, user_facing}
    versions: dict
    timestamp_utc: str
    wall_clock_s: float


@dataclasses.dataclass
class RetiredRecord:
    """Paths deleted by the retirement sweep."""
    paths: list  # list of relpath strings
    timestamp_utc: str


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def utc_now():
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _serialize_output(out):
    return {"path": out.path, "class": out.cls}


def _serialize_record(record):
    if isinstance(record, StagedRecord):
        return json.dumps(
            {
                "ledger_format": LEDGER_FORMAT,
                "outputs": [_serialize_output(o) for o in record.outputs],
                "record_type": "staged",
                "step": record.step,
                "timestamp_utc": record.timestamp_utc,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    if isinstance(record, CompletionRecord):
        return json.dumps(
            {
                "ledger_format": LEDGER_FORMAT,
                "outputs": [_serialize_output(o) for o in record.outputs],
                "qc": record.qc,
                "record_type": "completion",
                "stage_hash": record.stage_hash,
                "step": record.step,
                "timestamp_utc": record.timestamp_utc,
                "versions": record.versions,
                "wall_clock_s": record.wall_clock_s,
                "warnings": record.warnings,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    if isinstance(record, RetiredRecord):
        return json.dumps(
            {
                "ledger_format": LEDGER_FORMAT,
                "paths": record.paths,
                "record_type": "retired",
                "timestamp_utc": record.timestamp_utc,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    raise TypeError(f"Unknown record type: {type(record)}")


def append_record(ledger_path, record):
    """Append a single record to the ledger file (fsync)."""
    line = _serialize_record(record) + "\n"
    fd = os.open(ledger_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT)
    try:
        os.write(fd, line.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class LedgerHistory:
    """Parsed ledger records plus the line numbers that could not be parsed."""
    records: list  # parsed record dataclasses in file order
    unreadable_lines: list  # 1-based line numbers


_REQUIRED_KEYS = {
    "staged": {"step": str, "outputs": list, "timestamp_utc": str},
    "completion": {
        "step": str,
        "stage_hash": str,
        "outputs": list,
        "qc": dict,
        "warnings": list,
        "versions": dict,
        "timestamp_utc": str,
        "wall_clock_s": (int, float),
    },
    "retired": {"paths": list, "timestamp_utc": str},
}


def _parse_output(obj):
    return OutputRecord(path=obj["path"], cls=obj["class"])


def _try_parse_line(obj):
    """Return a record dataclass or None if the line is unreadable."""
    if not isinstance(obj, dict):
        return None
    if obj.get("ledger_format") != LEDGER_FORMAT:
        return None
    rtype = obj.get("record_type")
    if rtype not in _REQUIRED_KEYS:
        return None
    for key, expected_type in _REQUIRED_KEYS[rtype].items():
        val = obj.get(key)
        if val is None and key not in obj:
            return None
        if not isinstance(val, expected_type):
            return None
    if rtype == "staged":
        return StagedRecord(
            step=obj["step"],
            outputs=[_parse_output(o) for o in obj["outputs"]],
            timestamp_utc=obj["timestamp_utc"],
        )
    if rtype == "completion":
        return CompletionRecord(
            step=obj["step"],
            stage_hash=obj["stage_hash"],
            outputs=[_parse_output(o) for o in obj["outputs"]],
            qc=obj["qc"],
            warnings=obj["warnings"],
            versions=obj["versions"],
            timestamp_utc=obj["timestamp_utc"],
            wall_clock_s=obj["wall_clock_s"],
        )
    if rtype == "retired":
        return RetiredRecord(
            paths=obj["paths"],
            timestamp_utc=obj["timestamp_utc"],
        )
    return None


def read_history(ledger_path):
    """Read a ledger file and return a LedgerHistory.

    Missing file returns an empty history.  Lines that cannot be parsed
    are recorded in ``unreadable_lines`` (1-based) but never raise.
    """
    records = []
    unreadable = []
    if not os.path.exists(ledger_path):
        return LedgerHistory(records=records, unreadable_lines=unreadable)
    with open(ledger_path, "r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                unreadable.append(lineno)
                continue
            parsed = _try_parse_line(obj)
            if parsed is None:
                unreadable.append(lineno)
            else:
                records.append(parsed)
    return LedgerHistory(records=records, unreadable_lines=unreadable)


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def latest_completion(history, step):
    """Return the last CompletionRecord for *step*, or None."""
    result = None
    for rec in history.records:
        if isinstance(rec, CompletionRecord) and rec.step == step:
            result = rec
    return result


def recorded_paths(history):
    """Return every output path mentioned in staged and completion records."""
    paths = set()
    for rec in history.records:
        if isinstance(rec, (StagedRecord, CompletionRecord)):
            for out in rec.outputs:
                paths.add(out.path)
    return paths


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def sha256_file(path):
    """Return the hex SHA-256 digest of *path* (streamed in 1 MiB chunks)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _jsonable(obj):
    """Convert Python objects to JSON-compatible types for canonical hashing."""
    if isinstance(obj, set):
        return sorted(obj)
    if isinstance(obj, tuple):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonable(v) for v in obj]
    return obj


def canonical_json(obj):
    """Return a deterministic JSON string for hashing.

    Sets are sorted; tuples become lists.  Anything else that is not
    JSON-serializable raises TypeError.
    """
    return json.dumps(
        _jsonable(obj), sort_keys=True, separators=(",", ":")
    )


def compute_stage_hash(payload):
    """Return the SHA-256 hex digest of the canonical JSON of *payload*."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
