"""Tests for abcd/validity.py. Identifiers here are synthetic."""

import csv

import pytest

from fmri_first_level_proc.abcd import validity

BETA = "mr_y_tfmri__nback__0b__r01__aseg__ab__lh_beta"


def tsv(path, header, rows):
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(header)
        writer.writerows(rows)
    return path


@pytest.fixture
def tables(tmp_path):
    qc = tsv(
        tmp_path / "qc.tsv",
        ["participant_id", "session_id", validity.VALID_COUNT],
        [
            ["sub-TWO", "ses-00A", "2"],
            ["sub-TWOQC", "ses-00A", "2"],
            ["sub-R2", "ses-00A", "1"],
            ["sub-R1", "ses-00A", "1.0"],
            ["sub-NONE", "ses-00A", "1"],
            ["sub-ZERO", "ses-00A", "0"],
            ["sub-BLANK", "ses-00A", ""],
            ["sub-HOLD", "ses-00A", "2"],
        ],
    )
    head = ["participant_id", "session_id", BETA, "other_beta", "note"]
    r1 = tsv(
        tmp_path / "r1.tsv",
        head,
        [
            ["sub-TWO", "ses-00A", "0.1", "0.2", "x"],
            ["sub-TWOQC", "ses-00A", "0.1", "0.2", ""],
            ["sub-R1", "ses-00A", "0.1", "0.2", ""],
            ["sub-R2", "ses-00A", "", "n/a", "x"],  # a row with no values is not a result
        ],
    )
    r2 = tsv(
        tmp_path / "r2.tsv",
        head,
        [["sub-TWO", "ses-00A", "0.1", "0.2", ""], ["sub-R2", "ses-00A", "0.1", "0.2", ""]],
    )
    subjects = ["TWO", "TWOQC", "R2", "R1", "NONE", "ZERO", "BLANK", "HOLD", "UNLISTED"]
    runs = tmp_path / "runs.csv"
    with runs.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["subject_id", "session", "run"])
        for name in subjects:
            for run in ("01", "02"):
                writer.writerow([f"sub-{name}", "ses-00A", f"task-nback_run-{run}"])
    hold = tmp_path / "hold.csv"
    hold.write_text("subject_id,session,reason\nsub-HOLD,ses-00A,zero-dummy-untested\n")
    return qc, r1, r2, runs, hold


def decided(tables):
    qc, r1, r2, runs, hold = tables
    rows = validity.build(runs, qc, r1, r2, hold)
    return {(row[0], row[2][-2:]): (row[3], row[4]) for row in rows}


def test_the_treatment_table(tables):
    got = decided(tables)
    assert got[("sub-TWO", "01")] == got[("sub-TWO", "02")] == ("1", "")
    assert got[("sub-R2", "02")] == ("1", "")
    assert got[("sub-R2", "01")] == ("0", "other-run-has-valid-timing")
    assert got[("sub-R1", "01")] == ("1", "")
    assert got[("sub-R1", "02")] == ("0", "other-run-has-valid-timing")
    assert got[("sub-NONE", "01")] == ("0", "valid-run-unidentified")
    assert got[("sub-ZERO", "02")] == ("0", "no-valid-timing-runs")
    assert got[("sub-BLANK", "01")] == ("0", "no-valid-count")
    assert got[("sub-UNLISTED", "01")] == ("0", "no-valid-count")


def test_qc_does_not_stand_in_for_timing(tables):
    """Run-level results can be missing for QC reasons, so two valid runs stay usable."""
    got = decided(tables)
    assert got[("sub-TWOQC", "02")] == ("1", "")


def test_a_hold_overrides(tables):
    assert decided(tables)[("sub-HOLD", "01")] == ("0", "zero-dummy-untested")


def test_a_malformed_run_id_stops_the_build(tmp_path, tables):
    qc, r1, r2, _, _ = tables
    runs = tmp_path / "bad.csv"
    runs.write_text("subject_id,session,run\nsub-A,ses-00A,run-01\n")
    with pytest.raises(ValueError, match="task-nback_run-01"):
        validity.build(runs, qc, r1, r2, None)


def test_a_results_table_with_no_betas_stops_the_build(tmp_path):
    path = tsv(tmp_path / "x.tsv", ["participant_id", "session_id"], [])
    with pytest.raises(ValueError, match="_beta"):
        validity.sessions_with_results(path)


def test_the_cli_writes_the_table_and_reports_only_counts(tables, tmp_path, capsys):
    qc, r1, r2, runs, hold = tables
    out = tmp_path / "out.csv"
    code = validity.main(
        ["--mr-qc-nback", str(qc), "--results-r01", str(r1), "--results-r02", str(r2), "--runs", str(runs),
         "--hold", str(hold), "--out", str(out)]
    )  # fmt: skip
    assert code == 0
    assert out.read_text().splitlines()[0] == "subject_id,session,run,use,reason"
    printed = capsys.readouterr().out
    assert "wrote 18 runs" in printed and "sub-" not in printed
