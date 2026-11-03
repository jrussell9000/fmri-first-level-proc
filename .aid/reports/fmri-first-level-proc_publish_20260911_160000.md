<publish_report>
  <meta project="fmri-first-level-proc" mode="publish" timestamp="2026-09-11T16:00:00Z" />
  <preflight>
    <tests_passing>true</tests_passing>
    <docs_current>true</docs_current>
    <sensitive_files_found>none</sensitive_files_found>
    <gitignore_adequate>true</gitignore_adequate>
    <aid_log_present>true</aid_log_present>
  </preflight>
  <aid>
    <reports_synced>24</reports_synced>
    <pii_check_passed>true</pii_check_passed>
    <aid_log_updated>true</aid_log_updated>
    <files_added>
      fmri-first-level-proc_brainstorm_20260824_140104.md
      fmri-first-level-proc_brainstorm_20260825_185436.md
      fmri-first-level-proc_brainstorm_20260911_142835.md
      fmri-first-level-proc_document_20260911_150000.md
      fmri-first-level-proc_implement_build_20260825_192525.md
      fmri-first-level-proc_implement_build_20260825_214115.md
      fmri-first-level-proc_implement_build_20260826_195800.md
      fmri-first-level-proc_implement_build_20260911_143823.md
      fmri-first-level-proc_implement_plan_20260819_145136.md
      fmri-first-level-proc_implement_plan_20260825_190018.md
      fmri-first-level-proc_implement_plan_20260825_213459.md
      fmri-first-level-proc_implement_plan_20260826_195500.md
      fmri-first-level-proc_implement_plan_20260911_143722.md
      fmri-first-level-proc_test_20260825_194710.md
      fmri-first-level-proc_test_20260826_123720.md
      fmri-first-level-proc_test_20260826_195900.md
      fmri_first_level_proc_brainstorm_20260812_181523.md
      fmri_first_level_proc_brainstorm_20260813_125601.md
      fmri_first_level_proc_brainstorm_20260818_150000.md
      fmri_first_level_proc_brainstorm_20260824_120000.md
      fmri_first_level_proc_cr_20260813_083501.md
      fmri_first_level_proc_implement_build_20260824_121500.md
      fmri_first_level_proc_implement_plan_20260824_121000.md
      fmri_first_level_proc_test_20260824_122900.md
    </files_added>
  </aid>
  <security_gate>
    <agents_dispatched>5</agents_dispatched>
    <aggregation>union-with-dedup by (file, line, pattern_category)</aggregation>
    <unique_violations_found>5</unique_violations_found>
    <false_positives_dismissed>1</false_positives_dismissed>
    <violations_remediated>5</violations_remediated>
    <remediation_details>
      <file path=".aid/reports/fmri-first-level-proc_test_20260825_194710.md" lines="12-13" category="pii" action="Replaced /tmp/ absolute path and UUID nonce with placeholder tokens" />
      <file path=".aid/reports/fmri_first_level_proc_brainstorm_20260311_220000.md" line="4" category="pii" action="Replaced participant ID sub-00CY2MDM with sub-XXXXXXXX" />
      <file path=".aid/reports/fmri_first_level_proc_test_20260824_122900.md" line="11" category="pii" action="Replaced UUID nonce with redacted" />
    </remediation_details>
    <false_positive_details>
      <finding id="SG-4" file="AID_LOG.md" category="tier2" description="Flagged Function column header as Role column header pattern. Dismissed: column reads Function (user's explicit remediation from /document), not Role. 4/5 agents correctly did not flag this." />
    </false_positive_details>
    <post_remediation_status>clean</post_remediation_status>
  </security_gate>
  <git_operations>
    <operation type="add" status="success">
      <details>44 files staged (15 modified, 29 new)</details>
    </operation>
    <operation type="commit" status="success">
      <details>0ad0445 - v3.1.0: major infrastructure and feature release</details>
    </operation>
    <operation type="tag" status="success">
      <details>v3.1.0 lightweight tag created</details>
    </operation>
    <operation type="push" status="success">
      <details>cb2b8f8..0ad0445 main -> main; v3.1.0 -> v3.1.0</details>
    </operation>
  </git_operations>
  <github>
    <repo_url>https://github.com/tjkeding/fmri-first-level-proc</repo_url>
    <visibility>public</visibility>
    <issues_created>0</issues_created>
  </github>
  <summary>v3.1.0 published successfully. 44 files committed and pushed to GitHub with tag v3.1.0. Security gate (N=5 agents) passed after remediating 5 PII violations across 3 .aid/reports files. 24 AID reports synced from mode history directories. AID_LOG.md Version History updated. No LLM attribution in commit message, tag, or non-AID files.</summary>
</publish_report>
