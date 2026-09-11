"""BIDS derivative path construction, dataset description, and input discovery utilities.

Provides helpers for constructing BIDS-compliant output file paths under a
derivatives root directory, for writing the required dataset_description.json
file for BIDS derivative datasets, and for discovering BIDS derivative input
files from one or more derivatives directories.
"""

import dataclasses
import glob
import json
import logging
import os

from .exceptions import InputError  # noqa: F401 -- available for callers
from .first_level_utils import graded_warning, sanitize_filename_label

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DiscoveredInputs dataclass
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class DiscoveredInputs:
    """Container for BIDS-discovered input file paths.

    Single-path fields (scan_path, motion_path, task_timing_path, CSF_path,
    WM_path) are populated for task_act and task_conn analyses.
    List-path fields (scan_paths, motion_paths, CSF_paths, WM_paths, GS_paths)
    are populated for rest_conn analyses. template_path applies to all types.
    source_dirs maps each populated slot name to the derivatives directory in
    which the first match was found.
    """

    scan_path: str | None = None
    motion_path: str | None = None
    task_timing_path: str | None = None
    CSF_path: str | None = None
    WM_path: str | None = None
    scan_paths: list[str] | None = None
    motion_paths: list[str] | None = None
    CSF_paths: list[str] | None = None
    WM_paths: list[str] | None = None
    GS_paths: list[str] | None = None
    template_path: str | None = None
    source_dirs: dict[str, str] = dataclasses.field(default_factory=dict)


# ---------------------------------------------------------------------------
# Private discovery helpers
# ---------------------------------------------------------------------------

def _get_func_dir(deriv_dir: str, subject: str, session: str | None) -> str:
    """Return the BIDS func directory path within a derivatives root."""
    if session is not None:
        return os.path.join(deriv_dir, f"sub-{subject}", f"ses-{session}", "func")
    return os.path.join(deriv_dir, f"sub-{subject}", "func")


def _glob_bids_files(
    func_dir: str,
    subject: str,
    task: str | None,
    desc: str | None,
    suffix: str,
    ext: str,
) -> list[str]:
    """Glob for BIDS-named files in func_dir matching the given entities.

    The glob pattern follows BIDS entity ordering:
    sub-{sub}[*_task-{task}*][_desc-{desc}]_{suffix}{ext}

    Returns a sorted list of matching absolute paths, or an empty list when
    func_dir does not exist or no matches are found.
    """
    if not os.path.isdir(func_dir):
        return []

    if task is not None:
        if desc is not None:
            pattern = f"sub-{subject}*_task-{task}*_desc-{desc}_{suffix}{ext}"
        else:
            pattern = f"sub-{subject}*_task-{task}*_{suffix}{ext}"
    else:
        if desc is not None:
            pattern = f"sub-{subject}*_desc-{desc}_{suffix}{ext}"
        else:
            pattern = f"sub-{subject}*_{suffix}{ext}"

    return sorted(glob.glob(os.path.join(func_dir, pattern)))


# ---------------------------------------------------------------------------
# Public discovery API
# ---------------------------------------------------------------------------

def discover_inputs(
    derivatives_dirs: list[str],
    subject: str,
    session: str | None,
    task: str | None,
    analysis_type: str,
    logger: logging.Logger | None = None,
) -> DiscoveredInputs:
    """Discover BIDS derivative input files from one or more derivatives directories.

    Iterates derivatives_dirs in list order. For each slot, the first directory
    that yields matches wins. If a slot matches in more than one directory, a
    DISCOVERY_COLLISION graded_warning (severity='medium') is emitted. Slots
    with no matches in any directory are returned as None; mandatory-slot
    enforcement is the caller's responsibility (see resolve_config).

    Parameters
    ----------
    derivatives_dirs:
        Ordered list of BIDS derivatives root directories to search.
    subject:
        BIDS subject label without the ``sub-`` prefix (e.g. ``'001'``).
    session:
        BIDS session label without the ``ses-`` prefix, or None.
    task:
        BIDS task label without the ``task-`` prefix, or None.
    analysis_type:
        One of ``'task_act'``, ``'task_conn'``, or ``'rest_conn'``. Governs
        which slots are searched and whether single or list fields are populated.
    logger:
        Optional logger for DISCOVERY_COLLISION warnings. Warnings are silently
        suppressed when logger is None.

    Returns
    -------
    DiscoveredInputs
        Dataclass with discovered paths. Slots not found in any directory are
        set to None.

    Slot definitions
    ----------------
    +--------------------+----------+-----------+---------+---------------------+
    | Slot               | desc     | suffix    | ext     | Mandatory (by type) |
    +====================+==========+===========+=========+=====================+
    | scan_path/paths    | preproc  | bold      | .nii.gz | all types           |
    | motion_path/paths  | confounds| regressors| .tsv    | all types           |
    | task_timing_path   | --       | events    | .tsv    | task_act, task_conn |
    | CSF_path/paths     | CSF      | timeseries| .1D     | rest_conn           |
    | WM_path/paths      | WM       | timeseries| .1D     | rest_conn           |
    | GS_paths           | GS       | timeseries| .1D     | optional            |
    | template_path      | --       | dseg      | .nii.gz | optional            |
    +--------------------+----------+-----------+---------+---------------------+
    """
    result = DiscoveredInputs()

    # Slot definitions: (attr_name, desc, suffix, ext, is_list)
    if analysis_type in ("task_act", "task_conn"):
        slot_defs = [
            ("scan_path",        "preproc",   "bold",       ".nii.gz", False),
            ("motion_path",      "confounds", "regressors", ".tsv",    False),
            ("task_timing_path", None,        "events",     ".tsv",    False),
            ("CSF_path",         "CSF",       "timeseries", ".1D",     False),
            ("WM_path",          "WM",        "timeseries", ".1D",     False),
            ("template_path",    None,        "dseg",       ".nii.gz", False),
        ]
    else:  # rest_conn
        slot_defs = [
            ("scan_paths",    "preproc",   "bold",       ".nii.gz", True),
            ("motion_paths",  "confounds", "regressors", ".tsv",    True),
            ("CSF_paths",     "CSF",       "timeseries", ".1D",     True),
            ("WM_paths",      "WM",        "timeseries", ".1D",     True),
            ("GS_paths",      "GS",        "timeseries", ".1D",     True),
            ("template_path", None,        "dseg",       ".nii.gz", False),
        ]

    for attr_name, desc, suffix, ext, is_list in slot_defs:
        first_matches: list[str] | None = None
        first_dir: str | None = None

        for deriv_dir in derivatives_dirs:
            func_dir = _get_func_dir(deriv_dir, subject, session)
            matches = _glob_bids_files(func_dir, subject, task, desc, suffix, ext)

            if matches:
                if first_matches is None:
                    first_matches = matches
                    first_dir = deriv_dir
                elif logger is not None:
                    graded_warning(
                        logger,
                        severity="medium",
                        code="DISCOVERY_COLLISION",
                        message=(
                            f"BIDS discovery collision for slot '{attr_name}': matches found in "
                            f"'{first_dir}' and '{deriv_dir}'. Using '{first_dir}'."
                        ),
                        user_facing=True,
                    )

        if first_matches is not None:
            if is_list:
                setattr(result, attr_name, first_matches)
            else:
                setattr(result, attr_name, first_matches[0])
            result.source_dirs[attr_name] = first_dir  # type: ignore[assignment]

    return result


# Canonical BIDS entity ordering for derivative filenames.
_ENTITY_ORDER: list[str] = [
    "sub",
    "ses",
    "task",
    "acq",
    "rec",
    "run",
    "space",
    "desc",
    "stat",
]


def build_bids_output_path(
    output_dir: str,
    entities: dict[str, str],
    suffix: str,
    ext: str,
) -> str:
    """Construct an absolute BIDS-derivative output path for a given file.

    The directory structure follows BIDS derivatives convention:
    ``{output_dir}/sub-{sub}[/ses-{ses}]/func/``

    The filename follows BIDS entity ordering (sub, ses, task, acq, rec, run,
    space, desc, stat). Only entities with non-None values are included.
    All entity values are sanitized via ``sanitize_filename_label()``.

    Parameters
    ----------
    output_dir:
        Derivatives root directory (the ``out_dir`` value from ResolvedConfig).
    entities:
        Mapping of BIDS entity keys to their string values. Recognised keys are
        ``sub``, ``ses``, ``task``, ``acq``, ``rec``, ``run``, ``space``,
        ``desc``, and ``stat``. Keys absent from the mapping or mapped to
        ``None`` are omitted from the filename and directory path.
    suffix:
        BIDS suffix (e.g. ``"bold"``, ``"timeseries"``).
    ext:
        File extension including the leading dot (e.g. ``".nii.gz"``,
        ``".tsv"``).

    Returns
    -------
    str
        Absolute path to the target output file.
    """
    sub = entities.get("sub")
    if sub is None:
        raise ValueError("entities must contain a non-None 'sub' key.")

    sub_val = sanitize_filename_label(str(sub))

    # Build directory: output_dir/sub-{sub}[/ses-{ses}]/func/
    ses = entities.get("ses")
    if ses is not None:
        ses_val = sanitize_filename_label(str(ses))
        func_dir = os.path.join(
            output_dir,
            f"sub-{sub_val}",
            f"ses-{ses_val}",
            "func",
        )
    else:
        ses_val = None
        func_dir = os.path.join(output_dir, f"sub-{sub_val}", "func")

    # Build filename from ordered entities.
    parts: list[str] = []
    for key in _ENTITY_ORDER:
        val = entities.get(key)
        if val is None:
            continue
        sanitized = sanitize_filename_label(str(val))
        parts.append(f"{key}-{sanitized}")

    filename = "_".join(parts) + f"_{suffix}{ext}"
    return os.path.join(func_dir, filename)


def write_dataset_description(
    derivatives_dir: str,
    source_datasets: list[dict] | None = None,
) -> None:
    """Write a BIDS dataset_description.json for a derivative dataset.

    Creates ``{derivatives_dir}/dataset_description.json`` with the following
    required fields:

    - ``Name``: ``"fmri-first-level-proc"``
    - ``BIDSVersion``: ``"1.9.0"``
    - ``DatasetType``: ``"derivative"``
    - ``GeneratedBy``: ``[{"Name": "fmri-first-level-proc"}]``
    - ``SourceDatasets``: the supplied list, or an empty list when omitted.

    This function is a no-op if ``dataset_description.json`` already exists in
    ``derivatives_dir``, preserving any externally-managed file.

    Parameters
    ----------
    derivatives_dir:
        Root directory of the BIDS derivative dataset.
    source_datasets:
        Optional list of BIDS SourceDatasets entries (each a dict with at
        minimum a ``"URL"`` key). Defaults to an empty list.
    """
    out_path = os.path.join(derivatives_dir, "dataset_description.json")
    if os.path.isfile(out_path):
        logger.debug(
            "dataset_description.json already exists at %s; skipping write.",
            out_path,
        )
        return

    description: dict = {
        "Name": "fmri-first-level-proc",
        "BIDSVersion": "1.9.0",
        "DatasetType": "derivative",
        "GeneratedBy": [{"Name": "fmri-first-level-proc"}],
        "SourceDatasets": source_datasets if source_datasets is not None else [],
    }

    os.makedirs(derivatives_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(description, fh, indent=2)
    logger.info("Wrote dataset_description.json to %s", out_path)
