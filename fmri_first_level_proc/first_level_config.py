#!/usr/bin/env python3

# ============================================================================
# YAML CONFIG LOADER AND VALIDATOR FOR fMRI FIRST-LEVEL PROCESSING
# Reads a YAML config file, validates its structure and values, merges global
# defaults into each analysis block, and builds ResolvedConfig typed dataclass
# objects for each analysis block.
#
# Author: Taylor J. Keding, Ph.D.
# ============================================================================
"""
YAML configuration loader, validator, and resolver for fmri_first_level_proc.

Public API
----------
load_and_validate(config_path, logger, **overrides)
    Full pipeline: load YAML -> merge overrides -> validate -> resolve.
    Returns a list of ResolvedConfig instances suitable for direct dispatch
    to each pipeline's run() function. The first invalid block raises.

load_and_validate_blocks(config_path, logger, **overrides)
    Per-block variant used by the CLI: returns one BlockResolution per
    analysis block, each holding either a ResolvedConfig or the error that
    block raised, so valid blocks can run when others are invalid. Global
    problems (unreadable YAML, top-level or global section errors) still raise.

BlockResolution
    Dataclass with index, name, analysis_type, config, error, raw_out_dir
    and raw_out_file_pre for one analysis block.

ResolvedConfig
    Typed dataclass with all pipeline-specific fields; its docstring states
    the schema_version policy.

Config Schema Overview
----------------------
global:
    tr              : float (required)
    num_cores       : int
    template_path   : str
    force_diff_atlas: bool
    derivatives_dirs: list[str]

analyses:
    - name           : str (optional label)
      type           : 'task_act' | 'task_conn' | 'rest_conn'
      out_dir        : str
      out_file_pre   : str
      paths          : dict of file paths (type-dependent, Mode A or Mode B)
      run_labels     : list[int]
      run_lengths    : list[int] (Mode B only)
      smoothing      : {enabled: bool, fwhm: float}
      roi_zero_handling: 'exclude' | 'include'
      ... (type-specific keys; see INPUT_SPECIFICATION.md for full schema)

Validation uses a closed schema: unknown keys produce aggregate ConfigError.
"""
from __future__ import annotations

import dataclasses
import logging
import math
import numbers
import os
import re
from decimal import Decimal

import yaml

from .bids import discover_inputs, RUN_RE
from .exceptions import ConfigError, InputError
from .first_level_utils import (
    VALID_HRF_MODELS, validate_custom_hrf, needs_married_timing, sanitize_filename_label,
    valid_contrast_functions,
)


# ---------------------------------------------------------------------------
# Enum constants
# ---------------------------------------------------------------------------

VALID_TYPES = {"task_act", "task_conn", "rest_conn"}
VALID_STAT_BUCKET_TYPES = {"Coef", "Tstat", "Fstat", "R^2", "Zstat"}
VALID_AVE_TYPES = {"mean", "median"}
VALID_CONN_TYPES = {"seed_to_voxel", "parcellated"}
VALID_ROI_ZERO_HANDLING = {"exclude", "include"}

# Config schema version; see ResolvedConfig's docstring for the versioning policy.
SCHEMA_VERSION = "4.0.0"


# ---------------------------------------------------------------------------
# Closed schema key tables
# ---------------------------------------------------------------------------

TOP_KEYS = {"global", "analyses"}

GLOBAL_KEYS = {"tr", "num_cores", "template_path", "force_diff_atlas", "derivatives_dirs"}

GLOBAL_ONLY_KEYS = ("num_cores", "template_path", "force_diff_atlas", "tr")

_COMMON = {
    "name", "type", "out_dir", "out_file_pre", "paths", "average_type",
    "fd_threshold", "censor_prev_tr", "remove_previous", "scale_to_psc",
    "run_labels", "smoothing", "roi_zero_handling", "derivatives_dirs",
    "subject", "session", "task", "extraction",
}

BLOCK_KEYS = {
    "task_act": _COMMON | {
        "hrf_model", "custom_hrf", "include_motion_derivs",
        "use_tissue_derivs", "run_lengths", "cond_labels", "contrasts",
    },
    "task_conn": _COMMON | {
        "hrf_model", "custom_hrf", "include_motion_derivs",
        "use_tissue_derivs", "run_lengths", "cond_beta_labels", "connectivity",
    },
    "rest_conn": _COMMON | {
        "bandpass", "notch_filter_band", "motion_deriv_degree",
        "use_tissue_derivs", "use_sequenced_bandpass",
        "keep_run_res_dtseries", "connectivity",
    },
}

PATH_KEYS = {
    "task_act": {
        "scan_path", "scan_paths", "task_timing_path", "task_timing_paths",
        "motion_path", "motion_paths", "CSF_path", "CSF_paths",
        "WM_path", "WM_paths",
    },
    "task_conn": {
        "scan_path", "scan_paths", "task_timing_path", "task_timing_paths",
        "motion_path", "motion_paths", "CSF_path", "CSF_paths",
        "WM_path", "WM_paths",
    },
    "rest_conn": {
        "scan_paths", "motion_paths", "CSF_paths", "WM_paths", "GS_paths",
    },
}

EXTRACTION_KEYS = {
    "task_act": {"stat_buckets", "extract_out_file_pre", "extract_resids", "extract_raw_ptseries"},
    "task_conn": {"extract_pbseries", "extract_out_file_pre", "extract_raw_ptseries"},
    "rest_conn": {"extract_ptseries", "extract_out_file_pre", "extract_raw_ptseries"},
}

CONNECTIVITY_KEYS = {
    "task_conn": {"calc_conn", "conn_out_file_pre", "pcorr", "fishZ", "contrasts"},
    "rest_conn": {"calc_conn", "conn_out_file_pre", "pcorr", "fishZ"},
}

CONTRAST_KEYS = {"functions", "labels"}
SMOOTHING_KEYS = {"enabled", "fwhm"}

LEGACY_EXTRACTION_KEYS = {"extract", "extract_labels", "extract_stat"}

# File-name-safe token for output prefixes and condition labels
FILENAME_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

# Boolean keys (true, false or null = default)
_TASK_BOOLS = ("censor_prev_tr", "remove_previous", "scale_to_psc",
               "include_motion_derivs", "use_tissue_derivs")
BOOL_FIELDS = {
    "task_act": _TASK_BOOLS,
    "task_conn": _TASK_BOOLS,
    "rest_conn": ("censor_prev_tr", "remove_previous", "scale_to_psc", "use_tissue_derivs",
                  "use_sequenced_bandpass", "keep_run_res_dtseries"),
}
NESTED_BOOL_FIELDS = {
    "extraction": ("extract_resids", "extract_raw_ptseries", "extract_pbseries", "extract_ptseries"),
    "connectivity": ("pcorr", "fishZ"),
}

# Fields excluded from stage hashing (exempt from per-stage field declarations)
EXEMPT_FIELDS = frozenset({
    "num_cores", "remove_previous", "schema_version", "analysis_type",
    "analysis_name", "out_dir", "out_file_pre", "derivatives_dirs",
    "force_diff_atlas",
})


def allowed_keys(analysis_type):
    """Return the frozenset of dotted key names accepted for *analysis_type*.

    Includes nested keys such as ``'paths.scan_path'``,
    ``'extraction.stat_buckets'``, ``'connectivity.contrasts.functions'``,
    ``'smoothing.fwhm'``.

    Parameters
    ----------
    analysis_type : str

    Returns
    -------
    frozenset of str
    """
    keys = set(BLOCK_KEYS[analysis_type])
    for pk in PATH_KEYS[analysis_type]:
        keys.add(f"paths.{pk}")
    for ek in EXTRACTION_KEYS.get(analysis_type, set()):
        keys.add(f"extraction.{ek}")
    for ck in CONNECTIVITY_KEYS.get(analysis_type, set()):
        keys.add(f"connectivity.{ck}")
    if analysis_type == "task_conn" and "contrasts" in CONNECTIVITY_KEYS.get(analysis_type, set()):
        for cckeys in CONTRAST_KEYS:
            keys.add(f"connectivity.contrasts.{cckeys}")
    if analysis_type == "task_act" and "contrasts" in BLOCK_KEYS.get(analysis_type, set()):
        for cckeys in CONTRAST_KEYS:
            keys.add(f"contrasts.{cckeys}")
    for sk in SMOOTHING_KEYS:
        keys.add(f"smoothing.{sk}")
    return frozenset(keys)


# ---------------------------------------------------------------------------
# ResolvedConfig dataclass
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class ResolvedConfig:
    """Flat, typed configuration for one analysis block.

    All pipeline-specific Optional fields default to None or their zero-value.
    schema_version follows the policy: MAJOR.MINOR.0 of the package release in
    which the config schema, ResolvedConfig fields and YAML validation rules last
    changed. Removal, rename, meaning change or validation tightening ship only in
    a package major. Additions bump minor at the package minor that adds them.
    Patch is always 0. Current value: SCHEMA_VERSION.
    """

    # Schema and identity
    schema_version: str       # SCHEMA_VERSION
    analysis_type: str        # "task_act" | "task_conn" | "rest_conn"
    analysis_name: str | None = None

    # Common
    out_dir: str = ""
    out_file_pre: str = ""
    tr: float = 0.0
    fd_threshold: float = 0.0
    average_type: str = ""
    num_cores: int = 1
    remove_previous: bool = False
    censor_prev_tr: bool = False
    template_path: str | None = None
    force_diff_atlas: bool = False
    scale_to_psc: bool = True

    # BIDS discovery (optional)
    derivatives_dirs: list[str] | None = None

    # Task-common (task_act + task_conn): Mode B (singular paths)
    scan_path: str | None = None
    task_timing_path: str | None = None
    motion_path: str | None = None
    hrf_model: str | None = None
    custom_hrf: str | None = None
    CSF_path: str | None = None
    WM_path: str | None = None
    include_motion_derivs: bool = False
    use_tissue_derivs: bool = False

    # Condition labels
    cond_labels: list[str] | None = None        # task_act
    cond_beta_labels: list[str] | None = None   # task_conn

    # Contrasts (task_act + task_conn)
    contrast_functions: list[str] | None = None
    contrast_labels: list[str] | None = None

    # task_act extraction
    stat_buckets: list[str] | None = None
    extract_out_file_pre: str | None = None
    extract_resids: bool = False
    extract_raw_ptseries: bool = False

    # task_conn extraction
    extract_pbseries: bool = False

    # Connectivity (task_conn + rest_conn)
    calc_conn: str | None = None
    conn_out_file_pre: str | None = None
    pcorr: bool = False
    fishZ: bool = False

    # Per-run lists (rest_conn and task Mode A)
    scan_paths: list[str] | None = None
    motion_paths: list[str] | None = None
    CSF_paths: list[str] | None = None
    WM_paths: list[str] | None = None
    GS_paths: list[str] | None = None
    task_timing_paths: list[str] | None = None

    # rest_conn specific
    bandpass: list[float] | None = None
    notch_filter_band: list[float] | None = None
    motion_deriv_degree: int | None = None
    use_sequenced_bandpass: bool = False
    keep_run_res_dtseries: bool = True

    # rest_conn extraction
    extract_ptseries: bool = False

    # Run identity, smoothing, and ROI zero-handling (all analysis types; run_lengths is task-only)
    run_lengths: list[int] | None = None
    run_labels: list[int] | None = None
    smoothing_enabled: bool = False
    smoothing_fwhm: float | None = None
    roi_zero_handling: str = "exclude"

    @property
    def input_mode(self) -> str:
        """Return ``'A'`` if per-run file lists are set, else ``'B'``."""
        if self.scan_paths is not None:
            return "A"
        return "B"


# ---------------------------------------------------------------------------
# Stage 1: load_config
# ---------------------------------------------------------------------------

def load_config(config_path: str) -> dict:
    """Load a YAML config file and return the raw dict.

    Raises ConfigError on missing file or YAML parse failure.
    """
    if not os.path.isfile(config_path):
        raise ConfigError(f"Config file not found: {config_path}")
    with open(config_path, "r") as f:
        try:
            raw = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"YAML parse error in {config_path}: {e}") from e
    if raw is None:
        raise ConfigError(f"Config file is empty: {config_path}")
    if not isinstance(raw, dict):
        raise ConfigError(
            f"Config file {config_path} must contain a mapping with 'global' and "
            "'analyses' keys."
        )
    return raw


# ---------------------------------------------------------------------------
# Stage 2: validate_config
# ---------------------------------------------------------------------------

def _finite_number(value, where):
    """Return *value* as a float, raising ConfigError unless it is a finite real number."""
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ConfigError(f"{where} must be a number, got {value!r}.")
    if not math.isfinite(value):
        raise ConfigError(f"{where} must be finite, got {value!r}.")
    return float(value)


def _positive_int(value, where):
    """Return *value* if it is an integer >= 1 (booleans rejected); else raise ConfigError."""
    if isinstance(value, bool) or not isinstance(value, numbers.Integral) or value < 1:
        raise ConfigError(f"{where} must be a positive integer, got {value!r}.")
    return int(value)


def _check_derivatives_dirs(value, where):
    """Raise ConfigError unless *value* is None or a non-empty list of non-empty strings."""
    if value is None:
        return
    if isinstance(value, str):
        raise ConfigError(
            f"{where} must be a YAML list of directory paths, got the string {value!r}; "
            f"write it as a list, e.g. [{value!r}]."
        )
    if (not isinstance(value, list) or not value
            or not all(isinstance(d, str) and d for d in value)):
        raise ConfigError(f"{where} must be a non-empty list of directory path strings.")


def _check_token(value, where):
    """Raise ConfigError unless *value* is a file-name-safe string (FILENAME_TOKEN_RE)."""
    if not isinstance(value, str) or not FILENAME_TOKEN_RE.match(value):
        raise ConfigError(
            f"{where} must be a string of letters, digits, '.', '_' or '-' that starts "
            f"with a letter or digit, got {value!r}."
        )


def _global_schema_errors(raw_config):
    """Return (pass-1 error list, global dict) for the top-level and global sections."""
    errors = []
    for k in raw_config:
        if k not in TOP_KEYS:
            errors.append(f"top-level key '{k}': unknown (valid: {sorted(TOP_KEYS)})")

    if "analyses" not in raw_config:
        raise ConfigError("Config missing required top-level key 'analyses'.")
    if not isinstance(raw_config["analyses"], list) or len(raw_config["analyses"]) == 0:
        raise ConfigError("'analyses' must be a non-empty list.")

    global_cfg = raw_config.get("global", {})
    if not isinstance(global_cfg, dict):
        raise ConfigError("'global' must be a dict if provided.")

    for k in global_cfg:
        if k not in GLOBAL_KEYS:
            errors.append(f"global.{k}: unknown (valid: {sorted(GLOBAL_KEYS)})")
    return errors, global_cfg


def _schema_pass1_block(idx, block):
    """Return the closed-schema (pass 1) violations of one analysis block."""
    if not isinstance(block, dict):
        return [f"analyses[{idx}]: must be a mapping, got {type(block).__name__}"]
    errors = []
    name = block.get("name", f"analyses[{idx}]")
    prefix = f"analyses[{idx}] ({name})"

    atype = block.get("type")
    if atype is None or atype not in VALID_TYPES:
        errors.append(f"{prefix}.type: missing or invalid (got {atype!r}, valid: {sorted(VALID_TYPES)})")
        return errors  # cannot check further keys without a valid type

    valid_block = BLOCK_KEYS[atype]
    valid_path = PATH_KEYS[atype]
    valid_ext = EXTRACTION_KEYS.get(atype, set())
    valid_conn = CONNECTIVITY_KEYS.get(atype, set())

    # Block-level unknown keys (global-only keys get their own message below)
    for k in block:
        if k not in valid_block and k not in GLOBAL_ONLY_KEYS:
            errors.append(f"{prefix}.{k}: unknown for type '{atype}'")

    for k in GLOBAL_ONLY_KEYS:
        if k in block:
            errors.append(
                f"{prefix}.{k}: this key belongs in the global section, "
                "not in an analysis block"
            )

    paths = block.get("paths")
    if isinstance(paths, dict):
        for k in paths:
            if k not in valid_path:
                errors.append(f"{prefix}.paths.{k}: unknown for type '{atype}'")

    extraction = block.get("extraction")
    if isinstance(extraction, dict):
        for k in extraction:
            if k in LEGACY_EXTRACTION_KEYS:
                errors.append(
                    f"{prefix}.extraction.{k}: legacy key removed in 4.0.0. "
                    "Use extraction.stat_buckets instead."
                )
            elif k not in valid_ext:
                errors.append(f"{prefix}.extraction.{k}: unknown for type '{atype}'")

    connectivity = block.get("connectivity")
    if isinstance(connectivity, dict):
        for k in connectivity:
            if k == "contrasts" and "contrasts" in valid_conn:
                conn_contrasts = connectivity.get("contrasts")
                if isinstance(conn_contrasts, dict):
                    for ck in conn_contrasts:
                        if ck not in CONTRAST_KEYS:
                            errors.append(
                                f"{prefix}.connectivity.contrasts.{ck}: unknown "
                                f"(valid: {sorted(CONTRAST_KEYS)})"
                            )
            elif k not in valid_conn:
                errors.append(f"{prefix}.connectivity.{k}: unknown for type '{atype}'")

    if atype == "task_act":
        contrasts = block.get("contrasts")
        if isinstance(contrasts, dict):
            for k in contrasts:
                if k not in CONTRAST_KEYS:
                    errors.append(
                        f"{prefix}.contrasts.{k}: unknown (valid: {sorted(CONTRAST_KEYS)})"
                    )

    smoothing = block.get("smoothing")
    if isinstance(smoothing, dict):
        for k in smoothing:
            if k not in SMOOTHING_KEYS:
                errors.append(
                    f"{prefix}.smoothing.{k}: unknown (valid: {sorted(SMOOTHING_KEYS)})"
                )
    return errors


def _raise_schema_errors(errors):
    if errors:
        raise ConfigError("Config schema violations:\n  " + "\n  ".join(errors))


def _validate_global_values(global_cfg):
    """Validate the values of the global section (pass 2)."""
    tr_val = global_cfg.get("tr")
    if tr_val is None:
        raise ConfigError("global.tr is required. Set it to the repetition time (seconds) for all scans.")
    if _finite_number(tr_val, "global.tr") <= 0:
        raise ConfigError(f"global.tr must be a positive number, got {tr_val}.")

    if global_cfg.get("num_cores") is not None:
        _positive_int(global_cfg["num_cores"], "global.num_cores")

    fda = global_cfg.get("force_diff_atlas")
    if fda is not None and not isinstance(fda, bool):
        raise ConfigError(f"global.force_diff_atlas must be true or false, got {fda!r}.")

    tpl = global_cfg.get("template_path")
    if tpl is not None:
        if not isinstance(tpl, str) or not tpl:
            raise ConfigError(f"global.template_path must be a file path string, got {tpl!r}.")
        if not os.path.isfile(tpl):
            raise InputError(f"global.template_path file does not exist: '{tpl}'.")

    _check_derivatives_dirs(global_cfg.get("derivatives_dirs"), "global.derivatives_dirs")


def _validate_block_values(idx, block, global_cfg, logger):
    """Validate the values of one analysis block (pass 2, fail-fast)."""
    label = block.get("name", f"analyses[{idx}]")
    atype = block["type"]

    _check_derivatives_dirs(block.get("derivatives_dirs"), f"[{label}] derivatives_dirs")
    discovery_active = (
        global_cfg.get("derivatives_dirs") is not None
        or block.get("derivatives_dirs") is not None
    )

    _check_required_block_keys(block, atype, label, discovery_active, logger)
    _check_container_types(block, atype, label)
    _check_bool_fields(block, atype, label)

    paths = block.get("paths", {})
    if paths is None and discovery_active:
        paths = {}
    if not isinstance(paths, dict):
        raise ConfigError(f"[{label}] 'paths' must be a dict.")
    _validate_paths(paths, atype, label, discovery_active, logger)

    ave = block.get("average_type")
    if ave is not None and ave not in VALID_AVE_TYPES:
        raise ConfigError(
            f"[{label}] average_type must be one of {sorted(VALID_AVE_TYPES)}, got '{ave}'."
        )

    rzh = block.get("roi_zero_handling")
    if rzh is not None and rzh not in VALID_ROI_ZERO_HANDLING:
        raise ConfigError(
            f"[{label}] roi_zero_handling must be one of "
            f"{sorted(VALID_ROI_ZERO_HANDLING)}, got '{rzh}'."
        )

    fd = block.get("fd_threshold")
    if fd is not None:
        if _finite_number(fd, f"[{label}] fd_threshold") <= 0:
            raise ConfigError(f"[{label}] fd_threshold must be a positive number, got {fd}.")

    _check_token(block.get("out_file_pre"), f"[{label}] out_file_pre")
    _validate_condition_labels(block, atype, label)

    if atype in ("task_act", "task_conn"):
        _validate_hrf(block, atype, label, logger)

    if atype == "rest_conn":
        _validate_rest_params(block, label, logger)

    _validate_contrasts(block, atype, label, logger)
    _validate_extraction(block, atype, label, logger)
    _validate_connectivity(block, atype, label, logger)
    _validate_smoothing(block, label, logger)

    rl = block.get("run_lengths")
    if rl is not None:
        if not isinstance(rl, list) or not rl:
            raise ConfigError(f"[{label}] run_lengths must be a non-empty list of positive integers.")
        for v in rl:
            if not isinstance(v, int) or v <= 0:
                raise ConfigError(
                    f"[{label}] run_lengths entries must be positive integers, got {v!r}."
                )

    rlb = block.get("run_labels")
    if rlb is not None:
        if not isinstance(rlb, list) or not rlb:
            raise ConfigError(f"[{label}] run_labels must be a non-empty list of non-negative integers.")
        for v in rlb:
            if not isinstance(v, int) or v < 0:
                raise ConfigError(
                    f"[{label}] run_labels entries must be non-negative integers, got {v!r}."
                )
        if len(set(rlb)) != len(rlb):
            raise ConfigError(f"[{label}] run_labels contains duplicates: {rlb}.")

    out_dir = block.get("out_dir")
    if not isinstance(out_dir, str) or not out_dir:
        raise ConfigError(f"[{label}] out_dir must be a directory path string, got {out_dir!r}.")
    if not os.path.isdir(out_dir):
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError as e:
            raise ConfigError(f"[{label}] Cannot create out_dir '{out_dir}': {e}")


def validate_config(raw_config: dict, logger: logging.Logger | None = None) -> dict:
    """Validate the structure and values of a raw config dict.

    Pass 1 (aggregate): scan for unknown keys, legacy keys, GLOBAL_ONLY_KEYS
    in blocks and non-mapping blocks. All violations are collected into a
    single ConfigError.

    Pass 2 (fail-fast): validate types, ranges, file existence, and logic,
    first for the global section, then for each block in order.

    Cross-block output collisions are checked after resolution (see
    load_and_validate).

    Parameters
    ----------
    raw_config : dict
    logger : logging.Logger, optional

    Returns
    -------
    dict
        Validated config with 'global' key guaranteed present.

    Raises
    ------
    ConfigError
        For structural errors, unknown keys, type/enum violations, missing
        required keys, or logic errors.
    InputError
        For user-specified file paths that do not exist on the filesystem.
    """
    errors, global_cfg = _global_schema_errors(raw_config)
    for idx, block in enumerate(raw_config["analyses"]):
        errors.extend(_schema_pass1_block(idx, block))
    _raise_schema_errors(errors)

    _validate_global_values(global_cfg)
    for idx, block in enumerate(raw_config["analyses"]):
        _validate_block_values(idx, block, global_cfg, logger)

    raw_config["global"] = global_cfg
    return raw_config


# ---------------------------------------------------------------------------
# Pass 2 validation helpers
# ---------------------------------------------------------------------------

def _check_required_block_keys(block, atype, label, discovery_active, logger):
    """Check required top-level keys for a block; a key set to null counts as missing,
    except boolean keys (null means the default) and bandpass (validated by
    _validate_rest_params)."""
    required = {
        "task_act":  {"out_dir", "out_file_pre", "cond_labels",
                      "average_type", "hrf_model", "include_motion_derivs", "fd_threshold"},
        "task_conn": {"out_dir", "out_file_pre", "cond_beta_labels",
                      "average_type", "hrf_model", "include_motion_derivs", "fd_threshold"},
        "rest_conn": {"out_dir", "out_file_pre",
                      "average_type", "bandpass", "motion_deriv_degree", "fd_threshold"},
    }
    check = required[atype]
    if not discovery_active:
        check = check | {"paths"}
    presence_only = set(BOOL_FIELDS[atype]) | {"bandpass"}
    for key in sorted(check):
        missing = key not in block if key in presence_only else block.get(key) is None
        if missing:
            raise ConfigError(f"[{label}] Missing required key '{key}' for type '{atype}'.")


def _check_container_types(block, atype, label):
    """Raise ConfigError when a nested section is present but is not a mapping."""
    for key in ("extraction", "connectivity", "smoothing"):
        value = block.get(key)
        if value is not None and not isinstance(value, dict):
            raise ConfigError(f"[{label}] {key} must be a mapping, got {type(value).__name__}.")
    if atype == "task_act":
        contrasts = block.get("contrasts")
        if contrasts is not None and not isinstance(contrasts, dict):
            raise ConfigError(f"[{label}] contrasts must be a mapping {{functions, labels}}.")
    if atype == "task_conn":
        conn_contrasts = (block.get("connectivity") or {}).get("contrasts")
        if conn_contrasts is not None and not isinstance(conn_contrasts, dict):
            raise ConfigError(
                f"[{label}] connectivity.contrasts must be a mapping {{functions, labels}}."
            )


def _check_bool_fields(block, atype, label):
    """Raise ConfigError when a boolean key holds a non-boolean, non-null value."""
    for key in BOOL_FIELDS[atype]:
        value = block.get(key)
        if value is not None and not isinstance(value, bool):
            raise ConfigError(f"[{label}] {key} must be true or false, got {value!r}.")
    for container, keys in NESTED_BOOL_FIELDS.items():
        sub = block.get(container)
        if not isinstance(sub, dict):
            continue
        for key in keys:
            value = sub.get(key)
            if value is not None and not isinstance(value, bool):
                raise ConfigError(
                    f"[{label}] {container}.{key} must be true or false, got {value!r}."
                )


def _validate_condition_labels(block, atype, label):
    """Require condition label lists of unique, file-name-safe strings."""
    key = {"task_act": "cond_labels", "task_conn": "cond_beta_labels"}.get(atype)
    if key is None or block.get(key) is None:
        return
    labels = block[key]
    if not isinstance(labels, list) or not labels:
        raise ConfigError(f"[{label}] {key} must be a non-empty list of condition names.")
    bad = [lbl for lbl in labels if not isinstance(lbl, str) or not FILENAME_TOKEN_RE.match(lbl)]
    if bad:
        raise ConfigError(
            f"[{label}] {key} entries must be strings of letters, digits, '.', '_' or '-' "
            f"starting with a letter or digit; invalid: {bad}. Quote numeric condition "
            "codes (e.g. \"1\")."
        )
    dups = sorted({lbl for lbl in labels if labels.count(lbl) > 1})
    if dups:
        raise ConfigError(f"[{label}] {key} contains duplicates: {dups}.")


def _validate_paths(paths, atype, label, discovery_active, logger):
    """Validate path types and file existence for explicitly provided paths."""
    if atype in ("task_act", "task_conn"):
        singular = ("scan_path", "task_timing_path", "motion_path", "CSF_path", "WM_path")
        plural = ("scan_paths", "task_timing_paths", "motion_paths", "CSF_paths", "WM_paths")
    else:
        singular = ()
        plural = ("scan_paths", "motion_paths", "CSF_paths", "WM_paths", "GS_paths")

    for pkey in singular:
        value = paths.get(pkey)
        if value is None:
            continue
        if not isinstance(value, str) or not value:
            raise ConfigError(f"[{label}] paths.{pkey} must be a file path string, got {value!r}.")
        if not os.path.isfile(value):
            raise InputError(f"[{label}] File does not exist: paths.{pkey} = '{value}'.")

    for pkey in plural:
        value = paths.get(pkey)
        if value is None:
            continue
        if not isinstance(value, list) or len(value) == 0:
            raise ConfigError(f"[{label}] paths.{pkey} must be a non-empty list of file paths.")
        for fp in value:
            if not isinstance(fp, str) or not fp:
                raise ConfigError(
                    f"[{label}] paths.{pkey} entries must be file path strings, got {fp!r}."
                )
            if not os.path.isfile(fp):
                raise InputError(f"[{label}] File does not exist: paths.{pkey} entry '{fp}'.")


def _validate_hrf(block, atype, label, logger):
    """Validate HRF model and custom_hrf."""
    hrf = block.get("hrf_model")
    if hrf is not None:
        if hrf not in VALID_HRF_MODELS:
            raise ConfigError(
                f"[{label}] hrf_model must be one of {sorted(VALID_HRF_MODELS)}, got '{hrf}'."
            )
        if hrf == "custom":
            custom = block.get("custom_hrf")
            if not custom:
                raise ConfigError(
                    f"[{label}] custom_hrf string is required when hrf_model='custom'."
                )
            col_count = validate_custom_hrf(custom, logger)
            # task_conn with a custom HRF must produce exactly one basis column
            if atype == "task_conn" and col_count != 1:
                raise ConfigError(
                    f"[{label}] custom_hrf '{custom}' produces {col_count} column(s) "
                    "in the design matrix. task_conn (3dLSS) requires exactly 1 column "
                    "per trial. Use GAM, BLOCK, SPMG1, or TWOGAMpw instead."
                )
        # Married timing check for task_conn
        if atype == "task_conn":
            custom = block.get("custom_hrf")
            if needs_married_timing(hrf, custom):
                raise ConfigError(
                    f"[{label}] hrf_model '{hrf}' requires married timing (-stim_times_AM1) "
                    "which is incompatible with 3dLSS (-stim_times_IM). "
                    "Use GAM, SPMG1, or another non-married HRF for task_conn analyses."
                )


def _validate_rest_params(block, label, logger):
    """Validate rest_conn-specific parameters."""
    mdd = block.get("motion_deriv_degree")
    if mdd is not None:
        _positive_int(mdd, f"[{label}] motion_deriv_degree")

    bp = block.get("bandpass")
    if bp is None:
        raise ConfigError(f"[{label}] bandpass is required for rest_conn. Provide [low, high] Hz.")
    if bp is True or bp is False:
        raise ConfigError(f"[{label}] bandpass must be a [low, high] list for rest_conn, not true/false.")
    if not (isinstance(bp, list) and len(bp) == 2):
        raise ConfigError(f"[{label}] bandpass must be a list of 2 floats [low, high].")
    bp_low = _finite_number(bp[0], f"[{label}] bandpass low")
    bp_high = _finite_number(bp[1], f"[{label}] bandpass high")
    if bp_low < 0 or bp_high <= bp_low:
        raise ConfigError(f"[{label}] bandpass must satisfy 0 <= low < high. Got [{bp[0]}, {bp[1]}].")

    nfb = block.get("notch_filter_band")
    if nfb is not None:
        if not (isinstance(nfb, list) and len(nfb) == 2):
            raise ConfigError(
                f"[{label}] notch_filter_band must be a list of 2 floats [low, high] or null."
            )
        nfb_low = _finite_number(nfb[0], f"[{label}] notch_filter_band low")
        nfb_high = _finite_number(nfb[1], f"[{label}] notch_filter_band high")
        if nfb_low <= 0 or nfb_high <= 0 or nfb_low >= nfb_high:
            raise ConfigError(
                f"[{label}] notch_filter_band must satisfy 0 < low < high. "
                f"Got [{nfb[0]}, {nfb[1]}]."
            )


def _check_contrast_label_integrity(clabels, label):
    """Raise ConfigError if contrast labels repeat or collide after sanitization."""
    seen = set()
    dups = set()
    for lbl in clabels:
        if lbl in seen:
            dups.add(lbl)
        seen.add(lbl)
    if dups:
        raise ConfigError(
            f"[{label}] contrast labels must be unique; duplicated: {sorted(dups)}."
        )

    safe_to_labels = {}
    for lbl in clabels:
        safe = sanitize_filename_label(lbl)
        safe_to_labels.setdefault(safe, []).append(lbl)
    for safe, group in safe_to_labels.items():
        if len(group) > 1:
            raise ConfigError(
                f"[{label}] contrast labels {group} map to the same filename label "
                f"'{safe}' after sanitization; rename them."
            )


def _check_contrast_spec(contrasts, where, label):
    """Validate one {functions, labels} contrast mapping."""
    funcs = contrasts.get("functions")
    clabels = contrasts.get("labels")
    if funcs is None:
        if clabels is not None:
            raise ConfigError(
                f"[{label}] {where}.labels provided but {where}.functions is missing."
            )
        return
    if clabels is None:
        raise ConfigError(
            f"[{label}] {where}.functions provided but {where}.labels is missing."
        )
    for key, value in (("functions", funcs), ("labels", clabels)):
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise ConfigError(f"[{label}] {where}.{key} must be a list of strings.")
    if len(funcs) != len(clabels):
        raise ConfigError(
            f"[{label}] {where}.functions and {where}.labels must be the same length."
        )
    _check_contrast_label_integrity(clabels, label)


def _validate_contrasts(block, atype, label, logger):
    """Validate contrast definitions."""
    if atype == "task_act":
        contrasts = block.get("contrasts")
        if isinstance(contrasts, dict):
            _check_contrast_spec(contrasts, "contrasts", label)
    elif atype == "task_conn":
        tc_contrasts = (block.get("connectivity") or {}).get("contrasts")
        if isinstance(tc_contrasts, dict):
            _check_contrast_spec(tc_contrasts, "connectivity.contrasts", label)


def _validate_extraction(block, atype, label, logger):
    """Validate extraction configuration and its output prefix."""
    ext = block.get("extraction")
    if ext is None:
        return

    ext_pre = ext.get("extract_out_file_pre")
    if ext_pre is not None:
        _check_token(ext_pre, f"[{label}] extraction.extract_out_file_pre")

    if atype == "task_act":
        stat_buckets = ext.get("stat_buckets")
        if stat_buckets is not None:
            if not isinstance(stat_buckets, list) or not stat_buckets:
                raise ConfigError(f"[{label}] extraction.stat_buckets must be a non-empty list.")
            for sb in stat_buckets:
                if sb not in VALID_STAT_BUCKET_TYPES:
                    raise ConfigError(
                        f"[{label}] extraction.stat_buckets contains invalid type '{sb}'. "
                        f"Must be one of {sorted(VALID_STAT_BUCKET_TYPES)}."
                    )
        needs_prefix = [k for k, on in (
            ("stat_buckets", stat_buckets is not None),
            ("extract_resids", bool(ext.get("extract_resids"))),
            ("extract_raw_ptseries", bool(ext.get("extract_raw_ptseries"))),
        ) if on]
    elif atype == "task_conn":
        needs_prefix = [k for k in ("extract_pbseries", "extract_raw_ptseries") if ext.get(k)]
    else:
        needs_prefix = [k for k in ("extract_ptseries", "extract_raw_ptseries") if ext.get(k)]

    if needs_prefix and ext_pre is None:
        raise ConfigError(
            f"[{label}] extraction.extract_out_file_pre is required when "
            f"{', '.join(needs_prefix)} is set."
        )


def _validate_connectivity(block, atype, label, logger):
    """Validate connectivity configuration and its output prefix."""
    b_conn = block.get("connectivity") or {}
    conn_pre = b_conn.get("conn_out_file_pre")
    if conn_pre is not None:
        _check_token(conn_pre, f"[{label}] connectivity.conn_out_file_pre")
    b_calc = b_conn.get("calc_conn")
    if b_calc is not None:
        if b_calc not in VALID_CONN_TYPES:
            raise ConfigError(
                f"[{label}] connectivity.calc_conn must be one of {sorted(VALID_CONN_TYPES)}, "
                f"got '{b_calc}'."
            )
        if b_calc == "seed_to_voxel" and b_conn.get("pcorr"):
            raise ConfigError(
                f"[{label}] pcorr is not supported for seed_to_voxel connectivity. "
                "Partial correlation is available only with calc_conn='parcellated'."
            )
        if conn_pre is None:
            raise ConfigError(
                f"[{label}] connectivity.conn_out_file_pre is required when calc_conn is set."
            )
    elif atype == "task_conn":
        conn_contrasts = b_conn.get("contrasts")
        if isinstance(conn_contrasts, dict) and conn_contrasts.get("functions") is not None:
            raise ConfigError(
                f"[{label}] connectivity.contrasts requires connectivity.calc_conn; "
                "set calc_conn or remove the contrasts."
            )


def _validate_smoothing(block, label, logger):
    """Validate smoothing configuration."""
    sm = block.get("smoothing")
    if sm is None:
        return
    if not isinstance(sm, dict):
        raise ConfigError(f"[{label}] smoothing must be a dict {{enabled: bool, fwhm: float}}.")

    enabled = sm.get("enabled")
    if enabled is not None:
        if not isinstance(enabled, bool):
            raise ConfigError(f"[{label}] smoothing.enabled must be a boolean.")

    if enabled:
        fwhm = sm.get("fwhm")
        if fwhm is None:
            raise ConfigError(f"[{label}] smoothing.fwhm is required when smoothing.enabled is true.")
        if isinstance(fwhm, bool):
            raise ConfigError(f"[{label}] smoothing.fwhm must be a number, not a boolean.")
        if not isinstance(fwhm, (int, float)):
            raise ConfigError(f"[{label}] smoothing.fwhm must be a number (int or float), got {type(fwhm).__name__}.")
        if not math.isfinite(fwhm):
            raise ConfigError(f"[{label}] smoothing.fwhm must be finite, got {fwhm!r}.")
        if fwhm <= 0:
            raise ConfigError(f"[{label}] smoothing.fwhm must be > 0, got {fwhm}.")
        # At most two decimal places (relies on shortest round-trip repr)
        d = Decimal(repr(float(fwhm)))
        exponent = d.as_tuple().exponent
        if exponent < -2:
            raise ConfigError(
                f"[{label}] smoothing.fwhm {fwhm!r}: at most two decimal places allowed "
                f"(e.g. 6, 4.5, 2.25)."
            )


# ---------------------------------------------------------------------------
# Stage 3: resolve_config
# ---------------------------------------------------------------------------

def resolve_config(
    validated_block: dict,
    global_cfg: dict,
    logger: logging.Logger | None = None,
) -> ResolvedConfig:
    """Merge global defaults into a validated analysis block and build a ResolvedConfig.

    BIDS discovery mode is active when derivatives_dirs (block or global) and
    subject are both set; discovered per-run slots are aligned to the
    analysis run labels. Required inputs are enforced after explicit paths
    and discovery are merged.

    Parameters
    ----------
    validated_block : dict
    global_cfg : dict
    logger : logging.Logger, optional

    Returns
    -------
    ResolvedConfig
    """
    atype = validated_block["type"]
    paths = validated_block.get("paths") or {}
    extraction = validated_block.get("extraction", None)
    connectivity = validated_block.get("connectivity", {}) or {}
    contrasts = validated_block.get("contrasts", None)
    smoothing = validated_block.get("smoothing", {}) or {}

    # Global-sourced fields
    num_cores_raw = global_cfg.get("num_cores")
    num_cores = int(num_cores_raw) if num_cores_raw is not None else 1
    template_path = global_cfg.get("template_path", None)
    force_diff_atlas = bool(global_cfg.get("force_diff_atlas", False))
    tr = float(global_cfg["tr"])

    derivatives_dirs = validated_block.get("derivatives_dirs", global_cfg.get("derivatives_dirs", None))

    # Smoothing
    sm_enabled = bool(smoothing.get("enabled", False))
    sm_fwhm = float(smoothing["fwhm"]) if sm_enabled and smoothing.get("fwhm") is not None else None

    # Absolute paths helper
    def _abspath(p):
        return os.path.abspath(p) if p is not None else None

    def _abspath_list(lst):
        if lst is None:
            return None
        return [os.path.abspath(p) for p in lst]

    # Build base config
    cfg = ResolvedConfig(
        schema_version=SCHEMA_VERSION,
        analysis_type=atype,
        analysis_name=validated_block.get("name", None),
        out_dir=os.path.abspath(validated_block.get("out_dir", "")),
        out_file_pre=validated_block.get("out_file_pre", ""),
        tr=tr,
        fd_threshold=float(validated_block.get("fd_threshold", 0.0)),
        average_type=validated_block.get("average_type", ""),
        num_cores=num_cores,
        remove_previous=bool(validated_block.get("remove_previous", False)),
        censor_prev_tr=bool(validated_block.get("censor_prev_tr", False)),
        template_path=_abspath(template_path),
        force_diff_atlas=force_diff_atlas,
        scale_to_psc=validated_block.get("scale_to_psc") is not False,
        derivatives_dirs=_abspath_list(derivatives_dirs),
        smoothing_enabled=sm_enabled,
        smoothing_fwhm=sm_fwhm,
        roi_zero_handling=validated_block.get("roi_zero_handling") or "exclude",
    )
    label = cfg.analysis_name or atype

    # Type-specific population
    if atype == "task_act":
        cfg.scan_path = _abspath(paths.get("scan_path"))
        cfg.scan_paths = _abspath_list(paths.get("scan_paths"))
        cfg.task_timing_path = _abspath(paths.get("task_timing_path"))
        cfg.task_timing_paths = _abspath_list(paths.get("task_timing_paths"))
        cfg.motion_path = _abspath(paths.get("motion_path"))
        cfg.motion_paths = _abspath_list(paths.get("motion_paths"))
        cfg.cond_labels = validated_block.get("cond_labels")
        cfg.hrf_model = validated_block.get("hrf_model")
        cfg.custom_hrf = validated_block.get("custom_hrf", None)
        cfg.CSF_path = _abspath(paths.get("CSF_path"))
        cfg.CSF_paths = _abspath_list(paths.get("CSF_paths"))
        cfg.WM_path = _abspath(paths.get("WM_path"))
        cfg.WM_paths = _abspath_list(paths.get("WM_paths"))
        cfg.include_motion_derivs = bool(validated_block.get("include_motion_derivs", False))
        cfg.use_tissue_derivs = bool(validated_block.get("use_tissue_derivs", False))
        cfg.run_lengths = validated_block.get("run_lengths")

        if contrasts is not None and isinstance(contrasts, dict):
            funcs = contrasts.get("functions")
            clabels = contrasts.get("labels")
            if funcs is not None and clabels is not None:
                cfg.contrast_functions = funcs
                cfg.contrast_labels = clabels

        if extraction is not None and isinstance(extraction, dict):
            cfg.stat_buckets = extraction.get("stat_buckets", None)
            cfg.extract_raw_ptseries = bool(extraction.get("extract_raw_ptseries", False))
            cfg.extract_out_file_pre = extraction.get("extract_out_file_pre")
            cfg.extract_resids = bool(extraction.get("extract_resids", False))

    elif atype == "task_conn":
        cfg.scan_path = _abspath(paths.get("scan_path"))
        cfg.scan_paths = _abspath_list(paths.get("scan_paths"))
        cfg.task_timing_path = _abspath(paths.get("task_timing_path"))
        cfg.task_timing_paths = _abspath_list(paths.get("task_timing_paths"))
        cfg.motion_path = _abspath(paths.get("motion_path"))
        cfg.motion_paths = _abspath_list(paths.get("motion_paths"))
        cfg.cond_beta_labels = validated_block.get("cond_beta_labels")
        cfg.hrf_model = validated_block.get("hrf_model")
        cfg.custom_hrf = validated_block.get("custom_hrf", None)
        cfg.CSF_path = _abspath(paths.get("CSF_path"))
        cfg.CSF_paths = _abspath_list(paths.get("CSF_paths"))
        cfg.WM_path = _abspath(paths.get("WM_path"))
        cfg.WM_paths = _abspath_list(paths.get("WM_paths"))
        cfg.include_motion_derivs = bool(validated_block.get("include_motion_derivs", False))
        cfg.use_tissue_derivs = bool(validated_block.get("use_tissue_derivs", False))
        cfg.run_lengths = validated_block.get("run_lengths")

        conn_contrasts = connectivity.get("contrasts", None)
        if conn_contrasts is not None and isinstance(conn_contrasts, dict):
            funcs = conn_contrasts.get("functions")
            clabels = conn_contrasts.get("labels")
            if funcs is not None and clabels is not None:
                cfg.contrast_functions = funcs
                cfg.contrast_labels = clabels

        if extraction is not None and isinstance(extraction, dict):
            cfg.extract_pbseries = bool(extraction.get("extract_pbseries", False))
            cfg.extract_raw_ptseries = bool(extraction.get("extract_raw_ptseries", False))
            cfg.extract_out_file_pre = extraction.get("extract_out_file_pre")

        cfg.calc_conn = connectivity.get("calc_conn", None)
        cfg.conn_out_file_pre = connectivity.get("conn_out_file_pre", None)
        val = connectivity.get("pcorr")
        cfg.pcorr = bool(val) if val is not None else False
        val = connectivity.get("fishZ")
        cfg.fishZ = bool(val) if val is not None else False

    elif atype == "rest_conn":
        cfg.scan_paths = _abspath_list(paths.get("scan_paths"))
        cfg.motion_paths = _abspath_list(paths.get("motion_paths"))
        cfg.CSF_paths = _abspath_list(paths.get("CSF_paths"))
        cfg.WM_paths = _abspath_list(paths.get("WM_paths"))
        cfg.GS_paths = _abspath_list(paths.get("GS_paths", None))
        cfg.notch_filter_band = validated_block.get("notch_filter_band", None)
        cfg.bandpass = validated_block.get("bandpass")
        cfg.motion_deriv_degree = int(validated_block.get("motion_deriv_degree", 1))
        cfg.use_tissue_derivs = bool(validated_block.get("use_tissue_derivs", False))
        cfg.use_sequenced_bandpass = bool(validated_block.get("use_sequenced_bandpass", False))
        val = validated_block.get("keep_run_res_dtseries")
        cfg.keep_run_res_dtseries = bool(val) if val is not None else True

        if extraction is not None and isinstance(extraction, dict):
            cfg.extract_ptseries = bool(extraction.get("extract_ptseries", False))
            cfg.extract_raw_ptseries = bool(extraction.get("extract_raw_ptseries", False))
            cfg.extract_out_file_pre = extraction.get("extract_out_file_pre")

        cfg.calc_conn = connectivity.get("calc_conn", None)
        cfg.conn_out_file_pre = connectivity.get("conn_out_file_pre", None)
        val = connectivity.get("pcorr")
        cfg.pcorr = bool(val) if val is not None else False
        val = connectivity.get("fishZ")
        cfg.fishZ = bool(val) if val is not None else False

    # ---- BIDS discovery merge ----
    discovery_mode = derivatives_dirs is not None and validated_block.get("subject") is not None
    discovered = None
    filled = set()
    if derivatives_dirs is not None:
        if discovery_mode:
            _check_discovery_entities(validated_block, label)
            discovered = discover_inputs(
                derivatives_dirs=derivatives_dirs,
                subject=validated_block.get("subject"),
                session=validated_block.get("session"),
                task=validated_block.get("task"),
                analysis_type=atype,
                logger=logger,
            )

            # Merge slot by slot (explicit wins)
            if atype in ("task_act", "task_conn"):
                slots = [("scan_path", "scan_paths"), ("motion_path", "motion_paths"),
                         ("task_timing_path", "task_timing_paths"),
                         ("CSF_path", "CSF_paths"), ("WM_path", "WM_paths")]
            else:
                slots = [(None, "scan_paths"), (None, "motion_paths"), (None, "CSF_paths"),
                         (None, "WM_paths"), (None, "GS_paths")]
            for singular, plural in slots:
                explicit = getattr(cfg, plural) is not None or (
                    singular is not None and getattr(cfg, singular) is not None
                )
                found = getattr(discovered, plural)
                if not explicit and found is not None:
                    setattr(cfg, plural, _abspath_list(found))
                    filled.add(plural)
        elif logger is not None:
            logger.warning(
                "[%s] derivatives_dirs is set but no 'subject' key found; BIDS discovery skipped.",
                label,
            )

    # ---- Run labels, discovery alignment, mode checks, required inputs ----
    _resolve_run_labels(cfg, validated_block, atype, logger)
    _align_discovered_slots(cfg, discovered, filled, label)
    if atype in ("task_act", "task_conn"):
        _resolve_task_mode_checks(cfg, validated_block, logger)
    _check_required_slots(cfg, discovery_mode, derivatives_dirs, label)

    # ---- Contrasts (parsed here so validation and --dry-run catch errors) ----
    if atype == "task_act" and cfg.contrast_functions:
        valid_contrast_functions(cfg.contrast_functions, cfg.contrast_labels, cfg.cond_labels)
    if atype == "task_conn" and cfg.calc_conn is not None and cfg.contrast_functions:
        valid_contrast_functions(cfg.contrast_functions, cfg.contrast_labels, cfg.cond_beta_labels)

    # ---- Extraction requires template_path ----
    _check_extraction_template(cfg, validated_block, logger)

    # ---- Connectivity requires template_path ----
    if cfg.calc_conn is not None and cfg.template_path is None:
        raise ConfigError(
            f"[{label}] connectivity.calc_conn requires global.template_path."
        )

    return cfg


def _check_discovery_entities(block, label):
    """BIDS discovery mode: subject, session and task must be strings; task is required."""
    for key in ("subject", "session", "task"):
        value = block.get(key)
        if value is None:
            continue
        if not isinstance(value, str) or not value:
            raise ConfigError(
                f"[{label}] {key} must be a string in BIDS discovery mode, got {value!r}; "
                f"quote it in the YAML (e.g. {key}: \"{value}\")."
            )
    if block.get("task") is None:
        raise ConfigError(
            f"[{label}] BIDS discovery mode (derivatives_dirs and subject set) requires 'task'."
        )


def _align_discovered_slots(cfg, discovered, filled, label):
    """Reorder discovered per-run slots to cfg.run_labels; raise InputError on run mismatch."""
    if discovered is None or not filled or cfg.run_labels is None:
        return
    if cfg.analysis_type in ("task_act", "task_conn") and cfg.scan_path is not None:
        return  # Mode B: singular/plural conflicts are reported by the mode checks
    target = list(cfg.run_labels)
    for slot in sorted(filled):
        files = getattr(cfg, slot)
        labels = discovered.run_labels.get(slot, [])
        if labels == [None]:
            if len(target) == 1:
                continue
            raise InputError(
                f"[{label}] Discovered {slot} has a single file without a run-N entity, "
                f"but the analysis has runs {target}.",
                context={"slot": slot, "runs": target},
            )
        if set(labels) != set(target):
            missing = sorted(set(target) - set(labels))
            extra = sorted(set(labels) - set(target))
            raise InputError(
                f"[{label}] Discovered {slot} in '{discovered.source_dirs.get(slot)}' does not "
                f"match the analysis runs {target}: missing runs {missing}, extra runs {extra}.",
                context={"slot": slot, "missing_runs": missing, "extra_runs": extra},
            )
        by_label = dict(zip(labels, files))
        setattr(cfg, slot, [by_label[lbl] for lbl in target])


def _check_required_slots(cfg, discovery_mode, derivatives_dirs, label):
    """Raise when a required input is unresolved after explicit paths and discovery."""
    if cfg.analysis_type in ("task_act", "task_conn"):
        if cfg.scan_path is not None:
            required = ("task_timing_path", "motion_path")
        else:
            required = ("scan_paths", "task_timing_paths", "motion_paths")
    else:
        required = ("scan_paths", "motion_paths", "CSF_paths", "WM_paths")
    missing = [slot for slot in required if getattr(cfg, slot) is None]
    if not missing and cfg.run_labels is None:
        missing = ["run_labels"]
    if not missing:
        return
    if discovery_mode:
        raise InputError(
            f"[{label}] Required input(s) {missing} not resolved from explicit paths or "
            f"BIDS discovery in {derivatives_dirs}.",
            context={"missing_slots": missing},
        )
    raise ConfigError(
        f"[{label}] Required input(s) {missing} are not set. Provide them under paths, "
        "or use BIDS discovery (derivatives_dirs, subject and task).",
        context={"missing_slots": missing},
    )


def _resolve_task_mode_checks(cfg, block, logger):
    """Enforce Mode A / Mode B mutual exclusivity for task analyses."""
    label = cfg.analysis_name or cfg.analysis_type

    # Singular/plural conflict per slot
    for singular, plural in [
        ("scan_path", "scan_paths"),
        ("task_timing_path", "task_timing_paths"),
        ("motion_path", "motion_paths"),
        ("CSF_path", "CSF_paths"),
        ("WM_path", "WM_paths"),
    ]:
        s_val = getattr(cfg, singular)
        p_val = getattr(cfg, plural)
        if s_val is not None and p_val is not None:
            raise ConfigError(
                f"[{label}] Both {singular} and {plural} are set. "
                f"Use singular paths with run_lengths (Mode B) or "
                f"per-run lists (Mode A), not both."
            )

    # run_lengths with any plural field
    if cfg.run_lengths is not None:
        for plural in ("scan_paths", "task_timing_paths", "motion_paths", "CSF_paths", "WM_paths"):
            if getattr(cfg, plural) is not None:
                raise ConfigError(
                    f"[{label}] run_lengths cannot be used with {plural}. "
                    "Use singular paths with run_lengths (Mode B) or "
                    "per-run lists without run_lengths (Mode A)."
                )

    # Mode B: scan_path + run_lengths + run_labels required
    if cfg.scan_path is not None:
        if cfg.run_lengths is None:
            raise ConfigError(
                f"[{label}] Mode B (scan_path): run_lengths is required."
            )
        rlb = block.get("run_labels")
        if rlb is None:
            raise ConfigError(
                f"[{label}] Mode B (scan_path): run_labels is required."
            )
        if len(rlb) != len(cfg.run_lengths):
            raise ConfigError(
                f"[{label}] run_labels length ({len(rlb)}) must equal "
                f"run_lengths length ({len(cfg.run_lengths)})."
            )

    # Mode A: per-run lists must be same length as scan_paths; tissue must be per-run
    if cfg.scan_paths is not None:
        n = len(cfg.scan_paths)
        for plural in ("task_timing_paths", "motion_paths", "CSF_paths", "WM_paths"):
            p_val = getattr(cfg, plural)
            if p_val is not None and len(p_val) != n:
                raise ConfigError(
                    f"[{label}] {plural} has {len(p_val)} entries but "
                    f"scan_paths has {n}."
                )
        if cfg.run_lengths is not None:
            raise ConfigError(
                f"[{label}] run_lengths is not allowed with scan_paths (Mode A)."
            )
        if cfg.CSF_path is not None or cfg.WM_path is not None:
            raise ConfigError(
                f"[{label}] Mode A (scan_paths) uses per-run tissue lists; replace "
                "CSF_path/WM_path with CSF_paths/WM_paths (one entry per run)."
            )


def _resolve_run_labels(cfg, block, atype, logger):
    """Resolve run_labels from explicit config, discovery or BIDS entities."""
    label = cfg.analysis_name or atype
    explicit = block.get("run_labels")

    if atype in ("task_act", "task_conn"):
        if cfg.scan_path is not None:
            # Mode B: labels from config only
            cfg.run_labels = list(explicit) if explicit else None
        else:
            # Mode A or not yet resolved
            if cfg.scan_paths is not None:
                n = len(cfg.scan_paths)
                if explicit is not None:
                    if len(explicit) != n:
                        raise ConfigError(
                            f"[{label}] run_labels length ({len(explicit)}) does not match "
                            f"scan_paths length ({n})."
                        )
                    cfg.run_labels = list(explicit)
                else:
                    # Try to infer from filenames
                    labels = _infer_labels_from_paths(cfg.scan_paths, label)
                    cfg.run_labels = labels
    elif atype == "rest_conn":
        if cfg.scan_paths is not None:
            n = len(cfg.scan_paths)
            if explicit is not None:
                if len(explicit) != n:
                    raise ConfigError(
                        f"[{label}] run_labels length ({len(explicit)}) does not match "
                        f"scan_paths length ({n})."
                    )
                cfg.run_labels = list(explicit)
            else:
                labels = _infer_labels_from_paths(cfg.scan_paths, label)
                cfg.run_labels = labels


def _infer_labels_from_paths(paths, label):
    """Infer integer run labels from BIDS run entities in file basenames."""
    labels = []
    for p in paths:
        bn = os.path.basename(p)
        m = RUN_RE.search(bn)
        if m:
            labels.append(int(m.group(2)))
        else:
            raise ConfigError(
                f"[{label}] run_labels not provided and file '{bn}' has no "
                "run-N entity. Provide explicit run_labels."
            )
    if len(set(labels)) != len(labels):
        raise ConfigError(
            f"[{label}] Inferred run_labels contain duplicates: {labels}."
        )
    return labels


def _check_extraction_template(cfg, block, logger):
    """Check that extraction features requiring a template have template_path set."""
    label = cfg.analysis_name or cfg.analysis_type
    needs_template = False
    if cfg.extract_raw_ptseries:
        needs_template = True
    if cfg.extract_resids:
        needs_template = True
    if cfg.extract_ptseries:
        needs_template = True
    if cfg.extract_pbseries:
        needs_template = True
    if cfg.stat_buckets is not None:
        needs_template = True
    if needs_template and cfg.template_path is None:
        raise ConfigError(
            f"[{label}] Extraction features require global.template_path to be set."
        )


def _cross_block_conflicts(resolved):
    """Return {block_index: message} for blocks sharing an out_dir and an output prefix.

    Parameters
    ----------
    resolved : list of (int, str, ResolvedConfig)
        (block index, label, resolved config) for every resolved block.
    """
    owners = {}
    for idx, label, cfg in resolved:
        out = os.path.normpath(cfg.out_dir)
        prefixes = {cfg.out_file_pre, cfg.extract_out_file_pre, cfg.conn_out_file_pre} - {None}
        for p in prefixes:
            owners.setdefault((out, p), []).append((idx, label))
    conflicts = {}
    for (out, p), blocks in sorted(owners.items()):
        if len(blocks) > 1:
            names_ = ", ".join(f"[{lbl}]" for _, lbl in blocks)
            msg = (f"Blocks {names_} share out_dir '{out}' and output prefix '{p}'; "
                   "output files would collide.")
            for idx, _ in blocks:
                conflicts.setdefault(idx, msg)
    return conflicts


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _apply_overrides(raw, overrides):
    if overrides:
        for block in raw.get("analyses") or []:
            if isinstance(block, dict):
                block.update(overrides)


def load_and_validate(
    config_path: str,
    logger: logging.Logger | None = None,
    **overrides,
) -> list[ResolvedConfig]:
    """Load, validate, and resolve a YAML config into ResolvedConfig objects.

    Overrides are merged into each raw analysis block BEFORE validation,
    allowing the orchestrator to inject subject-specific values at dispatch
    time. The first invalid block raises; see load_and_validate_blocks for
    per-block results.

    Parameters
    ----------
    config_path : str
    logger : logging.Logger, optional
    **overrides
        Keyword arguments merged into each raw analysis block before validation.

    Returns
    -------
    list of ResolvedConfig
        One per analysis block, in config file order.
    """
    raw = load_config(config_path)
    _apply_overrides(raw, overrides)

    validated = validate_config(raw, logger)

    global_cfg = validated["global"]
    results: list[ResolvedConfig] = []

    for block in validated["analyses"]:
        cfg = resolve_config(block, global_cfg, logger)
        results.append(cfg)

    conflicts = _cross_block_conflicts(
        [(i, c.analysis_name or f"analyses[{i}]", c) for i, c in enumerate(results)]
    )
    if conflicts:
        raise ConfigError(conflicts[min(conflicts)])

    return results


@dataclasses.dataclass
class BlockResolution:
    """Validation and resolution outcome of one analysis block.

    Exactly one of ``config`` and ``error`` is set. ``raw_out_dir`` and
    ``raw_out_file_pre`` are the block's values as written in the config
    (used to record a failure in the block's qc_summary).
    """

    index: int
    name: str | None
    analysis_type: str | None
    config: ResolvedConfig | None
    error: Exception | None
    raw_out_dir: str | None
    raw_out_file_pre: str | None


def load_and_validate_blocks(
    config_path: str,
    logger: logging.Logger | None = None,
    **overrides,
) -> list[BlockResolution]:
    """Load a YAML config and validate and resolve each analysis block independently.

    Global problems (unreadable YAML, top-level or global schema, global
    values) raise. Each block's own errors are recorded on its
    BlockResolution; blocks that share an out_dir and an output prefix all
    receive a ConfigError.

    Parameters
    ----------
    config_path : str
    logger : logging.Logger, optional
    **overrides
        Keyword arguments merged into each raw analysis block before validation.

    Returns
    -------
    list of BlockResolution
        One per analysis block, in config file order.
    """
    raw = load_config(config_path)
    _apply_overrides(raw, overrides)

    errors, global_cfg = _global_schema_errors(raw)
    _raise_schema_errors(errors)
    _validate_global_values(global_cfg)

    results = []
    for idx, block in enumerate(raw["analyses"]):
        is_map = isinstance(block, dict)
        atype = block.get("type") if is_map else None
        res = BlockResolution(
            index=idx,
            name=block.get("name") if is_map else None,
            analysis_type=atype if atype in VALID_TYPES else None,
            config=None,
            error=None,
            raw_out_dir=block.get("out_dir") if is_map else None,
            raw_out_file_pre=block.get("out_file_pre") if is_map else None,
        )
        try:
            _raise_schema_errors(_schema_pass1_block(idx, block))
            _validate_block_values(idx, block, global_cfg, logger)
            res.config = resolve_config(block, global_cfg, logger)
        except Exception as exc:
            res.error = exc
        results.append(res)

    valid = [(r.index, r.name or f"analyses[{r.index}]", r.config)
             for r in results if r.config is not None]
    for idx, msg in _cross_block_conflicts(valid).items():
        results[idx].config = None
        results[idx].error = ConfigError(msg)

    return results
