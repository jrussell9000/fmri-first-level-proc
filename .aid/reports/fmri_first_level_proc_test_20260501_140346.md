<test_report>
  <meta project="fmri_first_level_proc" mode="test" timestamp="2026-05-01T14:03:46Z" />

  <pre_design_run>
    <total>460</total>
    <passed>434</passed>
    <failed>26</failed>
    <errors>0</errors>
    <coverage_pct>null</coverage_pct>
    <failures_summary>All 26 failures share a single root cause: AttributeError on `args.use_sequenced_bandpass` raised by the new dispatch branch in gen_residual_ts. Locally-built rest_conn SimpleNamespace fixtures and the shared make_rest_conn_args fixture predate the v2.5.0 sequenced-denoising additions and do not declare the field. Affected modules: test_cenmode (1), test_censor_creation (3), test_rest_conn_dof_skip (1), test_rest_conn_pipeline (5 base + 5 parametrized), test_tr_explicit (2), test_v240_extract_raw_ptseries (2), test_v240_pipeline_integration (7).</failures_summary>
  </pre_design_run>

  <design_phase>
    <tests_created>55</tests_created>
    <tests_modified>5</tests_modified>
    <files_created>
      <file path="tests/test_sequenced_utils.py" test_count="11" coverage_target="Unit tests for censor_interpolate_1d_afni and bandpass_filter_1d_afni: command structure (-polort -1, -dt, -input apostrophe, -censor, -cenmode NTRP, -prefix; 3dBandpass -nodetrend with positional fbot/ftop), 1dtranspose round-trip, exit-on-AFNI-failure, exit-on-transpose-failure, six-column motion variants, passband passthrough" />
      <file path="tests/test_sequenced_pipeline.py" test_count="13" coverage_target="Integration tests for _generate_run_residual_sequenced: six-step command sequence (NTRP BOLD, bandpass BOLD, per-regressor NTRP+bandpass, regression on filtered BOLD, 3dcalc post-step), filtered-input/filtered-ort assertions, 3dcalc 'a*b' censor masking, premask intermediate file flow, tissue-derivative routing through filter pipeline, GS routing, intermediate-directory creation, cleanup gating on keep_run_res_dtseries, intermediate preservation on failure, parametrized failure semantics at all four steps, idempotency on existing run_out" />
      <file path="tests/test_sequenced_dispatch.py" test_count="9" coverage_target="Dispatch tests for refactored gen_residual_ts: simultaneous selected when flag is False, sequenced selected when flag is True, correct positional args passed to backend, backend invoked once per run in both branches, shared setup runs in both branches, low-DOF skip happens before dispatch in both branches, None-return continues to next run, all-None aborts via SystemExit" />
      <file path="tests/test_sequenced_config.py" test_count="10" coverage_target="Config-validation for use_sequenced_bandpass: BOOL_KEYS membership, default-False when absent, explicit-False preserved, explicit-True preserved, global setting is intentionally ignored (BOOL_KEYS not inherited per merger doctrine), block override semantics, null coercion, non-rest_conn analyses do not expose the attribute, independence from use_tissue_derivs, both-True coexistence" />
      <file path="tests/test_sequenced_regression.py" test_count="12" coverage_target="Regression tests for use_sequenced_bandpass=False: full v2.4.0-post1 3dTproject command structural identity (input, dt, cenmode ZERO, polort -1, ort order, bandpass passband), GS-only ort form, tissue-deriv ort order, GS+derivs ort order, polort-after-orts ordering, bandpass-after-polort ordering, no -bandpass when bandpass is null, 3dTcat command form, no 3dBandpass call when flag False, no 3dcalc call when flag False, no _sequenced_intermediates directory when flag False" />
    </files_created>
    <files_modified_in_design>
      <file path="tests/conftest.py" change="Added use_sequenced_bandpass=False to make_rest_conn_args defaults; resolves shared-fixture AttributeError across the pre-existing rest_conn test suite" />
      <file path="tests/test_cenmode.py" change="Added use_sequenced_bandpass=False to the locally-built rest_conn SimpleNamespace fixture" />
      <file path="tests/test_tr_explicit.py" change="Added use_sequenced_bandpass=False to the locally-built rest_conn SimpleNamespace fixture" />
      <file path="tests/test_censor_creation.py" change="Added use_sequenced_bandpass=False to all three locally-built rest_conn SimpleNamespace fixtures" />
      <file path="tests/test_sequenced_utils.py" change="Post-design fix: corrected a patch-cleanup bug where the for-loop iterated over Mock return values from p.start() instead of patcher objects, causing patches to leak across tests and breaking test_v230_regression's numpy-savetxt-via-DataSource path; fix replaces the iteration variable" />
      <file path="tests/test_sequenced_pipeline.py" change="Same patch-cleanup fix applied to mock helpers; now returns and stops the patcher list correctly" />
      <file path="tests/test_sequenced_config.py" change="Post-design correction: a global use_sequenced_bandpass setting is intentionally ignored unless mirrored under the rest_conn block (BOOL_KEYS are not inherited per the _merge_global_into_block doctrine; only GLOBAL_ONLY_KEYS propagate). Test renamed and assertion inverted to match documented behavior." />
    </files_modified_in_design>
    <design_rationale>The brainstorm report enumerated six P1 test items; the five new test modules map to those items (utilities are paired in test_sequenced_utils.py since they share the same .1D-orientation contract; the remaining four items each get a dedicated module). The regression item is implemented as a structural-identity check on the dispatched 3dTproject command; a literal bitwise-output check would require live AFNI runs on real fMRI data, which is out of scope for unit tests. All new tests follow the existing make_pipeline_mocks pattern from conftest.py, with one exception: the unit tests for the new 1D-AFNI utilities patch run_afni_command, os.path.exists, and os.replace at the first_level_utils module level so the transpose round-trip can be verified end-to-end without requiring real AFNI binaries on disk. Tests are deterministic (no random seeds because no statistical content is generated; mock inputs are fixed strings). The pre-design run revealed all 26 baseline failures share a single root cause: the addition of use_sequenced_bandpass to the rest_conn args namespace required all rest_conn test fixtures (shared and local) to declare the field. This was resolved during design by adding the field to make_rest_conn_args and to the three locally-built fixtures.</design_rationale>
  </design_phase>

  <post_design_run>
    <total>515</total>
    <passed>515</passed>
    <failed>0</failed>
    <errors>0</errors>
    <coverage_pct>null</coverage_pct>
    <failures />
  </post_design_run>

  <summary>
    <all_passing>true</all_passing>
    <recommendation>proceed_to_document</recommendation>
  </summary>

  <action_items>
    <item priority="P2" target_mode="document" description="Update INPUT_SPECIFICATION.md to describe the new rest_conn use_sequenced_bandpass boolean key (default False), its effect (selects sequenced six-step Ciric-inspired denoising path instead of the default simultaneous 3dTproject path), and its interaction with keep_run_res_dtseries (False clears the per-run intermediate subdirectory; True or any failure preserves it for inspection)." />
    <item priority="P2" target_mode="document" description="Update README.md key-features list to mention the new sequenced-bandpass option for users with high-motion data who experience excessive DOF loss with the default simultaneous pipeline." />
    <item priority="P2" target_mode="document" description="Add module-level docstring entries to rest_conn_first_level.py introducing _generate_run_residual_simultaneous and _generate_run_residual_sequenced as the two backends; reference the Ciric et al. 2017 (PMID 28302591) and Hallquist et al. 2013 motivations briefly so future readers understand the design rationale." />
  </action_items>
</test_report>
