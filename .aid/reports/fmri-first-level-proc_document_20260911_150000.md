<document_report>
  <meta project="fmri-first-level-proc" mode="document" timestamp="2026-09-11T15:00:00Z" />
  <files_updated>
    <file path="README.md" changes="Comprehensive rewrite: Python version corrected to >=3.12; programmatic usage example updated to list[ResolvedConfig]/DISPATCH API; fmri-first-level-proc set as primary CLI entry point with run-first-level noted as deprecated alias; added exception hierarchy diagram; added exit code table; added new-feature descriptions for PSC scaling, stat_buckets extraction, warning accumulator, BIDS discovery, processing DAG, and runtime validation; added public exports list and warning-accumulator API example; added Runtime Validation section.">
      <type>readme</type>
    </file>
    <file path="INPUT_SPECIFICATION.md" changes="Comprehensive rewrite: task_act extraction section rewritten for the stat_buckets API (replacing the removed extract/extract_labels/extract_stat fields); scale_to_psc field documented for all three analysis types; new output files documented (PSC-scaled NIfTI, mean NIfTI, per-stat-type bucket NIfTIs and index JSONs, bucket_stats master index JSON); BIDS-format timing file (_events.tsv) documented as the preferred format alongside legacy CSV (deprecated, removal in v4.0.0) with content-authoritative detection logic; added BIDS Input Discovery section (derivatives_dirs, slot definitions, discovery rules); added Tools Lockfile section; added Runtime Validation section (AFNI binary preflight, version lock checks); added Exit Codes table; added Exception Hierarchy section.">
      <type>input_spec</type>
    </file>
    <file path="fmri_first_level_proc/first_level_utils.py" changes="Added docstrings for get_warnings(), clear_warnings(), and the FirstLevelResult dataclass (including attribute descriptions). No functional code changed.">
      <type>docstring</type>
    </file>
    <file path="AID_LOG.md" changes="Updated Section 3 model table to reflect current model tiers used this development cycle (Claude Opus 4 / Opus 4.6; Claude Sonnet 4 / Sonnet 4.6 / Sonnet 5). Added missing Clean workflow stage to Section 4 (was present in the template but omitted from this project's copy). Appended v3.1.0 Version History entry summarizing the combined v3.0.0-scope infrastructure work and v3.1.0-scope feature work (v3.0.0 was never published as a standalone version). Remediated a Tier 2 LLM-attribution finding: renamed the Section 3 table's 'Role' column header to 'Function' per explicit user decision (security gate flagged 'Role' as a role-noun pattern near Claude/LLM references).">
      <type>aid_log</type>
    </file>
    <file path=".aid/project_claude.md" changes="Updated sanitized project structure to include the four new modules added during the v3.0.0/v3.1.0 development cycle (bids.py, checkpoint.py, exceptions.py, runtime.py) and tools.lock.yaml, which were missing from the prior snapshot. Verified no local paths, sandbox paths, or usernames present (sanitized copy of project CLAUDE.md).">
      <type>readme</type>
    </file>
  </files_updated>
  <aid_log>
    <status>updated</status>
    <sections_modified>Section 3 (Tools Used), Section 4 (Development Workflow), Version History</sections_modified>
  </aid_log>
  <coverage>
    <public_functions_documented>all public symbols in scope/total</public_functions_documented>
    <classes_documented>1/1 (FirstLevelResult)</classes_documented>
    <modules_with_docstrings>10/10</modules_with_docstrings>
  </coverage>
  <security_gate>
    <dispatched>5</dispatched>
    <aggregation>union-with-dedup by (file, line, pattern_category)</aggregation>
    <findings_surfaced>1</findings_surfaced>
    <finding detail="Tier 2 LLM-attribution: 'Role' column header in AID_LOG.md Section 3 table matched the role-noun-near-Claude pattern. Surfaced for explicit user decision per doctrine (no auto-remediate, no auto-exempt)." resolution="User selected: rename column header to 'Function'. Applied and verified via grep (zero remaining 'Role' matches in AID_LOG.md)." />
    <clean_files>fmri_first_level_proc/first_level_utils.py, README.md, INPUT_SPECIFICATION.md, .aid/project_claude.md</clean_files>
  </security_gate>
  <summary>Exhaustive documentation sweep completed for the v3.1.0 release, exceeding the brainstorm's non-exhaustive T4 minimum scope. README.md and INPUT_SPECIFICATION.md were fully rewritten to reflect current codebase state (stat_buckets extraction API, scale_to_psc, BIDS discovery and timing-file acceptance, processing DAG, runtime validation, exception hierarchy, exit codes). Three missing docstrings were added in first_level_utils.py. AID_LOG.md and .aid/project_claude.md were brought current. Security Gate (N=5 agents) found zero PII/PHI issues; one Tier 2 LLM-attribution finding was surfaced, adjudicated by the user, and remediated. Documentation is now consistent with the codebase and ready for /publish.</summary>
</document_report>
