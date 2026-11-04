"""Config resolution, runtime version probing, and CLI dry-run tests."""

import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

from fmri_first_level_proc import cli, runtime
from fmri_first_level_proc.config import _schema_violations, load_and_validate
from fmri_first_level_proc.exceptions import ConfigError, InputError, ToolVersionError

from fake_afni import FakeAfni

pytestmark = pytest.mark.level1_internal_integration


@pytest.fixture
def task_inputs(tmp_path):
    files = {}
    for name in ("scan.nii.gz", "events.tsv", "motion.txt"):
        p = tmp_path / name
        p.write_text("x")
        files[name] = str(p)
    return files


def _write_config(tmp_path, analyses, **global_extra):
    cfg = {"global": {"tr": 0.8, "num_cores": 2, **global_extra}, "analyses": analyses}
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg))
    return str(path)


def _task_act_block(tmp_path, files, **extra):
    block = {
        "name": "act",
        "type": "task_act",
        "paths": {
            "scan_path": files["scan.nii.gz"],
            "task_timing_path": files["events.tsv"],
            "motion_path": files["motion.txt"],
        },
        "out_dir": str(tmp_path / "out"),
        "out_file_pre": "sub01",
        "cond_labels": ["A", "B"],
        "average_type": "mean",
        "hrf_model": "GAM",
        "include_motion_derivs": False,
        "fd_threshold": 0.9,
    }
    block.update(extra)
    return block


def test_load_and_validate_task_act(tmp_path, task_inputs, logger):
    path = _write_config(tmp_path, [_task_act_block(tmp_path, task_inputs)])
    (cfg,) = load_and_validate(path, logger)
    assert cfg.analysis_type == "task_act"
    assert cfg.tr == 0.8
    assert cfg.num_cores == 2
    assert cfg.cond_labels == ["A", "B"]
    assert cfg.scan_path == task_inputs["scan.nii.gz"]


def test_num_cores_auto(tmp_path, task_inputs, monkeypatch, logger):
    monkeypatch.setattr("fmri_first_level_proc.config.available_cpus", lambda: (3, "test"))
    path = _write_config(tmp_path, [_task_act_block(tmp_path, task_inputs)], num_cores="auto")
    (cfg,) = load_and_validate(path, logger)
    assert cfg.num_cores == 3


@pytest.mark.parametrize("bad", [0, -1, 1.5, "four", True])
def test_num_cores_rejects_invalid(tmp_path, task_inputs, logger, bad):
    path = _write_config(tmp_path, [_task_act_block(tmp_path, task_inputs)], num_cores=bad)
    with pytest.raises(ConfigError, match="num_cores"):
        load_and_validate(path, logger)


def test_load_and_validate_errors(tmp_path, task_inputs, logger):
    with pytest.raises(ConfigError):
        load_and_validate(str(tmp_path / "nope.yaml"), logger)
    missing = dict(task_inputs, **{"scan.nii.gz": str(tmp_path / "missing.nii.gz")})
    with pytest.raises(InputError):
        load_and_validate(_write_config(tmp_path, [_task_act_block(tmp_path, missing)]), logger)
    with pytest.raises(ConfigError):
        load_and_validate(
            _write_config(tmp_path, [_task_act_block(tmp_path, task_inputs, hrf_model="NOPE")]), logger
        )
    dup = _task_act_block(tmp_path, task_inputs)
    with pytest.raises(ConfigError):
        load_and_validate(_write_config(tmp_path, [dup, dict(dup, name="act2")]), logger)


def test_parse_afni_version():
    assert runtime._parse_afni_version("Precompiled binary linux: AFNI_26.0.09 'X'", "") == "26.0.09"
    assert runtime._parse_afni_version("nothing", "") is None


def test_probe_tool_versions_python_mismatch_warns(tmp_path, logger):
    """Issue #3: a Python minor mismatch is advisory (requires-python is the contract)."""
    from fmri_first_level_proc.reporting import get_warnings

    lock = tmp_path / "tools.lock.yaml"
    lock.write_text(yaml.safe_dump({"python": "2.7.0", "binaries": {"AFNI": "PLACEHOLDER"}}))
    runtime.probe_tool_versions(str(lock), logger=logger)  # does not raise
    [w] = get_warnings()
    assert (w["code"], w["severity"]) == ("PYTHON_VERSION_MISMATCH", "medium")

    here = f"{sys.version_info.major}.{sys.version_info.minor}.0"
    lock.write_text(yaml.safe_dump({"python": here, "binaries": {"AFNI": "PLACEHOLDER"}}))
    runtime.probe_tool_versions(str(lock), logger=logger)
    assert len(get_warnings()) == 1  # matching minor adds nothing


def test_probe_tool_versions_afni_mismatch_still_fails(tmp_path, monkeypatch, logger):
    import subprocess

    lock = tmp_path / "tools.lock.yaml"
    lock.write_text(yaml.safe_dump({"binaries": {"AFNI": "26.3.07"}}))
    fake = subprocess.CompletedProcess([], 0, stdout="Precompiled binary x: (Version AFNI_26.0.09 'X')", stderr="")
    monkeypatch.setattr(runtime.subprocess, "run", lambda *a, **k: fake)
    with pytest.raises(ToolVersionError, match="AFNI: expected 26.3.07, got 26.0.09"):
        runtime.probe_tool_versions(str(lock), logger=logger)


def test_lockfile_ships_as_package_data():
    assert cli._LOCKFILE.is_file()


@pytest.fixture
def dry_run_inputs(tmp_path, task_inputs):
    """Readable motion and events for 100 volumes; the scan is only read through 3dinfo."""
    np.savetxt(task_inputs["motion.txt"], np.zeros((100, 6)))
    Path(task_inputs["events.tsv"]).write_text("onset\tduration\ttrial_type\n10\t2\tA\n20\t2\tB\n")
    return task_inputs


def _dry_run(path, monkeypatch, **fake):
    FakeAfni(n_trs=100, tr=0.8, **fake).install(monkeypatch)
    monkeypatch.setattr(cli, "preflight_tool_environments", lambda **k: None)
    monkeypatch.setattr(cli, "probe_tool_versions", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["fmri-first-level-proc", "--config", path, "--dry-run"])
    cli.main()


def test_cli_dry_run(tmp_path, dry_run_inputs, monkeypatch):
    path = _write_config(tmp_path, [_task_act_block(tmp_path, dry_run_inputs)])
    _dry_run(path, monkeypatch)
    assert list((tmp_path / "out").iterdir()) == []  # nothing written


@pytest.mark.parametrize(
    "file_name, content, message",
    [("motion.txt", "\n".join(["0 0 0 0 0 0"] * 99), "99 rows"),
     ("motion.txt", "\n".join(["0 0 0 0 0"] * 100), "5 columns"),
     ("motion.txt", "\n".join(["nan 0 0 0 0 0"] * 100), "non-finite"),
     ("events.tsv", "onset\tduration\ttrial_type\n10\t2\tA\n80\t2\tB\n", "outside the 80 s scan"),
     ("events.tsv", "onset\tduration\ttrial_type\n-1\t2\tA\n20\t2\tB\n", "outside the 80 s scan"),
     ("events.tsv", "onset\tduration\ttrial_type\n10\t2\tA\n", "not found")],
)
def test_cli_dry_run_checks_input_files(tmp_path, dry_run_inputs, monkeypatch, caplog, file_name, content, message):
    Path(dry_run_inputs[file_name]).write_text(content + "\n")
    path = _write_config(tmp_path, [_task_act_block(tmp_path, dry_run_inputs)])
    with pytest.raises(SystemExit) as exc:
        _dry_run(path, monkeypatch)
    assert exc.value.code == 2
    assert message in caplog.text
    assert list((tmp_path / "out").iterdir()) == []  # the timing record is not written in a dry run


def test_cli_dry_run_checks_header_tr(tmp_path, dry_run_inputs, monkeypatch, caplog):
    path = _write_config(tmp_path, [_task_act_block(tmp_path, dry_run_inputs)], tr=2.0)
    with pytest.raises(SystemExit) as exc:
        _dry_run(path, monkeypatch)
    assert exc.value.code == 2
    assert "header TR" in caplog.text


def test_contrast_errors_are_config_errors(tmp_path, task_inputs, logger):
    block = _task_act_block(tmp_path, task_inputs, contrasts={"functions": ["1*A-1*C"], "labels": ["AvC"]})
    with pytest.raises(ConfigError, match="not in --cond_labels"):
        load_and_validate(_write_config(tmp_path, [block]), logger)
    conn = _conn_block(tmp_path, task_inputs,
                       connectivity={"calc_conn": "parcellated", "conn_out_file_pre": "sub01_fc",
                                     "contrasts": {"functions": ["A-B"], "labels": ["AvB"]}})
    with pytest.raises(ConfigError, match="missing coefficients"):
        load_and_validate(_write_config(tmp_path, [conn]), logger)


@pytest.mark.parametrize(
    "second, collides",
    [({"out_dir": "same"}, False),
     ({"out_dir": "./same/", "out_file_pre": "sub01"}, True),
     ({"out_dir": "same", "extraction": {"extract_out_file_pre": "sub01"}}, True),
     ({"out_dir": "other", "out_file_pre": "sub01"}, False)],
)
def test_cross_block_output_collisions(tmp_path, task_inputs, logger, monkeypatch, second, collides):
    monkeypatch.chdir(tmp_path)
    first = _task_act_block(tmp_path, task_inputs, out_dir="same", name="first")
    other = _task_act_block(tmp_path, task_inputs, **{"name": "second", "out_file_pre": "sub02", **second})
    path = _write_config(tmp_path, [first, other])
    if collides:
        with pytest.raises(ConfigError, match="also used by"):
            load_and_validate(path, logger)
    else:
        assert len(load_and_validate(path, logger)) == 2


def test_block_reuses_one_prefix_for_its_own_outputs(tmp_path, task_inputs, logger):
    block = _task_act_block(tmp_path, task_inputs, extraction={"extract_out_file_pre": "sub01"})
    load_and_validate(_write_config(tmp_path, [block]), logger)


@pytest.mark.parametrize(
    "smoothing",
    ["6", {"enabled": "yes", "fwhm": 6}, {"enabled": True}, {"enabled": True, "fwhm": True},
     {"enabled": True, "fwhm": 0}, {"enabled": True, "fwhm": float("nan")}, {"enabled": True, "fwhm": 4.125}],
)
def test_invalid_smoothing_rejected(tmp_path, task_inputs, logger, smoothing):
    block = _task_act_block(tmp_path, task_inputs, smoothing=smoothing)
    with pytest.raises(ConfigError, match="smoothing"):
        load_and_validate(_write_config(tmp_path, [block]), logger)


def test_smoothing_and_roi_zero_handling_resolve(tmp_path, task_inputs, logger):
    (default,) = load_and_validate(_write_config(tmp_path, [_task_act_block(tmp_path, task_inputs)]), logger)
    assert (default.roi_zero_handling, default.smoothing_enabled, default.smoothing_fwhm) == ("exclude", False, None)

    block = _task_act_block(tmp_path, task_inputs, roi_zero_handling="include",
                            smoothing={"enabled": True, "fwhm": 4.5})
    (cfg,) = load_and_validate(_write_config(tmp_path, [block]), logger)
    assert (cfg.roi_zero_handling, cfg.smoothing_enabled, cfg.smoothing_fwhm) == ("include", True, 4.5)

    block = _task_act_block(tmp_path, task_inputs, roi_zero_handling="drop")
    with pytest.raises(ConfigError, match="roi_zero_handling"):
        load_and_validate(_write_config(tmp_path, [block]), logger)


def test_cli_config_error_exit_code(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "preflight_tool_environments", lambda **k: None)
    monkeypatch.setattr(cli, "probe_tool_versions", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["fmri-first-level-proc", "--config", str(tmp_path / "x.yaml")])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2


# ---------------------------------------------------------------------------
# Closed schema and strict values
# ---------------------------------------------------------------------------

def _conn_block(tmp_path, files, **extra):
    block = _task_act_block(tmp_path, files, type="task_conn", cond_beta_labels=["A", "B"], **extra)
    del block["cond_labels"]
    return block


def _rest_block(tmp_path, **extra):
    files = {}
    for name in ("scan", "motion", "csf", "wm"):
        path = tmp_path / f"{name}.txt"
        path.write_text("x")
        files[name] = [str(path)]
    block = {"name": "rest", "type": "rest_conn",
             "paths": {"scan_paths": files["scan"], "motion_paths": files["motion"],
                       "CSF_paths": files["csf"], "WM_paths": files["wm"]},
             "out_dir": str(tmp_path / "out"), "out_file_pre": "sub01", "average_type": "mean",
             "bandpass": [0.01, 0.1], "motion_deriv_degree": 1, "fd_threshold": 0.4}
    block.update(extra)
    return block


def test_unknown_keys_are_all_reported_together(tmp_path, task_inputs, logger):
    block = _task_act_block(tmp_path, task_inputs, censor_prev_TR=True, tr=2.0,
                            connectivity={"calc_conn": None},
                            contrasts={"function": []},
                            extraction={"extract_ptseries": True},
                            smoothing={"enabled": False, "kernel": 6})
    block["paths"]["run_length"] = [100]
    path = _write_config(tmp_path, [block], template="x")
    with pytest.raises(ConfigError) as exc:
        load_and_validate(path, logger)
    message = str(exc.value)
    for fragment in ("global.template", "act.censor_prev_TR", "act.tr: valid only in the global section",
                     "act.connectivity", "act.contrasts.function", "act.extraction.extract_ptseries",
                     "act.smoothing.kernel", "act.paths.run_length"):
        assert fragment in message, fragment


def test_shipped_configs_fit_the_schema():
    for path in (Path(__file__).parents[1] / "examples" / "config.yaml",
                 Path(cli.__file__).parent / "abcd" / "data" / "proc_config_final.yaml"):
        assert _schema_violations(yaml.safe_load(path.read_text())) == [], path


@pytest.mark.parametrize("root", [["a"], "text"])
def test_config_root_must_be_a_mapping(tmp_path, root):
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(root))
    with pytest.raises(ConfigError, match="mapping"):
        load_and_validate(str(path))


def test_analysis_entry_must_be_a_mapping(tmp_path):
    with pytest.raises(ConfigError, match=r"analyses\[0\] must be a mapping"):
        load_and_validate(_write_config(tmp_path, ["not a block"]))


@pytest.mark.parametrize(
    "key, value, message",
    [("fd_threshold", None, "Missing required key 'fd_threshold'"),
     ("hrf_model", None, "Missing required key 'hrf_model'"),
     ("out_dir", None, "Missing required key 'out_dir'"),
     ("fd_threshold", float("nan"), "finite"),
     ("fd_threshold", float("inf"), "finite"),
     ("fd_threshold", True, "finite"),
     ("censor_prev_tr", "false", "true, false or null"),
     ("include_motion_derivs", 1, "true, false or null"),
     ("scale_to_psc", "no", "true, false or null"),
     ("out_file_pre", "sub/01", "file-name-safe"),
     ("out_file_pre", 1, "file-name-safe"),
     ("cond_labels", "AB", "non-empty list"),
     ("cond_labels", [1, 2], "file-name-safe"),
     ("cond_labels", ["A", "A"], "must not repeat"),
     ("derivatives_dirs", "/deriv", "list of directory paths"),
     ("subject", 1, "must be a string")],
)
def test_invalid_block_values(tmp_path, task_inputs, logger, key, value, message):
    block = _task_act_block(tmp_path, task_inputs, **{key: value})
    with pytest.raises(ConfigError, match=message):
        load_and_validate(_write_config(tmp_path, [block]), logger)


def test_boolean_null_means_the_default(tmp_path, task_inputs, logger):
    block = _task_act_block(tmp_path, task_inputs, include_motion_derivs=None, scale_to_psc=None)
    (cfg,) = load_and_validate(_write_config(tmp_path, [block]), logger)
    assert cfg.include_motion_derivs is False and cfg.scale_to_psc is True


@pytest.mark.parametrize("tr", [float("nan"), float("inf"), True, "2"])
def test_invalid_tr(tmp_path, task_inputs, logger, tr):
    with pytest.raises(ConfigError, match="global.tr"):
        load_and_validate(_write_config(tmp_path, [_task_act_block(tmp_path, task_inputs)], tr=tr), logger)


def test_invalid_force_diff_atlas(tmp_path, task_inputs, logger):
    path = _write_config(tmp_path, [_task_act_block(tmp_path, task_inputs)], force_diff_atlas="yes")
    with pytest.raises(ConfigError, match="force_diff_atlas"):
        load_and_validate(path, logger)


@pytest.mark.parametrize(
    "extra, message",
    [({"bandpass": [0.01, float("nan")]}, "finite"),
     ({"bandpass": [True, 0.1]}, "finite"),
     ({"notch_filter_band": [float("inf"), 0.4]}, "finite"),
     ({"motion_deriv_degree": 2.9}, "positive integer"),
     ({"motion_deriv_degree": True}, "positive integer"),
     ({"keep_run_res_dtseries": "no"}, "true, false or null"),
     ({"connectivity": {"calc_conn": "parcellated"}}, "conn_out_file_pre"),
     ({"connectivity": {"calc_conn": "parcellated", "conn_out_file_pre": "a b"}}, "file-name-safe"),
     ({"connectivity": {"calc_conn": "parcellated", "conn_out_file_pre": "fc", "fishZ": "true"}}, "true, false or null"),
     ({"extraction": {"extract_ptseries": True, "extract_out_file_pre": None}}, "extract_out_file_pre")],
)
def test_invalid_rest_values(tmp_path, logger, extra, message):
    with pytest.raises(ConfigError, match=message):
        load_and_validate(_write_config(tmp_path, [_rest_block(tmp_path, **extra)]), logger)


@pytest.mark.parametrize(
    "extraction, message",
    [({"extract_resids": True}, "extract_resids needs"),
     ({"extract_resids": "false", "stat_buckets": ["Coef"], "extract_out_file_pre": "x"}, "true, false or null"),
     ({"stat_buckets": ["Coef"], "extract_out_file_pre": None}, "extract_out_file_pre"),
     ({"stat_buckets": ["Coef"], "extract_out_file_pre": "../x"}, "file-name-safe"),
     ({"extract_raw_ptseries": True, "extract_out_file_pre": None}, "extract_out_file_pre")],
)
def test_invalid_task_act_extraction(tmp_path, task_inputs, logger, extraction, message):
    block = _task_act_block(tmp_path, task_inputs, extraction=extraction)
    with pytest.raises(ConfigError, match=message):
        load_and_validate(_write_config(tmp_path, [block]), logger)


def test_null_sections_are_allowed(tmp_path, task_inputs, logger):
    block = _task_act_block(tmp_path, task_inputs, extraction=None, contrasts=None, smoothing=None)
    assert load_and_validate(_write_config(tmp_path, [block]), logger)


@pytest.mark.parametrize("labels", [["AvB", "AvB"], ["A/B", "A_B"]])
def test_contrast_labels_stay_unique_in_file_names(tmp_path, task_inputs, logger, labels):
    block = _task_act_block(tmp_path, task_inputs, contrasts={"functions": ["1*A-1*B", "1*B-1*A"], "labels": labels})
    with pytest.raises(ConfigError, match="unique in file names"):
        load_and_validate(_write_config(tmp_path, [block]), logger)


def test_task_conn_contrasts_need_calc_conn(tmp_path, task_inputs, logger):
    block = _conn_block(tmp_path, task_inputs,
                        connectivity={"calc_conn": None, "contrasts": {"functions": ["1*A-1*B"], "labels": ["AvB"]}})
    with pytest.raises(ConfigError, match="need connectivity.calc_conn"):
        load_and_validate(_write_config(tmp_path, [block]), logger)


# ---------------------------------------------------------------------------
# BIDS discovery
# ---------------------------------------------------------------------------

def _touch_rest_files(func, runs_by_suffix, task="rest"):
    func.mkdir(parents=True, exist_ok=True)
    for name, runs in runs_by_suffix.items():
        for run in runs:
            (func / f"sub-01_task-{task}_run-{run}_{name}").write_text("x")


REST_NAMES = {"scan": "desc-preproc_bold.nii.gz", "motion": "desc-confounds_regressors.tsv",
              "csf": "desc-CSF_timeseries.1D", "wm": "desc-WM_timeseries.1D"}


def _discovery_block(tmp_path, **extra):
    block = {"name": "rest", "type": "rest_conn", "derivatives_dirs": [str(tmp_path / "deriv")],
             "subject": "01", "task": "rest", "out_dir": str(tmp_path / "out"), "out_file_pre": "sub01",
             "average_type": "mean", "bandpass": [0.01, 0.1], "motion_deriv_degree": 1, "fd_threshold": 0.4}
    block.update(extra)
    return block


def test_discovery_matches_task_exactly(tmp_path, logger):
    func = tmp_path / "deriv" / "sub-01" / "func"
    _touch_rest_files(func, {name: [1] for name in REST_NAMES.values()})
    _touch_rest_files(func, {name: [2] for name in REST_NAMES.values()}, task="restpre")
    (cfg,) = load_and_validate(_write_config(tmp_path, [_discovery_block(tmp_path)]), logger)
    assert [Path(p).name for p in cfg.scan_paths] == ["sub-01_task-rest_run-1_desc-preproc_bold.nii.gz"]


def test_discovery_requires_task(tmp_path, logger):
    block = _discovery_block(tmp_path)
    del block["task"]
    with pytest.raises(ConfigError, match="requires 'task'"):
        load_and_validate(_write_config(tmp_path, [block]), logger)


def test_discovery_without_subject_is_an_input_error(tmp_path, logger):
    block = _discovery_block(tmp_path)
    del block["subject"]
    with pytest.raises(InputError, match="Mandatory slot"):
        load_and_validate(_write_config(tmp_path, [block]), logger)


def test_discovery_refuses_misaligned_runs(tmp_path, logger):
    func = tmp_path / "deriv" / "sub-01" / "func"
    runs = {name: [1, 2] for name in REST_NAMES.values()}
    runs[REST_NAMES["motion"]] = [1, 3]
    _touch_rest_files(func, runs)
    with pytest.raises(InputError, match="name different runs"):
        load_and_validate(_write_config(tmp_path, [_discovery_block(tmp_path)]), logger)


def test_discovery_refuses_uneven_run_lists(tmp_path, logger):
    func = tmp_path / "deriv" / "sub-01" / "func"
    runs = {name: [1, 2] for name in REST_NAMES.values()}
    runs[REST_NAMES["wm"]] = [1]
    _touch_rest_files(func, runs)
    with pytest.raises(InputError, match="differ in length"):
        load_and_validate(_write_config(tmp_path, [_discovery_block(tmp_path)]), logger)


# ---------------------------------------------------------------------------
# Events and tissue files
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "rows, message",
    [(["10\t-2\tA", "20\t2\tB"], "negative or non-finite duration"),
     (["10\tn/a\tA", "20\t2\tB"], "negative or non-finite duration"),
     (["10\t2\tA", "10\t2\tA", "20\t2\tB"], "repeats 1 trial"),
     (["n/a\t2\tA", "20\t2\tB"], "outside the 80 s scan")],
)
def test_cli_dry_run_refuses_bad_events(tmp_path, dry_run_inputs, monkeypatch, caplog, rows, message):
    Path(dry_run_inputs["events.tsv"]).write_text("\n".join(["onset\tduration\ttrial_type", *rows]) + "\n")
    path = _write_config(tmp_path, [_task_act_block(tmp_path, dry_run_inputs)])
    with pytest.raises(SystemExit) as exc:
        _dry_run(path, monkeypatch)
    assert exc.value.code == 2
    assert message in caplog.text


def test_numeric_trial_types_match_quoted_labels(tmp_path, dry_run_inputs, monkeypatch):
    Path(dry_run_inputs["events.tsv"]).write_text("onset\tduration\ttrial_type\n10\t2\t1\n20\t2\t2\n")
    block = _task_act_block(tmp_path, dry_run_inputs, cond_labels=["1", "2"])
    _dry_run(_write_config(tmp_path, [block]), monkeypatch)


def test_tissue_file_must_be_single_column(tmp_path, dry_run_inputs, monkeypatch, caplog):
    csf = tmp_path / "csf.txt"
    np.savetxt(csf, np.zeros((100, 2)))
    block = _task_act_block(tmp_path, dry_run_inputs)
    block["paths"]["CSF_path"] = str(csf)
    with pytest.raises(SystemExit) as exc:
        _dry_run(_write_config(tmp_path, [block]), monkeypatch)
    assert exc.value.code == 2
    assert "2 columns, expected 1" in caplog.text
