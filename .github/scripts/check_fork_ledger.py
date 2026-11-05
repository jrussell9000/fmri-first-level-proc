#!/usr/bin/env python3
"""Fail unless every difference from the upstream base is one FORK.md declares.

An upstream file the fork changed must be listed in FORK.md's ledger table, and a listed file must
still differ. Any other file the fork has must be new, under a path FORK.md lists as added.
Run from the repository root, with full history. Standard library only.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

FORK_MD = Path("FORK.md")
BASE = re.compile(r"\*\*Upstream base:\*\* `([0-9a-f]{40})`")
LEDGER_ROW = re.compile(r"^\|\s*([MD])\s*\|\s*`([^`]+)`\s*\|")
ADDED_ROW = re.compile(r"^- `([^`]+)`$")


def section(text: str, name: str) -> list[str]:
    match = re.search(rf"<!-- {name}:start -->\n(.*?)<!-- {name}:end -->", text, re.DOTALL)
    if match is None:
        raise ValueError(f"FORK.md has no {name} section")
    return match.group(1).splitlines()


def parse_fork_md(text: str) -> tuple[str, dict[str, str], list[str]]:
    """Return (upstream base, {path: status} from the ledger, added paths)."""
    base = BASE.search(text)
    if base is None:
        raise ValueError("FORK.md states no full upstream base commit")
    ledger = {m.group(2): m.group(1) for m in map(LEDGER_ROW.match, section(text, "ledger")) if m}
    added = [m.group(1) for m in map(ADDED_ROW.match, section(text, "added")) if m]
    if not ledger or not added:
        raise ValueError("FORK.md's ledger or added section is empty")
    return base.group(1), ledger, added


def is_under(path: str, prefixes: list[str]) -> bool:
    return any(path.startswith(p) if p.endswith("/") else path == p for p in prefixes)


def problems(changes: dict[str, str], ledger: dict[str, str], added: list[str]) -> list[str]:
    """Compare {path: status} from git with what FORK.md declares."""
    found = []
    for path, status in sorted(changes.items()):
        if status == "A":
            if not is_under(path, added):
                found.append(f"{path}: new file outside the paths FORK.md lists as added")
        elif ledger.get(path) != status:
            found.append(f"{path}: status {status} differs from upstream, not declared in the ledger")
    for path, status in sorted(ledger.items()):
        if changes.get(path) != status:
            found.append(f"{path}: the ledger says {status}, git says {changes.get(path, 'unchanged')}")
    return found


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def main() -> int:
    base, ledger, added = parse_fork_md(FORK_MD.read_text())
    if subprocess.run(["git", "merge-base", "--is-ancestor", base, "HEAD"], check=False).returncode:
        print(f"Upstream base {base} is not an ancestor of HEAD")
        return 1
    changes = {}
    for line in git("diff", "--name-status", "--no-renames", base, "HEAD").splitlines():
        status, path = line.split("\t", 1)
        changes[path] = status
    found = problems(changes, ledger, added)
    for problem in found:
        print(problem)
    print(f"{len(changes)} files differ from {base[:7]}; {len(found)} undeclared")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
