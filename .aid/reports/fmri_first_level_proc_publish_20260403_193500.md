<?xml version="1.0" encoding="UTF-8"?>
<publish_report>
  <meta project="fmri_first_level_proc" mode="publish" timestamp="2026-04-03T19:35:00Z" />
  <preflight>
    <tests_passing>true (460 passed, 0 failures)</tests_passing>
    <docs_current>true (document pass completed this session)</docs_current>
    <sensitive_files_found>none</sensitive_files_found>
    <gitignore_adequate>true (whitelist approach)</gitignore_adequate>
    <aid_log_present>true</aid_log_present>
  </preflight>
  <aid>
    <reports_synced>1 (fmri_first_level_proc_document_20260403_191937.md)</reports_synced>
    <pii_check_passed>true (7-category exhaustive scan, zero findings)</pii_check_passed>
    <pii_remediation>1 file: absolute path removed from fmri_first_level_proc_implement_build_20260311_195653.md</pii_remediation>
    <aid_log_updated>true (v2.4.0-post1 entry added)</aid_log_updated>
    <files_added>
      - .aid/reports/fmri_first_level_proc_document_20260403_191937.md (new)
      - .aid/reports/fmri_first_level_proc_implement_build_20260311_195653.md (PII fix)
      - AID_LOG.md (version history entry)
    </files_added>
  </aid>
  <git_operations>
    <operation type="add" status="success">
      <details>6 files staged: rest_conn_first_level.py, run_first_level.py, first_level_utils.py, AID_LOG.md, 2 .aid/ reports</details>
    </operation>
    <operation type="commit" status="success">
      <details>046c293 — fix(rest_conn): correct DOF pre-flight regressor count for polort -1; add run_first_level docstring</details>
    </operation>
    <operation type="push" status="success">
      <details>e2bca93..046c293 main -> main</details>
    </operation>
  </git_operations>
  <github>
    <repo_url>https://github.com/tjkeding/fmri-first-level-proc</repo_url>
    <visibility>public</visibility>
    <issues_created>0</issues_created>
  </github>
  <summary>Published fix for DOF pre-flight regressor overcount (polort -1), run_first_level docstring, utils formatting, and AID artifact updates. 460 tests passing, PII clean.</summary>
</publish_report>
