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
    num_cores    : int -- CPU cores for parallel processing
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
from pathlib import Path
from typing import NoReturn

import yaml

from .bids import discover_inputs
from .exceptions import ConfigError, InputError
from .design import VALID_HRF_MODELS, validate_custom_hrf, needs_married_timing

VALID_TYPES = {"task_act", "task_conn", "rest_conn"}
VALID_STAT_BUCKET_TYPES = {"Coef", "Tstat", "Fstat", "R^2", "Zstat"}
VALID_AVE_TYPES = {"mean", "median"}
VALID_CONN_TYPES = {"seed_to_voxel", "parcellated"}

# Boolean flag keys (null -> False when merging)
BOOL_KEYS = (
    "remove_previous",
    "include_motion_derivs",
    "use_tissue_derivs",
    "censor_prev_tr",
    "use_sequenced_bandpass",
)

# Keys always sourced from global (block values ignored)
GLOBAL_ONLY_KEYS = ("num_cores", "template_path", "force_diff_atlas", "tr")


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

    # -- Top-level structure --
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
    tr_float: float
    try:
        tr_float = float(tr_val)
    except (TypeError, ValueError):
        _cfg_err(logger, "global.tr must be a positive number.")
    if tr_float <= 0:
        _cfg_err(logger, "global.tr must be a positive number, got %s.", tr_val)

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
        for key in check_required_top:
            if key not in block:
                _cfg_err(logger, "[%s] Missing required key '%s' for type '%s'.", label, key, atype)

        # Required path sub-keys
        paths = block.get("paths", {})
        if not isinstance(paths, dict):
            _cfg_err(logger, "[%s] 'paths' must be a dict.", label)
        if not discovery_active:
            for pkey in required_paths[atype]:
                if pkey not in paths:
                    _cfg_err(logger, "[%s] Missing required path key '%s' for type '%s'.", label, pkey, atype)

        # Validate file paths exist (only for paths that ARE explicitly provided)
        if atype in ("task_act", "task_conn"):
            for pkey in required_paths[atype]:
                if pkey in paths:
                    fpath = paths[pkey]
                    if not Path(fpath).is_file():
                        _inp_err(logger, "[%s] File does not exist: paths.%s = '%s'.", label, pkey, fpath)
            # Optional tissue regressor paths (skip if null)
            for opt_pkey in ("CSF_path", "WM_path"):
                if opt_pkey in paths and paths[opt_pkey] is not None:
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
                if pkey not in paths:
                    continue  # absent; will be discovered or caught in resolve_config
                plist = paths[pkey]
                if not isinstance(plist, list) or len(plist) == 0:
                    _cfg_err(logger, "[%s] paths.%s must be a non-empty list for rest_conn.", label, pkey)
                for fpath in plist:
                    if not Path(fpath).is_file():
                        _inp_err(logger, "[%s] File does not exist: paths.%s entry '%s'.", label, pkey, fpath)

            # Optional GS_paths
            if "GS_paths" in paths and paths["GS_paths"] is not None:
                gs_list = paths["GS_paths"]
                if not isinstance(gs_list, list) or len(gs_list) == 0:
                    _cfg_err(logger, "[%s] paths.GS_paths must be a non-empty list for rest_conn.", label)
                for fpath in gs_list:
                    if not Path(fpath).is_file():
                        _inp_err(logger, "[%s] File does not exist: paths.GS_paths entry '%s'.", label, fpath)

            # All explicitly-provided rest_conn path lists must be the same length.
            provided_required = {pkey for pkey in required_paths[atype] if pkey in paths}
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

        # Warn if block contains global-only keys (they will be ignored)
        for key in GLOBAL_ONLY_KEYS:
            if key in block and logger is not None:
                logger.warning("[%s] '%s' is a global-only setting -- block value will be ignored.", label, key)

        # -- rest_conn-specific parameter validation --
        if atype == "rest_conn":
            # motion_deriv_degree
            mdd = block.get("motion_deriv_degree")
            if mdd is not None:
                mdd_int: int
                try:
                    mdd_int = int(mdd)
                except (TypeError, ValueError):
                    _cfg_err(logger, "[%s] motion_deriv_degree must be a positive integer.", label)
                if mdd_int < 1:
                    _cfg_err(logger, "[%s] motion_deriv_degree must be a positive integer, got %s.", label, mdd)

            # Bandpass -- required for rest_conn, must be [low, high] list
            bp = block.get("bandpass")
            if bp is None:
                _cfg_err(logger, "[%s] bandpass is required for rest_conn. Provide [low, high] Hz.", label)
            if bp is True or bp is False:
                _cfg_err(logger, "[%s] bandpass must be a [low, high] list for rest_conn, not true/false.", label)
            if not (isinstance(bp, list) and len(bp) == 2):
                _cfg_err(logger, "[%s] bandpass must be a list of 2 floats [low, high].", label)
            bp_low: float
            bp_high: float
            try:
                bp_low, bp_high = float(bp[0]), float(bp[1])
            except (TypeError, ValueError):
                _cfg_err(logger, "[%s] bandpass values must be numeric.", label)
            if bp_low < 0 or bp_high <= bp_low:
                _cfg_err(logger, "[%s] bandpass must satisfy 0 <= low < high. Got [%s, %s].",
                         label, bp[0], bp[1])

            # notch_filter_band (optional)
            nfb = block.get("notch_filter_band")
            if nfb is not None:
                if not (isinstance(nfb, list) and len(nfb) == 2):
                    _cfg_err(logger,
                             "[%s] notch_filter_band must be a list of 2 floats [low, high] or null.", label)
                nfb_low: float
                nfb_high: float
                try:
                    nfb_low, nfb_high = float(nfb[0]), float(nfb[1])
                except (TypeError, ValueError):
                    _cfg_err(logger, "[%s] notch_filter_band values must be numeric.", label)
                if nfb_low <= 0 or nfb_high <= 0 or nfb_low >= nfb_high:
                    _cfg_err(logger,
                             "[%s] notch_filter_band must satisfy 0 < low < high. Got [%s, %s].",
                             label, nfb[0], nfb[1])

        # -- fd_threshold (all types) --
        fd = block.get("fd_threshold")
        if fd is not None:
            fd_float: float
            try:
                fd_float = float(fd)
            except (TypeError, ValueError):
                _cfg_err(logger, "[%s] fd_threshold must be a positive number.", label)
            if fd_float <= 0:
                _cfg_err(logger, "[%s] fd_threshold must be a positive number, got %s.", label, fd)

        # -- Validate out_dir can be created --
        out_dir = block["out_dir"]
        if not Path(out_dir).is_dir():
            try:
                Path(out_dir).mkdir(parents=True, exist_ok=True)
            except OSError as e:
                _cfg_err(logger, "[%s] Cannot create out_dir '%s': %s", label, out_dir, e)

        # -- Contrasts validation --
        if atype == "task_act" and "contrasts" in block:
            contrasts = block["contrasts"]
            funcs = contrasts.get("functions")
            clabels = contrasts.get("labels")
            if funcs is not None and clabels is not None:
                if len(funcs) != len(clabels):
                    _cfg_err(logger,
                             "[%s] contrasts.functions and contrasts.labels must be the same length.", label)
            elif funcs is not None and clabels is None:
                _cfg_err(logger,
                         "[%s] contrasts.functions provided but contrasts.labels is missing.", label)
        elif atype == "task_conn":
            tc_conn = block.get("connectivity", {}) or {}
            tc_contrasts = tc_conn.get("contrasts")
            if tc_contrasts is not None:
                funcs = tc_contrasts.get("functions")
                clabels = tc_contrasts.get("labels")
                if funcs is not None and clabels is not None:
                    if len(funcs) != len(clabels):
                        _cfg_err(logger,
                                 "[%s] connectivity.contrasts.functions and "
                                 "connectivity.contrasts.labels must be the same length.", label)
                elif funcs is not None and clabels is None:
                    _cfg_err(logger,
                             "[%s] connectivity.contrasts.functions provided but "
                             "connectivity.contrasts.labels is missing.", label)
        elif "contrasts" in block and atype not in ("task_act",):
            if logger is not None:
                logger.warning(
                    "[%s] contrasts block at the analysis level is only supported for task_act; "
                    "for task_conn, place contrasts under connectivity. Ignoring.", label)

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
        if "extraction" in block:
            ext = block["extraction"]
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
                    if "extract_out_file_pre" not in ext:
                        _cfg_err(logger,
                                 "[%s] extraction block missing 'extract_out_file_pre' for task_act "
                                 "when stat_buckets is set.", label)
                if ext.get("extract_raw_ptseries", False) and "extract_out_file_pre" not in ext:
                    _cfg_err(logger,
                             "[%s] extraction block missing 'extract_out_file_pre' for task_act "
                             "when extract_raw_ptseries=true.", label)
            elif atype == "task_conn":
                if ext.get("extract_pbseries", False) and "extract_out_file_pre" not in ext:
                    _cfg_err(logger,
                             "[%s] extraction block missing 'extract_out_file_pre' for task_conn "
                             "when extract_pbseries=true.", label)
                if ext.get("extract_raw_ptseries", False) and "extract_out_file_pre" not in ext:
                    _cfg_err(logger,
                             "[%s] extraction block missing 'extract_out_file_pre' for task_conn "
                             "when extract_raw_ptseries=true.", label)
            elif atype == "rest_conn":
                if ext.get("extract_ptseries", False) and "extract_out_file_pre" not in ext:
                    _cfg_err(logger,
                             "[%s] extraction block missing 'extract_out_file_pre' for rest_conn "
                             "when extract_ptseries=true.", label)
                if ext.get("extract_raw_ptseries", False) and "extract_out_file_pre" not in ext:
                    _cfg_err(logger,
                             "[%s] extraction block missing 'extract_out_file_pre' for rest_conn "
                             "when extract_raw_ptseries=true.", label)

        # -- Connectivity validation --
        b_conn = block.get("connectivity", {}) or {}
        b_calc = b_conn.get("calc_conn")
        if b_calc is not None:
            if b_calc not in VALID_CONN_TYPES:
                _cfg_err(logger, "[%s] connectivity.calc_conn must be one of %s, got '%s'.",
                         label, VALID_CONN_TYPES, b_calc)

        # -- Template path validation (global-only) --
        tpl = global_cfg.get("template_path")
        if tpl is not None and not Path(tpl).is_file():
            _inp_err(logger, "[%s] template_path file does not exist: '%s'.", label, tpl)

    # -- Duplicate (out_dir, out_file_pre) pair check --
    seen_pairs: dict[tuple[str, str], str] = {}
    for idx, block in enumerate(raw_config["analyses"]):
        label = block.get("name", f"analyses[{idx}]")
        pair = (block["out_dir"], block["out_file_pre"])
        if pair in seen_pairs:
            _cfg_err(
                logger,
                "[%s] Duplicate (out_dir, out_file_pre) pair: ('%s', '%s') -- also used by [%s]. "
                "Output files would collide.",
                label, pair[0], pair[1], seen_pairs[pair])
        seen_pairs[pair] = label

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
    paths = validated_block.get("paths", {})
    extraction = validated_block.get("extraction", None)
    connectivity = validated_block.get("connectivity", {}) or {}
    contrasts = validated_block.get("contrasts", None)  # task_act block-level contrasts

    # -- Global-sourced fields --
    num_cores_raw = global_cfg.get("num_cores")
    num_cores = int(num_cores_raw) if num_cores_raw is not None else 1
    template_path = global_cfg.get("template_path", None)
    force_diff_atlas = bool(global_cfg.get("force_diff_atlas", False))
    tr = float(global_cfg["tr"])

    # BIDS discovery dirs: block-level overrides global if present
    derivatives_dirs = validated_block.get("derivatives_dirs", global_cfg.get("derivatives_dirs", None))

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
        scale_to_psc=bool(validated_block.get("scale_to_psc", True)),
        derivatives_dirs=derivatives_dirs,
    )

    # -- Type-specific field population --
    # Use .get() for path slots so that BIDS discovery can fill gaps below.
    if atype == "task_act":
        cfg.scan_path = paths.get("scan_path")
        cfg.task_timing_path = paths.get("task_timing_path")
        cfg.motion_path = paths.get("motion_path")
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

            # Tier 3: enforce mandatory slots; raise InputError if still unresolved.
            block_label = validated_block.get("name", atype)
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

    return cfg


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
