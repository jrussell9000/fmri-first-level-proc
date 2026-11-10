"""Filename and path conventions for fmri-first-level-proc.

Every package-created path inside out_dir starts with an analysis prefix
(out_file_pre, extract_out_file_pre or conn_out_file_pre) except staging
directories ``.staging_{pre}_{step}``.  The three frozen primary output
names are a stable interface:

- task_act: ``{pre}_concat_bucket_stats.nii.gz``
- task_conn: ``{pre}_concat_LSS.nii.gz``
- rest_conn: ``{pre}_concat_residual_dtseries.nii.gz``

All functions in this module are pure (no I/O, no subprocess calls).
"""

import os
from decimal import Decimal

# ---------------------------------------------------------------------------
# Frozen primary output templates (stable interface)
# ---------------------------------------------------------------------------
TASK_ACT_BUCKET_STATS = "{pre}_concat_bucket_stats.nii.gz"
TASK_CONN_LSS = "{pre}_concat_LSS.nii.gz"
REST_CONCAT_RESIDUAL = "{pre}_concat_residual_dtseries.nii.gz"

TYPE_LABEL = {
    "task_act": "task-act",
    "task_conn": "task-conn",
    "rest_conn": "rest-conn",
}

_EXTENSIONS = (
    ".nii.gz", ".nii", ".x1D", ".1D", ".1d", ".csv", ".json", ".txt",
    ".REML_cmd",
)


# ---------------------------------------------------------------------------
# Frozen names
# ---------------------------------------------------------------------------

def frozen_primary(analysis_type, pre):
    """Return the single frozen primary output basename for *analysis_type*."""
    templates = {
        "task_act": TASK_ACT_BUCKET_STATS,
        "task_conn": TASK_CONN_LSS,
        "rest_conn": REST_CONCAT_RESIDUAL,
    }
    return templates[analysis_type].format(pre=pre)


def frozen_names(analysis_type, pre):
    """Return the set of frozen names that must never be retired."""
    return {frozen_primary(analysis_type, pre)}


# ---------------------------------------------------------------------------
# Smoothing helpers
# ---------------------------------------------------------------------------

def smoothing_canonical(fwhm):
    """Return the canonical string representation of *fwhm* (e.g. ``'6'``, ``'4.5'``)."""
    return format(Decimal(repr(float(fwhm))).normalize(), "f")


def smoothing_token(fwhm):
    """Return ``''`` when *fwhm* is None, else ``'_s{N}mm'``."""
    if fwhm is None:
        return ""
    canon = smoothing_canonical(fwhm)
    return "_s" + canon.replace(".", "p") + "mm"


def with_token(name, token):
    """Insert *token* before the first matching extension in *name*.

    If *token* is empty the original name is returned unchanged.
    """
    if not token:
        return name
    for ext in _EXTENSIONS:
        if name.endswith(ext):
            stem = name[: -len(ext)]
            return stem + token + ext
    return name + token


# ---------------------------------------------------------------------------
# Infrastructure paths
# ---------------------------------------------------------------------------

def staging_dir(pre, step):
    return f".staging_{pre}_{step}"


def ledger(pre):
    return f"{pre}_ledger.jsonl"


def qc_summary(pre):
    return f"{pre}_qc_summary.json"


def timing_errors(pre):
    return f"{pre}_timing_errors.json"


# ---------------------------------------------------------------------------
# Per-run EPI / PSC / mean volumes
# ---------------------------------------------------------------------------

def min_outlier_epi(pre, label=None):
    if label is None:
        return f"{pre}_min_outlier_epi.nii.gz"
    return f"{pre}_run{label}_min_outlier_epi.nii.gz"


def run_mean(pre, label=None):
    if label is None:
        return f"{pre}_mean.nii.gz"
    return f"{pre}_run{label}_mean.nii.gz"


def run_psc(pre, label=None):
    if label is None:
        return f"{pre}_psc.nii.gz"
    return f"{pre}_run{label}_psc.nii.gz"


# The concatenations are uncompressed: each is the per-run files end to end, written
# once and read whole by the model, the raw ptseries and validation, and gzip costs a
# full compression to write and a full decompression on every read. (With one run
# supplied, run_psc(pre, None) is the model input and keeps its .nii.gz name.)
def psc_concat(pre):
    return f"{pre}_psc.nii"


def concat_scan(pre):
    return f"{pre}_concat_scan.nii"


def run_intersect_mask(pre):
    return f"{pre}_run_intersect_mask.nii.gz"


# ---------------------------------------------------------------------------
# Censor / motion / tissue
# ---------------------------------------------------------------------------

def censor_prefix(pre, label=None):
    if label is None:
        return f"{pre}_concat"
    return f"{pre}_run{label}"


def censor(pre, label=None):
    return censor_prefix(pre, label) + "_censor.1D"


def censor_enorm(pre, label=None):
    return censor_prefix(pre, label) + "_enorm.1D"


def censor_fd(pre, label=None):
    return censor_prefix(pre, label) + "_fd.1D"


def censor_side_files(pre, label=None):
    return [censor_enorm(pre, label), censor_fd(pre, label)]


def motion_prepared(pre, label=None):
    if label is None:
        return f"{pre}_concat_motion_prepared.1D"
    return f"{pre}_run{label}_motion_prepared.1D"


def notch_motion(pre, label):
    return f"{pre}_run{label}_notch_motion.1D"


def tissue_prepared(pre, tissue, label=None):
    """Prepared single-column tissue regressor: concat (task) or per run (rest)."""
    if label is None:
        return f"{pre}_concat_{tissue}_prepared.1D"
    return f"{pre}_run{label}_{tissue}_prepared.1D"


def tissue_deriv(pre, tissue, label=None):
    if label is None:
        return f"{pre}_concat_{tissue}_deriv.1D"
    return f"{pre}_run{label}_{tissue}_deriv.1D"


# ---------------------------------------------------------------------------
# Task onset / design-matrix files
# ---------------------------------------------------------------------------

def onset_file(pre, cond):
    return f"{pre}_concat_{cond}_onsets.txt"


def beta_onsets(pre):
    return f"{pre}_concat_beta_onsets.txt"


def preflight_dmat(pre):
    return f"{pre}_preflight_dmat.x1D"


def estimability_dmat(pre):
    return f"{pre}_estimability_dmat.x1D"


def bseries_dmat(pre):
    return f"{pre}_concat_bseries_dmat.x1D"


def reml_cmd(pre, step):
    return f"{pre}_{step}.REML_cmd"


# ---------------------------------------------------------------------------
# task_act bucket / stat-bucket / extraction outputs
# ---------------------------------------------------------------------------

def bucket_stats(pre, token=""):
    return with_token(f"{pre}_concat_bucket_stats.nii.gz", token)


def bucket_resids(pre, token=""):
    return with_token(f"{pre}_concat_bucket_resids.nii.gz", token)


def bucket_stats_index(pre, token=""):
    return with_token(f"{pre}_concat_bucket_stats_index.json", token)


def stat_bucket(ext, stat, token=""):
    return with_token(f"{ext}_{stat}_bucket.nii.gz", token)


def stat_index(ext, stat, token=""):
    return with_token(f"{ext}_{stat}_index.json", token)


def stat_parcellated(ext, stat):
    return f"{ext}_{stat}_parcellated.csv"


def resids_csv(ext):
    return f"{ext}_resids.csv"


# ---------------------------------------------------------------------------
# task_conn LSS / beta-series / pbseries
# ---------------------------------------------------------------------------

def lss(pre, token=""):
    return with_token(f"{pre}_concat_LSS.nii.gz", token)


def lss_1d(pre):
    return f"{pre}_concat_LSS.1d"


def bseries(pre, cond, token=""):
    return with_token(f"{pre}_concat_bseries_{cond}.nii.gz", token)


def lss_index(pre, token=""):
    return with_token(f"{pre}_concat_LSS_index.json", token)


def bseries_index(pre, cond, token=""):
    return with_token(f"{pre}_concat_bseries_{cond}_index.json", token)


def pbseries(ext, cond):
    return f"{ext}_pbseries_{cond}.csv"


# ---------------------------------------------------------------------------
# Raw ptseries (task and rest)
# ---------------------------------------------------------------------------

def raw_ptseries(ext, label=None):
    if label is None:
        return f"{ext}_raw_ptseries.csv"
    return f"{ext}_run{label}_raw_ptseries.csv"


def raw_psc_ptseries(ext, label=None):
    if label is None:
        return f"{ext}_raw_psc_ptseries.csv"
    return f"{ext}_run{label}_raw_psc_ptseries.csv"


# ---------------------------------------------------------------------------
# rest_conn residual / ptseries
# ---------------------------------------------------------------------------

def residual_run(pre, label, token=""):
    return with_token(f"{pre}_run{label}_residual_dtseries.nii.gz", token)


def residual_concat(pre, token=""):
    return with_token(f"{pre}_concat_residual_dtseries.nii.gz", token)


def residual_ptseries(ext):
    return f"{ext}_residual_ptseries.csv"


def sequenced_dir(pre, label):
    return f"{pre}_sequenced_intermediates/run{label}"


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------

def template_stem(template_path):
    """Return the template basename with ``.nii.gz`` or ``.nii`` removed."""
    base = os.path.basename(template_path)
    if base.endswith(".nii.gz"):
        return base[:-7]
    if base.endswith(".nii"):
        return base[:-4]
    return base


def template_resampled(pre, template_path):
    return f"{pre}_{template_stem(template_path)}_resampled.nii.gz"


def legacy_template_resampled(template_path):
    """Pre-4.0.0 unprefixed resampled template name (for the unrecorded-file refusal scan)."""
    return f"{template_stem(template_path)}_resampled.nii.gz"


# ---------------------------------------------------------------------------
# Smoothing
# ---------------------------------------------------------------------------

def smoothing_mask(pre):
    return f"{pre}_smoothing_mask.nii.gz"


def blurred_run(pre, label, token):
    if label is None:
        return with_token(f"{pre}_blur.nii.gz", token)
    return with_token(f"{pre}_run{label}_blur.nii.gz", token)


def blurred_psc_run(pre, label, token):
    return with_token(run_psc(pre, label), token)


def blurred_concat(pre, token, psc=False):
    base = psc_concat(pre) if psc else concat_scan(pre)
    return with_token(base, token)


# ---------------------------------------------------------------------------
# Connectivity outputs
# ---------------------------------------------------------------------------

def conn_output(conn_pre, condition, fishZ, pcorr, calc_conn, token=""):
    """Return the connectivity output basename.

    Parameters
    ----------
    conn_pre : str
        Connectivity output prefix (conn_out_file_pre).
    condition : str or None
        Condition name, or None for rest.
    fishZ : bool
        Whether Fisher Z transform is applied.
    pcorr : bool
        Whether partial correlation is used.
    calc_conn : str
        ``'parcellated'`` or ``'seed_to_voxel'``.
    token : str
        Smoothing token (empty string for unsmoothed).
    """
    prefix = conn_pre if condition is None else f"{conn_pre}_{condition}"
    if calc_conn == "parcellated":
        if pcorr and fishZ:
            suffix = "_pcorr_fishZ_mat.txt"
        elif fishZ:
            suffix = "_fishZ_mat.txt"
        elif pcorr:
            suffix = "_pcorr_mat.txt"
        else:
            suffix = "_corr_mat.txt"
    else:
        # seed_to_voxel (pcorr rejected at config time)
        if fishZ:
            suffix = "_fishZ.nii.gz"
        else:
            suffix = "_corr.nii.gz"
    return with_token(prefix + suffix, token)


# ---------------------------------------------------------------------------
# Prefix enumeration
# ---------------------------------------------------------------------------

def all_prefixes(pre, ext, conn):
    """Return a tuple of the non-None analysis prefixes."""
    result = [pre]
    if ext is not None:
        result.append(ext)
    if conn is not None:
        result.append(conn)
    return tuple(result)
