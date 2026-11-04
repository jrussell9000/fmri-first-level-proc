"""Group metrics for the rest denoising comparison. Pure numpy, with no AFNI or file access."""

import numpy as np
from scipy.stats import rankdata, t as t_dist

Z_CAP = 4.0  # 3dNetCorr's cap on Fisher z


def upper_triangle(n_parcels):
    return np.triu_indices(n_parcels, k=1)


def session_fc(series, keeps):
    """Fisher z edge vector from runs pooled on their kept frames, each run demeaned first.

    series: list of (T, P) parcel time series. keeps: list of (T,) boolean arrays.
    A parcel with no signal gives NaN edges.
    """
    kept = [s[k] - s[k].mean(axis=0) for s, k in zip(series, keeps, strict=True)]
    pooled = np.vstack(kept)
    norm = np.sqrt((pooled**2).sum(axis=0))
    with np.errstate(invalid="ignore", divide="ignore"):
        unit = pooled / norm
        unit[:, norm == 0] = np.nan
    r = unit.T @ unit
    upper = upper_triangle(r.shape[0])
    return np.arctanh(np.clip(r[upper], -np.tanh(Z_CAP), np.tanh(Z_CAP)))


def split_runs(run_ids):
    """Alternate a session's usable runs into two halves, or None with fewer than two runs."""
    runs = sorted(run_ids)
    if len(runs) < 2:
        return None
    return runs[0::2], runs[1::2]


def edgewise_icc(half_a, half_b):
    """ICC(3,1) per edge for two measurements. Inputs are (subjects, edges)."""
    mean = (half_a + half_b) / 2
    between = 2 * np.var(mean, axis=0, ddof=1)
    error = np.var(half_a - half_b, axis=0, ddof=1) / 2
    with np.errstate(invalid="ignore", divide="ignore"):
        return (between - error) / (between + error)


def fingerprint_accuracy(half_a, half_b):
    """Share of subjects whose other half is their best match, averaged over both directions."""
    a = half_a - half_a.mean(axis=0, keepdims=True)
    b = half_b - half_b.mean(axis=0, keepdims=True)
    a = a / np.linalg.norm(a, axis=1, keepdims=True)
    b = b / np.linalg.norm(b, axis=1, keepdims=True)
    similarity = a @ b.T
    subjects = np.arange(len(a))
    return float(((similarity.argmax(axis=1) == subjects).mean() + (similarity.argmax(axis=0) == subjects).mean()) / 2)


def _residualize(values, covariates):
    design = np.column_stack([np.ones(len(values)), covariates]) if covariates.size else np.ones((len(values), 1))
    beta, *_ = np.linalg.lstsq(design, values, rcond=None)
    return values - design @ beta, design.shape[1]


def qc_fc(fc, mean_fd, covariates):
    """Partial correlation of each edge with mean FD. Returns (r, two-sided p).

    fc is (subjects, edges). covariates is (subjects, k), and k may be 0.
    """
    y, n_terms = _residualize(fc, covariates)
    x, _ = _residualize(np.asarray(mean_fd, dtype=float), covariates)
    with np.errstate(invalid="ignore", divide="ignore"):
        r = (x @ y) / (np.linalg.norm(x) * np.linalg.norm(y, axis=0))
        df = len(x) - n_terms - 1
        t = r * np.sqrt(df / (1 - r**2))
    return r, 2 * t_dist.sf(np.abs(t), df)


def fdr_fraction(p, q=0.05):
    """Fraction of finite p-values significant under Benjamini-Hochberg."""
    finite = np.sort(p[np.isfinite(p)])
    if not finite.size:
        return float("nan")
    passed = finite <= q * np.arange(1, finite.size + 1) / finite.size
    return float((np.nonzero(passed)[0].max() + 1) / finite.size) if passed.any() else 0.0


def distance_dependence(r, distances):
    """Spearman correlation of QC-FC with the distance between an edge's parcels."""
    good = np.isfinite(r) & np.isfinite(distances)
    return float(np.corrcoef(rankdata(r[good]), rankdata(distances[good]))[0, 1])


def edge_distances(centroids):
    upper = upper_triangle(len(centroids))
    return np.linalg.norm(centroids[upper[0]] - centroids[upper[1]], axis=1)


def bootstrap_difference(statistic, n_subjects, n_boot, seed):
    """Paired percentile interval for statistic(indices), resampling subjects."""
    rng = np.random.default_rng(seed)
    draws = np.array([statistic(rng.integers(0, n_subjects, n_subjects)) for _ in range(n_boot)])
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))
