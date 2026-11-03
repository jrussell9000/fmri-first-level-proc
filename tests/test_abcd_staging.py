"""Tests for abcd/staging.py. AFNI and the CLI are faked, because these tests are about
what staging prepares and records, not about what AFNI computes."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

nib = pytest.importorskip("nibabel")
pytest.importorskip("scipy")

from fmri_first_level_proc.abcd import staging as sfl  # noqa: E402

TR = 0.8
SUBJ, SES = "sub-TEST0001", "ses-00A"
TEMPLATE = sfl.PROC_TEMPLATE
ATLAS = "/atlas/parcels.nii.gz"


# ---------------------------------------------------------------------------
# NSS, motion
# ---------------------------------------------------------------------------


def confounds(n_frames: int, n_nss: int, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    cols = {c: rng.normal(size=n_frames) for c in reversed(sfl.MOTION_BASE)}  # odd order
    cols.update({f"non_steady_state_outlier_{i:02d}": np.eye(n_frames)[i] for i in range(n_nss)})
    cols["global_signal"] = np.arange(n_frames, dtype=float) + 100.0
    return pd.DataFrame(cols)


def test_nss_count_is_the_outlier_column_count():
    assert sfl.nss_count(confounds(20, 8)) == 8


def test_global_signal_is_the_trimmed_confound():
    """Rest keeps the retired orchestrator's GSR: global_signal, NSS-trimmed."""
    np.testing.assert_array_equal(sfl.global_signal(confounds(20, 8), 8), np.arange(8, 20) + 100.0)


def test_missing_global_signal_fails_the_run():
    with pytest.raises(sfl.SessionError, match="global_signal"):
        sfl.global_signal(confounds(20, 0).drop(columns="global_signal"), 0)


def test_no_nss_columns_means_no_trim():
    assert sfl.nss_count(confounds(20, 0)) == 0


def test_motion_is_translations_first_then_derivatives():
    df = confounds(20, 0)
    m = sfl.motion_matrix(df, 0)
    assert m.shape == (20, 12)
    np.testing.assert_allclose(m[:, :6], df[sfl.MOTION_BASE].to_numpy())
    np.testing.assert_allclose(m[1:, 6:], np.diff(df[sfl.MOTION_BASE].to_numpy(), axis=0))
    assert (m[0, 6:] == 0).all()


def test_motion_derivatives_come_from_the_untrimmed_series():
    """The orchestrator's order: diff, then trim; the first kept row is not 0."""
    df = confounds(20, 0)
    m = sfl.motion_matrix(df, 8)
    base = df[sfl.MOTION_BASE].to_numpy()
    assert m.shape == (12, 12)
    np.testing.assert_allclose(m[0, 6:], base[8] - base[7])


def test_an_isolated_nan_is_set_to_999():
    df = confounds(20, 0)
    df.loc[5, "trans_x"] = np.nan
    m = sfl.motion_matrix(df, 0)
    assert m[5, 0] == 999.0
    assert m[5, 6] == 999.0 and m[6, 6] == 999.0  # both derivative rows touching it


def test_an_all_nan_motion_column_fails():
    df = confounds(20, 0)
    df["rot_y"] = np.nan
    with pytest.raises(sfl.SessionError, match="rot_y"):
        sfl.motion_matrix(df, 0)


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def nback_events() -> pd.DataFrame:
    # As ABCD 7.0 ships them: quoted trial_type values.
    text = (
        "onset\tduration\tresponse_time\ttrial_type\n"
        '0.000\t6.400\t"n/a"\t"dummy"\n'
        '6.410\t2.890\t"n/a"\t"cue"\n'
        '9.410\t1.900\t"n/a"\t"0_back_posface"\n'
        '12.000\t1.900\t"n/a"\t"0_back_posface"\n'
        '30.000\t2.890\t"n/a"\t"cue"\n'
        '33.000\t1.900\t"n/a"\t"2_back_place"\n'
    )
    return pd.read_csv(io.StringIO(text), sep="\t")


def test_cue_relabel_matches_the_orchestrator():
    ev = sfl.fix_nback_cue_labels(nback_events())
    assert list(ev["trial_type"]) == [
        "dummy",
        "posface",
        "0_back_posface",
        "0_back_posface",
        "instruction",
        "2_back_place",
    ]


def test_a_cue_with_no_following_trial_fails_the_run():
    ev = nback_events().iloc[:2]
    with pytest.raises(sfl.SessionError, match="cue"):
        sfl.fix_nback_cue_labels(ev)


def test_staged_events_drop_dummy_and_cue_and_shift_onsets():
    ev, dropped = sfl.stage_events(nback_events(), 8, TR)
    assert list(ev.columns) == ["onset", "duration", "trial_type"]
    assert "dummy" not in set(ev["trial_type"]) and "cue" not in set(ev["trial_type"])
    # 9.41 - 8 * 0.8 = 3.01 (spec: "Trimmed inputs stay aligned")
    assert ev.loc[ev["trial_type"] == "0_back_posface", "onset"].iloc[0] == pytest.approx(3.01)
    # The 6.41 s cue (now "posface") lands at 0.01 s: kept.
    assert ev["onset"].iloc[0] == pytest.approx(0.01) and dropped == 0


def test_events_shifted_before_zero_are_dropped_and_counted():
    ev, dropped = sfl.stage_events(nback_events(), 9, TR)  # 9 * 0.8 = 7.2 s
    assert dropped == 1  # the 6.41 s cue
    assert (ev["onset"] >= 0).all()


def test_concatenated_onsets_are_offset_by_earlier_runs():
    first, _ = sfl.stage_events(nback_events(), 8, TR)
    second, _ = sfl.stage_events(nback_events(), 8, TR)
    cat = sfl.concat_events([(first, 362), (second, 362)], TR)
    run2 = cat.iloc[len(first) :]
    # 3.01 + 362 * 0.8 = 292.61 (spec: "Second-run onsets are offset")
    trial = run2.loc[run2["trial_type"] == "0_back_posface", "onset"].iloc[0]
    assert trial == pytest.approx(292.61)


# ---------------------------------------------------------------------------
# Tissue masks
# ---------------------------------------------------------------------------

# The real relationship (task 2.4): 1 mm RAS probseg, 2 mm BOLD with x and y
# flipped, centres offset half a millimetre so each 2 mm voxel covers 8 whole ones.
PROB_AFFINE = np.diag([1.0, 1.0, 1.0, 1.0])
REF_AFFINE = np.array([[-2.0, 0, 0, 6.5], [0, -2.0, 0, 6.5], [0, 0, 2.0, 0.5], [0, 0, 0, 1.0]])


def prob_img(data) -> nib.Nifti1Image:
    return nib.Nifti1Image(np.asarray(data, dtype=np.float32), PROB_AFFINE)


def ref_img(shape=(4, 4, 4), affine=REF_AFFINE, value=1) -> nib.Nifti1Image:
    return nib.Nifti1Image(np.full(shape, value, dtype=np.uint8), affine)


def brute_force_block_mean(prob: nib.Nifti1Image, ref: nib.Nifti1Image) -> np.ndarray:
    """World-coordinate reference: average prob at the 8 sub-centres of each ref voxel."""
    data = np.asarray(prob.dataobj)
    inv = np.linalg.inv(prob.affine)
    out = np.zeros(ref.shape[:3])
    for ijk in np.ndindex(ref.shape[:3]):
        centre = ref.affine @ [*ijk, 1]
        total = 0.0
        for d in np.array(np.meshgrid([-0.5, 0.5], [-0.5, 0.5], [-0.5, 0.5])).T.reshape(-1, 3):
            p = np.rint(inv @ [*(centre[:3] + d), 1])[:3].astype(int)
            if all(0 <= p[k] < data.shape[k] for k in range(3)):
                total += data[tuple(p)]
        out[ijk] = total / 8
    return out


def test_block_mean_matches_a_world_coordinate_reference():
    rng = np.random.default_rng(1)
    prob = prob_img(rng.random((8, 8, 9)))  # one slab outside the ref FOV, one short
    ref = ref_img(shape=(4, 4, 5))
    np.testing.assert_allclose(
        sfl.block_mean_to_grid(prob, ref), brute_force_block_mean(prob, ref), atol=1e-6
    )


def test_partial_volume_is_measured_not_sampled():
    data = np.zeros((8, 8, 8))
    data[0:2, 0:2, 0:2] = 1.0
    data[0, 0, 0] = 0.52  # 7 x 1.0 + 0.52 -> mean 0.94
    frac = sfl.block_mean_to_grid(prob_img(data), ref_img())
    # prob x/y {0,1} are ref index 3 (flipped axes); z {0,1} is ref index 0.
    assert frac[3, 3, 0] == pytest.approx(0.94)
    wm = np.ones((8, 8, 8))
    wm[0, 0, 0] = 0.52  # the same 0.94 block, inside an otherwise pure-WM volume
    masks, _, _ = build(wm=wm)
    assert not masks["WM"][3, 3, 0] and masks["WM"].sum() == 63


ONES, ZEROS = np.ones((8, 8, 8)), np.zeros((8, 8, 8))


def build(gm=ZEROS, wm=ONES, csf=ONES, label=ONES, ref=None, *, min_voxels=1):
    """tissue_masks_from_probseg on the 8^3 -> 4^3 test grids. The real floor
    (CSF_MIN_VOXELS = 100) exceeds a 64-voxel grid, so tests pass their own."""
    original = sfl.CSF_MIN_VOXELS
    sfl.CSF_MIN_VOXELS = min_voxels
    try:
        return sfl.tissue_masks_from_probseg(
            prob_img(gm), prob_img(wm), prob_img(csf), prob_img(label), ref or ref_img()
        )
    finally:
        sfl.CSF_MIN_VOXELS = original


def test_the_threshold_is_strictly_above_099_as_in_fmriprep():
    """niworkflows Binarize(thresh_low=0.99) keeps data > 0.99, not >= 0.99."""
    wm = np.ones((8, 8, 8))
    wm[0, 0, 0] = 0.92  # 7 x 1.0 + 0.92 -> mean exactly 0.99
    masks, _, _ = build(wm=wm)
    assert not masks["WM"][3, 3, 0] and masks["WM"][2, 2, 0]


def test_masks_land_on_the_bold_grid():
    masks, reason, threshold = build()
    assert reason is None and threshold == 0.99
    for mask in masks.values():
        assert mask.shape == (4, 4, 4) and mask.dtype == bool


def test_no_erosion_without_grey_matter():
    """fMRIPrep removes dilated GM instead of eroding, so with no GM nothing is lost."""
    masks, _, _ = build()
    assert masks["WM"].sum() == 64 and masks["CSF"].sum() == 64


def test_dilated_grey_matter_is_removed_from_wm_only():
    gm = np.zeros((8, 8, 8))
    gm[4, 4, 4] = 0.06  # one voxel just over the 0.05 GM threshold
    gm_low = np.zeros((8, 8, 8))
    gm_low[4, 4, 4] = 0.05  # at the threshold: not GM (fMRIPrep uses > 0.05)
    assert sfl.dilated_gm(prob_img(gm)).sum() == sfl.ball(3).sum()  # a whole radius-3 ball
    assert not sfl.dilated_gm(prob_img(gm_low)).any()
    masks, _, _ = build(gm=gm)
    assert masks["CSF"].sum() == 64  # CSF is not GM-masked
    assert 0 < masks["WM"].sum() < 64


def test_ball_matches_skimage_definition():
    b = sfl.ball(3)
    assert b.shape == (7, 7, 7) and b.sum() == 123 and b[3, 3, 3] and not b[0, 0, 0]


def test_csf_is_restricted_to_the_fastsurfer_label():
    """CSF probseg outside label-CSF_mask (brain-edge CSF) never enters the mask."""
    label = np.zeros((8, 8, 8))
    label[0:2, 0:2, 0:4] = 1  # two 2x2x2 blocks: ref (3, 3, 0) and (3, 3, 1)
    masks, reason, threshold = build(label=label)
    assert reason is None and threshold == 0.99
    assert masks["CSF"].sum() == 2 and masks["CSF"][3, 3, 0] and masks["CSF"][3, 3, 1]


def test_the_ladder_uses_the_first_rung_with_enough_voxels():
    csf = np.full((8, 8, 8), 0.95)  # every block 0.95: fails > 0.99, passes > 0.9
    masks, reason, threshold = build(csf=csf, min_voxels=64)
    assert reason is None and threshold == 0.9 and masks["CSF"].sum() == 64
    masks, reason, threshold = build(csf=np.full((8, 8, 8), 0.6), min_voxels=64)
    assert reason is None and threshold == 0.5


def test_below_the_last_rung_rest_is_skipped():
    masks, reason, threshold = build(csf=np.full((8, 8, 8), 0.4), min_voxels=1)
    assert masks == {} and reason == "csf-mask-too-small" and threshold is None


def test_the_real_floor_is_100_voxels():
    assert sfl.CSF_MIN_VOXELS == 100 and sfl.CSF_THRESHOLD_LADDER == (0.99, 0.9, 0.5)
    _, reason, _ = sfl.tissue_masks_from_probseg(
        prob_img(ZEROS), prob_img(ONES), prob_img(ONES), prob_img(ONES), ref_img()
    )
    assert reason == "csf-mask-too-small"  # a 64-voxel grid cannot reach 100


def test_an_empty_wm_mask_is_a_reason_not_a_regressor():
    masks, reason, _ = build(wm=ZEROS)
    assert masks == {} and reason == "empty-WM-mask"


def test_a_label_on_another_grid_is_refused():
    with pytest.raises(sfl.SessionError, match="one grid"):
        sfl.tissue_masks_from_probseg(
            prob_img(ZEROS), prob_img(ONES), prob_img(ONES), prob_img(np.ones((8, 8, 9))), ref_img()
        )


@pytest.mark.parametrize(
    "affine, match",
    [
        (REF_AFFINE + np.diag([0, 0, 0, 0]) + np.array([[0, 0, 0, 0.25]] + [[0] * 4] * 3), "nest"),
        (np.diag([1.0, 1.0, 1.0, 1.0]), "2:1"),
        (
            np.array([[0, -2.0, 0, 6.5], [-2.0, 0, 0, 6.5], [0, 0, 2.0, 0.5], [0, 0, 0, 1]]),
            "axis-aligned",
        ),
    ],
)
def test_grids_that_do_not_nest_are_refused(affine, match):
    with pytest.raises(sfl.SessionError, match=match):
        sfl.block_mean_to_grid(prob_img(np.ones((8, 8, 8))), ref_img(affine=affine))


# ---------------------------------------------------------------------------
# Config and CLI exits
# ---------------------------------------------------------------------------


def template() -> dict:
    return yaml.safe_load(TEMPLATE.read_text())


def test_fill_config_sets_prefixes_and_leaves_settings_alone(tmp_path):
    tmpl = template()
    paths = {"scan_path": "/x.nii.gz"}
    cfg = sfl.fill_config(tmpl, SUBJ, SES, {"nback_act": paths, "rest_conn": paths}, tmp_path, ATLAS)
    assert cfg["global"]["template_path"] == ATLAS
    names = [b["name"] for b in cfg["analyses"]]
    assert names == ["nback_act", "rest_conn"]  # nback_conn not staged -> dropped
    act = cfg["analyses"][0]
    assert act["out_file_pre"] == f"{SUBJ}_{SES}_nback"
    assert act["extraction"]["extract_out_file_pre"] == f"{SUBJ}_{SES}_nback_SchaeferTian"
    assert act["out_dir"] == str(tmp_path / "nback_act")
    rest = cfg["analyses"][1]
    assert rest["connectivity"]["conn_out_file_pre"] == f"{SUBJ}_{SES}_rest_SchaeferTian"
    original = next(b for b in tmpl["analyses"] if b["name"] == "nback_act")
    for key in ("hrf_model", "fd_threshold", "scale_to_psc", "contrasts", "cond_labels"):
        assert act[key] == original[key]
    assert act["extraction"]["stat_buckets"] == ["Coef", "Tstat", "Zstat"]


def test_every_template_analysis_has_a_prefix_rule():
    assert {b["name"] for b in template()["analyses"]} <= set(sfl.ANALYSES)


@pytest.mark.parametrize("code, status", [(0, "completed"), (3, "completed"), (5, "failed")])
def test_published_exit_codes(code, status):
    entry = sfl.classify_exit(code)
    assert entry["status"] == status and entry["exit_code"] == code
    assert entry["high_warnings"] is (code == 3)


@pytest.mark.parametrize("code", [1, 2, 4, 137])
def test_session_failing_exit_codes(code):
    with pytest.raises(sfl.SessionError, match=str(code)):
        sfl.classify_exit(code)


# ---------------------------------------------------------------------------
# Whole session, from a local directory
# ---------------------------------------------------------------------------


N_FRAMES, N_NSS = 20, 4


def save_nifti(path, data, affine, zooms=None):
    img = nib.Nifti1Image(np.asarray(data), affine)
    if zooms:
        img.header.set_zooms(zooms)
    nib.save(img, str(path))


def seed_session(root, runs=("task-nback_run-01", "task-nback_run-02", "task-rest_run-01")):
    root.mkdir(parents=True, exist_ok=True)
    for rid in runs:
        stem = root / f"{SUBJ}_{SES}_{rid}"
        save_nifti(
            f"{stem}_space-MNI152NLin2009cAsym_bold.nii.gz",
            np.ones((4, 4, 4, N_FRAMES), np.float32),
            REF_AFFINE,
            (2, 2, 2, TR),
        )
        save_nifti(
            f"{stem}_space-MNI152NLin2009cAsym_brainmask.nii.gz",
            np.ones((4, 4, 4), np.uint8),
            REF_AFFINE,
        )
        confounds(N_FRAMES, N_NSS).to_csv(f"{stem}_desc-confounds_timeseries.tsv", sep="\t", index=False)
        if "nback" in rid:
            nback_events().to_csv(f"{stem}_events.tsv", sep="\t", index=False)
    for name, fill in zip(sfl.probseg_names(SUBJ, SES), (0.0, 1.0, 1.0), strict=True):
        save_nifti(root / name, np.full((8, 8, 8), fill, np.float32), PROB_AFFINE)
    label = f"{SUBJ}_{SES}_space-MNI152NLin2009cAsym_res-1_label-CSF_mask.nii.gz"
    save_nifti(root / label, np.ones((8, 8, 8), np.uint8), PROB_AFFINE)
    (root / "_complete.json").write_text(json.dumps({"runs": {r: [] for r in runs}}))


@pytest.fixture
def fake_tools(monkeypatch):
    """AFNI writes its -prefix output; 3dmaskave prints one value per frame; the CLI
    returns the exit code a test asks for, per analysis."""
    calls: list[list[str]] = []
    exits: dict[str, int] = {}

    def run_cmd(cmd, **_):
        calls.append(cmd)
        if cmd[0] in ("3dcalc", "3dTcat"):
            src = cmd[cmd.index("-a") + 1].split("[")[0] if cmd[0] == "3dcalc" else cmd[-1]
            shutil.copy(src, cmd[cmd.index("-prefix") + 1])
        out = "\n".join(["1.0"] * (N_FRAMES - N_NSS)) if cmd[0] == "3dmaskave" else ""
        return type("R", (), {"stdout": out})()

    def run_cli(cmd, cwd):
        calls.append(cmd)
        cfg = yaml.safe_load(Path(cmd[cmd.index("--config") + 1]).read_text())
        name = cfg["analyses"][int(cmd[cmd.index("--analyses") + 1])]["name"]
        (Path(cwd) / f"{name}_out.txt").write_text("result")
        return exits.get(name, 0)

    monkeypatch.setattr(sfl, "run_cmd", run_cmd)
    monkeypatch.setattr(sfl, "run_cli", run_cli)
    monkeypatch.setattr(sfl, "CSF_MIN_VOXELS", 1)  # the 4^3 test grid holds only 64
    return calls, exits


def session(tmp_path, state="fixed") -> sfl.Session:
    return sfl.Session(SUBJ, SES, tmp_path / "raw", state, tmp_path / "work")


def run(tmp_path, state="fixed") -> dict:
    return sfl.run_session(session(tmp_path, state), template(), tmp_path / "out", ATLAS)


def test_a_full_session_runs_every_analysis(tmp_path, fake_tools):
    seed_session(tmp_path / "raw")
    result = run(tmp_path)
    assert {k: v["status"] for k, v in result["analyses"].items()} == {
        "nback_act": "completed",
        "nback_conn": "completed",
        "rest_conn": "completed",
    }
    assert result["runs"]["task-nback_run-01"]["n_remove"] == N_NSS
    assert result["runs"]["task-rest_run-01"]["mask_voxels"] == {"WM": 64, "CSF": 64}
    assert result["runs"]["task-rest_run-01"]["csf_threshold"] == 0.99
    calls, _ = fake_tools
    trims = [c for c in calls if c[0] == "3dcalc"]
    assert all(c[2].endswith(f"[{N_NSS}..$]") for c in trims)
    config = yaml.safe_load((tmp_path / "out" / f"{SUBJ}_{SES}_first_level_config.yaml").read_text())
    assert config["global"]["template_path"] == ATLAS
    rest = next(b for b in config["analyses"] if b["name"] == "rest_conn")
    [gs] = rest["paths"]["GS_paths"]  # GSR, as the orchestrator always passed it
    assert np.loadtxt(gs).shape == (N_FRAMES - N_NSS,)
    assert rest["censor_prev_tr"] is False and rest["fd_threshold"] == 0.4


def test_stale_probseg_skips_rest_not_the_session(tmp_path, fake_tools):
    seed_session(tmp_path / "raw")
    result = run(tmp_path, "stale")
    assert result["analyses"]["rest_conn"] == {"status": "skipped", "reason": "probseg-stale"}
    assert result["analyses"]["nback_act"]["status"] == "completed"
    calls, _ = fake_tools
    assert not any(c[0] == "3dmaskave" for c in calls)


def test_a_model_failure_fails_only_its_analysis(tmp_path, fake_tools):
    _, exits = fake_tools
    exits["rest_conn"] = 5
    seed_session(tmp_path / "raw")
    result = run(tmp_path)
    assert result["analyses"]["rest_conn"]["status"] == "failed"
    assert result["analyses"]["nback_act"]["status"] == "completed"


def test_a_tool_failure_fails_the_session(tmp_path, fake_tools):
    _, exits = fake_tools
    exits["nback_conn"] = 4
    seed_session(tmp_path / "raw")
    with pytest.raises(sfl.SessionError, match="4"):
        run(tmp_path)


def test_one_bad_run_does_not_fail_the_session(tmp_path, fake_tools):
    seed_session(tmp_path / "raw")
    bad = tmp_path / "raw" / f"{SUBJ}_{SES}_task-nback_run-02_desc-confounds_timeseries.tsv"
    confounds(N_FRAMES - 1, N_NSS).to_csv(bad, sep="\t", index=False)
    result = run(tmp_path)
    assert "excluded" in result["runs"]["task-nback_run-02"]
    assert result["analyses"]["nback_act"]["status"] == "completed"
    calls, _ = fake_tools
    assert not any(c[0] == "3dTcat" for c in calls)  # one surviving run: no concat


def test_a_session_without_a_marker_is_refused(tmp_path, fake_tools):
    (tmp_path / "raw").mkdir()
    with pytest.raises(sfl.SessionError, match="_complete.json"):
        run(tmp_path)


def test_a_missing_input_is_a_session_failure(tmp_path, fake_tools):
    seed_session(tmp_path / "raw")
    (tmp_path / "raw" / f"{SUBJ}_{SES}_task-nback_run-01_events.tsv").unlink()
    with pytest.raises(sfl.SessionError, match="missing input"):
        run(tmp_path)


def cli_args(tmp_path):
    return [
        "--subj", SUBJ, "--ses", SES, "--input-dir", str(tmp_path / "raw"), "--probseg-state", "fixed",
        "--workdir", str(tmp_path / "work"), "--out-dir", str(tmp_path / "out"), "--atlas", ATLAS,
        "--result", str(tmp_path / "result.json"),
    ]  # fmt: skip


def test_the_cli_writes_the_result_outside_the_output_tree(tmp_path, fake_tools):
    seed_session(tmp_path / "raw")
    assert sfl.main(cli_args(tmp_path)) == 0
    result = json.loads((tmp_path / "result.json").read_text())
    assert result["analyses"]["rest_conn"]["status"] == "completed"
    assert not list((tmp_path / "out").rglob("result.json"))


def test_a_session_failure_exits_1_and_writes_no_result(tmp_path, fake_tools):
    (tmp_path / "raw").mkdir()
    assert sfl.main(cli_args(tmp_path)) == 1
    assert not (tmp_path / "result.json").exists()


def test_the_packaged_template_carries_no_deployment_path():
    assert template()["global"]["template_path"] == "/path/to/atlas.nii.gz"
    assert template()["global"]["num_cores"] == "auto"


def test_the_core_does_not_import_the_abcd_module():
    code = (
        "import sys, fmri_first_level_proc; "
        "bad = [m for m in sys.modules if m.startswith('fmri_first_level_proc.abcd') or m in ('nibabel', 'scipy')]; "
        "sys.exit(repr(bad) if bad else 0)"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
