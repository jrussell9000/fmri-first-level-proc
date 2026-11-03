"""QC summary key schema, producer validation and fragment merge rule.

The QC_KEYS table defines every permitted key in the qc_summary JSON,
along with its kind (``'value'`` or ``'records'``), identity fields,
allowed producer label patterns and valid analysis types. The
``merge_fragments`` function enforces these constraints when assembling
the per-step QC fragments into the final qc_summary.
"""

import dataclasses
import fnmatch
import json

from .exceptions import GuardError
from . import names


@dataclasses.dataclass(frozen=True)
class QCKeySpec:
    """Specification of a single qc_summary key.

    Attributes
    ----------
    kind : str
        ``'value'`` (scalar or dict) or ``'records'`` (list of dicts).
    identity : tuple of str
        Field names that form the identity of a record. Empty for values.
    producers : tuple of str
        Label patterns that may produce this key (``{t}`` is replaced by the
        type label, fnmatch wildcards allowed).
    types : frozenset of str
        Analysis types that permit this key.
    """
    kind: str
    identity: tuple
    producers: tuple
    types: frozenset


TASK = frozenset({"task_act", "task_conn"})
ALL = TASK | frozenset({"rest_conn"})

# Insertion order = output order in qc_summary.json
QC_KEYS = {
    "analysis_type": QCKeySpec("value", (), ("{t}-qc",), ALL),
    "run_status": QCKeySpec("value", (), ("{t}-qc",), ALL),
    "hrf_model": QCKeySpec("value", (), ("{t}-qc",), TASK),
    "fd_threshold": QCKeySpec("value", (), ("{t}-qc",), ALL),
    "censor_prev_tr": QCKeySpec("value", (), ("{t}-qc",), ALL),
    "censor_metric": QCKeySpec("value", (), ("{t}-qc",), ALL),
    "fd_radius_mm": QCKeySpec("value", (), ("{t}-qc",), ALL),
    "bandpass": QCKeySpec("value", (), ("{t}-qc",), frozenset({"rest_conn"})),
    "bandpass_backend": QCKeySpec("value", (), ("{t}-qc",), frozenset({"rest_conn"})),
    "contrast_labels": QCKeySpec("value", (), ("{t}-qc",), frozenset({"task_conn"})),
    "n_trs_total": QCKeySpec("value", (), ("{t}-nuisance",), ALL),
    "n_trs_censored": QCKeySpec("value", (), ("{t}-nuisance",), ALL),
    "pct_censored": QCKeySpec("value", (), ("{t}-nuisance",), ALL),
    "fd_summary": QCKeySpec("value", (), ("{t}-nuisance",), ALL),
    "enorm_summary": QCKeySpec("value", (), ("{t}-nuisance",), ALL),
    "per_run_censoring": QCKeySpec("records", ("run",), ("{t}-nuisance",), frozenset({"rest_conn"})),
    "per_run_dof": QCKeySpec("records", ("run",), ("{t}-nuisance",), frozenset({"rest_conn"})),
    "dof": QCKeySpec("value", (), ("task-act-preflight", "task-conn-estimability"), TASK),
    "trials": QCKeySpec("records", ("run", "condition", "onset"), ("{t}-estimability",), TASK),
    "per_condition_trial_counts": QCKeySpec("value", (), ("{t}-estimability",), TASK),
    "per_condition_surviving_trials": QCKeySpec("value", (), ("{t}-estimability",), TASK),
    "per_condition_run_counts": QCKeySpec("records", ("run", "condition"), ("{t}-estimability",), TASK),
    "excluded_runs": QCKeySpec("records", ("run",), ("{t}-qc",), ALL),
    "failed_runs": QCKeySpec("records", ("run",), ("rest-conn-residuals-run*", "rest-conn-residuals-concat"), frozenset({"rest_conn"})),
    "psc_per_run": QCKeySpec("records", ("run",), ("{t}-prep",), ALL),
    "smoothing_per_run": QCKeySpec("records", ("run",), ("task-act-smooth", "task-conn-smooth", "rest-conn-smooth-residuals"), ALL),
    "pcorr_rank_checks": QCKeySpec("records", ("condition",), ("{t}-connectivity",), frozenset({"task_conn", "rest_conn"})),
    "null_rois": QCKeySpec("records", ("condition", "output"), ("{t}-connectivity",), frozenset({"task_conn", "rest_conn"})),
    "null_seed_conditions": QCKeySpec("records", ("condition",), ("task-conn-connectivity",), frozenset({"task_conn"})),
    "zero_variance_target_voxels": QCKeySpec("records", ("output",), ("{t}-connectivity",), frozenset({"task_conn", "rest_conn"})),
    "roi_coverage": QCKeySpec("records", ("run", "roi"), ("{t}-roi-qc",), ALL),
    "low_baseline": QCKeySpec("records", ("run", "roi"), ("{t}-roi-qc",), ALL),
    "reused_stages": QCKeySpec("value", (), ("{t}-qc",), ALL),
    "retired_outputs": QCKeySpec("value", (), ("{t}-qc",), ALL),
    "provenance": QCKeySpec("value", (), ("{t}-qc",), ALL),
}


def type_label(analysis_type):
    """Return the type label for an analysis type."""
    return names.TYPE_LABEL[analysis_type]


def _matches_producer(label, patterns, tl):
    """Check if *label* matches any producer pattern."""
    for pat in patterns:
        resolved = pat.replace("{t}", tl)
        if fnmatch.fnmatch(label, resolved):
            return True
    return False


def merge_fragments(fragments, analysis_type):
    """Merge per-step QC fragments into the final qc_summary dict.

    Parameters
    ----------
    fragments : list of (str, dict)
        Each element is ``(producer_label, fragment_dict)``.
    analysis_type : str
        One of ``'task_act'``, ``'task_conn'``, ``'rest_conn'``.

    Returns
    -------
    dict
        Merged QC summary in QC_KEYS insertion order.

    Raises
    ------
    GuardError
        On unknown keys, disallowed producer labels, duplicate value
        producers, or duplicate identity records.
    """
    tl = type_label(analysis_type)
    merged = {}
    value_producers = {}  # key -> producer label that set it

    for label, frag in fragments:
        for key, value in frag.items():
            if key not in QC_KEYS:
                raise GuardError(
                    f"Unknown qc_summary key '{key}' from producer '{label}'."
                )
            spec = QC_KEYS[key]
            if analysis_type not in spec.types:
                raise GuardError(
                    f"QC key '{key}' is not valid for analysis type "
                    f"'{analysis_type}' (valid: {spec.types}). "
                    f"Producer: '{label}'."
                )
            if not _matches_producer(label, spec.producers, tl):
                raise GuardError(
                    f"Producer '{label}' is not allowed for QC key '{key}'. "
                    f"Allowed patterns: {spec.producers}"
                )

            if spec.kind == "value":
                if key in value_producers:
                    raise GuardError(
                        f"QC key '{key}' (value kind) already set by "
                        f"'{value_producers[key]}'; second producer: '{label}'."
                    )
                merged[key] = value
                value_producers[key] = label
            else:
                # records: must be a list of dicts with identity fields
                if not isinstance(value, list):
                    raise GuardError(
                        f"QC key '{key}' (records kind) from '{label}' "
                        f"must be a list, got {type(value).__name__}."
                    )
                for rec in value:
                    if not isinstance(rec, dict):
                        raise GuardError(
                            f"QC key '{key}' record from '{label}' "
                            f"must be a dict, got {type(rec).__name__}."
                        )
                    for idf in spec.identity:
                        if idf not in rec:
                            raise GuardError(
                                f"QC key '{key}' record from '{label}' "
                                f"is missing identity field '{idf}'."
                            )
                if key not in merged:
                    merged[key] = []
                # Check for cross-producer identity duplicates
                existing_ids = set()
                for rec in merged[key]:
                    identity = tuple(
                        (f, rec.get(f)) for f in spec.identity
                    )
                    existing_ids.add(identity)
                for rec in value:
                    identity = tuple(
                        (f, rec.get(f)) for f in spec.identity
                    )
                    if identity in existing_ids:
                        raise GuardError(
                            f"QC key '{key}': duplicate identity {dict(identity)} "
                            f"from producer '{label}'."
                        )
                    existing_ids.add(identity)
                merged[key].extend(value)

    # Sort records by identity (None-safe)
    for key, spec in QC_KEYS.items():
        if key in merged and spec.kind == "records":
            merged[key] = sorted(
                merged[key],
                key=lambda rec: tuple(
                    (rec.get(f) is None, rec.get(f))
                    for f in spec.identity
                ),
            )

    # Re-order to QC_KEYS insertion order
    ordered = {}
    for key in QC_KEYS:
        if key in merged:
            ordered[key] = merged[key]
    return ordered


def qc_json_text(qc):
    """Serialize a QC summary dict to canonical JSON text.

    Uses ``allow_nan=False`` so that NaN values in QC data are caught as
    bugs (QC producers must emit null instead).

    Returns
    -------
    str
        JSON text with a trailing newline.
    """
    return json.dumps(qc, indent=2, allow_nan=False) + "\n"
