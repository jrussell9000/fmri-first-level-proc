# ABCD staging

`fmri_first_level_proc.abcd` prepares one ABCD session for first-level analysis and runs
it. It is optional and separate from the framework: nothing in the core imports it, and
it needs the `abcd` extra.

```bash
pip install "fmri-first-level-proc[abcd] @ git+https://github.com/jrussell9000/fmri-first-level-proc.git"
```

## Running it

```bash
fmri-first-level-abcd \
    --subj sub-XXXX --ses ses-00A \
    --input-dir /data/sub-XXXX/ses-00A \
    --probseg-state fixed \
    --workdir /scratch/stage \
    --out-dir /scratch/out \
    --atlas /path/to/parcellation.nii.gz \
    --result /scratch/result.json
```

It works only on local files and never contacts a remote store. It needs AFNI and the
`fmri-first-level-proc` CLI on `PATH`.

| Exit | Meaning |
|---|---|
| 0 | Every analysis finished, and the result JSON is written. An analysis may be recorded `failed` (a data-determined model failure, CLI exit 5) or skipped. |
| 1 | The session failed, and no result is written. |

## Inputs

`--input-dir` holds one session of [cloudpipe](https://github.com/jrussell9000/cloudpipe)
func derivatives, or any files with the same names:

| File | Used for |
|---|---|
| `_complete.json` | Its `runs` keys name the session's runs |
| `{subj}_{ses}_{task}_{run}_space-MNI152NLin2009cAsym_bold.nii.gz` | BOLD |
| `{subj}_{ses}_{task}_{run}_space-MNI152NLin2009cAsym_brainmask.nii.gz` | Brain mask |
| `{subj}_{ses}_{task}_{run}_desc-confounds_timeseries.tsv` | Motion, `global_signal`, `non_steady_state_outlier_*` |
| `{subj}_{ses}_task-nback_{run}_events.tsv` | n-back timing |
| `{subj}_{ses}_space-MNI152NLin2009cAsym_res-1_label-{GM,WM,CSF}_probseg.nii.gz` | Rest tissue masks |
| `{subj}_{ses}_space-MNI152NLin2009cAsym_res-1_label-CSF_mask.nii.gz` | Ventricle restriction |

`--probseg-state` must be `fixed` for rest to run. Any other value skips rest and records
the reason; the two tissue rows above are needed only for `fixed`.

## What it does

- **Trimming:** removes the frames flagged by the confounds' `non_steady_state_outlier_*`
  columns from the BOLD and motion, and shifts event onsets to match. An event that then
  starts before 0 is dropped and counted.
- **Motion:** translations first, in degrees, with first derivatives taken before
  trimming. An isolated NaN becomes 999 so that FD censoring removes that TR.
- **n-back events:** a 0-back cue takes its block's condition and a 2-back cue becomes
  `instruction`. `dummy` rows are dropped.
- **n-back runs** are concatenated, masked by the intersection of their brain masks. A run
  that fails staging is excluded and recorded, and the rest continue.
- **Rest WM mask:** as fMRIPrep builds `white_matter`: dilated grey matter removed, moved
  to the BOLD grid as partial-volume fractions, brain-masked, kept above 0.99.
- **Rest CSF mask:** restricted to the ventricles with FastSurfer's `label-CSF_mask`, then
  kept above the first of 0.99, 0.9 and 0.5 that leaves at least 100 voxels. This departs
  from fMRIPrep, and is likely specific to ABCD.
- **Rest global signal:** the confounds' `global_signal`, trimmed.
- **Analyses:** fills `abcd/data/proc_config_final.yaml` (or `--template`) and runs each
  block through the `fmri-first-level-proc` CLI, once per block.

## Result JSON

`package_version`, `probseg_state`, `analyses` (name to status, exit code and warning flag,
or skip reason) and `runs` (run to `n_remove`, `n_frames`, `dropped_events`, plus the
mask voxel counts and `csf_threshold` on rest, or `excluded`).
