<implement_report>
  <meta project="fmri-first-level-proc" mode="implement" submodule="build" timestamp="2026-11-02T14:55:56Z" />
  <spec_ref>fmri-first-level-proc_implement_plan_20261102_142625.md</spec_ref>
  <changes_applied>
    <change id="C1" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/exceptions.py" lines_changed="19" />
      </files_modified>
      <notes>exit_code(exc) added as specified.</notes>
    </change>
    <change id="C2" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_config.py" lines_changed="~420" />
      </files_modified>
      <notes>Validation split into global schema, per-block pass 1, global values and per-block values helpers (shared with the per-block API). Numeric checks use numbers.Real/numbers.Integral so numpy scalars passed as overrides are accepted. scale_to_psc: null and roi_zero_handling: null now resolve to their documented defaults (previously null made scale_to_psc false).</notes>
    </change>
    <change id="C3" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_config.py" lines_changed="~25" />
      </files_modified>
      <notes>Contrasts are parsed in resolve_config (without a logger, so the zero-coefficient warning is logged once, by the pipeline). The ConfigError for task_conn contrasts with calc_conn null is raised during block validation (_validate_connectivity) rather than in resolve_config; this is earlier than specified and has the same effect.</notes>
    </change>
    <change id="C4" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/bids.py" lines_changed="~40" />
      </files_modified>
      <notes>As specified.</notes>
    </change>
    <change id="C5" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_config.py" lines_changed="~150" />
      </files_modified>
      <notes>Resolution order: discovery merge, run-label resolution, alignment of discovered slots, Mode A/B checks, required inputs, contrast parsing, template checks. Alignment is skipped for task Mode B, where singular/plural conflicts are reported by the mode checks.</notes>
    </change>
    <change id="C6" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_config.py" lines_changed="6" />
      </files_modified>
      <notes>As specified.</notes>
    </change>
    <change id="C7" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_config.py" lines_changed="~120" />
        <file path="fmri_first_level_proc/__init__.py" lines_changed="5" />
      </files_modified>
      <notes>The raw-string duplicate (out_dir, out_file_pre) check was removed from validate_config; the normalized cross-block collision check runs in load_and_validate and load_and_validate_blocks after resolution. load_and_validate_blocks records any exception per block (not only FmriFirstLevelError), so an unexpected error in one block does not stop the others.</notes>
    </change>
    <change id="C8" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/runsets.py" lines_changed="~45" />
      </files_modified>
      <notes>As specified.</notes>
    </change>
    <change id="C9" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/events.py" lines_changed="~45" />
      </files_modified>
      <notes>The duplicate-trial check runs on the assembled valid rows of both modes, before build_event_table returns.</notes>
    </change>
    <change id="C10" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_conn_first_level.py" lines_changed="~12" />
      </files_modified>
      <notes>As specified.</notes>
    </change>
    <change id="C11" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/names.py" lines_changed="5" />
        <file path="fmri_first_level_proc/nuisance.py" lines_changed="~40" />
        <file path="fmri_first_level_proc/rest_conn_first_level.py" lines_changed="~25" />
      </files_modified>
      <notes>Prepared copies are written for every supplied run (used by the DOF dry run) and listed as outputs for S_pre runs only, so copies of excluded runs stay in staging. Residual-stage derived_files now hash the prepared copies; derived_values keep the raw paths for provenance. Existing rest_conn outputs rerun once because stage hashes change.</notes>
    </change>
    <change id="C12" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_conn_first_level.py" lines_changed="~45" />
      </files_modified>
      <notes>conn_listed is read from the connectivity stage's recorded outputs, which exist for both executed and reused stages.</notes>
    </change>
    <change id="C13" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/qc.py" lines_changed="1" />
        <file path="fmri_first_level_proc/engine.py" lines_changed="~100" />
      </files_modified>
      <notes>As specified. The failure summary is written atomically (temporary file, then os.replace).</notes>
    </change>
    <change id="C14" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_act_first_level.py" lines_changed="~15" />
        <file path="fmri_first_level_proc/task_conn_first_level.py" lines_changed="~15" />
        <file path="fmri_first_level_proc/rest_conn_first_level.py" lines_changed="~15" />
      </files_modified>
      <notes>Pre-engine steps are tracked as {type}-runtime-check, {type}-contrast-validation (task), {type}-path-checks (rest), {type}-run-sets and {type}-template-check; engine steps and stages report their own labels.</notes>
    </change>
    <change id="C15" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/inputs.py" lines_changed="86 (new)" />
        <file path=".gitignore" lines_changed="1" />
      </files_modified>
      <notes>.gitignore uses a whitelist, so the new module was added to it; without this entry inputs.py would not be published and the published CLI would fail to import.</notes>
    </change>
    <change id="C16" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/run_first_level.py" lines_changed="~150" />
      </files_modified>
      <notes>Config-invalid blocks get a failure summary with provenance from the CLI's runtime check (the spec passed None; L6 allows provenance when known). run_first_level no longer re-exports load_and_validate or the exception classes; sibling projects import these from the package root and exceptions module.</notes>
    </change>
    <change id="C17" status="done" user_decision="n/a">
      <files_modified>
        <file path="INPUT_SPECIFICATION.md" lines_changed="~90" />
        <file path="README.md" lines_changed="~15" />
        <file path="CHANGELOG.md" lines_changed="~30" />
        <file path="example_config.yaml" lines_changed="~20" />
      </files_modified>
      <notes>All five documentation inaccuracies from the audit are corrected, alongside the new behavior.</notes>
    </change>
  </changes_applied>
  <summary>
    <total_changes>17</total_changes>
    <completed>17</completed>
    <skipped>0</skipped>
    <blocked>0</blocked>
  </summary>
  <verification_performed>Compilation and import of every modified module, a static undefined-name scan of first_level_config.py, a YAML parse of example_config.yaml, and an em-dash scan of edited files. No tests were run (per this skill).</verification_performed>
  <expected_test_impact>Existing tests likely to need re-expression as obsolete-test: CLI exit-code tests that monkeypatch run_first_level.load_and_validate (the CLI now calls load_and_validate_blocks); tests expecting the raw duplicate-pair ConfigError from validate_config; QC tests asserting exact qc_summary key sets (run_status is added); bids tests that relied on prefix glob matching; config tests expecting empty or None-containing Mode A path lists, string booleans, or null scale_to_psc to be accepted; rest_conn tests that inspect residual-stage derived_files or tissue -ort paths.</expected_test_impact>
  <next_steps>Recommended: run /test to validate all changes, using the testing note in the tech spec (error-path matrix through load_and_validate, load_and_validate_blocks and main(); discovery-through-resolve; events duplicates and negative durations; non-finite motion and tissue; rest multi-column tissue; run_status on success and failure; task_conn skipped-contrast warning and rerun behavior).</next_steps>
</implement_report>
