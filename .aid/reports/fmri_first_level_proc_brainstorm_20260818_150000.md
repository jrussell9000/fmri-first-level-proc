<brainstorm_report>
  <meta project="fmri_first_level_proc" mode="brainstorm" timestamp="2026-08-18T15:00:00-04:00" />
  <context_files>
    <file path="HARMONIZE_fmri-first-level-proc_20260816_212459.md" relevance="Source document: orchestrator harmonization recommendations (3 items)" />
    <file path="fmri_first_level_proc/exceptions.py" relevance="T1: current FmriFirstLevelError hierarchy (no __init__ override)" />
    <file path="tools.lock.yaml" relevance="T2/T3: current lockfile (AFNI=PLACEHOLDER, no python field)" />
    <file path="fmri_first_level_proc/runtime.py" relevance="T2/T3: probe_tool_versions() and preflight_tool_environments()" />
    <file path="fmri_first_level_proc/run_first_level.py" relevance="T2/T3: lockfile-absent resilience path (lines 139-146)" />
  </context_files>
  <topics>
    <topic id="T1" title="Exception base class context: dict">
      <summary>Add a context: dict parameter to FmriFirstLevelError.__init__() so raise sites can attach structured metadata (subject ID, run number, analysis type) to exceptions. Fully backward-compatible: context defaults to None (stored as {}), so all 123 existing raise sites continue to work unchanged. No subclass __init__ overrides exist, so the new signature propagates automatically. Incremental adoption: individual raise sites updated as needed in future work.</summary>
      <research>Not required (codebase-local, mechanical change).</research>
      <approaches>
        <approach id="A1" label="Add context: dict to FmriFirstLevelError" feasibility="high" risk="low">
          <description>Add context: dict | None = None parameter to FmriFirstLevelError.__init__(). Store as self.context = context if context is not None else {}. Single-file change to exceptions.py.</description>
          <pros>Backward-compatible with all existing raise sites. Enables structured error metadata for orchestrator consumption. Standard Python pattern.</pros>
          <cons>None identified.</cons>
        </approach>
      </approaches>
      <decision status="decided" chosen="A1">Accepted as specified by orchestrator recommendation. 4-line change to exceptions.py. No downstream raise-site modifications.</decision>
    </topic>
    <topic id="T2" title="AFNI version pin (PLACEHOLDER to 26.0.09)">
      <summary>Replace the PLACEHOLDER value in tools.lock.yaml with 26.0.09, the AFNI version deployed in the orchestrator's Environment B. The PLACEHOLDER bypass code path in runtime.py:probe_tool_versions() (lines 153-155) is retained as a development escape hatch. The pip-installed resilience path (run_first_level.py:139-146, graded_warning when lockfile absent) is unaffected.</summary>
      <research>Not required (codebase-local, value change).</research>
      <approaches>
        <approach id="A1" label="Set AFNI pin to 26.0.09, retain PLACEHOLDER bypass" feasibility="high" risk="low">
          <description>Single-line change in tools.lock.yaml. No changes to runtime.py. Existing validation logic (exact-match comparison, ToolUnavailableError on mismatch) handles the new value correctly.</description>
          <pros>Enforces version consistency in orchestrator deployments. PLACEHOLDER bypass preserved for local development flexibility. Zero code changes beyond the lockfile.</pros>
          <cons>None identified.</cons>
        </approach>
      </approaches>
      <decision status="decided" chosen="A1">Accepted as specified. Single-line lockfile change. PLACEHOLDER bypass retained.</decision>
    </topic>
    <topic id="T3" title="Python pin in tools.lock.yaml">
      <summary>Add python: "3.14.3" as a top-level field in tools.lock.yaml and add validation logic in runtime.py. Validation uses minor-series match semantics: the pin string "3.14.3" documents the exact tested version, but enforcement compares only major.minor (sys.version_info.major and sys.version_info.minor against the pin's parsed major.minor). Strict enforcement: raises ToolUnavailableError on mismatch. This respects PEP 440 semantics (patch releases within a minor series are backward-compatible) while catching major/minor mismatches. The Python check is added inside probe_tool_versions() to reuse the already-loaded lockfile dict. The lockfile-absent resilience path is unaffected. The graded_warning message at run_first_level.py:143 should be generalized from "skipping AFNI version pinning" to "skipping version pinning" since the lockfile now covers both tools.</summary>
      <research>Not required (codebase-local, standard Python versioning semantics).</research>
      <approaches>
        <approach id="A1" label="Lockfile field only (no validation)" feasibility="high" risk="low">
          <description>Add python: "3.14.3" to tools.lock.yaml as a declarative record. No validation code.</description>
          <pros>Zero code changes beyond lockfile.</pros>
          <cons>Pin is inert. Mismatches go undetected. First-level-proc is a standalone module and cannot rely on the orchestrator for enforcement.</cons>
        </approach>
        <approach id="A2" label="Lockfile field + minor-series strict enforcement" feasibility="high" risk="low">
          <description>Add lockfile field. Add validation in probe_tool_versions() comparing sys.version_info major.minor against pin's major.minor. Raise ToolUnavailableError on mismatch.</description>
          <pros>Self-contained enforcement. Respects PEP 440 patch-level compatibility. Avoids maintenance burden of updating the pin for every patch release. Reuses existing lockfile read.</pros>
          <cons>Rejects users on a different minor version (e.g., 3.12 user with a 3.14.3 lockfile). Mitigated by: lockfile absence (pip-installed) already skips gracefully.</cons>
        </approach>
        <approach id="A3" label="Lockfile field + soft validation (graded_warning)" feasibility="high" risk="low">
          <description>Same as A2 but uses graded_warning instead of raising.</description>
          <pros>Does not block non-orchestrator users on different Python versions.</pros>
          <cons>Warnings may be ignored. Does not enforce the contract first-level-proc needs as a standalone module.</cons>
        </approach>
      </approaches>
      <decision status="decided" chosen="A2">Minor-series match with strict enforcement. Pin string "3.14.3" in lockfile; validation compares major.minor only. Raises ToolUnavailableError on mismatch. Validation logic added inside probe_tool_versions(). Lockfile-absent resilience path unaffected. graded_warning message at the call site generalized to cover both AFNI and Python pinning.</decision>
    </topic>
  </topics>
  <action_items>
    <item priority="P1" target_mode="implement" description="T1: Add context: dict | None = None parameter to FmriFirstLevelError.__init__() in exceptions.py" />
    <item priority="P1" target_mode="implement" description="T2: Replace PLACEHOLDER with 26.0.09 in tools.lock.yaml" />
    <item priority="P1" target_mode="implement" description="T3: Add python: 3.14.3 field to tools.lock.yaml; add minor-series Python version validation in runtime.py:probe_tool_versions(); generalize lockfile-absent graded_warning message in run_first_level.py" />
    <item priority="P2" target_mode="test" description="Add tests for Python version validation: matching minor (pass), mismatched minor (ToolUnavailableError), absent python field in lockfile (skip gracefully), absent lockfile (existing resilience path unchanged)" />
    <item priority="P2" target_mode="test" description="Add test for FmriFirstLevelError context parameter: default is {}, explicit dict is stored, subclasses inherit" />
  </action_items>
  <next_steps>Proceed to /implement for the 3 changes (all mechanical, well-specified). Follow with /test to cover the new validation logic and exception constructor.</next_steps>
</brainstorm_report>
