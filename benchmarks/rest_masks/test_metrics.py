"""Known-answer tests for benchmarks/rest_masks. No AFNI, and all data is synthetic."""

import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("scipy")

sys.path.insert(0, str(Path(__file__).resolve().parent))

import analyze  # noqa: E402
import metrics  # noqa: E402

MARGINS = {"icc": 0.007, "qc_fc": 0.002}


def result(icc=(0.01, 0.02), qc=(-0.002, 0.001), gm=(-0.1, 0.1), control=(-0.2, -0.1)):
    return {
        "candidate_minus_reference_ci": {"icc": icc, "qc_fc": qc, "global_motion": gm},
        "control_minus_candidate_ci": {"global_motion": control},
    }


def test_candidate_replaces_the_reference_only_when_all_rules_hold():
    decision = analyze.decide(result(), MARGINS)
    assert decision["use_candidate"] and decision["measure_discriminates"]


@pytest.mark.parametrize("kwargs, rule", [
    ({"icc": (-0.01, 0.02)}, "reliability_not_worse"),
    ({"qc": (-0.001, 0.003)}, "motion_link_not_worse"),
    ({"gm": (0.01, 0.2)}, "global_motion_not_clearly_worse"),
    ({"icc": (-0.001, 0.02)}, "reliability_better"),
])  # fmt: skip
def test_each_rule_alone_keeps_the_reference(kwargs, rule):
    decision = analyze.decide(result(**kwargs), MARGINS)
    assert not decision[rule] and not decision["use_candidate"]


def test_a_control_with_no_effect_means_the_measure_cannot_discriminate():
    assert not analyze.decide(result(control=(-0.1, 0.05)), MARGINS)["measure_discriminates"]


def test_mean_fc_motion_finds_a_shift_that_follows_motion():
    rng = np.random.default_rng(0)
    fd = rng.normal(size=200)
    shifted = rng.normal(size=(200, 50)) + 2 * fd[:, None]
    assert metrics.mean_fc_motion(shifted, fd, np.empty((200, 0))) > 0.9
    assert abs(metrics.mean_fc_motion(rng.normal(size=(200, 50)), fd, np.empty((200, 0)))) < 0.2


def test_network_contrast_on_known_edges():
    networks = np.array(["a", "a", "b", ""])
    # Upper-triangle order: (0,1) within, (0,2) between, (0,3) none, (1,2) between, (1,3), (2,3) none.
    fc = np.array([[1.0, 0.25, 9.0, 0.25, 9.0, 9.0]])
    assert metrics.network_contrast(fc, networks) == pytest.approx(0.75)


def test_edgewise_icc_is_one_for_identical_halves_and_near_zero_for_unrelated():
    rng = np.random.default_rng(1)
    a = rng.normal(size=(300, 20))
    assert metrics.edgewise_icc(a, a) == pytest.approx(1.0)
    assert abs(np.median(metrics.edgewise_icc(a, rng.normal(size=(300, 20))))) < 0.1


def test_qc_fc_recovers_a_known_correlation_and_controls_covariates():
    rng = np.random.default_rng(2)
    fd = rng.normal(size=5000)
    fc = (0.6 * fd + 0.8 * rng.normal(size=5000))[:, None]
    r, p = metrics.qc_fc(fc, fd, np.empty((5000, 0)))
    assert r[0] == pytest.approx(0.6, abs=0.03) and p[0] < 1e-10
    make = (rng.random(5000) > 0.5).astype(float)[:, None]
    r2, _ = metrics.qc_fc(rng.normal(size=(5000, 1)) + 5 * make, fd + 5 * make[:, 0], make)
    assert abs(r2[0]) < 0.05


def test_batched_bootstrap_matches_the_per_draw_loop():
    rng = np.random.default_rng(4)
    n, edges, n_boot = 40, 30, 25
    a, b = rng.normal(size=(n, edges)), rng.normal(size=(n, edges))
    fd = rng.normal(size=n)
    make = np.zeros((n, 2))
    make[:3, 0] = 1  # a rare level, which some draws leave out
    make[3:20, 1] = 1
    counts = metrics.bootstrap_counts(n, n_boot, 7)
    gen = np.random.default_rng(7)
    picks = [gen.integers(0, n, n) for _ in range(n_boot)]
    assert any(c[:3].sum() == 0 for c in counts)
    loop_icc = [np.nanmedian(metrics.edgewise_icc(a[i], b[i])) for i in picks]
    loop_qc = np.stack([metrics.qc_fc(a[i], fd[i], make[i])[0] for i in picks])
    assert metrics.batched_median_icc(a, b, counts, chunk=10) == pytest.approx(loop_icc, abs=1e-10)
    assert metrics.batched_qc_fc(a, fd, make, counts, chunk=10) == pytest.approx(loop_qc, abs=1e-10)


def test_session_fc_uses_only_kept_frames():
    t = np.arange(10.0)
    series = np.column_stack([t, t])
    series[9, 1] = -1000  # a censored outlier
    keep = np.ones(10, bool)
    keep[9] = False
    assert metrics.session_fc([series], [keep])[0] == pytest.approx(4.0)


def test_collect_uses_runs_every_arm_kept_and_a_lone_run_counts_for_motion_only():
    frames, parcels = 200, 3
    rng = np.random.default_rng(3)
    arrays, arms = {}, {}
    for arm in analyze.ARMS:
        for i in range(4):
            arrays[f"{arm}_series{i}"] = rng.normal(size=(frames, parcels))
            arrays[f"{arm}_censor{i}"] = np.ones(frames, np.int8)
        arms[arm] = {"kept_runs": [0, 1, 2, 3]}
    arms["ours_on"] = {"kept_runs": [0, 2]}
    summary = {"make": "GE", "mean_fd": [0.1, 9.0, 0.3, 9.0], "arms": arms}
    [(make, per_arm)] = analyze.collect([(summary, arrays)])
    assert make == "GE" and per_arm["taylor_off"][3] == pytest.approx(0.2)  # runs 0 and 2 only
    assert per_arm["taylor_off"][0] is not None
    arms["ours_on"] = {"kept_runs": [0]}
    [(_, lone)] = analyze.collect([(summary, arrays)])
    assert lone["taylor_off"][0] is None and lone["taylor_off"][2] is not None
    arms["ours_on"] = {"kept_runs": []}
    assert analyze.collect([(summary, arrays)]) == []
