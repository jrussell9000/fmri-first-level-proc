"""Config resolution, runtime version probing, and CLI dry-run tests."""

import sys

import pytest
import yaml

from fmri_first_level_proc import cli, runtime
from fmri_first_level_proc.config import load_and_validate
from fmri_first_level_proc.exceptions import ConfigError, InputError, ToolVersionError

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


def test_probe_tool_versions_python_mismatch(tmp_path, logger):
    lock = tmp_path / "tools.lock.yaml"
    lock.write_text(yaml.safe_dump({"python": "2.7.0", "binaries": {"AFNI": "PLACEHOLDER"}}))
    with pytest.raises(ToolVersionError):
        runtime.probe_tool_versions(str(lock), logger=logger)
    here = f"{sys.version_info.major}.{sys.version_info.minor}.0"
    lock.write_text(yaml.safe_dump({"python": here, "binaries": {"AFNI": "PLACEHOLDER"}}))
    runtime.probe_tool_versions(str(lock), logger=logger)


def test_lockfile_ships_as_package_data():
    assert cli._LOCKFILE.is_file()


def test_cli_dry_run(tmp_path, task_inputs, monkeypatch):
    path = _write_config(tmp_path, [_task_act_block(tmp_path, task_inputs)])
    monkeypatch.setattr(cli, "preflight_tool_environments", lambda **k: None)
    monkeypatch.setattr(cli, "probe_tool_versions", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["fmri-first-level-proc", "--config", path, "--dry-run"])
    cli.main()


def test_cli_config_error_exit_code(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "preflight_tool_environments", lambda **k: None)
    monkeypatch.setattr(cli, "probe_tool_versions", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["fmri-first-level-proc", "--config", str(tmp_path / "x.yaml")])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
