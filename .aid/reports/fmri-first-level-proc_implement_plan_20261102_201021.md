<implement_plan>
  <meta project="fmri-first-level-proc" mode="implement" submodule="plan" timestamp="2026-11-02T20:10:21Z" />
  <input_reports>
    <report path="fmri-first-level-proc_test_20261102_183001.md" mode="test" key_items="2" />
  </input_reports>
  <locked_decisions>
    <decision id="D1">The two documentation lines stating "A required key set to null counts as missing" (INPUT_SPECIFICATION.md line 61, CHANGELOG.md line 27) are amended in this change set to match the fixed behavior (user choice: include now).</decision>
  </locked_decisions>
  <changes>
    <change id="C1" priority="P1" source_item="test report action_items 1 and 2">
      <file path="fmri_first_level_proc/first_level_config.py" action="modify" />
      <description>Narrow the null-as-missing rule in _check_required_block_keys so that, for boolean keys (BOOL_FIELDS[atype]) and for bandpass, only absence of the key counts as missing. An explicit null for include_motion_derivs then resolves to its documented default (False), and an explicit bandpass: null reaches _validate_rest_params's specific "bandpass is required for rest_conn" message.</description>
      <spec>
In _check_required_block_keys(block, atype, label, discovery_active, logger):
- Compute presence_only = set(BOOL_FIELDS[atype]) | {"bandpass"}.
- In the loop over sorted(check): if key in presence_only, raise the existing ConfigError (same message text) only when key not in block; otherwise keep the existing rule (raise when block.get(key) is None).
- Update the docstring to: "Check required top-level keys for a block; a key set to null counts as missing, except boolean keys (null means the default) and bandpass (validated by _validate_rest_params)."
- No change to the required key sets, the error message text, or any caller. resolve_config already coerces include_motion_derivs with bool(validated_block.get("include_motion_derivs", False)), so null resolves to False; _check_bool_fields already accepts null for boolean keys.
Expected effect on tests: tests/test_config_edge_cases.py::TestResolveConfigGlobalMerge::test_bool_keys_default_false and tests/test_config_validation.py::TestRestParamValidation::test_bandpass_null_rejected pass; the null cond_labels/fd_threshold/out_dir ConfigError tests are unaffected (those keys are neither boolean nor bandpass).
      </spec>
      <dependencies>none</dependencies>
      <risk>low - single function, two keys affected; omitted keys still raise the same message, and every other required key keeps its current behavior.</risk>
      <rollback>Restore the single-rule loop (raise when block.get(key) is None) and the previous docstring.</rollback>
    </change>
    <change id="C2" priority="P1" source_item="D1">
      <file path="INPUT_SPECIFICATION.md" action="modify" />
      <file path="CHANGELOG.md" action="modify" />
      <description>Amend the documented null rule to match C1.</description>
      <spec>
- INPUT_SPECIFICATION.md line 61: replace "- A required key set to `null` counts as missing." with "- A required key set to `null` counts as missing, except boolean keys (`null` means the documented default, e.g. `include_motion_derivs: null` is `false`) and `bandpass` (`null` raises the `rest_conn` message \"bandpass is required\")."
- CHANGELOG.md line 27: in the "Strict config values" entry, replace "A required key set to `null` counts as missing." with "A required key set to `null` counts as missing, except boolean keys (`null` means the default) and `bandpass` (which reports its own \"bandpass is required\" error)."
- No em-dashes; no other text changes.
      </spec>
      <dependencies>C1</dependencies>
      <risk>low - documentation only.</risk>
      <rollback>Restore the two original sentences.</rollback>
    </change>
  </changes>
  <execution_order>C1, C2</execution_order>
</implement_plan>
