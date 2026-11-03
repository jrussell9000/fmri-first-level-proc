"""BIDS derivative input discovery for per-run slots.

Discovers per-run input files from BIDS derivative directories. Every per-run
slot is returned as a list (length 1 for a single run). ``template_path`` is
never discovered here (it is a global config key only).

Run labels are extracted from BIDS ``run-{N}`` entities in filenames. Files
without a run entity are treated as single-run inputs (label None).
Subject, task and desc entities are matched exactly (``task-rest`` does not
match ``task-restpre``).
"""

import dataclasses
import glob
import logging
import os
import re

from .exceptions import InputError
from .first_level_utils import graded_warning

RUN_RE = re.compile(r"(^|_)run-(\d+)(_|\.)")
ENTITY_RE = re.compile(r"(?:^|_)([a-zA-Z]+)-([a-zA-Z0-9]+)(?=_|\.)")


# ---------------------------------------------------------------------------
# DiscoveredInputs dataclass
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class DiscoveredInputs:
    """Container for BIDS-discovered input file paths.

    Every per-run slot is a list (length 1 for a single run). The
    ``run_labels`` dict maps each populated slot name to the list of
    integer run labels (or [None] for a single unlabeled file), aligned
    with that slot's file list. ``template_path`` is never discovered
    (global config key only).
    """

    scan_paths: list[str] | None = None
    motion_paths: list[str] | None = None
    task_timing_paths: list[str] | None = None
    CSF_paths: list[str] | None = None
    WM_paths: list[str] | None = None
    GS_paths: list[str] | None = None
    run_labels: dict[str, list[int | None]] = dataclasses.field(default_factory=dict)
    source_dirs: dict[str, str] = dataclasses.field(default_factory=dict)


# ---------------------------------------------------------------------------
# Private discovery helpers
# ---------------------------------------------------------------------------

def _get_func_dir(deriv_dir, subject, session=None):
    """Return the BIDS func directory path within a derivatives root."""
    if session is not None:
        return os.path.join(deriv_dir, f"sub-{subject}", f"ses-{session}", "func")
    return os.path.join(deriv_dir, f"sub-{subject}", "func")


def _entities(basename):
    """Return the BIDS key-value entities of a file basename as a dict."""
    return {k: v for k, v in ENTITY_RE.findall(basename)}


def _glob_bids_files(func_dir, subject, task, desc, suffix, ext):
    """Find BIDS-named files in func_dir whose entities match exactly.

    sub must equal *subject*; task must equal *task* when given; desc must
    equal *desc* when given (desc is not checked when None, as for events
    files). Returns an unsorted list of matching absolute paths (ordering is
    done by label in the caller).
    """
    if not os.path.isdir(func_dir):
        return []

    matches = []
    for path in glob.glob(os.path.join(func_dir, f"sub-{subject}_*_{suffix}{ext}")):
        ents = _entities(os.path.basename(path))
        if ents.get("sub") != subject:
            continue
        if task is not None and ents.get("task") != task:
            continue
        if desc is not None and ents.get("desc") != desc:
            continue
        matches.append(path)
    return matches


def _label_and_sort(files, slot_name):
    """Label files by run entity and sort by integer label.

    Parameters
    ----------
    files : list of str
    slot_name : str
        For error messages.

    Returns
    -------
    (sorted_files, labels)
        sorted_files: list of str, ordered by integer label.
        labels: list of int|None, aligned with sorted_files.

    Raises
    ------
    InputError
        If files mix labeled and unlabeled, have duplicate labels, or
        contain more than one unlabeled file.
    """
    labeled = []
    unlabeled = []
    for path in files:
        basename = os.path.basename(path)
        m = RUN_RE.search(basename)
        if m:
            labeled.append((int(m.group(2)), path))
        else:
            unlabeled.append(path)

    if labeled and unlabeled:
        raise InputError(
            f"Discovery slot '{slot_name}': files mix labeled and unlabeled "
            f"run entities. Labeled: {[p for _, p in labeled]}. "
            f"Unlabeled: {unlabeled}."
        )

    if len(unlabeled) > 1:
        raise InputError(
            f"Discovery slot '{slot_name}': multiple unlabeled files "
            f"(no run entity): {unlabeled}."
        )

    if unlabeled:
        return unlabeled, [None]

    # Check for duplicate labels
    label_set = set()
    for lbl, path in labeled:
        if lbl in label_set:
            raise InputError(
                f"Discovery slot '{slot_name}': duplicate run label {lbl} "
                f"in files: {[p for _, p in labeled]}."
            )
        label_set.add(lbl)

    # Sort by label
    labeled.sort(key=lambda x: x[0])
    return [p for _, p in labeled], [lbl for lbl, _ in labeled]


# ---------------------------------------------------------------------------
# Public discovery API
# ---------------------------------------------------------------------------

def discover_inputs(derivatives_dirs, subject, session, task, analysis_type,
                    logger=None):
    """Discover BIDS derivative input files from one or more derivatives directories.

    Iterates derivatives_dirs in list order. For each slot, the first directory
    that yields matches wins. If a slot matches in more than one directory, a
    DISCOVERY_COLLISION graded_warning (severity='medium') is emitted.

    Parameters
    ----------
    derivatives_dirs : list of str
    subject : str
        BIDS subject label without the ``sub-`` prefix.
    session : str or None
    task : str or None
    analysis_type : str
        ``'task_act'``, ``'task_conn'``, or ``'rest_conn'``.
    logger : logging.Logger, optional

    Returns
    -------
    DiscoveredInputs
    """
    result = DiscoveredInputs()

    # Slot definitions: (attr_name, desc, suffix, ext)
    # All slots return lists (per-run).
    common_slots = [
        ("scan_paths", "preproc", "bold", ".nii.gz"),
        ("motion_paths", "confounds", "regressors", ".tsv"),
        ("CSF_paths", "CSF", "timeseries", ".1D"),
        ("WM_paths", "WM", "timeseries", ".1D"),
    ]

    if analysis_type in ("task_act", "task_conn"):
        slot_defs = common_slots + [
            ("task_timing_paths", None, "events", ".tsv"),
        ]
    else:  # rest_conn
        slot_defs = common_slots + [
            ("GS_paths", "GS", "timeseries", ".1D"),
        ]

    for attr_name, desc, suffix, ext in slot_defs:
        first_matches = None
        first_dir = None

        for deriv_dir in derivatives_dirs:
            func_dir = _get_func_dir(deriv_dir, subject, session)
            matches = _glob_bids_files(func_dir, subject, task, desc, suffix, ext)

            if matches:
                if first_matches is None:
                    first_matches = matches
                    first_dir = deriv_dir
                else:
                    graded_warning(
                        logger or logging.getLogger(__name__),
                        severity="medium",
                        code="DISCOVERY_COLLISION",
                        message=(
                            f"BIDS discovery collision for slot '{attr_name}': "
                            f"matches found in '{first_dir}' and '{deriv_dir}'. "
                            f"Using '{first_dir}'."
                        ),
                        user_facing=True,
                    )

        if first_matches is not None:
            sorted_files, labels = _label_and_sort(first_matches, attr_name)
            setattr(result, attr_name, sorted_files)
            result.run_labels[attr_name] = labels
            result.source_dirs[attr_name] = first_dir

    return result
