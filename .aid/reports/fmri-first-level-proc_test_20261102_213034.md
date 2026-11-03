<test_report>
  <meta project="fmri-first-level-proc" mode="test" timestamp="2026-11-02T21:30:34Z" />
  <input_ref>fmri-first-level-proc_implement_build_20261102_201658.md</input_ref>
  <pre_design_run>
    <total>749</total>
    <passed>749</passed>
    <failed>0</failed>
    <errors>0</errors>
    <coverage_pct></coverage_pct>
    <receipt_verified>true (14/14 freshness checks match, nonce session-3, duration 231.65s)</receipt_verified>
    <failures></failures>
  </pre_design_run>
  <failing_test_dispositions>
    <!-- none: pre-design run was clean (0 failures). The 2 tests previously failing by design
         (tests/test_config_edge_cases.py::TestResolveConfigGlobalMerge::test_bool_keys_default_false
         and tests/test_config_validation.py::TestRestParamValidation::test_bandpass_null_rejected)
         now pass, confirming the fix in fmri-first-level-proc_implement_build_20261102_201658.md. -->
  </failing_test_dispositions>
  <design_phase>
    <tests_created>0</tests_created>
    <tests_modified>2</tests_modified>
    <files_created>
    </files_created>
    <design_rationale>
      With zero failures and a narrow source change (first_level_config.py::_check_required_block_keys split into two branches: `key not in block` for boolean/bandpass keys, `block.get(key) is None` for every other required key), the only candidate gap was that split itself. No existing test exercised "required key omitted from the block entirely" for any key, so the new branch's "still raises when omitted" half (as opposed to its "no longer raises when explicitly null" half, already covered) had zero direct coverage. Added two tests, one per affected key, confirming the generic "Missing required key" message still fires when the key is absent rather than null: tests/test_config_edge_cases.py::TestValidateConfigEdges::test_include_motion_derivs_omitted_entirely_raises_config_error (task_act) and tests/test_config_validation.py::TestRestParamValidation::test_bandpass_omitted_entirely_raises_config_error (rest_conn). No other coverage gap was identified from this change; the null-default and null-specific-message postconditions were already covered by the two now-passing tests above.
    </design_rationale>
  </design_phase>
  <post_design_run>
    <total>751</total>
    <passed>751</passed>
    <failed>0</failed>
    <errors>0</errors>
    <coverage_pct></coverage_pct>
    <receipt_verified>true (14/14 freshness checks match, nonce session-4, duration 227.87s)</receipt_verified>
    <failures></failures>
  </post_design_run>
  <summary>
    <assertions_preserved_or_strengthened>true</assertions_preserved_or_strengthened>
    <bugs_routed_to_implement>0</bugs_routed_to_implement>
    <recommendation>proceed_to_document</recommendation>
  </summary>
  <action_items>
  </action_items>
</test_report>
