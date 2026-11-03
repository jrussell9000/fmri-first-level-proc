"""Config resolution, runtime version probing, and CLI dry-run tests."""

import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

from fmri_first_level_proc import cli, runtime
from fmri_first_level_proc.config import load_and_validate
from fmri_first_level_proc.exceptions import ConfigError, InputError, ToolVersionError

from fake_afni import FakeAfni

pytestmark = pytest.mark.level1_internal_integration


@pytest.fixture
def task_inputs(tmp_path):
    files = {}
    for name in ("scan.nii.gz", "events.tsv", "motion.txt"):
        p = tmp_path / name
        p.write_text("x")
        files[name] = str(p)
    return files


def _write_config(tmp_path, analyses, **global_extra):
    cfg = {"global": {"tr": 0.8, "num_cores": 2, **global_extra}, "analyses": analyses}
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg))
    return str(path)


def _task_act_block(tmp_path, files, **extra):
    block = {
        "name": "act",
        "type": "task_act",
        "paths": {
            "scan_path": files["scan.nii.gz"],
            "task_timing_path": files["events.tsv"],
            "motion_path": files["motion.txt"],
        },
        "out_dir": str(tmp_path / "out"),
        "out_file_pre": "sub01",
        "cond_labels": ["A", "B"],
        "average_type": "mean",
        "hrf_model": "GAM",
        "include_motion_derivs": False,
        "fd_threshold": 0.9,
    }
    block.update(extra)
    return block


def test_load_and_validate_task_act(tmp_path, task_inputs, logger):
    path = _write_config(tmp_path, [_task_act_block(tmp_path, task_inputs)])
    (cfg,) = load_and_validate(path, logger)
    assert cfg.analysis_type == "task_act"
    assert cfg.tr == 0.8
    assert cfg.num_cores == 2
    assert cfg.cond_labels == ["A", "B"]
    assert cfg.scan_path == task_inputs["scan.nii.gz"]


def test_num_cores_auto(tmp_path, task_inputs, monkeypatch, logger):
    monkeypatch.setattr("fmri_first_level_proc.config.available_cpus", lambda: (3, "test"))
    path = _write_config(tmp_path, [_task_act_block(tmp_path, task_inputs)], num_cores="auto")
    (cfg,) = load_and_validate(path, logger)
    assert cfg.num_cores == 3


@pytest.mark.parametrize("bad", [0, -1, 1.5, "four", True])
def test_num_cores_rejects_invalid(tmp_path, task_inputs, logger, bad):
    path = _write_config(tmp_path, [_task_act_block(tmp_path, task_inputs)], num_cores=bad)
    with pytest.raises(ConfigError, match="num_cores"):
        load_and_validate(path, logger)


def test_load_and_validate_errors(tmp_path, task_inputs, logger):
    with pytest.raises(ConfigError):
        load_and_validate(str(tmp_path / "nope.yaml"), logger)
    missing = dict(task_inputs, **{"scan.nii.gz": str(tmp_path / "missing.nii.gz")})
    with pytest.raises(InputError):
        load_and_validate(_write_config(tmp_path, [_task_act_block(tmp_path, missing)]), logger)
    with pytest.raises(ConfigError):
        load_and_validate(
            _write_config(tmp_path, [_task_act_block(tmp_path, task_inputs, hrf_model="NOPE")]), logger
        )
    dup = _task_act_block(tmp_path, task_inputs)
    with pytest.raises(ConfigError):
        load_and_validate(_write_config(tmp_path, [dup, dict(dup, name="act2")]), logger)


def test_parse_afni_version():
    assert runtime._parse_afni_version("Precompiled binary linux: AFNI_26.0.09 'X'", "") == "26.0.09"
    assert runtime._parse_afni_version("nothing", "") is None


def test_probe_tool_versions_python_mismatch_warns(tmp_path, logger):
    """Issue #3: a Python minor mismatch is advisory (requires-python is the contract)."""
    from fmri_first_level_proc.reporting import get_warnings

    lock = tmp_path / "tools.lock.yaml"
    lock.write_text(yaml.safe_dump({"python": "2.7.0", "binaries": {"AFNI": "PLACEHOLDER"}}))
    runtime.probe_tool_versions(str(lock), logger=logger)  # does not raise
    [w] = get_warnings()
    assert (w["code"], w["severity"]) == ("PYTHON_VERSION_MISMATCH", "medium")

    here = f"{sys.version_info.major}.{sys.version_info.minor}.0"
    lock.write_text(yaml.safe_dump({"python": here, "binaries": {"AFNI": "PLACEHOLDER"}}))
    runtime.probe_tool_versions(str(lock), logger=logger)
    assert len(get_warnings()) == 1  # matching minor adds nothing


def test_probe_tool_versions_afni_mismatch_still_fails(tmp_path, monkeypatch, logger):
    import subprocess

    lock = tmp_path / "tools.lock.yaml"
    lock.write_text(yaml.safe_dump({"binaries": {"AFNI": "26.3.07"}}))
    fake = subprocess.CompletedProcess([], 0, stdout="Precompiled binary x: (Version AFNI_26.0.09 'X')", stderr="")
    monkeypatch.setattr(runtime.subprocess, "run", lambda *a, **k: fake)
    with pytest.raises(ToolVersionError, match="AFNI: expected 26.3.07, got 26.0.09"):
        runtime.probe_tool_versions(str(lock), logger=logger)


def test_lockfile_ships_as_package_data():
    assert cli._LOCKFILE.is_file()


@pytest.fixture
def dry_run_inputs(tmp_path, task_inputs):
    """Readable motion and events for 100 volumes; the scan is only read through 3dinfo."""
    np.savetxt(task_inputs["motion.txt"], np.zeros((100, 6)))
    Path(task_inputs["events.tsv"]).write_text("onset\tduration\ttrial_type\n10\t2\tA\n20\t2\tB\n")
    return task_inputs


def _dry_run(path, monkeypatch, **fake):
    FakeAfni(n_trs=100, tr=0.8, **fake).install(monkeypatch)
    monkeypatch.setattr(cli, "preflight_tool_environments", lambda **k: None)
    monkeypatch.setattr(cli, "probe_tool_versions", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["fmri-first-level-proc", "--config", path, "--dry-run"])
    cli.main()


def test_cli_dry_run(tmp_path, dry_run_inputs, monkeypatch):
    path = _write_config(tmp_path, [_task_act_block(tmp_path, dry_run_inputs)])
    _dry_run(path, monkeypatch)
    assert list((tmp_path / "out").iterdir()) == []  # nothing written


@pytest.mark.parametrize(
    "file_name, content, message",
    [("motion.txt", "\n".join(["0 0 0 0 0 0"] * 99), "99 rows"),
     ("motion.txt", "\n".join(["0 0 0 0 0"] * 100), "5 columns"),
     ("motion.txt", "\n".join(["nan 0 0 0 0 0"] * 100), "non-finite"),
     ("events.tsv", "onset\tduration\ttrial_type\n10\t2\tA\n80\t2\tB\n", "outside the 80 s scan"),
     ("events.tsv", "onset\tduration\ttrial_type\n-1\t2\tA\n20\t2\tB\n", "outside the 80 s scan"),
     ("events.tsv", "onset\tduration\ttrial_type\n10\t2\tA\n", "not found")],
)
def test_cli_dry_run_checks_input_files(tmp_path, dry_run_inputs, monkeypatch, caplog, file_name, content, message):
    Path(dry_run_inputs[file_name]).write_text(content + "\n")
    path = _write_config(tmp_path, [_task_act_block(tmp_path, dry_run_inputs)])
    with pytest.raises(SystemExit) as exc:
        _dry_run(path, monkeypatch)
    assert exc.value.code == 2
    assert message in caplog.text
    assert list((tmp_path / "out").iterdir()) == []  # the timing record is not written in a dry run


def test_cli_dry_run_checks_header_tr(tmp_path, dry_run_inputs, monkeypatch, caplog):
    path = _write_config(tmp_path, [_task_act_block(tmp_path, dry_run_inputs)], tr=2.0)
    with pytest.raises(SystemExit) as exc:
        _dry_run(path, monkeypatch)
    assert exc.value.code == 2
    assert "header TR" in caplog.text


def test_contrast_errors_are_config_errors(tmp_path, task_inputs, logger):
    block = _task_act_block(tmp_path, task_inputs, contrasts={"functions": ["1*A-1*C"], "labels": ["AvC"]})
    with pytest.raises(ConfigError, match="not in --cond_labels"):
        load_and_validate(_write_config(tmp_path, [block]), logger)
    conn = _task_act_block(tmp_path, task_inputs, type="task_conn", cond_beta_labels=["A", "B"],
                           connectivity={"calc_conn": None, "contrasts": {"functions": ["A-B"], "labels": ["AvB"]}})
    with pytest.raises(ConfigError, match="missing coefficients"):
        load_and_validate(_write_config(tmp_path, [conn]), logger)


@pytest.mark.parametrize(
    "second, collides",
    [({"out_dir": "same"}, False),
     ({"out_dir": "./same/", "out_file_pre": "sub01"}, True),
     ({"out_dir": "same", "extraction": {"extract_out_file_pre": "sub01"}}, True),
     ({"out_dir": "other", "out_file_pre": "sub01"}, False)],
)
def test_cross_block_output_collisions(tmp_path, task_inputs, logger, monkeypatch, second, collides):
    monkeypatch.chdir(tmp_path)
    first = _task_act_block(tmp_path, task_inputs, out_dir="same", name="first")
    other = _task_act_block(tmp_path, task_inputs, **{"name": "second", "out_file_pre": "sub02", **second})
    path = _write_config(tmp_path, [first, other])
    if collides:
        with pytest.raises(ConfigError, match="also used by"):
            load_and_validate(path, logger)
    else:
        assert len(load_and_validate(path, logger)) == 2


def test_block_reuses_one_prefix_for_its_own_outputs(tmp_path, task_inputs, logger):
    block = _task_act_block(tmp_path, task_inputs, extraction={"extract_out_file_pre": "sub01"})
    load_and_validate(_write_config(tmp_path, [block]), logger)


@pytest.mark.parametrize(
    "smoothing",
    ["6", {"enabled": "yes", "fwhm": 6}, {"enabled": True}, {"enabled": True, "fwhm": True},
     {"enabled": True, "fwhm": 0}, {"enabled": True, "fwhm": float("nan")}, {"enabled": True, "fwhm": 4.125}],
)
def test_invalid_smoothing_rejected(tmp_path, task_inputs, logger, smoothing):
    block = _task_act_block(tmp_path, task_inputs, smoothing=smoothing)
    with pytest.raises(ConfigError, match="smoothing"):
        load_and_validate(_write_config(tmp_path, [block]), logger)


def test_smoothing_and_roi_zero_handling_resolve(tmp_path, task_inputs, logger):
    (default,) = load_and_validate(_write_config(tmp_path, [_task_act_block(tmp_path, task_inputs)]), logger)
    assert (default.roi_zero_handling, default.smoothing_enabled, default.smoothing_fwhm) == ("exclude", False, None)

    block = _task_act_block(tmp_path, task_inputs, roi_zero_handling="include",
                            smoothing={"enabled": True, "fwhm": 4.5})
    (cfg,) = load_and_validate(_write_config(tmp_path, [block]), logger)
    assert (cfg.roi_zero_handling, cfg.smoothing_enabled, cfg.smoothing_fwhm) == ("include", True, 4.5)

    block = _task_act_block(tmp_path, task_inputs, roi_zero_handling="drop")
    with pytest.raises(ConfigError, match="roi_zero_handling"):
        load_and_validate(_write_config(tmp_path, [block]), logger)


def test_cli_config_error_exit_code(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "preflight_tool_environments", lambda **k: None)
    monkeypatch.setattr(cli, "probe_tool_versions", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["fmri-first-level-proc", "--config", str(tmp_path / "x.yaml")])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
