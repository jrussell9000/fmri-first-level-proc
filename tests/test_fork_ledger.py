"""Tests for .github/scripts/check_fork_ledger.py, the check that FORK.md is complete."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("check_fork_ledger", ROOT / ".github/scripts/check_fork_ledger.py")
ledger_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ledger_check)

LEDGER = {"pyproject.toml": "M", "gone.md": "D"}
ADDED = ["FORK.md", "docs/", "fmri_first_level_proc/abcd/"]


def test_declared_differences_pass():
    changes = {"pyproject.toml": "M", "gone.md": "D", "FORK.md": "A", "docs/page.md": "A"}
    assert ledger_check.problems(changes, LEDGER, ADDED) == []


def test_a_changed_core_module_fails():
    changes = {"pyproject.toml": "M", "gone.md": "D", "fmri_first_level_proc/engine.py": "M"}
    [problem] = ledger_check.problems(changes, LEDGER, ADDED)
    assert problem.startswith("fmri_first_level_proc/engine.py")


def test_a_new_file_in_the_core_fails():
    changes = {"pyproject.toml": "M", "gone.md": "D", "fmri_first_level_proc/extra.py": "A"}
    [problem] = ledger_check.problems(changes, LEDGER, ADDED)
    assert "outside the paths" in problem


def test_a_path_prefix_needs_its_slash_and_a_file_needs_its_whole_name():
    assert ledger_check.is_under("docs/a.md", ADDED)
    assert not ledger_check.is_under("docs.md", ADDED)
    assert not ledger_check.is_under("FORK.md.bak", ADDED)


def test_a_listed_file_that_no_longer_differs_fails():
    [problem] = ledger_check.problems({"pyproject.toml": "M"}, LEDGER, ADDED)
    assert "gone.md" in problem and "unchanged" in problem


def test_a_listed_file_with_another_status_fails():
    changes = {"pyproject.toml": "D", "gone.md": "D"}
    assert len(ledger_check.problems(changes, LEDGER, ADDED)) == 2


def test_this_repository_fork_md_parses():
    base, ledger, added = ledger_check.parse_fork_md((ROOT / "FORK.md").read_text())
    assert len(base) == 40
    assert ledger["pyproject.toml"] == "M"
    assert "fmri_first_level_proc/abcd/" in added


def test_fork_md_without_a_full_base_is_an_error():
    with pytest.raises(ValueError, match="upstream base"):
        ledger_check.parse_fork_md("**Upstream base:** `e40d1bc`")
