"""Real-AFNI test of abcd/staging.py: the commands it builds, on small synthetic NIfTIs.

Opt-in, like test_real_afni.py: run with ``-m afni`` where AFNI is installed.
"""

import json
import shutil

import numpy as np
import pandas as pd
import pytest

nib = pytest.importorskip("nibabel")
pytest.importorskip("scipy")

from fmri_first_level_proc.abcd import staging  # noqa: E402

pytestmark = [
    pytest.mark.afni,
    pytest.mark.skipif(shutil.which("3dcalc") is None, reason="AFNI not installed"),
]

TR = 0.8
SUBJ, SES = "sub-TEST0001", "ses-00A"
N_FRAMES, N_NSS = 370, 8
PROB_AFFINE = np.diag([1.0, 1.0, 1.0, 1.0])
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
        cols["global_signal"] = np.arange(N_FRAMES, dtype=float) + 100.0
        pd.DataFrame(cols).to_csv(f"{stem}_desc-confounds_timeseries.tsv", sep="\t", index=False)
        if "nback" in rid:
            (root / f"{SUBJ}_{SES}_{rid}_events.tsv").write_text(EVENTS)
    for name, fill in zip(staging.probseg_names(SUBJ, SES), (0.0, 1.0, 1.0), strict=True):
        _save(root / name, np.full((8, 8, 8), fill, np.float32), PROB_AFFINE)
    label = f"{SUBJ}_{SES}_space-MNI152NLin2009cAsym_res-1_label-CSF_mask.nii.gz"
    _save(root / label, np.ones((8, 8, 8), np.uint8), PROB_AFFINE)
    (root / "_complete.json").write_text(json.dumps({"runs": {r: [] for r in runs}}))
    return runs


def test_staging_commands_trim_mask_concatenate_and_average(tmp_path, monkeypatch):
    monkeypatch.setattr(staging, "CSF_MIN_VOXELS", 1)  # the 4^3 test grid holds only 64
    raw = tmp_path / "raw"
    _seed(raw, np.random.default_rng(0))
    work = tmp_path / "work"
    work.mkdir()
    validity = {rid: (True, "") for rid in ("task-nback_run-01", "task-nback_run-02")}
    sess = staging.Session(SUBJ, SES, raw, "fixed", work, validity)
    by_task = sess.runs_by_task(sess.read_marker())

    nback, _ = sess.stage_task("nback", by_task["nback"], TR)
    assert not any(r.excluded for r in nback)
    first = nib.load(str(nback[0].bold))
    assert first.shape[3] == N_FRAMES - N_NSS
    assert first.header.get_zooms()[3] == pytest.approx(TR)
    # 3dcalc's [n..$] kept the right frames: index n is the first one left.
    assert np.asarray(first.dataobj)[0, 0, 0, 0] == pytest.approx(N_NSS + 1)

    paths = sess.nback_paths(nback, TR)
    assert nib.load(paths["scan_path"]).shape[3] == 2 * (N_FRAMES - N_NSS)
    assert np.loadtxt(paths["motion_path"]).shape == (2 * (N_FRAMES - N_NSS), 12)

    rest, raws = sess.stage_task("rest", by_task["rest"], TR)
    rest_paths, reason = sess.rest_paths(rest, raws)
    assert reason is None
    for key in ("WM_paths", "CSF_paths", "GS_paths"):
        assert np.loadtxt(rest_paths[key][0]).shape == (N_FRAMES - N_NSS,)
