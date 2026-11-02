"""Real-AFNI tests: the output formats the package parses, and every pipeline end to end.

Opt-in: these run only where AFNI is installed and are selected with ``-m afni``.
Datasets are synthetic (AFNI's jRandomDataset), so no imaging data is needed.

    docker build -t fflp-afni:26.3.07 tests/docker
    docker run --rm -v "$PWD":/src:ro -w /tmp fflp-afni:26.3.07 \
        pytest /src/tests -m afni -p no:cacheprovider
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
import yaml

from fmri_first_level_proc import DISPATCH, runtime
from fmri_first_level_proc.afni import get_3dinfo_properties
from fmri_first_level_proc.config import load_and_validate
from fmri_first_level_proc.connectivity import format_netcorr_mat
from fmri_first_level_proc.pipelines.task_act import _get_subbrik_stat_aux
from fmri_first_level_proc.templates import extract_roi_stats

pytestmark = [
    pytest.mark.afni,
    pytest.mark.skipif(shutil.which("3dDeconvolve") is None, reason="AFNI not installed"),
]

N_TRS = 120
TR = 2.0
ONSETS = {"A": [10, 50, 90, 130, 170, 210], "B": [30, 70, 110, 150, 190, 230]}


def _afni(*args, cwd):
    subprocess.run(list(args), cwd=cwd, check=True, capture_output=True, text=True,
                   env={**os.environ, "AFNI_COMPRESSOR": "GZIP"})


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    """Synthetic 20x20x12 scans (TR 2 s), a 3-ROI parcellation, a binary seed, and 1D/TSV inputs."""
    d = tmp_path_factory.mktemp("afni_data")
    rng = np.random.default_rng(0)
    for name in ("scan", "run1", "run2"):
        _afni("3dcalc", "-a", f"jRandomDataset:20,20,12,{N_TRS}", "-expr", "a*10+1000",
              "-datum", "float", "-prefix", f"{name}.nii.gz", cwd=d)
        _afni("3drefit", "-TR", str(TR), f"{name}.nii.gz", cwd=d)
    _afni("3dcalc", "-a", "scan.nii.gz[0]", "-expr", "1+step(i-6)+step(i-13)",
          "-datum", "short", "-prefix", "parc.nii.gz", cwd=d)
    _afni("3dcalc", "-a", "scan.nii.gz[0]", "-expr", "within(i,4,8)*within(j,4,8)*within(k,3,6)",
          "-datum", "short", "-prefix", "seed.nii.gz", cwd=d)
    rows = ["onset\tduration\ttrial_type"] + [f"{o}\t2\t{c}" for c, os_ in ONSETS.items() for o in os_]
    (d / "events.tsv").write_text("\n".join(rows) + "\n")
    for name, cols in (("motion.txt", 12), ("motion_run1.txt", 6), ("motion_run2.txt", 6)):
        np.savetxt(d / name, rng.normal(0, 0.01, (N_TRS, cols)))
    for name in ("csf.txt", "wm.txt", "csf_run1.txt", "csf_run2.txt", "wm_run1.txt", "wm_run2.txt"):
        np.savetxt(d / name, rng.normal(100, 1, N_TRS))
    return d


@pytest.fixture(scope="module")
def bucket(data):
    """A real 3dDeconvolve bucket with two stimuli and one GLT."""
    timing = {}
    for cond, onsets in ONSETS.items():
        timing[cond] = data / f"{cond}_onsets.txt"
        timing[cond].write_text("\n".join(map(str, onsets)) + "\n")
    _afni("3dDeconvolve", "-quiet", "-input", "scan.nii.gz", "-polort", "A", "-num_stimts", "2",
          "-stim_times", "1", timing["A"], "GAM(8.6,.547,2)", "-stim_label", "1", "A",
          "-stim_times", "2", timing["B"], "GAM(8.6,.547,2)", "-stim_label", "2", "B",
          "-num_glt", "1", "-gltsym", "SYM: 1*A -1*B", "-glt_label", "1", "AvB",
          "-fout", "-rout", "-tout", "-bucket", "bucket.nii.gz", "-jobs", "1", cwd=data)
    return data / "bucket.nii.gz"


# ---------------------------------------------------------------------------
# Format contracts
# ---------------------------------------------------------------------------

def test_afni_version_parses_and_matches_lockfile():
    out = subprocess.run(["afni", "-ver"], capture_output=True, text=True)
    version = runtime._parse_afni_version(out.stdout, out.stderr)
    lock = yaml.safe_load((Path(runtime.__file__).parent / "data" / "tools.lock.yaml").read_text())
    assert version == lock["binaries"]["AFNI"]


def test_combined_3dinfo_is_one_call(data, monkeypatch, logger):
    calls = []
    import fmri_first_level_proc.afni as afni_mod
    real = afni_mod.run_afni_command
    monkeypatch.setattr(afni_mod, "run_afni_command", lambda cmd, **k: calls.append(cmd) or real(cmd, **k))

    props = get_3dinfo_properties(data / "parc.nii.gz", logger=logger)

    assert props == {"space": "ORIG", "orient": "RAI", "spacing": "1.000000\t1.000000\t1.000000", "dmax": "3"}
    assert len(calls) == 1  # no per-flag fallback
    assert get_3dinfo_properties(data / "scan.nii.gz", logger=logger)["orient"] == "RAI"


def test_roistats_parse(data, logger):
    df = extract_roi_stats(f"{data / 'scan.nii.gz'}[0..1]", data / "parc.nii.gz", "mean", logger=logger)
    assert list(df.columns) == ["ROI_1", "ROI_2", "ROI_3"] and df.shape == (2, 3)
    med = extract_roi_stats(data / "scan.nii.gz[0]", data / "seed.nii.gz", "median", logger=logger)
    assert list(med.columns) == ["ROI_1"]


def test_brick_stataux_gives_tstat_dof(bucket, logger):
    labels = subprocess.run(["3dinfo", "-label", bucket], capture_output=True, text=True).stdout.strip().split("|")
    t_index = labels.index("A#0_Tstat")
    [dof] = _get_subbrik_stat_aux(str(bucket), t_index, logger=logger)
    assert dof == N_TRS - 2 - 3  # TRs - stimuli - polort A (1 + floor(240 s / 150))


@pytest.mark.parametrize(
    "flags, sections",
    [([], ["CC"]), (["-fish_z"], ["CC", "FZ"]), (["-part_corr"], ["CC", "PC", "PCB"]),
     (["-fish_z", "-part_corr"], ["CC", "FZ", "PC", "PCB"])],
)
def test_netcorr_sections(data, tmp_path, flags, sections):
    _afni("3dNetCorr", "-prefix", tmp_path / "nc", "-inset", data / "scan.nii.gz",
          "-in_rois", data / "parc.nii.gz", "-push_thru_many_zeros", *flags, cwd=tmp_path)
    lines = (tmp_path / "nc_000.netcc").read_text().splitlines()
    headers = [ln.split()[1] for ln in lines if ln.startswith("# ") and len(ln.split()) == 2]
    assert headers == ["WITH_ROI_LABELS", *sections]


@pytest.mark.parametrize("fishZ, pcorr", [(False, False), (True, False), (False, True)])
def test_format_netcorr_mat_extracts_symmetric_matrix(data, tmp_path, fishZ, pcorr):
    flags = (["-fish_z"] if fishZ else []) + (["-part_corr"] if pcorr else [])
    _afni("3dNetCorr", "-prefix", tmp_path / "nc", "-inset", data / "scan.nii.gz",
          "-in_rois", data / "parc.nii.gz", "-push_thru_many_zeros", *flags, cwd=tmp_path)
    out = tmp_path / "mat.txt"
    format_netcorr_mat(tmp_path / "nc_000.netcc", fishZ, pcorr, out)
    mat = np.loadtxt(out, delimiter="\t")
    assert mat.shape == (3, 3)
    np.testing.assert_allclose(mat, mat.T, atol=1e-4)


@pytest.mark.xfail(strict=True, reason="issue #1: fishZ+pcorr extracts PCB (partial-correlation "
                   "betas, asymmetric); AFNI writes no Fisher-Z partial correlation")
def test_format_netcorr_mat_fishz_pcorr_is_not_pcb(data, tmp_path):
    _afni("3dNetCorr", "-prefix", tmp_path / "nc", "-inset", data / "scan.nii.gz",
          "-in_rois", data / "parc.nii.gz", "-push_thru_many_zeros", "-fish_z", "-part_corr", cwd=tmp_path)
    netcc = (tmp_path / "nc_000.netcc").read_text().splitlines()
    pcb = [ln.split() for ln in netcc[netcc.index("# PCB") + 1:] if ln.strip()]
    out = tmp_path / "mat.txt"
    format_netcorr_mat(tmp_path / "nc_000.netcc", True, True, out)
    extracted = [ln.split("\t") for ln in out.read_text().splitlines()]
    assert extracted != pcb  # PCB holds regression betas, not Fisher-Z partial correlations


# ---------------------------------------------------------------------------
# Pipelines end to end
# ---------------------------------------------------------------------------

def _resolve(tmp_path, block, template):
    cfg = {"global": {"tr": TR, "num_cores": 2, "template_path": str(template) if template else None},
           "analyses": [block]}
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg))
    (resolved,) = load_and_validate(str(path))
    return resolved


def _task_paths(data):
    return {"scan_path": str(data / "scan.nii.gz"), "task_timing_path": str(data / "events.tsv"),
            "motion_path": str(data / "motion.txt"), "CSF_path": str(data / "csf.txt"),
            "WM_path": str(data / "wm.txt")}


def _rest_paths(data):
    return {"scan_paths": [str(data / "run1.nii.gz"), str(data / "run2.nii.gz")],
            "motion_paths": [str(data / "motion_run1.txt"), str(data / "motion_run2.txt")],
            "CSF_paths": [str(data / "csf_run1.txt"), str(data / "csf_run2.txt")],
            "WM_paths": [str(data / "wm_run1.txt"), str(data / "wm_run2.txt")]}


def _assert_ok(result):
    assert result.status == "success", result.warnings
    assert result.output_files
    assert all(Path(p).exists() for p in result.output_files)


@pytest.fixture
def act_result(data, tmp_path, monkeypatch, logger):
    monkeypatch.chdir(tmp_path)
    block = {
        "name": "act", "type": "task_act", "paths": _task_paths(data),
        "out_dir": str(tmp_path / "act"), "out_file_pre": "sub01", "cond_labels": ["A", "B"],
        "average_type": "mean", "hrf_model": "GAM", "include_motion_derivs": True,
        "use_tissue_derivs": True, "fd_threshold": 0.9,
        "contrasts": {"functions": ["1*A-1*B"], "labels": ["AvB"]},
        "extraction": {"stat_buckets": ["Coef", "Tstat", "Zstat"], "extract_out_file_pre": "sub01_parc",
                       "extract_resids": True, "extract_raw_ptseries": True},
    }
    return tmp_path / "act", DISPATCH["task_act"](_resolve(tmp_path, block, data / "parc.nii.gz"), logger)


def test_task_act_end_to_end(act_result):
    out, result = act_result
    _assert_ok(result)
    for stat in ("Coef", "Tstat", "Zstat"):
        assert (out / f"sub01_parc_{stat}_bucket.nii.gz").exists()
        csv = (out / f"sub01_parc_{stat}_parcellated.csv").read_text().splitlines()
        assert len(csv) == 1 + 3  # header + A, B, AvB
    assert json.loads((out / "sub01_manifest.json").read_text())["status"] == "completed"


def test_task_act_stat_bucket_labels(act_result):
    """Issue #4: labels come from 3dinfo -label without quotes, and GLTs keep their configured label."""
    out, _ = act_result
    for stat in ("Coef", "Tstat", "Zstat"):
        index = json.loads((out / f"sub01_parc_{stat}_index.json").read_text())
        assert index == {"A": 0, "B": 1, "AvB": 2}
    rows = (out / "sub01_parc_Zstat_parcellated.csv").read_text().splitlines()[1:]
    assert [r.split(",")[0] for r in rows] == ["A", "B", "AvB"]


def test_task_conn_end_to_end(data, tmp_path, monkeypatch, logger):
    monkeypatch.chdir(tmp_path)
    block = {
        "name": "conn", "type": "task_conn", "paths": _task_paths(data),
        "out_dir": str(tmp_path / "conn"), "out_file_pre": "sub01", "cond_beta_labels": ["A", "B"],
        "average_type": "mean", "hrf_model": "GAM", "include_motion_derivs": False, "fd_threshold": 0.9,
        "extraction": {"extract_pbseries": True, "extract_out_file_pre": "sub01_parc"},
        "connectivity": {"calc_conn": "parcellated", "conn_out_file_pre": "sub01_fc", "fishZ": True,
                         "contrasts": {"functions": ["1*A-1*B"], "labels": ["AvB"]}},
    }
    result = DISPATCH["task_conn"](_resolve(tmp_path, block, data / "parc.nii.gz"), logger)
    _assert_ok(result)
    out = tmp_path / "conn"
    for cond in ("A", "B"):
        info = subprocess.run(["3dinfo", "-nv", out / f"sub01_concat_bseries_{cond}.nii.gz"],
                              capture_output=True, text=True).stdout.strip()
        assert info == str(len(ONSETS[cond]))  # one beta per trial
        assert np.loadtxt(out / f"sub01_fc_{cond}_fishZ_mat.txt", delimiter="\t").shape == (3, 3)
    assert np.loadtxt(out / "sub01_fc_AvB_fishZ_mat.txt", delimiter="\t").shape == (3, 3)


@pytest.mark.parametrize("sequenced", [False, True])
def test_rest_conn_end_to_end(data, tmp_path, monkeypatch, logger, sequenced):
    monkeypatch.chdir(tmp_path)
    block = {
        "name": "rest", "type": "rest_conn", "paths": _rest_paths(data),
        "out_dir": str(tmp_path / "rest"), "out_file_pre": "sub01", "average_type": "mean",
        "bandpass": [0.01, 0.1], "motion_deriv_degree": 1, "fd_threshold": 0.9,
        "use_sequenced_bandpass": sequenced, "use_tissue_derivs": True,
        "extraction": {"extract_ptseries": True, "extract_out_file_pre": "sub01_parc"},
        "connectivity": {"calc_conn": "parcellated", "conn_out_file_pre": "sub01_fc", "fishZ": True},
    }
    result = DISPATCH["rest_conn"](_resolve(tmp_path, block, data / "parc.nii.gz"), logger)
    _assert_ok(result)
    out = tmp_path / "rest"
    nv = subprocess.run(["3dinfo", "-nv", out / "sub01_concat_residual_dtseries.nii.gz"],
                        capture_output=True, text=True).stdout.strip()
    assert nv == str(2 * N_TRS)
    assert np.loadtxt(out / "sub01_fc_fishZ_mat.txt", delimiter="\t").shape == (3, 3)


def test_rest_conn_seed_to_voxel(data, tmp_path, monkeypatch, logger):
    monkeypatch.chdir(tmp_path)
    block = {
        "name": "rest", "type": "rest_conn", "paths": _rest_paths(data),
        "out_dir": str(tmp_path / "rest"), "out_file_pre": "sub01", "average_type": "mean",
        "bandpass": [0.01, 0.1], "motion_deriv_degree": 1, "fd_threshold": 0.9,
        "connectivity": {"calc_conn": "seed_to_voxel", "conn_out_file_pre": "sub01_fc", "fishZ": True},
    }
    result = DISPATCH["rest_conn"](_resolve(tmp_path, block, data / "seed.nii.gz"), logger)
    _assert_ok(result)
    assert (tmp_path / "rest" / "sub01_fc_fishZ.nii.gz").exists()
    assert not (tmp_path / "rest" / "sub01_fc_000_INDIV").exists()
