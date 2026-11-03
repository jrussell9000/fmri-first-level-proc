<test_report>
  <meta project="fmri-first-level-proc" mode="test" timestamp="2026-11-02T18:30:01Z" />
  <input_ref>fmri-first-level-proc_implement_build_20261102_145556.md</input_ref>
  <pre_design_run>
    <total>682</total>
    <passed>664</passed>
    <failed>18</failed>
    <errors>0</errors>
    <coverage_pct></coverage_pct>
    <receipt_verified>true (14/14 freshness checks match, nonce session-1)</receipt_verified>
    <failures>
      <failure test="TestResolveConfigGlobalMerge::test_bool_keys_default_false" file="tests/test_config_edge_cases.py" line="415">
        <error_type>ConfigError</error_type>
        <message>[test_task_act] Missing required key 'include_motion_derivs' for type 'task_act'.</message>
      </failure>
      <failure test="TestRestParamValidation::test_bandpass_null_rejected" file="tests/test_config_validation.py" line="225">
        <error_type>AssertionError</error_type>
        <message>Expected regex 'bandpass is required'; actual message "[t] Missing required key 'bandpass' for type 'rest_conn'."</message>
      </failure>
      <failure test="TestMainExitCodeMapping::test_config_error_exits_2" file="tests/test_exceptions.py" line="113">
        <error_type>AttributeError</error_type>
        <message>module 'fmri_first_level_proc.run_first_level' has no attribute 'load_and_validate'. Did you mean: 'load_and_validate_blocks'?</message>
      </failure>
      <failure test="TestMainExitCodeMapping::test_input_error_exits_2" file="tests/test_exceptions.py" line="113">
        <error_type>AttributeError</error_type>
        <message>same cause as test_config_error_exits_2</message>
      </failure>
      <failure test="TestMainExitCodeMapping::test_model_error_exits_5" file="tests/test_exceptions.py" line="113">
        <error_type>AttributeError</error_type>
        <message>same cause as test_config_error_exits_2</message>
      </failure>
      <failure test="TestMainExitCodeMapping::test_tool_unavailable_error_exits_4" file="tests/test_exceptions.py" line="113">
        <error_type>AttributeError</error_type>
        <message>same cause as test_config_error_exits_2</message>
      </failure>
      <failure test="TestMainExitCodeMapping::test_tool_execution_error_exits_4" file="tests/test_exceptions.py" line="113">
        <error_type>AttributeError</error_type>
        <message>same cause as test_config_error_exits_2</message>
      </failure>
      <failure test="TestMainExitCodeMapping::test_guard_error_exits_1" file="tests/test_exceptions.py" line="113">
        <error_type>AttributeError</error_type>
        <message>same cause as test_config_error_exits_2</message>
      </failure>
      <failure test="TestMainExitCodeMapping::test_high_severity_warning_exits_3" file="tests/test_exceptions.py" line="195">
        <error_type>AttributeError</error_type>
        <message>patched run_first_level.load_and_validate directly (not via the shared helper); same missing-attribute cause</message>
      </failure>
      <failure test="TestMainExitCodeMapping::test_success_returns_without_exit" file="tests/test_exceptions.py" line="195">
        <error_type>AttributeError</error_type>
        <message>same cause as test_high_severity_warning_exits_3</message>
      </failure>
      <failure test="TestBuildRunsets::test_task_mode_a_two_runs" file="tests/test_runsets.py" line="30">
        <error_type>AttributeError</error_type>
        <message>'types.SimpleNamespace' object has no attribute 'include_motion_derivs', raised from runsets.py _motion_columns()</message>
      </failure>
      <failure test="TestBuildRunsets::test_task_mode_b_single_concatenated_file" file="tests/test_runsets.py" line="55">
        <error_type>AttributeError</error_type>
        <message>same cause as test_task_mode_a_two_runs</message>
      </failure>
      <failure test="TestBuildRunsets::test_rest_conn_always_mode_a" file="tests/test_runsets.py" line="75">
        <error_type>AttributeError</error_type>
        <message>'types.SimpleNamespace' object has no attribute 'motion_deriv_degree' (rest_conn branch of _motion_columns())</message>
      </failure>
      <failure test="TestBuildRunsets::test_motion_row_count_mismatch_raises_input_error" file="tests/test_runsets.py" line="90">
        <error_type>AttributeError</error_type>
        <message>same cause as test_rest_conn_always_mode_a</message>
      </failure>
      <failure test="TestBuildRunsets::test_tissue_row_count_mismatch_raises_input_error" file="tests/test_runsets.py" line="105">
        <error_type>AttributeError</error_type>
        <message>same cause as test_rest_conn_always_mode_a</message>
      </failure>
      <failure test="TestBuildRunsets::test_header_tr_mismatch_raises_input_error" file="tests/test_runsets.py" line="120">
        <error_type>AttributeError</error_type>
        <message>same cause as test_rest_conn_always_mode_a</message>
      </failure>
      <failure test="TestBuildRunsets::test_header_tr_checked_on_concatenated_file_for_mode_b" file="tests/test_runsets.py" line="135">
        <error_type>AttributeError</error_type>
        <message>same cause as test_task_mode_a_two_runs (task_conn branch)</message>
      </failure>
      <failure test="TestBuildRunsets::test_grid_mismatch_raises_input_error" file="tests/test_runsets.py" line="150">
        <error_type>AttributeError</error_type>
        <message>same cause as test_rest_conn_always_mode_a</message>
      </failure>
    </failures>
  </pre_design_run>
  <failing_test_dispositions>
    <disposition test="TestResolveConfigGlobalMerge::test_bool_keys_default_false" file="tests/test_config_edge_cases.py" classification="product-bug">
      <intended_contract>include_motion_derivs: null must resolve to its documented default (False). This is a documented, intentional null-default boolean field (BOOL_FIELDS / _TASK_BOOLS in first_level_config.py; INPUT_SPECIFICATION.md and CHANGELOG.md edited this session state "Boolean keys accept true, false or null (null means the documented default)").</intended_contract>
      <current_test_claim>Sets remove_previous=None and include_motion_derivs=None, asserts both resolve to False.</current_test_claim>
      <evidence>first_level_config.py _check_required_block_keys treats ANY null required-key value as missing, including include_motion_derivs, which is simultaneously in the required-key set AND documented as null-default. The blanket check fires and raises ConfigError before the later bool-coercion logic can apply the default. remove_previous is not in the required-key set for any type, so it is unaffected.</evidence>
      <action>no assertion edit (product-bug disposition prohibits it). Routed to /implement: see action_items.</action>
    </disposition>
    <disposition test="TestRestParamValidation::test_bandpass_null_rejected" file="tests/test_config_validation.py" classification="product-bug">
      <intended_contract>An explicit bandpass: null must raise the specific, pre-existing message "bandpass is required for rest_conn..." from _validate_rest_params, distinct from the generic "Missing required key" message an omitted key would produce. The test's own docstring states this intended contract verbatim and the test is not new this session.</intended_contract>
      <current_test_claim>Sets bandpass=None, expects ConfigError matching "bandpass is required".</current_test_claim>
      <evidence>The same blanket null-as-missing check in _check_required_block_keys fires first with "Missing required key 'bandpass'...", preempting _validate_rest_params's more specific, already-correct message. grep confirms no other required field has a conflicting downstream null-specific message, so this is a narrow carve-out, not a general design defect.</evidence>
      <action>no assertion edit (product-bug disposition prohibits it). Routed to /implement: see action_items.</action>
    </disposition>
    <disposition test="TestMainExitCodeMapping (8 tests: test_config_error_exits_2, test_input_error_exits_2, test_model_error_exits_5, test_tool_unavailable_error_exits_4, test_tool_execution_error_exits_4, test_guard_error_exits_1, test_high_severity_warning_exits_3, test_success_returns_without_exit)" file="tests/test_exceptions.py" classification="obsolete-test">
      <intended_contract>Each exception type raised while loading/validating the config must map to its documented CLI exit code (ConfigError/InputError-&gt;2, ModelError-&gt;5, ToolUnavailableError/ToolExecutionError-&gt;4, GuardError-&gt;1); a successful run with no high-severity warning returns normally; a successful run with a high-severity warning exits 3.</intended_contract>
      <current_test_claim>Monkeypatches fmri_first_level_proc.run_first_level.load_and_validate to raise or to return a bare list of ResolvedConfig.</current_test_claim>
      <evidence>Change C16 (per the implement build) removed run_first_level's re-export of load_and_validate and restructured main() to call load_and_validate_blocks for per-block CLI isolation (locked decisions L5/L7). The attribute genuinely no longer exists on that module. The outer try/except mechanism these tests target is unchanged: a global loader failure is still caught by the same handler and mapped through the same exceptions.exit_code() table.</evidence>
      <action>re-expressed: patch load_and_validate_blocks instead of load_and_validate, raising directly for the 6 exception-mapping tests (same mechanism, same postcondition). For test_high_severity_warning_exits_3 and test_success_returns_without_exit, patch it to return a single BlockResolution(index=0, name=None, analysis_type="task_act", config=cfg, error=None, raw_out_dir=None, raw_out_file_pre=None) in place of the old bare [cfg] list, since main()'s per-block loop reads config from block.config when block.error is None -- an exact structural analog with an identical postcondition. All original exit-code and no-exit assertions preserved verbatim.</action>
    </disposition>
    <disposition test="TestBuildRunsets (8 tests: test_task_mode_a_two_runs, test_task_mode_b_single_concatenated_file, test_rest_conn_always_mode_a, test_motion_row_count_mismatch_raises_input_error, test_tissue_row_count_mismatch_raises_input_error, test_header_tr_mismatch_raises_input_error, test_header_tr_checked_on_concatenated_file_for_mode_b, test_grid_mismatch_raises_input_error)" file="tests/test_runsets.py" classification="obsolete-test">
      <intended_contract>build_runsets' per-run consistency checks (row counts, header TR, grid match) are unaffected by this round's changes; none of these 8 tests assert anything about motion column counts.</intended_contract>
      <current_test_claim>Builds minimal SimpleNamespace config fixtures lacking include_motion_derivs (task types) or motion_deriv_degree (rest_conn).</current_test_claim>
      <evidence>Change C8 added a genuinely new column-count + finiteness check (_motion_columns()) that reads these attributes unconditionally at the top of _run_consistency_checks, for every analysis type -- this closes boundary-audit finding A4 (a NaN motion value previously passed censoring silently). The pre-C8 function never read these attributes. make_motion's default output is 6 columns, so include_motion_derivs=False (needs 6) and motion_deriv_degree=1 (needs 6) both satisfy the new check without altering any of these 8 tests' own assertions (row-count mismatches, TR mismatches, grid mismatches, Mode A/B structure), confirmed by tracing the row-count/TR/grid checks' relative order after the new column check in the function body.</evidence>
      <action>re-expressed: added include_motion_derivs=False to each task_act/task_conn fixture and motion_deriv_degree=1 to each rest_conn fixture. All original assertions unchanged and unweakened; verified by local run after the fix (all 8 pass with their original postconditions intact).</action>
    </disposition>
  </failing_test_dispositions>
  <design_phase>
    <files_created>
      <file path="tests/test_inputs.py" test_count="7" coverage_target="inputs.check_inputs (new module, C15): valid real configs pass and write nothing to out_dir; the rest_conn path-list-length ConfigError guard; onset-violation InputError surfaced with the dry-run-specific message; a real template ConfigError (seed_to_voxel with a multi-ROI template) surfaced identically to a real run, writing nothing." />
      <file path="tests/test_run_status.py" test_count="9" coverage_target="engine.write_failure_qc / run_with_status (C13/C14): success-path run_status on a real pipeline run; failure qc_summary contains only analysis_type/run_status/provenance (never partial metrics); exit_code() embedded correctly per exception type; all 4 guard conditions under which write_failure_qc writes nothing (missing out_dir, unsafe pre, unknown analysis_type); run_with_status passthrough on success and re-raise-after-write on failure, including when tracker.step was never set." />
      <file path="tests/test_discovery_integration.py" test_count="11" coverage_target="resolve_config-level BIDS discovery (C4/C5), complementing test_bids.py's pure discover_inputs()-level unit tests: task-required and string-typed-entity validation; task not required outside discovery mode; end-to-end discovery populating a real ResolvedConfig; explicit paths winning over discovery per-slot; discovered-slot reordering to explicit run_labels and the InputError on a run-label mismatch; the B1 regression (empty paths + no discovery now raises ConfigError, not a TypeError) and its InputError counterpart when discovery is active but finds nothing." />
    </files_created>
    <files_modified>
      <file path="tests/test_exceptions.py" new_tests="11 (1 parametrized across 7 exit-code cases + 4 discrete)" fixed_tests="8" description="Fixed the 8 TestMainExitCodeMapping tests (see dispositions). Added TestExitCodeHelper (direct unit coverage of exceptions.exit_code() for every mapped type, including ToolVersionError and subprocess.CalledProcessError) and TestPerBlockIsolation (C16: an invalid block does not block a valid sibling block from running, and the CLI exit code is the first failing block's code in config order; --dry-run calls check_inputs instead of DISPATCH)." />
      <file path="tests/test_runsets.py" new_tests="4" fixed_tests="8" description="Fixed the 8 TestBuildRunsets tests (see dispositions). Added TestMotionColumnAndFiniteChecks: insufficient motion columns for both task and rest_conn degree settings, and the A4 regression itself (a NaN motion value and a non-finite tissue value both now raise InputError from build_runsets, before any AFNI call)." />
      <file path="tests/test_config_edge_cases.py" new_tests="9" description="Regression tests for 3 of the confirmed boundary-audit bugs now fixed (null cond_labels/fd_threshold/out_dir all raise ConfigError), the C6 rest_conn singular-tissue-path rejection, the C3/L3 task_conn contrasts-without-calc_conn ConfigError, the C7 cross-block output-prefix collision check (via load_and_validate directly) and its negative case, and the scale_to_psc: null default-to-True fix (plus its explicit-false counterpart) noted as a build deviation in the implement report." />
      <file path="tests/test_config_validation.py" new_tests="6" description="Regression tests for the remaining confirmed boundary-audit bugs: strict boolean rejection (a quoted 'false' string), NaN tr and NaN fd_threshold (A5/A5b), a non-filename-safe out_file_pre, a string (non-list) derivatives_dirs (A9), and extract_resids without extract_out_file_pre (A6)." />
      <file path="tests/test_bids.py" new_tests="1" description="Exact task-entity matching (C4): a file with task='restpre' must not match a discovery request for task='rest'." />
      <file path="tests/test_task_conn_pipeline.py" new_tests="3" description="Real-AFNI coverage for C10 (an unsafe nuisance-condition name raises InputError before any AFNI call) and C12 (a connectivity contrast referencing a condition confined to a run excluded by task_nuisance is skipped with CONTRAST_DROPPED and excluded from qc_summary['contrast_labels']; a rerun against the same out_dir after this completes without a GuardError, closing the B5 risk noted but not reproduced in the implement build report)." />
      <file path="tests/test_rest_conn_pipeline.py" new_tests="2" description="Real-AFNI coverage for the L1 locked decision (C11): a multi-column CSF/WM file produces byte-identical final residual output to an equivalent single-column file holding only the first column, and the per-run prepared single-column tissue copy is written to out_dir." />
    </files_modified>
    <design_rationale>
      Every pre-design failure was traced to one of two causes: a genuine pre-existing defect in the just-built required-key null check (2 tests, left failing by design and routed to /implement), or a deliberate, documented behavior change from the same build (16 tests, re-expressed with their original postconditions fully preserved, confirmed by local re-run after each fix). One test (test_bids.py addition) was filed in the module that already owns discover_inputs()-level unit tests rather than the newly-created resolve_config-level integration file, matching the approved plan's intent (exact-match coverage for C4) without altering its scope.

      Beyond fixing and re-expressing the pre-design failures, new coverage was added for all 17 implement changes, with particular weight on the boundary audit's originally-confirmed-by-execution defects: B1 (missing required inputs), A4 (NaN motion), A5/A5b (NaN tr/fd_threshold), A6 (extract_resids without a prefix), A9 (string derivatives_dirs), and B2 (duplicate events, closed in a prior round and re-verified here via the cross-run disposition). Two features newly introduced by this round's build (C11's prepared-tissue first-column contract and C12's contrast-skip warning) had zero prior test coverage and are now covered end-to-end against real AFNI.
    </design_rationale>
  </design_phase>
  <post_design_run>
    <total>749</total>
    <passed>747</passed>
    <failed>2</failed>
    <errors>0</errors>
    <coverage_pct></coverage_pct>
    <receipt_verified>true (14/14 freshness checks match, nonce session-2, duration 224.9s)</receipt_verified>
    <failures>
      <failure test="TestResolveConfigGlobalMerge::test_bool_keys_default_false" file="tests/test_config_edge_cases.py" line="461">
        <error_type>ConfigError</error_type>
        <message>Intentional: documents the product-bug above, routed to /implement. [test_task_act] Missing required key 'include_motion_derivs' for type 'task_act'.</message>
      </failure>
      <failure test="TestRestParamValidation::test_bandpass_null_rejected" file="tests/test_config_validation.py" line="225">
        <error_type>AssertionError</error_type>
        <message>Intentional: documents the second product-bug above, routed to /implement. Expected regex 'bandpass is required'; actual "[t] Missing required key 'bandpass' for type 'rest_conn'."</message>
      </failure>
    </failures>
  </post_design_run>
  <summary>
    <assertions_preserved_or_strengthened>true</assertions_preserved_or_strengthened>
    <bugs_routed_to_implement>2</bugs_routed_to_implement>
    <recommendation>proceed_to_implement</recommendation>
  </summary>
  <action_items>
    <item priority="P1" target_mode="implement" description="first_level_config.py _check_required_block_keys(): exempt keys that are also documented null-default boolean fields (BOOL_FIELDS/_TASK_BOOLS) from the blanket null-as-missing check, so include_motion_derivs: null (and any other required-and-boolean field) reaches the later default-coercion logic instead of raising a spurious 'Missing required key' ConfigError. Test: tests/test_config_edge_cases.py::TestResolveConfigGlobalMerge::test_bool_keys_default_false (currently failing by design)." />
    <item priority="P1" target_mode="implement" description="first_level_config.py _check_required_block_keys(): exempt 'bandpass' from the same blanket null-as-missing check, so an explicit bandpass: null reaches _validate_rest_params's existing, more specific 'bandpass is required for rest_conn...' message instead of the generic one. Both this item and the one above are narrow carve-outs to the same function and can likely be fixed together; confirmed via grep that no other required field has a conflicting downstream null-specific message, so no broader mechanism change is needed. Test: tests/test_config_validation.py::TestRestParamValidation::test_bandpass_null_rejected (currently failing by design)." />
  </action_items>
</test_report>
