<brainstorm_report>
  <meta project="fmri_first_level_proc" mode="brainstorm" timestamp="2026-03-11T22:00:00Z" />
  <context_files>
    <file path="FIX_fromOrch.txt" relevance="Upstream bug report from real-world testing (v2.2.0, sub-XXXXXXXX)" />
    <file path="fmri_first_level_proc/task_conn_first_level.py" relevance="Contains BUG-001 (sub-brick ordering) and BUG-002 (onset file flow) — get_stim_data, gen_design_matrix, gen_beta_series, run" />
    <file path="fmri_first_level_proc/first_level_utils.py" relevance="Contains BUG-003 (notch_filter_motion 1D transpose)" />
    <file path="fmri_first_level_proc/task_act_first_level.py" relevance="Harmonization target — condition-drop ordering consistency" />
  </context_files>
  <topics>
    <topic id="T1" title="BUG-001: Silent sub-brick ordering mismatch in gen_beta_series()">
      <summary>get_stim_data() accumulates beta onsets in first-appearance order (pandas .unique()), but gen_beta_series() extracts sub-bricks in alphabetical order (np.unique()). The total_used counter assigns wrong sub-brick indices to every condition after the first group. All task_conn condition-specific beta series, connectivity matrices, and contrasts are silently incorrect. Present since initial implementation.</summary>
      <approaches>
        <approach id="A1" label="Return beta_cond_order from get_stim_data (Option A)" feasibility="high" risk="low">
          <description>Have get_stim_data() return the explicit condition accumulation order as a list. Thread this list through gen_beta_series() and gen_design_matrix() so downstream functions use the ground-truth order rather than independently reconstructing it. Eliminates np.unique() from the task_conn pipeline entirely.</description>
          <pros>Makes the ordering contract explicit and testable; eliminates implicit agreement between functions; self-documenting; robust to future edits</pros>
          <cons>Slightly more invasive than Option B (changes function signatures)</cons>
          <statistical_considerations>Silent data corruption is the worst class of bug in neuroimaging — analyses complete "successfully" but every condition label maps to incorrect neural data. Any prior task_conn results from this pipeline must be considered invalid.</statistical_considerations>
        </approach>
        <approach id="A2" label="Alphabetical accumulation in get_stim_data (Option B)" feasibility="high" risk="med">
          <description>Change get_stim_data() line 153 to use np.unique() instead of .unique(), making both functions independently choose alphabetical order.</description>
          <pros>Minimal code change (one line)</pros>
          <cons>Contract remains implicit — both functions must independently choose the same ordering convention; fragile to future edits; no explicit documentation of the dependency</cons>
        </approach>
      </approaches>
      <decision status="decided" chosen="A1">Option A selected. The ordering contract must be explicit. Additionally, np.unique() will be eliminated from gen_design_matrix() line 216 — nuisance condition iteration will use stim_data['CONDITION'].unique() with a filter (preserving first-appearance order throughout). This removes np.unique() from the entire task_conn pipeline, eliminating the class of ordering ambiguity.</decision>
    </topic>
    <topic id="T2" title="BUG-002: Dropped conditions' onset files not written for nuisance regressors">
      <summary>get_stim_data() runs before check_trial_survival() in run(). Conditions in cond_beta_labels at call time get combined into beta_onsets.txt (no individual onset file). After trial survival filtering drops conditions from cond_beta_labels, gen_design_matrix() treats them as nuisance and references individual onset files that were never written. Crashes with "can't read file" on sessions with heavy censoring. Introduced in v2.2.0 by the condition-drop logic.</summary>
      <approaches>
        <approach id="A1" label="Reorder: drop before get_stim_data, with double-read" feasibility="high" risk="low">
          <description>Call read_and_validate_stim_data() first (for trial survival check), then call get_stim_data() after condition filtering. The timing CSV is read twice (once for validation/survival, once for onset file writing).</description>
          <pros>Minimal refactor; straightforward</pros>
          <cons>Double-read of timing CSV; get_stim_data() encapsulates both read and write, making the API unclear about what has already been validated</cons>
        </approach>
        <approach id="A2" label="Split get_stim_data into read + write phases" feasibility="high" risk="low">
          <description>Refactor get_stim_data() into two functions: (1) read_stim_data() — reads, validates, and returns the sorted DataFrame; (2) write_stim_onset_files() — writes the onset files based on the current cond_beta_labels. The run() function calls read first, performs trial survival and condition filtering, then calls write with the updated labels.</description>
          <pros>Single read of timing CSV; clear separation of concerns; each function has a single responsibility; the write function explicitly receives the filtered state</pros>
          <cons>Slightly more refactoring; changes the function API (but get_stim_data is internal, not public)</cons>
        </approach>
      </approaches>
      <decision status="decided" chosen="A2">Split get_stim_data() into read + write phases. This provides clean separation of concerns, avoids double-reading the timing CSV, and makes the data flow explicit. The write phase receives the already-filtered cond_beta_labels, so dropped conditions naturally get individual onset files. Composes cleanly with BUG-001 fix — the write phase returns beta_cond_order reflecting only surviving conditions.</decision>
    </topic>
    <topic id="T3" title="BUG-003: notch_filter_motion() 1D dimension misinterpretation by 3dTproject">
      <summary>AFNI interprets .1D files as rows=voxels, cols=timepoints. A 378x6 motion file is seen as 378 voxels x 6 timepoints, causing "fewer than 9 time points" error. The original code used a trailing ' (AFNI transpose) on input, but v2.2.0 removed it to fix a downstream orientation issue. Both states (with/without transpose) fail — the ' is needed for input but the output must be transposed back. Independent of BUG-001/002.</summary>
      <approaches>
        <approach id="A1" label="numpy transpose of output" feasibility="high" risk="low">
          <description>Restore ' on input. After 3dTproject, use np.loadtxt + .T + np.savetxt to transpose output back to rows=TRs, cols=params.</description>
          <pros>Self-contained in Python; no additional AFNI dependency</pros>
          <cons>Introduces numpy I/O for a file format that is AFNI-native; potential precision/formatting differences; prior np.savetxt issues in this codebase (compute_matrix_contrast)</cons>
        </approach>
        <approach id="A2" label="AFNI 1dtranspose on output" feasibility="high" risk="low">
          <description>Restore ' on input. After 3dTproject, run AFNI's 1dtranspose on the output file to convert from rows=params,cols=TRs back to rows=TRs,cols=params. Keeps everything in the AFNI ecosystem.</description>
          <pros>AFNI-native; no precision/format conversion; consistent with the rest of the pipeline's tool usage; avoids numpy I/O edge cases</pros>
          <cons>Additional subprocess call (trivially fast for a 6-column file)</cons>
        </approach>
        <approach id="A3" label="Per-column 3dTproject (avoid transpose entirely)" feasibility="med" risk="low">
          <description>Apply 3dTproject to each of the 6 motion columns independently as single-column 1D files, then recombine. No transpose ambiguity.</description>
          <pros>Eliminates transpose issue entirely</pros>
          <cons>Over-engineered; 6x subprocess overhead; harder to read/maintain</cons>
        </approach>
      </approaches>
      <decision status="decided" chosen="A2">Use AFNI's 1dtranspose on the output. This keeps the entire notch filtering operation within the AFNI ecosystem, avoids numpy I/O format concerns, and is consistent with the pipeline's design philosophy of wrapping AFNI commands rather than reimplementing their functionality in Python.</decision>
    </topic>
    <topic id="T4" title="task_act condition-drop ordering harmonization">
      <summary>task_act_first_level.py calls get_stim_data() before condition dropping (line 505 vs 508-513). For task_act this is harmless because onset files are per-condition and dropped conditions are simply not referenced in 3dDeconvolve. However, the asymmetry creates maintenance risk — a future developer may assume the ordering is safe because "task_act does it this way."</summary>
      <approaches>
        <approach id="A1" label="Harmonize task_act to drop-before-write" feasibility="high" risk="low">
          <description>Apply the same read/write split pattern to task_act: read timing data first, perform trial survival check and condition filtering, then write onset files with the filtered condition list.</description>
          <pros>Consistent pattern across both pipelines; prevents maintenance errors; makes the data flow identical</pros>
          <cons>Requires touching task_act code that currently works correctly</cons>
        </approach>
      </approaches>
      <decision status="decided" chosen="A1">Harmonize task_act to use the same drop-before-write pattern. Consistency across pipelines is a defensibility requirement — both pipelines should follow identical data flow patterns.</decision>
    </topic>
  </topics>
  <action_items>
    <item priority="P0" target_mode="implement" description="BUG-001: Split get_stim_data() into read_stim_data() + write_stim_onset_files(). write_stim_onset_files() returns beta_cond_order. Thread beta_cond_order through gen_beta_series() for sub-brick extraction. Eliminate np.unique() from gen_design_matrix() — use stim_data['CONDITION'].unique() with filter." />
    <item priority="P0" target_mode="implement" description="BUG-003: Restore trailing ' on 3dTproject -input in notch_filter_motion(). Add AFNI 1dtranspose call on output to restore rows=TRs, cols=params orientation." />
    <item priority="P1" target_mode="implement" description="BUG-002: Reorder run() in task_conn — call read_stim_data() first, then trial survival + condition filtering, then write_stim_onset_files() with filtered cond_beta_labels. Composes with BUG-001 fix (write phase returns beta_cond_order for surviving conditions only)." />
    <item priority="P2" target_mode="implement" description="Harmonize task_act run() to use the same read/write split and drop-before-write ordering pattern as task_conn." />
    <item priority="P0" target_mode="test" description="BUG-001 test: create timing DataFrame with conditions whose alphabetical order differs from first-appearance order. Verify beta_onsets.txt line order and gen_beta_series() sub-brick indices produce the same condition mapping." />
    <item priority="P0" target_mode="test" description="BUG-003 test: create synthetic 1D motion file (N rows x 6 cols). Run notch_filter_motion(). Verify output has N rows x 6 cols and values are numerically reasonable." />
    <item priority="P1" target_mode="test" description="BUG-002 test: create timing data where some conditions have 0-1 surviving trials. Verify dropped conditions get individual onset files, gen_design_matrix() references them, and beta_onsets.txt contains only surviving conditions' trials." />
    <item priority="P2" target_mode="test" description="task_act harmonization test: verify task_act onset files are written correctly after condition filtering." />
  </action_items>
  <next_steps>Proceed to /implement mode. Recommended order: (1) BUG-001 + BUG-002 together (shared code region in task_conn — the read/write split addresses both), (2) BUG-003 independently in first_level_utils.py, (3) task_act harmonization. Then /test to verify all fixes and add regression tests.</next_steps>
</brainstorm_report>
