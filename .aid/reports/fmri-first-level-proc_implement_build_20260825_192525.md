<implement_report>
  <meta project="fmri-first-level-proc" mode="implement" submodule="build" timestamp="2026-08-25T19:25:25Z" />
  <spec_ref>fmri-first-level-proc_implement_plan_20260825_190018.md</spec_ref>
  <changes_applied>
    <change id="C1" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_utils.py" lines_changed="14" />
      </files_modified>
      <notes>Added module-level warning accumulator (_WARNING_ACCUMULATOR, get_warnings, clear_warnings). Modified graded_warning to build record, append to accumulator, and return the record.</notes>
    </change>
    <change id="C2" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/__init__.py" lines_changed="3" />
      </files_modified>
      <notes>Added get_warnings, clear_warnings to imports and __all__. Also added ToolVersionError export (from C4 dependency).</notes>
    </change>
    <change id="C3" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_act_first_level.py" lines_changed="12" />
        <file path="fmri_first_level_proc/task_conn_first_level.py" lines_changed="10" />
        <file path="fmri_first_level_proc/rest_conn_first_level.py" lines_changed="18" />
      </files_modified>
      <notes>All three pipelines: replaced local warnings lists with clear_warnings() at entry; converted warnings.append(graded_warning(...)) to bare graded_warning() calls; updated FirstLevelResult construction to use get_warnings(). rest_conn: changed gen_residual_ts() return from tuple[dict, list[dict]] to list[int | None]; removed run_warnings accumulation; updated call site from tuple-unpacking to single-value assignment.</notes>
    </change>
    <change id="C4" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/exceptions.py" lines_changed="6" />
      </files_modified>
      <notes>Added ToolVersionError(FmriFirstLevelError) subclass. Updated ToolUnavailableError docstring to remove version-mismatch mention.</notes>
    </change>
    <change id="C5" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/runtime.py" lines_changed="6" />
      </files_modified>
      <notes>Changed two version-mismatch raise sites (AFNI version mismatch, Python minor-series mismatch) from ToolUnavailableError to ToolVersionError. Updated import and docstring. Kept ToolUnavailableError for probe-failure and unparseable-output cases.</notes>
    </change>
    <change id="C6" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/run_first_level.py" lines_changed="4" />
      </files_modified>
      <notes>Added ToolVersionError to import and exit code 4 except clause. Updated docstring to mention ToolVersionError.</notes>
    </change>
    <change id="C7" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_utils.py" lines_changed="42" />
      </files_modified>
      <notes>Added scale_to_psc() function: 3dTstat -mean for voxelwise mean, 3dcalc min(200,a/b*100)*step(a)*step(b) for PSC conversion. Includes idempotency guard and output verification.</notes>
    </change>
    <change id="C8" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/runtime.py" lines_changed="1" />
      </files_modified>
      <notes>Added "3dTstat" to _AFNI_BINARIES (now 15 binaries).</notes>
    </change>
    <change id="C9" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_config.py" lines_changed="4" />
      </files_modified>
      <notes>Added scale_to_psc: bool = True to ResolvedConfig and resolve_config().</notes>
    </change>
    <change id="C10" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_act_first_level.py" lines_changed="8" />
        <file path="fmri_first_level_proc/task_conn_first_level.py" lines_changed="8" />
        <file path="fmri_first_level_proc/rest_conn_first_level.py" lines_changed="12" />
      </files_modified>
      <notes>Integrated PSC scaling into all three pipelines (after min-outlier EPI, before regression). When enabled, downstream processing uses the PSC-scaled scan. rest_conn: copies scan_paths list before mutation to avoid modifying the original config. All pipelines: PSC output paths added to output_files collection.</notes>
    </change>
    <change id="C11" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/first_level_config.py" lines_changed="18" />
      </files_modified>
      <notes>Replaced extract/extract_labels/extract_stat config fields with stat_buckets: list[str] | None. Replaced VALID_STAT_TYPES with VALID_STAT_BUCKET_TYPES = {"Coef", "Tstat", "Fstat", "R^2", "Zstat"}. Updated validate_config() and resolve_config() for the new schema.</notes>
    </change>
    <change id="C12" status="done" user_decision="n/a">
      <files_modified>
        <file path="fmri_first_level_proc/task_act_first_level.py" lines_changed="120" />
      </files_modified>
      <notes>Replaced extract_effects() with extract_stat_buckets(): discovers all sub-bricks per stat type via 3dinfo, extracts into multi-sub-brick NIfTI via 3dbucket, writes JSON index, optionally writes parcellated CSV. Zstat path converts T-to-Z via fitt_t2z(). Updated run() to call the new function. Removed dead code: valid_extract_labels, _find_subbrik_index, valid_stat_type import. Removed extract-label filtering block (no longer needed). Updated docstring references.</notes>
    </change>
    <change id="C13" status="done" user_decision="n/a">
      <files_modified>
        <file path="example_config.yaml" lines_changed="12" />
      </files_modified>
      <notes>Added scale_to_psc: true to all three analysis blocks. Replaced task_act extraction block: removed extract, extract_labels, extract_stat; added stat_buckets list.</notes>
    </change>
  </changes_applied>
  <summary>
    <total_changes>13</total_changes>
    <completed>13</completed>
    <skipped>0</skipped>
    <blocked>0</blocked>
  </summary>
  <next_steps>Recommended: run /test to validate all changes. Key areas requiring test coverage: (1) warning accumulator pattern (get_warnings/clear_warnings lifecycle), (2) ToolVersionError exception and its exit code mapping, (3) scale_to_psc integration (idempotency, config toggle, path reassignment), (4) extract_stat_buckets (sub-brick discovery, JSON index, parcellated CSV, Zstat T-to-Z conversion, residuals extraction), (5) stat_buckets config validation. Existing tests referencing config.extract, config.extract_labels, or config.extract_stat will need updates to use config.stat_buckets.</next_steps>
</implement_report>
