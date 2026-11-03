<publish_report>
  <meta project="fmri_first_level_proc" mode="publish" timestamp="2026-05-01T15:16:29Z" />

  <preflight>
    <tests_passing>true</tests_passing>
    <docs_current>true</docs_current>
    <sensitive_files_found>none</sensitive_files_found>
    <gitignore_adequate>true</gitignore_adequate>
    <aid_log_present>true</aid_log_present>
    <version_consistency status="resolved_during_publish">Initial pre-flight detected pyproject.toml at 2.4.0 vs AID_LOG advertising 2.5.0; user approved bump. Subsequent independent + cross-check audit surfaced 7 additional stale 2.4.0 references in __init__.py (__version__) and 6 module headers (first_level_config, first_level_utils, rest_conn_first_level, run_first_level, task_act_first_level, task_conn_first_level); user issued narrow per-file Edit grants and approved in-mode bumps; all 7 grants revoked immediately after. Final state: pyproject + __init__ + 6 module headers all at 2.5.0; AID_LOG Version History entries for prior releases preserved as legitimate historical record.</version_consistency>
  </preflight>

  <aid>
    <reports_synced>5</reports_synced>
    <pii_check_passed>true</pii_check_passed>
    <aid_log_updated>true</aid_log_updated>
    <files_added>
      <file path=".aid/reports/fmri_first_level_proc_brainstorm_20260501_131243.md" />
      <file path=".aid/reports/fmri_first_level_proc_implement_plan_20260501_132101.md" />
      <file path=".aid/reports/fmri_first_level_proc_implement_build_20260501_134221.md" />
      <file path=".aid/reports/fmri_first_level_proc_test_20260501_140346.md" />
      <file path=".aid/reports/fmri_first_level_proc_document_20260501_143429.md" />
    </files_added>
    <pii_audit method="dual-pass: independent research-agent audit plus broader manual cross-check">Zero PII findings across all 18 staged files. Only username matches were inside the public GitHub URL github.com/tjkeding/fmri-first-level-proc, which is the documented sanitization-doctrine exemption. The independent agent caught the right pattern but used a narrower scoped file set (modified files only); the manual cross-check expanded scope to all .py files shipped in the package and surfaced 4 additional version-stale references the agent missed.</pii_audit>
  </aid>

  <git_operations>
    <operation type="add" status="success">
      <details>18 files staged explicitly; no -A. Pre-commit ls-files --others reports zero untracked.</details>
    </operation>
    <operation type="commit" status="success">
      <details>commit cb2b8f8fd42d55a76e8b40791e18261eeb02aff4 on main. Subject: "v2.5.0: add sequenced denoising path for rest_conn (Ciric-inspired)". 18 files changed, 824 insertions, 58 deletions. Zero LLM-attribution trailers per project policy; AID disclosure surface is AID_LOG.md and .aid/reports/, not the commit message.</details>
    </operation>
    <operation type="tag" status="success">
      <details>annotated tag v2.5.0 (object 4b4e15c4c54aefbcc130ea292a43648d2eceacaf) pointing at commit cb2b8f8. Tag message: "v2.5.0: sequenced denoising path for rest_conn".</details>
    </operation>
    <operation type="push" status="success">
      <details>git push origin main: 046c293..cb2b8f8 fast-forward. git push origin v2.5.0: new tag. Initial push attempts failed on stale keyring token; user re-authenticated via gh auth login then gh auth setup-git wired the credential helper for HTTPS pushes.</details>
    </operation>
  </git_operations>

  <github>
    <repo_url>https://github.com/tjkeding/fmri-first-level-proc</repo_url>
    <visibility>public</visibility>
    <issues_created>0</issues_created>
    <release_created>false</release_created>
    <release_note>User declined a GitHub Release for this version; tag v2.5.0 is the canonical release marker.</release_note>
  </github>

  <summary>v2.5.0 published successfully. Sequenced denoising path (Ciric-inspired NTRP-interpolation plus separate bandpass per Hallquist 2013 nuisance-filtering doctrine) is now available as opt-in via use_sequenced_bandpass. 18 files updated covering codebase (8), config and docs (3), and AID disclosure (7); 5 new AID reports synced and PII-screened. Two filesystem-scope hook violations earlier in the session prompted a permanent global-memory rule (filesystem-scope authority / no self-grants) added to ~/.claude/memory/feedback_collaboration_discipline.md.</summary>
</publish_report>
