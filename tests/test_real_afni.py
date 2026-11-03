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
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import yaml

from fmri_first_level_proc import DISPATCH, runtime
from fmri_first_level_proc.afni import get_3dinfo_properties
from fmri_first_level_proc.config import load_and_validate
from fmri_first_level_proc.connectivity import format_netcorr_mat, seed_to_voxel_conn, seed_to_voxel_smoothed
from fmri_first_level_proc.design import (
    build_decon_base_command,
    compute_dof,
    polort_a_regressors,
    trial_energy_ratios,
)
from fmri_first_level_proc.inputs import check_inputs
from fmri_first_level_proc.pipelines.task_act import _get_subbrik_stat_aux
from fmri_first_level_proc.preprocessing import scale_to_psc
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


def test_format_netcorr_mat_fishz_pcorr_is_fisher_z_of_pc(data, tmp_path):
    """Issue #1: fishZ+pcorr is arctanh(PC) with AFNI's |z| <= 4 cap, not the PCB betas."""
    _afni("3dNetCorr", "-prefix", tmp_path / "nc", "-inset", data / "scan.nii.gz",
          "-in_rois", data / "parc.nii.gz", "-push_thru_many_zeros", "-fish_z", "-part_corr", cwd=tmp_path)
    netcc = (tmp_path / "nc_000.netcc").read_text().splitlines()
    start, stop = netcc.index("# PC") + 1, netcc.index("# PCB")
    pc = np.array([ln.split() for ln in netcc[start:stop] if ln.strip()], dtype=float)
    cc = np.array([ln.split() for ln in netcc[netcc.index("# CC") + 1:netcc.index("# FZ")]], dtype=float)
    fz = np.array([ln.split() for ln in netcc[netcc.index("# FZ") + 1:start - 1]], dtype=float)
    # Same transform reproduces AFNI's own FZ from CC, so the cap matches AFNI's
    np.testing.assert_allclose(np.arctanh(np.clip(cc, -np.tanh(4), np.tanh(4))), fz, atol=1e-4)

    out = tmp_path / "mat.txt"
    format_netcorr_mat(tmp_path / "nc_000.netcc", True, True, out)
    mat = np.loadtxt(out, delimiter="\t")
    np.testing.assert_allclose(mat, np.arctanh(np.clip(pc, -np.tanh(4), np.tanh(4))), atol=1e-4)
    np.testing.assert_allclose(mat, mat.T, atol=1e-4)
    np.testing.assert_allclose(np.diag(mat), -4.0)


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


# ---------------------------------------------------------------------------
# Run boundaries, Power FD, rest_conn detrending
# ---------------------------------------------------------------------------

# Unequal runs, so polort A's dependence on the longest run shows: 200 s and 320 s
RUN_LENGTHS = [100, 160]


def _write_two_run_scan(d):
    """A scan whose two runs have different baselines (1000 and 1500), concatenated."""
    runs = []
    for name, n_trs, baseline in (("a", RUN_LENGTHS[0], 1000), ("b", RUN_LENGTHS[1], 1500)):
        _afni("3dcalc", "-a", f"jRandomDataset:8,8,6,{n_trs}", "-expr", f"a*10+{baseline}",
              "-datum", "float", "-prefix", f"{name}.nii.gz", cwd=d)
        runs.append(f"{name}.nii.gz")
    _afni("3dTcat", "-prefix", "two_runs.nii.gz", *runs, cwd=d)
    _afni("3drefit", "-TR", str(TR), "two_runs.nii.gz", cwd=d)
    return d / "two_runs.nii.gz"


def _x1d_rows(path):
    return np.array([ln.split() for ln in Path(path).read_text().splitlines()
                     if ln.strip() and not ln.startswith("#")], dtype=float)


def _x1d_labels(path):
    text = Path(path).read_text()
    labels = text.split('ColumnLabels = "', 1)[1].split('"', 1)[0]
    return [label.strip() for label in labels.split(";")]


def test_concat_design_matrix_and_dof(tmp_path, logger):
    """-concat gives each run a baseline, global onsets stay put, and compute_dof matches AFNI."""
    scan = _write_two_run_scan(tmp_path)
    n_trs = sum(RUN_LENGTHS)
    np.savetxt(tmp_path / "motion.1D", np.random.default_rng(0).normal(0, 0.01, (n_trs, 6)))
    censor = tmp_path / "censor.1D"
    np.savetxt(censor, np.ones(n_trs), fmt="%d")
    # Global times: 240 s is 40 s into run 2
    (tmp_path / "stim.txt").write_text("".join(f"{t}\n" for t in (20, 100, 240, 400)))

    cmd = build_decon_base_command(str(scan), str(censor), str(tmp_path / "motion.1D"), tr=TR,
                                   run_lengths=RUN_LENGTHS)
    cmd += ["-num_stimts", "1", "-stim_times", "1", "stim.txt", "BLOCK(2,1)", "-stim_label", "1", "A",
            "-x1D", "x.1D", "-x1D_stop", "-nobucket"]
    _afni(*cmd, cwd=tmp_path)

    labels = _x1d_labels(tmp_path / "x.1D")
    rows = _x1d_rows(tmp_path / "x.1D")
    baseline = [i for i, label in enumerate(labels) if label.startswith("Run#")]
    assert {labels[i].split("Pol#")[0] for i in baseline} == {"Run#1", "Run#2"}
    assert len(baseline) == polort_a_regressors(RUN_LENGTHS, TR)
    # Each run's baseline columns are zero outside that run
    run1 = [i for i in baseline if labels[i].startswith("Run#1")]
    run2 = [i for i in baseline if labels[i].startswith("Run#2")]
    assert not rows[RUN_LENGTHS[0]:, run1].any() and not rows[:RUN_LENGTHS[0], run2].any()
    # The 240 s onset rises from TR 120 of the concatenated scan. Read as local times,
    # it would be 100 TRs later. BLOCK is 0 at its onset, so its first non-zero row is 121.
    stim = rows[:, labels.index("A#0")]
    assert stim[121] > 0 and not stim[116:121].any()

    assert compute_dof(censor, 6 + 1, logger, tr=TR, run_lengths=RUN_LENGTHS) == rows.shape[0] - rows.shape[1]


def test_psc_scales_each_run_by_its_own_mean(tmp_path, logger):
    scan = _write_two_run_scan(tmp_path)
    psc = scale_to_psc(str(scan), tmp_path, "sub01", "", logger, run_lengths=RUN_LENGTHS)
    assert subprocess.run(["3dinfo", "-nv", psc], capture_output=True, text=True).stdout.strip() == str(sum(RUN_LENGTHS))

    def grand_mean(selector):
        out = subprocess.run(["3dmaskave", "-quiet", f"{psc}{selector}"], capture_output=True, text=True).stdout
        return np.loadtxt(out.splitlines()).mean()

    # Scaling across both runs would leave these near 80 and 120
    assert grand_mean(f"[0..{RUN_LENGTHS[0] - 1}]") == pytest.approx(100, abs=0.5)
    assert grand_mean(f"[{RUN_LENGTHS[0]}..{sum(RUN_LENGTHS) - 1}]") == pytest.approx(100, abs=0.5)


@pytest.mark.parametrize("atype, conds", [("task_act", {"cond_labels": ["A", "B"]}),
                                          ("task_conn", {"cond_beta_labels": ["A", "B"]})])
def test_task_pipelines_with_run_lengths(tmp_path, monkeypatch, logger, atype, conds):
    monkeypatch.chdir(tmp_path)
    scan = _write_two_run_scan(tmp_path)
    n_trs = sum(RUN_LENGTHS)
    motion = np.random.default_rng(0).normal(0, 0.01, (n_trs, 6))
    motion[RUN_LENGTHS[0]:, 0] += 50.0  # a step between runs is not head motion
    np.savetxt(tmp_path / "motion.txt", motion)
    rows = ["onset\tduration\ttrial_type"]
    rows += [f"{20 + 40 * i}\t2\t{'AB'[i % 2]}" for i in range(12)]
    (tmp_path / "events.tsv").write_text("\n".join(rows) + "\n")
    block = {
        "name": "two_runs", "type": atype,
        "paths": {"scan_path": str(scan), "task_timing_path": str(tmp_path / "events.tsv"),
                  "motion_path": str(tmp_path / "motion.txt"), "run_lengths": RUN_LENGTHS},
        "out_dir": str(tmp_path / "out"), "out_file_pre": "sub01", "average_type": "mean",
        "hrf_model": "GAM", "include_motion_derivs": False, "fd_threshold": 0.9, **conds,
    }
    result = DISPATCH[atype](_resolve(tmp_path, block, None), logger)
    _assert_ok(result)
    out = tmp_path / "out"
    assert np.loadtxt(out / "sub01_concat_censor.1D").all()
    assert result.qc_summary["censor_metric"] == "power_fd"
    if atype == "task_act":
        bucket = out / "sub01_concat_bucket_stats.nii.gz"
        labels = subprocess.run(["3dinfo", "-label", bucket], capture_output=True, text=True).stdout.strip().split("|")
        [dof] = _get_subbrik_stat_aux(str(bucket), labels.index("A#0_Tstat"), logger=logger)
        assert dof == result.qc_summary["dof"]


def test_tproject_polort_2_removes_quadratic_trend(tmp_path):
    """Fix for -polort -1 with -bandpass: sinusoids leave a quadratic trend behind."""
    _afni("3dcalc", "-a", f"jRandomDataset:8,8,6,{N_TRS}", "-expr", "a+100+200*((t/239)-0.5)^2*4",
          "-datum", "float", "-prefix", "trend.nii.gz", cwd=tmp_path)
    _afni("3drefit", "-TR", str(TR), "trend.nii.gz", cwd=tmp_path)

    def residual_sd(polort):
        prefix = f"res{polort}.nii.gz"
        _afni("3dTproject", "-input", "trend.nii.gz", "-dt", str(TR), "-polort", polort,
              "-bandpass", "0.01", "0.1", "-prefix", prefix, cwd=tmp_path)
        _afni("3dTstat", "-stdev", "-prefix", f"sd{polort}.nii.gz", prefix, cwd=tmp_path)
        out = subprocess.run(["3dmaskave", "-quiet", f"sd{polort}.nii.gz"], cwd=tmp_path,
                             capture_output=True, text=True).stdout
        return float(out.split()[0])

    assert residual_sd("2") < 0.5 * residual_sd("-1")


# ---------------------------------------------------------------------------
# Onset, PSC, ROI averaging and smoothing against real AFNI
# ---------------------------------------------------------------------------

def test_psc_qc_counts_on_real_data(tmp_path, logger):
    """A constant-free scan with one column of voxels spiking above twice its mean."""
    _afni("3dcalc", "-a", "jRandomDataset:6,6,4,30", "-expr", "(a+100)*(1+500*equals(i,0)*equals(t,3))",
          "-datum", "float", "-prefix", "scan.nii.gz", cwd=tmp_path)
    records = []
    scale_to_psc(tmp_path / "scan.nii.gz", tmp_path, "sub01", "", logger, qc_records=records)
    [record] = records
    assert record["n_mask_voxels"] == 6 * 6 * 4
    assert record["n_capped_voxels"] == 6 * 4  # i == 0 only
    assert record["n_guarded_voxels"] == 0
    assert record["n_nonpositive_mean_voxels"] == 0


def test_psc_refuses_demeaned_input(tmp_path, logger):
    from fmri_first_level_proc.exceptions import InputError

    _afni("3dcalc", "-a", "jRandomDataset:6,6,4,30", "-expr", "a-1000*step(k-1)", "-datum", "float",
          "-prefix", "demeaned.nii.gz", cwd=tmp_path)
    with pytest.raises(InputError, match="demeaned"):
        scale_to_psc(tmp_path / "demeaned.nii.gz", tmp_path, "sub01", "", logger, qc_records=[])


def test_header_tr_is_checked_on_real_data(data, tmp_path, logger):
    from fmri_first_level_proc.exceptions import InputError

    config = _resolve(tmp_path, {
        "name": "act", "type": "task_act", "paths": _task_paths(data),
        "out_dir": str(tmp_path / "act"), "out_file_pre": "sub01", "cond_labels": ["A", "B"],
        "average_type": "mean", "hrf_model": "GAM", "include_motion_derivs": True, "fd_threshold": 0.9,
    }, None)
    check_inputs(config, logger)
    config.tr = 1.5
    with pytest.raises(InputError, match="header TR"):
        check_inputs(config, logger)


@pytest.mark.parametrize("average", ["mean", "median"])
def test_roi_zero_handling_on_real_data(tmp_path, logger, average):
    """Three quarters of each ROI is zero: excluding zeros gives 10; including them gives 2.5 or 0."""
    _afni("3dcalc", "-a", "jRandomDataset:8,8,4,2", "-expr", "1+step(i-3)", "-datum", "short",
          "-prefix", "parc.nii.gz", cwd=tmp_path)
    _afni("3dcalc", "-a", "jRandomDataset:8,8,4,2", "-expr", "10*step(j-5)", "-datum", "float",
          "-prefix", "data.nii.gz", cwd=tmp_path)
    exclude = extract_roi_stats(tmp_path / "data.nii.gz", tmp_path / "parc.nii.gz", average, logger=logger)
    include = extract_roi_stats(tmp_path / "data.nii.gz", tmp_path / "parc.nii.gz", average, logger=logger,
                                roi_zero_handling="include")
    assert list(exclude.columns) == list(include.columns) == ["ROI_1", "ROI_2"]
    np.testing.assert_allclose(exclude.to_numpy(), 10.0)
    np.testing.assert_allclose(include.to_numpy(), 2.5 if average == "mean" else 0.0)


def test_smoothed_seed_backend_matches_3dnetcorr(data, tmp_path, logger):
    """With an unsmoothed target, 3dTcorr1D and 3dNetCorr give the same map."""
    for fishZ in (False, True):
        seed_to_voxel_conn(data / "scan.nii.gz", tmp_path, "net", data / "seed.nii.gz", fishZ, False, logger=logger)
        seed_to_voxel_smoothed(data / "scan.nii.gz", data / "scan.nii.gz", tmp_path, "tc", data / "seed.nii.gz",
                               fishZ, False, "_x", logger=logger)
        suffix = "fishZ" if fishZ else "corr"
        _afni("3dcalc", "-a", f"net_{suffix}.nii.gz", "-b", f"tc_{suffix}_x.nii.gz", "-expr", "abs(a-b)",
              "-prefix", f"diff_{suffix}.nii.gz", cwd=tmp_path)
        out = subprocess.run(["3dBrickStat", "-max", f"diff_{suffix}.nii.gz"], cwd=tmp_path,
                             capture_output=True, text=True, check=True).stdout
        assert float(out.split()[0]) < 1e-3


def test_task_act_smoothing_end_to_end(tmp_path, monkeypatch, logger):
    monkeypatch.chdir(tmp_path)
    # Spatially white data can make the ACF fit fail, and 3dBlurToFWHM then doesn't blur
    white = _write_two_run_scan(tmp_path)
    _afni("3dmerge", "-1blur_fwhm", "3", "-doall", "-prefix", "smooth3mm.nii.gz", white, cwd=tmp_path)
    _afni("3drefit", "-TR", str(TR), "smooth3mm.nii.gz", cwd=tmp_path)
    scan = tmp_path / "smooth3mm.nii.gz"
    before = set(tmp_path.iterdir())
    n_trs = sum(RUN_LENGTHS)
    np.savetxt(tmp_path / "motion.txt", np.random.default_rng(0).normal(0, 0.01, (n_trs, 6)))
    rows = ["onset\tduration\ttrial_type"] + [f"{20 + 40 * i}\t2\t{'AB'[i % 2]}" for i in range(12)]
    (tmp_path / "events.tsv").write_text("\n".join(rows) + "\n")
    block = {
        "name": "act", "type": "task_act",
        "paths": {"scan_path": str(scan), "task_timing_path": str(tmp_path / "events.tsv"),
                  "motion_path": str(tmp_path / "motion.txt"), "run_lengths": RUN_LENGTHS},
        "out_dir": str(tmp_path / "act"), "out_file_pre": "sub01", "average_type": "mean",
        "cond_labels": ["A", "B"], "hrf_model": "GAM", "include_motion_derivs": False, "fd_threshold": 0.9,
        "smoothing": {"enabled": True, "fwhm": 6},
        "extraction": {"stat_buckets": ["Coef", "Zstat"], "extract_out_file_pre": "sub01_wb"},
    }
    result = DISPATCH["task_act"](_resolve(tmp_path, block, None), logger)
    assert all(Path(p).exists() for p in result.output_files)
    out = tmp_path / "act"
    assert (out / "sub01_concat_bucket_stats_s6mm.nii.gz").exists()
    assert (out / "sub01_wb_Zstat_bucket_s6mm.nii.gz").exists()
    nv = subprocess.run(["3dinfo", "-nv", out / "sub01_psc_s6mm.nii.gz"], capture_output=True, text=True).stdout.strip()
    assert nv == str(n_trs)
    records = result.qc_summary["smoothing_per_run"]
    assert [r["run"] for r in records] == [1, 2]
    for record in records:
        assert record["acf_fwhm_output_mm"] > record["acf_fwhm_input_mm"]
        assert record["mask_n_voxels"] == 8 * 8 * 6
        assert record["mask_fov_fraction"] == 1.0

    def mean_temporal_sd(name):
        _afni("3dTstat", "-stdev", "-prefix", tmp_path / f"sd_{name}", out / name, cwd=tmp_path)
        out_sd = subprocess.run(["3dBrickStat", "-mean", tmp_path / f"sd_{name}"], capture_output=True, text=True).stdout
        (tmp_path / f"sd_{name}").unlink()
        return float(out_sd.split()[0])

    assert mean_temporal_sd("sub01_psc_s6mm.nii.gz") < mean_temporal_sd("sub01_psc.nii.gz")
    # Nothing written to the working directory
    assert {p for p in tmp_path.iterdir() if p.name not in ("config.yaml", "motion.txt", "events.tsv", "act")} <= before


def test_task_conn_smoothing_end_to_end(data, tmp_path, monkeypatch, logger):
    monkeypatch.chdir(tmp_path)
    block = {
        "name": "conn", "type": "task_conn", "paths": _task_paths(data),
        "out_dir": str(tmp_path / "conn"), "out_file_pre": "sub01", "cond_beta_labels": ["A", "B"],
        "average_type": "mean", "hrf_model": "GAM", "include_motion_derivs": False, "fd_threshold": 0.9,
        "smoothing": {"enabled": True, "fwhm": 6},
        "connectivity": {"calc_conn": "seed_to_voxel", "conn_out_file_pre": "sub01_fc", "fishZ": True,
                         "contrasts": {"functions": ["1*A-1*B"], "labels": ["AvB"]}},
    }
    result = DISPATCH["task_conn"](_resolve(tmp_path, block, data / "seed.nii.gz"), logger)
    assert all(Path(p).exists() for p in result.output_files)
    out = tmp_path / "conn"
    for name in ("sub01_concat_LSS_s6mm.nii.gz", "sub01_concat_bseries_A_s6mm.nii.gz", "sub01_fc_A_fishZ_s6mm.nii.gz",
                 "sub01_fc_B_fishZ_s6mm.nii.gz", "sub01_fc_AvB_fishZ_s6mm.nii.gz"):
        assert (out / name).exists(), name
    index = json.loads((out / "sub01_concat_bseries_B_index_s6mm.json").read_text())
    assert [t["lss_index"] for t in index] == list(range(6, 12))
    assert not list(out.glob("tmp*"))


def test_rest_conn_smoothing_end_to_end(data, tmp_path, monkeypatch, logger):
    monkeypatch.chdir(tmp_path)
    block = {
        "name": "rest", "type": "rest_conn", "paths": _rest_paths(data),
        "out_dir": str(tmp_path / "rest"), "out_file_pre": "sub01", "average_type": "mean",
        "bandpass": [0.01, 0.1], "motion_deriv_degree": 1, "fd_threshold": 0.9,
        "smoothing": {"enabled": True, "fwhm": 6},
        "connectivity": {"calc_conn": "seed_to_voxel", "conn_out_file_pre": "sub01_fc", "fishZ": True},
    }
    result = DISPATCH["rest_conn"](_resolve(tmp_path, block, data / "seed.nii.gz"), logger)
    assert all(Path(p).exists() for p in result.output_files)
    out = tmp_path / "rest"
    nv = subprocess.run(["3dinfo", "-nv", out / "sub01_concat_residual_dtseries_s6mm.nii.gz"],
                        capture_output=True, text=True).stdout.strip()
    assert nv == str(2 * N_TRS)
    assert (out / "sub01_fc_fishZ_s6mm.nii.gz").exists()
    assert [r["run"] for r in result.qc_summary["smoothing_per_run"]] == [1, 2]


# ---------------------------------------------------------------------------
# Trial estimability
# ---------------------------------------------------------------------------

def test_trial_energy_ratios_on_real_afni(tmp_path, logger):
    """Whole response censored -> 0; onset TR censored only -> near 1; peak censored -> small but above 0."""
    onsets = [20.0, 60.0, 100.0, 140.0]
    df = pd.DataFrame({"trial_type": ["A"] * 4, "onset": onsets, "duration": [2.0] * 4})
    keep = np.ones(120, int)
    keep[30:42] = 0  # trial 1: all of the response window
    keep[50] = 0  # trial 2: only the onset TR
    keep[72:76] = 0  # trial 3: the peak
    censor = tmp_path / "censor.1D"
    np.savetxt(censor, keep, fmt="%d")
    config = SimpleNamespace(tr=TR, hrf_model="GAM", custom_hrf=None, run_lengths=None, out_dir=str(tmp_path))
    ratios = trial_energy_ratios(df, ["A"], str(censor), config, logger)["A"]
    assert ratios[0] == 1.0
    assert ratios[1] == 0.0
    assert ratios[2] > 0.99
    assert 0 < ratios[3] < 0.5
    assert [p.name for p in tmp_path.iterdir()] == ["censor.1D"]


@pytest.mark.parametrize("hrf_model, custom_hrf, columns_each", [("dmBLOCK", None, 1), ("custom", "TENT(0,12,5)", 5)])
def test_trial_energy_ratios_other_hrfs(tmp_path, logger, hrf_model, custom_hrf, columns_each):
    df = pd.DataFrame({"trial_type": ["A", "A", "B", "B"], "onset": [20.0, 100.0, 60.0, 140.0], "duration": [2.0] * 4})
    keep = np.ones(120, int)
    keep[30:45] = 0  # all of the response to B's trial at 60 s
    censor = tmp_path / "censor.1D"
    np.savetxt(censor, keep, fmt="%d")
    config = SimpleNamespace(tr=TR, hrf_model=hrf_model, custom_hrf=custom_hrf, run_lengths=[60, 60], out_dir=str(tmp_path))
    ratios = trial_energy_ratios(df.sort_values("onset"), ["A", "B"], str(censor), config, logger)
    assert ratios["A"] == [1.0, 1.0]
    assert ratios["B"] == [0.0, 1.0]


def test_trial_energy_ratios_with_equal_condition_sizes(tmp_path, logger):
    """AFNI run-length encodes StimBots ("0..4") here; found on real ABCD n-back designs."""
    conds = ["A", "B", "C", "D", "E"]
    df = pd.DataFrame({"trial_type": conds * 2, "onset": [10.0 + 20 * i for i in range(10)], "duration": [2.0] * 10})
    keep = np.ones(120, int)
    keep[15:25] = 0  # all of the response to C's first trial, at 50 s, and most of D's start
    keep[25:36] = 0
    censor = tmp_path / "censor.1D"
    np.savetxt(censor, keep, fmt="%d")
    config = SimpleNamespace(tr=TR, hrf_model="GAM", custom_hrf=None, run_lengths=None, out_dir=str(tmp_path))
    ratios = trial_energy_ratios(df, conds, str(censor), config, logger)
    assert list(ratios) == conds and all(len(r) == 2 for r in ratios.values())
    assert ratios["C"][0] == 0.0 and ratios["A"] == [1.0, 1.0] and ratios["E"][1] == 1.0


def test_im_columns_follow_mixed_onset_file_order(tmp_path):
    """gen_beta_series relies on this: the combined onset file is grouped by condition, not time."""
    (tmp_path / "beta.txt").write_text("".join(f"{t}\n" for t in (100, 20, 180, 60, 140)))
    _afni("3dDeconvolve", "-nodata", "120", str(TR), "-polort", "-1", "-num_stimts", "1",
          "-stim_times_IM", "1", "beta.txt", "GAM(8.6,.547,2)", "-stim_label", "1", "b",
          "-x1D", "x.1D", "-x1D_stop", cwd=tmp_path)
    labels = _x1d_labels(tmp_path / "x.1D")
    rows = _x1d_rows(tmp_path / "x.1D")
    first_rows = [int(np.flatnonzero(rows[:, labels.index(f"b#{j}")])[0]) for j in range(5)]
    assert first_rows == [51, 11, 91, 31, 71]


def test_task_conn_drops_fully_censored_trial_on_real_afni(data, tmp_path, monkeypatch, logger):
    monkeypatch.chdir(tmp_path)
    motion = np.random.default_rng(0).normal(0, 0.001, (N_TRS, 6))
    # Each step exceeds the 0.9 mm threshold from TR 25 to TR 40: 50-80 s, covering A's 50 s trial
    motion[25:41, 0] += np.arange(16) * 5.0
    motion[41:, 0] += 75.0
    np.savetxt(tmp_path / "motion.txt", motion)
    paths = {**_task_paths(data), "motion_path": str(tmp_path / "motion.txt"), "CSF_path": None, "WM_path": None}
    block = {
        "name": "conn", "type": "task_conn", "paths": paths,
        "out_dir": str(tmp_path / "conn"), "out_file_pre": "sub01", "cond_beta_labels": ["A", "B"],
        "average_type": "mean", "hrf_model": "GAM", "include_motion_derivs": False, "fd_threshold": 0.9,
    }
    result = DISPATCH["task_conn"](_resolve(tmp_path, block, None), logger)
    trial = next(t for t in result.qc_summary["trials"] if t["condition"] == "A" and t["onset"] == 50)
    assert trial["survived"] is False
    assert result.qc_summary["per_condition_surviving_trials"]["A"] == len(ONSETS["A"]) - 1
    nv = subprocess.run(["3dinfo", "-nv", tmp_path / "conn" / "sub01_concat_bseries_A.nii.gz"],
                        capture_output=True, text=True).stdout.strip()
    assert nv == str(len(ONSETS["A"]) - 1)
