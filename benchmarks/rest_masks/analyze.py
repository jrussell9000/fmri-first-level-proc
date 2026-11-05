"""Compare the mask arms from each session's saved series. Writes one JSON with no subject IDs.

    analyze.py --sessions-dir DIR --margins margins_v7.json --networks labels.csv --out report.json
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import metrics  # noqa: E402

ARMS = ("taylor_off", "ours_off", "ours_on")
REFERENCE = "taylor_off"
CANDIDATE = "ours_off"
CONTROL = "ours_on"
MIN_FRAMES_PER_HALF = 150  # 2 minutes
N_CORTICAL = 400  # the atlas's Schaefer parcels; Tian's subcortical ones follow, with no network


def load_session(path):
    with np.load(path, allow_pickle=False) as npz:
        return json.loads(str(npz["summary"])), {k: npz[k] for k in npz.files if k != "summary"}


def run_data(arrays, arm, runs):
    return [arrays[f"{arm}_series{i}"] for i in runs], [arrays[f"{arm}_censor{i}"] == 1 for i in runs]


def halves(arrays, arm, runs):
    """(half A z, half B z), or None when a half has too few frames."""
    split = metrics.split_runs(runs)
    if split is None:
        return None
    out = []
    for part in split:
        series, keeps = run_data(arrays, arm, part)
        if sum(k.sum() for k in keeps) < MIN_FRAMES_PER_HALF:
            return None
        out.append(metrics.session_fc(series, keeps))
    return tuple(out)


def collect(sessions, arms=ARMS):
    """One row per session with enough frames in the runs every arm kept. Off arms have equal
    regressor counts, so kept runs can differ only for the GSR control. Each arm holds
    (half A z or None, half B z or None, whole z, mean FD): a session with one usable run has
    no halves, and counts toward the motion measures only."""
    rows = []
    for summary, arrays in sessions:
        shared = sorted(set.intersection(*(set(summary["arms"][a]["kept_runs"]) for a in arms)))
        if not shared or sum(int(arrays[f"{arms[0]}_censor{i}"].sum()) for i in shared) < MIN_FRAMES_PER_HALF:
            continue
        per_arm = {}
        for arm in arms:
            split = halves(arrays, arm, shared)
            whole = metrics.session_fc(*run_data(arrays, arm, shared))
            per_arm[arm] = (*(split or (None, None)), whole, float(np.mean([summary["mean_fd"][i] for i in shared])))
        rows.append((summary["make"], per_arm))
    return rows


def make_covariates(makes):
    levels = sorted(set(makes))[1:]
    return np.array([[m == level for level in levels] for m in makes], dtype=float).reshape(len(makes), len(levels))


def network_ids(path, n_edges_parcels):
    """Network name per parcel, from the Schaefer label table; '' for parcels with none."""
    with open(path, newline="") as handle:
        names = [row["ROI Name"].split("_")[2] for row in csv.DictReader(handle)]
    if len(names) != N_CORTICAL:
        raise ValueError(f"expected {N_CORTICAL} labels, got {len(names)}")
    return np.array(names + [""] * (n_edges_parcels - len(names)))


def evaluate(rows, distances, networks, n_boot, seed, arms=ARMS):
    """Metrics per arm, with paired intervals against the reference arm."""
    split_rows = [r for r in rows if r[1][arms[0]][0] is not None]
    if len(split_rows) < 10:
        return {"n_sessions_motion": len(rows), "n_sessions_reliability": len(split_rows),
                "note": "too few sessions for group metrics"}  # fmt: skip
    covariates = make_covariates([r[0] for r in rows])
    whole = {arm: np.stack([r[1][arm][2] for r in rows]) for arm in arms}
    split = {arm: tuple(np.stack([r[1][arm][j] for r in split_rows]) for j in range(2)) for arm in arms}
    fd = np.array([r[1][arms[0]][3] for r in rows])
    n, n_split = len(rows), len(split_rows)
    n_edges = whole[REFERENCE].shape[1]
    subset = np.random.default_rng(seed).choice(n_edges, min(20000, n_edges), replace=False)

    def median_icc(arm, idx, edges=Ellipsis):
        return float(np.nanmedian(metrics.edgewise_icc(split[arm][0][idx][:, edges], split[arm][1][idx][:, edges])))

    def median_qc(arm, idx, edges=Ellipsis):
        r, _ = metrics.qc_fc(whole[arm][idx][:, edges], fd[idx], covariates[idx])
        return float(np.nanmedian(np.abs(r)))

    def global_motion(arm, idx):
        return abs(metrics.mean_fc_motion(whole[arm][idx], fd[idx], covariates[idx]))

    def intervals(arm, other):
        return {
            "icc": metrics.bootstrap_difference(
                lambda idx: median_icc(arm, idx, subset) - median_icc(other, idx, subset), n_split, n_boot, seed),
            "qc_fc": metrics.bootstrap_difference(
                lambda idx: median_qc(arm, idx, subset) - median_qc(other, idx, subset), n, n_boot, seed),
            "global_motion": metrics.bootstrap_difference(
                lambda idx: global_motion(arm, idx) - global_motion(other, idx), n, n_boot, seed),
        }  # fmt: skip

    report = {"n_sessions_motion": n, "n_sessions_reliability": n_split,
              "by_make": {m: sum(r[0] == m for r in rows) for m in {r[0] for r in rows}},
              "median_mean_fd": float(np.median(fd)), "chance_median_abs_r": float(0.6745 / np.sqrt(n)),
              "arms": {}}  # fmt: skip
    for arm in arms:
        r, p = metrics.qc_fc(whole[arm], fd, covariates)
        report["arms"][arm] = {
            "median_edge_icc": median_icc(arm, np.arange(n_split)),
            "median_abs_qc_fc": float(np.nanmedian(np.abs(r))),
            "mean_fc_motion_r": metrics.mean_fc_motion(whole[arm], fd, covariates),
            "fingerprint_accuracy": metrics.fingerprint_accuracy(*(np.nan_to_num(x) for x in split[arm])),
            "fraction_qc_fc_p05": float(np.mean(p[np.isfinite(p)] < 0.05)),
            "fdr_fraction_qc_fc": metrics.fdr_fraction(p),
            "qc_fc_distance_dependence": metrics.distance_dependence(r, distances),
            "mean_z": float(np.nanmean(whole[arm])),
            "pct_negative_edges": float(np.nanmean(whole[arm] < 0) * 100),
        }
        if networks is not None:
            report["arms"][arm]["within_minus_between_network_z"] = metrics.network_contrast(whole[arm], networks)
    report["candidate_minus_reference_ci"] = intervals(CANDIDATE, REFERENCE)
    report["control_minus_candidate_ci"] = intervals(CONTROL, CANDIDATE)
    return report


def decide(result, margins):
    """The rule in README.md, fixed before any arm ran on the test sample."""
    ci = result["candidate_minus_reference_ci"]
    rule = {
        "reliability_not_worse": ci["icc"][0] > -margins["icc"],
        "motion_link_not_worse": ci["qc_fc"][1] < margins["qc_fc"],
        "global_motion_not_clearly_worse": ci["global_motion"][0] <= 0,
        "reliability_better": ci["icc"][0] > 0,
    }
    control = result["control_minus_candidate_ci"]["global_motion"]
    return {**rule, "use_candidate": all(rule.values()), "measure_discriminates": control[1] < 0}


def retention(sessions, arms=ARMS):
    out = {}
    for arm in arms:
        done = [s for s, _ in sessions]
        out[arm] = {"runs_kept": sum(len(s["arms"][arm]["kept_runs"]) for s in done),
                    "runs_total": sum(len(s["runs"]) for s in done),
                    "sessions_losing_a_run": sum(len(s["arms"][arm]["kept_runs"]) < len(s["runs"]) for s in done),
                    "sessions_losing_all": sum(not s["arms"][arm]["kept_runs"] for s in done),
                    "median_seconds": float(np.median([s["arms"][arm]["seconds"] for s in done])) if done else None}  # fmt: skip
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sessions-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--margins", type=Path, required=True)
    ap.add_argument("--networks", type=Path, help="Schaefer label table; without it, no network measure")
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=20261104)
    args = ap.parse_args(argv)
    loaded = [load_session(p) for p in sorted(args.sessions_dir.glob("*.npz"))]
    sessions = [(s, a) for s, a in loaded if "skipped" not in s]
    report = {"sessions_loaded": len(loaded), "sessions_skipped": len(loaded) - len(sessions),
              "retention": retention(sessions)}  # fmt: skip
    if sessions:
        centroids = sessions[0][1]["centroids"]
        networks = network_ids(args.networks, len(centroids)) if args.networks else None
        report["result"] = evaluate(collect(sessions), metrics.edge_distances(centroids), networks, args.n_boot, args.seed)
        if "arms" in report["result"]:
            report["decision"] = decide(report["result"], json.loads(args.margins.read_text()))
    args.out.write_text(json.dumps(report, indent=2))
    print(f"wrote {args.out}: {report['sessions_loaded']} sessions, {report['sessions_skipped']} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
