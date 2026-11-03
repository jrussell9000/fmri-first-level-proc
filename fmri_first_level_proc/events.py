"""Events reading, run-aware event table, onset validation and AFNI onset-file generation.

Supports two event-file schemes:

- **BIDS**: columns onset, duration, trial_type (tab- or comma-delimited)
- **CONDITION**: columns CONDITION, ONSET, DURATION (tab- or comma-delimited)

Both delimiters are tried; exactly one must produce a recognized header
(both or neither raises InputError listing the columns found under each).
Onset and duration must be finite numbers: BIDS 'n/a', empty cells and inf
raise InputError; nothing is imputed. Negative durations raise InputError.
trial_type values are compared as strings in both input modes, and
duplicate trials (same run, condition and onset) raise InputError.
"""

import dataclasses
import math

import numpy as np
import pandas as pd

from .exceptions import InputError


# ---------------------------------------------------------------------------
# Event file reading
# ---------------------------------------------------------------------------

def read_events_file(path, required_conditions):
    """Read an events file and normalize to BIDS column names.

    Parameters
    ----------
    path : str
        Path to the events file.
    required_conditions : list of str
        Conditions that must appear in the trial_type column.

    Returns
    -------
    pd.DataFrame
        Columns: onset (float), duration (float), trial_type (str).
        Rows in file order.

    Raises
    ------
    InputError
        If the file cannot be parsed, the header does not match either
        scheme, or required conditions are absent.
    """
    bids_cols = {"onset", "duration", "trial_type"}
    cond_cols = {"condition", "onset", "duration"}

    recognized = {}
    found = {}
    for sep in ("\t", ","):
        try:
            hdr = pd.read_csv(path, sep=sep, nrows=0)
        except Exception:
            found[sep] = "unparseable"
            continue
        stripped = [c.strip() for c in hdr.columns]
        found[sep] = stripped
        cols_lower = {c.lower() for c in stripped}
        # Within one delimiter, BIDS takes precedence when both schemes appear.
        if bids_cols.issubset(cols_lower):
            recognized[sep] = "bids"
        elif cond_cols.issubset(cols_lower):
            recognized[sep] = "condition"

    if len(recognized) != 1:
        which = "neither" if not recognized else "both"
        raise InputError(
            f"Events file '{path}': header recognized under {which} delimiter(s). "
            f"Columns found: tab -> {found.get(chr(9))}; comma -> {found.get(',')}. "
            "Expected BIDS (onset, duration, trial_type) or CONDITION "
            "(CONDITION, ONSET, DURATION), tab- or comma-delimited."
        )
    sep = next(iter(recognized))

    fmt = recognized[sep]
    try:
        df = pd.read_csv(path, sep=sep)
    except Exception as e:
        raise InputError(f"Cannot read events file '{path}': {e}") from e

    df.columns = df.columns.str.strip()

    if fmt == "bids":
        rename_map = {c: c.lower() for c in df.columns if c.lower() in bids_cols}
        df = df.rename(columns=rename_map)
    else:
        col_map = {c: c.lower() for c in df.columns if c.lower() in cond_cols}
        df = df.rename(columns=col_map)
        if "condition" in df.columns:
            df = df.rename(columns={"condition": "trial_type"})

    # Validate onset/duration are numeric
    for col in ("onset", "duration"):
        try:
            df[col] = df[col].astype(float)
        except (ValueError, TypeError) as e:
            raise InputError(
                f"Events file '{path}': column '{col}' contains "
                f"non-numeric values: {e}"
            ) from e

    # Missing or non-finite values. pandas parses the BIDS token 'n/a' and
    # empty cells to NaN without raising, so this check is separate from the
    # numeric conversion above. No value is ever imputed.
    remedies = {
        "onset": "Supply the true onset time.",
        "duration": "Supply the true duration, or 0 for impulse events.",
    }
    for col in ("onset", "duration"):
        bad = ~np.isfinite(df[col].to_numpy())
        if bad.any():
            rows = [int(i) + 1 for i in np.flatnonzero(bad)]
            raise InputError(
                f"Events file '{path}': column '{col}' has missing or non-finite "
                f"values (e.g. BIDS 'n/a', empty cells, inf) in data rows {rows}. "
                "'n/a' is valid BIDS meaning the value is unknown, but this "
                f"package cannot model it. {remedies[col]}"
            )

    negative = df["duration"].to_numpy() < 0
    if negative.any():
        rows = [int(i) + 1 for i in np.flatnonzero(negative)]
        raise InputError(
            f"Events file '{path}': column 'duration' has negative values in data "
            f"rows {rows}. Use 0 for impulse events."
        )

    # Condition names are compared as strings in both input modes
    df["trial_type"] = df["trial_type"].astype(str)

    # Check required conditions
    present = set(df["trial_type"].unique())
    missing = [c for c in required_conditions if c not in present]
    if missing:
        raise InputError(
            f"Events file '{path}': required conditions not found: {missing}"
        )

    return df[["onset", "duration", "trial_type"]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# TR index helper
# ---------------------------------------------------------------------------

def tr_index(t, tr):
    """Return the 0-based TR index for onset time *t*."""
    return math.floor(t / tr + 1e-6)


# ---------------------------------------------------------------------------
# Event table
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class EventTable:
    """Run-aware event table.

    Attributes
    ----------
    df : pd.DataFrame
        Columns: run (int label), condition (str), onset (float, run-local
        seconds), duration (float), events_file (str), seq (int, original
        order within its file).
    """
    df: pd.DataFrame

    def for_runs(self, labels):
        """Return a filtered copy containing only the given run labels."""
        mask = self.df["run"].isin(labels)
        return EventTable(df=self.df[mask].copy())

    def conditions(self):
        """Return the set of conditions present in the table."""
        return set(self.df["condition"].unique())


@dataclasses.dataclass
class TimingCheck:
    """Result of onset timing validation."""
    violations: list
    runs: list


def build_event_table(config, runsets, required_conditions):
    """Build a run-aware event table and validate onset timing.

    Parameters
    ----------
    config : ResolvedConfig
    runsets : RunSets
    required_conditions : list of str
        Conditions required to appear. Mode A: must each appear in at least one
        supplied events file (union of valid events). Mode B: must each appear
        in the single file.

    Returns
    -------
    (EventTable, TimingCheck)
    """
    rows = []
    violations = []
    run_summaries = []

    if runsets.input_mode == "A":
        # Mode A: one file per run
        for lbl in runsets.supplied:
            ri = runsets.run(lbl)
            path = config.task_timing_paths[ri.position]
            df = read_events_file(path, [])
            run_end = ri.n_vols * config.tr

            run_violations = []
            valid_rows = []
            for seq, (_, row) in enumerate(df.iterrows()):
                onset = float(row["onset"])
                dur = float(row["duration"])
                cond = str(row["trial_type"])

                violation = None
                if onset < 0:
                    violation = "negative"
                elif onset >= run_end:
                    violation = "at_or_after_run_end"

                if violation:
                    run_violations.append({
                        "events_file": path,
                        "run": lbl,
                        "run_null_reason": None,
                        "condition": cond,
                        "onset_s": onset,
                        "violation": violation,
                    })
                else:
                    valid_rows.append({
                        "run": lbl,
                        "condition": cond,
                        "onset": onset,
                        "duration": dur,
                        "events_file": path,
                        "seq": seq,
                    })

            violations.extend(run_violations)
            rows.extend(valid_rows)

            # Run summary
            n_neg = sum(1 for v in run_violations if v["violation"] == "negative")
            n_after = sum(1 for v in run_violations if v["violation"] == "at_or_after_run_end")
            valid_onsets = [r["onset"] for r in valid_rows]
            run_summaries.append({
                "run": lbl,
                "events_file": path,
                "n_vols": ri.n_vols,
                "run_end_s": run_end,
                "n_onsets": len(valid_rows),
                "min_onset_s": min(valid_onsets) if valid_onsets else None,
                "max_onset_s": max(valid_onsets) if valid_onsets else None,
                "n_negative": n_neg,
                "n_at_or_after_run_end": n_after,
            })

        if len(violations) == 0:
            paths = [config.task_timing_paths[runsets.run(lbl).position]
                     for lbl in runsets.supplied]
            present = set(r["condition"] for r in rows)
            missing = [c for c in required_conditions if c not in present]
            if missing:
                raise InputError(
                    f"Required condition(s) {missing} not found in any supplied events file "
                    f"(checked the union of valid events across: {paths})",
                    context={"missing_conditions": missing, "events_files": paths}
                )
    else:
        # Mode B: single file
        path = config.task_timing_path
        df = read_events_file(path, required_conditions)
        total = runsets.total_vols(runsets.supplied) * config.tr

        per_run_valid = {lbl: [] for lbl in runsets.supplied}

        for seq, (_, row) in enumerate(df.iterrows()):
            onset = float(row["onset"])
            dur = float(row["duration"])
            cond = str(row["trial_type"])

            if onset < 0:
                violations.append({
                    "events_file": path,
                    "run": None,
                    "run_null_reason": "outside_concatenated_series",
                    "condition": cond,
                    "onset_s": onset,
                    "violation": "negative",
                })
                continue
            if onset >= total:
                violations.append({
                    "events_file": path,
                    "run": None,
                    "run_null_reason": "outside_concatenated_series",
                    "condition": cond,
                    "onset_s": onset,
                    "violation": "at_or_after_run_end",
                })
                continue

            # Assign to a run
            vol_idx = tr_index(onset, config.tr)
            assigned_label = None
            for lbl in runsets.supplied:
                ri = runsets.run(lbl)
                if ri.start <= vol_idx < ri.start + ri.n_vols:
                    assigned_label = lbl
                    break

            if assigned_label is None:
                # Should not happen if total check passed, but guard
                violations.append({
                    "events_file": path,
                    "run": None,
                    "run_null_reason": "outside_concatenated_series",
                    "condition": cond,
                    "onset_s": onset,
                    "violation": "at_or_after_run_end",
                })
                continue

            ri = runsets.run(assigned_label)
            local_onset = onset - ri.start * config.tr
            per_run_valid[assigned_label].append({
                "run": assigned_label,
                "condition": cond,
                "onset": local_onset,
                "duration": dur,
                "events_file": path,
                "seq": seq,
            })

        for lbl in runsets.supplied:
            rows.extend(per_run_valid[lbl])

        # Run summaries
        for lbl in runsets.supplied:
            ri = runsets.run(lbl)
            valid_onsets = [r["onset"] for r in per_run_valid[lbl]]
            run_summaries.append({
                "run": lbl,
                "events_file": path,
                "n_vols": ri.n_vols,
                "run_end_s": ri.n_vols * config.tr,
                "n_onsets": len(per_run_valid[lbl]),
                "min_onset_s": min(valid_onsets) if valid_onsets else None,
                "max_onset_s": max(valid_onsets) if valid_onsets else None,
                "n_negative": 0,
                "n_at_or_after_run_end": 0,
            })

    event_df = pd.DataFrame(rows, columns=["run", "condition", "onset", "duration",
                                            "events_file", "seq"])
    _check_duplicate_trials(event_df)
    return (
        EventTable(df=event_df),
        TimingCheck(violations=violations, runs=run_summaries),
    )


def _check_duplicate_trials(event_df):
    """Raise InputError when two events share run, condition and onset."""
    dup_mask = event_df.duplicated(subset=["run", "condition", "onset"], keep=False)
    if not dup_mask.any():
        return
    dups = (
        event_df[dup_mask]
        .drop_duplicates(subset=["run", "condition", "onset"])
        .head(10)
    )
    records = [
        {"events_file": r.events_file, "run": int(r.run),
         "condition": r.condition, "onset": float(r.onset)}
        for r in dups.itertuples(index=False)
    ]
    shown = "; ".join(
        f"{d['events_file']} run {d['run']} {d['condition']} @ {d['onset']} s" for d in records
    )
    raise InputError(
        f"Duplicate trials (same run, condition and onset) in the events data: {shown}. "
        "Each trial must appear once.",
        context={"duplicates": records},
    )


# ---------------------------------------------------------------------------
# Timing error records
# ---------------------------------------------------------------------------

def timing_record(analysis_type, input_mode, tr, check):
    """Build the timing_errors.json record."""
    return {
        "analysis_type": analysis_type,
        "input_mode": input_mode,
        "tr": tr,
        "violations": check.violations,
        "runs": check.runs,
    }


def timing_error_message(record, record_relpath):
    """Build the InputError message for timing violations."""
    n_files = len({v["events_file"] for v in record["violations"]})
    affected_runs = sorted({v["run"] for v in record["violations"] if v["run"] is not None})
    n_neg = sum(1 for v in record["violations"] if v["violation"] == "negative")
    n_after = sum(1 for v in record["violations"] if v["violation"] == "at_or_after_run_end")
    parts = [
        f"{len(record['violations'])} onset timing violation(s) in "
        f"{n_files} events file(s)",
    ]
    if affected_runs:
        parts.append(f"affected runs: {affected_runs}")
    if n_neg:
        parts.append(f"{n_neg} negative onset(s)")
    if n_after:
        parts.append(f"{n_after} onset(s) at or after run end")
    parts.append(f"details written to {record_relpath}")
    parts.append(
        "Onsets inside the run window in the same file may also be wrong; "
        "check the timing reference, file pairing, units and run order "
        "before rerunning."
    )
    return ". ".join(parts)


# ---------------------------------------------------------------------------
# AFNI onset file generation
# ---------------------------------------------------------------------------

def onset_rows_labeled(event_table, conditions, model_runs):
    """Build condition-labelled onset rows for AFNI onset files.

    This is the single source of onset-file row order. The order is: per
    model run in the given order; within a run, per condition in the given
    order; within a condition, trials sorted by onset (stable sort). With
    ``-stim_times_IM``, 3dDeconvolve creates one design-matrix column per
    onset in this file order (verified on AFNI 26.0.09 and guarded at
    runtime by ``estimability.check_im_order``).

    Parameters
    ----------
    event_table : EventTable
    conditions : list of str
        Conditions to include, in the desired order.
    model_runs : list of int
        Run labels in acquisition order.

    Returns
    -------
    list of list of (str, float, float)
        One list per model run; each element is (condition, onset, duration).
    """
    result = []
    for lbl in model_runs:
        run_events = []
        for cond in conditions:
            mask = (event_table.df["run"] == lbl) & (event_table.df["condition"] == cond)
            cond_df = event_table.df[mask].sort_values("onset", kind="mergesort")
            for _, row in cond_df.iterrows():
                run_events.append((cond, float(row["onset"]), float(row["duration"])))
        result.append(run_events)
    return result


def onset_rows(event_table, conditions, model_runs):
    """Build onset rows for AFNI onset files.

    Same ordering as ``onset_rows_labeled`` (it is a projection of it), so
    an onset file written from these rows and a trial-to-column map built
    from the labelled rows always agree.

    Parameters
    ----------
    event_table : EventTable
    conditions : list of str
        Conditions to include, in the desired order.
    model_runs : list of int
        Run labels in acquisition order.

    Returns
    -------
    list of list of (float, float)
        One list per model run; each element is (onset, duration) for the
        given conditions in order, with each condition's trials ordered by onset.
    """
    return [
        [(onset, duration) for (_, onset, duration) in run_events]
        for run_events in onset_rows_labeled(event_table, conditions, model_runs)
    ]


def onset_file_text(rows, married):
    """Generate AFNI-compatible onset file text.

    Parameters
    ----------
    rows : list of list of (float, float)
        Output of ``onset_rows`` or equivalent.
    married : bool
        If True, format as ``onset*duration``.

    Returns
    -------
    str
        One line per run, trailing newline.
    """
    lines = []
    for run_events in rows:
        if not run_events:
            lines.append("*")
        else:
            tokens = []
            for onset, duration in run_events:
                if married:
                    tokens.append(f"{repr(float(onset))}*{repr(float(duration))}")
                else:
                    tokens.append(repr(float(onset)))
            lines.append(" ".join(tokens))
    return "\n".join(lines) + "\n"
