<brainstorm_report>
  <meta project="fmri-first-level-proc" mode="brainstorm" timestamp="2026-09-11T14:28:35Z" />
  <context_files>
    <file path=".gitignore" relevance="Whitelist-based gitignore missing 4 new Python modules and tools.lock.yaml" />
    <file path="fmri_first_level_proc/__init__.py" relevance="Version string (currently 3.0.0, to be bumped to 3.1.0)" />
    <file path="pyproject.toml" relevance="Version string (currently 3.0.0, to be bumped to 3.1.0)" />
    <file path="fmri_first_level_proc/run_first_level.py" relevance="Exit code 5 (ModelError) missing from docstring; stale header metadata" />
    <file path="README.md" relevance="Multiple factually wrong and missing documentation items" />
    <file path="INPUT_SPECIFICATION.md" relevance="task_act extraction section documents removed API; missing new fields and outputs" />
    <file path="tools.lock.yaml" relevance="Decision to commit; pins AFNI 26.0.09 and Python 3.14.3" />
  </context_files>
  <topics>
    <topic id="T1" title=".gitignore whitelist gap">
      <summary>Four new Python modules (bids.py, checkpoint.py, exceptions.py, runtime.py) added during the v3.0.0 refactor are not whitelisted in the project's ignore-all .gitignore. Without whitelisting, git will not track them and pip install from GitHub will fail on import.</summary>
      <research>No research needed; identified by direct comparison of .gitignore entries against fmri_first_level_proc/ directory listing.</research>
      <approaches>
        <approach id="A1" label="Add whitelist entries" feasibility="high" risk="low">
          <description>Add !fmri_first_level_proc/bids.py, !fmri_first_level_proc/checkpoint.py, !fmri_first_level_proc/exceptions.py, and !fmri_first_level_proc/runtime.py to .gitignore under the existing module block.</description>
          <pros>Straightforward fix; no alternatives.</pros>
          <cons>None.</cons>
        </approach>
      </approaches>
      <decision status="decided" chosen="A1">Add all four whitelist entries. User also approved adding !tools.lock.yaml in the same edit (resolving T3).</decision>
    </topic>
    <topic id="T2" title="Version number decision">
      <summary>All changes since v2.5.0 (the last commit) are one uncommitted delta spanning two logical scopes: "v3.0.0" infrastructure refactor and "v3.1.0" feature additions. Version in __init__.py and pyproject.toml currently reads 3.0.0. Decision needed on what version to publish.</summary>
      <research>No research needed; decision is purely about project versioning strategy.</research>
      <approaches>
        <approach id="A1" label="Single v3.0.0" feasibility="high" risk="low">
          <description>Ship everything as v3.0.0. One commit, one tag.</description>
          <pros>Simple; version already set in code.</pros>
          <cons>Semantically loose: "3.0.0" suggests infrastructure-only, but PSC/stat_buckets are user-facing API changes.</cons>
        </approach>
        <approach id="A2" label="Single v3.1.0" feasibility="high" risk="low">
          <description>Ship everything as v3.1.0, skipping v3.0.0 as a published version. One commit, one tag. Bump version strings from 3.0.0 to 3.1.0.</description>
          <pros>Acknowledges both infrastructure and feature scope. v3.0.0 was never released so skipping costs nothing. Avoids partial-diff staging risk. Test suite (686/686) validated against combined state.</pros>
          <cons>Minor version bump required in two files.</cons>
        </approach>
        <approach id="A3" label="Split v3.0.0 + v3.1.0" feasibility="low" risk="high">
          <description>Stage partial diffs for v3.0.0 commit/tag, then remaining diffs for v3.1.0 commit/tag.</description>
          <pros>Cleanest semantic history.</pros>
          <cons>Deeply interleaved changes make surgical staging error-prone. Test suite validated only against combined state, not each stage independently.</cons>
        </approach>
      </approaches>
      <decision status="decided" chosen="A2">Single v3.1.0 release. Update __init__.py and pyproject.toml from 3.0.0 to 3.1.0.</decision>
    </topic>
    <topic id="T3" title="tools.lock.yaml tracking">
      <summary>tools.lock.yaml pins AFNI 26.0.09 and Python 3.14.3. The code gracefully handles its absence (emits low-severity graded_warning, skips version pinning). Decision: commit to repo or keep local-only?</summary>
      <research>No research needed; code behavior verified by reading run_first_level.py lines 140-147.</research>
      <approaches>
        <approach id="A1" label="Commit (whitelist in .gitignore)" feasibility="high" risk="low">
          <description>Add !tools.lock.yaml to .gitignore. File ships with the repo for clone-and-run users; pip-installed users still get the graceful-absence path since the lockfile resolves relative to __file__.parent.parent (repo root, not site-packages).</description>
          <pros>Documents expected tool versions. Clone-and-run users get version validation out of the box.</pros>
          <cons>Users with different AFNI/Python versions will see version mismatch warnings or errors (ToolVersionError) until they update the lockfile. This is arguably a feature, not a bug.</cons>
        </approach>
        <approach id="A2" label="Keep local-only" feasibility="high" risk="low">
          <description>Do not whitelist. Lockfile remains a local development artifact.</description>
          <pros>No version constraints imposed on other users.</pros>
          <cons>Clone-and-run users lose version validation; version pinning becomes invisible.</cons>
        </approach>
      </approaches>
      <decision status="decided" chosen="A1">Commit tools.lock.yaml. Resolved during T1 discussion by user's proactive approval.</decision>
    </topic>
    <topic id="T4" title="Documentation staleness scope for /document">
      <summary>README.md and INPUT_SPECIFICATION.md have material gaps relative to the v3.1.0 codebase. This topic defines the minimum scope /document must address.</summary>
      <research>No research needed; gaps identified by comparing documentation text against current code.</research>
      <approaches>
        <approach id="A1" label="Comprehensive update (both files)" feasibility="high" risk="low">
          <description>Update both README.md and INPUT_SPECIFICATION.md to reflect v3.1.0 state. Non-exhaustive minimum items enumerated; /document may address additional staleness it encounters.</description>
          <pros>Documentation matches code at release time. Users and orchestrators have accurate contracts.</pros>
          <cons>Substantial writing effort for /document, particularly INPUT_SPECIFICATION.md.</cons>
        </approach>
      </approaches>
      <decision status="decided" chosen="A1">
        /document must address at minimum:
        README.md: (1) Python version >= 3.12, (2) programmatic usage example updated to list[ResolvedConfig] API, (3) CLI entry point fmri-first-level-proc as primary with run-first-level noted as deprecated, (4) exception hierarchy and exit codes, (5) new features (PSC scaling, stat_buckets, warning accumulator, BIDS, DAG, runtime validation).
        INPUT_SPECIFICATION.md: (1) task_act extraction section rewritten for stat_buckets API, (2) scale_to_psc field for all three types, (3) new output files (PSC NIfTI, stat bucket NIfTIs, bucket index JSONs, bucket_stats index JSON), (4) BIDS-format timing file acceptance, (5) exit code table, (6) runtime validation (tools.lock.yaml, AFNI/Python version checks).
        List is non-exhaustive; /document should also catch any additional staleness it encounters.
      </decision>
    </topic>
    <topic id="T5" title="Minor code-level cleanups">
      <summary>Two minor issues in run_first_level.py to fix before commit: (1) docstring exit code table omits exit code 5 (ModelError), and (2) header metadata says Version 3.0.0 / Last updated 05/01/26.</summary>
      <research>No research needed; verified by reading run_first_level.py lines 30 and 208.</research>
      <approaches>
        <approach id="A1" label="Fix both in /implement" feasibility="high" risk="low">
          <description>Add exit code 5 line to docstring. Update header version to 3.1.0 and date to current.</description>
          <pros>Trivial fixes; included in the same /implement pass as T1/T2/T3.</pros>
          <cons>None.</cons>
        </approach>
      </approaches>
      <decision status="decided" chosen="A1">Fix both items in /implement alongside T1, T2, and T3 changes.</decision>
    </topic>
  </topics>
  <action_items>
    <item priority="P0" target_mode="implement" description="Add 4 new module whitelist entries + tools.lock.yaml to .gitignore (T1, T3)" />
    <item priority="P0" target_mode="implement" description="Bump version from 3.0.0 to 3.1.0 in __init__.py and pyproject.toml (T2)" />
    <item priority="P1" target_mode="implement" description="Add exit code 5 (ModelError) to run_first_level.py docstring; update header metadata to v3.1.0 and current date (T5)" />
    <item priority="P0" target_mode="document" description="Update README.md and INPUT_SPECIFICATION.md per T4 minimum scope (non-exhaustive)" />
    <item priority="P0" target_mode="publish" description="Commit, tag v3.1.0, push to GitHub (AI-005 resolution)" />
  </action_items>
  <next_steps>Invoke /implement for T1+T2+T3+T5 code changes (small, surgical edits). Then /document for T4. Then /publish to commit, tag, and push v3.1.0.</next_steps>
</brainstorm_report>
