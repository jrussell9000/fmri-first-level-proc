<implement_plan>
  <meta project="fmri-first-level-proc" mode="implement" submodule="plan" timestamp="2026-10-09T12:00:06-04:00" target_release="4.0.0" />

  <input_reports>
    <report path="fmri-first-level-proc_brainstorm_20261009_112745.md" mode="brainstorm" key_items="68" />
  </input_reports>

  <assumptions_and_resolved_decisions>
    Decisions resolved with the user during this plan (2026-10-09):
    D1. AFNI minimum = validated = 26.0.09.
    D2. qc_summary keeps `hrf_model` for task types (producer {type}-qc); it is added to the AUD-Q key table.
    D3. Lockfile numpy minimum = validated = 2.4.2, pandas minimum = validated = 3.0.1 (base miniforge versions); Python minimum 3.12,
        validated 3.14. /test confirms or updates these on the validation environment.
    D4. task_act smoothing produces _s{N}mm siblings of {pre}_concat_bucket_stats.nii.gz, {pre}_concat_bucket_resids.nii.gz and every
        {ext}_{stat}_bucket.nii.gz; parcel CSVs and index JSONs exist only unsmoothed.
    Planner decisions (implementation-level operationalizations of locked text, stated as directives):
    A1. Ledger paths are stored relative to out_dir (POSIX separators); FirstLevelResult lists are absolute paths.
    A2. run_labels and run_lengths are analysis-block-level config keys (not under paths). smoothing is a nested block
        `smoothing: {enabled, fwhm}`; ResolvedConfig flattens it to smoothing_enabled / smoothing_fwhm.
    A3. Task Mode A per-run keys are the plural names scan_paths, task_timing_paths, motion_paths, CSF_paths, WM_paths (T11-table
        "task_timing_path(s)" etc.); Mode B uses the singular names plus run_lengths.
    A4. task_conn smoothing finals: {pre}_concat_LSS_s{N}mm.nii.gz and {pre}_concat_bseries_{cond}_s{N}mm.nii.gz (mirrors D4); seed-to-voxel
        smoothed maps are the _s{N}mm siblings of each seed map; rest smoothing finals are {pre}_concat_residual_dtseries_s{N}mm.nii.gz and,
        when keep_run_res_dtseries is true, {pre}_run{N}_residual_dtseries_s{N}mm.nii.gz.
    A5. Voxel counts and medians needed by QC are computed with programs already on the locked binary list: 3dTstat, 3dcalc, 3dROIstats
        (-nzvoxels, -median, -nzmedian), 3dinfo (-nijk, -same_grid, -nv, -dmin/-dmax). No nibabel dependency is added.
    A6. roi_coverage.nonzero_fraction = (template-ROI voxels with any nonzero time point in that run of the series entering the model) /
        n_voxels (atlas count).
    A7. The AUD5-5 "identical identity -> GuardError" check applies across distinct producer labels (including per-run instances of a
        stage family); records from a single producer instance are that producer's responsibility.
    A8. The task T4 censor is computed twice inside task-{act,conn}-nuisance: pass 1 over all supplied runs (temporary; drives exclusion),
        pass 2 over S_pre runs only (promoted). With 1d_tool -set_run_lengths the S_pre rows are identical in both passes.
    A9. Expected-path sets (G2(2)) enumerate every final output plus deterministic intermediates; REML_cmd files, 1d_tool side files and
        sequenced-backend intermediates are not enumerated (they remain listed via the ledger and are never retired while listed).
    A10. Test-suite changes (including fixture schema_version updates named in T12b) are performed by /test per the report's action
        items; /implement does not edit tests/ and does not run tests.
    A11. CHANGELOG.md, README.md and INPUT_SPECIFICATION.md prose are written by /document (T12d(2)); /implement updates code-adjacent
        docs only (T12d(1)): module/function docstrings, example_config.yaml, tools.lock.yaml.
  </assumptions_and_resolved_decisions>

  <conventions_for_all_changes>
    G-1. Labels: {type} prefix map {"task_act": "task-act", "task_conn": "task-conn", "rest_conn": "rest-conn"}. Run identity is the
         integer run label; never list position.
    G-2. Every file the package writes into out_dir goes through engine.RunContext.run_step / run_stage (G3 protocol). No module writes
         directly into out_dir. Every AFNI call that writes files runs with cwd = the step staging dir and writes into it.
    G-3. AFNI subprocesses go through first_level_utils.run_afni_command (raises ToolExecutionError with command, description, stderr) or
         first_level_utils.run_afni_capture (never raises on exit status; caller decides).
    G-4. Exception classes (C4/T11-ledger(6)): AFNI-written output fails validation or cannot be parsed -> ToolExecutionError naming file,
         command + description and the failed check; Python-written file missing or not byte-equal -> GuardError; OSError propagates
         unwrapped; invalid user data -> InputError; invalid config -> ConfigError; model infeasible -> ModelError.
    G-5. Graded warnings use first_level_utils.graded_warning with a code from WARNING_CODES and its exact severity.
    G-6. No os.path.exists skip branches anywhere in pipeline code (the ledger is the sole reuse gate).
    G-7. No em-dashes in code, comments or docstrings. Follow existing naming and docstring style (numpy-style docstrings).
    G-8. Do not edit files under tests/. Do not run tests.
  </conventions_for_all_changes>

  <changes>

    <!-- ===================================================================== -->
    <!-- PACKAGING AND METADATA                                                 -->
    <!-- ===================================================================== -->

    <change id="C1" priority="P0" source_item="T12a, T12f, T12g(1), A2, A3">
      <file path="pyproject.toml" action="modify" />
      <description>Release 4.0.0 packaging: version, dependencies with minimums, packaged lockfile, single console script.</description>
      <spec>
        - [project] version = "4.0.0"; requires-python = ">=3.12" (unchanged).
        - dependencies = ["numpy>=2.4.2", "pandas>=3.0.1", "pyyaml", "packaging"] (pyyaml and packaging carry no minimum).
        - [project.scripts]: exactly one entry `fmri-first-level-proc = "fmri_first_level_proc.run_first_level:main"`; delete the
          run-first-level entry.
        - Add:
            [tool.setuptools.package-data]
            fmri_first_level_proc = ["tools.lock.yaml"]
        - Leave [tool.pytest.ini_options] unchanged.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - metadata only.</risk>
      <rollback>git checkout pyproject.toml</rollback>
    </change>

    <change id="C2" priority="P0" source_item="A3">
      <file path="environment.yaml" action="modify" />
      <description>Align conda environment with lockfile minimums.</description>
      <spec>
        dependencies: python>=3.12; numpy>=2.4.2; pandas>=3.0.1; pyyaml; packaging. Keep the header comment block, including the
        AFNI-installed-separately note. Package-name set (excluding python, pip) must equal the pyproject dependency name set
        {numpy, pandas, pyyaml, packaging}.
      </spec>
      <dependencies>none</dependencies>
      <risk>low</risk>
      <rollback>git checkout environment.yaml</rollback>
    </change>

    <change id="C3" priority="P0" source_item="T12f-min, T12g(1), D1, D3">
      <file path="fmri_first_level_proc/tools.lock.yaml" action="create" />
      <file path="tools.lock.yaml" action="delete" />
      <description>Lockfile 2.0.0 as package data with per-tool minimum and validated versions; remove the repository-root lockfile.</description>
      <spec>
        Create fmri_first_level_proc/tools.lock.yaml with exactly:
          lockfile_version: "2.0.0"
          tools:
            afni:
              minimum: "26.0.09"
              validated: "26.0.09"
            python:
              minimum: "3.12"
              validated: "3.14"
            numpy:
              minimum: "2.4.2"
              validated: "2.4.2"
            pandas:
              minimum: "3.0.1"
              validated: "3.0.1"
        Then delete the repository-root tools.lock.yaml (destructive operation: requires explicit per-invocation user permission at
        build time).
      </spec>
      <dependencies>none</dependencies>
      <risk>low - consumers updated in C12 and C25.</risk>
      <rollback>git checkout tools.lock.yaml; delete the package copy.</rollback>
    </change>

    <change id="C4" priority="P0" source_item="T12g(1), T12c, new modules">
      <file path=".gitignore" action="modify" />
      <description>Whitelist the packaged lockfile, CHANGELOG and every new module.</description>
      <spec>
        Replace `!tools.lock.yaml` with `!fmri_first_level_proc/tools.lock.yaml`. Add `!CHANGELOG.md` under "Core pipeline files". Add
        whitelist lines for the new modules: names.py, runsets.py, engine.py, qc.py, events.py, nuisance.py, estimability.py, roi.py,
        prep.py, smoothing.py, connectivity.py (each as `!fmri_first_level_proc/&lt;name&gt;.py`). Keep everything else unchanged.
      </spec>
      <dependencies>none</dependencies>
      <risk>low</risk>
      <rollback>git checkout .gitignore</rollback>
    </change>

    <change id="C5" priority="P1" source_item="DOC-ITEMS 31 (T12f)">
      <file path="fmri_first_level_proc/exceptions.py" action="modify" />
      <description>ToolVersionError docstring to minimum-version wording.</description>
      <spec>
        ToolVersionError docstring: "Installed external tool or library version is below the minimum recorded in the packaged lockfile."
        No other change. FmriFirstLevelError.context stays as is.
      </spec>
      <dependencies>none</dependencies>
      <risk>low</risk>
      <rollback>git checkout the file</rollback>
    </change>

    <!-- ===================================================================== -->
    <!-- FOUNDATION MODULES                                                     -->
    <!-- ===================================================================== -->

    <change id="C6" priority="P0" source_item="T8, T11b, SMOOTH(3), G4(2), A1(1), RUNSETS(4), P4a(2), T11-b, T2(3)">
      <file path="fmri_first_level_proc/names.py" action="create" />
      <description>Single source of every package filename and the smoothing token. Pure functions, no I/O. All other modules build
      paths only through this module (naming-invariant contract).</description>
      <spec>
        Module docstring states: every package-created path in out_dir starts with an analysis prefix ({out_file_pre},
        {extract_out_file_pre} or {conn_out_file_pre}) except staging dirs `.staging_{pre}_{step}`; frozen T8 names are a stable interface.
        Imports: os, decimal.Decimal only.

        Constants (T8 frozen templates):
          TASK_ACT_BUCKET_STATS = "{pre}_concat_bucket_stats.nii.gz"
          TASK_CONN_LSS = "{pre}_concat_LSS.nii.gz"
          REST_CONCAT_RESIDUAL = "{pre}_concat_residual_dtseries.nii.gz"
          TYPE_LABEL = {"task_act": "task-act", "task_conn": "task-conn", "rest_conn": "rest-conn"}
          _EXTENSIONS = (".nii.gz", ".nii", ".x1D", ".1D", ".1d", ".csv", ".json", ".txt", ".REML_cmd")

        Functions (all return file basenames or out_dir-relative paths using "/" separators):
          frozen_primary(analysis_type, pre) -> str               # one of the three constants formatted
          frozen_names(analysis_type, pre) -> set[str]            # {frozen_primary}; never deleted by G2
          smoothing_canonical(fwhm: float) -> str                 # format(Decimal(repr(float(fwhm))).normalize(), "f")
          smoothing_token(fwhm: float | None) -> str              # "" if None else "_s" + canonical.replace(".", "p") + "mm"
          with_token(name: str, token: str) -> str                # insert token immediately before the first matching extension
                                                                   # in _EXTENSIONS (longest match first); "" token returns name
          run_tag(label: int) -> str                              # f"run{label}" (unpadded)
          staging_dir(pre, step) -> str                           # f".staging_{pre}_{step}"
          ledger(pre) -> str                                      # f"{pre}_ledger.jsonl"
          qc_summary(pre) -> str                                  # f"{pre}_qc_summary.json"
          timing_errors(pre) -> str                               # f"{pre}_timing_errors.json"
          min_outlier_epi(pre, label: int | None) -> str          # None -> f"{pre}_min_outlier_epi.nii.gz";
                                                                   # else f"{pre}_run{label}_min_outlier_epi.nii.gz"
          run_mean(pre, label: int | None), run_psc(pre, label: int | None)
                                                                   # None -> f"{pre}_mean.nii.gz" / f"{pre}_psc.nii.gz" (v3.1.0
                                                                   # single-run names); else f"{pre}_run{label}_mean.nii.gz" / _psc
          psc_concat(pre) -> f"{pre}_psc.nii.gz"
          concat_scan(pre) -> f"{pre}_concat_scan.nii.gz"
          run_intersect_mask(pre) -> f"{pre}_run_intersect_mask.nii.gz"
          censor_prefix(pre, label: int | None) -> f"{pre}_concat" | f"{pre}_run{label}"     # 1d_tool prefix
          censor(pre, label) -> censor_prefix + "_censor.1D"
          censor_side_files(pre, label) -> [censor_prefix + "_enorm.1D", censor_prefix + "_CENSORTR.txt"]
          motion_prepared(pre, label: int | None) -> f"{pre}_concat_motion_prepared.1D" | f"{pre}_run{label}_motion_prepared.1D"
          notch_motion(pre, label) -> f"{pre}_run{label}_notch_motion.1D"
          tissue_prepared(pre, tissue) -> f"{pre}_concat_{tissue}_prepared.1D"            # tissue in {"CSF","WM"}
          tissue_deriv(pre, tissue, label: int | None) -> f"{pre}_concat_{tissue}_deriv.1D" | f"{pre}_run{label}_{tissue}_deriv.1D"
          onset_file(pre, cond) -> f"{pre}_concat_{cond}_onsets.txt"
          beta_onsets(pre) -> f"{pre}_concat_beta_onsets.txt"
          preflight_dmat(pre) -> f"{pre}_preflight_dmat.x1D"
          estimability_dmat(pre) -> f"{pre}_estimability_dmat.x1D"
          bseries_dmat(pre) -> f"{pre}_concat_bseries_dmat.x1D"
          reml_cmd(pre, step) -> f"{pre}_{step}.REML_cmd"
          bucket_stats(pre, token="") -> with_token(f"{pre}_concat_bucket_stats.nii.gz", token)
          bucket_resids(pre, token="") -> with_token(f"{pre}_concat_bucket_resids.nii.gz", token)
          bucket_stats_index(pre) -> f"{pre}_concat_bucket_stats_index.json"
          stat_bucket(ext, stat, token="") -> with_token(f"{ext}_{stat}_bucket.nii.gz", token)
          stat_index(ext, stat) -> f"{ext}_{stat}_index.json"
          stat_parcellated(ext, stat) -> f"{ext}_{stat}_parcellated.csv"
          resids_csv(ext) -> f"{ext}_resids.csv"
          lss(pre, token="") -> with_token(f"{pre}_concat_LSS.nii.gz", token);  lss_1d(pre) -> f"{pre}_concat_LSS.1d"
          bseries(pre, cond, token="") -> with_token(f"{pre}_concat_bseries_{cond}.nii.gz", token)
          pbseries(ext, cond) -> f"{ext}_pbseries_{cond}.csv"
          raw_ptseries(ext, label: int | None), raw_psc_ptseries(ext, label: int | None)
                                                                   # None -> f"{ext}_raw_ptseries.csv" / f"{ext}_raw_psc_ptseries.csv"
                                                                   # else f"{ext}_run{label}_raw_ptseries.csv" / _raw_psc_ptseries.csv
          residual_run(pre, label, token="") -> with_token(f"{pre}_run{label}_residual_dtseries.nii.gz", token)
          residual_concat(pre, token="") -> with_token(f"{pre}_concat_residual_dtseries.nii.gz", token)
          residual_ptseries(ext) -> f"{ext}_residual_ptseries.csv"
          sequenced_dir(pre, label) -> f"{pre}_sequenced_intermediates/run{label}"
          template_stem(template_path) -> basename with ".nii.gz" / ".nii" removed
          template_resampled(pre, template_path) -> f"{pre}_{template_stem}_resampled.nii.gz"
          legacy_template_resampled(template_path) -> f"{template_stem}_resampled.nii.gz"   # G4 pre-4.0.0 name
          smoothing_mask(pre) -> f"{pre}_smoothing_mask.nii.gz"
          blurred_run(pre, label: int | None, token) -> with_token(f"{pre}_run{label}_blur.nii.gz" | f"{pre}_blur.nii.gz", token)
          blurred_psc_run(pre, label: int | None, token) -> with_token(run_psc(pre, label), token)
          blurred_concat(pre, token, psc: bool) -> with_token(psc_concat(pre) if psc else concat_scan(pre), token)
          conn_output(conn_pre, condition: str | None, fishZ, pcorr, calc_conn, token="") -> str
              # prefix = conn_pre if condition is None else f"{conn_pre}_{condition}"; parcellated suffix
              # "_pcorr_fishZ_mat.txt" | "_fishZ_mat.txt" | "_pcorr_mat.txt" | "_corr_mat.txt"; seed_to_voxel suffix
              # "_fishZ.nii.gz" | "_corr.nii.gz" (pcorr is rejected for seed_to_voxel at config time); token applied with with_token
          all_prefixes(pre, ext, conn) -> tuple of the non-None prefixes
      </spec>
      <dependencies>none</dependencies>
      <risk>low - pure functions.</risk>
      <rollback>delete the file</rollback>
    </change>

    <change id="C7" priority="P0" source_item="T10, C2, T11b, T6e, C4(2), C4(6), T5b, T4, T11-polort, WARN, G3(2), G3(4), T6d">
      <file path="fmri_first_level_proc/first_level_utils.py" action="modify" />
      <description>Shared utilities updated for 4.0.0: result dataclass with intermediate_files, closed warning-code table, AFNI runner
      with cwd and non-raising capture variant, 3dDeconvolve warning logging, T5b custom-HRF column count, within-run tissue derivatives,
      updated nuisance-filter helpers; removal of functions superseded by new modules.</description>
      <spec>
        Header comment: Version 4.0.0. Module docstring: rewrite the bullet list to the functions that remain.

        KEEP UNCHANGED: dir_path_exists, file_path_exists, valid_string_list, valid_stat_type, valid_ave_type, valid_conn_type,
        setup_logging, get_warnings, clear_warnings, HRF constants (HRF_DURATION_MODELS, HRF_DM_MODELS, HRF_IMPULSE_MODELS,
        VALID_HRF_MODELS, AFNI_MODEL_PREFIXES), needs_married_timing, build_hrf_string, log_hrf_model, log_nuisance_model,
        get_3dinfo_properties, valid_contrast_functions, sanitize_filename_label.

        FirstLevelResult: fields status: str ("success" | "warning"), output_dir: Path, warnings: list[dict], qc_summary: dict,
        output_files: list[str] (final products, absolute paths), intermediate_files: list[str] (every other file the analysis leaves
        on disk, absolute paths). Docstring states the two lists are disjoint and exclude staging dirs and the CLI log file.

        WARNING_CODES: dict[str, str] (code -> severity), exactly:
          CENSOR_HIGH high, COND_DROPPED medium, CONTRAST_DROPPED medium, GS_MISSING low, RUN_SKIPPED high, DISCOVERY_COLLISION medium,
          UNVALIDATED_VERSION medium, LEDGER_ENTRY_UNREADABLE medium, RETIREMENT_FAILED high, NULL_ROI high, SEED_NULL high,
          PCORR_RANK_DEFICIENT high, RUN_FAILED high, RUN_INSUFFICIENT_TRS high, DERIV_RUN_BOUNDARY medium, SMOOTH_FWHM_OFF_TARGET medium,
          SMOOTH_INPUT_ABOVE_TARGET medium.
        graded_warning(logger, severity, code, message, *, user_facing=False): raise GuardError if code not in WARNING_CODES or
          severity != WARNING_CODES[code]; otherwise unchanged behavior and record shape {severity, code, message, user_facing}.
          Docstring: high-severity warnings set FirstLevelResult.status to "warning" and CLI exit code 3.
        reemit_warning(record: dict, logger, prefix: str) -> None: logs at WARNING if record["user_facing"] else INFO the message
          f"{prefix} [{code}] {message}" and appends a shallow copy of record to the accumulator (no table re-check needed beyond the
          same GuardError check).
        warning_count() -> int: len of accumulator (used by engine to slice per-stage warnings).

        run_afni_command(command, capture_output=False, description="", logger=None, cwd=None):
          env = os.environ.copy(); env["AFNI_COMPRESSOR"]="GZIP"; env["AFNI_USE_ERROR_FILE"]="NO"; subprocess.run(command,
          capture_output=True, text=True, check=True, env=env, cwd=cwd). On success, if os.path.basename(command[0]) == "3dDeconvolve"
          call _log_afni_warnings(result.stderr, logger). Return result.stdout if capture_output else the CompletedProcess. On
          CalledProcessError raise ToolExecutionError(f"AFNI command failed ({description}): {' '.join(command)}\n  stderr: ...")
          exactly as v3.1.0 formats it.
        run_afni_capture(command, description="", logger=None, cwd=None) -> subprocess.CompletedProcess: same env and cwd, check=False,
          never raises for nonzero exit; raises ToolExecutionError only if the executable cannot be started (OSError), message naming
          the command and description.
        _log_afni_warnings(stderr: str, logger): split stderr into lines; a block starts at a line containing "*+ WARNING"; continuation
          lines are following lines that do not start with "++", "**", "*+" or " + "; log each block joined with "\n" at WARNING with no
          graded-warning code; no-op when logger is None.

        validate_custom_hrf(custom_hrf, logger) -> int: stage 1 prefix whitelist unchanged (failure -> ConfigError naming custom_hrf and
          listing known models). Stage 2 inside `with tempfile.TemporaryDirectory() as tmp:` write tmp/timing.1D containing "10\n", run
          run_afni_command(["3dDeconvolve", "-nodata", "100", "1", "-polort", "-1", "-num_stimts", "1", "-stim_times", "1",
          "timing.1D", custom_hrf, "-x1D", "hrf_test.x1D", "-x1D_stop", "-nobucket"], description="custom_hrf validation", logger=logger,
          cwd=tmp); a ToolExecutionError is re-raised as ConfigError(f"custom_hrf '{custom_hrf}' failed AFNI validation: ...") from it.
          Return np.loadtxt(os.path.join(tmp, "hrf_test.x1D"), comments="#", ndmin=2).shape[1].

        compute_tissue_derivative(values: np.ndarray, run_lengths: list[int]) -> np.ndarray: pure function; for each run segment the
          first-difference with the first element of the segment set to 0 (np.diff with prepend of the segment's first value), segments
          concatenated. Raise InputError if values is not 1-D or sum(run_lengths) != len(values).
        load_numeric_table(path, what: str) -> np.ndarray: np.loadtxt(path, ndmin=2) wrapped; any read/parse failure -> InputError(f"Cannot
          read {what} file '{path}': {e}"). Used for motion and tissue files.
        format_table(array: np.ndarray, fmt="%.8f") -> str: rows joined with "\n" (trailing "\n"), columns joined with "\t", each value
          formatted with fmt. Python-written 1D text uses this so the engine can verify byte-equality.

        censor_interpolate_1d_afni(input_path, tr, censor_path, out_dir, out_prefix, label, logger): unchanged command; add keyword
          cwd=None passed to both run_afni_command calls; out_dir is the caller's staging location.
        bandpass_filter_1d_afni(input_path, tr, bandpass, out_dir, out_prefix, label, logger, cwd=None): REMOVE "-nodetrend" from the
          3dBandpass command (T11-polort); docstring states 3dBandpass applies its default quadratic detrend, matching the BOLD path.

        build_decon_base_command(input_spec, censor_path, motion_path, ortvecs, run_starts, mask_path, tr) -> list[str]:
          ["3dDeconvolve", "-quiet", "-input", input_spec, "-polort", "A"]
          + (["-concat", "1D: " + " ".join(str(s) for s in run_starts)] if run_starts is not None and len(run_starts) > 1 else [])
          + (["-mask", mask_path] if mask_path else [])
          + ["-censor", censor_path, "-ortvec", motion_path, "motion_regressors"]
          + for (path, name) in ortvecs: ["-ortvec", path, name]
          + ["-TR_times", str(tr), "-local_times"].
        build_decon_nodata_command(total_trs, tr, run_starts, polort) -> list[str]:
          ["3dDeconvolve", "-nodata", str(total_trs), str(tr), "-polort", polort] + (-concat as above when len > 1) + ["-local_times"].

        collect_reml_cmds(staging_dir, pre, step) -> list[tuple[str, str]]: list *.REML_cmd in staging_dir root; unprefixed names
          ("3dDeconvolve.REML_cmd", "Decon.REML_cmd") are renamed (os.replace) to names.reml_cmd(pre, step); more than one unprefixed
          file -> GuardError; returns [(relpath, "reml_cmd")] for every REML_cmd now present (prefixed ones keep their names and must
          start with pre, else GuardError).

        gen_min_outlier_epi(source_path, start, n_vols, out_path, logger, cwd=None) -> dict:
          selector = f"{source_path}[{start}..{start + n_vols - 1}]"; stdout = run_afni_command(["3dToutcount", "-automask",
          "-fraction", "-quiet", selector], capture_output=True, description="3dToutcount min-outlier scan", logger=logger, cwd=cwd);
          parse floats; parse failure or empty -> ToolExecutionError naming the command and the parse error (C4(2)); idx = argmin
          (first minimum); run_afni_command(["3dbucket", "-prefix", out_path, f"{source_path}[{start + idx}]"], description="3dbucket
          min-outlier EPI", logger=logger, cwd=cwd); log TR index and fraction at INFO; return {"tr_index": idx, "fraction": float}.
          No exists-skip.

        DELETE (superseded; do not leave stubs): CENSOR_WARN_THRESHOLD, CENSOR_HIGH_THRESHOLD (move value 50.0 into nuisance as
        CENSOR_HIGH_PCT), validate_extract_options, validate_connectivity_options, remove_files_from_dir, validate_custom_hrf (replaced
        above), validate_onset_file_format, read_and_validate_stim_data, write_onset_file, create_censor_file, check_trial_survival,
        notch_filter_motion, compute_tissue_derivative (replaced above), prepare_motion_file, clean_deconvolve_err, validate_template,
        extract_roi_stats, scale_to_psc, write_qc_summary, compute_dof, build_conn_output_path, compute_matrix_contrast,
        seed_to_voxel_conn, format_netcorr_mat, parcellated_conn.
        Keep imports minimal (remove shutil, StringIO, Path if unused; add tempfile).
      </spec>
      <dependencies>C6</dependencies>
      <risk>medium - many callers change; all callers are rewritten in later changes.</risk>
      <rollback>git checkout fmri_first_level_proc/first_level_utils.py</rollback>
    </change>

    <change id="C8" priority="P0" source_item="T11-ledger, G1, G3, G2(1), AUD5-5(1,5), AUD6-2(2)">
      <file path="fmri_first_level_proc/checkpoint.py" action="modify" />
      <description>Rewrite the ledger module: ledger_format 2 records (staged, completion, retired), full-history reader with unreadable-line
      reporting, hashing helpers. Delete the v3.0.0 DAG lists, resolve_rerun_set, auto_reconstruct_ledger and compute_config_hash.</description>
      <spec>
        Header: Version 4.0.0. Imports: dataclasses, datetime, hashlib, json, os.
        LEDGER_FORMAT = 2
        Record serialization: one JSON object per line, keys sorted, separators (",", ":"), always containing "record_type" and
        "ledger_format": 2. Output entries serialize as {"path": relpath, "class": "final" | "intermediate"}.
          staged:     {"record_type": "staged", "ledger_format": 2, "step": str, "outputs": [...], "timestamp_utc": str}
          completion: {"record_type": "completion", "ledger_format": 2, "step": str, "stage_hash": str, "outputs": [...], "qc": dict,
                       "warnings": [{"code", "severity", "message", "user_facing"}], "versions": dict, "timestamp_utc": str,
                       "wall_clock_s": float}
          retired:    {"record_type": "retired", "ledger_format": 2, "paths": [relpath...], "timestamp_utc": str}
        Dataclasses: OutputRecord(path: str, cls: str); StagedRecord(step, outputs, timestamp_utc); CompletionRecord(step, stage_hash,
        outputs, qc, warnings, versions, timestamp_utc, wall_clock_s); RetiredRecord(paths, timestamp_utc).
        utc_now() -> str ISO-8601 UTC.
        append_record(ledger_path, record) -> None: serialize, open "a", write line + "\n", flush, os.fsync. OSError propagates.
        LedgerHistory dataclass: records: list (parsed records in file order), unreadable_lines: list[int] (1-based).
        read_history(ledger_path) -> LedgerHistory: missing file -> empty history. A line is unreadable (appended to unreadable_lines,
          never raised) if: invalid JSON; ledger_format missing or != 2; record_type unknown; any required key of that record type missing
          or of wrong JSON type (completion requires qc (object) and warnings (array) per AUD5-5(5)).
        latest_completion(history, step) -> CompletionRecord | None; latest_staged(history, step) -> StagedRecord | None (last occurrence).
        recorded_paths(history) -> set[str]: every output path in staged and completion records.
        sha256_file(path) -> str (streamed 1 MiB chunks).
        canonical_json(obj) -> str: json.dumps(obj, sort_keys=True, separators=(",", ":"), default=_jsonable) where _jsonable converts
          tuples/sets to sorted lists only for sets and to lists for tuples; anything else -> TypeError.
        compute_stage_hash(payload: dict) -> str: sha256 of canonical_json(payload).encode("utf-8").
        Module docstring describes the three record types, that completion entries are the sole reuse gate, and that staged records are
        cleanup tracking only (never evidence of content integrity).
      </spec>
      <dependencies>none</dependencies>
      <risk>medium - replaces an unused module; old tests for it are rewritten by /test.</risk>
      <rollback>git checkout fmri_first_level_proc/checkpoint.py</rollback>
    </change>

    <change id="C9" priority="P0" source_item="RUNSETS, T1, A1, AUD5-1, AUD5-2">
      <file path="fmri_first_level_proc/runsets.py" action="create" />
      <description>Run identity and run-set state: supplied runs, S_pre, S_final, K_supplied, K_model, label-to-offset maps, Mode B selectors,
      and the T1 run-structure checks.</description>
      <spec>
        Imports: dataclasses, logging, math; from .exceptions import GuardError, InputError; from .first_level_utils import
        run_afni_command, load_numeric_table.
        @dataclass(frozen=True) class RunInfo: label: int; position: int (0-based acquisition order); n_vols: int; source_path: str;
          start: int (first volume in source_path; 0 for Mode A and rest); property spec -> str: source_path if start == 0 and the run is
          the whole file (Mode A / rest) else f"{source_path}[{start}..{start + n_vols - 1}]".
        class RunSets:
          __init__(self, runs: list[RunInfo], input_mode: str ("A" | "B"), tr: float, grid_ref: str)
          supplied -> tuple[int, ...] (labels in acquisition order); k_supplied -> int
          s_pre / s_final properties: GuardError if read before being set.
          set_s_pre(labels): GuardError if already set, if labels not a subsequence of supplied in acquisition order. Stores tuple.
          set_s_final(labels): GuardError if already set, if s_pre unset, if not a subsequence of s_pre.
          k_model -> len(s_pre)
          run(label) -> RunInfo; runs(labels) -> list[RunInfo]
          run_lengths(labels) -> list[int]; total_vols(labels) -> int
          offsets(labels) -> dict[int, int]: cumulative 0-based start index of each label within the concatenation of `labels` in
            acquisition order.
          run_starts(labels) -> list[int] (offsets in order).
          mode_b_selector(labels) -> str: GuardError unless input_mode == "B"; f"{source}[{a}..{b},{c}..{d}...]" covering the labels'
            volume ranges in acquisition order (single range when all supplied runs are included).
          d_max_seconds() -> float: max(n_vols over supplied) * tr.
        build_runsets(config, analysis_type, logger) -> RunSets (always-run, non-writing):
          labels = config.run_labels (already resolved and validated by config).
          task Mode A (config.scan_paths is not None): per file n_vols = int(3dinfo -nv), source=file, start=0.
          task Mode B: n_vols from config.run_lengths; start = cumulative; source = config.scan_path; InputError if sum(run_lengths) !=
            3dinfo -nv scan_path.
          rest: as Mode A over config.scan_paths.
          T1 checks (InputError naming file and counts): Mode A/rest: motion rows (load_numeric_table) == n_vols per run; tissue rows
            (CSF/WM/GS per-run lists when present) == n_vols; every run 3dinfo -tr equal to the first run's (abs diff &gt; 1e-4 ->
            InputError) and `3dinfo -same_grid first_scan this_scan` first token == "1". Mode B: motion and tissue rows == total volumes.
          grid_ref = first supplied run's source_path.
        Module docstring defines S_pre, S_final, K_supplied, K_model exactly as topic RUNSETS and states that only set_s_pre/set_s_final
        assign the sets (single source).
      </spec>
      <dependencies>C7</dependencies>
      <risk>medium</risk>
      <rollback>delete the file</rollback>
    </change>

    <change id="C10" priority="P0" source_item="AUD-Q, AUD6-1, AUD5-5(3), AUD6-5, D2, A7">
      <file path="fmri_first_level_proc/qc.py" action="create" />
      <description>qc_summary key schema (type, identity, producers, analysis types) and the fragment merge rule.</description>
      <spec>
        Imports: dataclasses, fnmatch, json; from .exceptions import GuardError.
        @dataclass(frozen=True) class QCKeySpec: kind: str ("value" | "records"); identity: tuple[str, ...]; producers: tuple[str, ...]
          (label patterns; "{t}" is replaced by the type label, fnmatch wildcards allowed); types: frozenset[str].
        TASK = {"task_act", "task_conn"}; ALL = TASK | {"rest_conn"}.
        QC_KEYS: dict[str, QCKeySpec], insertion order = output order:
          analysis_type value () ("{t}-qc",) ALL
          hrf_model value () ("{t}-qc",) TASK
          fd_threshold value () ("{t}-qc",) ALL
          censor_prev_tr value () ("{t}-qc",) ALL
          bandpass value () ("{t}-qc",) {"rest_conn"}
          bandpass_backend value () ("{t}-qc",) {"rest_conn"}
          contrast_labels value () ("{t}-qc",) {"task_conn"}
          n_trs_total, n_trs_censored, pct_censored value () ("{t}-nuisance",) ALL
          per_run_censoring records ("run",) ("{t}-nuisance",) {"rest_conn"}
          per_run_dof records ("run",) ("{t}-nuisance",) {"rest_conn"}
          dof value () ("task-act-preflight", "task-conn-estimability") TASK
          trials records ("run", "condition", "onset") ("{t}-estimability",) TASK
          per_condition_trial_counts value () ("{t}-estimability",) TASK
          per_condition_surviving_trials value () ("{t}-estimability",) TASK
          per_condition_run_counts records ("run", "condition") ("{t}-estimability",) TASK
          excluded_runs records ("run",) ("{t}-qc",) ALL
          failed_runs records ("run",) ("rest-conn-residuals-run*", "rest-conn-residuals-concat") {"rest_conn"}
          psc_per_run records ("run",) ("{t}-prep",) ALL
          smoothing_per_run records ("run",) ("task-act-smooth", "task-conn-smooth", "rest-conn-smooth-residuals") ALL
          pcorr_rank_checks records ("condition",) ("{t}-connectivity",) {"task_conn", "rest_conn"}
          null_rois records ("condition", "output") ("{t}-connectivity",) {"task_conn", "rest_conn"}
          null_seed_conditions records ("condition",) ("task-conn-connectivity",) {"task_conn"}
          zero_variance_target_voxels records ("output",) ("{t}-connectivity",) {"task_conn", "rest_conn"}
          roi_coverage records ("run", "roi") ("{t}-roi-qc",) ALL
          low_baseline records ("run", "roi") ("{t}-roi-qc",) ALL
          reused_stages value () ("{t}-qc",) ALL
          retired_outputs value () ("{t}-qc",) ALL
          provenance value () ("{t}-qc",) ALL
        merge_fragments(fragments: list[tuple[str, dict]], analysis_type: str) -> dict:
          for (label, frag) in fragments, for key in frag: unknown key -> GuardError; analysis_type not in spec.types -> GuardError;
          label must match a producer pattern -> else GuardError naming key and label. value kind: a second producer label for the same key
          -> GuardError. records kind: value must be a list of dicts each containing every identity field (None allowed); duplicates of
          identity across different producer labels -> GuardError; concatenate and sort by tuple((v is None, v) for v in identity values).
          Return {key: merged for key in QC_KEYS if key present}.
        qc_json_text(qc: dict) -> str: json.dumps(qc, indent=2, allow_nan=False) + "\n" (allow_nan=False: NaN in QC is a bug -> ValueError
          surfaces; QC producers must emit null instead).
        type_label(analysis_type) -> str via names.TYPE_LABEL (import names).
      </spec>
      <dependencies>C6</dependencies>
      <risk>low</risk>
      <rollback>delete the file</rollback>
    </change>

    <change id="C11" priority="P0" source_item="T11-ledger, G1, G2, G3, G4, C4(1), AUD5-5, AUD5-6(4), AUD6-2(2), AUD6-3, C2(2), T11b">
      <file path="fmri_first_level_proc/engine.py" action="create" />
      <description>Execution engine shared by all pipelines: G4 refusal, ledger-scoped remove_previous, always-run steps and ledgered stages
      under the uniform write protocol, per-stage hashing and reuse with qc/warning replay, list assembly, expected-path cross-check,
      retirement sweep, and the end-of-run order.</description>
      <spec>
        Imports: copy, dataclasses, gzip, logging, os, shutil, time; from pathlib import Path; from . import checkpoint, names, qc;
        from .exceptions import GuardError, InputError, ToolExecutionError; from .first_level_utils import (FirstLevelResult,
        get_warnings, graded_warning, reemit_warning, warning_count, run_afni_command).

        @dataclass class Output:
          relpath: str                 # relative to out_dir and to the staging dir ("/" separators; may include one subdirectory)
          cls: str                     # "final" | "intermediate"
          kind: str                    # "nifti" | "afni_text" | "x1d" | "py_text" | "reml_cmd" | "afni_aux"
          producer: str = ""           # human description of the producing command (used in ToolExecutionError messages)
          expected_text: str | None = None      # py_text: exact file content
          expected_rows: int | None = None; expected_cols: int | None = None    # afni_text / x1d
          expected_nvols: int | None = None     # nifti
          check_grid: bool = True               # nifti: compare grid with RunContext.grid_ref
        @dataclass class StageSpec: label: str; fields: tuple[str, ...] = (); derived_files: tuple[str, ...] = () (absolute paths);
          derived_values: dict = field(default_factory=dict); upstream: tuple[str, ...] = ()
        @dataclass class StepIO: label: str; staging: str (absolute); out_dir: str; pre: str
          path(relpath) -> str: absolute path inside staging (creates parent dirs); out(relpath) -> str: absolute path inside out_dir.
        @dataclass class Outcome: outputs: list[Output] = []; qc: dict = {}; deferred_error: Exception | None = None; reused: bool = False

        class RunContext:
          __init__(self, config, analysis_type, logger, versions: dict, grid_ref: str):
            self.entry_config = copy.deepcopy(config)  (the run()-entry copy used for hashing)
            self.config = config (working copy the pipeline mutates); self.out_dir = os.path.abspath(config.out_dir);
            self.pre = config.out_file_pre; self.type_label = names.TYPE_LABEL[analysis_type]; self.analysis_type = analysis_type
            self.ledger_path = join(out_dir, names.ledger(pre)); self.history = None; self.versions = versions; self.grid_ref = grid_ref
            self.stage_hashes = {}; self.executed = []; self.reused = []; self.failed = {}; self.dag_order = []
            self.step_outputs = {} (label -> list[Output] validated this run); self.stage_outputs = {} (label -> list[OutputRecord])
            self.fragments = [] (list of (label, dict)); self.new_records = [] (records appended this run, for path-set comparisons)

          start(self) -> None:
            1. if ledger file absent: self._refuse_unrecorded() (G4(1)).
            2. if config.remove_previous and ledger present: self._remove_previous() (G3(5)).
            3. self.history = checkpoint.read_history(ledger_path); if history.unreadable_lines: graded_warning(logger, "medium",
               "LEDGER_ENTRY_UNREADABLE", f"Ledger {ledger_path}: unreadable lines {lines}; affected stages rerun.", user_facing=True).
          _refuse_unrecorded(): prefixes = names.all_prefixes(pre, config.extract_out_file_pre, config.conn_out_file_pre); collect top-level
            out_dir entries whose name starts with f"{p}_" for any prefix, or equals names.legacy_template_resampled(template_path) when
            template_path is set, or equals "_sequenced_intermediates"; expand matching directories recursively to their files; exclude
            the CLI log file (any logging.FileHandler.baseFilename attached to logger or its parents) and every path recorded in other
            "*_ledger.jsonl" files in out_dir (checkpoint.recorded_paths of each, joined to out_dir). If any remain: raise InputError with
            count, first 20 paths, "No ledger for analysis '{pre}' records these files (for example, output of an earlier package
            version or a deleted ledger). remove_previous cannot remove them. Use an empty out_dir or remove the listed paths.";
            context {"unrecorded_paths": [...first 20], "count": n}. Never deletes anything.
          _remove_previous(): history = read_history; for rel in sorted(recorded_paths(history)): path = join(out_dir, rel); if exists:
            os.remove; then remove now-empty parent dirs inside out_dir; then shutil.rmtree every out_dir entry named
            names.staging_dir(pre, *) (glob f".staging_{pre}_*"); then os.remove(ledger_path) last. OSError propagates.

          _validate(io, out: Output) -> None (file at io.path(out.relpath)):
            missing file: kind py_text -> GuardError; otherwise ToolExecutionError.
            nifti: full decompress (gzip.open in 1 MiB chunks for .gz; plain read for .nii); then if check_grid: run_afni_command(["3dinfo",
              "-same_grid", grid_ref, path], capture_output=True) first token != "1" -> ToolExecutionError; if expected_nvols:
              int(3dinfo -nv) != expected -> ToolExecutionError. Decompression errors -> ToolExecutionError.
            afni_text / x1d: np.loadtxt(path, comments="#", ndmin=2); parse failure or row/col mismatch vs expected -> ToolExecutionError.
              (Empty file allowed only for afni_aux.)
            afni_aux: file exists and decodes as UTF-8.
            py_text: content (read as text, newline="") == expected_text exactly, else GuardError naming the file.
            reml_cmd: UTF-8, non-empty, contains "3dREMLfit", else ToolExecutionError.
            ToolExecutionError messages: f"Validation failed for {relpath} produced by {producer}: {check}: expected {e}, found {f}".

          _promote(io, outputs) -> list[OutputRecord]: for each output: os.makedirs(dirname(out(rel))); os.replace(io.path(rel), out(rel)).
          _path_set(outputs) -> frozenset((rel, cls)).
          _latest_staged_set(label) -> frozenset from the last staged record for label in history.records + new_records (empty if none).

          run_step(self, label, fn) -> Outcome:   # always-run step (G3(1),(3); C4(1))
            staging = join(out_dir, names.staging_dir(pre, label)); if exists: shutil.rmtree(staging); os.makedirs(staging).
            io = StepIO(label, staging, out_dir, pre); outcome = fn(io) (exceptions propagate; staging is left in place).
            validate every output; if _path_set(outputs) != _latest_staged_set(label): append StagedRecord(label, outputs) to the ledger
            (and new_records); promote; shutil.rmtree(staging); self.step_outputs[label] = outputs; if outcome.qc: fragments.append((label,
            outcome.qc)); if outcome.deferred_error: raise outcome.deferred_error; return outcome.
          stage_hash(self, spec) -> str: payload = {"label": spec.label, "fields": {f: [_jsonable(getattr(entry_config, f)),
            _jsonable(getattr(config, f))] for f in spec.fields}, "derived_files": {p: checkpoint.sha256_file(p) for p in
            spec.derived_files}, "derived_values": spec.derived_values, "upstream": {u: self.stage_hashes[u] for u in spec.upstream},
            "versions": self.versions}; an upstream label not yet run this invocation -> GuardError. _jsonable: tuples -> lists, dicts and
            lists recursively, other values unchanged.
          run_stage(self, spec, fn) -> Outcome:   # ledgered stage (T11-ledger(2))
            dag_order.append(label); h = stage_hash(spec); latest = checkpoint.latest_completion(history, label);
            rerun = latest is None or latest.stage_hash != h or any(not os.path.exists(out(o.path)) for o in latest.outputs) or
                    any(u in self.executed for u in spec.upstream) or bool(latest.qc.get("failed_runs"))
            not rerun: stage_hashes[label] = h; reused.append(label); stage_outputs[label] = latest.outputs; fragments.append((label,
              latest.qc)) if latest.qc; for w in latest.warnings: reemit_warning(w, logger, f"[reused stage {label}]"); log INFO
              f"Reusing stage {label}"; return Outcome(reused=True, qc=latest.qc).
            rerun: staging handling as run_step; n0 = warning_count(); t0 = time.time(); outcome = fn(io) (exceptions propagate, staging
              left); stage_warnings = get_warnings()[n0:]; validate; append StagedRecord; promote; append CompletionRecord(label, h,
              outputs, outcome.qc, stage_warnings, versions, utc_now, elapsed); rmtree staging; stage_hashes[label] = h;
              executed.append(label); stage_outputs[label] = records; fragments.append((label, outcome.qc)) if outcome.qc; return outcome.
          record_stage_failure(self, label, qc: dict) -> None: failed[label] = qc; fragments.append((label, qc)); the label's stage_hash is
            not set (downstream stages must not declare it upstream; pipelines route around failed per-run stages via S_final).
          dag_order excludes failed labels from list assembly.

          finish(self, *, expected: set[str], qc_step_fragment: Callable[[list[str]], dict]) -> FirstLevelResult:   # AUD6-3
            (1) listed: dict rel -> cls. For label in dag_order not in failed: for o in stage_outputs[label]: add. For label, outs in
                step_outputs: add each. Add names.ledger(pre) as intermediate; add names.qc_summary(pre) as final (planned path). A rel
                added twice -> GuardError naming both producers. Every listed rel except qc_summary must exist on disk -> else GuardError.
            (2) cross-check: for rel in expected: if os.path.exists(out(rel)) and rel not in listed -> GuardError("Expected output {rel}
                exists but is not listed; refusing to retire anything").
            (3) sweep: hist = read_history(ledger_path); candidates = recorded_paths(hist) - listed - expected -
                names.frozen_names(analysis_type, pre); for rel in sorted(candidates) where os.path.lexists(out(rel)): try os.remove;
                remove empty parent dirs; log INFO "Retired {rel}"; retired.append(rel); except OSError as e: graded_warning(logger,
                "high", "RETIREMENT_FAILED", f"Could not delete {rel}: {e}; retried next run.", user_facing=True). If retired: append
                RetiredRecord(retired).
            (4) qc: frag = qc_step_fragment(retired) (must include reused_stages=list(self.reused) and retired_outputs=retired);
                merged = qc.merge_fragments(fragments + [(f"{type_label}-qc", frag)], analysis_type); text = qc.qc_json_text(merged);
                run_step(f"{type_label}-qc", lambda io: write text to io.path(names.qc_summary(pre)) and return
                Outcome(outputs=[Output(names.qc_summary(pre), "final", "py_text", producer="qc_summary writer", expected_text=text)])).
                Any exception propagates (retirements already performed stand).
            (5) status = "warning" if any(w["severity"] == "high" for w in get_warnings()) else "success"; return
                FirstLevelResult(status, Path(out_dir), get_warnings(), merged, output_files=sorted(abs paths with cls final),
                intermediate_files=sorted(abs paths with cls intermediate)).
        Module docstring documents the write protocol order (staging -> validate -> staged record -> os.replace -> completion entry), the
        five rerun triggers, reuse replay of qc and warnings, and the end-of-run order.
      </spec>
      <dependencies>C6, C7, C8, C10</dependencies>
      <risk>high - core of the release; every pipeline depends on it.</risk>
      <rollback>delete the file</rollback>
    </change>

    <change id="C12" priority="P0" source_item="T12f, T12f-min, T12g, T12h, BINARIES, D1, D3">
      <file path="fmri_first_level_proc/runtime.py" action="modify" />
      <description>Packaged-lockfile runtime check with minimum enforcement, validated-version warning, per-process probe cache, provenance
      versions, and the 19-binary preflight list. Bypasses removed.</description>
      <spec>
        Imports: importlib.resources, logging, os, re, shutil, subprocess, sys, yaml; from packaging.version import Version, InvalidVersion;
        from .exceptions import ToolUnavailableError, ToolVersionError; from .first_level_utils import graded_warning.
        _AFNI_BINARIES = ["3dDeconvolve", "3dTproject", "3dTstat", "3dBandpass", "3dROIstats", "3dresample", "3dinfo", "3dToutcount",
          "3dbucket", "3dcalc", "3dLSS", "3dTcat", "1d_tool.py", "1dtranspose", "3dAttribute", "1ddot", "3dTcorr1D", "3dBlurToFWHM",
          "3dFWHMx"]   (comment: equals the set of programs passed to run_afni_command / run_afni_capture; 3dNetCorr is a test-only
          dependency; contract-tested)
        LOCKFILE_RESOURCE = "tools.lock.yaml"
        _parse_afni_version unchanged.
        preflight_tool_environments(afni_home=None, logger=None): unchanged logic over the new list; docstring count 19.
        load_lockfile() -> dict: path = importlib.resources.files("fmri_first_level_proc").joinpath(LOCKFILE_RESOURCE); missing, unreadable
          or YAML error -> ToolUnavailableError(f"Packaged lockfile {path} is missing or unparseable: ..."). Validate: lockfile_version ==
          "2.0.0"; tools has afni, python, numpy, pandas each with string minimum and validated; afni values match ^\d+\.\d+\.\d+$;
          python values match ^\d+\.\d+$; numpy/pandas values parse with Version(); any violation -> ToolUnavailableError naming the
          resource path, tool and offending value (T12h(1) format validation).
        _PROBE_CACHE: dict = {}  ;  reset_runtime_cache() -> None clears it (test hook).
        _probe(afni_home) -> dict: if cached return; preflight_tool_environments(afni_home); run [afni or join(afni_home,"afni"), "-ver"]
          with subprocess.run(capture_output, text, timeout=30); any failure -> ToolUnavailableError; version = _parse_afni_version; None
          -> ToolUnavailableError("AFNI version could not be determined from 'afni -ver' output"). numpy.__version__, pandas.__version__,
          python f"{major}.{minor}.{micro}". Cache and return {"afni", "python", "numpy", "pandas"}.
        runtime_check(logger=None, afni_home=None) -> dict:
          lock = load_lockfile(); probed = _probe(afni_home); evaluate on every call (not cached):
          minimums: AFNI tuple(int) &lt; minimum tuple -> ToolVersionError(f"AFNI {v} is below the minimum {m}"); Python (major, minor) &lt;
            minimum -> ToolVersionError; numpy/pandas Version(installed) &lt; Version(minimum) -> ToolVersionError.
          validated: AFNI != validated; Python major.minor != validated; numpy/pandas Version != Version(validated) -> one
            graded_warning(logger, "medium", "UNVALIDATED_VERSION", f"{tool} {installed} differs from the validated version {validated};
            results are produced with an unvalidated version.", user_facing=True) per tool.
          from fmri_first_level_proc import __version__ (lazy import inside the function).
          return {"package_version": __version__, "afni_version": probed afni, "python_version": probed python, "numpy_version": ...,
            "pandas_version": ...}.
        Delete probe_tool_versions, PLACEHOLDER handling and every absent-lockfile path.
        Module docstring: minimum-version policy; validated-version warning; probes cached per process; checks re-evaluated each run().
      </spec>
      <dependencies>C3, C7</dependencies>
      <risk>medium</risk>
      <rollback>git checkout fmri_first_level_proc/runtime.py</rollback>
    </change>

    <!-- ===================================================================== -->
    <!-- DOMAIN MODULES                                                         -->
    <!-- ===================================================================== -->

    <change id="C13" priority="P0" source_item="T2, T6, T12e, AUD6-4b, STEPS">
      <file path="fmri_first_level_proc/events.py" action="create" />
      <description>Events reading (both schemes, both delimiters), run-aware event table, onset validation with the timing-error record, and
      AFNI onset-file text generation.</description>
      <spec>
        Imports: json, logging, math, numpy as np, pandas as pd; from .exceptions import InputError; from . import names.
        read_events_file(path, required_conditions: list[str]) -> pd.DataFrame:
          try parsing the header with sep="\t" and sep=","; a parse is "recognized" if its lower-cased stripped columns contain
          {onset, duration, trial_type} (BIDS) or {condition, onset, duration} (CONDITION scheme). Exactly one delimiter recognized ->
          use it; both or neither -> InputError naming the file and the columns found under each delimiter. BIDS takes precedence when
          a header holds both schemes. Normalize to columns onset (float), duration (float), trial_type (str); keep file row order;
          non-numeric onset/duration -> InputError naming file. Any required condition absent -> InputError listing them. No warnings
          about formats (EVENTS_LEGACY removed). Conditions with zero trials are not an error here.
        tr_index(t: float, tr: float) -> int: math.floor(t / tr + 1e-6).
        @dataclass class EventTable: df (columns: run (int label), condition (str), onset (float, run-local seconds), duration (float),
          events_file (str), seq (int, original order within its file)). Methods: for_runs(labels), conditions().
        @dataclass class TimingCheck: violations: list[dict]; runs: list[dict]
        build_event_table(config, runsets, required_conditions) -> tuple[EventTable, TimingCheck]:
          Mode A: for each supplied run (acquisition order) read config.task_timing_paths[position]; run_end = n_vols * tr; violation if
            onset &lt; 0 ("negative") or onset &gt;= run_end ("at_or_after_run_end"): record {events_file, run: label, run_null_reason: None,
            condition, onset_s, violation}. Rows kept only if valid.
          Mode B: read config.task_timing_path once; total = total_vols(supplied) * tr; violation if onset &lt; 0 or onset &gt;= total with
            run = None, run_null_reason = "outside_concatenated_series"; valid onsets are assigned to the run whose volume range contains
            tr_index(onset, tr); local onset = onset - start_volume * tr.
          runs[] covers every supplied run: {run, events_file, n_vols, run_end_s, n_onsets, min_onset_s, max_onset_s, n_negative,
            n_at_or_after_run_end} (Mode B: events_file = the single file; counts attribute in-range onsets to their run; out-of-range
            onsets are counted only in violations; min/max over the run's in-range onsets, None when the run has none).
        timing_record(analysis_type, input_mode, tr, check) -> dict: {analysis_type, input_mode, tr, violations, runs}.
        timing_error_message(record, record_relpath) -> str: states the number of events files with violations, affected run labels,
          violation counts by type, the record path, and "Onsets inside the run window in the same file may also be wrong; check the
          timing reference, file pairing, units and run order before rerunning."
        onset_rows(event_table, conditions: list[str], model_runs: list[int]) -> list[list[tuple[float, float]]]: one list per model run in
          acquisition order of (onset, duration) for the given conditions; within a run, conditions in the given order and each
          condition's trials ordered by onset (task_conn beta file: conditions in beta_cond_order).
        onset_file_text(rows, married: bool) -> str: one line per model run; a run with no events is the single token "*"; entries
          formatted with repr(float(x)) for onsets and f"{repr(float(o))}*{repr(float(d))}" when married; tokens separated by a single
          space; file ends with "\n".
      </spec>
      <dependencies>C6, C9</dependencies>
      <risk>medium</risk>
      <rollback>delete the file</rollback>
    </change>

    <change id="C14" priority="P0" source_item="T4, T6d, T11-polort, AUD5-3, AUD5-7, AUD6-2(4), STEPS, P4b-corr, WARN">
      <file path="fmri_first_level_proc/nuisance.py" action="create" />
      <description>Always-run nuisance steps: task censor/exclusion/motion/tissue preparation, rest per-run notch/censor/motion and DOF dry
      runs with dof_below_1 exclusion.</description>
      <spec>
        Imports: logging, math, re, numpy as np; from . import names; from .engine import Output, Outcome; from .exceptions import
        InputError, ModelError, ToolExecutionError; from .first_level_utils import (graded_warning, run_afni_command, run_afni_capture,
        load_numeric_table, format_table, compute_tissue_derivative).
        CENSOR_HIGH_PCT = 50.0
        _censor(io, motion6: np.ndarray, run_lengths, prefix_rel, fd, censor_prev_tr, logger) -> np.ndarray: write motion6 with
          format_table to io.path(prefix_rel + "_censor_src.1D") (temporary), run 1d_tool.py -infile src -set_run_lengths n1 ... -censor_motion
          str(fd) io.path(prefix_rel) [-censor_prev_TR] with cwd=io.staging; read the censor with np.loadtxt -> 1-D int array; unreadable
          -> InputError naming the censor file (T6e); delete the temporary src file.
        task_nuisance(io, config, runsets, logger) -> tuple[Outcome, dict]:
          1. Motion per supplied run: Mode A load_numeric_table(config.motion_paths[i], "motion"); Mode B split
             load_numeric_table(config.motion_path) by run lengths. use_cols = 12 if include_motion_derivs else 6; columns &lt; use_cols ->
             InputError.
          2. DERIV_RUN_BOUNDARY (Mode B and include_motion_derivs): for each run start row s (all runs except the first) and i in 0..5:
             d = M[s, i] - M[s-1, i]; if d != 0 and abs(M[s, 6+i] - d) &lt;= 1e-6 * max(1.0, abs(d)): collect (run label, column 7+i). If any:
             one graded_warning medium DERIV_RUN_BOUNDARY listing them and stating derivative columns must be computed within run.
          3. Pass 1 (all supplied runs, temporary prefix "_pass1"): censor; per-run uncensored counts; p = 1 + floor(d_max_seconds / 150);
             excluded = runs with uncensored &lt;= p + 1, each -> graded_warning high RUN_INSUFFICIENT_TRS f"Run {label}: {u} uncensored
             TRs &lt;= {p+1}; run excluded from the model." (user_facing). Delete pass-1 files. If no run remains -> ModelError naming every
             run label and count (after the warnings), context {"excluded_runs": [{"run": l, "reason": "insufficient_uncensored_trs"}]}.
          4. s_pre = remaining labels; runsets.set_s_pre(s_pre).
          5. Pass 2 over S_pre: censor with prefix names.censor_prefix(pre, None) -> outputs censor (afni_text, rows = total S_pre vols,
             cols = 1, intermediate) and side files names.censor_side_files (afni_aux, intermediate); producer "1d_tool.py censor".
          6. Motion prepared: concat S_pre rows, first use_cols columns -> names.motion_prepared(pre, None), py_text via format_table.
          7. Tissue (CSF, WM when provided; Mode A per-run lists, Mode B single file split): concat S_pre rows -> names.tissue_prepared;
             task_act only and use_tissue_derivs: compute_tissue_derivative(prepared, run_lengths(S_pre)) -> names.tissue_deriv(pre, T,
             None). py_text outputs, intermediate.
          8. QC fragment: n_trs_total = total S_pre vols; n_trs_censored; pct_censored = round(100 * censored / total, 2); log per-run
             counts at INFO; pct_censored &gt; CENSOR_HIGH_PCT -> graded_warning high CENSOR_HIGH.
          Return (Outcome(outputs, qc), {"excluded": [{"run", "reason": "insufficient_uncensored_trs"}], "censor_rel", "motion_rel",
            "tissue_rel": {T: rel}, "tissue_deriv_rel": {T: rel}}).
        rest_nuisance(io, config, runsets, logger) -> tuple[Outcome, dict]:
          use_cols = 6 * motion_deriv_degree; n_orts = use_cols + 2 + (1 if GS_paths) + ((2 + (1 if GS_paths)) if use_tissue_derivs).
          For each supplied run (label N, position i):
           a. M = load_numeric_table(motion_paths[i]); cols &lt; use_cols -> InputError.
           b. If notch_filter_band: write first 6 cols temporary src; 3dTproject -polort -1 -dt TR -input src' -stopband lo hi -prefix
              io.path(names.notch_motion(pre, N)) with cwd staging; 1dtranspose to restore rows=TRs (as v3.1.0 notch_filter_motion);
              censor source = notch output; else first 6 columns.
           c. Censor with prefix names.censor_prefix(pre, N) (single run length).
           d. Motion prepared: first use_cols columns -> names.motion_prepared(pre, N) (py_text).
           e. Dry-run DOF. polort P = 2 if bandpass[0] &gt; 0 else 1 + floor(n_vols * tr / 150). Temporary derivative files (CSF, WM, GS
              when present) when use_tissue_derivs. Surrogate: io.path(f"_dof_surrogate_run{N}.1D") containing ONE row of n_vols values
              (np.arange(1, n+1) formatted "%.1f", space-separated).
              Simultaneous backend: cp = run_afni_capture(["3dTproject", "-input", surrogate, "-prefix", io.path(f"_dof_dry_run{N}.1D"),
                "-polort", str(P), "-censor", censor, "-cenmode", "ZERO", "-ort", motion_prepared, "-ort", CSF, "-ort", WM, [-ort GS],
                [-ort derivs...], "-bandpass", lo, hi, "-dt", str(tr)], cwd=staging); text = stdout + stderr; K = int(re.search(r"(\d+)
                stopband regressors", text)); dof = int(re.search(r"==&gt;\s*(-?\d+)\s+D\.O\.F\. left", text)); either missing ->
                ToolExecutionError naming command, description "3dTproject DOF dry run", returncode and stderr. bandpass_dim = None
                (reason "simultaneous_backend"); n_stopband_regressors = K.
              Sequenced backend: cp = run_afni_capture(["3dBandpass", "-dt", str(tr), "-prefix", io.path(f"_dof_bp_run{N}.1D"), lo, hi,
                surrogate]); parse r"nFFT=(\d+)" and r"passband indexes=(\d+)\.\.(\d+)" from stdout+stderr (missing -> ToolExecutionError);
                bandpass_dim = sum over k in a..b of (1 if k == 0 or (nFFT % 2 == 0 and k == nFFT // 2) else 2); dof =
                min(bandpass_dim, n_uncensored) - n_orts; n_stopband_regressors = None (reason "sequenced_backend").
              Delete the dry-run temporaries.
           f. dof &lt; 1 -> graded_warning high RUN_SKIPPED f"Run {N}: DOF={dof} &lt; 1; run excluded." (user_facing); excluded dof_below_1.
           g. per_run_censoring record {run: N, n_trs_total, n_trs_censored, pct_censored}; per_run_dof record {run: N, dof,
              bandpass_dim, bandpass_dim_null_reason, n_stopband_regressors, n_stopband_regressors_null_reason}.
          s_pre = runs with dof &gt;= 1. If empty -> ModelError(f"Every run has DOF &lt; 1: {label: dof, ...}") with context {"excluded_runs":
            [{"run": N, "reason": "dof_below_1"}...]} (raised from the step function, so no file is promoted). Else runsets.set_s_pre.
          Outputs (S_pre runs only): notch motion (afni_text rows n_vols cols 6), censor (afni_text rows n_vols cols 1) and side files
            (afni_aux), motion prepared (py_text); all intermediate. Files of excluded runs stay in staging and are discarded with it.
          QC fragment: n_trs_total / n_trs_censored / pct_censored summed over every supplied run; per_run_censoring and per_run_dof for
            every supplied run; CENSOR_HIGH when pct_censored &gt; 50.
          Return (Outcome, {"excluded": [...dof_below_1], "dof": {N: dof}, "polort": {N: P}, "n_orts": n_orts}).
      </spec>
      <dependencies>C7, C9, C11</dependencies>
      <risk>high - exclusion semantics and dry-run parsing.</risk>
      <rollback>delete the file</rollback>
    </change>

    <change id="C15" priority="P0" source_item="T5, T7a, T6b, AUD-Q trials, C2(2)">
      <file path="fmri_first_level_proc/estimability.py" action="create" />
      <description>x1D parsing, T7a estimability dry run and survival table, T6b floors with condition/contrast drops, T5 matrix-derived DOF
      for task_act (preflight) and task_conn (LSS).</description>
      <spec>
        Imports: logging, re, numpy as np; from . import names; from .engine import Output; from .exceptions import ModelError,
        ToolExecutionError; from .first_level_utils import (run_afni_command, build_decon_nodata_command, build_hrf_string,
        needs_married_timing, HRF_DURATION_MODELS, collect_reml_cmds, graded_warning).
        MIN_SURVIVING_TRIALS = {"task_act": 2, "task_conn": 3}
        parse_x1d(path) -> tuple[np.ndarray, dict]: matrix via np.loadtxt(comments="#", ndmin=2); header dict from lines "# Name = \"...\""
          for ColumnLabels (split on ";" and strip), StimLabels (split on ";"), StimBots and StimTops (ints, whitespace split); malformed
          -> ToolExecutionError naming the file.
        im_columns(header, stim_label) -> list[int]: column indices from StimBots/StimTops of that stim label; absent -> ToolExecutionError.
        estimability_dry_run(io, config, runsets, onset_specs: list[tuple[str, str, str]], logger) -> np.ndarray matrix:
          onset_specs = [(stim_label, onset_file_abs_path, hrf_string)]. cmd = build_decon_nodata_command(total_vols(S_pre), tr,
          run_starts(S_pre), "-1") + ["-num_stimts", str(len(onset_specs))] + per k: ["-stim_times_IM", str(k), path, hrf, "-stim_label",
          str(k), label] + ["-x1D_uncensored", io.path(names.estimability_dmat(pre)), "-x1D_stop", "-nobucket"]; run with cwd=staging;
          returns parse_x1d result.
        compute_estimability(matrix, cols, censor_vec) -> list[tuple[float | None, str | None]]: for column j: den = sum(x^2); den == 0 ->
          (0.0, "no_in_run_support"); num = sum(x[censor == 1]^2); f = num / den; (f, None if f &gt; 0 else "fully_censored").
        build_trials(event_table, conditions, s_pre, column_order, fvalues, analysis_type) -> list[dict]: one record per trial of every
          requested condition in every supplied run: {run, condition, onset (run-local), estimability (float or None), survived (bool),
          reason (None | "run_excluded" | "no_in_run_support" | "fully_censored"), beta_series_position (None)}; trials of runs not in
          S_pre get estimability None, reason run_excluded. task_conn: beta_series_position = 0-based position among the condition's
          surviving trials ordered by (run acquisition order, onset).
        survival_summary(trials, conditions) -> (trial_counts {cond: n}, surviving {cond: n}, run_counts [{condition, run, n_trials,
          n_surviving}] for every supplied run).
        apply_floor(analysis_type, conditions, surviving, contrasts, contrast_labels, logger) -> (kept_conditions, kept_contrasts,
          kept_labels, dropped): floor = MIN_SURVIVING_TRIALS; dropped conditions -> one graded_warning medium COND_DROPPED stating the
          floor and each dropped condition's surviving/total counts; contrasts referencing a dropped condition -> graded_warning medium
          CONTRAST_DROPPED each; no condition kept -> ModelError("No task condition has at least {floor} estimable trials.").
        task_act_preflight_dof(io, config, runsets, onset_files: list[tuple[str, str]] (cond, abs path), censor, motion, ortvecs,
          event_table, logger) -> int: cmd = build_decon_nodata_command(total S_pre vols, tr, run_starts(S_pre), "A") + ["-censor", censor,
          "-ortvec", motion, "motion_regressors"] + ortvecs + ["-num_stimts", C] + per condition k (stim flag "-stim_times_AM1" when
          married else "-stim_times"; HRF string from build_hrf_string with mean duration over the condition's S_pre trials for duration
          models) + ["-x1D", io.path(names.preflight_dmat(pre)), "-x1D_stop", "-nobucket"]; cwd=staging; dof = rows - cols of the x1D;
          dof &lt; 1 -> ModelError("Insufficient degrees of freedom (DOF={dof}) ..."); return dof.
        task_conn_lss_dof(dmat_path) -> int: rows - (number of non-IM columns + 2) where IM columns = im_columns(header, "beta_stims");
          dof &lt; 1 -> ModelError.
        Callers add Output records for the x1D (x1d, intermediate) and for collect_reml_cmds results (reml_cmd, intermediate).
      </spec>
      <dependencies>C7, C9, C11, C13</dependencies>
      <risk>high - IM column mapping and x1D parsing.</risk>
      <rollback>delete the file</rollback>
    </change>

    <change id="C16" priority="P0" source_item="T11-nz, T11-b, AUD5-4, AUD6-1, AUD6-5, T11-lowbase, C4(2), C4(6)">
      <file path="fmri_first_level_proc/roi.py" action="create" />
      <description>Parcel aggregation with roi_zero_handling, template checks and resampling, voxel-count helpers, and the roi-qc
      computations (roi_coverage, low_baseline with record-level nulls).</description>
      <spec>
        Imports: logging, os, re, numpy as np, pandas as pd; from . import names; from .engine import Output; from .exceptions import
        ConfigError, InputError, ToolExecutionError; from .first_level_utils import run_afni_command, get_3dinfo_properties.
        _parse_roistats(stdout, column_regex, description) -> pd.DataFrame: lines split on "\t"; header line = second line; columns
          matching column_regex (e.g. r"^NZMean_(\d+)$") renamed to f"ROI_{label}"; data lines = non-comment lines; any parse error or no
          match -> ToolExecutionError naming the description (C4(2)).
        extract_roi_stats(input_spec, template_path, average_type, roi_zero_handling, logger, cwd=None) -> pd.DataFrame (rows =
          sub-bricks, columns ROI_{label} in template-label order):
          exclude: ["3dROIstats", f"-nz{average_type}", "-nomeanout", "-1Dformat", "-mask", template, input] with column regex
            NZMean_(\d+) or NZMed_(\d+); include + mean: ["3dROIstats", "-1Dformat", "-mask", template, input] regex Mean_(\d+); include +
            median: ["3dROIstats", "-median", "-nomeanout", "-1Dformat", "-mask", template, input] regex Med_(\d+) (strip trailing
            spaces in header tokens).
        count_nonzero_by_roi(mask_spec, data_spec, logger, cwd=None) -> dict[int, int]: 3dROIstats -nomeanout -nzvoxels -1Dformat -mask
          mask data; regex NZcount_(\d+); single sub-brick.
        median_by_roi(mask_spec, data_spec, nonzero_only: bool, logger, cwd=None) -> dict[int, float]: 3dROIstats -nomeanout -nzmedian|-median.
        template_labels(template_path, logger) -> list[int]: keys of count_nonzero_by_roi(template, template) sorted.
        check_template(template_path, scan_ref, force_diff_atlas, conn_types: set[str], logger) -> bool:
          always-run, non-writing replacement for v3.1.0 validate_template checks: 3dinfo properties unavailable -> InputError;
          non-numeric dmax -> InputError (C4(6), was GuardError); non-integer dmax -> InputError; dmax == 0 -> InputError;
          "parcellated" in conn_types and dmax &lt; 2 -> ConfigError; "seed_to_voxel" in conn_types and dmax &gt; 1 -> ConfigError;
          atlas-space mismatch -> InputError unless force_diff_atlas (WARNING log); return 3dinfo -same_grid scan_ref template first
          token == "1".
        resample_template(io, template_path, scan_ref, rel, logger) -> Output: 3dresample -master scan_ref -rmode NN -overwrite -input
          template -prefix io.path(rel) (cwd staging); Output(rel, "intermediate", "nifti", producer "3dresample template").
        nonconstant_mask(io, run_spec, rel, logger) -> str: 3dTstat -max -min -prefix io.path(rel + "_mm.nii.gz") run_spec, then 3dcalc
          -a mm[0] -b mm[1] -expr "step(a-b)" -prefix io.path(rel); temp files; returns abs path (masked voxels of a run, AUD5-4(1)).
        roi_qc(io, config, runsets, labels: list[int], template_resolved, unscaled_spec: Callable[[int], str], model_series_spec:
          Callable[[int], str], mean_volume: Callable[[int], str | None], logger) -> dict:
          tlabels = template_labels; n_vox = count_nonzero_by_roi(template, template).
          For each run label N in labels (all files temporary in staging, removed before return):
            M = nonconstant_mask(unscaled_spec(N)); B = mean_volume(N) or 3dTstat -mean of unscaled_spec(N).
            total_masked = count_nonzero_by_roi(M, M)[1]; NP = 3dcalc -a M -b B -expr "step(a)*not(ispositive(b))" (indicator of
              masked voxels with mean &lt;= 0); nonpos_count = count_nonzero_by_roi(NP, NP).get(1, 0); sentinel_fail = total_masked &gt; 0
              and nonpos_count / total_masked &gt;= 0.25.
            med = median_by_roi(M, B, nonzero_only=False)[1] (brain-mask median, AUD5-4(2)).
            roi_coverage: AM = 3dTstat -absmax of model_series_spec(N); A = 3dcalc -a AM -expr "step(a)"; nz = count_nonzero_by_roi(
              template, A); record {run: N, roi, n_voxels: n_vox[roi], nonzero_fraction: nz.get(roi, 0) / n_vox[roi]}.
            low_baseline per roi: masked_count = count_nonzero_by_roi(template, M); if sentinel_fail: values null, reason
              "nonpositive_baseline"; elif masked_count.get(roi, 0) == 0: null, "no_masked_voxels"; else L = 3dcalc -a M -b B -expr
              f"a*step({0.2*med}-b)" (mean below 0.2 x median); low = count_nonzero_by_roi(template, L).get(roi, 0); V = 3dcalc -a M
              -b B -expr "a*b"; roi_med = median_by_roi(template, V, nonzero_only=True)[roi]; record {run, roi, low_baseline_fraction:
              low / masked_count, median_baseline_ratio: roi_med / med (None with reason nonpositive_baseline if med &lt;= 0),
              low_baseline_null_reason: None}.
          Return {"roi_coverage": [...], "low_baseline": [...]}.
        Docstring documents the definitions (masked voxels, brain-mask median, 20% reporting convention, assumption of brain-masked input).
      </spec>
      <dependencies>C6, C7, C9, C11</dependencies>
      <risk>medium - several AFNI calls per run; formats verified on AFNI 26.0.09.</risk>
      <rollback>delete the file</rollback>
    </change>

    <change id="C17" priority="P0" source_item="T3, T11-psc, AUD5-4, AUD-Q psc_per_run, RUNSETS(5)">
      <file path="fmri_first_level_proc/prep.py" action="create" />
      <description>Prep-stage computations: per-run PSC with psc_per_run QC and the 25% sentinel, task concatenation, Mode A concat_scan,
      run-intersection mask; model-input path helpers.</description>
      <spec>
        Imports: logging; from . import names; from .engine import Output; from .exceptions import InputError; from .first_level_utils
        import run_afni_command; from .roi import count_nonzero_by_roi, nonconstant_mask.
        psc_run(io, input_spec, mean_rel, psc_rel, logger) -> list[Output]: 3dTstat -mean -prefix io.path(mean_rel) input; 3dcalc -a input
          -b mean -expr "min(200,a/b*100)*step(a)*step(b)" -prefix io.path(psc_rel); returns two nifti intermediate outputs
          (expected_nvols for psc = run n_vols).
        psc_qc(io, run_label, input_spec, mean_path, logger) -> dict: temporary 3dTstat -min -max of input; masked = nonconstant_mask;
          counts (count_nonzero_by_roi(masked, indicator)[1]) for: guarded = masked AND (min &lt;= 0 OR mean &lt;= 0); capped = masked AND
          mean &gt; 0 AND max &gt; 2*mean; nonpositive_mean = masked AND mean &lt;= 0; record {run, n_mask_voxels, n_guarded_voxels,
          pct_guarded_voxels, n_capped_voxels, pct_capped_voxels, n_nonpositive_mean_voxels, pct_nonpositive_mean_voxels} with pct =
          round(100 * n / n_mask, 2) (None when n_mask == 0). Sentinel: pct_nonpositive_mean_voxels &gt;= 25.0 -> InputError(f"Run {label}:
          {pct}% of non-constant voxels have temporal mean &lt;= 0 (demeaned input); percent signal change scaling requires positive-baseline
          input. Set scale_to_psc: false for demeaned input.").
        task_prep(io, config, runsets, logger) -> Outcome: labels = S_pre; K_sup = k_supplied.
          PSC on: per run label N -> psc_run with names.run_mean(pre, None if K_sup == 1 else N) / run_psc(...); psc_qc; if K_sup &gt; 1:
            3dTcat -prefix io.path(names.psc_concat(pre)) of the per-run psc files in acquisition order (nifti intermediate,
            expected_nvols = total S_pre vols).
          Mode A and K_sup &gt; 1: 3dTcat unscaled S_pre run files -> names.concat_scan (nifti intermediate).
          K_model &gt; 1: per run 3dTstat -max -min of the series entering the model (psc run file when PSC else unscaled run spec) into temp
            files; 3dcalc with one -a.. letter per run and expr product of ispositive(max_k - min_k) -> names.run_intersect_mask (nifti
            intermediate). Runs beyond 13 letters: chain in groups (3dcalc supports a..z; pair max/min per letter pair).
          Outcome.qc = {"psc_per_run": [...]} when PSC on.
        rest_prep(io, config, runsets, logger) -> Outcome: PSC on: per S_pre label N psc_run with run_mean(pre, N)/run_psc(pre, N) +
          psc_qc; qc psc_per_run. PSC off: returns Outcome([]) (stage still recorded).
        task_model_input(config, runsets, out_dir, token="") -> str (pure): PSC on -> out(with_token(psc_concat or run_psc(pre, None) when
          K_sup == 1, token)); PSC off: Mode A K_sup &gt; 1 -> concat_scan (with token); Mode A K_sup == 1 -> the supplied file (token must
          be "": smoothed variant is names.blurred_run(pre, None, token)); Mode B -> scan_path when S_pre == supplied else
          runsets.mode_b_selector(S_pre); smoothed Mode B / K_sup == 1 handled by smoothing helpers (C18).
        task_mask_path(config, runsets, out_dir) -> str | None: run_intersect_mask path when K_model &gt; 1 else None.
        rest_run_input(config, runsets, out_dir, label) -> str: run_psc(pre, label) when PSC else the supplied file.
      </spec>
      <dependencies>C6, C7, C9, C11, C16</dependencies>
      <risk>medium</risk>
      <rollback>delete the file</rollback>
    </change>

    <change id="C18" priority="P0" source_item="SMOOTH, P4c, AUD-S, AUD5-8, AUD6-2(3), D4, A4">
      <file path="fmri_first_level_proc/smoothing.py" action="create" />
      <description>Smoothing helpers: data-derived mask, per-run 3dBlurToFWHM, ACF FWHM QC via 3dFWHMx, smoothing warnings and
      smoothing_per_run records.</description>
      <spec>
        Imports: logging, re; from . import names; from .engine import Output; from .exceptions import ToolExecutionError; from
        .first_level_utils import run_afni_command, graded_warning; from .roi import count_nonzero_by_roi.
        smoothing_mask(io, unscaled_specs: list[str], rel, logger) -> Output: per spec 3dTstat -max -min (temp); 3dcalc product of
          ispositive(max-min) over runs (same grouping rule as the T3 mask) -> io.path(rel); nifti intermediate.
        blur(io, input_spec, mask_path, fwhm, out_rel, logger) -> Output: run_afni_command(["3dBlurToFWHM", "-FWHM",
          names.smoothing_canonical(fwhm), "-ACF", "-mask", mask_path, "-input", input_spec, "-prefix", io.path(out_rel)], cwd=staging).
        acf_fwhm(io, spec, mask_path, detrend: bool, logger) -> float: cmd ["3dFWHMx", "-mask", mask_path] + (["-detrend"] if detrend else
          []) + ["-acf", "NULL", "-input", spec]; stdout lines with exactly four floats; the ACF line is the last such line; value =
          4th float; no such line -> ToolExecutionError naming command, purpose "ACF FWHM estimate" and stdout/stderr.
        mask_stats(mask_path, logger) -> (n_voxels, fov_fraction): n = count_nonzero_by_roi(mask, mask)[1]; total = int(3dinfo -nijk);
          fov = n / total.
        qc_record(label, fwhm, fin, fout, n_mask, fov, logger) -> dict: {run, fwhm_target_mm: float(fwhm), acf_fwhm_input_mm: fin,
          acf_fwhm_output_mm: fout, mask_n_voxels, mask_fov_fraction}; abs(fout - fwhm) &gt; 0.1 * fwhm -> graded_warning medium
          SMOOTH_FWHM_OFF_TARGET (run label, achieved, target); fin &gt; fwhm -> graded_warning medium SMOOTH_INPUT_ABOVE_TARGET.
        Docstring: smoothing feeds only voxelwise outputs; parcel-level stages never consume smoothed data; automask is never used.
      </spec>
      <dependencies>C6, C7, C11, C16</dependencies>
      <risk>medium</risk>
      <rollback>delete the file</rollback>
    </change>

    <change id="C19" priority="P0" source_item="C1 (connectivity), T6c, T11-nz, T7b, T6e, AUD-Q connectivity keys">
      <file path="fmri_first_level_proc/connectivity.py" action="create" />
      <description>Parcellated connectivity via 3dROIstats + 1ddot with rank gate, partial correlation, Fisher Z clip and null-ROI NaN
      handling; seed-to-voxel via 3dTcorr1D + 3dcalc clipped atanh with null-seed and zero-variance target handling; contrasts.</description>
      <spec>
        Imports: logging, os, re, numpy as np, pandas as pd; from . import names; from .engine import Output; from .exceptions import
        InputError, ToolExecutionError; from .first_level_utils import run_afni_command, graded_warning, format_table; from .roi import
        extract_roi_stats, count_nonzero_by_roi.
        R_CLIP = 0.999329
        parse_1ddot(stdout) -> (corr np.ndarray, inv np.ndarray): blocks introduced by "++ Correlation Matrix:" and "++ Correlation Matrix
          Inverse:" (not "Inverse Normalized"); each block: skip the index header and dashed line; rows "NN: v v ..." until a blank line;
          malformed -> ToolExecutionError.
        rank_check(series) -> (m, rank, n): X centered by column; s = np.linalg.svd(X.astype(np.float64), compute_uv=False); tol = s.max()
          * max(n, m) * np.finfo(np.float32).eps; rank = int((s &gt; tol).sum()).
        matrix_text(mat) -> str: tab-delimited rows, values f"{v:.8f}" or "NaN"; trailing "\n".
        parcellated(io, input_spec, template, average_type, roi_zero_handling, fishZ, pcorr, out_rel, condition, logger) -> tuple[Output |
          None, dict]:
          df = extract_roi_stats(...) (time x ROI_label); labels from column names; null = columns with np.ptp == 0; write non-null
          columns to io.path("_series.1D") (format_table "%.9g"); stdout = run_afni_command(["1ddot", series], capture_output=True,
          description="1ddot parcellated correlation", cwd=staging); corr, inv = parse_1ddot.
          pcorr: (m, rank, n) = rank_check(full df including null columns); record pcorr_rank_checks {condition, n_rois: m, rank,
            n_timepoints: n, skipped: rank &lt; m}; rank &lt; m -> graded_warning high PCORR_RANK_DEFICIENT (m, rank, n, condition) and
            return (None, qc) ; else vals = -inv_ij / sqrt(inv_ii inv_jj), diagonal +1.
          not pcorr: vals = corr.
          fishZ: vals = arctanh(clip(vals, -R_CLIP, R_CLIP)) (diagonal becomes 4.0 after clipping).
          Full matrix over all labels (label order) with NaN rows and columns (diagonal included) for null labels; nulls -> graded_warning
            high NULL_ROI listing labels and record null_rois {condition, output: basename(out_rel), rois: [labels]}.
          Write matrix_text to io.path(out_rel); Output(out_rel, "final", "py_text", expected_text=text). qc: {"pcorr_rank_checks": [..]
          when pcorr, "null_rois": [..] when nulls}.
        seed_to_voxel(io, seed_input_spec, target_spec, seed_mask, average_type, roi_zero_handling, fishZ, out_rel, condition, logger)
          -> tuple[Output | None, dict, bool]:
          seed = extract_roi_stats(seed_input_spec, seed_mask, ...)["ROI_1"]; np.ptp(seed) == 0 -> graded_warning high SEED_NULL
            (condition or "rest") and return (None, {"null_seed_conditions": [{"condition": condition}]} if condition else {}, True).
          write seed to io.path("_seed.1D") (one column); 3dTcorr1D -pearson -prefix io.path("_r.nii.gz") target seed (cwd staging);
          3dTstat -stdev -absmax target -> temp; zero-variance in-mask indicator 3dcalc -a sd -b absmax -expr "step(b)*iszero(a)";
          n_zero = count_nonzero_by_roi(indicator, indicator).get(1, 0); r_clean = 3dcalc -a r -b sd -expr "a*step(b)"; fishZ: 3dcalc -a
          r_clean -expr f"atanh(max(-{R_CLIP},min({R_CLIP},a)))" -prefix io.path(out_rel) else r_clean written to io.path(out_rel).
          Output(out_rel, "final", "nifti"); qc {"zero_variance_target_voxels": [{"output": basename(out_rel), "n_voxels": n_zero}]}.
          Return (output, qc, False). Nonzero exits of 3dROIstats, 1ddot, 3dTcorr1D or 3dcalc propagate as ToolExecutionError (C1(1)).
        matrix_contrast(paths, coefs, out_rel, io) -> Output: np.loadtxt(delimiter="\t") each (NaN preserved); shapes must match ->
          InputError; weighted sum; matrix_text; py_text final.
        seed_contrast(io, paths, coefs, out_rel, label, logger) -> Output: 3dcalc with letters a..z (more than 26 -> InputError naming the
          contrast) and expr built as v3.1.0 gen_conn_contrasts; nifti final.
      </spec>
      <dependencies>C6, C7, C11, C16</dependencies>
      <risk>high - numerical equivalence to the KI-005 contract tests (1e-3 tolerance).</risk>
      <rollback>delete the file</rollback>
    </change>

    <!-- ===================================================================== -->
    <!-- CONFIG AND DISCOVERY                                                   -->
    <!-- ===================================================================== -->

    <change id="C20" priority="P0" source_item="P2-2, P3-1, P4-2, P2-1, A1(2)">
      <file path="fmri_first_level_proc/bids.py" action="modify" />
      <description>Discovery returns per-run lists with integer run ordering and explicit labels for every per-run slot; template slot and
      unused BIDS output helpers removed.</description>
      <spec>
        Module docstring: "BIDS derivative input discovery for per-run slots." (remove output-path and dataset-description text).
        Imports: dataclasses, glob, logging, os, re; from .exceptions import InputError; from .first_level_utils import graded_warning.
        Delete build_bids_output_path, write_dataset_description, _ENTITY_ORDER, the json import and the sanitize_filename_label import.
        RUN_RE = re.compile(r"(^|_)run-(\d+)(_|\.)")
        @dataclass class DiscoveredInputs: scan_paths, motion_paths, task_timing_paths, CSF_paths, WM_paths, GS_paths: list[str] | None;
          run_labels: dict[str, list[int | None]] (per slot, aligned with that slot's list); source_dirs: dict[str, str]. Docstring: every
          per-run slot is a list (length 1 for a single run); template_path is never discovered (global config key only).
        discover_inputs(derivatives_dirs, subject, session, task, analysis_type, logger=None) -> DiscoveredInputs:
          slot table for all types: scan_paths (preproc, bold, .nii.gz), motion_paths (confounds, regressors, .tsv), CSF_paths (CSF,
          timeseries, .1D), WM_paths (WM, timeseries, .1D), GS_paths (GS, timeseries, .1D; rest only), task_timing_paths (None, events,
          .tsv; task types only). First directory with matches wins; later matches -> DISCOVERY_COLLISION medium (unchanged).
          Per slot (P2-2): label each file by RUN_RE on basename; InputError listing the files when the slot mixes labeled and unlabeled
          files, has two or more unlabeled files, or two files share a label; order labeled files by integer label; single unlabeled
          file -> labels [None].
        _glob_bids_files unchanged except returning unsorted (ordering is done by label).
      </spec>
      <dependencies>C7</dependencies>
      <risk>medium</risk>
      <rollback>git checkout fmri_first_level_proc/bids.py</rollback>
    </change>

    <change id="C21" priority="P0" source_item="T9, T1, A1, T10, T12b, T5b, T6c, P4c, SMOOTH(2), T11-nz, P2-2, P3-1, P4-2, T11-ledger(4), C6">
      <file path="fmri_first_level_proc/first_level_config.py" action="modify" />
      <description>Closed config schema with aggregate unknown-key errors, multi-run task inputs (Mode A / Mode B), run labels, smoothing and
      zero-handling blocks, merge-then-validate discovery, absolute paths, schema_version 4.0.0.</description>
      <spec>
        Header/docstring: Version 4.0.0; schema overview updated with the new keys.
        Constants (module level, introspectable):
          VALID_TYPES, VALID_STAT_BUCKET_TYPES, VALID_AVE_TYPES, VALID_CONN_TYPES unchanged; VALID_ROI_ZERO_HANDLING = {"exclude", "include"}.
          TOP_KEYS = {"global", "analyses"}; GLOBAL_KEYS = {"tr", "num_cores", "template_path", "force_diff_atlas", "derivatives_dirs"};
          GLOBAL_ONLY_KEYS = ("num_cores", "template_path", "force_diff_atlas", "tr").
          _COMMON = {"name", "type", "out_dir", "out_file_pre", "paths", "average_type", "fd_threshold", "censor_prev_tr",
            "remove_previous", "scale_to_psc", "run_labels", "smoothing", "roi_zero_handling", "derivatives_dirs", "subject", "session",
            "task", "extraction"}
          BLOCK_KEYS = {"task_act": _COMMON | {"hrf_model", "custom_hrf", "include_motion_derivs", "use_tissue_derivs", "run_lengths",
            "cond_labels", "contrasts"}, "task_conn": _COMMON | {"hrf_model", "custom_hrf", "include_motion_derivs",
            "use_tissue_derivs", "run_lengths", "cond_beta_labels", "connectivity"}, "rest_conn": _COMMON | {"bandpass",
            "notch_filter_band", "motion_deriv_degree", "use_tissue_derivs", "use_sequenced_bandpass", "keep_run_res_dtseries",
            "connectivity"}}
          PATH_KEYS = {"task_act"/"task_conn": {"scan_path", "scan_paths", "task_timing_path", "task_timing_paths", "motion_path",
            "motion_paths", "CSF_path", "CSF_paths", "WM_path", "WM_paths"}, "rest_conn": {"scan_paths", "motion_paths", "CSF_paths",
            "WM_paths", "GS_paths"}}
          EXTRACTION_KEYS = {"task_act": {"stat_buckets", "extract_out_file_pre", "extract_resids", "extract_raw_ptseries"},
            "task_conn": {"extract_pbseries", "extract_out_file_pre", "extract_raw_ptseries"}, "rest_conn": {"extract_ptseries",
            "extract_out_file_pre", "extract_raw_ptseries"}}
          CONNECTIVITY_KEYS = {"task_conn": {"calc_conn", "conn_out_file_pre", "pcorr", "fishZ", "contrasts"}, "rest_conn": {"calc_conn",
            "conn_out_file_pre", "pcorr", "fishZ"}}
          CONTRAST_KEYS = {"functions", "labels"}; SMOOTHING_KEYS = {"enabled", "fwhm"}
          LEGACY_EXTRACTION_KEYS = {"extract", "extract_labels", "extract_stat"}
          allowed_keys(analysis_type) -> frozenset[str]: dotted names of every accepted key including nested ("paths.scan_path",
            "extraction.stat_buckets", "connectivity.contrasts.functions", "smoothing.fwhm", "contrasts.labels" for task_act).
          EXEMPT_FIELDS = frozenset({"num_cores", "remove_previous", "schema_version", "analysis_type", "analysis_name", "out_dir",
            "out_file_pre", "derivatives_dirs", "force_diff_atlas"})
        ResolvedConfig: docstring states the schema_version policy (T12b: MAJOR.MINOR.0 of the package release in which the config schema,
          ResolvedConfig fields and YAML validation rules, last changed; removal/rename/meaning change/validation tightening ship only in a
          package major; additions bump minor at the package minor that adds them; patch always 0), replacing "additive-growth".
          Fields: keep all v3.1.0 fields; add scan_paths/task_timing_paths/motion_paths/CSF_paths/WM_paths usage for task Mode A (the
          existing rest fields are shared), run_lengths: list[int] | None = None, run_labels: list[int] | None = None,
          smoothing_enabled: bool = False, smoothing_fwhm: float | None = None, roi_zero_handling: str = "exclude", task_timing_paths:
          list[str] | None = None. Property input_mode -> "A" if scan_paths is not None else "B" (rest always "A").
        validate_config(raw, logger) -> dict:
          Pass 1 (aggregate): unknown top-level, global and block keys (by type), unknown nested keys in paths/extraction/connectivity/
          contrasts/connectivity.contrasts/smoothing, legacy extraction keys (message naming stat_buckets as the replacement),
          GLOBAL_ONLY_KEYS inside a block, missing or invalid 'type' (that block's remaining keys skipped) -> one ConfigError listing every
          problem as "analyses[{idx}] ({name}).{dotted.key}: {reason}".
          Pass 2 (fail-fast, as v3.1.0 plus): global.tr; per block required keys (task: paths unless discovery, out_dir, out_file_pre,
          cond_labels | cond_beta_labels, average_type, hrf_model, include_motion_derivs, fd_threshold; rest: + bandpass,
          motion_deriv_degree); explicit path existence (InputError) for every provided path (singular or list entries); enums;
          bandpass/notch/fd/motion_deriv_degree checks unchanged; HRF checks unchanged plus T5b: task_conn with hrf_model "custom" and
          validate_custom_hrf(...) column count != 1 -> ConfigError naming custom_hrf and the count and listing GAM, BLOCK, SPMG1,
          TWOGAMpw; task_act custom HRF still validated (count unused); contrasts parity; extraction rules (stat_buckets values;
          extract_out_file_pre required when stat_buckets/extract_raw_ptseries/extract_pbseries/extract_ptseries; extract_resids,
          extract_raw_ptseries, extract_pbseries, extract_ptseries require global template_path -> ConfigError); connectivity: calc_conn
          enum; calc_conn requires conn_out_file_pre and template_path; pcorr with calc_conn "seed_to_voxel" -> ConfigError naming the
          parcellated-only restriction; roi_zero_handling in VALID_ROI_ZERO_HANDLING; smoothing (P4c) when smoothing.enabled is true:
          fwhm required; checks in order: not bool; int or float (not string); math.isfinite; &gt; 0; at most two decimals via
          Decimal(repr(float(v))).as_tuple().exponent &gt;= -2 (comment: relies on shortest round-trip repr) -> ConfigError(f"smoothing.fwhm
          {v!r}: ..."); smoothing.enabled must be bool; run_lengths list of positive ints; run_labels list of unique non-negative ints
          (duplicates -> ConfigError); out_dir creation; duplicate (out_dir, out_file_pre) pairs; global template_path existence.
        resolve_config(validated_block, global_cfg, logger) -> ResolvedConfig:
          Build fields; T10: os.path.abspath every path (paths.* singular and list entries, out_dir, template_path, derivatives_dirs).
          Discovery (P4-2): when derivatives_dirs is set and subject is present, discover_inputs; merge slot by slot (explicit wins); a
          slot discovered for a task analysis fills the plural Mode A field.
          Mode checks on the merged result (P4-2(B2)): task: singular and plural forms of the same slot both set -> ConfigError; run_lengths
            with any plural field -> ConfigError; Mode B (scan_path set): every other slot must be singular, run_lengths required, run_labels
            required with len == len(run_lengths); Mode A (scan_paths set): every per-run slot list has len == len(scan_paths), run_lengths
            forbidden. Violations name the conflicting fields and the remedy text from P4-2(B2). Tier-3 mandatory slots per mode ->
            InputError naming slot and derivatives_dirs.
          Run labels (A1(2)): Mode B -> run_labels only; Mode A and rest -> run_labels if given, else discovery labels of the scan slot
            (when every entry is an int), else the run- entity parsed by RUN_RE from every scan basename; any run without a label ->
            ConfigError naming run_labels; duplicates -> ConfigError; run_labels given and discovery labels present -> must be equal in
            integer order (InputError). Mode A: every per-run slot file whose basename carries a run- entity must equal the run's label ->
            InputError naming file and label. P3-1(3) (Mode A): every populated per-run slot carries exactly the scan slot's label set
            (discovered slots compared by their labels) -> InputError naming slot and missing/extra labels; GS all-or-none.
          Stored: run_labels (list[int]), run_lengths, smoothing_enabled/fwhm (fwhm as float), roi_zero_handling (default "exclude"),
          schema_version="4.0.0".
        load_and_validate(config_path, logger=None, **overrides): raw = load_config; merge overrides into every raw analysis block BEFORE
          validate_config (T9); then validate, resolve each block.
      </spec>
      <dependencies>C6, C7, C20</dependencies>
      <risk>high - user-facing schema; breaking by design.</risk>
      <rollback>git checkout fmri_first_level_proc/first_level_config.py</rollback>
    </change>

    <!-- ===================================================================== -->
    <!-- PIPELINES                                                              -->
    <!-- ===================================================================== -->

    <change id="C22" priority="P0" source_item="T1-T7a, T8, T11-table (task_act), STEPS, SMOOTH, P4a, AUD6-1, AUD6-2, AUD6-3, P7-1, D2, D4">
      <file path="fmri_first_level_proc/task_act_first_level.py" action="modify" />
      <description>Rewrite the task activation pipeline on the engine: always-run steps, ledgered stages with T11-table declarations,
      smoothing branch, roi-qc, expected-path enumeration and qc step fragment.</description>
      <spec>
        Module docstring (T12d(1)): replace the v3.1.0 argparse-style INPUTS/OUTPUTS block with: inputs (Mode A / Mode B, run_labels,
        smoothing, roi_zero_handling); FINAL outputs ({pre}_concat_bucket_stats.nii.gz [frozen], {pre}_concat_bucket_resids.nii.gz,
        {pre}_concat_bucket_stats_index.json, {ext}_{stat}_bucket.nii.gz, {ext}_{stat}_index.json, {ext}_{stat}_parcellated.csv,
        {ext}_resids.csv, {ext}_raw_ptseries.csv, {ext}_raw_psc_ptseries.csv, min-outlier EPI (single or run-labeled), _s{N}mm siblings
        of the bucket stats, residuals and stat buckets, {pre}_qc_summary.json, {pre}_timing_errors.json on timing failure);
        INTERMEDIATE outputs (ledger, mean/psc volumes, concat_scan, run_intersect_mask, resampled template, smoothing mask, smoothed
        inputs, onset files, preflight and estimability design matrices, REML_cmd files, censor and side files, prepared motion, tissue
        prepared/derivative files); always-run and ledgered step order.
        Imports: copy, json, logging, numpy as np, pandas as pd; from . import names, events, nuisance, estimability, prep, roi,
        smoothing; from .engine import RunContext, StageSpec, Outcome, Output; from .runsets import build_runsets; from .runtime import
        runtime_check; from .exceptions import ConfigError, GuardError, InputError, ModelError, ToolExecutionError; from
        .first_level_utils import (FirstLevelResult, clear_warnings, setup_logging, run_afni_command, build_hrf_string,
        needs_married_timing, build_decon_base_command, collect_reml_cmds, valid_contrast_functions, gen_min_outlier_epi, log_hrf_model,
        log_nuisance_model, HRF_DURATION_MODELS).
        Keep _get_subbrik_stat_aux but on ToolExecutionError raise GuardError(...) from e preserving the message (T6e) instead of
        returning []. Keep generate_bucket_stats_index logic as a function writing into a StepIO path (py_text final output) without the
        exists-skip. Rework extract_stat_buckets into extract_stat_bucket_niftis(io, bucket_path, stat_types, ext, token, logger) ->
        (outputs, matched: dict[stat, list[(label, idx)]]) (3dbucket / T-to-Z as v3.1.0, temporaries in staging) and
        stat_bucket_parcellations(io, ext, matched, bucket_out_paths, template, average_type, roi_zero_handling, logger) -> outputs (CSV
        py_text final; index JSON py_text final).
        run(config, logger=None) -> FirstLevelResult:
          1. logger default; config = copy.copy(config); clear_warnings(); versions = runtime_check(logger).
          2. Contrast checks (labels/functions pairing) and valid_contrast_functions against config.cond_labels (ConfigError).
          3. runsets = build_runsets(config, "task_act", logger); ctx = RunContext(config, "task_act", logger, versions, runsets.grid_ref);
             ctx.start(). log_hrf_model; log_nuisance_model.
          4. Template checks (always-run, non-writing) when config.template_path is set and any template-reading output is configured
             (stat_buckets with template, extract_resids, extract_raw_ptseries): same_grid = roi.check_template(template, grid_ref,
             force_diff_atlas, {"extract"}, logger).
          5. Step task-act-events: event table over cond_labels (events.build_event_table); violations -> Outcome(outputs=[timing record
             py_text final], deferred_error=InputError(message, context=record)); else Outcome([]).
          6. Step task-act-nuisance: nuisance.task_nuisance (sets S_pre). excluded = its result.
          7. Step task-act-estimability: temp onset files per condition in cond_labels for S_pre runs (onset_rows/onset_file_text, married
             per HRF) written in staging (never outputs); estimability_dry_run with stim labels = condition names and each condition's
             HRF string; IM columns per condition via im_columns(header, cond); f_j with the promoted censor vector; trials, summary,
             apply_floor (floor 2) -> config.cond_labels, config.contrast_functions, config.contrast_labels updated (working copy);
             outputs: estimability_dmat (x1d intermediate) + collect_reml_cmds; qc {trials, per_condition_trial_counts,
             per_condition_surviving_trials, per_condition_run_counts}.
          8. Step task-act-onsets: final onset files for surviving conditions over S_pre runs (py_text intermediate), byte-identical to the
             temporary copies.
          9. Step task-act-preflight: estimability.task_act_preflight_dof (ortvecs: CSF/WM prepared and derivatives when present) ->
             outputs preflight_dmat (x1d intermediate) + REML_cmd; qc {"dof": dof}.
          10. Ledgered stages (in this order; skip when not configured):
            a. task-act-template (when template used): fields ("template_path",), derived_values {"template_sha256": sha256(template),
               "scan_grid": grid_ref-derived 3dinfo -orient/-ad3/-nijk string, "same_grid": same_grid}; same_grid false ->
               roi.resample_template -> names.template_resampled; resolved template path = resampled out path or template_path.
            b. task-act-prep: fields (scan_path, scan_paths, run_lengths, run_labels, scale_to_psc), derived {"s_pre": list(S_pre)};
               prep.task_prep.
            c. task-act-min-outlier-epi: fields (scan_path, scan_paths, run_lengths, run_labels), derived {"s_final": S_final}; per run
               gen_min_outlier_epi(source, start, n_vols, io.path(names.min_outlier_epi(pre, None if K_supplied == 1 else N))); nifti
               final outputs (expected_nvols 1).
               Before this stage: runsets.set_s_final(S_pre).
            d. task-act-raw-ptseries (extract_raw_ptseries): fields (extract_raw_ptseries, extract_out_file_pre, template_path,
               average_type, roi_zero_handling, scan_path, scan_paths, run_labels, scale_to_psc), derived {"s_pre", "template_resolved"},
               upstream (task-act-prep, task-act-template); unscaled series = Mode A concat_scan / single file / Mode B selector of S_pre;
               extract_roi_stats -> names.raw_ptseries(ext, None) (py_text final via df.to_csv()); scale_to_psc -> PSC series
               (task_model_input) -> raw_psc_ptseries.
            e. task-act-glm: fields (scan_path, scan_paths, run_lengths, run_labels, tr, hrf_model, custom_hrf, cond_labels,
               contrast_functions, contrast_labels, task_timing_path, task_timing_paths, motion_path, motion_paths,
               include_motion_derivs, fd_threshold, censor_prev_tr, CSF_path, CSF_paths, WM_path, WM_paths, use_tissue_derivs), derived
               files (final onset files, censor, motion prepared, tissue prepared/deriv), derived {"s_pre"}, upstream (task-act-prep,);
               command = build_decon_base_command(task_model_input, censor, motion, ortvecs, run_starts(S_pre), task_mask_path, tr) +
               ["-num_stimts", C] + per condition stim flag/onset file/HRF/-stim_label + GLTs (as v3.1.0) + ["-errts",
               io.path(bucket_resids), "-fout", "-rout", "-tout", "-bucket", io.path(bucket_stats), "-jobs", num_cores]; cwd staging;
               outputs bucket_stats (nifti final), bucket_resids (nifti final), REML_cmd(s), bucket_stats_index (py_text final from
               3dinfo -label).
            f. task-act-extract (stat_buckets or extract_resids): fields (stat_buckets, extract_resids, extract_out_file_pre,
               average_type, roi_zero_handling, template_path), derived {"template_resolved"}, upstream (task-act-glm, task-act-template
               when present); extract_stat_bucket_niftis from out_dir bucket stats (token ""); parcellations when template; resids CSV
               when extract_resids.
            g. Smoothing (smoothing_enabled): token = names.smoothing_token(fwhm).
               task-act-smooth: fields (smoothing_enabled, smoothing_fwhm, scan_path, scan_paths, run_lengths, run_labels,
                 scale_to_psc), derived {"s_pre"}, upstream (task-act-prep,); mask from unscaled S_pre runs (smoothing.smoothing_mask);
                 per run blur(unscaled run spec) -> names.blurred_run(pre, label|None, token); QC 3dFWHMx with -detrend on the unscaled
                 input and the blurred output; PSC on: psc_run on the blurred run -> names.blurred_psc_run; concat (K_supplied &gt; 1) ->
                 names.blurred_concat(pre, token, psc); all intermediate; qc {"smoothing_per_run": [...]}.
               task-act-glm-smooth: fields = task-act-glm fields + (smoothing_enabled, smoothing_fwhm, stat_buckets,
                 extract_out_file_pre); same derived files; upstream (task-act-smooth,); same command with the smoothed model input and
                 outputs bucket_stats(pre, token), bucket_resids(pre, token) (nifti final), REML_cmd; when stat_buckets:
                 extract_stat_bucket_niftis on the smoothed bucket with token (nifti final; no index JSON, no CSV).
            h. task-act-roi-qc (template used): fields (template_path, roi_zero_handling, scan_path, scan_paths, run_lengths, run_labels,
               scale_to_psc), derived {"s_pre", "template_resolved"}, upstream (task-act-template, task-act-prep); roi.roi_qc over
               S_pre with unscaled spec, model series spec (per-run PSC file or unscaled), mean volume (prep run_mean when PSC).
          11. expected = task_act_expected(config, runsets, ...): every final output above for the surviving conditions/contrasts and
              configured options (including _s{N}mm siblings), plus deterministic intermediates (prep volumes, concat_scan, mask,
              resampled template when produced, smoothing intermediates, onset files, censor, motion and tissue files, design matrices).
          12. return ctx.finish(expected=expected, qc_step_fragment=lambda retired: {"analysis_type": "task_act", "hrf_model":
              hrf_model if not custom else f"custom ({custom_hrf})", "fd_threshold", "censor_prev_tr", "excluded_runs": nuisance
              excluded records, "reused_stages": ctx.reused, "retired_outputs": retired, "provenance": {package_version,
              schema_version, afni_version, python_version, numpy_version, pandas_version}}).
        Every stage function reads from config only its declared fields (plus exempt fields); derived values are passed as arguments.
        No stage or step uses os.path.exists to skip work.
      </spec>
      <dependencies>C6-C19, C21</dependencies>
      <risk>high - full pipeline rewrite.</risk>
      <rollback>git checkout fmri_first_level_proc/task_act_first_level.py</rollback>
    </change>

    <change id="C23" priority="P0" source_item="T1-T7b, T8, T11-table (task_conn), STEPS, SMOOTH, C1, T6c, P4a, AUD6-1, P7-1, A4">
      <file path="fmri_first_level_proc/task_conn_first_level.py" action="modify" />
      <description>Rewrite the task connectivity pipeline on the engine: events, nuisance and onset steps, design matrix, estimability with
      LSS DOF, beta series with survival-based composition, parcel beta series, connectivity and contrasts, smoothing branch, roi-qc.</description>
      <spec>
        Module docstring rewritten as in C22 for task_conn outputs (FINAL: {pre}_concat_LSS.nii.gz [frozen], {pre}_concat_LSS.1d,
        {pre}_concat_bseries_{cond}.nii.gz, {pre}_concat_bseries_dmat.x1D, {ext}_pbseries_{cond}.csv, connectivity matrices/maps and
        contrasts, raw/raw_psc ptseries, min-outlier EPI, _s{N}mm siblings of LSS, bseries and seed maps, qc_summary, timing_errors;
        INTERMEDIATE as task_act plus beta_onsets and the design-matrix REML_cmd).
        Imports as C22 plus connectivity.
        run(config, logger=None):
          1-4 as C22 (template conn types: {"extract"} for pbseries/raw ptseries, {calc_conn} for connectivity).
          5. task-conn-events over every condition in the events files (cond_beta_labels required present).
          6. task-conn-nuisance (no derivative files; nuisance.task_nuisance with task_conn semantics).
          7. task-conn-onsets: beta_cond_order = cond_beta_labels ordered by first appearance in the event table sorted by (run acquisition
             order, onset); nuisance onset files for every non-beta condition present in the event table; beta onset file with all
             trials of beta conditions per S_pre run row, conditions in beta_cond_order and chronological within condition; all py_text
             intermediate. Store the ordered (run, condition, onset) beta sequence (IM column order).
          8. task-conn-template, task-conn-prep (as C22 with task_conn labels).
          9. task-conn-design-matrix: fields (scan_path, scan_paths, run_lengths, run_labels, tr, hrf_model, custom_hrf,
             cond_beta_labels, task_timing_path, task_timing_paths, motion_path, motion_paths, include_motion_derivs, fd_threshold,
             censor_prev_tr, CSF_path, CSF_paths, WM_path, WM_paths, use_tissue_derivs), derived files (all onset files, censor,
             motion prepared, tissue prepared), derived {"s_pre", "beta_cond_order"}, upstream (task-conn-prep,); tissue derivatives
             within run (compute_tissue_derivative with run_lengths(S_pre)) -> names.tissue_deriv(pre, T, None) py_text intermediate;
             3dDeconvolve base (input = task_model_input, -concat, -mask when K_model &gt; 1, -local_times) + nuisance stim conditions
             (-stim_times / -stim_times_AM1 per HRF) + ["-stim_times_IM", k, beta_onsets, hrf, "-stim_label", k, "beta_stims", "-x1D",
             io.path(bseries_dmat), "-x1D_stop", "-nobucket", "-jobs", num_cores]; outputs dmat (x1d final), REML_cmd renamed to
             {pre}_task-conn-design-matrix.REML_cmd.
          10. task-conn-estimability step: dof = estimability.task_conn_lss_dof(dmat); T7a dry run with the single beta onset file
              (stim label "beta_stims"); IM columns mapped to the ordered beta sequence; trials (beta_series_position per condition),
              summary, apply_floor (floor 3; contrasts are connectivity contrasts); outputs estimability_dmat + REML_cmd; qc {dof,
              trials, per_condition_trial_counts, per_condition_surviving_trials, per_condition_run_counts}.
          11. runsets.set_s_final(S_pre); task-conn-min-outlier-epi and task-conn-raw-ptseries as C22.
          12. task-conn-beta-series: fields (cond_beta_labels, scan_path, scan_paths, run_labels), derived {"s_pre", "survival":
              {cond: [IM column indices of surviving trials in (run, onset) order]}}, upstream (task-conn-design-matrix,); 3dLSS -matrix
              dmat -input task_model_input [-mask] -save1D io.path(lss_1d) -prefix io.path(lss) (cwd staging); per surviving condition
              3dcalc -a f"{lss}[i,j,...]" -expr a -prefix bseries(pre, cond); non-finite check: 3dinfo -dmin -dmax on each bseries
              (either value not finite -> GuardError naming condition and file); outputs lss (nifti final), lss_1d (afni_aux final),
              bseries per condition (nifti final).
          13. task-conn-pbseries (extract_pbseries): fields (extract_pbseries, extract_out_file_pre, average_type, roi_zero_handling,
              template_path), derived {"template_resolved", "conditions"}, upstream (task-conn-beta-series, task-conn-template); one CSV
              per condition (py_text final).
          14. Smoothing (enabled): task-conn-smooth (as C22 task-act-smooth with task_conn labels; QC with -detrend);
              task-conn-beta-series-smooth: fields = beta-series fields + (smoothing_enabled, smoothing_fwhm), same derived, upstream
              (task-conn-smooth, task-conn-design-matrix); 3dLSS on the smoothed model input -> lss(pre, token) and bseries(pre, cond,
              token) (nifti final).
          15. task-conn-connectivity (calc_conn): fields (calc_conn, conn_out_file_pre, pcorr, fishZ, template_path, roi_zero_handling,
              contrast_functions, contrast_labels, average_type), derived {"template_resolved", "conditions"}, upstream
              (task-conn-beta-series, task-conn-template) plus task-conn-beta-series-smooth when smoothing and seed_to_voxel; per surviving
              condition: parcellated -> connectivity.parcellated(bseries file, ...) -> names.conn_output(conn, cond, fishZ, pcorr,
              "parcellated"); seed_to_voxel -> connectivity.seed_to_voxel(seed input = unsmoothed bseries, target = unsmoothed bseries)
              and when smoothing a second map with target = smoothed bseries and token. No condition yields a matrix/map -> ModelError.
              Contrasts: only over conditions whose output exists in this stage; matrix_contrast (parcellated) or seed_contrast (seed
              maps, and their _s{N}mm siblings when smoothing) named names.conn_output(conn, sanitize_filename_label(label), ...).
              qc fragment merges the per-condition connectivity qc records.
          16. task-conn-roi-qc as C22.
          17. finish with expected = task_conn_expected(...) and qc fragment {"analysis_type": "task_conn", "hrf_model", "fd_threshold",
              "censor_prev_tr", "contrast_labels" (when contrasts run), "excluded_runs", "reused_stages", "retired_outputs", "provenance"}.
        Remove TRIALS_FEW logic, check_trial_survival use, total_used counter, and all os.path.exists skip branches.
      </spec>
      <dependencies>C6-C19, C21</dependencies>
      <risk>high - full pipeline rewrite.</risk>
      <rollback>git checkout fmri_first_level_proc/task_conn_first_level.py</rollback>
    </change>

    <change id="C24" priority="P0" source_item="T6d, T11-polort, T11-table (rest_conn), AUD5-1, AUD5-3, AUD5-6, P4d, SMOOTH, C1, T11-raw, AUD6-1, AUD6-2, P7-1">
      <file path="fmri_first_level_proc/rest_conn_first_level.py" action="modify" />
      <description>Rewrite the resting-state pipeline on the engine: nuisance step with DOF exclusion, per-run or concatenated residual
      stages with run_failed handling, S_final, concat, raw ptseries, min-outlier EPI, smoothing of residuals, parcel time series,
      connectivity, roi-qc.</description>
      <spec>
        Module docstring rewritten (inputs; FINAL: {pre}_concat_residual_dtseries.nii.gz [frozen], {pre}_run{N}_residual_dtseries.nii.gz
        when keep_run_res_dtseries, {ext}_residual_ptseries.csv, {ext}_run{N}_raw_ptseries.csv and _raw_psc_ptseries.csv,
        {pre}_run{N}_min_outlier_epi.nii.gz, connectivity outputs, _s{N}mm siblings, qc_summary; INTERMEDIATE: ledger, run mean/psc,
        notch/censor/side/motion files, derivative files, resampled template, smoothing mask, sequenced intermediates when kept, REML none).
        Remove the "bandpass subsumes polynomial detrending" claims (L40-41 equivalents) and document per-context polort.
        Simultaneous residual for one run (function _residual_simultaneous(io, config, label, run_input, censor, motion, tissue, polort,
        out_rel, logger)): ["3dTproject", "-input", run_input, "-dt", tr, "-censor", censor, "-cenmode", "ZERO", "-ort", motion, "-ort",
        CSF, "-ort", WM, [-ort GS], [-ort derivatives], "-polort", str(polort), "-bandpass", lo, hi, "-prefix", io.path(out_rel)]; cwd
        staging; derivatives via compute_tissue_derivative(values, [n]) written to names.tissue_deriv(pre, T, label) (py_text
        intermediate) in per-run mode, temporary in concat mode. The dead `if config.bandpass is not None` guard is gone (bandpass
        always required).
        Sequenced residual (_residual_sequenced(...)): v3.1.0 flow with intermediates under io.path(names.sequenced_dir(pre, label)),
        3dBandpass without -nodetrend (BOLD and 1D via bandpass_filter_1d_afni), -polort -1 in NTRP and final regression, post-step 3dcalc
        a*b with the censor; failures raise ToolExecutionError (no None returns). Per-run mode with keep_run_res_dtseries true: the
        intermediates are outputs (intermediate class, kinds nifti / afni_text); otherwise temporary.
        run(config, logger=None):
          1. logger; config copy; clear_warnings; versions = runtime_check(logger); path-list length guard as v3.1.0; GSR log / GS_MISSING
             low warning unchanged.
          2. runsets = build_runsets(config, "rest_conn", logger); ctx = RunContext(...); ctx.start(); template checks when template used
             (conn types {"extract"} for ptseries/raw ptseries, {calc_conn} for connectivity).
          3. Step rest-conn-nuisance: nuisance.rest_nuisance (sets S_pre; ModelError when every run has DOF &lt; 1).
          4. rest-conn-template (when template used), rest-conn-prep (fields scan_paths, scale_to_psc, run_labels; derived {"s_pre"}).
          5. Residuals:
             Per-run mode (keep_run_res_dtseries true): for N in S_pre: stage rest-conn-residuals-run{N}: fields (tr, bandpass,
               notch_filter_band, motion_deriv_degree, fd_threshold, censor_prev_tr, use_tissue_derivs, use_sequenced_bandpass,
               keep_run_res_dtseries); derived files (censor, motion prepared, notch motion of run N); derived values {"run_label": N,
               "scan": scan_paths[i], "motion": motion_paths[i], "CSF": CSF_paths[i], "WM": WM_paths[i], "GS": GS_paths[i] or None,
               "polort": P_N, "scale_to_psc": scale_to_psc}; upstream (rest-conn-prep,); output names.residual_run(pre, N) (nifti final,
               expected_nvols n_vols) plus derivative and sequenced intermediates. On ToolExecutionError from the stage: graded_warning
               high RUN_FAILED f"Run {N}: {e}"; ctx.record_stage_failure(label, {"failed_runs": [{"run": N, "error": str(e)}]}); continue.
               S_final = S_pre minus failed. Empty -> ToolExecutionError(f"All runs failed regression; runs excluded for DOF &lt; 1: ...")
               with context {"excluded_runs": [...dof_below_1 and run_failed records]} (AUD5-3(2)).
               runsets.set_s_final(S_final). Stage rest-conn-concat: fields (tr, keep_run_res_dtseries), derived {"s_final"}, upstream the
               residuals-run{N} stages for N in S_final; ["3dTcat", "-TR", str(tr), "-prefix", io.path(residual_concat), *the
               S_final run residual files in out_dir in acquisition order] (v3.1.0 flags) -> residual_concat (nifti final).
             Concat mode (keep_run_res_dtseries false): stage rest-conn-residuals-concat: fields = union of the per-run fields; derived
               files = all S_pre runs' censor/motion/notch files; derived values {"s_pre", per-run entries, polort per run}; upstream
               (rest-conn-prep,); inside: per S_pre run in subdirectory run{N}/ of staging, catch ToolExecutionError per run ->
               RUN_FAILED high + failed record; S_final = successes; none -> raise ToolExecutionError (as above; no completion entry);
               3dTcat S_final run residuals -> residual_concat (nifti final); qc {"failed_runs": [...]} (empty list when none: emit
               key only when non-empty). After the stage (executed or reused): S_final = S_pre minus the stage's failed runs (from the
               returned qc) -> runsets.set_s_final.
          6. rest-conn-raw-ptseries (extract_raw_ptseries): fields (extract_raw_ptseries, extract_out_file_pre, template_path,
             average_type, roi_zero_handling, scan_paths, run_labels, scale_to_psc), derived {"s_final", "template_resolved"}, upstream
             (rest-conn-prep, rest-conn-template); per S_final run: unscaled from the supplied file -> raw_ptseries(ext, N); PSC ->
             raw_psc_ptseries(ext, N) from run_psc(pre, N).
          7. rest-conn-min-outlier-epi: fields (scan_paths, run_labels), derived {"s_final"}; per S_final run
             names.min_outlier_epi(pre, N).
          8. Smoothing (enabled): rest-conn-smooth-residuals: fields (smoothing_enabled, smoothing_fwhm, scan_paths, run_lengths,
             run_labels), derived {"s_final"}, upstream (rest-conn-concat or rest-conn-residuals-concat); mask from unscaled supplied
             scans of S_final runs; offsets over S_final; per run blur f"{residual_concat}[a..b]" -> names.residual_run(pre, N, token)
             (final when keep_run_res_dtseries else temporary); 3dTcat -> names.residual_concat(pre, token) (nifti final); QC without
             -detrend; qc smoothing_per_run.
          9. rest-conn-ptseries (extract_ptseries): fields (extract_ptseries, extract_out_file_pre, average_type, roi_zero_handling,
             template_path), derived {"template_resolved"}, upstream (residual concat stage, rest-conn-template); residual_ptseries CSV.
          10. rest-conn-connectivity (calc_conn): fields (calc_conn, conn_out_file_pre, pcorr, fishZ, template_path, roi_zero_handling,
              average_type), derived {"template_resolved"}, upstream (residual concat stage, rest-conn-template) plus
              rest-conn-smooth-residuals for seed_to_voxel with smoothing; parcellated on the concat residual: a skipped pcorr matrix
              (rank deficient) -> ModelError; seed_to_voxel: null seed -> ModelError; smoothed target map with token when smoothing.
          11. rest-conn-roi-qc: fields (template_path, roi_zero_handling, scan_paths, run_lengths, run_labels, scale_to_psc), derived
              {"s_final", "template_resolved"}, upstream (rest-conn-template, rest-conn-prep) and placed after the residual stages.
          12. finish: expected = rest_expected(...) (S_pre-derived for nuisance/prep files; S_final-derived for residual run files,
              raw ptseries, min-outlier, smoothed residual run files); qc fragment {"analysis_type": "rest_conn", "fd_threshold",
              "censor_prev_tr", "bandpass", "bandpass_backend": "sequenced" if use_sequenced_bandpass else "simultaneous",
              "excluded_runs" (dof_below_1 from nuisance + run_failed), "reused_stages", "retired_outputs", "provenance"}.
        Delete _generate_run_residual_* None-return paths, gen_residual_ts, compute_dof use, os.path.exists skips, shutil cleanup of
        _sequenced_intermediates, and the per-run psc output_files loop.
      </spec>
      <dependencies>C6-C19, C21</dependencies>
      <risk>high - full pipeline rewrite with failure semantics.</risk>
      <rollback>git checkout fmri_first_level_proc/rest_conn_first_level.py</rollback>
    </change>

    <!-- ===================================================================== -->
    <!-- ENTRY POINTS AND EXAMPLES                                              -->
    <!-- ===================================================================== -->

    <change id="C25" priority="P0" source_item="A2, T12g(3), T12h, C4(4)">
      <file path="fmri_first_level_proc/run_first_level.py" action="modify" />
      <description>Single CLI entry point; runtime check from the packaged lockfile; alias and lockfile bypass removed.</description>
      <spec>
        Header Version 4.0.0. Module docstring: delete the _main_deprecated section and the run-first-level mention (L39-41, L105-106
        equivalents); exit-code table unchanged plus a line that OSError and unexpected exceptions exit 1.
        Imports: replace `from .runtime import preflight_tool_environments, probe_tool_versions` with `from .runtime import runtime_check`;
        remove graded_warning import if unused; delete _LOCKFILE_PATH.
        main() -> None (no cli_name parameter): parse args as before; logger = setup_logging(...); inside try: runtime_check(logger)
        (replaces preflight + probe + LOCKFILE_ABSENT branch); rest unchanged (config load, --analyses selection, plan logging, dry run,
        dispatch, exit 3 on high warnings, exception mapping unchanged).
        Delete _main_deprecated and the CLI_DEPRECATED branch.
      </spec>
      <dependencies>C12, C21, C22, C23, C24</dependencies>
      <risk>low</risk>
      <rollback>git checkout fmri_first_level_proc/run_first_level.py</rollback>
    </change>

    <change id="C26" priority="P0" source_item="T12a">
      <file path="fmri_first_level_proc/__init__.py" action="modify" />
      <description>Package version 4.0.0.</description>
      <spec>__version__ = "4.0.0". Public API unchanged (load_and_validate, ResolvedConfig, setup_logging, FirstLevelResult,
      graded_warning, get_warnings, clear_warnings, DISPATCH, ToolVersionError, __version__); pipeline run imports unchanged.</spec>
      <dependencies>C25</dependencies>
      <risk>low</risk>
      <rollback>git checkout the file</rollback>
    </change>

    <change id="C27" priority="P1" source_item="T12d(1), A2, T12e, DOC-ITEMS 37">
      <file path="example_config.yaml" action="modify" />
      <description>Example config for 4.0.0.</description>
      <spec>
        Usage lines use `fmri-first-level-proc --config ...` (no run-first-level). task_act example in Mode B (scan_path, motion_path,
        task_timing_path + run_lengths: [300, 300] + run_labels: [1, 2]) with a commented Mode A alternative (scan_paths, motion_paths,
        task_timing_paths lists); task_conn example in Mode A with run_labels; rest example with run_labels: [1, 2]. Every block gains
        `roi_zero_handling: "exclude"` and `smoothing: {enabled: false, fwhm: null}` with comments (voxelwise outputs only; _s{N}mm
        siblings; fwhm at most two decimals). Timing comment: events files may use BIDS (onset, duration, trial_type) or CONDITION/ONSET/
        DURATION columns, tab- or comma-delimited; no "legacy" or "deprecated" wording. Remove `pcorr` comment implying seed support.
        The file must validate under the C21 closed schema (with placeholder paths it fails only on file existence).
      </spec>
      <dependencies>C21</dependencies>
      <risk>low</risk>
      <rollback>git checkout example_config.yaml</rollback>
    </change>

  </changes>

  <execution_order>
    C1, C2, C3, C4, C5, C6, C7, C8, C9, C10, C11, C12, C13, C16, C17, C14, C15, C18, C19, C20, C21, C22, C23, C24, C25, C26, C27
  </execution_order>

  <build_notes>
    - Parallelizable groups (non-overlapping files, dependencies satisfied): {C1, C2, C3, C4, C5, C6, C8}; then {C7}; then {C9, C10, C12};
      then {C11}; then {C13, C16, C20}; then {C14, C17, C18, C19}; then {C15, C21}; then {C22, C23, C24}; then {C25}; then {C26, C27}.
    - The build is large (27 changes, more than 5 files); worktree isolation is recommended for the build submodule.
    - Every existing test that imports a deleted function will fail until /test redesigns the suite (A10). /test must also cover every
      test enumerated in the brainstorm report topics and the contract tests (T12d(3a-d), T11-ledger(4), BINARIES, WARN, STEPS, AUD-Q
      producers, RUNSETS single source, naming invariant).
  </build_notes>
</implement_plan>
