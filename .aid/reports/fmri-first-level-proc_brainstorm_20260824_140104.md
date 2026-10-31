<brainstorm_report>
  <meta project="fmri-first-level-proc" mode="brainstorm" timestamp="2026-08-24T14:01:04Z" source_project="fmri-proc-orchestrator" source_report="fmri-proc-orchestrator_brainstorm_20260824_140104.md" />
  <context>This report contains the subset of harmonization decisions from the fmri-proc-orchestrator brainstorm that require changes in fmri-first-level-proc. These decisions were made during a cross-module harmonization audit of the four-project pipeline (orchestrator, bids-recon, preproc, first-level-proc).</context>
  <topics>
    <topic id="T4" title="Warning accumulation: add module-level _WARNING_ACCUMULATOR">
      <summary>The cross-pipeline contract standardizes warning accumulation via a module-level _WARNING_ACCUMULATOR list with get_warnings()/clear_warnings() API. first-level-proc's first_level_utils.py currently returns dicts from graded_warning() without accumulating; callers append to local warnings lists threaded into FirstLevelResult.warnings. The accumulator pattern must be adopted for plumbing consistency across sister modules.</summary>
      <decision status="decided">Add _WARNING_ACCUMULATOR (list[dict]), get_warnings() -> list[dict], and clear_warnings() -> None to first_level_utils.py. Have graded_warning() append to the accumulator. Update each pipeline entry point (run_task_act in task_act_first_level.py, run_task_conn in task_conn_first_level.py, run_rest_conn in rest_conn_first_level.py): call clear_warnings() at entry; at FirstLevelResult construction, use get_warnings() instead of the locally-threaded warnings list. Remove the local warnings list threading from intermediate function signatures where it is no longer needed.</decision>
    </topic>
    <topic id="T5" title="Add ToolVersionError to exception hierarchy">
      <summary>The cross-pipeline contract distinguishes ToolUnavailableError (binary not found on PATH) from ToolVersionError (binary exists but version below required floor). bids-recon already defines ToolVersionError. first-level-proc currently uses ToolUnavailableError for both conditions in runtime.py. The distinction must be added for semantic precision and orchestrator exception mapping.</summary>
      <decision status="decided">Add ToolVersionError as a subclass of FmriFirstLevelError (with context: dict parameter, matching the existing exception hierarchy pattern) in exceptions.py. Update runtime.py: where probe_tool_versions() currently raises ToolUnavailableError on version mismatch (binary found but version wrong), raise ToolVersionError instead. Retain ToolUnavailableError for the case where the binary is genuinely absent. Update run_first_level.py entry point to map ToolVersionError to exit code 4.</decision>
    </topic>
  </topics>
  <action_items>
    <item priority="P1" target_mode="implement" description="T4: Add _WARNING_ACCUMULATOR, get_warnings(), clear_warnings() to first_level_utils.py; update run_task_act, run_task_conn, run_rest_conn to call clear_warnings() at entry and use get_warnings() at FirstLevelResult construction; remove local warnings list threading" />
    <item priority="P1" target_mode="implement" description="T5: Add ToolVersionError to exceptions.py; update runtime.py probe_tool_versions() to raise ToolVersionError on version mismatch; update run_first_level.py to map ToolVersionError to exit 4" />
  </action_items>
</brainstorm_report>
