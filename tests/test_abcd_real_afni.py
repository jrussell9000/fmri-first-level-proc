"""Real-AFNI test of abcd/staging.py: the commands it builds, on small synthetic NIfTIs.

Opt-in, like test_real_afni.py: run with ``-m afni`` where AFNI is installed.
"""

import json
import shutil

import numpy as np
import pandas as pd
import pytest

nib = pytest.importorskip("nibabel")

from fmri_first_level_proc.abcd import staging  # noqa: E402

pytestmark = [
    pytest.mark.afni,
    pytest.mark.skipif(shutil.which("3dcalc") is None, reason="AFNI not installed"),
]

TR = 0.8
SUBJ, SES = "sub-TEST0001", "ses-00A"
N_FRAMES, N_NSS = 370, 8
REF_AFFINE = np.array([[-2.0, 0, 0, 6.5], [0, -2.0, 0, 6.5], [0, 0, 2.0, 0.5], [0, 0, 0, 1.0]])
EVENTS = (
    "onset\tduration\tresponse_time\ttrial_type\n"
    '0.000\t6.400\t"n/a"\t"dummy"\n'
    '6.410\t2.890\t"n/a"\t"cue"\n'
    '9.410\t1.900\t"n/a"\t"0_back_posface"\n'
)


def _save(path, data, affine, zooms=None):
    img = nib.Nifti1Image(np.asarray(data), affine)
    if zooms:
        img.header.set_zooms(zooms)
    nib.save(img, str(path))


def _seed(root, rng):
    root.mkdir()
    runs = ("task-nback_run-01", "task-nback_run-02", "task-rest_run-01")
    for rid in runs:
        stem = root / f"{SUBJ}_{SES}_{rid}"
        bold = rng.normal(100, 1, (4, 4, 4, N_FRAMES)).astype(np.float32)
        bold[0, 0, 0, :] = np.arange(N_FRAMES, dtype=np.float32) + 1  # the frame's own index
        _save(f"{stem}_space-MNI152NLin2009cAsym_bold.nii.gz", bold, REF_AFFINE, (2, 2, 2, TR))
        _save(f"{stem}_space-MNI152NLin2009cAsym_brainmask.nii.gz", np.ones((4, 4, 4), np.uint8), REF_AFFINE)
        cols = {c: rng.normal(size=N_FRAMES) for c in staging.MOTION_BASE}
        cols.update({f"non_steady_state_outlier_{i:02d}": np.eye(N_FRAMES)[i] for i in range(N_NSS)})
        # cloudpipe writes these over every frame, NSS included. Here csf is the voxel
        # holding each frame's own index, so its trimmed column must line up with the
        # trimmed BOLD frame for frame.
        cols["csf"] = bold[0, 0, 0, :].astype(float)
        cols["white_matter"] = bold.reshape(-1, N_FRAMES).mean(axis=0, dtype=np.float64)
        pd.DataFrame(cols).to_csv(f"{stem}_desc-confounds_timeseries.tsv", sep="\t", index=False)
        if "nback" in rid:
            (root / f"{SUBJ}_{SES}_{rid}_events.tsv").write_text(EVENTS)
    (root / "_complete.json").write_text(json.dumps({"runs": {r: [] for r in runs}}))
    return runs


def test_staging_commands_trim_mask_and_average(tmp_path):
    raw = tmp_path / "raw"
    _seed(raw, np.random.default_rng(0))
    work = tmp_path / "work"
    work.mkdir()
    validity = {rid: (True, "") for rid in ("task-nback_run-01", "task-nback_run-02")}
    sess = staging.Session(SUBJ, SES, raw, work, validity)
    by_task = sess.runs_by_task(sess.read_marker())

    nback, _ = sess.stage_task("nback", by_task["nback"], TR)
    assert not any(r.excluded for r in nback)
    # Staged runs are uncompressed NIfTI: each analysis reads them several times.
    assert nback[0].bold.suffix == ".nii"
    assert nback[0].bold.read_bytes()[:2] != b"\x1f\x8b"  # no gzip magic
    first = nib.load(str(nback[0].bold))
    assert first.shape[3] == N_FRAMES - N_NSS
    assert first.header.get_zooms()[3] == pytest.approx(TR)
    # 3dcalc's [n..$] kept the right frames: index n is the first one left.
    assert np.asarray(first.dataobj)[0, 0, 0, 0] == pytest.approx(N_NSS + 1)

    paths = sess.nback_paths(nback)
    assert paths["run_labels"] == [1, 2]
    for scan, motion in zip(paths["scan_paths"], paths["motion_paths"], strict=True):
        assert nib.load(scan).shape[3] == N_FRAMES - N_NSS
        assert np.loadtxt(motion).shape == (N_FRAMES - N_NSS, 12)

    rest, raws = sess.stage_task("rest", by_task["rest"], TR)
    rest_paths, reason = sess.rest_paths(rest, raws)
    assert reason is None
    for key in ("WM_paths", "CSF_paths"):
        assert np.loadtxt(rest_paths[key][0]).shape == (N_FRAMES - N_NSS,)
    assert "GS_paths" not in rest_paths
    # The trimmed column lines up with AFNI's trimmed BOLD: the voxel holding the frame
    # index, read from the staged BOLD, equals the CSF regressor frame for frame.
    trimmed = np.asarray(nib.load(str(rest[0].bold)).dataobj)
    np.testing.assert_array_equal(np.loadtxt(rest_paths["CSF_paths"][0]), trimmed[0, 0, 0])
    np.testing.assert_allclose(
        np.loadtxt(rest_paths["WM_paths"][0]), trimmed.reshape(-1, trimmed.shape[3]).mean(axis=0), rtol=1e-6
    )
