<document_report>
  <meta project="fmri-first-level-proc" mode="document" timestamp="2026-11-02T23:15:41Z" />
  <files_updated>
    <file path="fmri_first_level_proc/run_first_level.py" changes="Module docstring: the CLI validates and resolves blocks through load_and_validate_blocks (previously named load_and_validate).">
      <type>docstring</type>
    </file>
    <file path="fmri_first_level_proc/first_level_config.py" changes="Module docstring Public API list: added load_and_validate_blocks and BlockResolution; noted that load_and_validate raises on the first invalid block.">
      <type>docstring</type>
    </file>
    <file path="fmri_first_level_proc/engine.py" changes="Module docstring: finish writes a run_status record; run_with_status and write_failure_qc write a failure summary (analysis_type, run_status, provenance only) before re-raising.">
      <type>docstring</type>
    </file>
    <file path="INPUT_SPECIFICATION.md" changes="Three places said a warning code is 'raised' (RUN_FAILED, DERIV_RUN_BOUNDARY, DISCOVERY_COLLISION); reworded to 'emits the ... warning', since these are graded warnings, not exceptions. All other sections changed in the boundary-audit round (validation order, value rules, run_status schema, exit codes, --dry-run, per-block API, BIDS discovery, events, motion and tissue files, CONTRAST_DROPPED) were verified against current source; no further discrepancies found.">
      <type>input_spec</type>
    </file>
    <file path="CLAUDE.md" changes="Project Structure tree: added fmri_first_level_proc/inputs.py.">
      <type>inline_comment</type>
    </file>
    <file path=".aid/project_claude.md" changes="Project Structure tree: added fmri_first_level_proc/inputs.py (sanitized copy kept in sync with CLAUDE.md).">
      <type>aid_log</type>
    </file>
    <file path="AID_LOG.md" changes="Section 2 and Section 4 item 6: 'authoring' replaced by 'drafting' (standing rule: tool-use framing only). Section 4 item 4 and its key-properties bullet: the inaccurate 'test-first' claims replaced with a description of the actual practice (tests designed after each implementation round, failures classified before any edit, run counts receipt-verified from August 2026 onward). Section 4 item 2: added the input-boundary audit. Section 5: added item (f) on the researcher's role in the audit.">
      <type>aid_log</type>
    </file>
    <file path="fmri-first-level-proc_test_20261102_183001.md, fmri-first-level-proc_test_20261102_213034.md" changes="Security-gate remediation: four UUID-format receipt nonces replaced with session-1 to session-4.">
      <type>inline_comment</type>
    </file>
  </files_updated>
  <aid_log>
    <status>updated</status>
    <sections_modified>2 (Scope), 4 (Development Workflow), 5 (Human Oversight). Sections 1, 3, 6, 7 and Version History unchanged.</sections_modified>
  </aid_log>
  <aid_directory>
    <status>.aid/ and .aid/reports/ present; .aid/project_claude.md updated. Report syncing into .aid/reports/ is performed by /publish (not by this skill); no 4.0.0-cycle reports have been synced yet.</status>
  </aid_directory>
  <security_gate>
    <agents>5 (SG-1 to SG-5), combined PII/PHI and LLM-attribution, patterns and exemptions copied verbatim from CONVENTIONS.md</agents>
    <files_scanned>31: all documentation, AID artifacts, the 15 package modules modified in this session, and the 8 project-root reports created in this session</files_scanned>
    <findings>4 after union and deduplication, all PII-tier (UUID pattern): receipt nonces in the two test reports, reported by 4 of 5 agents. Remediated in place to session-1 to session-4 and re-scanned clean. No PHI, no Tier 1 and no Tier 2 attribution findings. The public GitHub URL username and the AID_LOG.md model disclosures were confirmed exempt.</findings>
  </security_gate>
  <coverage>
    <public_functions_documented>158/206</public_functions_documented>
    <classes_documented>28/28</classes_documented>
    <modules_with_docstrings>23/23</modules_with_docstrings>
  </coverage>
  <observations>
    <item>The shared AID_LOG template (the document skill's templates/AID_LOG_template.md) contains the same 'authoring' wording (lines 19 and 54) and the same 'test-first' claims (lines 50 and 59) corrected here; it was not edited (harness file).</item>
    <item>A stray AFNI log, 3dDeconvolve.err, sits in the project root. The whitelist .gitignore keeps it out of the repository; it was not deleted.</item>
  </observations>
  <summary>Documentation reflects the 4.0.0 contract after the boundary-audit round and the follow-up required-key fix. Three stale module docstrings and three warning-code wording errors were corrected. AID_LOG.md no longer uses authorship-implying language for tool-generated content, no longer claims a test-first workflow, and records the input-boundary audit and the researcher's role in it. The 48 undocumented public functions are one-line path builders in names.py, left undocumented by the user's earlier decision because the module docstring states their shared convention. The security gate is clean after remediation. Next steps: /publish (merge, tag, report sync and its own security gate).</summary>
</document_report>
