"""Pipelines at production settings on real ABCD timing, against known signal.

Opt-in like test_real_afni.py: run with ``-m afni`` where AFNI is installed.

Tests marked ``known_defect`` state correct behaviour and fail today. They are strict
xfails, so fixing a defect turns its test into a failure until the marker is removed.
"""

import copy
import logging
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

pytest.importorskip("nibabel")
pytest.importorskip("scipy")

import abcd_timed as fx  # noqa: E402
from fmri_first_level_proc import DISPATCH, runtime  # noqa: E402
from fmri_first_level_proc.abcd import staging  # noqa: E402
from fmri_first_level_proc.config import load_and_validate  # noqa: E402
from fmri_first_level_proc.preprocessing import create_censor_file, notch_filter_motion  # noqa: E402

pytestmark = [
    pytest.mark.afni,
    pytest.mark.skipif(shutil.which("3dDeconvolve") is None, reason="AFNI not installed"),
]

TEMPLATE = Path(runtime.__file__).parent / "abcd" / "data" / "proc_config_final.yaml"


def known_defect(reason):
    return pytest.mark.xfail(strict=True, reason=reason)


@pytest.fixture(scope="module")
def session(tmp_path_factory):
    return fx.build_session(tmp_path_factory.mktemp("abcd_timed"))


def production_block(name):
    blocks = yaml.safe_load(TEMPLATE.read_text())["analyses"]
    return copy.deepcopy(next(b for b in blocks if b["name"] == name))


def _run(session, block, out, logger):
    block.update(out_dir=str(out), out_file_pre="s")
    block["extraction"]["extract_out_file_pre"] = "s_parc"
    if block.get("connectivity"):
        block["connectivity"]["conn_out_file_pre"] = "s_parc"
    cfg = {"global": {"tr": fx.TR, "num_cores": 2, "template_path": str(session.parcellation)}, "analyses": [block]}
    path = Path(out).with_suffix(".yaml")
    path.write_text(yaml.safe_dump(cfg))
    (resolved,) = load_and_validate(str(path))
    return DISPATCH[block["type"]](resolved, logger)


def _nv(path):
    return int(subprocess.run(["3dinfo", "-nv", str(path)], capture_output=True, text=True, check=True).stdout)


def _rest(session, paths, out, logger):
    block = production_block("rest_conn")
    block["paths"] = paths
    return _run(session, block, out, logger)


def _fz_to_r(mat):
    return np.tanh(mat)


@pytest.fixture(scope="module")
def module_logger():
    return logging.getLogger("fmri_first_level_proc.tests")


@pytest.fixture(scope="module")
def act(session, tmp_path_factory, module_logger):
    block = production_block("nback_act")
    block["paths"] = session.nback
    out = tmp_path_factory.mktemp("act") / "act"
    return out, _run(session, block, out, module_logger)


@pytest.fixture(scope="module")
def rest(session, tmp_path_factory, module_logger):
    out = tmp_path_factory.mktemp("rest") / "rest"
    return out, _rest(session, session.rest, out, module_logger)


@pytest.fixture(scope="module")
def rest_high(session, tmp_path_factory, module_logger):
    out = tmp_path_factory.mktemp("rest_high") / "rest"
    return out, _rest(session, session.rest_high_motion, out, module_logger)


# ---------------------------------------------------------------------------
# The fixture itself matches ABCD
# ---------------------------------------------------------------------------


def test_scans_have_abcd_timing(session):
    info = subprocess.run(["3dinfo", "-tr", "-nt", session.rest["scan_paths"][0]],
                          capture_output=True, text=True, check=True).stdout.split()  # fmt: skip
    assert float(info[0]) == pytest.approx(fx.TR)
    assert int(info[1]) == fx.REST_FRAMES
    assert _nv(session.nback["scan_path"]) == fx.NBACK_RUNS * fx.NBACK_FRAMES


def test_frame_counts_match_the_stager():
    assert (fx.NBACK_FRAMES, fx.NBACK_FRAMES_GE) == (staging.KEPT_FRAMES, staging.KEPT_FRAMES_GE)


def test_events_have_abcd_structure(session):
    events = pd.read_csv(session.nback["task_timing_path"], sep="\t")
    counts = events.trial_type.value_counts()
    for load in (0, 2):
        for stimulus in fx.STIMULI:
            assert counts[f"{load}_back_{stimulus}"] == 2 * fx.TRIALS_PER_BLOCK
    assert counts["instruction"] == 8  # 4 cues per run on 2-back blocks
    for stimulus in fx.STIMULI:
        assert counts[stimulus] == 2  # 0-back cues
    assert events.onset.max() + fx.TRIAL_DURATION < fx.NBACK_RUNS * fx.NBACK_FRAMES * fx.TR


@pytest.mark.parametrize("jerks, low, high", [(6, 1, fx.AFNI_MAX_CENSORED), (20, fx.AFNI_MAX_CENSORED + 1, 0.25 * fx.REST_FRAMES)])
def test_motion_censoring_matches_real_runs(tmp_path, logger, jerks, low, high):
    """Under production notch and threshold, one run censors like a typical run, one like a high-motion run."""
    path = tmp_path / "motion.txt"
    np.savetxt(path, fx.motion(fx.REST_FRAMES, jerks, np.random.default_rng(1)), fmt="%.6f")
    notched = notch_filter_motion(path, fx.TR, [0.31, 0.43], tmp_path, "s", "r", logger)
    censor = create_censor_file(notched, fx.FD_THRESHOLD, False, tmp_path, "s", "r", logger)
    n_censored = int((np.loadtxt(censor) == 0).sum())
    assert low <= n_censored <= high


# ---------------------------------------------------------------------------
# What works
# ---------------------------------------------------------------------------


def test_task_act_recovers_the_load_effect(session, act):
    out, result = act
    assert result.status == "success", result.warnings
    coef = pd.read_csv(out / "s_parc_Coef_parcellated.csv", index_col=0).loc["ave_tback-ave_zback"]
    for label, expected in session.truth.load_effect_psc.items():
        assert coef[f"ROI_{label}"] == pytest.approx(expected, abs=0.15)


def test_task_act_handles_the_ge_frame_count(session, tmp_path, logger):
    """GE keeps one more n-back frame per run, which moves run 2's onsets by 0.8 s."""
    block = production_block("nback_act")
    block["paths"] = session.nback_ge
    out = tmp_path / "act"
    result = _run(session, block, out, logger)
    assert result.status == "success", result.warnings
    assert _nv(session.nback_ge["scan_path"]) == fx.NBACK_RUNS * fx.NBACK_FRAMES_GE
    coef = pd.read_csv(out / "s_parc_Coef_parcellated.csv", index_col=0).loc["ave_tback-ave_zback"]
    for label, expected in session.truth.load_effect_psc.items():
        assert coef[f"ROI_{label}"] == pytest.approx(expected, abs=0.15)


def test_task_conn_gives_one_beta_per_trial(session, tmp_path, logger):
    block = production_block("nback_conn")
    block["paths"] = session.nback
    out = tmp_path / "conn"
    result = _run(session, block, out, logger)
    assert result.status == "success", result.warnings
    assert _nv(out / "s_concat_bseries_2_back_place.nii.gz") == 2 * fx.TRIALS_PER_BLOCK
    assert np.loadtxt(out / "s_parc_2_back_place_fishZ_mat.txt", delimiter="\t").shape == (3, 3)


def test_rest_keeps_every_low_motion_run_and_recovers_connectivity(session, rest):
    out, result = rest
    assert result.status == "success", result.warnings
    assert _nv(out / "s_concat_residual_dtseries.nii.gz") == fx.REST_RUNS * fx.REST_FRAMES
    r = _fz_to_r(np.loadtxt(out / "s_parc_fishZ_mat.txt", delimiter="\t"))
    for (a, b), expected in session.truth.rest_r.items():
        assert r[a - 1, b - 1] == pytest.approx(expected, abs=0.2)


def test_real_sized_drift_does_not_change_connectivity(session, tmp_path, logger):
    """Drift at the 90th percentile of real runs."""
    result = _rest(session, session.rest_drift, tmp_path / "rest", logger)
    assert result.status == "success", result.warnings
    r = _fz_to_r(np.loadtxt(tmp_path / "rest" / "s_parc_fishZ_mat.txt", delimiter="\t"))
    for (a, b), expected in session.truth.rest_r.items():
        assert r[a - 1, b - 1] == pytest.approx(expected, abs=0.2)


# ---------------------------------------------------------------------------
# Known defects: each test states correct behaviour
# ---------------------------------------------------------------------------


def test_a_run_past_afnis_censoring_limit_is_reported(rest_high):
    out, result = rest_high
    excluded = result.qc_summary["excluded_runs"]
    assert excluded and {r["reason"] for r in excluded} == {"too-few-frames"}
    assert result.status == "warning"
    assert sum(w["code"] == "RUN_SKIPPED" for w in result.warnings) == len(excluded)
    assert _nv(out / "s_concat_residual_dtseries.nii.gz") == (fx.REST_RUNS - len(excluded)) * fx.REST_FRAMES


@known_defect("per_run_dof ignores the columns that the bandpass adds")
def test_rest_dof_counts_the_bandpass(rest):
    _, result = rest
    frequencies = np.fft.rfftfreq(fx.REST_FRAMES, fx.TR)
    bandpass_dimensions = 2 * int(((frequencies >= 0.01) & (frequencies <= 0.1)).sum())
    assert max(result.qc_summary["per_run_dof"]) <= bandpass_dimensions


def test_task_model_has_a_baseline_per_run(act):
    out, _ = act
    labels = next(ln for ln in (out / "s_concat_bucket_stats.xmat.1D").read_text().splitlines() if "ColumnLabels" in ln)
    assert "Run#2Pol#0" in labels


def test_the_first_frame_of_a_run_is_not_censored_for_the_step_between_runs(act):
    out, _ = act
    censor = np.loadtxt(out / "s_concat_censor.1D")
    assert censor[fx.NBACK_FRAMES] == 1


def test_qc_dof_matches_the_design_matrix(act):
    out, result = act
    matrix = np.loadtxt(out / "s_concat_bucket_stats.xmat.1D", comments="#", ndmin=2)
    kept = int((np.loadtxt(out / "s_concat_censor.1D") == 1).sum())
    assert result.qc_summary["dof"] == kept - matrix.shape[1]


@known_defect("task_act uses OLS, so autocorrelated noise inflates t statistics")
def test_null_task_data_keeps_the_nominal_false_positive_rate(session, tmp_path, logger):
    block = production_block("nback_act")
    block["paths"] = session.nback_null
    out = tmp_path / "act"
    result = _run(session, block, out, logger)
    assert result.status == "success", result.warnings
    labels = subprocess.run(["3dinfo", "-label", out / "s_concat_bucket_stats.nii.gz"],
                            capture_output=True, text=True, check=True).stdout.strip().split("|")  # fmt: skip
    index = labels.index("ave_tback-ave_zback_GLT#0_Tstat")
    values = subprocess.run(["3dmaskdump", "-noijk", f"{out / 's_concat_bucket_stats.nii.gz'}[{index}]"],
                            capture_output=True, text=True, check=True).stdout.split()  # fmt: skip
    t = np.array(values, dtype=float)
    assert np.mean(np.abs(t) > 1.96) <= 0.08
