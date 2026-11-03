<test_report>
  <meta project="fmri_first_level_proc" mode="test" timestamp="2026-08-13T00:55:00Z" />

  <pre_design_run>
    <total>301</total>
    <passed>0</passed>
    <failed>0</failed>
    <errors>15</errors>
    <coverage_pct></coverage_pct>
    <failures>
      <failure test="test_config_edge_cases (collection)" file="tests/test_config_edge_cases.py" line="17">
        <error_type>ImportError</error_type>
        <message>cannot import name '_merge_global_into_block' from 'fmri_first_level_proc.first_level_config'</message>
        <traceback>ImportError: cannot import name '_merge_global_into_block'</traceback>
      </failure>
      <failure test="test_config_validation (collection)" file="tests/test_config_validation.py" line="9">
        <error_type>ImportError</error_type>
        <message>cannot import name 'build_namespace' from 'fmri_first_level_proc.first_level_config'</message>
        <traceback>ImportError: cannot import name 'build_namespace'</traceback>
      </failure>
      <failure test="test_error_paths (collection)" file="tests/test_error_paths.py" line="17">
        <error_type>ImportError</error_type>
        <message>cannot import name 'make_task_act_args' from 'tests.conftest'</message>
        <traceback>ImportError: cannot import name 'make_task_act_args'</traceback>
      </failure>
      <failure test="test_rest_conn_dof_skip (collection)" file="tests/test_rest_conn_dof_skip.py" line="5">
        <error_type>ImportError</error_type>
        <message>cannot import name 'make_rest_conn_args' from 'tests.conftest'</message>
        <traceback>ImportError: cannot import name 'make_rest_conn_args'</traceback>
      </failure>
      <failure test="test_rest_conn_pipeline (collection)" file="tests/test_rest_conn_pipeline.py" line="9">
        <error_type>ImportError</error_type>
        <message>cannot import name 'make_rest_conn_args' from 'tests.conftest'</message>
        <traceback>ImportError: cannot import name 'make_rest_conn_args'</traceback>
      </failure>
      <failure test="test_robust_survival (collection)" file="tests/test_robust_survival.py" line="16">
        <error_type>ImportError</error_type>
        <message>cannot import name 'make_task_act_args' from 'tests.conftest'</message>
        <traceback>ImportError: cannot import name 'make_task_act_args'</traceback>
      </failure>
      <failure test="test_sequenced_config (collection)" file="tests/test_sequenced_config.py" line="21">
        <error_type>ImportError</error_type>
        <message>cannot import name 'build_namespace' from 'fmri_first_level_proc.first_level_config'</message>
        <traceback>ImportError: cannot import name 'build_namespace'</traceback>
      </failure>
      <failure test="test_sequenced_dispatch (collection)" file="tests/test_sequenced_dispatch.py" line="24">
        <error_type>ImportError</error_type>
        <message>cannot import name 'make_rest_conn_args' from 'tests.conftest'</message>
        <traceback>ImportError: cannot import name 'make_rest_conn_args'</traceback>
      </failure>
      <failure test="test_sequenced_pipeline (collection)" file="tests/test_sequenced_pipeline.py" line="">
        <error_type>ImportError</error_type>
        <message>cannot import name 'make_rest_conn_args' from 'tests.conftest'</message>
        <traceback>ImportError: cannot import name 'make_rest_conn_args'</traceback>
      </failure>
      <failure test="test_sequenced_regression (collection)" file="tests/test_sequenced_regression.py" line="23">
        <error_type>ImportError</error_type>
        <message>cannot import name 'make_rest_conn_args' from 'tests.conftest'</message>
        <traceback>ImportError: cannot import name 'make_rest_conn_args'</traceback>
      </failure>
      <failure test="test_task_act_pipeline (collection)" file="tests/test_task_act_pipeline.py" line="9">
        <error_type>ImportError</error_type>
        <message>cannot import name 'make_task_act_args' from 'tests.conftest'</message>
        <traceback>ImportError: cannot import name 'make_task_act_args'</traceback>
      </failure>
      <failure test="test_task_conn_pipeline (collection)" file="tests/test_task_conn_pipeline.py" line="11">
        <error_type>ImportError</error_type>
        <message>cannot import name 'make_task_conn_args' from 'tests.conftest'</message>
        <traceback>ImportError: cannot import name 'make_task_conn_args'</traceback>
      </failure>
      <failure test="test_v230_regression (collection)" file="tests/test_v230_regression.py" line="35">
        <error_type>ImportError</error_type>
        <message>cannot import name 'make_task_conn_args' from 'tests.conftest'</message>
        <traceback>ImportError: cannot import name 'make_task_conn_args'</traceback>
      </failure>
      <failure test="test_v240_extract_raw_ptseries (collection)" file="tests/test_v240_extract_raw_ptseries.py" line="22">
        <error_type>ImportError</error_type>
        <message>cannot import name 'build_namespace' from 'fmri_first_level_proc.first_level_config'</message>
        <traceback>ImportError: cannot import name 'build_namespace'</traceback>
      </failure>
      <failure test="test_v240_pipeline_integration (collection)" file="tests/test_v240_pipeline_integration.py" line="35">
        <error_type>ImportError</error_type>
        <message>cannot import name 'make_task_act_args' from 'tests.conftest'</message>
        <traceback>ImportError: cannot import name 'make_task_act_args'</traceback>
      </failure>
    </failures>
  </pre_design_run>

  <failing_test_dispositions>
    <disposition test="(15 collection-error test modules, see pre_design_run above)" file="tests/*.py" classification="obsolete-test">
      <intended_contract>Each test module's fixtures/imports encode the v2.5.0 API surface (build_namespace, _merge_global_into_block, make_*_args factories, argparse.Namespace-based configs).</intended_contract>
      <current_test_claim>Imports named symbols that were renamed or removed by the v3.0.0 refactor (implement build report fmri_first_level_proc_implement_build_20260812_230500.md, changes C3/C8/C13).</current_test_claim>
      <evidence>first_level_config.py exports resolve_config (not build_namespace/_merge_global_into_block); conftest.py exports make_task_act_config/make_task_conn_config/make_rest_conn_config (not the _args variants), per C13.</evidence>
      <action>re-express: import renames, ResolvedConfig-based factory calls, resolve_config-based helper rewrites. All 15 modules re-expressed; see files_created/files_modified list below.</action>
    </disposition>

    <disposition test="115+ sites across 24 modified test files" file="tests/*.py" classification="obsolete-test">
      <intended_contract>Invalid input, insufficient DOF, missing tool output, and guard-path violations must produce a detectable, catchable error.</intended_contract>
      <current_test_claim>pytest.raises(SystemExit), some with exc_info.value.code == 1 assertions.</current_test_claim>
      <evidence>C1/C7 (implement build report) replaced all sys.exit(1) call sites with typed exceptions (ConfigError, InputError, ModelError, GuardError, ToolExecutionError, ToolUnavailableError) per fmri_first_level_proc/exceptions.py. compute_dof() signature dropped the exit_on_error parameter entirely (now always raises ModelError on dof &lt; 1).</evidence>
      <action>re-express: SystemExit -> the specific exception type raised by the exercised function (verified per-call-site against source, not assumed uniform per file — one initial mis-mapping in test_config_validation.py's test_atlas_mismatch_error, ConfigError vs the correct InputError from validate_template's atlas check, was caught by the post-design run and corrected). Postcondition strengthened: assertions now target the specific domain exception rather than the generic SystemExit.</action>
    </disposition>

    <disposition test="8 check_trial_survival fixture tests (test_qc_summary.py x3, test_utils_extended.py x2, test_v240_coverage_gaps.py x3) + test_utils_unit.py write_onset_file tests x2 + test_v230_regression.py::test_read_stim_data_returns_dataframe" file="tests/test_qc_summary.py, tests/test_utils_extended.py, tests/test_v240_coverage_gaps.py, tests/test_utils_unit.py, tests/test_v230_regression.py" classification="obsolete-test">
      <intended_contract>check_trial_survival and write_onset_file consume timing DataFrames using BIDS column names (trial_type, onset, duration); read_and_validate_stim_data / read_stim_data return BIDS-named DataFrames regardless of input file format.</intended_contract>
      <current_test_claim>Hand-constructed stim_df fixtures used legacy uppercase columns (CONDITION, ONSET, DURATION); one test asserted the legacy column-name list directly as the expected output of read_stim_data.</current_test_claim>
      <evidence>first_level_utils.py:496-593 (read_and_validate_stim_data, write_onset_file docstrings and bodies use lowercase BIDS names exclusively, per C6 in the implement build report). Discovered when the post-design run_suite surfaced KeyError('trial_type') and an explicit AssertionError diffing 'trial_type' against 'CONDITION'.</evidence>
      <action>re-express: fixture column names updated to trial_type/onset/duration; the one direct assertion updated to expect the BIDS name list. Postcondition preserved exactly (same trial-survival counts, same onset-file content), only the input/output column-naming convention changed.</action>
    </disposition>

    <disposition test="test_sequenced_dispatch.py::test_dispatch_skips_low_dof_run_in_both_branches" file="tests/test_sequenced_dispatch.py" classification="obsolete-test">
      <intended_contract>A run with insufficient DOF must be skipped before backend dispatch, in both the simultaneous and sequenced branches.</intended_contract>
      <current_test_claim>Local fake_compute_dof mock returned 0 for the low-DOF run instead of raising ModelError, so the real dispatch logic's except ModelError skip-path was never triggered — both runs were dispatched to the backend, failing the call_count==1 assertion.</current_test_claim>
      <evidence>rest_conn_first_level.py:420-430: `try: run_dof = compute_dof(...); skip_run.append(False) except ModelError: ... skip_run.append(True)`. compute_dof's v3.0.0 contract raises ModelError rather than returning a low-DOF sentinel.</evidence>
      <action>re-express: mock re-written to raise ModelError for the low-DOF run, matching the real function's contract. Postcondition (backend called exactly once, for the surviving run) unchanged.</action>
    </disposition>

    <disposition test="37 tests across test_censor_creation.py, test_error_paths.py, test_task_act_pipeline.py, test_task_conn_pipeline.py, test_v230_regression.py (x2, aligned), test_v240_extract_raw_ptseries.py, test_v240_pipeline_integration.py" file="fmri_first_level_proc/task_act_first_level.py, fmri_first_level_proc/task_conn_first_level.py" classification="product-bug">
      <intended_contract>write_stim_onset_files and run_first_level must consume the DataFrame returned by read_stim_data using the same column-naming convention that read_stim_data (via read_and_validate_stim_data) actually produces.</intended_contract>
      <current_test_claim>Tests call the real (unmocked) task_act_run / task_conn_run / write_stim_onset_files functions with real or realistically-mocked timing data; all fail with KeyError('CONDITION').</current_test_claim>
      <evidence>task_act_first_level.py lines 187, 188, 241, 736 and task_conn_first_level.py lines 188, 189, 198, 199, 201, 202, 246, 250, 254, 266, 346, 367, 374, 717, 778 all index stim_data['CONDITION'] / ['ONSET'] / ['DURATION'], but first_level_utils.py's read_and_validate_stim_data (C6) now returns BIDS column names (trial_type, onset, duration) unconditionally. The C6 utils-layer rename was not propagated to the C8 pipeline-module rewrite that consumes it.</evidence>
      <action>route-to-implement: rename all stim_data['CONDITION']/['ONSET']/['DURATION'] references to ['trial_type']/['onset']/['duration'] in task_act_first_level.py and task_conn_first_level.py at the line numbers cited above. NO test-side edit possible or appropriate; the tests correctly encode the intended (BIDS) contract.</action>
    </disposition>

    <disposition test="10 tests across test_utils_extended.py (5) and test_v240_coverage_gaps.py (5): file_path_exists, valid_string_list, valid_stat_type, valid_ave_type, valid_conn_type error paths" file="fmri_first_level_proc/first_level_utils.py" classification="product-bug">
      <intended_contract>dir_path_exists, file_path_exists, valid_string_list, valid_stat_type, valid_ave_type, and valid_conn_type raise argparse.ArgumentTypeError on invalid input (these remain legitimate argparse type-validators, used for --config-independent CLI-style value checks).</intended_contract>
      <current_test_claim>Calling these functions with invalid input raises NameError: name 'argparse' is not defined instead of argparse.ArgumentTypeError.</current_test_claim>
      <evidence>fmri_first_level_proc/first_level_utils.py's import block (lines 36-49) has no `import argparse`, yet lines 79, 145, 153, 162, 168, 176 reference argparse.ArgumentTypeError. The import was almost certainly dropped during the C7 sys.exit-migration pass under the (incorrect) assumption that argparse was entirely retired with the old per-analysis CLI.</evidence>
      <action>route-to-implement: add `import argparse` to fmri_first_level_proc/first_level_utils.py's import block. NO test-side edit possible or appropriate; the tests correctly encode the intended (ArgumentTypeError) contract, matching the many adjacent argparse.ArgumentTypeError tests in the same files that DO pass (those exercise call sites where the exception is constructed but the NameError is raised first only where `raise argparse.ArgumentTypeError(...)` is actually reached — i.e., every reachable raise site).</action>
    </disposition>
  </failing_test_dispositions>

  <design_phase>
    <tests_created>211</tests_created>
    <tests_modified>24</tests_modified>
    <files_created>
      <file path="tests/test_exceptions.py" test_count="24" coverage_target="Exception hierarchy (7 classes, inheritance) and run_first_level.main() exit-code mapping (0/1/2/3/4/5)" />
      <file path="tests/test_bids.py" test_count="27" coverage_target="build_bids_output_path entity ordering/sanitization, write_dataset_description BIDS 1.9.0 fields and no-op-if-exists, DiscoveredInputs defaults, discover_inputs single-path/list-path/collision/no-match behavior" />
      <file path="tests/test_checkpoint.py" test_count="30" coverage_target="DAG constants, append_ledger_entry/read_ledger round-trip and last-writer-wins, resolve_rerun_set cascade invalidation, auto_reconstruct_ledger artifact inference, compute_config_hash determinism" />
      <file path="tests/test_runtime.py" test_count="22" coverage_target="_parse_afni_version regex extraction, preflight_tool_environments collect-then-fail and 3-stage home discovery, probe_tool_versions strict-match/PLACEHOLDER-skip/mismatch/unparseable/subprocess-failure" />
      <file path="tests/test_graded_warning.py" test_count="17" coverage_target="graded_warning return contract and INFO/WARNING level dispatch, FirstLevelResult field settability and integration with the exit-code-3 high-severity check" />
    </files_created>
    <design_rationale>
      Scope was determined by the /implement build report (fmri_first_level_proc_implement_build_20260812_230500.md): the v3.0.0 refactor's 14 changes span a new exception hierarchy, a 3-stage config pipeline (load/validate/resolve), a BIDS output/discovery module, a checkpoint/DAG module, and an AFNI runtime-validation module — none of which had any test coverage prior to this pass. The 24 modified files carried collection errors or SystemExit-based assertions incompatible with the new API surface; each was re-expressed to the new contract per the disposition ledger above, with two product-bug classes routed to /implement rather than patched in tests. Full-file reads (not just SystemExit greps) surfaced two additional stale-fixture classes (BIDS column-naming, DOF-mock contract) that a search limited to "SystemExit" would have missed and silently left green against a since-changed contract.
    </design_rationale>
  </design_phase>

  <post_design_run>
    <total>635</total>
    <passed>589</passed>
    <failed>46</failed>
    <errors>0</errors>
    <coverage_pct></coverage_pct>
    <failures>
      <failure test="37 tests (task_act_first_level.py / task_conn_first_level.py callers)" file="see product-bug disposition above" line="">
        <error_type>KeyError</error_type>
        <message>KeyError: 'CONDITION'</message>
        <traceback>stim_data['CONDITION'].unique() -- column renamed to 'trial_type' by C6, not propagated to C8 pipeline modules</traceback>
        <likely_cause>product-bug: C8 did not propagate C6's BIDS column rename into task_act_first_level.py / task_conn_first_level.py. See action_items.</likely_cause>
      </failure>
      <failure test="9 tests (argparse validators)" file="see product-bug disposition above" line="">
        <error_type>NameError</error_type>
        <message>NameError: name 'argparse' is not defined</message>
        <traceback>raise argparse.ArgumentTypeError(...) -- 'import argparse' missing from first_level_utils.py</traceback>
        <likely_cause>product-bug: import argparse dropped during C7 sys.exit migration. See action_items.</likely_cause>
      </failure>
    </failures>
  </post_design_run>

  <summary>
    <assertions_preserved_or_strengthened>true</assertions_preserved_or_strengthened>
    <bugs_routed_to_implement>2</bugs_routed_to_implement>
    <recommendation>implement_fixes</recommendation>
  </summary>

  <action_items>
    <item priority="P0" target_mode="implement" description="Rename stim_data['CONDITION']/['ONSET']/['DURATION'] to ['trial_type']/['onset']/['duration'] in fmri_first_level_proc/task_act_first_level.py (lines 187, 188, 241, 736) and fmri_first_level_proc/task_conn_first_level.py (lines 188, 189, 198, 199, 201, 202, 246, 250, 254, 266, 346, 367, 374, 717, 778). Root cause: C6 renamed read_and_validate_stim_data's output columns to BIDS names; C8's pipeline-module rewrite did not propagate the rename. Confirmed by 37 test failures across 7 test files, all KeyError('CONDITION')." />
    <item priority="P0" target_mode="implement" description="Add 'import argparse' to fmri_first_level_proc/first_level_utils.py's import block. Root cause: the import was dropped (likely during the C7 sys.exit-to-exception migration) while dir_path_exists, file_path_exists, valid_string_list, valid_stat_type, valid_ave_type, and valid_conn_type still construct argparse.ArgumentTypeError on their error paths. Confirmed by 9 test failures, all NameError: name 'argparse' is not defined." />
  </action_items>
</test_report>
