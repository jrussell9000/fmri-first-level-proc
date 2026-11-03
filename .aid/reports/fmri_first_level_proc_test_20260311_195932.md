<test_report>
  <meta project="fmri_first_level_proc" mode="test" timestamp="2026-03-11T19:59:32Z" />
  <pre_design_run>
    <total>163</total>
    <passed>161</passed>
    <failed>2</failed>
    <errors>0</errors>
    <coverage_pct>N/A</coverage_pct>
    <failures>
      <failure test="test_notch_filter_no_backslash" file="tests/test_censor_creation.py" line="145">
        <error_type>AssertionError</error_type>
        <message>-input arg should end with ' but got: .../sub01_run1_notch_src_motion_prepared.1D</message>
        <traceback>Test asserts -input arg ends with single-quote (AFNI transpose), but v2.1 fix changed notch_filter_motion to use prepare_motion_file which outputs a plain .1D path without transpose suffix. The test assertion was outdated.</traceback>
      </failure>
      <failure test="TestAFNIFailurePropagation.test_rest_conn_tproject_failure_propagates" file="tests/test_error_paths.py" line="103">
        <error_type>SystemExit: 1</error_type>
        <message>Expected CalledProcessError but got SystemExit(1)</message>
        <traceback>rest_conn_first_level catches CalledProcessError per-run and continues. When all runs fail, it calls sys.exit(1). Test expected CalledProcessError to propagate but the pipeline wraps it in a graceful abort.</traceback>
      </failure>
    </failures>
  </pre_design_run>
  <design_phase>
    <tests_created>123</tests_created>
    <tests_modified>2</tests_modified>
    <files_created>
      <file path="tests/test_utils_extended.py" test_count="76" coverage_target="prepare_motion_file, compute_tissue_derivative, check_trial_survival, build_conn_output_path, write_qc_summary, validate_onset_file_format, build_decon_base_command edges, setup_logging, argparse validators (dir_path_exists, file_path_exists, valid_string_list, valid_stat_type, valid_ave_type, valid_conn_type), log_hrf_model, log_nuisance_model" />
      <file path="tests/test_config_edge_cases.py" test_count="38" coverage_target="load_config (empty/malformed YAML), validate_config edge cases (empty analyses, non-dict global/paths, boundary values for tr/fd_threshold/bandpass/motion_deriv_degree/notch_filter_band, invalid types, contrasts length mismatches), _merge_global_into_block, build_namespace with all optional features" />
      <file path="tests/test_contrast_adversarial.py" test_count="14" coverage_target="valid_contrast_functions adversarial inputs: empty strings, missing coefficients, trailing/consecutive operators, invalid characters, nonexistent conditions, zero coefficients, large coefficients, decimal-only coefficients" />
      <file path="tests/test_subbrik_and_dispatch.py" test_count="9" coverage_target="_find_subbrik_index (basic match, multiple conditions, Fstat, not found), valid_extract_labels (cond labels, contrast labels, invalid, mixed)" />
    </files_created>
    <design_rationale>
      Coverage analysis identified 15+ public functions with no direct test coverage.
      Two existing tests had stale assertions after v2.1 refactors. New tests target:
      (1) argparse type validators and helper functions (pure unit tests),
      (2) config loader/validator edge cases (malformed YAML, boundary values, all parameter validation branches),
      (3) contrast parser adversarial inputs (empty, malformed, special characters),
      (4) sub-brick index lookup and extraction label validation,
      (5) connectivity output path construction (exhaustive 8-combo parametric test),
      (6) tissue derivative computation (known-answer, multi-column error, constant signal),
      (7) trial survival counting with actual censor data (no mocks).
    </design_rationale>
  </design_phase>
  <post_design_run>
    <total>286</total>
    <passed>286</passed>
    <failed>0</failed>
    <errors>0</errors>
    <coverage_pct>N/A</coverage_pct>
    <failures>
    </failures>
  </post_design_run>
  <summary>
    <all_passing>true</all_passing>
    <recommendation>proceed_to_document</recommendation>
  </summary>
  <action_items>
    <item priority="P2" target_mode="implement" description="test_logging.py is a standalone script (not a pytest test) that appears to be a debugging artifact. Consider removing or converting to a proper test." />
    <item priority="P2" target_mode="implement" description="reproduce_issue.py in tests/ appears to be a debugging script. Consider removing if the issue it reproduces is resolved." />
  </action_items>
</test_report>
