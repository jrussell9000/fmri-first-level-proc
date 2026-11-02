"""CPU budget (OMP_NUM_THREADS, parallel_map) and cached/combined 3dinfo queries."""

import threading
import time

import pytest

from fmri_first_level_proc import afni
from fmri_first_level_proc.afni import get_3dinfo_properties, parallel_map, run_afni_command, thread_budget

from fake_afni import FakeAfni

pytestmark = pytest.mark.level0_unit


def _omp_seen():
    out = run_afni_command(["sh", "-c", 'printf %s "${OMP_NUM_THREADS-unset}"'], capture_output=True)
    return out


def test_omp_num_threads_follows_budget(monkeypatch):
    monkeypatch.delenv("OMP_NUM_THREADS", raising=False)
    assert _omp_seen() == "unset"
    with thread_budget(3):
        assert _omp_seen() == "3"
        with thread_budget(1):
            assert _omp_seen() == "1"
        assert _omp_seen() == "3"
    assert _omp_seen() == "unset"


def test_parallel_map_sequential_without_budget():
    threads = set()
    assert parallel_map(lambda x: threads.add(threading.get_ident()) or x * 2, [1, 2, 3]) == [2, 4, 6]
    assert threads == {threading.get_ident()}


def test_parallel_map_splits_budget_and_keeps_order():
    seen = []
    lock = threading.Lock()

    def work(x):
        time.sleep(0.01 * (3 - x))  # finish out of order
        with lock:
            seen.append(afni._thread_budget.get())
        return x

    with thread_budget(7):
        assert parallel_map(work, [0, 1, 2]) == [0, 1, 2]
        assert afni._thread_budget.get() == 7  # caller's budget restored
    assert seen == [2, 2, 2]  # 3 workers share 7 cores -> 2 threads each


def test_parallel_map_reraises_worker_error():
    def work(x):
        if x == 1:
            raise ValueError("boom")
        return x

    with thread_budget(4), pytest.raises(ValueError, match="boom"):
        parallel_map(work, [0, 1, 2])


def test_3dinfo_single_combined_call_then_cached(tmp_path, monkeypatch, logger):
    fake = FakeAfni(n_rois=5).install(monkeypatch)
    tpl = tmp_path / "parc.nii.gz"
    tpl.write_bytes(b"x")

    props = get_3dinfo_properties(tpl, logger=logger)
    assert props == {"space": "MNI", "orient": "RAI", "spacing": "2.000000\t2.000000\t2.000000", "dmax": "5"}
    assert fake.calls == [["3dinfo", "-space", "-orient", "-ad3", "-dmax", str(tpl)]]

    assert get_3dinfo_properties(str(tpl), logger=logger) == props
    assert len(fake.calls) == 1  # cache hit

    tpl.write_bytes(b"changed")  # size/mtime change invalidates
    get_3dinfo_properties(tpl, logger=logger)
    assert len(fake.calls) == 2


def test_3dinfo_falls_back_to_per_flag_queries(tmp_path, monkeypatch, logger):
    fake = FakeAfni().install(monkeypatch)
    real_info = fake._info
    monkeypatch.setattr(fake, "_info", lambda cmd: "garbled\n" if len(cmd) > 3 else real_info(cmd))
    scan = tmp_path / "scan.nii.gz"
    scan.write_bytes(b"x")

    props = get_3dinfo_properties(scan, logger=logger)

    assert props["spacing"] == "2.000000\t2.000000\t2.000000"
    assert [c[1] for c in fake.calls] == ["-space", "-space", "-orient", "-ad3", "-dmax"]
