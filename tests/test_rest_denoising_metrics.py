"""Known-answer tests for benchmarks/rest_denoising. No AFNI, and all data is synthetic."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("scipy")
pytest.importorskip("nibabel")

BENCH = Path(__file__).resolve().parents[1] / "benchmarks" / "rest_denoising"
sys.path.insert(0, str(BENCH))

import analyze  # noqa: E402
import anchors  # noqa: E402
import draw_sample  # noqa: E402
import metrics  # noqa: E402
import run_session  # noqa: E402


def two_halves(n, edges, signal_var, noise_var, rng):
    stable = rng.normal(0, np.sqrt(signal_var), (n, edges))
    return (stable + rng.normal(0, np.sqrt(noise_var), (n, edges)),
            stable + rng.normal(0, np.sqrt(noise_var), (n, edges)))  # fmt: skip


def test_session_fc_recovers_a_planted_correlation():
    rng = np.random.default_rng(0)
    shared = rng.normal(size=(5000, 1))
    series = np.hstack([shared + rng.normal(size=(5000, 1)), shared + rng.normal(size=(5000, 1)),
                        rng.normal(size=(5000, 1))])  # fmt: skip
    z = metrics.session_fc([series], [np.ones(5000, bool)])
    assert np.tanh(z) == pytest.approx([0.5, 0.0, 0.0], abs=0.04)


def test_session_fc_ignores_censored_frames_and_run_offsets():
    rng = np.random.default_rng(1)
    a, b = rng.normal(size=(400, 3)), rng.normal(size=(400, 3))
    keep = np.ones(400, bool)
    keep[::7] = False
    dirty = a.copy()
    dirty[~keep] = 1e6
    expected = metrics.session_fc([a, b], [keep, keep])
    assert metrics.session_fc([dirty, b + 500], [keep, keep]) == pytest.approx(expected)


def test_a_silent_parcel_gives_nan_edges_only():
    series = np.random.default_rng(2).normal(size=(100, 3))
    series[:, 2] = 0
    z = metrics.session_fc([series], [np.ones(100, bool)])
    assert np.isfinite(z[0]) and np.isnan(z[1:]).all()


@pytest.mark.parametrize("runs, expected", [([0, 1, 2, 3], ([0, 2], [1, 3])), ([0, 3, 2], ([0, 3], [2])), ([1], None), ([], None)])
def test_split_runs(runs, expected):
    assert metrics.split_runs(runs) == expected


@pytest.mark.parametrize("signal, noise, icc", [(1.0, 1.0, 0.5), (3.0, 1.0, 0.75), (1.0, 3.0, 0.25)])
def test_edgewise_icc_matches_the_variance_ratio(signal, noise, icc):
    a, b = two_halves(2000, 200, signal, noise, np.random.default_rng(3))
    assert np.median(metrics.edgewise_icc(a, b)) == pytest.approx(icc, abs=0.03)


def test_fingerprint_accuracy_separates_stable_subjects_from_noise():
    rng = np.random.default_rng(4)
    assert metrics.fingerprint_accuracy(*two_halves(50, 2000, 1, 1, rng)) == 1.0
    assert metrics.fingerprint_accuracy(*two_halves(50, 2000, 0, 1, rng)) < 0.2


def test_qc_fc_finds_planted_motion_and_controls_for_make():
    rng = np.random.default_rng(5)
    n = 2000
    fd = rng.normal(size=n)
    fc = rng.normal(size=(n, 2))
    fc[:, 0] += 0.5 * fd
    assert metrics.qc_fc(fc, fd, np.empty((n, 0)))[0][0] == pytest.approx(0.447, abs=0.05)
    # An edge tied to make alone looks motion-linked until make is a covariate.
    make = rng.integers(0, 2, n).astype(float)
    fd2, fc2 = fd + 3 * make, rng.normal(size=(n, 1))
    fc2[:, 0] += 3 * make
    assert abs(metrics.qc_fc(fc2, fd2, np.empty((n, 0)))[0][0]) > 0.5
    assert abs(metrics.qc_fc(fc2, fd2, make[:, None])[0][0]) < 0.08


def test_fdr_fraction_matches_benjamini_hochberg():
    p = np.array([0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216, np.nan])
    assert metrics.fdr_fraction(p) == pytest.approx(0.2)
    assert metrics.fdr_fraction(np.array([0.5, 0.9])) == 0.0


def test_distance_dependence_detects_a_monotonic_link():
    distances = np.arange(100.0)
    assert metrics.distance_dependence(-(distances**3), distances) == pytest.approx(-1.0)


def test_bootstrap_interval_covers_a_known_difference():
    rng = np.random.default_rng(6)
    x = rng.normal(0.3, 1.0, 2000)
    low, high = metrics.bootstrap_difference(lambda idx: x[idx].mean(), 2000, 300, 0)
    assert low < 0.3 < high and high - low < 0.2


def _session(index, rng, *, lose_run, make):
    """One saved session where every arm shares stable FC, and only `bandpass` can lose a run."""
    stable = rng.normal(size=(4, 4)) @ np.diag([1.0, 0.8, 0.6, 0.4])
    arrays = {"centroids": np.arange(12.0).reshape(4, 3)}
    runs = {arm: [0, 1, 2, 3] for arm in analyze.ARMS}
    if lose_run:
        runs["bandpass"] = [0, 1, 3]
    for arm in analyze.ARMS:
        for i in range(4):
            arrays[f"{arm}_censor{i}"] = np.ones(200, np.int8)
            if i in runs[arm]:
                arrays[f"{arm}_series{i}"] = rng.normal(size=(200, 4)) @ stable + 0.2 * rng.normal(size=(200, 4))
    summary = {"runs": ["a", "b", "c", "d"], "mean_fd": list(rng.uniform(0.1, 0.4, 4)), "n_frames": [200] * 4,
               "make": make, "index": index,
               "arms": {arm: {"kept_runs": runs[arm], "exit_code": 0} for arm in analyze.ARMS}}  # fmt: skip
    return summary, arrays


def test_analyze_end_to_end_reports_loss_and_decides(tmp_path):
    rng = np.random.default_rng(7)
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    for i in range(30):
        summary, arrays = _session(i, rng, lose_run=i % 3 == 0, make="GE" if i % 2 else "Siemens")
        np.savez_compressed(sessions / f"{i:05d}.npz", summary=json.dumps(summary), **arrays)
    skipped = sessions / "99999.npz"
    np.savez_compressed(skipped, summary=json.dumps({"skipped": "probseg-pending"}))
    out = tmp_path / "report.json"
    margins = tmp_path / "margins.json"
    margins.write_text(json.dumps({"icc": 0.05, "qc_fc": 0.05, "qc_fc_all_data": 0.05}))
    args = ["--sessions-dir", str(sessions), "--out", str(out), "--n-boot", "20", "--margins", str(margins)]
    assert analyze.main(args) == 0
    report = json.loads(out.read_text())
    assert report["sessions_skipped"] == 1
    assert report["retention"]["bandpass"] == {"runs_kept": 110, "runs_total": 120, "sessions_losing_a_run": 10,
                                               "sessions_losing_all": 0, "median_kept_frames": 800.0}  # fmt: skip
    assert report["retention"]["highpass"]["runs_kept"] == 120
    assert report["all_data"]["n_sessions"] == 30
    assert set(report["decision"]) == {"sequenced", "highpass", "anchor_9p"}
    assert "motion_link_not_worse_on_all_data" in report["decision"]["highpass"]
    assert "sub-" not in out.read_text()


def test_no_margins_means_no_decision(tmp_path):
    rng = np.random.default_rng(8)
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    for i in range(12):
        summary, arrays = _session(i, rng, lose_run=False, make="GE")
        np.savez_compressed(sessions / f"{i:05d}.npz", summary=json.dumps(summary), **arrays)
    out = tmp_path / "report.json"
    assert analyze.main(["--sessions-dir", str(sessions), "--out", str(out), "--n-boot", "5"]) == 0
    assert "decision" not in json.loads(out.read_text())


def _arm(icc, qc, icc_ci=None, qc_ci=None):
    arm = {"median_edge_icc": icc, "median_abs_qc_fc": qc}
    if icc_ci:
        arm.update(icc_minus_reference_ci=icc_ci, qc_fc_minus_reference_ci=qc_ci)
    return arm


def test_final_margins_use_resolution_and_ignore_the_spread():
    report = {"n_sessions": 75, "arms": {"bandpass": _arm(0.2, 0.06),
                                         "anchor_9p": _arm(0.3, 0.05, (0.08, 0.12), (-0.02, 0.0))}}  # fmt: skip
    margins = anchors.final_margins(report)
    assert margins["icc"] == pytest.approx(0.01)  # Half-width 0.02, at 75 then 300 sessions
    assert margins["qc_fc"] == pytest.approx(0.005)
    assert margins["qc_fc_all_data"] == pytest.approx(0.01 * np.sqrt(75 / 200))
    assert margins["icc_spread_9p_minus_production"] == pytest.approx(0.1)


def _pair(icc_ci, qc_ci):
    return {"icc_minus_reference_ci": icc_ci, "qc_fc_minus_reference_ci": qc_ci}


@pytest.mark.parametrize("common, whole, failed", [
    (_pair((0.0, 0.1), (-0.1, 0.0)), _pair((0.01, 0.1), (-0.1, 0.0)), None),
    (_pair((-0.02, 0.1), (-0.1, 0.0)), _pair((0.01, 0.1), (-0.1, 0.0)), "reliability_not_worse_on_common_runs"),
    (_pair((0.0, 0.1), (-0.1, 0.03)), _pair((0.01, 0.1), (-0.1, 0.0)), "motion_link_not_worse_on_common_runs"),
    (_pair((0.0, 0.1), (-0.1, 0.0)), _pair((-0.01, 0.1), (-0.1, 0.0)), "reliability_better_on_all_data"),
    (_pair((0.0, 0.1), (-0.1, 0.0)), _pair((0.01, 0.1), (-0.1, 0.03)), "motion_link_not_worse_on_all_data"),
])  # fmt: skip
def test_decision_requires_all_four_rules(common, whole, failed):
    arms = analyze.ARMS[1:]
    report = {"common_runs": {"arms": dict.fromkeys(arms, common)}, "all_data": {"arms": dict.fromkeys(arms, whole)}}
    verdict = analyze.decide(report, {"icc": 0.01, "qc_fc": 0.02, "qc_fc_all_data": 0.02})["highpass"]
    assert verdict["passes"] is (failed is None)
    if failed:
        assert verdict[failed] is False


def test_anchors_write_margins_and_refuse_test_arms(tmp_path):
    rng = np.random.default_rng(9)
    sessions = tmp_path / "anchor"
    sessions.mkdir()
    for i in range(20):
        summary, arrays = _session(i, rng, lose_run=False, make="GE" if i % 2 else "Siemens")
        keep = {k: v for k, v in arrays.items() if not k.startswith(("sequenced_", "highpass_"))}
        for key, value in arrays.items():
            if key.startswith("bandpass_censor"):
                keep[key.replace("bandpass_", "anchor_9p_")] = value
            elif key.startswith("bandpass_series"):
                keep[key.replace("bandpass_", "anchor_9p_")] = value + 0.3 * rng.normal(size=value.shape)
        summary["arms"] = {"bandpass": summary["arms"]["bandpass"], "anchor_9p": summary["arms"]["bandpass"]}
        np.savez_compressed(sessions / f"{i:05d}.npz", summary=json.dumps(summary), **keep)
    out = tmp_path / "margins.json"
    assert anchors.main(["--sessions-dir", str(sessions), "--out", str(out), "--n-boot", "20"]) == 0
    margins = json.loads(out.read_text())
    assert margins["icc"] > 0 and margins["qc_fc_all_data"] > margins["qc_fc"] > 0

    wrong = tmp_path / "wrong"
    wrong.mkdir()
    summary, arrays = _session(0, rng, lose_run=False, make="GE")
    np.savez_compressed(wrong / "00000.npz", summary=json.dumps(summary), **arrays)
    with pytest.raises(SystemExit, match="arms under test"):
        anchors.main(["--sessions-dir", str(wrong), "--out", str(tmp_path / "x.json")])


@pytest.mark.parametrize("arm", sorted(run_session.ARMS))
def test_every_arm_passes_the_packages_config_validation(arm, tmp_path, logger):
    from fmri_first_level_proc.config import load_and_validate
    import yaml

    files = {}
    for key in ("scan_paths", "motion_paths", "CSF_paths", "WM_paths", "GS_paths"):
        path = tmp_path / f"{key}.nii.gz"
        path.write_text("x")
        files[key] = [str(path)]
    atlas = tmp_path / "atlas.nii.gz"
    atlas.write_text("x")
    block = run_session.arm_block(arm, files, tmp_path / "out")
    config = tmp_path / "c.yaml"
    config.write_text(yaml.safe_dump({"global": {"num_cores": 1, "tr": 0.8, "template_path": str(atlas),
                                                 "force_diff_atlas": True}, "analyses": [block]}))  # fmt: skip
    (resolved,) = load_and_validate(str(config))
    assert resolved.keep_run_res_dtseries is True
    if arm == "anchor_9p":
        assert resolved.motion_deriv_degree == 1 and resolved.use_tissue_derivs is False
    if arm == "highpass":
        assert resolved.bandpass == [0.01, 99.0]


def test_anchor_and_test_slices_share_no_subject():
    sessions = [f"sub-{i:04d}" for i in range(1000)]
    makes = dict.fromkeys(sessions, "GE")
    anchor = draw_sample.choose(sessions, makes, 200, 7)
    test = draw_sample.choose(sessions, makes, 444, 7, skip=200)
    assert len(anchor) == 200 and len(test) == 444 and not set(anchor) & set(test)
    assert anchor == draw_sample.choose(list(reversed(sessions)), makes, 200, 7)
    assert set(anchor) <= set(sessions)
