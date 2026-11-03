<document_report>
  <meta project="fmri-first-level-proc" mode="document" timestamp="2026-11-02T13:20:51Z" />
  <files_updated>
    <file path="INPUT_SPECIFICATION.md" changes="Full rewrite to the 4.0.0 contract: closed schema and validation order, global-only keys (ConfigError), run model (Mode A/B, run_labels/run_lengths, run sets K_supplied/S_pre/K_model/S_final), every block field per type, HRF models, contrast grammar and label integrity, rest_conn backends and residual modes, smoothing, input file formats (events schemes, onset validation and timing_errors.json schema, motion column contract, tissue, template, packaged lockfile), Power FD censoring and run exclusion, trial estimability floors, DOF definitions (including the dry_run_aborted_censoring upper-bound note), PSC, parcel extraction and ROI QC, connectivity and output naming, BIDS discovery, every output file with final/intermediate class, sub-brick identifier files, QC summary schema with scope notes, warning-code table, new Stage Reuse and Reruns section, runtime validation (19 binaries, version policy), exit codes, CLI, programmatic API, exception hierarchy, known limitations, references. Removes stale enorm censoring text, run-first-level alias, repository-root lockfile and 13-run caps.">
      <type>input_spec</type>
    </file>
    <file path="README.md" changes="Rewritten for 4.0.0 at similar length: analyses, key features, prerequisites (AFNI on PATH, new dependency minimums), quick start, motion and events contracts, frozen primary outputs, CLI, exit codes, exception hierarchy, programmatic usage, runtime validation against the packaged lockfile, stage reuse and reruns (remove_previous scope, path-only scan hashing), corrected sequenced-backend citation framing, references. No development-process references.">
      <type>readme</type>
    </file>
    <file path="CHANGELOG.md" changes="New file. 4.0.0 entry (Unreleased) with Breaking changes, Added, Changed, Fixed (stat_buckets extraction) and Removed (run-first-level script, legacy extraction keys, six first_level_utils argparse helpers, get_3dinfo_properties orient/spacing keys, template_path discovery, four retired warning codes, 3dNetCorr runtime dependency); each claim checked against the v3.1.0 tag and current source.">
      <type>readme</type>
    </file>
    <file path="example_config.yaml" changes="Comment-only and placeholder updates: global-only keys are a ConfigError, tr must match header TR, template_path placeholder with requirement note, condition labels match trial_type or CONDITION, smoothed index JSONs are smoothed siblings while parcel CSVs are unsmoothed, notch filter affects FD censoring only, keep_run_res_dtseries residual-mode semantics.">
      <type>inline_comment</type>
    </file>
    <file path="AID_LOG.md" changes="Section 3 table converted to the template's two-column Model | Tasks form (Role/Function column removed), Opus 5.5 added, tasks updated with tool-framing language as approved by the user; closing sentence aligned with the template. Section 6 gains the Code quality reviews bullet. Version History v2.5.0 entry: citation correction only (interpolate-before-filter ordering per Power et al. 2014 and Ciric et al. 2017, linear NTRP, nuisance regressors filtered at the same passband per Hallquist et al. 2013), kept by user decision; no new Version History entry authored.">
      <type>aid_log</type>
    </file>
    <file path=".aid/project_claude.md" changes="Sanitized copy refreshed to the 4.0.0 structure tree (22 modules, packaged lockfile, CHANGELOG, AID_LOG, .aid/); local-instruction line and downstream-consumer reference remain removed.">
      <type>aid_log</type>
    </file>
    <file path="CLAUDE.md" changes="Project Structure block updated to the 4.0.0 layout (local-only file; first line and consumer reference unchanged), by user decision.">
      <type>readme</type>
    </file>
    <file path=".aid/reports/fmri-first-level-proc_brainstorm_20260825_185436.md" changes="Line 41: private downstream repository name replaced with a generic description.">
      <type>aid_log</type>
    </file>
    <file path=".aid/reports/fmri_first_level_proc_test_20260501_140346.md" changes="Line 52: Ciric et al. (2017) PMID corrected from 30446748 to 28302591.">
      <type>aid_log</type>
    </file>
    <file path=".aid/reports/fmri_first_level_proc_document_20260501_143429.md" changes="Line 11: same Ciric et al. (2017) PMID correction, by user decision.">
      <type>aid_log</type>
    </file>
    <file path="fmri_first_level_proc/task_conn_first_level.py" changes="Module docstring FINAL OUTPUTS now lists {pre}_concat_LSS_index.json and {pre}_concat_bseries_{cond}_index.json, and notes smoothed index siblings.">
      <type>docstring</type>
    </file>
    <file path="fmri_first_level_proc/first_level_config.py" changes="The from __future__ import was moved below the module docstring so the existing docstring is recognized as the module docstring (__doc__ was previously None); no other change.">
      <type>docstring</type>
    </file>
    <file path="fmri_first_level_proc/checkpoint.py" changes="One-line docstrings added to OutputRecord, StagedRecord, CompletionRecord, RetiredRecord and LedgerHistory.">
      <type>docstring</type>
    </file>
    <file path="fmri_first_level_proc/runsets.py" changes="One-line docstrings added to the RunSets properties k_supplied, s_pre, k_model, s_final, input_mode and tr.">
      <type>docstring</type>
    </file>
  </files_updated>
  <aid_log>
    <status>updated</status>
    <sections_modified>3. Tools Used; 6. Audit Trail; Version History (v2.5.0 citation correction only)</sections_modified>
  </aid_log>
  <coverage>
    <public_functions_documented>152/201</public_functions_documented>
    <classes_documented>26/26</classes_documented>
    <modules_with_docstrings>22/22</modules_with_docstrings>
  </coverage>
  <security_gate>
    <run index="1" status="invalid">Dispatched with paraphrased rather than verbatim scan patterns and exemptions; its two author-header flags arose from a narrowed exemption and its subj001 placeholder flag was not raised under the verbatim rules. Not used for adjudication.</run>
    <run index="2" status="clean">Five agents, patterns and exemptions verbatim from CONVENTIONS.md, twelve files: zero PII, PHI, Tier 1 or Tier 2 violations (5/5). Files edited after this run (.aid/project_claude.md, .aid/reports/fmri_first_level_proc_document_20260501_143429.md) were re-scanned with the verbatim regexes: clean.</run>
  </security_gate>
  <summary>User-facing documentation now describes the 4.0.0 contract as implemented, verified against current source and the v3.1.0 tag. The 49 undocumented public functions are all one-line path builders in names.py, left undocumented by user decision because the module docstring states their shared convention. Two functional gaps were observed by code reading (not reproduced) and are routed to /implement below; they also call the completeness of the 4.0.0 error-path test coverage into question, so publication should wait for their resolution.</summary>
  <action_items>
    <item priority="P1" target_mode="implement" description="Enforce required input paths during config resolution: a task or rest block whose mandatory slots (scan, motion, events for task; scan, motion, CSF, WM for rest) remain unresolved after explicit paths and BIDS discovery should raise ConfigError or InputError (exit 2). Currently build_runsets calls list(config.run_labels) on None, raising TypeError (exit 1, unexpected error). v3.1.0 enforced this with mandatory-slot InputError checks." />
    <item priority="P1" target_mode="implement" description="Emit a graded warning when a task_conn connectivity contrast is skipped, both when calc_conn is null with contrasts configured and when a referenced condition produced no connectivity output; currently the skip is silent." />
  </action_items>
</document_report>
