<document_report>
  <meta project="fmri_first_level_proc" mode="document" timestamp="2026-05-01T14:34:29Z" />

  <files_updated>
    <file path="INPUT_SPECIFICATION.md" changes="Added use_sequenced_bandpass row to rest_conn Optional Fields table (default False, semantics, interaction with bandpass and keep_run_res_dtseries). Added bullet under Output Files > rest_conn describing the per-run intermediate directory and its lifecycle.">
      <type>input_spec</type>
    </file>
    <file path="README.md" changes="Updated the Resting-State Connectivity feature bullet to mention the optional sequenced denoising path (separate BOLD and nuisance bandpass filtering per Ciric et al. 2017) and its DOF-cost benefit.">
      <type>readme</type>
    </file>
    <file path="fmri_first_level_proc/rest_conn_first_level.py" changes="Added module-level docstring entries introducing _generate_run_residual_simultaneous and _generate_run_residual_sequenced as the two backends; brief references to Ciric et al. 2017 (PMID 28302591) and Hallquist et al. 2013 for the design rationale.">
      <type>docstring</type>
    </file>
    <file path="AID_LOG.md" changes="Appended v2.5.0 entry to Version History describing the sequenced denoising path, new utility functions, test-suite expansion (55 new tests; 515 total passing), and documentation updates.">
      <type>aid_log</type>
    </file>
    <file path="CLAUDE.md" changes="Fixed file extension typo in Project Structure (INPUT_SPECIFICATION.toml -> INPUT_SPECIFICATION.md).">
      <type>readme</type>
    </file>
    <file path=".aid/project_claude.md" changes="Same typo fix mirrored in the sanitized project_claude.md.">
      <type>readme</type>
    </file>
  </files_updated>

  <aid_log>
    <status>updated</status>
    <sections_modified>Version History (v2.5.0 appended)</sections_modified>
  </aid_log>

  <coverage>
    <public_functions_documented>n_a/n_a</public_functions_documented>
    <classes_documented>n_a/n_a</classes_documented>
    <modules_with_docstrings>n_a/n_a</modules_with_docstrings>
  </coverage>

  <summary>Documentation aligned with v2.5.0 (sequenced denoising path). User-facing surfaces (README), LLM-oriented spec (INPUT_SPECIFICATION.md), AI Disclosure Log (AID_LOG.md), and rest_conn module-level docstring updated. Four session reports (brainstorm, implement-plan, implement-build, test) copied to .aid/reports/ with PII screening passed. Two minor typo fixes in CLAUDE.md and its sanitized mirror. After document-mode completion, a global collaboration-discipline rule was added to global memory (filesystem-scope authority / no self-grants) following two within-session hook-block violations; the rule is auto-loaded across all future sessions and projects via the existing global memory import chain.</summary>
</document_report>
