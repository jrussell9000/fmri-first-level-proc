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
    decon = _models(fake_afni)[0]
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


def _models(fake):
    """3dDeconvolve calls that fit data, leaving out the -nodata estimability design."""
    return [c for c in fake.calls_to("3dDeconvolve") if "-nodata" not in c]


def _two_run_block(workdir, inputs, atype):
    conds = {"cond_labels": ["A", "B"]} if atype == "task_act" else {"cond_beta_labels": ["A", "B"]}
    return {
        "name": atype, "type": atype,
        "paths": {"scan_path": inputs["scan.nii.gz"], "task_timing_path": inputs["events.tsv"],
                  "motion_path": inputs["motion.txt"], "CSF_path": inputs["csf.txt"],
                  "run_lengths": [40, 60]},
        "out_dir": str(workdir / "out"), "out_file_pre": "sub01", "average_type": "mean",
        "hrf_model": "GAM", "include_motion_derivs": False, "use_tissue_derivs": True,
        "fd_threshold": 0.9, **conds,
    }


@pytest.mark.parametrize("atype", ["task_act", "task_conn"])
def test_run_lengths_set_run_boundaries(workdir, inputs, fake_afni, logger, atype):
    motion = np.loadtxt(inputs["motion.txt"])
    motion[40:, 0] += 50.0  # a large step between runs is not head motion
    np.savetxt(inputs["motion.txt"], motion)

    DISPATCH[atype](_resolve(workdir, _two_run_block(workdir, inputs, atype), None), logger)

    out = workdir / "out"
    decon = _models(fake_afni)[0]
    assert decon[decon.index("-concat") + 1] == "1D: 0 40"
    assert "-global_times" in decon
    # Each run is PSC-scaled by its own mean, then concatenated for the GLM
    means = [c for c in fake_afni.calls_to("3dTstat") if "-mean" in c]
    assert [c[-1].rsplit("[", 1)[1] for c in means] == ["0..39]", "40..99]"]
    tcat = next(c for c in fake_afni.calls_to("3dTcat") if c[2].endswith("sub01_psc.nii.gz"))
    assert [Path(p).name for p in tcat[3:]] == ["sub01_run1_psc.nii.gz", "sub01_run2_psc.nii.gz"]
    assert decon[decon.index("-input") + 1].endswith("sub01_psc.nii.gz")
    assert not (out / "sub01_run1_psc.nii.gz").exists()
    assert (out / "sub01_run2_mean.nii.gz").exists()
    # The between-run step leaves FD, censoring and the tissue derivative at 0 for run 2's first TR
    assert np.loadtxt(out / "sub01_concat_fd.1D")[40] == 0.0
    assert np.loadtxt(out / "sub01_concat_censor.1D")[40] == 1
    assert np.loadtxt(out / "sub01_CSF_deriv.txt")[40] == 0.0
    qc = json.loads((out / "sub01_qc_summary.json").read_text())
    assert qc["censor_metric"] == "power_fd"


def test_run_lengths_must_match_motion_rows(workdir, inputs, fake_afni, logger):
    from fmri_first_level_proc.exceptions import InputError

    block = _two_run_block(workdir, inputs, "task_act")
    block["paths"]["run_lengths"] = [40, 50]
    with pytest.raises(InputError, match="run_lengths"):
        DISPATCH["task_act"](_resolve(workdir, block, None), logger)


@pytest.mark.parametrize("bad", [[], [40, 0], [40.5, 60], "40,60", [True, 60]])
def test_invalid_run_lengths_rejected(workdir, inputs, bad):
    from fmri_first_level_proc.exceptions import ConfigError

    block = _two_run_block(workdir, inputs, "task_act")
    block["paths"]["run_lengths"] = bad
    with pytest.raises(ConfigError, match="run_lengths"):
        _resolve(workdir, block, None)


def test_single_run_scan_has_no_concat(workdir, inputs, fake_afni, logger):
    block = _two_run_block(workdir, inputs, "task_act")
    del block["paths"]["run_lengths"]
    DISPATCH["task_act"](_resolve(workdir, block, None), logger)
    decon = _models(fake_afni)[0]
    assert "-concat" not in decon and "-global_times" not in decon
    assert (workdir / "out" / "sub01_mean.nii.gz").exists()


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
        assert all("-nodetrend" not in c for c in fake_afni.calls_to("3dBandpass"))
        assert all(c[c.index("-polort") + 1] == "-1" for c in fake_afni.calls_to("3dTproject"))
        assert all("-bandpass" not in c for c in fake_afni.calls_to("3dTproject"))
        # keep_run_res_dtseries defaults to True, so intermediates are retained
        assert (out / "_sequenced_intermediates" / "run1").is_dir()
        filtered = np.loadtxt(out / "_sequenced_intermediates" / "run1" / "sub01_run1_motion_bp.1D")
        assert filtered.shape == (N_TRS, 6)
    else:
        assert all("-bandpass" in c for c in fake_afni.calls_to("3dTproject"))
        assert all(c[c.index("-polort") + 1] == "2" for c in fake_afni.calls_to("3dTproject"))


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
    censor = workdir / "out" / "sub01_concat_censor.1D"
    censor.write_text("stale")

    DISPATCH["task_act"](changed, logger, force=True)
    assert not stale.exists()  # output only the old config produced is gone
    assert censor.read_text() != "stale"  # censoring redone, not reused
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
    assert "3dDeconvolve" in retry.programs()
    assert censor.read_text() != "truncated"  # partial censor file was deleted and regenerated


def test_manifest_force_leaves_other_blocks_in_shared_out_dir(workdir, inputs, fake_afni, logger):
    # 'sub01' is a prefix of 'sub01_b': ownership must come from the manifest, not filename globs
    DISPATCH["task_act"](_resolve(workdir, _act_block(workdir, inputs, "sub01"), None), logger)
    DISPATCH["task_act"](_resolve(workdir, _act_block(workdir, inputs, "sub01_b"), None), logger)
    other_outputs = sorted(p.name for p in (workdir / "out").iterdir() if p.name.startswith("sub01_b_"))
    assert len(other_outputs) > 5
    censor = workdir / "out" / "sub01_concat_censor.1D"
    assert np.loadtxt(censor).all()

    changed = _resolve(workdir, _act_block(workdir, inputs, "sub01", fd_threshold=0.5), None)
    DISPATCH["task_act"](changed, logger, force=True)
    assert not np.loadtxt(censor).all()  # sub01 recomputed with new threshold

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


# ---------------------------------------------------------------------------
# Onset validation, PSC QC, ROI averaging, trial records
# ---------------------------------------------------------------------------

def test_out_of_range_onset_writes_timing_errors(workdir, inputs, fake_afni, logger):
    from fmri_first_level_proc.exceptions import InputError

    with open(inputs["events.tsv"], "a") as f:
        f.write("200\t2\tA\n-3\t2\tignored_condition\n")
    with pytest.raises(InputError, match="outside the 200 s scan"):
        DISPATCH["task_act"](_resolve(workdir, _act_block(workdir, inputs), None), logger)
    record = json.loads((workdir / "out" / "sub01_timing_errors.json").read_text())
    assert record["run_end_s"] == 200.0
    assert [(v["condition"], v["onset_s"], v["violation"]) for v in record["violations"]] == [
        ("ignored_condition", -3.0, "negative"), ("A", 200.0, "at_or_after_run_end")]
    assert not fake_afni.calls_to("3dDeconvolve")


def test_psc_qc_records_and_demeaned_sentinel(workdir, inputs, monkeypatch, logger):
    from fmri_first_level_proc.exceptions import InputError

    FakeAfni(n_trs=N_TRS, nonzero_counts={"nonpositive": 100, "guarded": 200, "capped": 10}).install(monkeypatch)
    result = DISPATCH["task_act"](_resolve(workdir, _act_block(workdir, inputs), None), logger)
    assert result.qc_summary["psc_per_run"] == [{
        "run": 1, "n_mask_voxels": 1000, "n_guarded_voxels": 200, "pct_guarded_voxels": 20.0,
        "n_capped_voxels": 10, "pct_capped_voxels": 1.0,
        "n_nonpositive_mean_voxels": 100, "pct_nonpositive_mean_voxels": 10.0}]

    FakeAfni(n_trs=N_TRS, nonzero_counts={"nonpositive": 250}).install(monkeypatch)
    with pytest.raises(InputError, match="demeaned"):
        DISPATCH["task_act"](_resolve(workdir, _act_block(workdir, inputs, "sub02"), None), logger)


@pytest.mark.parametrize(
    "handling, average, flags",
    [("exclude", "mean", ["-nzmean"]), ("exclude", "median", ["-nzmedian"]),
     ("include", "mean", []), ("include", "median", ["-nomeanout", "-median"])],
)
def test_roi_zero_handling_flags(workdir, inputs, fake_afni, logger, handling, average, flags):
    block = _act_block(workdir, inputs, average_type=average, roi_zero_handling=handling,
                       extraction={"stat_buckets": ["Coef"], "extract_out_file_pre": "sub01_parc"})
    DISPATCH["task_act"](_resolve(workdir, block, inputs["parc.nii.gz"]), logger)
    roistats = fake_afni.calls_to("3dROIstats")[0]
    assert roistats[1:roistats.index("-1Dformat")] == flags
    csv = (workdir / "out" / "sub01_parc_Coef_parcellated.csv").read_text().splitlines()
    assert csv[0] == "condition,ROI_1,ROI_2,ROI_3"


def test_trial_records_and_lss_indexes(workdir, inputs, fake_afni, logger):
    block = _two_run_block(workdir, inputs, "task_conn")
    result = DISPATCH["task_conn"](_resolve(workdir, block, None), logger)

    trials = result.qc_summary["trials"]
    assert len(trials) == 12
    # Run 1 is 40 TRs at 2 s: 80 s
    assert trials[0] == {"run": 1, "condition": "A", "onset": 10.0, "duration": 2.0,
                         "estimability": 1.0, "survived": True}
    assert trials[-1]["run"] == 2

    out = workdir / "out"
    lss = json.loads((out / "sub01_concat_LSS_index.json").read_text())
    assert [t["lss_index"] for t in lss] == list(range(12))
    assert lss[6] == {"lss_index": 6, "beta_series_position": 0, "run": 1, "onset": 25.0,
                      "condition": "B", "survived": True}
    b_index = json.loads((out / "sub01_concat_bseries_B_index.json").read_text())
    assert b_index[0] == {"lss_index": 6, "beta_series_position": 0, "run": 1, "onset": 25.0}
    assert len(b_index) == 6


def test_fully_censored_trial_leaves_the_beta_series(workdir, inputs, fake_afni, logger):
    # FD is 5 mm at TRs 21-27 only: the whole response of A's second trial (onset 40 s) in the fake design
    motion = np.zeros((N_TRS, 6))
    motion[21:28, 0] = np.arange(1, 8) * 5.0
    motion[28:, 0] = 35.0
    np.savetxt(inputs["motion.txt"], motion)
    block = _two_run_block(workdir, inputs, "task_conn")
    del block["paths"]["run_lengths"]
    del block["paths"]["CSF_path"]
    block["use_tissue_derivs"] = False
    result = DISPATCH["task_conn"](_resolve(workdir, block, None), logger)

    out = workdir / "out"
    a_trial = next(t for t in result.qc_summary["trials"] if t["condition"] == "A" and t["onset"] == 40.0)
    assert a_trial["estimability"] == 0.0 and a_trial["survived"] is False
    assert result.qc_summary["per_condition_surviving_trials"]["A"] == 5
    # Second A trial (LSS sub-brick 1) is skipped when building the series
    selector = next(c[2] for c in fake_afni.calls_to("3dcalc") if "_concat_LSS.nii.gz[" in c[2])
    assert selector.endswith("[0,2,3,4,5]")
    a_index = json.loads((out / "sub01_concat_bseries_A_index.json").read_text())
    assert [t["lss_index"] for t in a_index] == [0, 2, 3, 4, 5]
    assert [t["beta_series_position"] for t in a_index] == [0, 1, 2, 3, 4]
    lss = json.loads((out / "sub01_concat_LSS_index.json").read_text())
    assert lss[1]["survived"] is False and lss[1]["beta_series_position"] is None
    assert len(lss) == 12


# ---------------------------------------------------------------------------
# Smoothing
# ---------------------------------------------------------------------------

SMOOTHING = {"enabled": True, "fwhm": 4.5}


def test_task_act_smoothing(workdir, inputs, fake_afni, logger):
    block = _act_block(workdir, inputs, smoothing=SMOOTHING,
                       paths={**_act_block(workdir, inputs)["paths"], "run_lengths": [40, 60]},
                       contrasts={"functions": ["1*A-1*B"], "labels": ["AvB"]},
                       extraction={"stat_buckets": ["Coef", "Zstat"], "extract_out_file_pre": "sub01_parc",
                                   "extract_resids": True})
    result = DISPATCH["task_act"](_resolve(workdir, block, inputs["parc.nii.gz"]), logger)
    _assert_outputs_exist(result)

    out = workdir / "out"
    plain, smoothed = _models(fake_afni)
    assert plain[plain.index("-input") + 1].endswith("sub01_psc.nii.gz")
    assert smoothed[smoothed.index("-input") + 1].endswith("sub01_psc_s4p5mm.nii.gz")
    assert "SYM: 1*A -1*B" in smoothed and smoothed[smoothed.index("-concat") + 1] == "1D: 0 40"
    # The unscaled runs are blurred, then scaled by their own means
    blurs = fake_afni.calls_to("3dBlurToFWHM")
    assert [c[c.index("-input") + 1].rsplit("/", 1)[1] for c in blurs] == ["scan.nii.gz[0..39]", "scan.nii.gz[40..99]"]
    assert all(c[c.index("-FWHM") + 1] == "4.5" for c in blurs)
    for name in ("sub01_concat_bucket_stats_s4p5mm.nii.gz", "sub01_concat_bucket_resids_s4p5mm.nii.gz",
                 "sub01_concat_bucket_stats_index_s4p5mm.json", "sub01_parc_Zstat_bucket_s4p5mm.nii.gz",
                 "sub01_parc_Coef_index_s4p5mm.json", "sub01_smoothing_mask.nii.gz", "sub01_run2_mean_s4p5mm.nii.gz"):
        assert (out / name).exists(), name
    assert not (out / "sub01_run1_blur_s4p5mm.nii.gz").exists()
    # Parcel-level outputs never come from smoothed data
    assert not list(out.glob("*_s4p5mm*.csv"))
    assert all("_s4p5mm" not in c[-1] for c in fake_afni.calls_to("3dROIstats"))
    records = result.qc_summary["smoothing_per_run"]
    assert [r["run"] for r in records] == [1, 2]
    assert records[0] == {"run": 1, "fwhm_target_mm": 4.5, "acf_fwhm_input_mm": 6.0, "acf_fwhm_output_mm": 6.0,
                          "mask_n_voxels": 1000, "mask_fov_fraction": 0.2}
    assert {w["code"] for w in result.warnings} >= {"SMOOTH_FWHM_OFF_TARGET", "SMOOTH_INPUT_ABOVE_TARGET"}
    assert result.status == "success"  # medium severity


def test_task_conn_smoothing_seed_maps(workdir, inputs, fake_afni, logger):
    block = {
        "name": "conn", "type": "task_conn",
        "paths": {"scan_path": inputs["scan.nii.gz"], "task_timing_path": inputs["events.tsv"],
                  "motion_path": inputs["motion.txt"]},
        "out_dir": str(workdir / "out"), "out_file_pre": "sub01", "smoothing": SMOOTHING,
        "cond_beta_labels": ["A", "B"], "average_type": "mean", "hrf_model": "GAM",
        "include_motion_derivs": False, "fd_threshold": 0.9,
        "extraction": {"extract_pbseries": True, "extract_out_file_pre": "sub01_seed"},
        "connectivity": {"calc_conn": "seed_to_voxel", "conn_out_file_pre": "sub01_fc", "fishZ": True,
                         "contrasts": {"functions": ["1*A-1*B"], "labels": ["AvB"]}},
    }
    result = DISPATCH["task_conn"](_resolve(workdir, block, inputs["seed.nii.gz"]), logger)
    _assert_outputs_exist(result)

    out = workdir / "out"
    plain, smoothed = fake_afni.calls_to("3dLSS")
    assert plain[plain.index("-input") + 1].endswith("sub01_psc.nii.gz")
    assert smoothed[smoothed.index("-input") + 1].endswith("sub01_psc_s4p5mm.nii.gz")
    for name in ("sub01_concat_LSS_s4p5mm.nii.gz", "sub01_concat_LSS_index_s4p5mm.json",
                 "sub01_concat_bseries_A_s4p5mm.nii.gz", "sub01_concat_bseries_A_index_s4p5mm.json",
                 "sub01_fc_A_fishZ_s4p5mm.nii.gz", "sub01_fc_AvB_fishZ_s4p5mm.nii.gz"):
        assert (out / name).exists(), name
    # The seed series comes from the unsmoothed beta series; the target is smoothed
    corr = fake_afni.calls_to("3dTcorr1D")
    assert len(corr) == 2 and all("_s4p5mm" in c[-2] for c in corr)
    assert all("_s4p5mm" not in c[-1] for c in fake_afni.calls_to("3dROIstats"))
    assert not list(out.glob("*pbseries*_s4p5mm*"))
    assert not list(out.glob("tmp*"))


@pytest.mark.parametrize("keep_runs", [True, False])
def test_rest_conn_smoothing(workdir, inputs, fake_afni, logger, keep_runs):
    block = {
        "name": "rest", "type": "rest_conn",
        "paths": {"scan_paths": [inputs["run1.nii.gz"], inputs["run2.nii.gz"]],
                  "motion_paths": [inputs["motion_run1.txt"], inputs["motion_run2.txt"]],
                  "CSF_paths": [inputs["csf_run1.txt"], inputs["csf_run2.txt"]],
                  "WM_paths": [inputs["wm_run1.txt"], inputs["wm_run2.txt"]]},
        "out_dir": str(workdir / "out"), "out_file_pre": "sub01", "smoothing": SMOOTHING,
        "average_type": "mean", "bandpass": [0.01, 0.1], "motion_deriv_degree": 1, "fd_threshold": 0.9,
        "keep_run_res_dtseries": keep_runs,
        "connectivity": {"calc_conn": "seed_to_voxel", "conn_out_file_pre": "sub01_fc", "fishZ": False},
    }
    result = DISPATCH["rest_conn"](_resolve(workdir, block, inputs["seed.nii.gz"]), logger)
    _assert_outputs_exist(result)

    out = workdir / "out"
    assert (out / "sub01_concat_residual_dtseries_s4p5mm.nii.gz").exists()
    assert (out / "sub01_fc_corr_s4p5mm.nii.gz").exists()
    assert (out / "sub01_run2_residual_dtseries_s4p5mm.nii.gz").exists() == keep_runs
    blurs = [Path(c[c.index("-input") + 1]).name for c in fake_afni.calls_to("3dBlurToFWHM")]
    assert blurs == ["sub01_run1_residual_dtseries.nii.gz", "sub01_run2_residual_dtseries.nii.gz"]
    assert all("-detrend" not in c for c in fake_afni.calls_to("3dFWHMx"))
    assert [r["run"] for r in result.qc_summary["smoothing_per_run"]] == [1, 2]
    corr = fake_afni.calls_to("3dTcorr1D")[0]
    assert corr[-2].endswith("sub01_concat_residual_dtseries_s4p5mm.nii.gz")
    assert result.qc_summary["psc_per_run"][1]["run"] == 2


@pytest.mark.parametrize("fit", ["0.5  -nan  -nan    5.28315", "0.5  0.01  0.01    0.948223"])
def test_acf_fit_failure_is_reported(monkeypatch, logger, fit):
    from fmri_first_level_proc import smoothing
    from fmri_first_level_proc.reporting import clear_warnings, get_warnings

    monkeypatch.setattr(smoothing, "run_afni_command", lambda *a, **k: f" 0  0  0    0\n {fit}\n")
    assert smoothing.acf_fwhm("scan.nii.gz", "mask.nii.gz", True, logger) is None

    clear_warnings()
    record = smoothing.qc_record(1, 6.0, None, None, (1000, 0.5), logger)
    assert record["acf_fwhm_output_mm"] is None
    assert [w["code"] for w in get_warnings()] == ["SMOOTH_ACF_FIT_FAILED"]
