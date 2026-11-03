#!/usr/bin/env python3
from __future__ import annotations

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
    Full pipeline: load YAML -> validate -> merge global defaults -> build
    ResolvedConfig objects. Returns a list of ResolvedConfig instances suitable
    for direct dispatch to each pipeline's run() function.

ResolvedConfig
    Typed dataclass with all pipeline-specific fields. schema_version='3.0.0'.
    Fields not applicable to an analysis_type are set to None or their default.

Config Schema Overview
----------------------
global:
    tr           : float (required) -- repetition time in seconds
    num_cores    : int | 'auto' -- CPU budget; 'auto' reads OMP_NUM_THREADS, then the cgroup limit
    template_path: str -- shared ROI template for all analyses
    force_diff_atlas: bool -- allow atlas space mismatches
    derivatives_dirs: list[str] -- BIDS derivatives directories (optional)

analyses:
    - name        : str (optional label)
      type        : 'task_act' | 'task_conn' | 'rest_conn'
      out_dir     : str
      out_file_pre: str
      paths       : dict of required/optional file paths (type-dependent)
      ... (type-specific keys; see docs/input_specification.md for full schema)

Validation enforces: required keys, file existence, enum ranges, bandpass
bounds, HRF model compatibility, contrast length parity, and unique
(out_dir, out_file_pre) pairs. Raises ConfigError for structural or logic
errors; raises InputError for missing user-specified files.
"""

import dataclasses
import logging
import math
import re
from pathlib import Path
from typing import NoReturn

import yaml

from .bids import discover_inputs
from .exceptions import ConfigError, InputError
from .fileutils import sanitize_filename_label
from .design import VALID_HRF_MODELS, valid_contrast_functions, validate_custom_hrf, needs_married_timing
from .runtime import available_cpus

VALID_TYPES = {"task_act", "task_conn", "rest_conn"}
VALID_STAT_BUCKET_TYPES = {"Coef", "Tstat", "Fstat", "R^2", "Zstat"}
VALID_AVE_TYPES = {"mean", "median"}
VALID_CONN_TYPES = {"seed_to_voxel", "parcellated"}
VALID_ROI_ZERO_HANDLING = ("exclude", "include")

# Boolean flag keys (null -> False when merging)
BOOL_KEYS = (
    "remove_previous",
    "include_motion_derivs",
    "use_tissue_derivs",
    "censor_prev_tr",
    "use_sequenced_bandpass",
)

# Keys that are valid only in the global section
GLOBAL_ONLY_KEYS = ("num_cores", "template_path", "force_diff_atlas", "tr")

# Closed schema: a key outside these sets is a ConfigError
_GLOBAL_KEYS = {*GLOBAL_ONLY_KEYS, "derivatives_dirs"}
_COMMON_BLOCK_KEYS = {
    "name", "type", "paths", "out_dir", "out_file_pre", "remove_previous", "average_type",
    "fd_threshold", "censor_prev_tr", "scale_to_psc", "derivatives_dirs", "roi_zero_handling",
    "smoothing", "subject", "session", "task", "use_tissue_derivs", "extraction",
}
_TASK_BLOCK_KEYS = {"hrf_model", "custom_hrf", "include_motion_derivs"}
_BLOCK_KEYS = {
    "task_act": _COMMON_BLOCK_KEYS | _TASK_BLOCK_KEYS | {"cond_labels", "contrasts"},
    "task_conn": _COMMON_BLOCK_KEYS | _TASK_BLOCK_KEYS | {"cond_beta_labels", "connectivity"},
    "rest_conn": _COMMON_BLOCK_KEYS | {"bandpass", "notch_filter_band", "motion_deriv_degree",
                                       "keep_run_res_dtseries", "use_sequenced_bandpass", "connectivity"},
}
_TASK_PATH_KEYS = {"scan_path", "task_timing_path", "motion_path", "run_lengths", "CSF_path", "WM_path"}
_PATH_KEYS = {
    "task_act": _TASK_PATH_KEYS,
    "task_conn": _TASK_PATH_KEYS,
    "rest_conn": {"scan_paths", "motion_paths", "CSF_paths", "WM_paths", "GS_paths"},
}
_EXTRACTION_KEYS = {
    "task_act": {"stat_buckets", "extract_out_file_pre", "extract_resids", "extract_raw_ptseries"},
    "task_conn": {"extract_pbseries", "extract_out_file_pre", "extract_raw_ptseries"},
    "rest_conn": {"extract_ptseries", "extract_out_file_pre", "extract_raw_ptseries"},
}
_CONNECTIVITY_KEYS = {
    "task_conn": {"calc_conn", "conn_out_file_pre", "pcorr", "fishZ", "contrasts"},
    "rest_conn": {"calc_conn", "conn_out_file_pre", "pcorr", "fishZ"},
}
_CONTRAST_KEYS = {"functions", "labels"}
_SMOOTHING_KEYS = {"enabled", "fwhm"}

# Prefixes and condition labels appear verbatim in output file names
_FILE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


# ---------------------------------------------------------------------------
# ResolvedConfig dataclass
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class ResolvedConfig:
    """Flat, typed configuration for one analysis block.

    All pipeline-specific Optional fields default to None or their zero-value.
    schema_version follows additive-growth policy: '3.0.0'.
    """

    # Schema and identity
    schema_version: str       # "3.0.0", additive-growth policy
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

    # Task-common (task_act + task_conn)
    scan_path: str | None = None
    task_timing_path: str | None = None
    motion_path: str | None = None
    run_lengths: list[int] | None = None
    roi_zero_handling: str = "exclude"
    smoothing_enabled: bool = False
    smoothing_fwhm: float | None = None
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

    # rest_conn specific
    scan_paths: list[str] | None = None
    motion_paths: list[str] | None = None
    CSF_paths: list[str] | None = None
    WM_paths: list[str] | None = None
    GS_paths: list[str] | None = None
    bandpass: list[float] | None = None
    notch_filter_band: list[float] | None = None
    motion_deriv_degree: int | None = None
    use_sequenced_bandpass: bool = False
    keep_run_res_dtseries: bool = True

    # rest_conn extraction
    extract_ptseries: bool = False


# ---------------------------------------------------------------------------
# Private error helpers
# ---------------------------------------------------------------------------

def _unknown_keys(section, allowed, where):
    """Describe a section's keys outside `allowed`, or its not being a mapping."""
    if section is None:
        return []
    if not isinstance(section, dict):
        return [f"{where} must be a mapping."]
    return [f"{where}.{key}: unknown key (valid: {sorted(allowed)})" for key in section if key not in allowed]


def _schema_violations(raw_config: dict) -> list[str]:
    """Every key in the config that the schema doesn't define, across all levels."""
    violations = _unknown_keys(raw_config, {"global", "analyses"}, "config")
    violations += _unknown_keys(raw_config.get("global"), _GLOBAL_KEYS, "global")
    analyses = raw_config.get("analyses")
    for idx, block in enumerate(analyses if isinstance(analyses, list) else []):
        if not isinstance(block, dict):
            violations.append(f"analyses[{idx}] must be a mapping.")
            continue
        where = str(block.get("name", f"analyses[{idx}]"))
        atype = block.get("type")
        if atype not in VALID_TYPES:
            continue  # reported by validate_config
        for key in block:
            if key in GLOBAL_ONLY_KEYS:
                violations.append(f"{where}.{key}: valid only in the global section.")
            elif key not in _BLOCK_KEYS[atype]:
                violations.append(f"{where}.{key}: unknown key for {atype} (valid: {sorted(_BLOCK_KEYS[atype])})")
        violations += _unknown_keys(block.get("paths"), _PATH_KEYS[atype], f"{where}.paths")
        violations += _unknown_keys(block.get("extraction"), _EXTRACTION_KEYS[atype], f"{where}.extraction")
        violations += _unknown_keys(block.get("smoothing"), _SMOOTHING_KEYS, f"{where}.smoothing")
        if atype == "task_act":
            violations += _unknown_keys(block.get("contrasts"), _CONTRAST_KEYS, f"{where}.contrasts")
        else:
            connectivity = block.get("connectivity")
            violations += _unknown_keys(connectivity, _CONNECTIVITY_KEYS[atype], f"{where}.connectivity")
            if atype == "task_conn" and isinstance(connectivity, dict):
                violations += _unknown_keys(connectivity.get("contrasts"), _CONTRAST_KEYS,
                                            f"{where}.connectivity.contrasts")
    return violations


def _check_bool(value, where, logger) -> None:
    """A boolean key accepts true, false or null (the default), and nothing else."""
    if value is not None and not isinstance(value, bool):
        _cfg_err(logger, "%s must be true, false or null, got %r.", where, value)


def _check_number(value, where, logger) -> float:
    """Return value as a float, refusing booleans, non-numbers, NaN and infinity."""
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        _cfg_err(logger, "%s must be a finite number, got %r.", where, value)
    return float(value)


def _check_file_token(value, where, logger) -> None:
    """Prefixes and labels end up in file names, so they must be safe there."""
    if not isinstance(value, str) or not _FILE_TOKEN.match(value):
        _cfg_err(logger, "%s must be a file-name-safe string (letters, digits, '.', '_', '-'; "
                         "starting with a letter or digit), got %r.", where, value)


def _check_labels(labels, where, logger) -> None:
    """Condition labels: a non-empty list of unique file-name-safe strings."""
    if not isinstance(labels, list) or not labels:
        _cfg_err(logger, "%s must be a non-empty list of strings.", where)
    for label in labels:
        _check_file_token(label, f"{where} entry", logger)
    if len(set(labels)) != len(labels):
        _cfg_err(logger, "%s must not repeat a label, got %s.", where, labels)


def _check_contrast_labels(labels, where, logger) -> None:
    """Contrast labels name output files, so they must stay distinct after sanitizing."""
    sanitized = [sanitize_filename_label(str(label)) for label in labels]
    if len(set(sanitized)) != len(sanitized):
        _cfg_err(logger, "%s must stay unique in file names, got %s (as %s).", where, labels, sanitized)


def _check_derivatives_dirs(value, where, logger) -> None:
    if value is None:
        return
    if not isinstance(value, list) or not value or not all(isinstance(d, str) and d for d in value):
        _cfg_err(logger, "%s must be a non-empty list of directory paths, got %r.", where, value)


def _check_path_value(value, where, logger) -> None:
    if not isinstance(value, str) or not value:
        _cfg_err(logger, "%s must be a non-empty path string, got %r.", where, value)


def _validate_smoothing(smoothing, label, logger) -> None:
    """Check a block's smoothing section: {enabled: bool, fwhm: float}."""
    if smoothing is None:
        return
    if not isinstance(smoothing, dict):
        _cfg_err(logger, "[%s] smoothing must be a mapping {enabled: bool, fwhm: number}.", label)
    enabled = smoothing.get("enabled", False)
    if not isinstance(enabled, bool):
        _cfg_err(logger, "[%s] smoothing.enabled must be a boolean.", label)
    if not enabled:
        return
    fwhm = smoothing.get("fwhm")
    valid_type = isinstance(fwhm, int | float) and not isinstance(fwhm, bool)
    if not valid_type or not math.isfinite(fwhm) or fwhm <= 0 or round(fwhm, 2) != fwhm:
        _cfg_err(logger, "[%s] smoothing.fwhm must be a finite number > 0 with at most two "
                         "decimal places when smoothing.enabled is true, got %r.", label, fwhm)


def _cfg_err(logger: logging.Logger | None, msg: str, *args) -> NoReturn:
    """Log at error level (if logger provided) then raise ConfigError."""
    if logger is not None:
        logger.error(msg, *args)
    raise ConfigError(msg % args if args else msg)


def _inp_err(logger: logging.Logger | None, msg: str, *args) -> NoReturn:
    """Log at error level (if logger provided) then raise InputError."""
    if logger is not None:
        logger.error(msg, *args)
    raise InputError(msg % args if args else msg)


# ---------------------------------------------------------------------------
# Stage 1: load_config
# ---------------------------------------------------------------------------

def load_config(config_path: str) -> dict:
    """Load a YAML config file and return the raw dict.

    Raises ConfigError on missing file or YAML parse failure.
    """
    if not Path(config_path).is_file():
        raise ConfigError(f"Config file not found: {config_path}")
    with open(config_path, "r") as f:
        try:
            raw = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"YAML parse error in {config_path}: {e}") from e
    if raw is None:
        raise ConfigError(f"Config file is empty: {config_path}")
    return raw


# ---------------------------------------------------------------------------
# Stage 2: validate_config
# ---------------------------------------------------------------------------

def validate_config(raw_config: dict, logger: logging.Logger | None = None) -> dict:
    """Validate the structure and values of a raw config dict.

    Parameters
    ----------
    raw_config:
        Raw dict from load_config().
    logger:
        Optional logger; errors are logged before raising if provided.

    Returns
    -------
    dict
        Validated config with 'global' key guaranteed present (defaults to {}).

    Raises
    ------
    ConfigError
        For structural errors, type/enum violations, missing required keys,
        bandpass/fd/HRF logic errors, contrast parity, duplicate output pairs,
        and out_dir creation failures.
    InputError
        For user-specified file paths that do not exist on the filesystem.
    """
    # Declarative required-key tables (local; not module-level constants)
    required_top: dict[str, set[str]] = {
        "task_act":  {"paths", "out_dir", "out_file_pre", "cond_labels",
                      "average_type", "hrf_model", "include_motion_derivs", "fd_threshold"},
        "task_conn": {"paths", "out_dir", "out_file_pre", "cond_beta_labels",
                      "average_type", "hrf_model", "include_motion_derivs", "fd_threshold"},
        "rest_conn": {"paths", "out_dir", "out_file_pre",
                      "average_type", "bandpass", "motion_deriv_degree", "fd_threshold"},
    }
    required_paths: dict[str, set[str]] = {
        "task_act":  {"scan_path", "task_timing_path", "motion_path"},
        "task_conn": {"scan_path", "task_timing_path", "motion_path"},
        "rest_conn": {"scan_paths", "motion_paths", "CSF_paths", "WM_paths"},
    }

    # -- Top-level structure and closed schema --
    if not isinstance(raw_config, dict):
        _cfg_err(logger, "The config must be a mapping with 'global' and 'analyses' keys.")
    violations = _schema_violations(raw_config)
    if violations:
        _cfg_err(logger, "%s", "Config has invalid keys:\n  " + "\n  ".join(violations))
    if "analyses" not in raw_config:
        _cfg_err(logger, "Config missing required top-level key 'analyses'.")
    if not isinstance(raw_config["analyses"], list) or len(raw_config["analyses"]) == 0:
        _cfg_err(logger, "'analyses' must be a non-empty list.")

    global_cfg = raw_config.get("global", {})
    if not isinstance(global_cfg, dict):
        _cfg_err(logger, "'global' must be a dict if provided.")

    # -- Validate global.tr (required for all analyses) --
    tr_val = global_cfg.get("tr")
    if tr_val is None:
        _cfg_err(logger, "global.tr is required. Set it to the repetition time (seconds) for all scans.")
    if _check_number(tr_val, "global.tr", logger) <= 0:
        _cfg_err(logger, "global.tr must be a positive number, got %s.", tr_val)
    _check_bool(global_cfg.get("force_diff_atlas"), "global.force_diff_atlas", logger)
    _check_derivatives_dirs(global_cfg.get("derivatives_dirs"), "global.derivatives_dirs", logger)

    # -- Validate global.num_cores (positive int or 'auto'; default 1) --
    nc_val = global_cfg.get("num_cores")
    if nc_val is not None and nc_val != "auto":
        if isinstance(nc_val, bool) or not isinstance(nc_val, int) or nc_val < 1:
            _cfg_err(logger, "global.num_cores must be a positive integer or 'auto', got %r.", nc_val)

    # -- Validate each analysis block --
    for idx, block in enumerate(raw_config["analyses"]):
        label = block.get("name", f"analyses[{idx}]")

        # type
        if "type" not in block:
            _cfg_err(logger, "[%s] Missing required key 'type'.", label)
        atype = block["type"]
        if atype not in VALID_TYPES:
            _cfg_err(logger, "[%s] Invalid type '%s'. Must be one of %s.", label, atype, VALID_TYPES)

        # BIDS discovery active if derivatives_dirs is set in global or block.
        # When active: (a) the 'paths' top-level key is optional; (b) required
        # path sub-keys within 'paths' may be absent (they will be discovered).
        discovery_active = (
            global_cfg.get("derivatives_dirs") is not None
            or block.get("derivatives_dirs") is not None
        )

        # Required top-level keys (declarative against required_top).
        # When discovery_active, 'paths' is optional (block may be path-free).
        check_required_top = required_top[atype]
        if discovery_active:
            check_required_top = check_required_top - {"paths"}
        for key in sorted(check_required_top):
            # null means missing, except for a boolean, where it means the default
            if key not in block or (block[key] is None and key not in BOOL_KEYS):
                _cfg_err(logger, "[%s] Missing required key '%s' for type '%s'.", label, key, atype)

        # -- Value types --
        for key in (*BOOL_KEYS, "scale_to_psc", "keep_run_res_dtseries"):
            _check_bool(block.get(key), f"[{label}] {key}", logger)
        _check_derivatives_dirs(block.get("derivatives_dirs"), f"[{label}] derivatives_dirs", logger)
        for key in ("subject", "session", "task"):
            if block.get(key) is not None and not isinstance(block[key], str):
                _cfg_err(logger, "[%s] %s must be a string (quote numeric labels), got %r.", label, key, block[key])
        _check_file_token(block["out_file_pre"], f"[{label}] out_file_pre", logger)
        if atype == "task_act":
            _check_labels(block["cond_labels"], f"[{label}] cond_labels", logger)
        elif atype == "task_conn":
            _check_labels(block["cond_beta_labels"], f"[{label}] cond_beta_labels", logger)

        # Required path sub-keys
        paths = block.get("paths") or {}
        if not isinstance(paths, dict):
            _cfg_err(logger, "[%s] 'paths' must be a dict.", label)
        if not discovery_active:
            for pkey in required_paths[atype]:
                if paths.get(pkey) is None:
                    _cfg_err(logger, "[%s] Missing required path key '%s' for type '%s'.", label, pkey, atype)

        # Validate file paths exist (only for paths that ARE explicitly provided)
        if atype in ("task_act", "task_conn"):
            for pkey in required_paths[atype]:
                if paths.get(pkey) is not None:
                    fpath = paths[pkey]
                    _check_path_value(fpath, f"[{label}] paths.{pkey}", logger)
                    if not Path(fpath).is_file():
                        _inp_err(logger, "[%s] File does not exist: paths.%s = '%s'.", label, pkey, fpath)
            # Optional run lengths of a concatenated scan (skip if null)
            run_lengths = paths.get("run_lengths")
            if run_lengths is not None and not (
                isinstance(run_lengths, list) and run_lengths
                and all(isinstance(n, int) and not isinstance(n, bool) and n > 0 for n in run_lengths)
            ):
                _cfg_err(logger, "[%s] paths.run_lengths must be a non-empty list of positive integers.", label)
            # Optional tissue regressor paths (skip if null)
            for opt_pkey in ("CSF_path", "WM_path"):
                if opt_pkey in paths and paths[opt_pkey] is not None:
                    _check_path_value(paths[opt_pkey], f"[{label}] paths.{opt_pkey}", logger)
                    if not Path(paths[opt_pkey]).is_file():
                        _inp_err(logger, "[%s] File does not exist: paths.%s = '%s'.",
                                 label, opt_pkey, paths[opt_pkey])
            # Warn if use_tissue_derivs but no tissue paths
            if block.get("use_tissue_derivs", False):
                csf_val = paths.get("CSF_path")
                wm_val = paths.get("WM_path")
                if csf_val is None and wm_val is None:
                    if logger is not None:
                        logger.warning(
                            "[%s] use_tissue_derivs is true but both CSF_path and WM_path are null "
                            "-- no tissue derivatives will be computed.", label)
        elif atype == "rest_conn":
            for pkey in required_paths[atype]:
                if paths.get(pkey) is None:
                    continue  # absent; will be discovered or caught in resolve_config
                plist = paths[pkey]
                if not isinstance(plist, list) or len(plist) == 0:
                    _cfg_err(logger, "[%s] paths.%s must be a non-empty list for rest_conn.", label, pkey)
                for fpath in plist:
                    _check_path_value(fpath, f"[{label}] paths.{pkey} entry", logger)
                    if not Path(fpath).is_file():
                        _inp_err(logger, "[%s] File does not exist: paths.%s entry '%s'.", label, pkey, fpath)

            # Optional GS_paths
            if "GS_paths" in paths and paths["GS_paths"] is not None:
                gs_list = paths["GS_paths"]
                if not isinstance(gs_list, list) or len(gs_list) == 0:
                    _cfg_err(logger, "[%s] paths.GS_paths must be a non-empty list for rest_conn.", label)
                for fpath in gs_list:
                    _check_path_value(fpath, f"[{label}] paths.GS_paths entry", logger)
                    if not Path(fpath).is_file():
                        _inp_err(logger, "[%s] File does not exist: paths.GS_paths entry '%s'.", label, fpath)

            # All explicitly-provided rest_conn path lists must be the same length.
            provided_required = {pkey for pkey in required_paths[atype] if paths.get(pkey) is not None}
            if provided_required:
                lengths = {pkey: len(paths[pkey]) for pkey in provided_required}
                if "GS_paths" in paths and paths["GS_paths"] is not None:
                    lengths["GS_paths"] = len(paths["GS_paths"])
                unique_lens = set(lengths.values())
                if len(unique_lens) > 1:
                    _cfg_err(logger, "[%s] All rest_conn path lists must be the same length. Got: %s",
                             label, lengths)

        # -- Per-block enum validation --
        ave = block.get("average_type")
        if ave is not None and ave not in VALID_AVE_TYPES:
            _cfg_err(logger, "[%s] average_type must be one of %s, got '%s'.", label, VALID_AVE_TYPES, ave)

        if atype in ("task_act", "task_conn"):
            hrf = block.get("hrf_model")
            if hrf is not None and hrf not in VALID_HRF_MODELS:
                _cfg_err(logger, "[%s] hrf_model must be one of %s, got '%s'.", label, VALID_HRF_MODELS, hrf)

        # -- rest_conn-specific parameter validation --
        if atype == "rest_conn":
            # motion_deriv_degree
            mdd = block.get("motion_deriv_degree")
            if mdd is not None:
                if isinstance(mdd, bool) or not isinstance(mdd, int) or mdd < 1:
                    _cfg_err(logger, "[%s] motion_deriv_degree must be a positive integer, got %r.", label, mdd)

            # Bandpass -- required for rest_conn, must be [low, high] list
            bp = block.get("bandpass")
            if bp is None:
                _cfg_err(logger, "[%s] bandpass is required for rest_conn. Provide [low, high] Hz.", label)
            if bp is True or bp is False:
                _cfg_err(logger, "[%s] bandpass must be a [low, high] list for rest_conn, not true/false.", label)
            if not (isinstance(bp, list) and len(bp) == 2):
                _cfg_err(logger, "[%s] bandpass must be a list of 2 floats [low, high].", label)
            bp_low = _check_number(bp[0], f"[{label}] bandpass lower bound", logger)
            bp_high = _check_number(bp[1], f"[{label}] bandpass upper bound", logger)
            if bp_low < 0 or bp_high <= bp_low:
                _cfg_err(logger, "[%s] bandpass must satisfy 0 <= low < high. Got [%s, %s].",
                         label, bp[0], bp[1])

            # notch_filter_band (optional)
            nfb = block.get("notch_filter_band")
            if nfb is not None:
                if not (isinstance(nfb, list) and len(nfb) == 2):
                    _cfg_err(logger,
                             "[%s] notch_filter_band must be a list of 2 floats [low, high] or null.", label)
                nfb_low = _check_number(nfb[0], f"[{label}] notch_filter_band lower bound", logger)
                nfb_high = _check_number(nfb[1], f"[{label}] notch_filter_band upper bound", logger)
                if nfb_low <= 0 or nfb_high <= 0 or nfb_low >= nfb_high:
                    _cfg_err(logger,
                             "[%s] notch_filter_band must satisfy 0 < low < high. Got [%s, %s].",
                             label, nfb[0], nfb[1])

        # -- fd_threshold (all types) --
        fd = block["fd_threshold"]
        if _check_number(fd, f"[{label}] fd_threshold", logger) <= 0:
            _cfg_err(logger, "[%s] fd_threshold must be a positive number, got %s.", label, fd)

        # -- Validate out_dir can be created --
        out_dir = block["out_dir"]
        if not Path(out_dir).is_dir():
            try:
                Path(out_dir).mkdir(parents=True, exist_ok=True)
            except OSError as e:
                _cfg_err(logger, "[%s] Cannot create out_dir '%s': %s", label, out_dir, e)

        # -- ROI averaging and smoothing --
        if block.get("roi_zero_handling", "exclude") not in VALID_ROI_ZERO_HANDLING:
            _cfg_err(logger, "[%s] roi_zero_handling must be one of %s, got '%s'.",
                     label, VALID_ROI_ZERO_HANDLING, block["roi_zero_handling"])
        _validate_smoothing(block.get("smoothing"), label, logger)

        # -- Contrasts validation --
        if atype == "task_act" and block.get("contrasts") is not None:
            contrasts = block["contrasts"]
            funcs = contrasts.get("functions")
            clabels = contrasts.get("labels")
            if funcs is not None and clabels is not None:
                if len(funcs) != len(clabels):
                    _cfg_err(logger,
                             "[%s] contrasts.functions and contrasts.labels must be the same length.", label)
                _check_contrast_labels(clabels, f"[{label}] contrasts.labels", logger)
                valid_contrast_functions(funcs, clabels, block["cond_labels"], logger=logger)
            elif funcs is not None and clabels is None:
                _cfg_err(logger,
                         "[%s] contrasts.functions provided but contrasts.labels is missing.", label)
        elif atype == "task_conn":
            tc_conn = block.get("connectivity", {}) or {}
            tc_contrasts = tc_conn.get("contrasts")
            if tc_contrasts is not None:
                if tc_conn.get("calc_conn") is None and tc_contrasts.get("functions") is not None:
                    _cfg_err(logger, "[%s] connectivity.contrasts need connectivity.calc_conn to be set.", label)
                funcs = tc_contrasts.get("functions")
                clabels = tc_contrasts.get("labels")
                if funcs is not None and clabels is not None:
                    if len(funcs) != len(clabels):
                        _cfg_err(logger,
                                 "[%s] connectivity.contrasts.functions and "
                                 "connectivity.contrasts.labels must be the same length.", label)
                    _check_contrast_labels(clabels, f"[{label}] connectivity.contrasts.labels", logger)
                    valid_contrast_functions(funcs, clabels, block["cond_beta_labels"], logger=logger)
                elif funcs is not None and clabels is None:
                    _cfg_err(logger,
                             "[%s] connectivity.contrasts.functions provided but "
                             "connectivity.contrasts.labels is missing.", label)

        # -- HRF model validation (task_act and task_conn only) --
        if atype in ("task_act", "task_conn"):
            hrf = block.get("hrf_model")
            if hrf is not None:
                if hrf not in VALID_HRF_MODELS:
                    _cfg_err(logger, "[%s] hrf_model must be one of %s, got '%s'.",
                             label, VALID_HRF_MODELS, hrf)
                if hrf == "custom":
                    custom = block.get("custom_hrf")
                    if not custom:
                        _cfg_err(logger,
                                 "[%s] custom_hrf string is required when hrf_model='custom'.", label)
                    else:
                        if not validate_custom_hrf(custom, logger):
                            raise ConfigError(f"[{label}] custom_hrf failed validation.")

                # task_conn uses 3dLSS which requires -stim_times_IM;
                # married-timing HRFs (e.g. dmBLOCK) require -stim_times_AM1
                # and are therefore incompatible.
                if atype == "task_conn":
                    custom = block.get("custom_hrf")
                    if needs_married_timing(hrf, custom):
                        _cfg_err(
                            logger,
                            "[%s] hrf_model '%s' requires married timing (-stim_times_AM1) which is "
                            "incompatible with 3dLSS (-stim_times_IM). Use GAM, SPMG1, or another "
                            "non-married HRF for task_conn analyses.",
                            label, hrf)

        # -- Extraction validation --
        if block.get("extraction") is not None:
            ext = block["extraction"]
            for key in ("extract_resids", "extract_raw_ptseries", "extract_pbseries", "extract_ptseries"):
                _check_bool(ext.get(key), f"[{label}] extraction.{key}", logger)
            if ext.get("extract_out_file_pre") is not None:
                _check_file_token(ext["extract_out_file_pre"], f"[{label}] extraction.extract_out_file_pre", logger)
            if atype == "task_act":
                stat_buckets = ext.get("stat_buckets")
                if stat_buckets is not None:
                    if not isinstance(stat_buckets, list) or not stat_buckets:
                        _cfg_err(logger,
                                 "[%s] extraction.stat_buckets must be a non-empty list.", label)
                    for sb in stat_buckets:
                        if sb not in VALID_STAT_BUCKET_TYPES:
                            _cfg_err(logger,
                                     "[%s] extraction.stat_buckets contains invalid type '%s'. "
                                     "Must be one of %s.", label, sb, VALID_STAT_BUCKET_TYPES)
                    if ext.get("extract_out_file_pre") is None:
                        _cfg_err(logger,
                                 "[%s] extraction block missing 'extract_out_file_pre' for task_act "
                                 "when stat_buckets is set.", label)
                elif ext.get("extract_resids", False):
                    _cfg_err(logger, "[%s] extraction.extract_resids needs extraction.stat_buckets "
                                     "and extract_out_file_pre.", label)
                if ext.get("extract_raw_ptseries", False) and ext.get("extract_out_file_pre") is None:
                    _cfg_err(logger,
                             "[%s] extraction block missing 'extract_out_file_pre' for task_act "
                             "when extract_raw_ptseries=true.", label)
            elif atype == "task_conn":
                if ext.get("extract_pbseries", False) and ext.get("extract_out_file_pre") is None:
                    _cfg_err(logger,
                             "[%s] extraction block missing 'extract_out_file_pre' for task_conn "
                             "when extract_pbseries=true.", label)
                if ext.get("extract_raw_ptseries", False) and ext.get("extract_out_file_pre") is None:
                    _cfg_err(logger,
                             "[%s] extraction block missing 'extract_out_file_pre' for task_conn "
                             "when extract_raw_ptseries=true.", label)
            elif atype == "rest_conn":
                if ext.get("extract_ptseries", False) and ext.get("extract_out_file_pre") is None:
                    _cfg_err(logger,
                             "[%s] extraction block missing 'extract_out_file_pre' for rest_conn "
                             "when extract_ptseries=true.", label)
                if ext.get("extract_raw_ptseries", False) and ext.get("extract_out_file_pre") is None:
                    _cfg_err(logger,
                             "[%s] extraction block missing 'extract_out_file_pre' for rest_conn "
                             "when extract_raw_ptseries=true.", label)

        # -- Connectivity validation --
        b_conn = block.get("connectivity", {}) or {}
        b_calc = b_conn.get("calc_conn")
        for key in ("pcorr", "fishZ"):
            _check_bool(b_conn.get(key), f"[{label}] connectivity.{key}", logger)
        if b_conn.get("conn_out_file_pre") is not None:
            _check_file_token(b_conn["conn_out_file_pre"], f"[{label}] connectivity.conn_out_file_pre", logger)
        elif b_calc is not None:
            _cfg_err(logger, "[%s] connectivity.conn_out_file_pre is required when calc_conn is set.", label)
        if b_calc is not None:
            if b_calc not in VALID_CONN_TYPES:
                _cfg_err(logger, "[%s] connectivity.calc_conn must be one of %s, got '%s'.",
                         label, VALID_CONN_TYPES, b_calc)

        # -- Template path validation (global-only) --
        tpl = global_cfg.get("template_path")
        if tpl is not None and not Path(tpl).is_file():
            _inp_err(logger, "[%s] template_path file does not exist: '%s'.", label, tpl)

    # -- Cross-block output collisions: no output prefix twice in one directory --
    seen_prefixes: dict[tuple[Path, str], str] = {}
    for idx, block in enumerate(raw_config["analyses"]):
        label = block.get("name", f"analyses[{idx}]")
        out_dir = Path(block["out_dir"]).resolve()
        prefixes = {block["out_file_pre"],
                    (block.get("extraction") or {}).get("extract_out_file_pre"),
                    (block.get("connectivity") or {}).get("conn_out_file_pre")} - {None}
        for prefix in sorted(prefixes):
            if (out_dir, prefix) in seen_prefixes:
                _cfg_err(logger,
                         "[%s] Output prefix '%s' in out_dir '%s' is also used by [%s]. "
                         "Output files would collide.",
                         label, prefix, out_dir, seen_prefixes[(out_dir, prefix)])
            seen_prefixes[(out_dir, prefix)] = label

    raw_config["global"] = global_cfg
    return raw_config


# ---------------------------------------------------------------------------
# Stage 3: resolve_config
# ---------------------------------------------------------------------------

def resolve_config(
    validated_block: dict,
    global_cfg: dict,
    logger: logging.Logger | None = None,
) -> ResolvedConfig:
    """Merge global defaults into a validated analysis block and build a ResolvedConfig.

    If derivatives_dirs is set in global_cfg or validated_block, the field is
    populated on ResolvedConfig. Input discovery (discover_inputs) is deferred
    and will be called by a later stage once implemented.

    Parameters
    ----------
    validated_block:
        A single validated analysis block from validate_config().
    global_cfg:
        The global section of the validated config dict.
    logger:
        Optional logger for diagnostic messages.

    Returns
    -------
    ResolvedConfig
        Fully resolved configuration dataclass for the analysis block.
    """
    atype = validated_block["type"]
    paths = validated_block.get("paths") or {}
    extraction = validated_block.get("extraction", None)
    connectivity = validated_block.get("connectivity", {}) or {}
    contrasts = validated_block.get("contrasts", None)  # task_act block-level contrasts

    # -- Global-sourced fields --
    num_cores_raw = global_cfg.get("num_cores")
    if num_cores_raw == "auto":
        num_cores, source = available_cpus()
        if logger is not None:
            logger.info("num_cores: auto -> %d (%s).", num_cores, source)
    else:
        num_cores = int(num_cores_raw) if num_cores_raw is not None else 1
    template_path = global_cfg.get("template_path", None)
    force_diff_atlas = bool(global_cfg.get("force_diff_atlas", False))
    tr = float(global_cfg["tr"])

    # BIDS discovery dirs: block-level overrides global if present
    derivatives_dirs = validated_block.get("derivatives_dirs") or global_cfg.get("derivatives_dirs")

    # -- Construct the base dataclass --
    cfg = ResolvedConfig(
        schema_version="3.0.0",
        analysis_type=atype,
        analysis_name=validated_block.get("name", None),
        out_dir=validated_block["out_dir"],
        out_file_pre=validated_block["out_file_pre"],
        tr=tr,
        fd_threshold=float(validated_block["fd_threshold"]),
        average_type=validated_block.get("average_type", ""),
        num_cores=num_cores,
        remove_previous=bool(validated_block.get("remove_previous", False)),
        censor_prev_tr=bool(validated_block.get("censor_prev_tr", False)),
        template_path=template_path,
        force_diff_atlas=force_diff_atlas,
        scale_to_psc=validated_block.get("scale_to_psc") is not False,
        derivatives_dirs=derivatives_dirs,
        roi_zero_handling=validated_block.get("roi_zero_handling", "exclude"),
    )
    smoothing = validated_block.get("smoothing") or {}
    if smoothing.get("enabled", False):
        cfg.smoothing_enabled = True
        cfg.smoothing_fwhm = float(smoothing["fwhm"])

    # -- Type-specific field population --
    # Use .get() for path slots so that BIDS discovery can fill gaps below.
    if atype == "task_act":
        cfg.scan_path = paths.get("scan_path")
        cfg.task_timing_path = paths.get("task_timing_path")
        cfg.motion_path = paths.get("motion_path")
        cfg.run_lengths = paths.get("run_lengths")
        cfg.cond_labels = validated_block["cond_labels"]
        cfg.hrf_model = validated_block["hrf_model"]
        cfg.custom_hrf = validated_block.get("custom_hrf", None)
        cfg.CSF_path = paths.get("CSF_path", None)
        cfg.WM_path = paths.get("WM_path", None)
        cfg.include_motion_derivs = bool(validated_block.get("include_motion_derivs", False))
        cfg.use_tissue_derivs = bool(validated_block.get("use_tissue_derivs", False))

        # Contrasts (functions: null = disabled)
        if contrasts is not None:
            funcs = contrasts.get("functions")
            clabels = contrasts.get("labels")
            if funcs is not None and clabels is not None:
                cfg.contrast_functions = funcs
                cfg.contrast_labels = clabels

        # Extraction
        if extraction is not None:
            cfg.stat_buckets = extraction.get("stat_buckets", None)
            cfg.extract_raw_ptseries = bool(extraction.get("extract_raw_ptseries", False))
            if cfg.stat_buckets is not None:
                cfg.extract_out_file_pre = extraction.get("extract_out_file_pre")
                cfg.extract_resids = bool(extraction.get("extract_resids", False))
            else:
                cfg.extract_out_file_pre = (
                    extraction.get("extract_out_file_pre") if cfg.extract_raw_ptseries else None
                )

    elif atype == "task_conn":
        cfg.scan_path = paths.get("scan_path")
        cfg.task_timing_path = paths.get("task_timing_path")
        cfg.motion_path = paths.get("motion_path")
        cfg.run_lengths = paths.get("run_lengths")
        cfg.cond_beta_labels = validated_block["cond_beta_labels"]
        cfg.hrf_model = validated_block["hrf_model"]
        cfg.custom_hrf = validated_block.get("custom_hrf", None)
        cfg.CSF_path = paths.get("CSF_path", None)
        cfg.WM_path = paths.get("WM_path", None)
        cfg.include_motion_derivs = bool(validated_block.get("include_motion_derivs", False))
        cfg.use_tissue_derivs = bool(validated_block.get("use_tissue_derivs", False))

        # Connectivity contrasts
        conn_contrasts = connectivity.get("contrasts", None)
        if conn_contrasts is not None:
            funcs = conn_contrasts.get("functions")
            clabels = conn_contrasts.get("labels")
            if funcs is not None and clabels is not None:
                cfg.contrast_functions = funcs
                cfg.contrast_labels = clabels

        # Extraction
        if extraction is not None:
            cfg.extract_pbseries = bool(extraction.get("extract_pbseries", False))
            cfg.extract_raw_ptseries = bool(extraction.get("extract_raw_ptseries", False))
            cfg.extract_out_file_pre = extraction.get("extract_out_file_pre")

        # Connectivity
        cfg.calc_conn = connectivity.get("calc_conn", None)
        cfg.conn_out_file_pre = connectivity.get("conn_out_file_pre", None)
        val = connectivity.get("pcorr")
        cfg.pcorr = bool(val) if val is not None else False
        val = connectivity.get("fishZ")
        cfg.fishZ = bool(val) if val is not None else False

    elif atype == "rest_conn":
        cfg.scan_paths = paths.get("scan_paths")
        cfg.motion_paths = paths.get("motion_paths")
        cfg.CSF_paths = paths.get("CSF_paths")
        cfg.WM_paths = paths.get("WM_paths")
        cfg.GS_paths = paths.get("GS_paths", None)
        cfg.notch_filter_band = validated_block.get("notch_filter_band", None)
        cfg.bandpass = validated_block["bandpass"]
        cfg.motion_deriv_degree = int(validated_block["motion_deriv_degree"])
        cfg.use_tissue_derivs = bool(validated_block.get("use_tissue_derivs", False))
        cfg.use_sequenced_bandpass = bool(validated_block.get("use_sequenced_bandpass", False))
        val = validated_block.get("keep_run_res_dtseries")
        cfg.keep_run_res_dtseries = val if val is not None else True

        # Extraction
        if extraction is not None:
            cfg.extract_ptseries = bool(extraction.get("extract_ptseries", False))
            cfg.extract_raw_ptseries = bool(extraction.get("extract_raw_ptseries", False))
            cfg.extract_out_file_pre = extraction.get("extract_out_file_pre")

        # Connectivity
        cfg.calc_conn = connectivity.get("calc_conn", None)
        cfg.conn_out_file_pre = connectivity.get("conn_out_file_pre", None)
        val = connectivity.get("pcorr")
        cfg.pcorr = bool(val) if val is not None else False
        val = connectivity.get("fishZ")
        cfg.fishZ = bool(val) if val is not None else False

    # -- Three-tier BIDS discovery resolution --
    # Tier 1 (explicit): already applied above via paths.get().
    # Tier 2 (discovered): fill gaps using BIDS discovery when derivatives_dirs is set.
    # Tier 3 (InputError): raise for any mandatory slot still None after both tiers.
    block_label = validated_block.get("name", atype)
    if derivatives_dirs is not None:
        disc_subject = validated_block.get("subject")
        if disc_subject is None:
            if logger is not None:
                logger.warning(
                    "[%s] derivatives_dirs is set but no 'subject' key found in block or overrides; "
                    "BIDS discovery skipped.",
                    validated_block.get("name", atype),
                )
        else:
            disc_session = validated_block.get("session")
            disc_task = validated_block.get("task")
            if disc_task is None:
                # Without a task, discovery would combine every task's files in the directory
                _cfg_err(logger, "[%s] BIDS discovery requires 'task'.", block_label)

            discovered = discover_inputs(
                derivatives_dirs=derivatives_dirs,
                subject=disc_subject,
                session=disc_session,
                task=disc_task,
                analysis_type=atype,
                logger=logger,
            )

            # Apply discovered values only where explicit config provided nothing (Tier 2).
            if atype in ("task_act", "task_conn"):
                if cfg.scan_path is None:
                    cfg.scan_path = discovered.scan_path
                if cfg.motion_path is None:
                    cfg.motion_path = discovered.motion_path
                if cfg.task_timing_path is None:
                    cfg.task_timing_path = discovered.task_timing_path
                if cfg.CSF_path is None and discovered.CSF_path is not None:
                    cfg.CSF_path = discovered.CSF_path
                if cfg.WM_path is None and discovered.WM_path is not None:
                    cfg.WM_path = discovered.WM_path
            elif atype == "rest_conn":
                if cfg.scan_paths is None:
                    cfg.scan_paths = discovered.scan_paths
                if cfg.motion_paths is None:
                    cfg.motion_paths = discovered.motion_paths
                if cfg.CSF_paths is None:
                    cfg.CSF_paths = discovered.CSF_paths
                if cfg.WM_paths is None:
                    cfg.WM_paths = discovered.WM_paths
                if cfg.GS_paths is None and discovered.GS_paths is not None:
                    cfg.GS_paths = discovered.GS_paths
            if cfg.template_path is None and discovered.template_path is not None:
                cfg.template_path = discovered.template_path

    # Tier 3: enforce mandatory slots, including when discovery was skipped for a missing subject.
    if atype in ("task_act", "task_conn"):
        mandatory_checks = [
            ("scan_path", cfg.scan_path),
            ("motion_path", cfg.motion_path),
            ("task_timing_path", cfg.task_timing_path),
        ]
    else:  # rest_conn
        mandatory_checks = [
            ("scan_paths", cfg.scan_paths),
            ("motion_paths", cfg.motion_paths),
            ("CSF_paths", cfg.CSF_paths),
            ("WM_paths", cfg.WM_paths),
        ]
    for slot_name, slot_val in mandatory_checks:
        if slot_val is None:
            _inp_err(
                logger,
                "[%s] Mandatory slot '%s' not resolved from explicit config or BIDS "
                "discovery in: %s",
                block_label, slot_name, derivatives_dirs,
            )
    if atype == "rest_conn":
        _check_rest_run_alignment(cfg, block_label, logger)

    return cfg


def _check_rest_run_alignment(cfg: ResolvedConfig, label, logger) -> None:
    """Refuse rest path lists that don't describe the same runs in the same order.

    Lists are paired by position. Explicit lists are the same length by validation, but
    discovered ones can differ, and any list whose names carry BIDS run entities can
    disagree about which run is which.
    """
    slots = {"scan_paths": cfg.scan_paths, "motion_paths": cfg.motion_paths, "CSF_paths": cfg.CSF_paths,
             "WM_paths": cfg.WM_paths}
    if cfg.GS_paths is not None:
        slots["GS_paths"] = cfg.GS_paths
    lengths = {slot: len(paths) for slot, paths in slots.items()}
    if len(set(lengths.values())) > 1:
        _inp_err(logger, "[%s] Run lists differ in length: %s", label, lengths)
    run_labels = {}
    for slot, paths in slots.items():
        found = [re.search(r"(?:^|_)run-([A-Za-z0-9]+)(?:_|$)", Path(p).name) for p in paths]
        if all(found):
            run_labels[slot] = [m.group(1) for m in found]
    if len({tuple(found) for found in run_labels.values()}) > 1:
        _inp_err(logger, "[%s] Run lists name different runs: %s", label, run_labels)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_and_validate(
    config_path: str,
    logger: logging.Logger | None = None,
    **overrides,
) -> list[ResolvedConfig]:
    """Load, validate, and resolve a YAML config into ResolvedConfig objects.

    Parameters
    ----------
    config_path:
        Path to the YAML configuration file.
    logger:
        Optional logger; errors and warnings are emitted before raising if provided.
    **overrides:
        Keyword arguments applied to each validated block before resolve_config()
        is called. The orchestrator uses this to inject subject-specific values
        (e.g. subject-specific paths) at dispatch time.

    Returns
    -------
    list[ResolvedConfig]
        One ResolvedConfig per analysis block, in config file order.

    Raises
    ------
    ConfigError
        For any structural or logic validation failure.
    InputError
        For any user-specified file path that does not exist.
    """
    raw = load_config(config_path)
    validated = validate_config(raw, logger)

    global_cfg = validated["global"]
    results: list[ResolvedConfig] = []

    for block in validated["analyses"]:
        merged = dict(block)
        if overrides:
            merged.update(overrides)
        cfg = resolve_config(merged, global_cfg, logger)
        results.append(cfg)

    return results
