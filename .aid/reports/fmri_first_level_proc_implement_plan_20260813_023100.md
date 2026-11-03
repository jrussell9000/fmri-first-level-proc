<implement_plan>
  <meta project="fmri_first_level_proc" mode="implement" submodule="plan" timestamp="2026-08-13T02:31:00Z" />
  <input_reports>
    <report path="fmri_first_level_proc_test_20260813_005500.md" mode="test" key_items="2" />
  </input_reports>
  <changes>
    <change id="C1" priority="P0" source_item="test_report/action_items[1]: BIDS column rename propagation">
      <file path="fmri_first_level_proc/task_act_first_level.py" action="modify" />
      <file path="fmri_first_level_proc/task_conn_first_level.py" action="modify" />
      <description>Propagate BIDS column rename from read_and_validate_stim_data into the two pipeline modules that consume its output. read_and_validate_stim_data (first_level_utils.py) now returns DataFrames with columns (trial_type, onset, duration) regardless of input format. Both task_act_first_level.py and task_conn_first_level.py still index the returned DataFrame using the legacy uppercase names (CONDITION, ONSET, DURATION), causing KeyError at runtime.</description>
      <spec>
task_act_first_level.py (4 sites):
  L187: stim_data['CONDITION'].unique()         -> stim_data['trial_type'].unique()
  L188: stim_data[stim_data['CONDITION'] == cond] -> stim_data[stim_data['trial_type'] == cond]
  L241: stim_data[stim_data['CONDITION'] == cond]['DURATION'] -> stim_data[stim_data['trial_type'] == cond]['duration']
  L736: stim_data[stim_data['CONDITION'] == c]  -> stim_data[stim_data['trial_type'] == c]

task_conn_first_level.py (15 DataFrame-column sites):
  L188: stim_data['CONDITION'].unique()         -> stim_data['trial_type'].unique()
  L189: stim_data[stim_data['CONDITION'] == cond] -> stim_data[stim_data['trial_type'] == cond]
  L198: cond_df['ONSET']                        -> cond_df['onset']
  L199: cond_df['DURATION']                     -> cond_df['duration']
  L201: cond_df['ONSET']                        -> cond_df['onset']
  L202: cond_df['DURATION']                     -> cond_df['duration']
  L205: pd.DataFrame({'ONSET': betas_onsets, 'DURATION': betas_durations})
     -> pd.DataFrame({'onset': betas_onsets, 'duration': betas_durations})
  L246: stim_data['CONDITION'].unique()         -> stim_data['trial_type'].unique()
  L250: stim_data['CONDITION'].unique()         -> stim_data['trial_type'].unique()
  L254: stim_data[stim_data['CONDITION'] == cond]['DURATION']
     -> stim_data[stim_data['trial_type'] == cond]['duration']
  L266: stim_data[stim_data['CONDITION'].isin(config.cond_beta_labels)]['DURATION']
     -> stim_data[stim_data['trial_type'].isin(config.cond_beta_labels)]['duration']
  L346: stim_data[stim_data['CONDITION'] == curr_cond]['ONSET']
     -> stim_data[stim_data['trial_type'] == curr_cond]['onset']
  L717: stim_data[stim_data['CONDITION'] == cond]
     -> stim_data[stim_data['trial_type'] == cond]
  L778: stim_data[stim_data['CONDITION'] == c]
     -> stim_data[stim_data['trial_type'] == c]

Note: Line 205 was not listed in the test report's action item but is required. The test report's grep targeted 'CONDITION'; line 205 uses 'ONSET'/'DURATION' as DataFrame column names for betas_df, which is passed to write_onset_file (expects lowercase BIDS names). Without this fix, the 37 KeyError('CONDITION') failures would resolve but a subset would reappear as KeyError('onset') at write_onset_file.

NOT changed (dict keys, not DataFrame columns):
  L341: bseries_out = {"CONDITION": [], "PATH": []}
  L367: bseries_out['CONDITION'].append(curr_cond)
  L374: bseries_out['CONDITION'].append(curr_cond)
  L380: len(bseries_out["CONDITION"])
  L405, 441, 486: bseries_info['CONDITION']
These are plain dict keys in an internal tracking structure (not stim_data column access). Changing them would require cascading edits to 7 additional lines (341, 380, 405, 441, 486 plus 3 docstrings at 316, 399, 434, 477) and does not fix any test failure. See scope_observations below.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - mechanical string replacement on well-identified sites; each site's surrounding code (variable names, logic) is unchanged. The only subtlety is line 205 (betas_df column names), which the test report omitted but which is required for write_onset_file compatibility.</risk>
      <rollback>Revert 'trial_type'/'onset'/'duration' back to 'CONDITION'/'ONSET'/'DURATION' at the same sites.</rollback>
    </change>

    <change id="C2" priority="P0" source_item="test_report/action_items[2]: missing import argparse">
      <file path="fmri_first_level_proc/first_level_utils.py" action="modify" />
      <description>Restore the 'import argparse' statement that was dropped during the v3.0.0 sys.exit-to-exception migration. Six validator functions (dir_path_exists, file_path_exists, valid_string_list, valid_stat_type, valid_ave_type, valid_conn_type) still raise argparse.ArgumentTypeError on invalid input; without the import, every error path hits NameError instead.</description>
      <spec>
first_level_utils.py import block (currently lines 36-49):
  Add 'import argparse' as the first stdlib import (alphabetical order), before 'import dataclasses' at line 36.

Current:
  import dataclasses
  import json
  ...

After:
  import argparse
  import dataclasses
  import json
  ...
      </spec>
      <dependencies>none</dependencies>
      <risk>low - single import statement; no side effects; restores previously-working behavior.</risk>
      <rollback>Remove the 'import argparse' line.</rollback>
    </change>
  </changes>

  <execution_order>C1, C2 (independent; may be executed in parallel)</execution_order>

  <scope_observations>
    <observation id="SO1" type="related-naming-consistency">
      <description>The bseries_out/bseries_info dict in task_conn_first_level.py uses 'CONDITION' as a key (lines 341, 367, 374, 380, 405, 441, 486) alongside three docstrings (316, 399, 434, 477). These are plain dict keys tracking beta series output metadata, not DataFrame column accesses. They do not cause test failures and are not consumed by any BIDS-aware function. Renaming them to 'trial_type' would require 10 additional edits (7 code + 3 docstring) with no functional benefit.</description>
      <recommendation>Do not change. The dict key 'CONDITION' here means "which experimental condition this beta series belongs to," not "the DataFrame column named CONDITION." Renaming it would be cosmetic and introduces unnecessary churn.</recommendation>
    </observation>
    <observation id="SO2" type="stale-docstrings">
      <description>Function-level docstrings in both pipeline modules still reference "CONDITION, ONSET, DURATION columns" when describing the stim_data parameter (task_act L182, task_conn docstrings at write_stim_onset_files, gen_design_matrix, gen_beta_series). Module-level docstrings at lines 24/26 (both files) describe the input file format using legacy column names, which remains valid since read_and_validate_stim_data accepts both formats.</description>
      <recommendation>Defer. Function-level docstring updates are cosmetic and do not affect runtime behavior. They can be addressed in a documentation pass. Module-level docstrings describing input file format are still accurate (legacy format is accepted).</recommendation>
    </observation>
  </scope_observations>
</implement_plan>
