<test_report>
  <meta project="fmri_first_level_proc" mode="test" timestamp="2026-08-18T16:11:00-04:00" />
  <pre_design_run>
    <total>635</total>
    <passed>635</passed>
    <failed>0</failed>
    <errors>0</errors>
    <coverage_pct></coverage_pct>
    <failures>
    </failures>
  </pre_design_run>
  <failing_test_dispositions>
  </failing_test_dispositions>
  <design_phase>
    <tests_created>30</tests_created>
    <tests_modified>0</tests_modified>
    <files_created>
      <file path="tests/test_exceptions.py" test_count="17" coverage_target="FmriFirstLevelError.context: default empty dict, explicit dict storage, None coercion, inheritance across all 6 subclasses (parametrized), positional-message backward-compatibility regression guard, no-args instantiation" />
      <file path="tests/test_runtime.py" test_count="13" coverage_target="probe_tool_versions() Python minor-series validation (12 tests: absent-field skip, matching minor pass, micro-mismatch tolerance, major/minor mismatch raises, malformed-pin raises for both under-specified and non-numeric forms, independence from AFNI PLACEHOLDER/pass state, verified-tool-count log correctness across 2-check/1-check/0-check combinations) plus run_first_level.main() lockfile-absent resilience path (1 test: no exception raised, graded_warning fires with the generalized 'skipping version pinning' wording)" />
    </files_created>
    <design_rationale>Both files were extended (not newly created) to close the coverage gap left by the prior /implement build, which added the context parameter to FmriFirstLevelError, restructured probe_tool_versions() to run AFNI and Python checks independently, and generalized the lockfile-absent warning message. The Python-independence tests are the highest-value additions: they directly exercise the behavioral change from early-return-on-PLACEHOLDER to independent if/else branches, which is exactly the kind of silent regression the prior session's polort A duplicate-read incident demonstrated this codebase is vulnerable to. Micro-mismatch-tolerance tests verify the minor-series (not exact-match) semantics that were the explicit design decision from the brainstorm. All new tests use dynamic sys.version_info-derived pins for the passing cases (avoiding fragile hardcoded version mocking) and deliberately out-of-range values (major=1, minor=999) for failure cases, so the suite remains valid across interpreter upgrades.</design_rationale>
  </design_phase>
  <post_design_run>
    <total>665</total>
    <passed>665</passed>
    <failed>0</failed>
    <errors>0</errors>
    <coverage_pct></coverage_pct>
    <failures>
    </failures>
  </post_design_run>
  <summary>
    <assertions_preserved_or_strengthened>true</assertions_preserved_or_strengthened>
    <bugs_routed_to_implement>0</bugs_routed_to_implement>
    <recommendation>proceed_to_document</recommendation>
  </summary>
  <action_items>
  </action_items>
</test_report>
