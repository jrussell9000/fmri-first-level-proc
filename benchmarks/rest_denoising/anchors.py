"""Set the comparison's margins by resolution, from production and 9P, without the other arms.

    anchors.py --sessions-dir DIR --out margins.json

Every margin is the half-width of the paired interval on production minus 9P, rescaled to the
number of usable test sessions. The spread between the two is recorded but sets no margin:
see "Margins" in README.md for why.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import analyze  # noqa: E402
import metrics  # noqa: E402

ANCHOR = "anchor_9p"
ARMS = (analyze.REFERENCE, ANCHOR)
TEST_USABLE = 300  # 444 drawn, at the 135 of 200 usable in the margin run
ALL_DATA_CHECK_USABLE = 200  # The size the all-data margin was approved at


def half_width(interval, n_anchor, n_test):
    """The interval's half-width, which shrinks with the square root of the session count."""
    return float((interval[1] - interval[0]) / 2 * np.sqrt(n_anchor / n_test))


def final_margins(anchor):
    """Margins from the anchor report's intervals, plus each spread as a record."""
    n = anchor["n_sessions"]
    reference, nine_p = anchor["arms"][analyze.REFERENCE], anchor["arms"][ANCHOR]
    icc_ci, qc_ci = nine_p["icc_minus_reference_ci"], nine_p["qc_fc_minus_reference_ci"]
    return {"icc": half_width(icc_ci, n, TEST_USABLE),
            "qc_fc": half_width(qc_ci, n, TEST_USABLE),
            "qc_fc_all_data": half_width(qc_ci, n, ALL_DATA_CHECK_USABLE),
            "icc_spread_9p_minus_production": nine_p["median_edge_icc"] - reference["median_edge_icc"],
            "qc_fc_spread_9p_minus_production": nine_p["median_abs_qc_fc"] - reference["median_abs_qc_fc"]}  # fmt: skip


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sessions-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=20261103)
    args = ap.parse_args(argv)
    loaded = [analyze.load_session(p) for p in sorted(args.sessions_dir.glob("*.npz"))]
    sessions = [(s, a) for s, a in loaded if "skipped" not in s]
    if set(ARMS) != set(sessions[0][0]["arms"]):
        raise SystemExit(f"anchor sessions must hold exactly {ARMS}, not the arms under test")

    def shared_runs(summary, arm):
        return sorted(set.intersection(*(set(summary["arms"][a]["kept_runs"]) for a in ARMS)))

    rows = analyze.collect(sessions, shared_runs, ARMS)
    distances = metrics.edge_distances(sessions[0][1]["centroids"])
    report = analyze.evaluate(rows, distances, args.n_boot, args.seed, ARMS)
    output = {**final_margins(report), "sessions_loaded": len(loaded), "sessions_skipped": len(loaded) - len(sessions),
              "retention": analyze.retention(sessions, ARMS), "anchor": report}  # fmt: skip
    args.out.write_text(json.dumps(output, indent=2))
    print(f"wrote {args.out}: icc {output['icc']:.4f}, qc_fc {output['qc_fc']:.4f}, {report['n_sessions']} sessions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
