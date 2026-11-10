"""engine.RunContext's shared stages (StageSpec.share_as, FFLP_STAGE_SHARE_DIR): one
analysis takes a sibling's outputs for a stage that is the same code in both."""

import logging
import os
from types import SimpleNamespace

import pytest

from fmri_first_level_proc import engine
from fmri_first_level_proc.engine import Outcome, Output, RunContext, StageSpec
from fmri_first_level_proc.first_level_utils import clear_warnings, get_warnings, graded_warning

PRE = "sub-X_ses-Y_nback"
VERSIONS = {"afni": "AFNI_26.3.07"}
LOGGER = logging.getLogger("test_shared_stages")


@pytest.fixture(autouse=True)
def share_dir(tmp_path, monkeypatch):
    path = tmp_path / "shared"
    monkeypatch.setenv(engine.SHARE_DIR_ENV, str(path))
    clear_warnings()
    return path


def context(root, analysis, pre=PRE, **fields):
    out_dir = root / analysis
    out_dir.mkdir(parents=True, exist_ok=True)
    config = SimpleNamespace(out_dir=str(out_dir), out_file_pre=pre, remove_previous=False,
                             scan_paths=["/in/run-01.nii.gz"], **fields)
    ctx = RunContext(config, "task_act" if analysis == "act" else "task_conn",
                     LOGGER, VERSIONS, grid_ref=None)
    ctx.start()
    return ctx


def body(text, calls, warn=False):
    """A stage body writing one text file; `calls` counts how often it ran."""
    def fn(io):
        calls.append(io.label)
        if warn:
            graded_warning(LOGGER, "medium", "LEDGER_ENTRY_UNREADABLE", "a warning")
        rel = f"{io.pre}_{io.label.split('-', 2)[2]}.txt"  # task-act-prep -> {pre}_prep.txt
        with open(io.path(rel), "w", newline="") as f:
            f.write(text)
        return Outcome(outputs=[Output(rel, "intermediate", "py_text", expected_text=text)],
                       qc={"psc_per_run": [{"run": 1}]})
    return fn


def spec(kind, **kw):
    return StageSpec(label=f"task-{kind}-prep", fields=("scan_paths",), share_as="task-prep", **kw)


def test_second_analysis_takes_the_first_ones_outputs(tmp_path):
    calls = []
    act = context(tmp_path, "act")
    act.run_stage(spec("act"), body("psc", calls, warn=True))
    n_warnings = len(get_warnings())

    conn = context(tmp_path, "conn")
    outcome = conn.run_stage(spec("conn"), body("never", calls))

    assert calls == ["task-act-prep"]  # conn's body never ran
    src, dst = tmp_path / "act" / f"{PRE}_prep.txt", tmp_path / "conn" / f"{PRE}_prep.txt"
    assert dst.read_text() == "psc"
    assert os.stat(src).st_ino == os.stat(dst).st_ino  # a hard link, not a copy
    assert outcome.qc == {"psc_per_run": [{"run": 1}]}
    assert conn.fragments == [("task-conn-prep", {"psc_per_run": [{"run": 1}]})]
    assert len(get_warnings()) == 2 * n_warnings  # replayed into this analysis
    assert "task-conn-prep" in conn.executed  # downstream stages rerun, as after any run

    # conn's own ledger records the stage, so a rerun of conn alone reuses it
    again = context(tmp_path, "conn")
    assert again.run_stage(spec("conn"), body("never", calls)).reused


def test_a_different_input_is_not_shared(tmp_path):
    calls = []
    context(tmp_path, "act").run_stage(spec("act"), body("a", calls))
    conn = context(tmp_path, "conn")
    conn.config.scan_paths = ["/in/other.nii.gz"]
    conn.entry_config.scan_paths = ["/in/other.nii.gz"]
    conn.run_stage(spec("conn"), body("b", calls))
    assert calls == ["task-act-prep", "task-conn-prep"]


def test_a_different_prefix_is_not_shared(tmp_path):
    calls = []
    context(tmp_path, "act").run_stage(spec("act"), body("a", calls))
    context(tmp_path, "conn", pre="sub-X_ses-Y_other").run_stage(spec("conn"), body("b", calls))
    assert calls == ["task-act-prep", "task-conn-prep"]


def test_unset_share_dir_shares_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv(engine.SHARE_DIR_ENV)
    calls = []
    context(tmp_path, "act").run_stage(spec("act"), body("a", calls))
    context(tmp_path, "conn").run_stage(spec("conn"), body("b", calls))
    assert calls == ["task-act-prep", "task-conn-prep"]


def test_missing_sibling_output_runs_the_stage(tmp_path):
    calls = []
    context(tmp_path, "act").run_stage(spec("act"), body("a", calls))
    (tmp_path / "act" / f"{PRE}_prep.txt").unlink()
    context(tmp_path, "conn").run_stage(spec("conn"), body("b", calls))
    assert calls == ["task-act-prep", "task-conn-prep"]


def downstream(kind, upstream_kind, template_resolved):
    return StageSpec(label=f"task-{kind}-roi-qc", fields=("scan_paths",),
                     derived_values={"template_resolved": template_resolved},
                     upstream=(f"task-{upstream_kind}-prep",), share_as="task-roi-qc")


def test_downstream_stage_shares_through_its_own_out_dir_paths(tmp_path):
    """A derived path inside each analysis's own out_dir (the resampled template)
    keys the same in both, and a shareable upstream enters by its share key."""
    calls = []
    act = context(tmp_path, "act")
    act.run_stage(spec("act"), body("a", calls))
    act.run_stage(downstream("act", "act", f"{act.out_dir}/tmpl.nii.gz"), body("q", calls))
    conn = context(tmp_path, "conn")
    conn.run_stage(spec("conn"), body("never", calls))
    conn.run_stage(downstream("conn", "conn", f"{conn.out_dir}/tmpl.nii.gz"), body("never", calls))
    assert calls == ["task-act-prep", "task-act-roi-qc"]


def test_downstream_of_an_unshared_stage_is_not_shared(tmp_path):
    calls = []
    for kind in ("act", "conn"):
        ctx = context(tmp_path, kind)
        unshared = StageSpec(label=f"task-{kind}-prep", fields=("scan_paths",))
        ctx.run_stage(unshared, body(kind, calls))
        ctx.run_stage(downstream(kind, kind, "/atlas.nii.gz"), body(kind, calls))
    assert calls == ["task-act-prep", "task-act-roi-qc", "task-conn-prep", "task-conn-roi-qc"]
