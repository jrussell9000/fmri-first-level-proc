"""BIDS input discovery/output paths and AFNI preflight binary checks."""

import json
import stat

import pytest

from fmri_first_level_proc import runtime
from fmri_first_level_proc.bids import build_bids_output_path, discover_inputs, write_dataset_description
from fmri_first_level_proc.exceptions import ToolUnavailableError
from fmri_first_level_proc.reporting import get_warnings

pytestmark = pytest.mark.level0_unit


def _touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("")
    return path


def test_discover_inputs_task(tmp_path, logger):
    func = tmp_path / "deriv" / "sub-01" / "ses-1" / "func"
    bold = _touch(func / "sub-01_ses-1_task-nback_desc-preproc_bold.nii.gz")
    motion = _touch(func / "sub-01_ses-1_task-nback_desc-confounds_regressors.tsv")
    events = _touch(func / "sub-01_ses-1_task-nback_events.tsv")
    _touch(func / "sub-01_ses-1_task-rest_desc-preproc_bold.nii.gz")  # other task, must not match

    found = discover_inputs([str(tmp_path / "deriv")], "01", "1", "nback", "task_act", logger=logger)

    assert found.scan_path == str(bold)
    assert found.motion_path == str(motion)
    assert found.task_timing_path == str(events)
    assert found.CSF_path is None


def test_discover_inputs_rest_lists_sorted_and_collision_warns(tmp_path, logger):
    for root in ("a", "b"):
        func = tmp_path / root / "sub-01" / "func"
        for run in (2, 1):
            _touch(func / f"sub-01_task-rest_run-{run}_desc-preproc_bold.nii.gz")
    found = discover_inputs([str(tmp_path / "a"), str(tmp_path / "b")], "01", None, "rest", "rest_conn", logger=logger)

    assert [p.rsplit("/", 1)[1] for p in found.scan_paths] == [
        "sub-01_task-rest_run-1_desc-preproc_bold.nii.gz",
        "sub-01_task-rest_run-2_desc-preproc_bold.nii.gz",
    ]
    assert found.source_dirs["scan_paths"] == str(tmp_path / "a")
    assert [w["code"] for w in get_warnings()] == ["DISCOVERY_COLLISION"]


def test_build_bids_output_path():
    path = build_bids_output_path("/out", {"sub": "01", "ses": "1", "task": "n back", "desc": None}, "bold", ".nii.gz")
    assert path == "/out/sub-01/ses-1/func/sub-01_ses-1_task-n_back_bold.nii.gz"
    with pytest.raises(ValueError):
        build_bids_output_path("/out", {"ses": "1"}, "bold", ".nii.gz")


def test_write_dataset_description_is_idempotent(tmp_path):
    deriv = tmp_path / "new" / "deriv"
    write_dataset_description(str(deriv))
    desc = json.loads((deriv / "dataset_description.json").read_text())
    assert desc["DatasetType"] == "derivative"
    (deriv / "dataset_description.json").write_text('{"Name": "external"}')
    write_dataset_description(str(deriv))
    assert json.loads((deriv / "dataset_description.json").read_text()) == {"Name": "external"}


def _fake_afni_home(tmp_path, skip=(), non_exec=()):
    home = tmp_path / "abin"
    home.mkdir()
    for name in runtime._AFNI_BINARIES:
        if name in skip:
            continue
        p = home / name
        p.write_text("#!/bin/sh\n")
        if name not in non_exec:
            p.chmod(p.stat().st_mode | stat.S_IXUSR)
    return home


def test_preflight_passes_with_all_binaries(tmp_path, logger):
    runtime.preflight_tool_environments(afni_home=str(_fake_afni_home(tmp_path)), logger=logger)


def test_preflight_reports_missing_and_non_executable(tmp_path, logger):
    home = _fake_afni_home(tmp_path, skip={"3dLSS"}, non_exec={"3dinfo"})
    with pytest.raises(ToolUnavailableError) as exc:
        runtime.preflight_tool_environments(afni_home=str(home), logger=logger)
    assert "3dLSS" in str(exc.value) and "3dinfo" in str(exc.value)
    assert "3dcalc" not in str(exc.value)
