<implement_plan>
  <meta project="fmri-first-level-proc" mode="implement" submodule="plan" timestamp="2026-08-26T19:55:00Z" />
  <assumptions_without_explicit_approval>
    <assumption id="A1">Labels in the bucket_stats index JSON will be raw AFNI sub-brick labels from `3dinfo -label` (e.g., `stimA#0_Coef`, `Full_Fstat`), not cleaned labels. This preserves the `#N` notation required for AM1/dmBLOCK models (where `#0` = base amplitude, `#1` = parametric modulator) and avoids label collisions. The structural format ({label: index} flat dict) matches the stat_bucket indices; the label content is more detailed because bucket_stats carries multiple stat types per condition. The user approved "keep the format of the {stat}_bucket jsons," which is interpreted as the JSON structure, not the exact label content.</assumption>
    <assumption id="A2">The function uses `3dinfo -label`, which outputs pipe-delimited (`|`) sub-brick labels. This is a standard AFNI flag not previously used in this codebase but consistent with the existing `run_afni_command(capture_output=True)` pattern.</assumption>
    <assumption id="A3">Scope is task_act only. Neither task_conn (beta series via 3dLSS) nor rest_conn (residuals via 3dTproject) produces a `bucket_stats` file.</assumption>
  </assumptions_without_explicit_approval>
  <input_reports>
    <report path="(inline user directive)" mode="conversation" key_items="1" />
  </input_reports>
  <changes>
    <change id="C1" priority="P0" source_item="inline directive: add bucket_stats index JSON">
      <file path="fmri_first_level_proc/task_act_first_level.py" action="modify" />
      <description>Add `generate_bucket_stats_index()` function that creates a JSON index mapping every sub-brick label in the 3dDeconvolve bucket_stats output to its 0-based index. Placed after `_get_subbrik_stat_aux()` and before `extract_stat_buckets()` (between lines 294 and 297).</description>
      <spec>
New function signature:
```python
def generate_bucket_stats_index(config: ResolvedConfig, logger: logging.Logger) -> str:
```

Logic:
1. Construct `bucket_path = f"{config.out_dir}/{config.out_file_pre}_concat_bucket_stats.nii.gz"`.
2. Construct `index_path = os.path.join(config.out_dir, f"{config.out_file_pre}_concat_bucket_stats_index.json")`.
3. Idempotency guard: if `os.path.exists(index_path)`, log and return `index_path` early.
4. Call `run_afni_command(['3dinfo', '-label', bucket_path], capture_output=True, description="3dinfo label for bucket stats index", logger=logger)`.
5. Parse: `labels = [l.strip() for l in info.strip().split('|') if l.strip()]`.
6. Build index: `index_map = {label: i for i, label in enumerate(labels)}`.
7. Write JSON: `with open(index_path, "w") as f: json.dump(index_map, f, indent=2)`.
8. Log: `logger.info("Wrote bucket stats index: %s", index_path)`.
9. Return `index_path`.

No new imports required (`json`, `os`, `run_afni_command`, `ResolvedConfig` are all already imported).
      </spec>
      <dependencies>none</dependencies>
      <risk>low - single new function, no changes to existing logic, uses established patterns (run_afni_command with capture_output, idempotency guard, JSON write)</risk>
      <rollback>Delete the function definition.</rollback>
    </change>
    <change id="C2" priority="P0" source_item="inline directive: wire index generation into run()">
      <file path="fmri_first_level_proc/task_act_first_level.py" action="modify" />
      <description>Call `generate_bucket_stats_index()` in `run()` after `run_first_level()` (line 700) and before the stat_buckets extraction block (line 702). Add the returned path to `output_files` in the output collection block (after line 720).</description>
      <spec>
Insert after line 700 (`run_first_level(stim_data, config, logger)`):
```python
    bucket_stats_index_path = generate_bucket_stats_index(config, logger)
```

In the output file collection block (after line 720 where `resids_path` is checked), add:
```python
    if os.path.exists(bucket_stats_index_path):
        output_files.append(bucket_stats_index_path)
```

This ensures the index is generated unconditionally (whenever bucket_stats exists) and is included in FirstLevelResult.output_files.
      </spec>
      <dependencies>C1</dependencies>
      <risk>low - two line insertions into run(), no modification of existing lines</risk>
      <rollback>Remove the two inserted lines.</rollback>
    </change>
  </changes>
  <execution_order>C1, C2</execution_order>
</implement_plan>
