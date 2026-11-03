# Pipeline Harmonization Investigation: Interim Report

**Date**: 2026-10-17
**Scope**: Cross-project alignment audit of the full fMRI processing pipeline
**Method**: Independent full-code read of all five projects (no reports, memory, or prior findings consulted)
**Status**: Investigation complete; findings presented below; no action taken yet

## Projects Audited

| Project | Location | Role in pipeline |
|---|---|---|
| fmri-bids-recon | ~/bids-recon | DICOM-to-BIDS reconstruction |
| fmri-preproc | <local_path>/fmri-preproc | Preprocessing (motion correction, SDC, normalization, confound extraction) |
| fmri-first-level-proc | <local_path>/fmri-first-level-proc | First-level analysis (activation, connectivity) |
| fmri-proc-orchestrator | <local_path>/fmri-proc-orchestrator | General-purpose pipeline orchestrator (bids-recon -> preproc -> first-level) |
| ABCD_fmri_orchestrator_S3 | <local_path>/ABCD_fmri_orchestrator_S3 | ABCD-specific orchestrator (preproc -> first-level on S3) |

## Part 1: ABCD_fmri_orchestrator_S3 and fmri-first-level-proc v4.0.0 Alignment

### Verified aligned

| Interface point | ABCD orchestrator | fmri-first-level-proc v4.0.0 | Status |
|---|---|---|---|
| `load_and_validate` import | `first_level_config.load_and_validate` | Defined at `first_level_config:1246`, re-exported from `__init__` | Resolves |
| `setup_logging` import | `first_level_utils.setup_logging` | Defined at `first_level_utils:186` | Resolves |
| `DISPATCH` import | `run_first_level.DISPATCH` | Dict at `run_first_level:83` | Resolves |
| `names` import | `import names as upstream_names` | Module exists; `frozen_primary`, `ledger`, `qc_summary` all present | Resolves |
| Exception classes | `ConfigError, InputError, ModelError, GuardError, ToolUnavailableError, ToolVersionError, ToolExecutionError` | All in `exceptions.py` | Resolves |
| Runtime functions | `preflight_tool_environments, runtime_check, load_lockfile` | All in `runtime.py` | Resolves |
| Version gate | `MIN=4.0.0, MAX=5.0.0` (orchestrator_utils.py:541-542) | `__version__ = "4.0.0"` | Compatible |
| Motion column order | Extracts from confounds TSV by name: `[trans_x, trans_y, trans_z, rot_x, rot_y, rot_z]` | Expects `[tx, ty, tz, rx, ry, rz]` (translations first) | Correct |
| Input mode | Mode A (per-run path lists) exclusively | Supported | Compatible |
| New QC keys | `result.qc_summary` embedded as `upstream_qc_summary` | `censor_metric`, `fd_radius_mm`, `fd_summary`, `enorm_summary` present | Pass-through works |
| Frozen primary names | `upstream_names.frozen_primary(atype, pre)` | Names unchanged from v3.1.0 | Compatible |

### Remaining work (existing documentation, not new findings)

The existing TODO (`TODO_ABCD_fmri_orchestrator_S3_20261009_113924.md`, 13 prescribed items) and the companion report (`fmri-first-level-proc_brainstorm_downstream_20261016_193730.md`, O1-O5) document the remaining adaptation work. These are known items; the code-level API alignment verified above is sound.

One observation: `orch_config_final.yaml` contains retired keys (`fmriprep_dir`, `calc_n_motion_derivs`, `concatenate_runs`) that the v4 orchestrator validator rejects. This config file is stale. The production config appears to be `orch_config_abcd-v7.yaml`.

**Part 1 verdict**: The ABCD orchestrator's Python-level integration with fmri-first-level-proc v4.0.0 is correctly aligned. No new issues beyond the existing TODO/companion documents.

---

## Part 2: Full Pipeline Harmonization (fmri-proc-orchestrator pipeline)

Items already documented in `TODO_fmri-proc-orchestrator_20261009_113924.md` (9 prescribed changes + review-required items) are excluded per the user's instruction (those changes have not yet been implemented and are known). The findings below are **new issues** discovered in this audit.

### F1 (CRITICAL): fmri-preproc `write_motion_1d` column order is wrong

**Project**: fmri-preproc
**File**: `fmri_preproc/output_contract.py:589-650`, called from `fmri_preproc/stages/spatial_normalization_stages.py:1458`
**Severity**: Critical for direct fmri-preproc to fmri-first-level-proc usage; mitigated in orchestrated pipelines

The `_desc-motion_bold.1D` output file is written in **3dvolreg native order** `[rot_z, rot_x, rot_y, trans_z, trans_x, trans_y]` (rotations first), but the function's docstring, parameter documentation, and log message all claim the order is `[tx, ty, tz, rx, ry, rz]` (translations first).

**Evidence chain**:

1. `3dvolreg -1Dfile` outputs `[roll, pitch, yaw, dS, dL, dP]` = `[rot_z, rot_x, rot_y, trans_z, trans_x, trans_y]` (AFNI documentation; confirmed by the within_scan_motion_correction stage docstring at `native_space_stages.py:265-267`).
2. `motion_arr = np.loadtxt(motion_1d)` at `native_space_stages.py:355` stores the raw output with no reorder.
3. `motion6 = np.asarray(run_ctx["within_scan_motion"], dtype=float)` at `spatial_normalization_stages.py:1354` passes through as-is.
4. `oc.write_motion_1d(motion6, ...)` at `spatial_normalization_stages.py:1458` writes to disk with no column reorder.
5. `confounds.py:friston24()` (line 38) and `confounds.py:framewise_displacement()` (line 73) both correctly treat `mp[:, :3]` as rotations and `mp[:, 3:]` as translations (3dvolreg convention). This is internally consistent within fmri-preproc.
6. `write_motion_1d` docstring (lines 598-608) claims `[tx, ty, tz, rx, ry, rz]` and explicitly states "This file maps to the `motion_path` input slot in fmri-first-level-proc."

**Impact**: fmri-first-level-proc's `_power_fd` (`nuisance.py:58-83`) treats columns 0-2 as translations (no rotation weight) and columns 3-5 as rotations (multiplied by `pi/180 * 50mm`). If fed the 3dvolreg-ordered file:

- Rotations (degrees) in columns 0-2 would be summed as mm translations (no arc-length conversion), underweighting them by a factor of ~0.873 per degree.
- Translations (mm) in columns 3-5 would be multiplied by `~0.873`, inappropriately reducing them.
- FD would be incorrect, producing wrong censoring decisions.

**Mitigation**: Both orchestrators (ABCD and fmri-proc-orchestrator seam2) extract motion from the confounds TSV by column **name**, correctly reordering to translations-first. They never read the `_desc-motion_bold.1D` file. But direct fmri-preproc to fmri-first-level-proc usage (the documented use case per the `write_motion_1d` docstring) would be silently incorrect.

**Recommended fix**: Reorder columns in `write_motion_1d` before writing (the function's contract already says translations-first, so the implementation should match). Alternatively, reorder at the call site in the confound extraction stage. Option (a) is cleaner.

---

### F2 (HIGH): fmri-preproc produces no standalone tissue signal 1D files

**Project**: fmri-preproc
**File**: `fmri_preproc/stages/spatial_normalization_stages.py` (confound_extraction stage), `fmri_preproc/output_contract.py`
**Severity**: High for direct usage; mitigated by orchestrator extraction

fmri-preproc writes CSF, WM, and GS tissue mean signals only as named columns in the confounds TSV (`csf`, `white_matter`, `global_signal`). fmri-first-level-proc's `CSF_paths`, `WM_paths`, and `GS_paths` config keys expect paths to standalone headerless 1D files.

fmri-proc-orchestrator's seam2 adapter extracts these columns into standalone 1D files (`_extract_tissue` in `adapters/seam2.py`). But there is no mechanism for direct fmri-preproc to fmri-first-level-proc usage without an extraction step, despite the implicit contract (per `write_motion_1d`'s docstring) that fmri-preproc outputs are directly consumable by fmri-first-level-proc.

**Recommended fix**: Add `write_tissue_1d()` functions to fmri-preproc's output contract (parallel to `write_motion_1d`) that write CSF, WM, and (optionally) GS as standalone 1D files. Alternatively, document that an orchestrator extraction step is required.

---

### F3 (MEDIUM): No cross-project AFNI version enforcement

**Projects**: fmri-preproc, fmri-first-level-proc, fmri-proc-orchestrator
**Files**: `fmri_proc_orchestrator/runtime.py` (utilities exist), `fmri_proc_orchestrator/pipeline.py` (not wired)
**Severity**: Medium (correctness risk from version-dependent numerical behavior)

Both fmri-preproc and fmri-first-level-proc independently pin AFNI 26.0.09 in their `tools.lock.yaml` files. fmri-proc-orchestrator has `validate_cross_module_versions()` and `validate_python_pin()` utility functions in `runtime.py`, but **neither is called** in the actual pipeline flow (`pipeline.py`). If the two packages were installed with different AFNI versions, numerical differences in `3dvolreg`, `3dDeconvolve`, `3dTproject`, etc. could introduce subtle, undetectable result drift between preprocessing and first-level analysis.

**Recommended fix**: Wire `validate_cross_module_versions()` into `pipeline.py`'s preflight checks, comparing lockfile entries across all enabled modules.

---

### F4 (MEDIUM): fmri-bids-recon to fmri-preproc handoff has no formal contract

**Projects**: fmri-bids-recon, fmri-preproc
**Severity**: Medium (fragile implicit coupling)

The integration between fmri-bids-recon and fmri-preproc is entirely via BIDS directory convention. There is no schema document, version check, or handoff manifest. Specific concerns:

- **Task labels**: fmri-bids-recon derives labels from SeriesDescription (lowercase alphanumeric, stop-word filtered). Downstream consumers must accept whatever labels emerge. If a protocol produces an unusual label, it will propagate silently through the entire pipeline.
- **Run indexing**: fmri-bids-recon always emits `run-{idx:02d}` (1-based, zero-padded), even for singletons. fmri-preproc discovers via BIDS globbing. Compatible, but brittle if either convention changes.
- **Session labels**: fmri-bids-recon always emits `ses-{label}`. fmri-preproc supports both with-session and without-session layouts. Compatible.
- **Sidecar fields**: fmri-preproc reads `RepetitionTime`, `SliceTiming`, `PhaseEncodingDirection`, `TotalReadoutTime` from JSON sidecars produced by fmri-bids-recon (passthrough from dcm2niix). No validation that these fields are present before fmri-preproc attempts to use them.

The fmri-proc-orchestrator's seam1 adapter bridges bids-recon to preproc by reading the bids-recon manifest and constructing a preproc config, but it does not validate structural compatibility.

**Recommended fix**: Define a minimal formal handoff contract (expected BIDS entities, required sidecar fields, run indexing convention) in a shared document or schema file that both projects can validate against.

---

### F5 (MEDIUM): fmri-preproc confounds TSV FD first-frame convention differs from fmri-first-level-proc

**Projects**: fmri-preproc, fmri-first-level-proc
**Files**: `fmri_preproc/confounds.py:73-96`, `fmri_first_level_proc/nuisance.py:58-83`
**Severity**: Medium (QC comparison confusion, not a runtime error)

fmri-preproc's `framewise_displacement()` returns `NaN` for the first frame (no prior frame to difference against). fmri-first-level-proc's `_power_fd()` returns `0` for the first TR of each run. Both compute Power FD with the same formula (50mm sphere, degree-to-radian conversion), but the boundary convention differs.

This is not a runtime bug: fmri-first-level-proc computes its own FD from raw motion parameters, never reading the confounds TSV FD column. However, if a researcher compares the preproc confounds FD column against fmri-first-level-proc's `_fd.1D` output, the first frame will disagree (`NaN` vs `0`), which could cause confusion in QC validation.

**Recommended fix**: Document the convention difference in both projects' output specifications. No code change needed.

---

### F6 (LOW): fmri-proc-orchestrator seam2 confounds TSV column expectations are undocumented

**Projects**: fmri-proc-orchestrator, fmri-preproc
**File**: `fmri_proc_orchestrator/adapters/seam2.py:26-28`
**Severity**: Low (currently aligned, but implicitly)

seam2 reads fmri-preproc confounds TSVs expecting exact column names: `trans_x`, `trans_y`, `trans_z`, `rot_x`, `rot_y`, `rot_z` (and `_derivative1` variants), `csf`, `white_matter`, `global_signal`. fmri-preproc uses these exact names (via `confounds.py:friston24()` labels and `tissue_mean()` column names). The coupling is correct but undocumented. If fmri-preproc renamed any column, seam2 would fail with a `KeyError`.

**Recommended fix**: Document the expected column name contract in seam2, referencing fmri-preproc's `CONFOUND_COLUMN_ORDER`.

---

## Summary Table

| ID | Severity | Project(s) | Description | Mitigated by orchestrators? |
|---|---|---|---|---|
| F1 | CRITICAL | fmri-preproc | `write_motion_1d` outputs rotations-first but documents translations-first; FD would be wrong if used directly | Yes (both extract from TSV by name) |
| F2 | HIGH | fmri-preproc | No standalone CSF/WM/GS 1D files; first-level-proc expects 1D paths | Yes (seam2 extracts from TSV) |
| F3 | MEDIUM | fmri-proc-orchestrator | Cross-module AFNI version validation exists but is not wired into pipeline | N/A |
| F4 | MEDIUM | fmri-bids-recon, fmri-preproc | No formal handoff contract (BIDS convention only) | Partially (seam1 bridges) |
| F5 | MEDIUM | fmri-preproc, fmri-first-level-proc | FD first-frame convention: NaN vs 0 | N/A (documentation only) |
| F6 | LOW | fmri-proc-orchestrator, fmri-preproc | Confounds TSV column name coupling is undocumented | N/A (documentation only) |

## Context for Resumption

- The v4.0.0 `/test` cycle completed earlier this session: 677/677 passing, 0 failures. Test report: `fmri-first-level-proc_test_20261016_231954.md`.
- The v4.0.0 `/implement build` completed earlier this session: all 8 changes done. Build report: `fmri-first-level-proc_implement_build_20261016_201148.md`.
- Next steps for fmri-first-level-proc specifically: `/document` (U5 action item: update `example_config.yaml` and `INPUT_SPECIFICATION.md` for Power FD metric and CENSORTR removal), then merge v4.0.0-build, tag, publish.
- The findings above (F1-F6) are in sibling projects, not in fmri-first-level-proc itself. F1 and F2 should be addressed in fmri-preproc before or alongside v4.0.0 publication, since `write_motion_1d`'s docstring explicitly references `fmri-first-level-proc >= 2.5.0` as the downstream consumer.
- fmri-proc-orchestrator TODO items (already documented) land only after fmri-first-level-proc 4.0.0 is published.
- ABCD_fmri_orchestrator_S3 TODO/companion items (already documented) land only after fmri-first-level-proc 4.0.0 is published.
