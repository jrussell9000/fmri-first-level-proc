"""End-to-end pipeline runs against FakeAfni (no AFNI installation required)."""

import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from fmri_first_level_proc import DISPATCH
from fmri_first_level_proc.config import load_and_validate

from fake_afni import FakeAfni

pytestmark = pytest.mark.level7_pipeline

N_TRS = 100
TR = 2.0


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    # Pipelines remove ./3dDeconvolve.err; keep that inside tmp_path.
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def fake_afni(monkeypatch):
    return FakeAfni(n_trs=N_TRS).install(monkeypatch)


@pytest.fixture
def inputs(workdir):
    rng = np.random.default_rng(0)
    d = workdir / "inputs"
    d.mkdir()
    files = {}
    for name in ("scan.nii.gz", "run1.nii.gz", "run2.nii.gz", "parc.nii.gz", "seed.nii.gz"):
        (d / name).write_bytes(b"fake nifti")
        files[name] = str(d / name)
    events = ["onset\tduration\ttrial_type"]
    for i in range(6):
        events.append(f"{10 + 30 * i}\t2\tA")
        events.append(f"{25 + 30 * i}\t2\tB")
    (d / "events.tsv").write_text("\n".join(events) + "\n")
    files["events.tsv"] = str(d / "events.tsv")
    for name, cols in (("motion.txt", 12), ("motion_run1.txt", 6), ("motion_run2.txt", 6)):
        np.savetxt(d / name, rng.normal(0, 0.05, (N_TRS, cols)))
        files[name] = str(d / name)
    for name in ("csf.txt", "wm.txt", "csf_run1.txt", "csf_run2.txt", "wm_run1.txt", "wm_run2.txt"):
        np.savetxt(d / name, rng.normal(100, 1, N_TRS))
        files[name] = str(d / name)
    return files


def _resolve(workdir, block, template):
    cfg = {"global": {"tr": TR, "num_cores": 2, "template_path": template}, "analyses": [block]}
    path = workdir / "config.yaml"
    path.write_text(yaml.safe_dump(cfg))
    (resolved,) = load_and_validate(str(path))
    return resolved


def _assert_outputs_exist(result):
    assert result.output_files
    missing = [p for p in result.output_files if not Path(p).exists()]
    assert not missing, missing


def test_task_act(workdir, inputs, fake_afni, logger):
    block = {
        "name": "act", "type": "task_act",
        "paths": {"scan_path": inputs["scan.nii.gz"], "task_timing_path": inputs["events.tsv"],
                  "motion_path": inputs["motion.txt"], "CSF_path": inputs["csf.txt"], "WM_path": inputs["wm.txt"]},
        "out_dir": str(workdir / "out_act"), "out_file_pre": "sub01",
        "cond_labels": ["A", "B"], "average_type": "mean", "hrf_model": "GAM",
        "include_motion_derivs": True, "use_tissue_derivs": True, "fd_threshold": 0.9,
        "contrasts": {"functions": ["1*A-1*B"], "labels": ["AvB"]},
        "extraction": {"stat_buckets": ["Coef", "Zstat"], "extract_out_file_pre": "sub01_parc"},
    }
    config = _resolve(workdir, block, inputs["parc.nii.gz"])
    result = DISPATCH["task_act"](config, logger)

    assert result.status == "success"
    _assert_outputs_exist(result)
    out = workdir / "out_act"
    for name in ("sub01_concat_bucket_stats.nii.gz", "sub01_parc_Coef_bucket.nii.gz", "sub01_parc_Zstat_bucket.nii.gz",
                 "sub01_parc_Coef_parcellated.csv", "sub01_qc_summary.json", "sub01_min_outlier_epi.nii.gz"):
        assert (out / name).exists(), name
    decon = fake_afni.calls_to("3dDeconvolve")[0]
    assert decon[decon.index("-jobs") + 1] == "2"
    assert "-gltsym" in decon and "SYM: 1*A -1*B" in decon
    # PSC-scaled scan feeds the GLM
    assert decon[decon.index("-input") + 1].endswith("sub01_psc.nii.gz")
    qc = json.loads((out / "sub01_qc_summary.json").read_text())
    assert qc["per_condition_surviving_trials"] == {"A": 6, "B": 6}
    assert not (workdir / "3dDeconvolve.err").exists()
    # Every AFNI call runs under the num_cores budget
    assert set(fake_afni.budgets) == {2}
    # Template + scan each queried once (combined 3dinfo, cached across both validations)
    assert len([c for c in fake_afni.calls_to("3dinfo") if "-space" in c]) == 2


def test_task_act_stat_bucket_labels(workdir, inputs, fake_afni, logger):
    block = {
        "name": "act", "type": "task_act",
        "paths": {"scan_path": inputs["scan.nii.gz"], "task_timing_path": inputs["events.tsv"],
                  "motion_path": inputs["motion.txt"]},
        "out_dir": str(workdir / "out_act"), "out_file_pre": "sub01",
        "cond_labels": ["A", "B"], "average_type": "mean", "hrf_model": "GAM",
        "include_motion_derivs": False, "fd_threshold": 0.9,
        "extraction": {"stat_buckets": ["Coef"], "extract_out_file_pre": "sub01_wb"},
    }
    DISPATCH["task_act"](_resolve(workdir, block, None), logger)
    index = json.loads((workdir / "out_act" / "sub01_wb_Coef_index.json").read_text())
    assert index == {"A": 0, "B": 1}


def test_task_act_rerun_skips_completed_stages(workdir, inputs, fake_afni, logger):
    block = {
        "name": "act", "type": "task_act",
        "paths": {"scan_path": inputs["scan.nii.gz"], "task_timing_path": inputs["events.tsv"],
                  "motion_path": inputs["motion.txt"]},
        "out_dir": str(workdir / "out_act"), "out_file_pre": "sub01",
        "cond_labels": ["A", "B"], "average_type": "mean", "hrf_model": "GAM",
        "include_motion_derivs": False, "fd_threshold": 0.9,
    }
    config = _resolve(workdir, block, None)
    DISPATCH["task_act"](config, logger)
    first = len(fake_afni.calls)
    DISPATCH["task_act"](config, logger)
    rerun_programs = fake_afni.programs()[first:]
    assert "3dDeconvolve" not in rerun_programs
    assert "1d_tool.py" not in rerun_programs


def test_task_conn_parcellated(workdir, inputs, fake_afni, logger):
    block = {
        "name": "conn", "type": "task_conn",
        "paths": {"scan_path": inputs["scan.nii.gz"], "task_timing_path": inputs["events.tsv"],
                  "motion_path": inputs["motion.txt"]},
        "out_dir": str(workdir / "out_conn"), "out_file_pre": "sub01",
        "cond_beta_labels": ["A", "B"], "average_type": "mean", "hrf_model": "GAM",
        "include_motion_derivs": False, "fd_threshold": 0.9,
        "extraction": {"extract_pbseries": True, "extract_out_file_pre": "sub01_parc"},
        "connectivity": {"calc_conn": "parcellated", "conn_out_file_pre": "sub01_fc", "fishZ": True,
                         "contrasts": {"functions": ["1*A-1*B"], "labels": ["AvB"]}},
    }
    config = _resolve(workdir, block, inputs["parc.nii.gz"])
    result = DISPATCH["task_conn"](config, logger)

    assert result.status == "success"
    _assert_outputs_exist(result)
    out = workdir / "out_conn"
    for cond in ("A", "B"):
        assert (out / f"sub01_concat_bseries_{cond}.nii.gz").exists()
        assert (out / f"sub01_parc_pbseries_{cond}.csv").exists()
        mat = np.loadtxt(out / f"sub01_fc_{cond}_fishZ_mat.txt", delimiter="\t")
        assert mat.shape == (3, 3)
    np.testing.assert_allclose(np.loadtxt(out / "sub01_fc_AvB_fishZ_mat.txt", delimiter="\t"), 0.0)
    # Beta-series sub-brick selectors follow onset-file order: A trials 0-5, B trials 6-11
    selectors = [c[2] for c in fake_afni.calls_to("3dcalc") if "_concat_LSS.nii.gz[" in c[2]]
    assert selectors[0].endswith("[0,1,2,3,4,5]")
    assert selectors[1].endswith("[6,7,8,9,10,11]")


@pytest.mark.parametrize("sequenced", [False, True])
def test_rest_conn_seed_to_voxel(workdir, inputs, fake_afni, logger, sequenced):
    block = {
        "name": "rest", "type": "rest_conn",
        "paths": {"scan_paths": [inputs["run1.nii.gz"], inputs["run2.nii.gz"]],
                  "motion_paths": [inputs["motion_run1.txt"], inputs["motion_run2.txt"]],
                  "CSF_paths": [inputs["csf_run1.txt"], inputs["csf_run2.txt"]],
                  "WM_paths": [inputs["wm_run1.txt"], inputs["wm_run2.txt"]]},
        "out_dir": str(workdir / "out_rest"), "out_file_pre": "sub01",
        "average_type": "mean", "bandpass": [0.01, 0.1], "motion_deriv_degree": 1, "fd_threshold": 0.9,
        "use_sequenced_bandpass": sequenced, "use_tissue_derivs": True,
        "extraction": {"extract_ptseries": True, "extract_out_file_pre": "sub01_seed"},
        "connectivity": {"calc_conn": "seed_to_voxel", "conn_out_file_pre": "sub01_fc", "fishZ": True},
    }
    config = _resolve(workdir, block, inputs["seed.nii.gz"])
    result = DISPATCH["rest_conn"](config, logger)

    assert result.status == "success"
    _assert_outputs_exist(result)
    out = workdir / "out_rest"
    assert (out / "sub01_concat_residual_dtseries.nii.gz").exists()
    assert (out / "sub01_fc_fishZ.nii.gz").exists()
    assert not (out / "sub01_fc_000_INDIV").exists()
    tcat = fake_afni.calls_to("3dTcat")[0]
    assert tcat[-2:] == [str(out / "sub01_run1_residual_dtseries.nii.gz"), str(out / "sub01_run2_residual_dtseries.nii.gz")]
    # num_cores=2 across 2 runs: per-run work gets 1 thread each; concat runs with the full budget
    per_run = [b for c, b in zip(fake_afni.calls, fake_afni.budgets) if c[0] in ("3dTproject", "3dToutcount")]
    assert per_run and set(per_run) == {1}
    assert fake_afni.budgets[fake_afni.calls.index(tcat)] == 2
    if sequenced:
        # Per run: 1 BOLD bandpass + 1 per nuisance file (motion, CSF, WM, CSF_deriv, WM_deriv)
        assert len(fake_afni.calls_to("3dBandpass")) == 2 * 6
        assert all("-bandpass" not in c for c in fake_afni.calls_to("3dTproject"))
        # keep_run_res_dtseries defaults to True, so intermediates are retained
        assert (out / "_sequenced_intermediates" / "run1").is_dir()
        filtered = np.loadtxt(out / "_sequenced_intermediates" / "run1" / "sub01_run1_motion_bp.1D")
        assert filtered.shape == (N_TRS, 6)
    else:
        assert all("-bandpass" in c for c in fake_afni.calls_to("3dTproject"))


def test_rest_conn_failed_run_is_skipped(workdir, inputs, monkeypatch, logger):
    fake = FakeAfni(n_trs=N_TRS).install(monkeypatch)
    real_tproject = fake._tproject

    def fail_run2(command):
        if "run2" in command[command.index("-input") + 1]:
            from fmri_first_level_proc.exceptions import ToolExecutionError
            raise ToolExecutionError("boom")
        return real_tproject(command)

    monkeypatch.setattr(fake, "_tproject", fail_run2)
    block = {
        "name": "rest", "type": "rest_conn",
        "paths": {"scan_paths": [inputs["run1.nii.gz"], inputs["run2.nii.gz"]],
                  "motion_paths": [inputs["motion_run1.txt"], inputs["motion_run2.txt"]],
                  "CSF_paths": [inputs["csf_run1.txt"], inputs["csf_run2.txt"]],
                  "WM_paths": [inputs["wm_run1.txt"], inputs["wm_run2.txt"]]},
        "out_dir": str(workdir / "out_rest"), "out_file_pre": "sub01",
        "average_type": "mean", "bandpass": [0.01, 0.1], "motion_deriv_degree": 1, "fd_threshold": 0.9,
    }
    config = _resolve(workdir, block, None)
    DISPATCH["rest_conn"](config, logger)
    tcat = fake.calls_to("3dTcat")[0]
    assert [Path(p).name for p in tcat[5:]] == ["sub01_run1_residual_dtseries.nii.gz"]


# ---------------------------------------------------------------------------
# Run manifest: stale-output guard and crash recovery
# ---------------------------------------------------------------------------

def _act_block(workdir, inputs, out_file_pre="sub01", **extra):
    block = {
        "name": out_file_pre, "type": "task_act",
        "paths": {"scan_path": inputs["scan.nii.gz"], "task_timing_path": inputs["events.tsv"],
                  "motion_path": inputs["motion.txt"]},
        "out_dir": str(workdir / "out"), "out_file_pre": out_file_pre,
        "cond_labels": ["A", "B"], "average_type": "mean", "hrf_model": "GAM",
        "include_motion_derivs": False, "fd_threshold": 0.9,
    }
    block.update(extra)
    return block


def _manifest(workdir, pre="sub01"):
    return json.loads((workdir / "out" / f"{pre}_manifest.json").read_text())


def test_manifest_completed_run_is_skipped(workdir, inputs, fake_afni, logger):
    config = _resolve(workdir, _act_block(workdir, inputs), None)
    first = DISPATCH["task_act"](config, logger)
    n_calls = len(fake_afni.calls)

    manifest = _manifest(workdir)
    assert manifest["status"] == "completed"
    assert "sub01_concat_bucket_stats.nii.gz" in manifest["owned_files"]
    assert "preexisting_files" not in manifest
    assert manifest["result"]["output_files"] == first.output_files

    second = DISPATCH["task_act"](config, logger)
    assert len(fake_afni.calls) == n_calls  # no AFNI work at all
    assert (second.status, second.output_files, second.qc_summary) == (first.status, first.output_files, first.qc_summary)


def test_manifest_missing_output_is_regenerated(workdir, inputs, fake_afni, logger):
    config = _resolve(workdir, _act_block(workdir, inputs), None)
    DISPATCH["task_act"](config, logger)
    (workdir / "out" / "sub01_concat_bucket_stats.nii.gz").unlink()
    n_calls = len(fake_afni.calls)

    DISPATCH["task_act"](config, logger)
    assert "3dDeconvolve" in fake_afni.programs()[n_calls:]
    assert "sub01_concat_bucket_stats.nii.gz" in _manifest(workdir)["owned_files"]


def test_manifest_config_change_requires_force(workdir, inputs, fake_afni, logger):
    from fmri_first_level_proc.exceptions import ConfigError

    with_buckets = _act_block(workdir, inputs, extraction={"stat_buckets": ["Coef"], "extract_out_file_pre": "sub01_wb"})
    DISPATCH["task_act"](_resolve(workdir, with_buckets, None), logger)
    stale = workdir / "out" / "sub01_wb_Coef_bucket.nii.gz"
    assert stale.exists()

    changed = _resolve(workdir, _act_block(workdir, inputs), None)
    with pytest.raises(ConfigError, match="different configuration"):
        DISPATCH["task_act"](changed, logger)
    assert stale.exists()  # nothing touched without force

    n_calls = len(fake_afni.calls)
    DISPATCH["task_act"](changed, logger, force=True)
    assert not stale.exists()  # output only the old config produced is gone
    assert "1d_tool.py" in fake_afni.programs()[n_calls:]  # censoring redone, not reused
    assert _manifest(workdir)["status"] == "completed"


def test_manifest_num_cores_change_is_not_a_config_change(workdir, inputs, fake_afni, logger):
    DISPATCH["task_act"](_resolve(workdir, _act_block(workdir, inputs), None), logger)
    n_calls = len(fake_afni.calls)
    config = _resolve(workdir, _act_block(workdir, inputs), None)
    config.num_cores = 8
    DISPATCH["task_act"](config, logger)
    assert len(fake_afni.calls) == n_calls


def test_manifest_crashed_attempt_is_discarded(workdir, inputs, monkeypatch, logger):
    from fmri_first_level_proc.exceptions import ToolExecutionError

    config = _resolve(workdir, _act_block(workdir, inputs), None)
    FakeAfni(n_trs=N_TRS, fail_on={"3dDeconvolve"}).install(monkeypatch)
    with pytest.raises(ToolExecutionError):
        DISPATCH["task_act"](config, logger)
    manifest = _manifest(workdir)
    assert manifest["status"] == "failed" and "ToolExecutionError" in manifest["error"]
    censor = workdir / "out" / "sub01_concat_censor.1D"
    censor.write_text("truncated")  # simulate a partial file left by the crash

    retry = FakeAfni(n_trs=N_TRS).install(monkeypatch)
    result = DISPATCH["task_act"](config, logger)
    assert result.status == "success"
    assert "1d_tool.py" in retry.programs()  # partial censor file was deleted and regenerated
    assert censor.read_text() != "truncated"


def test_manifest_force_leaves_other_blocks_in_shared_out_dir(workdir, inputs, fake_afni, logger):
    # 'sub01' is a prefix of 'sub01_b': ownership must come from the manifest, not filename globs
    DISPATCH["task_act"](_resolve(workdir, _act_block(workdir, inputs, "sub01"), None), logger)
    DISPATCH["task_act"](_resolve(workdir, _act_block(workdir, inputs, "sub01_b"), None), logger)
    other_outputs = sorted(p.name for p in (workdir / "out").iterdir() if p.name.startswith("sub01_b_"))
    assert len(other_outputs) > 5

    changed = _resolve(workdir, _act_block(workdir, inputs, "sub01", fd_threshold=0.5), None)
    n_calls = len(fake_afni.calls)
    DISPATCH["task_act"](changed, logger, force=True)
    redone = fake_afni.calls[n_calls:]
    assert any(c[0] == "1d_tool.py" and "0.5" in c for c in redone)  # sub01 recomputed with new threshold

    assert sorted(p.name for p in (workdir / "out").iterdir() if p.name.startswith("sub01_b_")) == other_outputs
    assert _manifest(workdir, "sub01_b")["status"] == "completed"


def test_cli_passes_force(workdir, inputs, monkeypatch):
    import sys

    from fmri_first_level_proc import cli
    from fmri_first_level_proc.reporting import FirstLevelResult

    seen = {}

    def fake_run(config, logger, force=False):
        seen["force"] = force
        return FirstLevelResult("success", Path(config.out_dir), [], {}, [])

    _resolve(workdir, _act_block(workdir, inputs), None)
    monkeypatch.setitem(cli.DISPATCH, "task_act", fake_run)
    monkeypatch.setattr(cli, "preflight_tool_environments", lambda **k: None)
    monkeypatch.setattr(cli, "probe_tool_versions", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["fmri-first-level-proc", "--config", str(workdir / "config.yaml"), "--force"])
    cli.main()
    assert seen == {"force": True}
