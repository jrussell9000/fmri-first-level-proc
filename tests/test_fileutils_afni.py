"""Filesystem helpers, the AFNI subprocess wrapper, and 3dNetCorr output handling."""

from pathlib import Path

import pytest

from fmri_first_level_proc.afni import clean_deconvolve_err, run_afni_command
from fmri_first_level_proc.connectivity import seed_to_voxel_conn
from fmri_first_level_proc.exceptions import GuardError, ToolExecutionError
from fmri_first_level_proc.fileutils import remove_files_from_dir

from fake_afni import FakeAfni

pytestmark = pytest.mark.level0_unit


def test_remove_files_from_dir_clears_contents_but_not_link_targets(tmp_path, logger):
    target = tmp_path / "out"
    (target / "sub").mkdir(parents=True)
    (target / "sub" / "f.txt").write_text("x")
    (target / "file.txt").write_text("x")
    keep = tmp_path / "keep"
    keep.mkdir()
    (keep / "precious.txt").write_text("x")
    (target / "dirlink").symlink_to(keep, target_is_directory=True)
    (target / "broken").symlink_to(tmp_path / "missing")

    remove_files_from_dir(target, logger=logger)

    assert target.is_dir() and list(target.iterdir()) == []
    assert (keep / "precious.txt").exists()


def test_remove_files_from_dir_guards(tmp_path, logger):
    with pytest.raises(GuardError):
        remove_files_from_dir("/", logger=logger)
    with pytest.raises(GuardError):
        remove_files_from_dir(Path.home(), logger=logger)
    remove_files_from_dir(tmp_path / "does-not-exist", logger=logger)  # warns, no error


def test_run_afni_command_accepts_paths_and_captures(tmp_path, logger):
    f = tmp_path / "hello world.txt"
    f.write_text("hi\n")
    assert run_afni_command(["cat", f], capture_output=True, logger=logger) == "hi\n"


def test_run_afni_command_failure_quotes_command(tmp_path, logger):
    with pytest.raises(ToolExecutionError) as exc:
        run_afni_command(["sh", "-c", "echo bad >&2; exit 3", tmp_path / "a b"], description="probe", logger=logger)
    msg = str(exc.value)
    assert "(probe)" in msg
    assert f"'{tmp_path / 'a b'}'" in msg  # shlex-quoted, copy-pasteable
    assert "stderr: bad" in msg


def test_clean_deconvolve_err(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    (tmp_path / "3dDeconvolve.err").write_text("")
    (out / "3dDeconvolve.err").write_text("")
    clean_deconvolve_err(out)
    clean_deconvolve_err(out)  # idempotent
    assert not (tmp_path / "3dDeconvolve.err").exists()
    assert not (out / "3dDeconvolve.err").exists()


@pytest.mark.parametrize("fishZ, kept", [(True, "WB_Z"), (False, "WB_CORR")])
def test_seed_to_voxel_conn_moves_map_and_cleans_up(tmp_path, monkeypatch, logger, fishZ, kept):
    fake = FakeAfni().install(monkeypatch)
    seed_to_voxel_conn("in.nii.gz", tmp_path, "pre", "seed.nii.gz", fishZ, False, condition="A", logger=logger)
    expected = tmp_path / ("pre_A_fishZ.nii.gz" if fishZ else "pre_A_corr.nii.gz")
    assert expected.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == [expected.name]
    assert ("-ts_wb_Z" in fake.calls[0]) is fishZ
