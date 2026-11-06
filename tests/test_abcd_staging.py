"""Tests for abcd/staging.py. AFNI and the CLI are faked, because these tests are about
what staging prepares and records, not about what AFNI computes."""

from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

nib = pytest.importorskip("nibabel")

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
    return pd.DataFrame(cols)


def test_nss_count_is_the_outlier_column_count():
    assert sfl.nss_count(confounds(20, 8)) == 8


def test_no_nss_columns_means_no_trim():
    assert sfl.nss_count(confounds(20, 0)) == 0


def test_motion_is_translations_first_then_derivatives():
    df = confounds(20, 0)
    m = sfl.motion_matrix(df, 0)
    base = df[sfl.MOTION_BASE].to_numpy()
    assert m.shape == (20, 12)
    np.testing.assert_allclose(m[:, :6], base)
    np.testing.assert_allclose(m[1:, 6:], np.diff(base, axis=0))
    assert (m[0, 6:] == 0).all()


def test_motion_rotations_pass_through_as_degrees():
    """ABCD's confounds already hold degrees: rot_y of 1.0 stays 1.0."""
    df = confounds(20, 0)
    df["rot_y"] = 1.0
    np.testing.assert_allclose(sfl.motion_matrix(df, 0)[:, sfl.MOTION_BASE.index("rot_y")], 1.0)


def test_motion_derivatives_come_from_the_untrimmed_series():
    """The orchestrator's order: diff, then trim; the first kept row is not 0."""
    df = confounds(20, 0)
    m = sfl.motion_matrix(df, 8)
    base = df[sfl.MOTION_BASE].to_numpy()
    assert m.shape == (12, 12)
    np.testing.assert_allclose(m[0, 6:], base[8] - base[7])


@pytest.mark.parametrize("bad", [np.nan, np.inf])
def test_non_finite_motion_excludes_the_run(bad):
    df = confounds(20, 0)
    df.loc[5, "trans_x"] = bad
    with pytest.raises(sfl.RunExcluded, match="motion_non_finite"):
        sfl.motion_matrix(df, 0)


def test_a_nan_trimmed_away_does_not_exclude_the_run():
    df = confounds(20, 8)
    df.loc[2, "trans_x"] = np.nan
    assert sfl.motion_matrix(df, 8).shape == (12, 12)


def test_a_nan_just_before_the_trim_excludes_the_run_through_its_derivative():
    df = confounds(20, 8)
    df.loc[7, "trans_x"] = np.nan
    with pytest.raises(sfl.RunExcluded, match="motion_non_finite"):
        sfl.motion_matrix(df, 8)


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
        "target_0back",
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
    ev, dropped = sfl.stage_events(nback_events(), 6.4)
    assert list(ev.columns) == ["onset", "duration", "trial_type"]
    assert "dummy" not in set(ev["trial_type"]) and "cue" not in set(ev["trial_type"])
    # 9.41 - 6.4 = 3.01 (spec: "Siemens and Philips inputs stay aligned")
    assert ev.loc[ev["trial_type"] == "0_back_posface", "onset"].iloc[0] == pytest.approx(3.01)
    # The 6.41 s cue (now "target_0back") lands at 0.01 s: kept.
    assert ev["onset"].iloc[0] == pytest.approx(0.01) and dropped == 0


def test_events_shifted_before_zero_are_dropped_and_counted():
    ev, dropped = sfl.stage_events(nback_events(), 7.2)
    assert dropped == 1  # the 6.41 s cue
    assert (ev["onset"] >= 0).all()


# ---------------------------------------------------------------------------
# Tissue masks
# ---------------------------------------------------------------------------

# cloudpipe's grids: 1 mm RAS label masks, 2 mm BOLD with x and y flipped.
LABEL_AFFINE = np.diag([1.0, 1.0, 1.0, 1.0])
REF_AFFINE = np.array([[-2.0, 0, 0, 6.5], [0, -2.0, 0, 6.5], [0, 0, 2.0, 0.5], [0, 0, 0, 1.0]])


def test_tissue_regressor_runs_the_orchestrators_commands(tmp_path, fake_tools):
    """compute_tissue_mask_regressor in ABCD_fmri_orchestrator_S3 5855f3f: 3dresample -rmode NN
    to the BOLD, 3dcalc step(a)*step(b) with the run's brain mask, 3dmaskave on the BOLD."""
    seed_session(tmp_path)
    bold = tmp_path / f"{SUBJ}_{SES}_task-rest_run-01_space-MNI152NLin2009cAsym_bold.nii.gz"
    brain = tmp_path / f"{SUBJ}_{SES}_task-rest_run-01_space-MNI152NLin2009cAsym_brainmask.nii.gz"
    label = tmp_path / sfl.tissue_mask_name(SUBJ, SES, "WM")
    path, voxels = sfl.tissue_regressor(bold, brain, label, tmp_path / "wm.1D")
    calls, _ = fake_tools
    resample, intersect, average = calls
    assert resample == ["3dresample", "-master", str(bold), "-rmode", "NN", "-input", str(label),
                        "-prefix", resample[-1]]  # fmt: skip
    assert intersect[:2] == ["3dcalc", "-a"] and intersect[2] == resample[-1]
    assert intersect[3:7] == ["-b", str(brain), "-expr", "step(a)*step(b)"]
    assert average == ["3dmaskave", "-quiet", "-mask", intersect[-1], str(bold)]
    assert voxels == 64 and len(path.read_text().split()) == N_FRAMES - N_NSS


def test_an_empty_tissue_mask_excludes_the_run(tmp_path, fake_tools):
    seed_session(tmp_path)
    label = tmp_path / sfl.tissue_mask_name(SUBJ, SES, "CSF")
    save_nifti(label, np.zeros((8, 8, 8), np.uint8), LABEL_AFFINE)
    bold = tmp_path / f"{SUBJ}_{SES}_task-rest_run-01_space-MNI152NLin2009cAsym_bold.nii.gz"
    brain = tmp_path / f"{SUBJ}_{SES}_task-rest_run-01_space-MNI152NLin2009cAsym_brainmask.nii.gz"
    with pytest.raises(sfl.RunExcluded, match="tissue_mask_empty"):
        sfl.tissue_regressor(bold, brain, label, tmp_path / "csf.1D")


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


def test_fill_config_moves_run_keys_out_of_paths_without_changing_the_staged_dict(tmp_path):
    paths = {"scan_paths": ["/a.nii.gz", "/b.nii.gz"], "run_labels": [1, 2]}
    cfg = sfl.fill_config(template(), SUBJ, SES, {"nback_act": paths, "nback_conn": paths}, tmp_path, ATLAS)
    for block in cfg["analyses"]:
        assert block["run_labels"] == [1, 2]
        assert "run_labels" not in block["paths"]
    assert paths["run_labels"] == [1, 2]


def test_auto_num_cores_becomes_a_number_the_framework_accepts(tmp_path, monkeypatch):
    monkeypatch.setenv("OMP_NUM_THREADS", "3")
    monkeypatch.setattr(sfl, "_cgroup_cpu_limit", lambda: None)
    assert sfl.fill_config(template(), SUBJ, SES, {}, tmp_path, ATLAS)["global"]["num_cores"] == 3
    monkeypatch.setattr(sfl, "_cgroup_cpu_limit", lambda: 2)
    assert sfl.fill_config(template(), SUBJ, SES, {}, tmp_path, ATLAS)["global"]["num_cores"] == 2


def test_run_label_is_the_run_number():
    assert sfl.run_label("task-nback_run-02") == 2
    with pytest.raises(sfl.SessionError, match="no run number"):
        sfl.run_label("task-nback")


def test_template_models_the_pooled_cue_and_no_contrast_uses_a_cue():
    blocks = {b["name"]: b for b in template()["analyses"]}
    assert "target_0back" in blocks["nback_act"]["cond_labels"]
    assert not {"target_0back", "instruction"} & set(blocks["nback_conn"]["cond_beta_labels"])
    labels = set(blocks["nback_act"]["cond_labels"])
    assert not labels & {"negface", "posface", "neutface", "place"}
    contrasts = [
        *blocks["nback_act"]["contrasts"]["functions"],
        *blocks["nback_conn"]["connectivity"]["contrasts"]["functions"],
    ]
    for contrast in contrasts:
        used = re.findall(r"[A-Za-z0-9_]+back_[a-z]+|\b(?:negface|posface|neutface|place)\b", contrast)
        assert used and set(used) <= labels - {"target_0back", "instruction"}, contrast


def test_nback_conn_has_the_same_29_contrasts_as_nback_act():
    blocks = {b["name"]: b for b in template()["analyses"]}
    assert blocks["nback_conn"]["connectivity"]["contrasts"] == blocks["nback_act"]["contrasts"]
    assert len(blocks["nback_act"]["contrasts"]["labels"]) == 29


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


N_FRAMES, N_NSS = 370, 8
NBACK_RUNS = ("task-nback_run-01", "task-nback_run-02")


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
    for tissue in sfl.TISSUES:
        save_nifti(root / sfl.tissue_mask_name(SUBJ, SES, tissue), np.ones((8, 8, 8), np.uint8), LABEL_AFFINE)
    (root / "_complete.json").write_text(json.dumps({"runs": {r: [] for r in runs}}))


@pytest.fixture
def analysis_qc() -> dict[str, dict]:
    """The QC summary a test wants an analysis to write, by analysis."""
    return {}


@pytest.fixture
def fake_tools(monkeypatch, analysis_qc):
    """AFNI writes its -prefix output (3dresample: the master's grid, all ones unless the
    label is empty); 3dmaskave prints one value per frame; the CLI writes a QC summary and
    returns the exit code a test asks for, per analysis."""
    calls: list[list[str]] = []
    exits: dict[str, int] = {}

    def run_cmd(cmd, **_):
        calls.append(cmd)
        if cmd[0] == "3dresample":
            master = nib.load(cmd[cmd.index("-master") + 1])
            label = np.asarray(nib.load(cmd[cmd.index("-input") + 1]).dataobj)
            mask = np.full(master.shape[:3], int(label.any()), np.uint8)
            nib.save(nib.Nifti1Image(mask, master.affine), cmd[cmd.index("-prefix") + 1])
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
        block = cfg["analyses"][int(cmd[cmd.index("--analyses") + 1])]
        (Path(cwd) / f"{block['out_file_pre']}_qc_summary.json").write_text(json.dumps(analysis_qc.get(name, {})))
        return exits.get(name, 0)

    monkeypatch.setattr(sfl, "run_cmd", run_cmd)
    monkeypatch.setattr(sfl, "run_cli", run_cli)
    monkeypatch.setenv("OMP_NUM_THREADS", "2")  # run_session sets it; this restores it after
    return calls, exits


ALL_VALID = {rid: (True, "") for rid in NBACK_RUNS}


def session(tmp_path, validity=None) -> sfl.Session:
    return sfl.Session(SUBJ, SES, tmp_path / "raw", tmp_path / "work", ALL_VALID if validity is None else validity)


def run(tmp_path, validity=None) -> dict:
    return sfl.run_session(session(tmp_path, validity), template(), tmp_path / "out", ATLAS)


def events_tsv(rows) -> str:
    lines = ["onset\tduration\tresponse_time\ttrial_type"]
    lines += [f'{o:.3f}\t{d:.3f}\t"n/a"\t"{label}"' for o, d, label in rows]
    return "\n".join(lines) + "\n"


def overwrite_events(tmp_path, rid, rows):
    (tmp_path / "raw" / f"{SUBJ}_{SES}_{rid}_events.tsv").write_text(events_tsv(rows))


def reseed_run(tmp_path, rid, frames, nss):
    stem = tmp_path / "raw" / f"{SUBJ}_{SES}_{rid}"
    save_nifti(
        f"{stem}_space-MNI152NLin2009cAsym_bold.nii.gz",
        np.ones((4, 4, 4, frames), np.float32),
        REF_AFFINE,
        (2, 2, 2, TR),
    )
    confounds(frames, nss).to_csv(f"{stem}_desc-confounds_timeseries.tsv", sep="\t", index=False)


def staged_events(tmp_path, rid="task-nback_run-01") -> pd.DataFrame:
    return pd.read_csv(tmp_path / "work" / f"{rid}_events.tsv", sep="\t")


def nback_block(tmp_path) -> dict:
    config = yaml.safe_load((tmp_path / "out" / f"{SUBJ}_{SES}_first_level_config.yaml").read_text())
    return next(b for b in config["analyses"] if b["name"] == "nback_act")


def test_each_nback_run_stays_separate_with_its_own_label_and_local_events(tmp_path, fake_tools):
    seed_session(tmp_path / "raw")
    run(tmp_path)
    block = nback_block(tmp_path)
    assert block["run_labels"] == [1, 2]
    assert "run_lengths" not in block and "run_labels" not in block["paths"]
    for key in ("scan_paths", "task_timing_paths", "motion_paths"):
        first, second = block["paths"][key]
        assert "run-01" in Path(first).name and "run-02" in Path(second).name
    assert block["paths"]["CSF_paths"] is None and block["paths"]["WM_paths"] is None
    # Run 2's onsets count from run 2's own first frame, not the session's.
    assert staged_events(tmp_path, "task-nback_run-02")["onset"].max() < 362 * TR
    calls, _ = fake_tools
    assert not any(c[0] == "3dTcat" for c in calls)


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
    assert "probseg_state" not in result
    calls, _ = fake_tools
    trims = [c for c in calls if c[0] == "3dcalc" and "[" in c[2]]
    assert len(trims) == 3  # each run's BOLD; the other 3dcalc calls build tissue masks
    assert all(c[2].endswith(f"[{N_NSS}..$]") for c in trims)
    config = yaml.safe_load((tmp_path / "out" / f"{SUBJ}_{SES}_first_level_config.yaml").read_text())
    assert config["global"]["template_path"] == ATLAS
    rest = next(b for b in config["analyses"] if b["name"] == "rest_conn")
    assert "GS_paths" not in rest["paths"]  # no GSR, as the orchestrator's config has it
    assert len([c for c in calls if c[0] == "3dmaskave"]) == 2  # WM, CSF
    assert rest["censor_prev_tr"] is True and rest["fd_threshold"] == 0.4


def test_an_empty_tissue_mask_excludes_only_its_rest_run(tmp_path, fake_tools, monkeypatch):
    seed_session(tmp_path / "raw", runs=(*NBACK_RUNS, "task-rest_run-01", "task-rest_run-02"))
    real = sfl.tissue_regressor

    def empty_for_run_one(bold, brainmask, label, dest):
        if "run-01" in dest.name and "wm" in dest.name:
            raise sfl.RunExcluded("tissue_mask_empty")
        return real(bold, brainmask, label, dest)

    monkeypatch.setattr(sfl, "tissue_regressor", empty_for_run_one)
    result = run(tmp_path)
    assert result["runs"]["task-rest_run-01"] == {"excluded": "tissue_mask_empty"}
    assert result["analyses"]["rest_conn"]["status"] == "completed"
    config = yaml.safe_load((tmp_path / "out" / f"{SUBJ}_{SES}_first_level_config.yaml").read_text())
    rest = next(b for b in config["analyses"] if b["name"] == "rest_conn")
    assert rest["run_labels"] == [2]
    assert all("run-02" in p for p in rest["paths"]["WM_paths"] + rest["paths"]["CSF_paths"])


def test_a_session_whose_rest_masks_are_all_empty_still_runs_nback(tmp_path, fake_tools):
    seed_session(tmp_path / "raw")
    save_nifti(tmp_path / "raw" / sfl.tissue_mask_name(SUBJ, SES, "WM"), np.zeros((8, 8, 8), np.uint8), LABEL_AFFINE)
    result = run(tmp_path)
    assert result["runs"]["task-rest_run-01"] == {"excluded": "tissue_mask_empty"}
    assert result["analyses"]["rest_conn"] == {"status": "skipped", "reason": "no-rest-runs"}
    assert result["analyses"]["nback_act"]["status"] == "completed"


def test_a_run_the_analysis_excluded_is_recorded_on_that_run(tmp_path, fake_tools, analysis_qc):
    analysis_qc["rest_conn"] = {"excluded_runs": [{"run": 1, "reason": "too-few-frames"}]}
    seed_session(tmp_path / "raw")
    result = run(tmp_path)
    assert result["runs"]["task-rest_run-01"]["excluded_by_analysis"] == "too-few-frames"
    assert "excluded_by_analysis" not in result["runs"]["task-nback_run-01"]


REST_RUNS = ("task-rest_run-01", "task-rest_run-02", "task-rest_run-03")


def test_the_analysis_reports_runs_by_label_not_position(tmp_path, fake_tools, analysis_qc):
    """With run 2 dropped in staging, the core's run 3 is the third run, not the second."""
    seed_session(tmp_path / "raw", runs=(*NBACK_RUNS, *REST_RUNS))
    path = tmp_path / "raw" / f"{SUBJ}_{SES}_task-rest_run-02_desc-confounds_timeseries.tsv"
    df = pd.read_csv(path, sep="\t")
    df.loc[100, "trans_x"] = np.nan
    df.to_csv(path, sep="\t", index=False)
    analysis_qc["rest_conn"] = {"excluded_runs": [{"run": 3, "reason": "dof_below_1"}]}
    runs = run(tmp_path)["runs"]
    assert runs["task-rest_run-03"]["excluded_by_analysis"] == "dof_below_1"
    assert "excluded_by_analysis" not in runs["task-rest_run-01"]
    assert runs["task-rest_run-02"] == {"excluded": "motion_non_finite"}


def failure_qc(message):
    error = {"type": "ModelError", "message": message, "exit_code": 5, "step": "rest-conn-nuisance"}
    return {"analysis_type": "rest_conn", "run_status": {"status": "failed", "error": error}}


@pytest.mark.parametrize("message, reason", [
    ("Every run has DOF < 1: run 1: DOF=-3, run 2: DOF=-1, run 3: DOF=0", "dof_below_1"),
    ("No run has enough uncensored TRs for the model. Runs: [(1, 'excluded')]", "insufficient_uncensored_trs"),
    ("Something the core may say later", "analysis_failed"),
])  # fmt: skip
def test_a_failed_rest_analysis_says_why_on_every_run(tmp_path, fake_tools, analysis_qc, message, reason):
    _, exits = fake_tools
    exits["rest_conn"] = 5
    analysis_qc["rest_conn"] = failure_qc(message)
    seed_session(tmp_path / "raw", runs=(*NBACK_RUNS, *REST_RUNS))
    result = run(tmp_path)
    entry = result["analyses"]["rest_conn"]
    assert entry["status"] == "failed"
    assert entry["error"] == {"type": "ModelError", "message": message, "step": "rest-conn-nuisance"}
    assert {result["runs"][r]["excluded_by_analysis"] for r in REST_RUNS} == {reason}
    assert "error" not in result["analyses"]["nback_act"]


def test_a_failed_analysis_without_qc_still_records_its_failure(tmp_path, fake_tools, analysis_qc, monkeypatch):
    _, exits = fake_tools
    exits["nback_conn"] = 5
    seed_session(tmp_path / "raw")
    real = sfl.analysis_qc
    monkeypatch.setattr(sfl, "analysis_qc", lambda b: {} if b["name"] == "nback_conn" else real(b))
    result = run(tmp_path)
    assert result["analyses"]["nback_conn"]["error"] == {"type": None, "message": None, "step": None}


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
    assert nback_block(tmp_path)["run_labels"] == [1]


def test_a_rest_run_with_nan_motion_is_excluded_and_the_session_finishes(tmp_path, fake_tools):
    seed_session(tmp_path / "raw")
    path = tmp_path / "raw" / f"{SUBJ}_{SES}_task-rest_run-01_desc-confounds_timeseries.tsv"
    df = pd.read_csv(path, sep="\t")
    df.loc[100, "trans_x"] = np.nan
    df.to_csv(path, sep="\t", index=False)
    result = run(tmp_path)
    assert result["runs"]["task-rest_run-01"] == {"excluded": "motion_non_finite"}
    assert result["analyses"]["rest_conn"] == {"status": "skipped", "reason": "no-rest-runs"}
    assert result["analyses"]["nback_act"]["status"] == "completed"


def test_an_nback_run_with_nan_motion_is_excluded_and_leaves_the_mask(tmp_path, fake_tools, monkeypatch):
    seed_session(tmp_path / "raw")
    path = tmp_path / "raw" / f"{SUBJ}_{SES}_task-nback_run-01_desc-confounds_timeseries.tsv"
    df = pd.read_csv(path, sep="\t")
    df.loc[100, "trans_x"] = np.nan
    df.to_csv(path, sep="\t", index=False)
    masked = []
    real = sfl.intersect_masks
    monkeypatch.setattr(sfl, "intersect_masks", lambda paths, dest: masked.extend(paths) or real(paths, dest))
    result = run(tmp_path)
    assert result["runs"]["task-nback_run-01"] == {"excluded": "motion_non_finite"}
    assert nback_block(tmp_path)["run_labels"] == [2]
    assert len(masked) == 1 and "task-nback_run-02" in Path(masked[0]).name


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
        "--subj", SUBJ, "--ses", SES, "--input-dir", str(tmp_path / "raw"),
        "--workdir", str(tmp_path / "work"), "--out-dir", str(tmp_path / "out"), "--atlas", ATLAS,
        "--result", str(tmp_path / "result.json"), "--run-validity", str(validity_table(tmp_path)),
    ]  # fmt: skip


def validity_table(tmp_path):
    path = tmp_path / "validity.csv"
    lines = ["subject_id,session,run,use,reason"]
    lines += [f"{SUBJ},{SES},{rid},1," for rid in NBACK_RUNS]
    lines += ["sub-OTHER,ses-00A,task-nback_run-01,0,no-valid-timing-runs"]
    path.write_text("\n".join(lines) + "\n")
    return path


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


def test_the_packaged_atlas_is_the_default_and_ships_its_licences(tmp_path):
    import hashlib

    args = cli_args(tmp_path)
    i = args.index("--atlas")
    atlas = sfl.PACKAGED_ATLAS
    assert sfl.build_parser().parse_args(args[:i] + args[i + 2 :]).atlas == str(atlas)
    digest = hashlib.sha256(atlas.read_bytes()).hexdigest()
    assert digest == "b105e68db7b716885c11cb80fc4fc147bc14d117a39850a34936fddee70728f6"
    labels = np.unique(np.asarray(nib.load(str(atlas)).dataobj)).astype(int)
    assert labels.tolist() == list(range(455))  # background, then 54 Tian, then 400 Schaefer
    for name in ("LICENSE-Tian-Melbourne-Subcortex-Atlas.txt", "LICENSE-CBIG-Schaefer2018.md", "README.md"):
        assert (atlas.parent / name).is_file()


def test_the_core_does_not_import_the_abcd_module():
    code = (
        "import sys, fmri_first_level_proc; "
        "bad = [m for m in sys.modules if m.startswith('fmri_first_level_proc.abcd') or m in ('nibabel', 'scipy')]; "
        "sys.exit(repr(bad) if bad else 0)"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


# ---------------------------------------------------------------------------
# n-back trim, from the `dummy` row
# ---------------------------------------------------------------------------


def trim(dummy, nss, frames):
    rows = [(0.0, dummy, "dummy"), (dummy + 0.5, 2.9, "cue"), (dummy + 3.5, 1.9, "2_back_place")]
    return sfl.nback_trim(pd.read_csv(io.StringIO(events_tsv(rows)), sep="\t"), nss, frames, TR)


@pytest.mark.parametrize(
    "dummy, nss, frames, n_remove",
    [
        (6.4, 8, 370, 8),  # Siemens, Philips: dummy equals the NSS count
        (12.0, 16, 378, 15),  # GE DV26 and later: one frame fewer than the NSS count
        (3.2, 5, 367, 4),  # GE DV25
        (0.0, 8, 370, 8),  # no pad: frames come from the NSS count, nothing leaves the onsets
    ],
)
def test_the_dummy_row_sets_the_trim(dummy, nss, frames, n_remove):
    assert trim(dummy, nss, frames) == (n_remove, dummy)


@pytest.mark.parametrize(
    "dummy, nss, frames, reason",
    [
        (12.8, 16, 378, "predates-ge-timing-correction"),
        (4.0, 5, 367, "predates-ge-timing-correction"),
        (3.2, 5, 378, "unexpected-frame-count"),  # labelled DV25, acquired like DV26
        (12.0, 16, 367, "unexpected-frame-count"),  # labelled DV26, acquired like DV25
        (6.4, 8, 180, "unexpected-frame-count"),  # a short run
        (12.0, 16, 200, "unexpected-frame-count"),
        (4.8, 8, 370, "unexpected-dummy"),  # neither 0, the NSS count, nor one below it
        (6.5, 8, 370, "unexpected-dummy"),  # not a whole number of frames
        (0.0, 16, 378, "unexpected-frame-count"),  # no GE run has been seen with no pad
    ],
)
def test_a_run_of_any_other_shape_is_excluded(dummy, nss, frames, reason):
    with pytest.raises(sfl.RunExcluded, match=reason):
        trim(dummy, nss, frames)


def test_a_run_with_no_task_events_is_excluded():
    ev = pd.read_csv(io.StringIO(events_tsv([(0.0, 6.4, "dummy")])), sep="\t")
    with pytest.raises(sfl.RunExcluded, match="no-task-events"):
        sfl.nback_trim(ev, 8, 370, TR)


def test_a_run_with_no_dummy_row_is_excluded():
    ev = pd.read_csv(io.StringIO(events_tsv([(6.4, 2.9, "cue"), (9.4, 1.9, "2_back_place")])), sep="\t")
    with pytest.raises(sfl.RunExcluded, match="no-dummy-row"):
        sfl.nback_trim(ev, 8, 370, TR)


def test_a_ge_run_keeps_its_first_cue(tmp_path, fake_tools):
    seed_session(tmp_path / "raw", runs=("task-nback_run-01",))
    reseed_run(tmp_path, "task-nback_run-01", 378, 16)
    overwrite_events(
        tmp_path,
        "task-nback_run-01",
        [(0.0, 12.0, "dummy"), (12.5, 2.9, "cue"), (15.5, 1.9, "2_back_place")],
    )
    result = run(tmp_path)
    record = result["runs"]["task-nback_run-01"]
    assert (record["n_remove"], record["n_frames"], record["dropped_events"]) == (15, 363, 0)
    ev = staged_events(tmp_path)
    assert ev.loc[ev["trial_type"] == "instruction", "onset"].iloc[0] == pytest.approx(0.5)
    calls, _ = fake_tools
    assert any(c[0] == "3dcalc" and c[2].endswith("[15..$]") for c in calls)


def test_a_zero_dummy_run_has_no_pad_to_remove(tmp_path, fake_tools):
    seed_session(tmp_path / "raw", runs=("task-nback_run-01",))
    overwrite_events(
        tmp_path,
        "task-nback_run-01",
        [(0.0, 0.0, "dummy"), (0.01, 2.9, "cue"), (3.01, 1.9, "0_back_place")],
    )
    record = run(tmp_path)["runs"]["task-nback_run-01"]
    assert (record["n_remove"], record["n_frames"], record["dropped_events"]) == (8, 362, 0)
    ev = staged_events(tmp_path)
    assert ev.loc[ev["trial_type"] == "target_0back", "onset"].iloc[0] == pytest.approx(0.01)


def test_rest_still_counts_its_frames_from_the_confounds(tmp_path, fake_tools):
    seed_session(tmp_path / "raw")
    reseed_run(tmp_path, "task-rest_run-01", 378, 16)
    assert run(tmp_path)["runs"]["task-rest_run-01"]["n_frames"] == 362


def test_a_short_run_cannot_spill_into_the_next(tmp_path, fake_tools):
    seed_session(tmp_path / "raw")
    reseed_run(tmp_path, "task-nback_run-01", 180, N_NSS)
    result = run(tmp_path)
    assert result["runs"]["task-nback_run-01"] == {"excluded": "unexpected-frame-count"}
    assert result["analyses"]["nback_act"]["status"] == "completed"
    assert nback_block(tmp_path)["run_labels"] == [2]


# ---------------------------------------------------------------------------
# Run validity
# ---------------------------------------------------------------------------


def test_only_runs_the_table_allows_are_used(tmp_path, fake_tools):
    seed_session(tmp_path / "raw")
    validity = {"task-nback_run-01": (False, "other-run-has-valid-timing"), "task-nback_run-02": (True, "")}
    result = run(tmp_path, validity=validity)
    assert result["runs"]["task-nback_run-01"] == {"excluded": "other-run-has-valid-timing"}
    assert result["runs"]["task-nback_run-02"]["n_frames"] == 362
    assert nback_block(tmp_path)["run_labels"] == [2]


def test_a_run_with_no_row_is_excluded(tmp_path, fake_tools):
    seed_session(tmp_path / "raw")
    result = run(tmp_path, validity={"task-nback_run-02": (True, "")})
    assert result["runs"]["task-nback_run-01"] == {"excluded": "no-validity-row"}


def test_a_held_out_session_still_runs_rest(tmp_path, fake_tools):
    seed_session(tmp_path / "raw")
    validity = {rid: (False, "no-valid-timing-runs") for rid in NBACK_RUNS}
    result = run(tmp_path, validity=validity)
    assert result["runs"]["task-nback_run-01"] == {"excluded": "no-valid-timing-runs"}
    assert result["analyses"]["nback_act"] == {"status": "skipped", "reason": "no-nback-runs"}
    assert result["analyses"]["rest_conn"]["status"] == "completed"


def test_an_excluded_run_leaves_the_mask_intersection(tmp_path, fake_tools):
    seed_session(tmp_path / "raw")
    mask = tmp_path / "raw" / f"{SUBJ}_{SES}_task-nback_run-01_space-MNI152NLin2009cAsym_brainmask.nii.gz"
    save_nifti(mask, np.zeros((4, 4, 4), np.uint8), REF_AFFINE)
    validity = {"task-nback_run-01": (False, "x"), "task-nback_run-02": (True, "")}
    run(tmp_path, validity=validity)
    assert np.asarray(nib.load(tmp_path / "work" / "nback_mask.nii.gz").dataobj).all()


def test_a_session_with_nothing_eligible_finishes_and_says_why(tmp_path, fake_tools):
    runs = ("task-nback_run-01", "task-nback_run-02")
    seed_session(tmp_path / "raw", runs=runs)
    result = run(tmp_path, validity={rid: (False, "no-valid-timing-runs") for rid in runs})
    assert result["analyses"]["nback_act"]["status"] == "skipped"
    assert result["analyses"]["rest_conn"] == {"status": "skipped", "reason": "no-rest-runs"}
    assert [p.name for p in (tmp_path / "out").iterdir()] == [f"{SUBJ}_{SES}_first_level_skipped.json"]
    calls, _ = fake_tools
    assert not calls


def test_a_session_whose_runs_all_fault_still_fails(tmp_path, fake_tools):
    seed_session(tmp_path / "raw", runs=("task-nback_run-01",))
    bad = tmp_path / "raw" / f"{SUBJ}_{SES}_task-nback_run-01_desc-confounds_timeseries.tsv"
    confounds(N_FRAMES - 1, N_NSS).to_csv(bad, sep="\t", index=False)
    with pytest.raises(sfl.SessionError, match="nothing to run"):
        run(tmp_path)


def test_the_validity_file_is_read_for_this_session_only(tmp_path):
    assert sfl.load_validity(validity_table(tmp_path), SUBJ, SES) == ALL_VALID
    assert sfl.load_validity(validity_table(tmp_path), "sub-OTHER", "ses-00A") == {
        "task-nback_run-01": (False, "no-valid-timing-runs")
    }


# ---------------------------------------------------------------------------
# Damaged event files
# ---------------------------------------------------------------------------


def test_an_empty_run_is_not_modelled_as_baseline(tmp_path, fake_tools):
    seed_session(tmp_path / "raw")
    overwrite_events(tmp_path, "task-nback_run-02", [(0.0, 6.4, "dummy")])
    result = run(tmp_path)
    assert result["runs"]["task-nback_run-02"] == {"excluded": "no-task-events"}
    assert result["analyses"]["nback_act"]["status"] == "completed"
    assert nback_block(tmp_path)["run_labels"] == [1], "its BOLD must not enter the model"


STRAY = [(0.0, 6.4, "dummy"), (6.41, 2.9, "cue"), (9.41, 1.9, "2_back_place"), (325.7, 2.9, "cue")]
UNCUED = [(0.0, 6.4, "dummy"), (9.42, 1.9, "2_back_neutface"), (34.52, 2.9, "cue"), (37.52, 1.9, "0_back_place")]


def test_a_stray_cue_returns_to_its_run(tmp_path, fake_tools):
    seed_session(tmp_path / "raw")
    overwrite_events(tmp_path, "task-nback_run-01", STRAY)
    overwrite_events(tmp_path, "task-nback_run-02", UNCUED)
    result = run(tmp_path)
    first, second = result["runs"]["task-nback_run-01"], result["runs"]["task-nback_run-02"]
    assert "excluded" not in first and "excluded" not in second
    assert first["cue_moved_to"] == "task-nback_run-02"
    assert second["cue_moved_from"] == "task-nback_run-01"
    ev1, ev2 = staged_events(tmp_path), staged_events(tmp_path, "task-nback_run-02")
    # run-01's cue at 0.01 s, and the moved one in run-02 at 9.42 - 3.0 - 6.4
    np.testing.assert_allclose(ev1.loc[ev1["trial_type"] == "instruction", "onset"], [0.01])
    np.testing.assert_allclose(ev2.loc[ev2["trial_type"] == "instruction", "onset"].iloc[:1], [0.02])
    assert ev1["onset"].max() < 362 * TR, "the stray cue left no event past the run's end"


def test_a_stray_cue_with_nowhere_to_go_still_excludes_its_run(tmp_path, fake_tools):
    seed_session(tmp_path / "raw")
    overwrite_events(tmp_path, "task-nback_run-01", STRAY)
    result = run(tmp_path)  # run-02 has its own first cue
    assert "no following" in result["runs"]["task-nback_run-01"]["excluded"]


def test_a_cue_inside_the_scan_with_no_trial_is_not_moved(tmp_path, fake_tools):
    seed_session(tmp_path / "raw")
    overwrite_events(tmp_path, "task-nback_run-01", [*STRAY[:3], (200.0, 2.9, "cue")])
    overwrite_events(tmp_path, "task-nback_run-02", UNCUED)
    result = run(tmp_path)
    assert "no following" in result["runs"]["task-nback_run-01"]["excluded"]
    assert "cue_moved_from" not in result["runs"]["task-nback_run-02"]


def test_clean_runs_are_left_alone():
    a, b = nback_events(), nback_events()
    out_a, out_b, moved = sfl.repair_stray_cue(a, b, N_FRAMES, TR)
    assert moved is False and out_a is a and out_b is b
