<test_report>
  <meta project="fmri-first-level-proc" mode="test" timestamp="2026-10-29T20:02:42Z" />
  <pre_design_run>
    <total>566</total>
    <passed>558</passed>
    <failed>4</failed>
    <errors>4</errors>
    <coverage_pct></coverage_pct>
    <failures>
      <failure test="TestGet3dinfoProperties::test_all_keys_present_for_valid_scan" file="tests/test_error_paths.py" line="96">
        <error_type>AssertionError</error_type>
        <message>get_3dinfo_properties returns only {dmax, space}; test expected {space, orient, spacing, dmax}</message>
        <traceback>assert set(props.keys()) == {"space", "orient", "spacing", "dmax"}
AssertionError: assert {'dmax', 'space'} == {'dmax', 'orient', 'space', 'spacing'}</traceback>
      </failure>
      <failure test="TestGet3dinfoProperties::test_nonexistent_file_does_not_raise" file="tests/test_error_paths.py" line="106">
        <error_type>AssertionError</error_type>
        <message>Same cause as above</message>
        <traceback>assert set(props.keys()) == {"space", "orient", "spacing", "dmax"}
AssertionError: assert {'dmax', 'space'} == {'dmax', 'orient', 'space', 'spacing'}</traceback>
      </failure>
      <failure test="test_run_tag_unpadded" file="tests/test_names.py" line="92">
        <error_type>AttributeError</error_type>
        <message>module 'fmri_first_level_proc.names' has no attribute 'run_tag'</message>
        <traceback>assert names.run_tag(1) == "run1"
AttributeError: module 'fmri_first_level_proc.names' has no attribute 'run_tag'</traceback>
      </failure>
      <failure test="TestRestConnSequencedBackendDerivativeKeys::test_sequenced_backend_regresses_base_and_derivative_tissue_signals" file="tests/test_rest_conn_pipeline.py" line="328">
        <error_type>TypeError</error_type>
        <message>_residual_sequenced() takes 9 positional arguments but 10 were given</message>
        <traceback>_residual_sequenced(io, config, 1, scan, censor, motion, tissue_paths, "residual.nii.gz", logger, "intermediate")
TypeError: _residual_sequenced() takes 9 positional arguments but 10 were given</traceback>
      </failure>
      <failure test="[collection] test_checkpoint.py" file="tests/test_checkpoint.py" line="11">
        <error_type>ImportError</error_type>
        <message>cannot import name 'latest_staged' from 'fmri_first_level_proc.checkpoint'</message>
        <traceback>from fmri_first_level_proc.checkpoint import (...)
ImportError: cannot import name 'latest_staged' from 'fmri_first_level_proc.checkpoint'</traceback>
      </failure>
      <failure test="[collection] test_roi.py" file="tests/test_roi.py" line="13">
        <error_type>ImportError</error_type>
        <message>cannot import name 'template_labels' from 'fmri_first_level_proc.roi'</message>
        <traceback>from fmri_first_level_proc.roi import (...)
ImportError: cannot import name 'template_labels' from 'fmri_first_level_proc.roi'</traceback>
      </failure>
      <failure test="[collection] test_sequenced_config.py" file="tests/test_sequenced_config.py" line="22">
        <error_type>ImportError</error_type>
        <message>cannot import name 'BOOL_KEYS' from 'fmri_first_level_proc.first_level_config'</message>
        <traceback>from fmri_first_level_proc.first_level_config import (...)
ImportError: cannot import name 'BOOL_KEYS' from 'fmri_first_level_proc.first_level_config'</traceback>
      </failure>
      <failure test="[collection] test_utils_unit.py" file="tests/test_utils_unit.py" line="16">
        <error_type>ImportError</error_type>
        <message>cannot import name 'dir_path_exists' from 'fmri_first_level_proc.first_level_utils'</message>
        <traceback>from fmri_first_level_proc.first_level_utils import (...)
ImportError: cannot import name 'dir_path_exists' from 'fmri_first_level_proc.first_level_utils'</traceback>
      </failure>
    </failures>
  </pre_design_run>
  <failing_test_dispositions>
    <disposition test="TestGet3dinfoProperties::test_all_keys_present_for_valid_scan, test_nonexistent_file_does_not_raise" file="tests/test_error_paths.py" classification="obsolete-test">
      <intended_contract>get_3dinfo_properties returns a dict of requested 3dinfo-derived metadata keys; the contract only ever promised the keys actually consumed downstream.</intended_contract>
      <current_test_claim>Asserted the returned key set is exactly {space, orient, spacing, dmax}.</current_test_claim>
      <evidence>fmri_first_level_proc/first_level_utils.py get_3dinfo_properties (line 649): the queries dict now contains only "space" and "dmax"; orient and spacing were removed. Confirmed via grep that no caller anywhere in the package reads either key.</evidence>
      <action>re-express: shrink the expected key set to {space, dmax} in both tests; all other assertions (dmax not-None for a valid scan, ValueError on float() of the sentinel for a missing file) preserved exactly.</action>
    </disposition>
    <disposition test="test_run_tag_unpadded" file="tests/test_names.py" classification="obsolete-test">
      <intended_contract>names.run_tag formatted a zero-padded-free run label string; this was dead code with no production caller.</intended_contract>
      <current_test_claim>Asserted names.run_tag(1) == "run1" and names.run_tag(12) == "run12".</current_test_claim>
      <evidence>fmri_first_level_proc/names.py: run_tag no longer exists. grep -rn "run_tag" fmri_first_level_proc/ returns no hits, confirming no production code ever called it.</evidence>
      <action>delete the test and its now-empty "Run identity" section header; the function itself is gone, so there is no contract left to assert.</action>
    </disposition>
    <disposition test="TestRestConnSequencedBackendDerivativeKeys::test_sequenced_backend_regresses_base_and_derivative_tissue_signals" file="tests/test_rest_conn_pipeline.py" classification="obsolete-test">
      <intended_contract>_residual_sequenced must regress exactly 7 distinct, correctly-keyed nuisance signals (motion, CSF/WM/GS base and derivative) per run, with no key collisions.</intended_contract>
      <current_test_claim>Called _residual_sequenced with 10 positional arguments, the last being the literal string "intermediate".</current_test_claim>
      <evidence>fmri_first_level_proc/rest_conn_first_level.py _residual_sequenced (line 134): signature is now 9 parameters; the always-constant intermediate_cls parameter was removed since both of its call sites already passed the literal "intermediate".</evidence>
      <action>re-express: drop the stale trailing argument from the call. All three assertions (call count, distinctness, exact key set) are unchanged.</action>
    </disposition>
    <disposition test="[collection] test_checkpoint.py (latest_staged)" file="tests/test_checkpoint.py" classification="obsolete-test">
      <intended_contract>latest_staged returned the most recent staged-record for a given step; dead code with no production caller (distinct from engine.py's private _latest_staged_set method).</intended_contract>
      <current_test_claim>Imported latest_staged and asserted it returns the most recently appended staged record for a step.</current_test_claim>
      <evidence>fmri_first_level_proc/checkpoint.py: latest_staged no longer exists. grep -rn "latest_staged" fmri_first_level_proc/ shows only engine.py's unrelated _latest_staged_set method.</evidence>
      <action>remove the name from the import statement; delete the one test exercising it. The module's other latest_completion/recorded_paths coverage is untouched.</action>
    </disposition>
    <disposition test="[collection] test_roi.py (template_labels)" file="tests/test_roi.py" classification="obsolete-test">
      <intended_contract>template_labels returned the sorted list of ROI labels in a template; dead code with no production caller after roi_qc was consolidated to derive labels from count_nonzero_by_roi's own result.</intended_contract>
      <current_test_claim>Asserted template_labels(tpl, logger) == [1, 2, 3] for a 3-ROI template.</current_test_claim>
      <evidence>fmri_first_level_proc/roi.py: template_labels no longer exists. grep -rn "template_labels" fmri_first_level_proc/ returns no hits. roi_qc now computes tlabels = sorted(n_vox) directly from count_nonzero_by_roi's return dict.</evidence>
      <action>remove the name from the import statement; delete the one test exercising it. The sibling test_count_nonzero_by_roi_matches_known_voxel_counts test still exercises the real 3dROIstats-based counting path this function used.</action>
    </disposition>
    <disposition test="[collection] test_sequenced_config.py (BOOL_KEYS)" file="tests/test_sequenced_config.py" classification="obsolete-test">
      <intended_contract>use_sequenced_bandpass's YAML null value must coerce to False during config resolution.</intended_contract>
      <current_test_claim>Asserted "use_sequenced_bandpass" in BOOL_KEYS, under the premise that a generic BOOL_KEYS loop performs the null-to-False coercion.</current_test_claim>
      <evidence>fmri_first_level_proc/first_level_config.py: BOOL_KEYS no longer exists. resolve_config's rest_conn branch (line 1030) coerces this field with an explicit inline bool(validated_block.get("use_sequenced_bandpass", False)) call, not a generic constant-driven loop. The file's own test_use_sequenced_bandpass_null_in_yaml_coerces_to_false test already exercises this exact postcondition through resolve_config directly and continues to pass.</evidence>
      <action>remove the name from the import statement; delete the one membership test. Updated the module docstring and two in-file comments that described the now-removed BOOL_KEYS mechanism, so the file no longer misdescribes how the coercion works. The null-coercion postcondition remains fully covered by the unaffected sibling test.</action>
    </disposition>
    <disposition test="[collection] test_utils_unit.py (6 argparse helpers)" file="tests/test_utils_unit.py" classification="obsolete-test">
      <intended_contract>dir_path_exists, file_path_exists, valid_string_list, valid_stat_type, valid_ave_type, and valid_conn_type were argparse type-converter helpers for a CLI surface the package no longer exposes this way; dead code with no production caller, already flagged for routing to /test in the prior build report.</intended_contract>
      <current_test_claim>TestArgparseValidators asserted each helper's accept/reject behavior for CLI-style string inputs.</current_test_claim>
      <evidence>fmri_first_level_proc/first_level_utils.py: all six names were removed along with the argparse import. grep -rn confirms no production caller for any of the six.</evidence>
      <action>remove the six names from the import statement; delete the now-fully-dead TestArgparseValidators class in its entirety; remove the now-unused argparse import; update the module docstring's "argparse validators" mention. No other test in the file referenced argparse.</action>
    </disposition>
  </failing_test_dispositions>
  <design_phase>
    <tests_created>1</tests_created>
    <tests_modified>10</tests_modified>
    <files_created>
      <file path="tests/test_stat_bucket_extraction.py" test_count="6" coverage_target="extract_stat_bucket_niftis and _get_stataux against a real 3dDeconvolve bucket: exact-label sub-brick selection for Coef/Fstat/R^2/Zstat including the Full_Fstat/Full_R^2 model sub-bricks, per-sub-brick DOF retrieval via a single 3dAttribute call, and a numerical cross-check of the Zstat conversion against a manually computed fitt_t2z reference using that same DOF" />
    </files_created>
    <design_rationale>Every edit in the pre-design failure set was traced to a confirmed-dead-code removal or an unchanged-behavior signature change from the preceding implement build (independently re-verified against current source and callers, not taken on the build report's word alone); none were weakened, and one (the BOOL_KEYS case) required confirming the real postcondition survives through a sibling test before the membership assertion could be safely deleted. Beyond those fixes, a coverage-gap survey found zero existing tests for four build changes that introduced genuine new behavior (not pure refactors verified byte-identical by hand during the build): the P0 stat-bucket extraction rewrite, the new lss_index field, the new contrast-label integrity guard, and the removal of the 13-run intersection-mask cap. New regression tests were added for all four, scoped by explicit user approval against a fifth category (the pure-refactor consolidations) that was deliberately left uncovered this pass since it introduces no new behavior to protect.</design_rationale>
  </design_phase>
  <post_design_run>
    <total>682</total>
    <passed>682</passed>
    <failed>0</failed>
    <errors>0</errors>
    <coverage_pct></coverage_pct>
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
