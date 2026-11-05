#!/usr/bin/env python3
"""Fail when upstream or the orchestrator has moved past the commits this repository records.

The failed run is the flag: it lists what to read. Run from the repository root, with `gh`
authenticated. Standard library only.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

PINS = (
    ("tjkeding/fmri-first-level-proc", Path("FORK.md"), r"\*\*Upstream base:\*\* `([0-9a-f]{7,40})`"),
    (
        "tjkeding/ABCD_fmri_orchestrator_S3",
        Path("docs/orchestrator_comparison.md"),
        r"\*\*Compared against:\*\* orchestrator `([0-9a-f]{7,40})`",
    ),
)


def report(repo: str, pin: str) -> list[str]:
    """Lines to report for `repo`; empty when its main is still at `pin`."""
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/compare/{pin}...main"],
        check=True,
        capture_output=True,
        text=True,
    )
    compare = json.loads(result.stdout)
    if compare["status"] == "identical":
        return []
    lines = [f"**{repo}** is {compare['status']} from `{pin}`:", ""]
    lines += [
        f"- `{c['sha'][:7]}` {c['commit']['message'].splitlines()[0]}" for c in compare["commits"]
    ]
    return [*lines, ""]


def main() -> int:
    out = []
    for repo, path, pattern in PINS:
        match = re.search(pattern, path.read_text())
        if match is None:
            raise ValueError(f"{path} records no commit for {repo}")
        out += report(repo, match.group(1))
    text = "\n".join(out) or "Upstream and the orchestrator match the recorded commits."
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as handle:
            handle.write(text + "\n")
    return 1 if out else 0


if __name__ == "__main__":
    sys.exit(main())
