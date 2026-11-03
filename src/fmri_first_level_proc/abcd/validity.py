"""Build the per-run table saying which n-back runs have valid E-Prime timing.

ABCD excludes runs with irregular trigger timing from its own analyses (5.2% of GE runs,
none elsewhere) but still ships their events. `eprime__run__valid_count` finds them, per
session. ABCD generates no results for an invalid run, so where one of two runs is valid,
the run-level results name it.

The table is keyed by subject ID and built from data under the ABCD data use agreement, so
it is never committed here. Output reports counts and never names a session.
"""

from __future__ import annotations

import argparse
import collections
import csv
import re
import sys
from pathlib import Path

VALID_COUNT = "mr_y_qc__raw__tfmri__nback__eprime__run__valid_count"
HEADER = ["subject_id", "session", "run", "use", "reason"]
_RUN = re.compile(r"^task-nback_run-(\d+)$")


def valid_counts(path: Path) -> dict[tuple[str, str], int]:
    out = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            value = (row.get(VALID_COUNT) or "").strip()
            if value and value.lower() != "n/a":
                out[(row["participant_id"], row["session_id"])] = int(float(value))
    return out


def sessions_with_results(path: Path) -> set[tuple[str, str]]:
    """Sessions where most of this run-level table's beta columns hold a value."""
    out = set()
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        betas = [c for c in reader.fieldnames or [] if c.endswith("_beta")]
        if not betas:
            raise ValueError(f"{path} has no _beta columns")
        for row in reader:
            filled = sum((row[c] or "").strip().lower() not in ("", "n/a", "nan") for c in betas)
            if filled * 2 > len(betas):
                out.add((row["participant_id"], row["session_id"]))
    return out


def decide(
    session: tuple[str, str],
    run: str,
    counts: dict[tuple[str, str], int],
    results: dict[str, set[tuple[str, str]]],
) -> tuple[bool, str]:
    """(use, reason) for one run. Run-level results decide only a session with one valid run,
    because they can also be missing for QC reasons."""
    count = counts.get(session)
    if count is None:
        return False, "no-valid-count"
    if count == 0:
        return False, "no-valid-timing-runs"
    if count >= 2:
        return True, ""
    with_results = {r for r, sessions in results.items() if session in sessions}
    if len(with_results) != 1:
        return False, "valid-run-unidentified"
    return (True, "") if run in with_results else (False, "other-run-has-valid-timing")


def build(
    runs_csv: Path, mr_qc: Path, results_r01: Path, results_r02: Path, hold: Path | None
) -> list[list[str]]:
    counts = valid_counts(mr_qc)
    results = {"01": sessions_with_results(results_r01), "02": sessions_with_results(results_r02)}
    holds = {}
    if hold:
        with hold.open(newline="", encoding="utf-8") as handle:
            holds = {(r["subject_id"], r["session"]): r["reason"] for r in csv.DictReader(handle)}
    rows = []
    with runs_csv.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            session = (row["subject_id"], row["session"])
            match = _RUN.match(row["run"])
            if match is None:
                raise ValueError(f"run must look like task-nback_run-01, got {row['run']!r}")
            use, reason = decide(session, match.group(1).zfill(2), counts, results)
            if session in holds:
                use, reason = False, holds[session]
            rows.append([*session, row["run"], "1" if use else "0", reason])
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--mr-qc-nback", type=Path, required=True, help="mr_y_qc__raw__tfmri__nback.tsv")
    ap.add_argument("--results-r01", type=Path, required=True, help="mr_y_tfmri__nback__0b__r01__aseg.tsv")
    ap.add_argument("--results-r02", type=Path, required=True, help="mr_y_tfmri__nback__0b__r02__aseg.tsv")
    ap.add_argument("--runs", type=Path, required=True, help="CSV: subject_id,session,run")
    ap.add_argument("--hold", type=Path, help="CSV: subject_id,session,reason; holds these sessions out")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    rows = build(args.runs, args.mr_qc_nback, args.results_r01, args.results_r02, args.hold)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows(rows)
    counts = collections.Counter(row[4] or "used" for row in rows)
    print(f"wrote {len(rows)} runs to {args.out}: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
