<brainstorm_report>
  <meta project="fmri_first_level_proc" mode="brainstorm" timestamp="2026-08-24T12:00:00-04:00" />
  <context_files>
    <file path="fmri-first-level-proc_implement_plan_20260819_145136.md" relevance="Upstream implement plan (T9c from fmri-proc-orchestrator brainstorm) proposing status vocabulary and severity gate harmonization across all three pipeline modules." />
    <file path="fmri_first_level_proc/task_act_first_level.py" relevance="Pipeline module with status gate at L764-765 and docstring at L510." />
    <file path="fmri_first_level_proc/task_conn_first_level.py" relevance="Pipeline module with status gate at L833-837." />
    <file path="fmri_first_level_proc/rest_conn_first_level.py" relevance="Pipeline module with status gate at L778-779 and docstring at L594." />
    <file path="fmri_first_level_proc/run_first_level.py" relevance="CLI dispatcher with high-only exit-code-3 gate at L199 (already aligned with the proposed change)." />
    <file path="fmri_first_level_proc/first_level_utils.py" relevance="FirstLevelResult dataclass (L60-65) and graded_warning() (L225-269)." />
  </context_files>
  <topics>
    <topic id="T1" title="Severity gate semantics">
      <summary>The three pipeline modules use a non-low gate (!= "low", catching medium + high) for FirstLevelResult.status, while run_first_level.py uses a high-only gate (== "high") for exit code 3. This mismatch means medium-severity warnings produce status="success_with_warnings" but exit code 0. The plan proposes aligning both layers to high-only gating with "warning" vocabulary, resolving the contradiction.</summary>
      <research>No external research required. Analysis based on codebase inspection of all four modules.</research>
      <approaches>
        <approach id="A1" label="Accept plan (high-only gate, 'warning' vocabulary)" feasibility="high" risk="low">
          <description>Align pipeline-level status gate to == "high" and change vocabulary from "success_with_warnings" to "warning". Matches the already-deployed CLI gate. Medium-severity warnings are still accessible via FirstLevelResult.warnings; the orchestrator inspects the list directly for medium-severity routing.</description>
          <pros>Resolves CLI-vs-pipeline gate mismatch. Simplifies the status contract to a binary signal (success/warning). Eliminates redundant medium-severity encoding in status when warnings list is always available. "warning" is a cleaner enum token than "success_with_warnings".</pros>
          <cons>Medium-severity conditions no longer degrade the status field. Orchestrator must inspect warnings list to detect them (which it should be doing regardless).</cons>
        </approach>
        <approach id="A2" label="Keep non-low gate, change vocabulary only" feasibility="high" risk="low">
          <description>Change vocabulary to "warning" but keep the non-low gate, so medium-severity warnings still degrade the status. Preserves current sensitivity at the cost of maintaining the CLI mismatch.</description>
          <pros>Retains medium-severity signal in the status field.</pros>
          <cons>Perpetuates the mismatch with run_first_level.py's high-only exit-code gate. Redundant with warnings list inspection.</cons>
        </approach>
      </approaches>
      <decision status="decided" chosen="A1">High-only gate with "warning" vocabulary accepted. The alignment with the CLI exit-code gate is the strongest argument: both layers should agree on what "notable" means. The orchestrator has full access to FirstLevelResult.warnings for medium-severity routing.</decision>
    </topic>
    <topic id="T2" title="Plan completeness (docstring gap)">
      <summary>The implement plan (C1/C2/C3) omits two docstring sites that explicitly reference the old "success_with_warnings" vocabulary: task_act_first_level.py:510 and rest_conn_first_level.py:594. These would become stale after the code changes.</summary>
      <research>Verified via codebase grep: exactly 2 docstring sites reference "success_with_warnings" (task_act L510, rest_conn L594). task_conn has no such docstring reference.</research>
      <approaches>
        <approach id="A1" label="Fold into plan (C4/C5)" feasibility="high" risk="low">
          <description>Add two docstring changes to the implement plan. Each is a single-line edit changing ('success' or 'success_with_warnings') to ('success' or 'warning'). Ensures the commit is self-consistent.</description>
          <pros>Commit-level consistency. Avoids shipping known-stale documentation. Trivial scope addition (2 single-line edits).</pros>
          <cons>None material.</cons>
        </approach>
        <approach id="A2" label="Defer to /document" feasibility="high" risk="low">
          <description>Leave the plan as-is and fix docstrings in a subsequent /document pass.</description>
          <pros>Keeps implement plan scoped to the orchestrator's T9c spec.</pros>
          <cons>Creates a known-stale artifact in the commit. /document is heavier than warranted for 2 lines.</cons>
        </approach>
      </approaches>
      <decision status="decided" chosen="A1">Fold docstring updates into the implement plan as C4/C5. Two single-line edits at task_act L510 and rest_conn L594, changing ('success' or 'success_with_warnings') to ('success' or 'warning').</decision>
    </topic>
  </topics>
  <action_items>
    <item priority="P0" target_mode="implement" description="Execute amended implement plan: C1 (task_act gate), C2 (task_conn gate), C3 (rest_conn gate), C4 (task_act docstring L510), C5 (rest_conn docstring L594)." />
    <item priority="P1" target_mode="test" description="Verify 665/665 tests still pass after the changes. No new tests expected (no existing tests assert on 'success_with_warnings'; the run_first_level exit-code-3 test already uses high-only gating)." />
  </action_items>
  <next_steps>Proceed to /implement to execute the amended 5-change plan, then /test run_suite to verify no regressions.</next_steps>
</brainstorm_report>
