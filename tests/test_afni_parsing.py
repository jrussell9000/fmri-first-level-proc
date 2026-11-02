"""Tests for AFNI output parsing and connectivity helpers that do not need AFNI installed."""

from pathlib import Path

import numpy as np
import pytest

from fmri_first_level_proc import templates
from fmri_first_level_proc.connectivity import (
    build_conn_output_path,
    compute_matrix_contrast,
    format_netcorr_mat,
)
from fmri_first_level_proc.exceptions import GuardError, InputError
from fmri_first_level_proc.fileutils import sanitize_filename_label
from fmri_first_level_proc.preprocessing import compute_tissue_derivative, prepare_motion_file
from fmri_first_level_proc.templates import extract_roi_stats

pytestmark = pytest.mark.level0_unit

NETCC = """\
# 2  # Number of network ROIs
# 2  # Number of netcc matrices
# WITH_ROI_LABELS
         1         2
     ROI_1     ROI_2
# CC
  1.000000  0.500000
  0.500000  1.000000
# FZ
  4.000000  0.549306
  0.549306  4.000000
"""


@pytest.mark.parametrize(
    "fishZ, expected",
    [
        (False, "1.000000\t0.500000\n0.500000\t1.000000\n#\tFZ\n4.000000\t0.549306\n0.549306\t4.000000\n"),
        (True, "4.000000\t0.549306\n0.549306\t4.000000\n"),
    ],
)
def test_format_netcorr_mat(tmp_path, fishZ, expected):
    # Characterizes current behavior: the CC section ends at a '# Z' header or EOF,
    # so without -fish_z (no FZ section in real output) CC runs to EOF.
    src = tmp_path / "x_000.netcc"
    src.write_text(NETCC)
    out = tmp_path / "mat.txt"
    format_netcorr_mat(str(src), fishZ, False, str(out))
    assert out.read_text() == expected


def test_compute_matrix_contrast(tmp_path, logger):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    np.savetxt(a, [[1.0, 2.0], [3.0, 4.0]], delimiter="\t")
    np.savetxt(b, [[1.0, 1.0], [1.0, 1.0]], delimiter="\t")
    out = tmp_path / "c.txt"
    compute_matrix_contrast([str(a), str(b)], ["1", "-1"], str(out), logger)
    np.testing.assert_allclose(np.loadtxt(out, delimiter="\t"), [[0, 1], [2, 3]])


def test_compute_matrix_contrast_shape_mismatch(tmp_path, logger):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    np.savetxt(a, np.eye(2), delimiter="\t")
    np.savetxt(b, np.eye(3), delimiter="\t")
    with pytest.raises(InputError):
        compute_matrix_contrast([str(a), str(b)], ["1", "-1"], str(tmp_path / "c.txt"), logger)


@pytest.mark.parametrize(
    "calc_conn, fishZ, pcorr, suffix",
    [
        ("parcellated", False, False, "_corr_mat.txt"),
        ("parcellated", True, True, "_pcorr_fishZ_mat.txt"),
        ("seed_to_voxel", True, False, "_fishZ.nii.gz"),
        ("seed_to_voxel", False, True, "_pcorr.nii.gz"),
    ],
)
def test_build_conn_output_path(calc_conn, fishZ, pcorr, suffix):
    assert build_conn_output_path("/o", "pre", "A", fishZ, pcorr, calc_conn) == Path(f"/o/pre_A{suffix}")
    assert build_conn_output_path("/o", "pre", None, fishZ, pcorr, calc_conn) == Path(f"/o/pre{suffix}")


def test_sanitize_filename_label():
    assert sanitize_filename_label("Fear - Neutral/x") == "Fear_-_Neutral_x"


def test_extract_roi_stats_parses_1dformat(monkeypatch, logger):
    fake = "#File\tSub-brick\n#\tNZMean_1\tNZMean_3\n# f.nii[0]\n1.5\t2.5\n# f.nii[1]\n3.5\t4.5\n"
    monkeypatch.setattr(templates, "run_afni_command", lambda *a, **k: fake)
    df = extract_roi_stats("f.nii", "tpl.nii", "mean", logger=logger)
    assert list(df.columns) == ["ROI_1", "ROI_3"]
    assert df.values.tolist() == [[1.5, 2.5], [3.5, 4.5]]


def test_extract_roi_stats_bad_output(monkeypatch, logger):
    monkeypatch.setattr(templates, "run_afni_command", lambda *a, **k: "garbage")
    with pytest.raises(GuardError):
        extract_roi_stats("f.nii", "tpl.nii", "mean", logger=logger)


def test_prepare_motion_file_truncates(tmp_path, logger):
    src = tmp_path / "motion.txt"
    np.savetxt(src, np.arange(24, dtype=float).reshape(2, 12))
    out = prepare_motion_file(str(src), 6, str(tmp_path), "pre", "concat", logger)
    assert np.loadtxt(out).shape == (2, 6)
    with pytest.raises(InputError):
        prepare_motion_file(str(src), 18, str(tmp_path), "pre", "concat", logger)


def test_compute_tissue_derivative(tmp_path, logger):
    src = tmp_path / "csf.txt"
    np.savetxt(src, [1.0, 3.0, 6.0])
    out = compute_tissue_derivative(str(src), str(tmp_path), "pre", "CSF", logger)
    np.testing.assert_allclose(np.loadtxt(out), [0.0, 2.0, 3.0])
