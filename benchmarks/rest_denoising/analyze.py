"""Compare the arms from each session's saved series. Writes one JSON with no subject IDs.

    analyze.py --sessions-dir DIR --margins margins.json --out report.json
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import metrics  # noqa: E402

ARMS = ("bandpass", "sequenced", "highpass", "anchor_9p")
REFERENCE = "bandpass"
MIN_FRAMES_PER_HALF = 150  # 2 minutes


def load_session(path):
    with np.load(path, allow_pickle=False) as npz:
        return json.loads(str(npz["summary"])), {k: npz[k] for k in npz.files if k != "summary"}


def run_data(arrays, arm, runs):
    series = [arrays[f"{arm}_series{i}"] for i in runs]
    keeps = [arrays[f"{arm}_censor{i}"] == 1 for i in runs]
    return series, keeps


def halves(arrays, arm, runs):
    """(half A z, half B z, whole z), or None when a half has too few frames."""
    split = metrics.split_runs(runs)
    if split is None:
        return None
    out = []
    for part in split:
        series, keeps = run_data(arrays, arm, part)
        if sum(k.sum() for k in keeps) < MIN_FRAMES_PER_HALF:
            return None
        out.append(metrics.session_fc(series, keeps))
    series, keeps = run_data(arrays, arm, list(runs))
    return out[0], out[1], metrics.session_fc(series, keeps)


def collect(sessions, runs_for, arms=ARMS):
    """Sessions usable in every arm, given a function naming each arm's runs."""
    rows = []
    for summary, arrays in sessions:
        per_arm = {}
        for arm in arms:
            result = halves(arrays, arm, runs_for(summary, arm))
            if result is None:
                break
            kept = runs_for(summary, arm)
            per_arm[arm] = (*result, float(np.mean([summary["mean_fd"][i] for i in kept])))
        else:
            rows.append((summary["make"], per_arm))
    return rows


def make_covariates(makes):
    levels = sorted(set(makes))[1:]
    return np.array([[m == level for level in levels] for m in makes], dtype=float).reshape(len(makes), len(levels))


def evaluate(rows, distances, n_boot, seed, arms=ARMS):
    """Metrics per arm, with paired intervals against the reference arm."""
    if len(rows) < 10:
        return {"n_sessions": len(rows), "note": "too few sessions for group metrics"}
    covariates = make_covariates([r[0] for r in rows])
    data = {arm: tuple(np.stack([r[1][arm][j] for r in rows]) for j in range(3)) for arm in arms}
    fd = {arm: np.array([r[1][arm][3] for r in rows]) for arm in arms}
    n = len(rows)
    rng = np.random.default_rng(seed)
    n_edges = data[REFERENCE][0].shape[1]
    subset = rng.choice(n_edges, min(20000, n_edges), replace=False)

    def median_icc(arm, idx, edges=Ellipsis):
        return float(np.nanmedian(metrics.edgewise_icc(data[arm][0][idx][:, edges], data[arm][1][idx][:, edges])))

    def median_qc(arm, idx, edges=Ellipsis):
        r, _ = metrics.qc_fc(data[arm][2][idx][:, edges], fd[arm][idx], covariates[idx])
        return float(np.nanmedian(np.abs(r)))

    report = {"n_sessions": n, "arms": {}}
    everyone = np.arange(n)
    for arm in arms:
        r, p = metrics.qc_fc(data[arm][2], fd[arm], covariates)
        report["arms"][arm] = {
            "median_edge_icc": median_icc(arm, everyone),
            "fingerprint_accuracy": metrics.fingerprint_accuracy(*(np.nan_to_num(x) for x in data[arm][:2])),
            "median_abs_qc_fc": float(np.nanmedian(np.abs(r))),
            "fdr_fraction_qc_fc": metrics.fdr_fraction(p),
            "qc_fc_distance_dependence": metrics.distance_dependence(r, distances),
        }
        if arm != REFERENCE:
            report["arms"][arm]["icc_minus_reference_ci"] = metrics.bootstrap_difference(
                lambda idx, a=arm: median_icc(a, idx, subset) - median_icc(REFERENCE, idx, subset), n, n_boot, seed)
            report["arms"][arm]["qc_fc_minus_reference_ci"] = metrics.bootstrap_difference(
                lambda idx, a=arm: median_qc(a, idx, subset) - median_qc(REFERENCE, idx, subset), n, n_boot, seed)
    return report


def decide(report, margins):
    """Apply the rule in README.md to the all-data population and the common-run population."""
    verdict = {}
    for arm in ARMS:
        if arm == REFERENCE:
            continue
        common, whole = report["common_runs"]["arms"][arm], report["all_data"]["arms"][arm]
        verdict[arm] = {
            "reliability_not_worse_on_common_runs": common["icc_minus_reference_ci"][0] > -margins["icc"],
            "motion_link_not_worse_on_common_runs": common["qc_fc_minus_reference_ci"][1] < margins["qc_fc"],
            "reliability_better_on_all_data": whole["icc_minus_reference_ci"][0] > 0,
            "motion_link_not_worse_on_all_data": whole["qc_fc_minus_reference_ci"][1] < margins["qc_fc_all_data"],
        }
        verdict[arm]["passes"] = all(verdict[arm].values())
    return verdict


def retention(sessions, arms=ARMS):
    out = {}
    for arm in arms:
        done = [s for s, _ in sessions]
        total = sum(len(s["runs"]) for s in done)
        kept = sum(len(s["arms"][arm]["kept_runs"]) for s in done)
        frames = [sum(int(a[f"{arm}_censor{i}"].sum()) for i in s["arms"][arm]["kept_runs"]) for s, a in sessions]
        out[arm] = {"runs_kept": kept, "runs_total": total,
                    "sessions_losing_a_run": sum(len(s["arms"][arm]["kept_runs"]) < len(s["runs"]) for s in done),
                    "sessions_losing_all": sum(not s["arms"][arm]["kept_runs"] for s in done),
                    "median_kept_frames": float(np.median(frames)) if frames else None}  # fmt: skip
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sessions-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--margins", type=Path, help="anchors.py output. Without it, no decision is made")
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=20261103)
    args = ap.parse_args(argv)
    loaded = [load_session(p) for p in sorted(args.sessions_dir.glob("*.npz"))]
    sessions = [(s, a) for s, a in loaded if "skipped" not in s]
    report = {"sessions_loaded": len(loaded), "sessions_skipped": len(loaded) - len(sessions),
              "retention": retention(sessions)}  # fmt: skip
    if sessions:
        distances = metrics.edge_distances(sessions[0][1]["centroids"])

        def own_runs(summary, arm):
            return summary["arms"][arm]["kept_runs"]

        def shared_runs(summary, arm):
            return sorted(set.intersection(*(set(summary["arms"][a]["kept_runs"]) for a in ARMS)))

        report["all_data"] = evaluate(collect(sessions, own_runs), distances, args.n_boot, args.seed)
        report["common_runs"] = evaluate(collect(sessions, shared_runs), distances, args.n_boot, args.seed)
        if args.margins and "arms" in report["all_data"] and "arms" in report["common_runs"]:
            report["decision"] = decide(report, json.loads(args.margins.read_text()))
    args.out.write_text(json.dumps(report, indent=2))
    print(f"wrote {args.out}: {report['sessions_loaded']} sessions, {report['sessions_skipped']} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
