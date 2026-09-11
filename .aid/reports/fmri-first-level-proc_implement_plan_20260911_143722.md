<implement_plan>
  <meta project="fmri-first-level-proc" mode="implement" submodule="plan" timestamp="2026-09-11T14:37:22Z" />
  <input_reports>
    <report path="fmri-first-level-proc_brainstorm_20260911_142835.md" mode="brainstorm" key_items="3" />
  </input_reports>
  <plan_notes>
    The brainstorm T5 item listed two sub-items: (1) exit code 5 missing from docstring, (2) stale header metadata. On verification, exit code 5 is already documented at run_first_level.py line 31. The brainstorm finding was a false positive caused by a truncated read during context gathering. Only the header metadata update (sub-item 2) is valid. This is reflected in C3 below.
  </plan_notes>
  <changes>
    <change id="C1" priority="P0" source_item="T1+T3: .gitignore whitelist gap + tools.lock.yaml tracking">
      <file path=".gitignore" action="modify" />
      <description>Add whitelist entries for 4 new Python modules (bids.py, checkpoint.py, exceptions.py, runtime.py) and tools.lock.yaml to the ignore-all .gitignore.</description>
      <spec>
        Insert after line 19 (`!fmri_first_level_proc/task_conn_first_level.py`), maintaining alphabetical order within the module block:
          !fmri_first_level_proc/bids.py
          !fmri_first_level_proc/checkpoint.py
          !fmri_first_level_proc/exceptions.py
          !fmri_first_level_proc/runtime.py

        Insert `!tools.lock.yaml` in a new section between the core pipeline files block and the AID Framework block, with a comment header:
          # Tool version lockfile
          !tools.lock.yaml
      </spec>
      <dependencies>none</dependencies>
      <risk>low - additive change to .gitignore; cannot break existing tracked files</risk>
      <rollback>Remove the added lines.</rollback>
    </change>
    <change id="C2" priority="P0" source_item="T2: Version bump to 3.1.0">
      <file path="fmri_first_level_proc/__init__.py" action="modify" />
      <file path="pyproject.toml" action="modify" />
      <description>Bump version string from "3.0.0" to "3.1.0" in both version-carrying files.</description>
      <spec>
        __init__.py line 9: change `__version__ = "3.0.0"` to `__version__ = "3.1.0"`.
        pyproject.toml line 7: change `version = "3.0.0"` to `version = "3.1.0"`.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - single-token replacement in two files</risk>
      <rollback>Revert the string replacements.</rollback>
    </change>
    <change id="C3" priority="P1" source_item="T5: Header metadata update in run_first_level.py">
      <file path="fmri_first_level_proc/run_first_level.py" action="modify" />
      <description>Update stale header comment metadata (version and date). Note: the brainstorm's exit code 5 docstring sub-item was verified as already present at line 31; only the header metadata is stale.</description>
      <spec>
        Line 15: change `# Version: 3.0.0` to `# Version: 3.1.0`.
        Line 16: change `# Last updated: 05/01/26` to `# Last updated: 09/11/26`.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - comment-only change; no runtime effect</risk>
      <rollback>Revert the two comment lines.</rollback>
    </change>
  </changes>
  <execution_order>C1, C2, C3 (no dependencies; may execute in any order or in parallel)</execution_order>
</implement_plan>
