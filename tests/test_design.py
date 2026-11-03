"""Pure-function tests for HRF, stimulus timing, contrast, and DOF helpers."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from fmri_first_level_proc.exceptions import ConfigError, InputError, ModelError
from fmri_first_level_proc.design import (
    build_decon_base_command,
    build_hrf_string,
    check_trial_survival,
    trial_energy_ratios,
    trial_records,
    compute_dof,
    needs_married_timing,
    read_and_validate_stim_data,
    valid_contrast_functions,
    validate_onset_file_format,
    write_onset_file,
)
from fmri_first_level_proc.reporting import get_warnings

pytestmark = pytest.mark.level0_unit


@pytest.mark.parametrize(
    "model, kwargs, expected",
    [
        ("GAM", {"mean_dur": 2.0}, "GAM(8.6,.547,2.0)"),
        ("BLOCK", {"mean_dur": 3}, "BLOCK(3,1)"),
        ("dmBLOCK", {}, "dmBLOCK(0)"),
        ("SPMG1", {}, "SPMG1"),
        ("custom", {"custom_hrf": "TENT(0,14,8)"}, "TENT(0,14,8)"),
    ],
)
def test_build_hrf_string(model, kwargs, expected):
    assert build_hrf_string(model, **kwargs) == expected


def test_build_hrf_string_errors():
    with pytest.raises(ConfigError):
        build_hrf_string("custom")
    with pytest.raises(ConfigError):
        build_hrf_string("NOPE")


@pytest.mark.parametrize(
    "model, custom, expected",
    [
        ("dmBLOCK", None, True),
        ("GAM", None, False),
        ("custom", "dmBLOCK(1)", True),
        ("custom", "dmBLOCK", True),
        ("custom", "TENT(0,14,8)", False),
        ("custom", None, False),
    ],
)
def test_needs_married_timing(model, custom, expected):
    assert needs_married_timing(model, custom) is expected


def test_valid_contrast_functions_parses_terms(logger):
    out = valid_contrast_functions(
        ["1*A-1*B", "-1*A + 0.5*B + 0.5*C"], ["AvB", "mix"], ["A", "B", "C"], logger=logger
    )
    assert out == [
        {"COEFS": ["1", "-1"], "CONDS": ["A", "B"]},
        {"COEFS": ["-1", "+0.5", "+0.5"], "CONDS": ["A", "B", "C"]},
    ]


@pytest.mark.parametrize(
    "contrast",
    ["A-B", "1*A-", "1*A-1*Z", "1*A$1*B", ""],
)
def test_valid_contrast_functions_rejects(contrast, logger):
    with pytest.raises(ConfigError):
        valid_contrast_functions([contrast], ["c"], ["A", "B"], logger=logger)


def test_valid_contrast_functions_label_mismatch(logger):
    with pytest.raises(ConfigError):
        valid_contrast_functions(["1*A"], [], ["A"], logger=logger)


def test_read_stim_data_bids_tsv(tmp_path, logger):
    p = tmp_path / "events.tsv"
    p.write_text("onset\tduration\ttrial_type\n10\t2\tB\n0\t2\tA\n5\t2\tA\n")
    df = read_and_validate_stim_data(str(p), ["A", "B"], logger=logger)
    assert list(df["onset"]) == [0, 5, 10]
    assert list(df["trial_type"]) == ["A", "A", "B"]
    assert get_warnings() == []


def test_read_stim_data_legacy_csv_warns(tmp_path, logger):
    p = tmp_path / "timing.csv"
    p.write_text("CONDITION,ONSET,DURATION\nA,0,2\nA,4,2\n")
    df = read_and_validate_stim_data(str(p), ["A"], logger=logger)
    assert set(df.columns) >= {"onset", "duration", "trial_type"}
    assert [w["code"] for w in get_warnings()] == ["EVENTS_LEGACY"]


def test_read_stim_data_errors(tmp_path, logger):
    p = tmp_path / "events.tsv"
    p.write_text("onset\tduration\ttrial_type\n0\t2\tA\n")
    with pytest.raises(InputError):
        read_and_validate_stim_data(str(p), ["A", "missing"], logger=logger)
    bad = tmp_path / "bad.tsv"
    bad.write_text("a\tb\n1\t2\n")
    with pytest.raises(InputError):
        read_and_validate_stim_data(str(bad), ["A"], logger=logger)


def test_write_onset_file_single_and_married(tmp_path, logger):
    df = pd.DataFrame({"onset": [1.5, 4.0], "duration": [2.0, 3.0]})
    single = tmp_path / "single.txt"
    married = tmp_path / "married.txt"
    write_onset_file(df, str(single), "GAM", logger=logger)
    write_onset_file(df, str(married), "dmBLOCK", logger=logger)
    assert single.read_text() == "1.5\n4.0\n"
    assert married.read_text() == "1.5*2.0\n4.0*3.0\n"
    assert validate_onset_file_format(str(married), True, logger=logger) is True
    assert validate_onset_file_format(str(married), False, logger=logger) is False


def test_check_trial_survival_counts_ratios_above_zero(logger):
    assert check_trial_survival({"A": [1.0, 0.0, 0.001], "B": [0.0]}, logger) == {"A": 2, "B": 0}


def test_parse_x1d_and_pooled_ratios(tmp_path, monkeypatch, logger):
    """Two basis columns per trial: a trial's ratio is pooled over both, in onset order."""
    def fake_deconvolve(command, **kwargs):
        rows = np.zeros((6, 4))
        rows[[0, 1], 0], rows[[0, 1], 1] = 1.0, 1.0  # trial 0: rows 0-1, censored row 1
        rows[[2, 3], 2], rows[[2, 3], 3] = 1.0, 1.0  # trial 1: rows 2-3, all censored
        path = command[command.index("-x1D") + 1]
        with open(path, "w") as f:
            f.write('# ColumnLabels = "stim1#0_0 ; stim1#0_1 ; stim1#1_0 ; stim1#1_1"\n')
            np.savetxt(f, rows)

    monkeypatch.setattr("fmri_first_level_proc.design.run_afni_command", fake_deconvolve)
    censor = tmp_path / "censor.1D"
    np.savetxt(censor, [1, 0, 0, 0, 1, 1])
    df = pd.DataFrame({"trial_type": ["A", "A"], "onset": [0.0, 2.0], "duration": [1.0, 1.0]})
    config = SimpleNamespace(tr=1.0, hrf_model="TENT", custom_hrf=None, run_lengths=None, out_dir=str(tmp_path))
    monkeypatch.setattr("fmri_first_level_proc.design.build_hrf_string", lambda *a, **k: "TENT(0,2,2)")
    assert trial_energy_ratios(df, ["A"], str(censor), config, logger) == {"A": [0.5, 0.0]}
    assert [p.name for p in tmp_path.iterdir()] == ["censor.1D"]


def test_trial_records_flag_survival(logger):
    df = pd.DataFrame({"trial_type": ["A", "B", "A"], "onset": [10.0, 20.0, 90.0], "duration": [2.0, 2.0, 2.0]})
    records = trial_records(df, {"A": [0.25, 0.0], "B": [1.0]}, 2.0, [40, 60])
    assert records[0] == {"run": 1, "condition": "A", "onset": 10.0, "duration": 2.0,
                          "estimability": 0.25, "survived": True}
    assert (records[1]["run"], records[1]["survived"]) == (2, False)
    assert records[2]["condition"] == "B"


def test_compute_dof(tmp_path, logger):
    censor = tmp_path / "censor.1D"
    np.savetxt(censor, [1] * 200 + [0] * 100)
    assert compute_dof(str(censor), 10, logger) == 190
    # polort A: degree 1 + floor(300 TRs * 1.0 s / 150) = 3, so 4 extra regressors
    assert compute_dof(str(censor), 10, logger, tr=1.0) == 186
    # Two runs: degree 1 + floor(200 s / 150) = 2 from the longest run, so 3 regressors per run
    assert compute_dof(str(censor), 10, logger, tr=1.0, run_lengths=[100, 200]) == 184
    with pytest.raises(ModelError):
        compute_dof(str(censor), 200, logger)
    assert compute_dof(str(tmp_path / "missing.1D"), 1, logger) is None


def test_build_decon_base_command():
    cmd = build_decon_base_command("scan.nii", "c.1D", "m.1D", CSF_path="csf.txt", tr=0.8)
    assert cmd == [
        "3dDeconvolve", "-quiet", "-input", "scan.nii", "-polort", "A",
        "-censor", "c.1D", "-ortvec", "m.1D", "motion_regressors",
        "-TR_times", "0.8", "-ortvec", "csf.txt", "CSF_regressor",
    ]
