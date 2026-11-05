# This fork

This is a fork of [tjkeding/fmri-first-level-proc](https://github.com/tjkeding/fmri-first-level-proc).
It runs upstream's analysis core unchanged and adds `fmri_first_level_proc/abcd/`, which stages
one ABCD session of [cloudpipe](https://github.com/jrussell9000/cloudpipe) func derivatives and
runs the core on it. Every difference from upstream is one of the commits or files listed here,
and CI fails if that stops being true.

**Upstream base:** `e40d1bc6f519b9a61996a594b395fef4ec9c9fd2`

**Fork version:** `4.0.0+cp.1`, in `pyproject.toml`. The part before the `+` is upstream's
version and the rest counts fork releases on it. `__version__` in `__init__.py` stays upstream's
value, so an analysis's QC reports the version of the core that ran it, and
`fmri-first-level-abcd` records the fork version in its result.

## Differences from upstream

### Upstream files changed

The core's Python modules are not on this list. `.github/scripts/check_fork_ledger.py` compares
the table with `git diff` from the upstream base, so a change to any other upstream file fails CI
until it is listed here with its reason.

<!-- ledger:start -->
| Status | File | Why |
|---|---|---|
| M | `.gitignore` | Upstream ignores everything by default, so the fork's paths need whitelisting |
| M | `pyproject.toml` | The fork version, the `abcd` extra, its two scripts, its package data and the `afni` test marker |
| D | `.aid/reports/fmri-first-level-proc_publish_20260911_160000.md` | It names a participant, and this fork holds no subject-keyed data |
<!-- ledger:end -->

### Files added

Everything else in the fork is a new file under one of these paths:

<!-- added:start -->
- `.github/`
- `FORK.md`
- `docs/`
- `fmri_first_level_proc/abcd/`
- `tests/`
<!-- added:end -->

### Commits

Each commit is one decision and can be read or reverted alone. Add a row with each new change.

| Commit | Change |
|---|---|
| `e41eb7b` | Add `abcd/` staging on the upstream core |
| `c94674c` | Keep n-back runs as separate files |
| `305f200` | Pool 0-back cues into `target_0back` |
| `9307dda` | Add the orchestrator comparison |
| `c5cf62e` | Adopt GAM for `nback_act`, previous-frame censoring for rest, and no `instruction` betas |
| `f2fa2bc` | Record masking and frame-count findings in the comparison |
| `812467a` | Adopt the 29 `nback_conn` contrasts |
| `a47175c` | Exclude rest runs with non-finite motion |
| `0c751a9` | Exclude any run with non-finite motion, and state the bandpass method |
| `5cf3572` | Record WM, CSF and global signal measurements in the comparison |
| `57cc57f` | Compute the rest global signal from the BOLD |
| `cafe83f` | Remove the upstream report listed above |

This page, CI and the version are the commit after these.

### Compared with upstream's orchestrator

Upstream runs its core through
[ABCD_fmri_orchestrator_S3](https://github.com/tjkeding/ABCD_fmri_orchestrator_S3). `abcd/` does
that work here and shares no code with it. [docs/orchestrator_comparison.md](docs/orchestrator_comparison.md)
records every difference, why it exists, and the orchestrator commit it was compared against.

## Following upstream

`.github/workflows/upstream-watch.yml` runs each Monday and fails when upstream or the
orchestrator has moved past the commits recorded in this repository. Its summary lists the new
commits. GitHub turns off a scheduled workflow after 60 days without repository activity, so
re-enable it if the Actions tab says it is off.

To take upstream's changes:

```bash
git remote add upstream https://github.com/tjkeding/fmri-first-level-proc.git  # once
git fetch upstream main
git log --oneline <upstream base>..upstream/main
git merge upstream/main
```

Then set **Upstream base** above to the merged commit, and take a new fork version, such as
`4.1.0+cp.1`. Merge rather than rebase, so the commits listed above keep their ids. Upstream's
tests are not published, so `tests/` covers only the fork's code; run the real-AFNI tests and
compare one session's results before releasing.

For the orchestrator, read its new commits, update the tables in the comparison, and change the
commit named there.

## Reversing it

- **One decision:** `git revert <commit>`, using the table above.
- **The whole fork:** delete the paths under "Files added", and restore the upstream files with
  `git checkout <upstream base> -- .gitignore pyproject.toml`. What remains is upstream's core.
  The removed report stays removed unless you restore it by its path.

## The older fork

Branch `legacy-5.0` holds the fork as it was before it was rebuilt on upstream's 4.0 core: a
refactored core with the `src/` layout. Tags `v4.1.0`, `v4.2.0` and `v5.0.0` belong to that line.
They are not ancestors of `main`, and `v5.0.0` is older than `4.0.0+cp.1` despite its number.

## Fork releases

### 4.0.0+cp.1

The first release on upstream's 4.0 core, at the upstream base above. The commits table lists its
contents.

Compared with `legacy-5.0`, output names and QC follow upstream's 4.0 schema, including
`{pre}_qc_summary.json` and run exclusions recorded as `excluded_runs`. n-back runs stay separate,
and staging takes the analysis settings in `abcd/data/proc_config_final.yaml`.
