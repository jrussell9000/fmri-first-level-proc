<implement_plan>
  <meta project="fmri_first_level_proc" mode="implement" submodule="plan" timestamp="2026-08-13T14:15:00Z" />
  <input_reports>
    <report path="fmri_first_level_proc_test_20260813_140700.md" mode="test" key_items="2" />
  </input_reports>
  <changes>
    <change id="C1" priority="P0" source_item="P0 action item: polort A DOF-preflight regression fix">
      <file path="fmri_first_level_proc/first_level_utils.py" action="modify" />
      <description>Add an optional `tr` parameter to `compute_dof()`. When `tr` is provided, compute the AFNI polort A polynomial regressor count (`n_poly = 1 + int((len(censor_data) * tr) / 150.0)`) from the `censor_data` array already loaded inside the function's existing try/except block, and add `n_poly` to `n_regressors` before the DOF check. When `tr` is None (default), behavior is unchanged. Update the docstring to document the new parameter and its effect.</description>
      <spec>
At first_level_utils.py:1449, change the signature from:
  `def compute_dof(censor_path, n_regressors, logger):`
to:
  `def compute_dof(censor_path, n_regressors, logger, tr=None):`

Inside the try block (L1471-1473), after `n_uncensored = int(np.sum(censor_data == 1))`, insert:
```python
    if tr is not None:
        n_poly = 1 + int((len(censor_data) * tr) / 150.0)
        n_regressors = n_regressors + n_poly
```

Update the docstring Parameters section to add:
```
    tr : float or None, optional
        Repetition time in seconds. When provided, the AFNI polort A
        polynomial regressor count (1 + floor(duration / 150)) is computed
        from the censor file length and added to n_regressors before the
        DOF check. When None (default), no polort adjustment is applied.
```

Update the docstring Returns section to note that the returned DOF value accounts for the polort adjustment when tr is provided.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - isolated function change with clear pre/post contract; the try/except already guards the censor read</risk>
      <rollback>Revert the signature to 3 positional args, remove the if-tr block, restore original docstring</rollback>
    </change>

    <change id="C2" priority="P0" source_item="P0 action item: delete task_act preflight block">
      <file path="fmri_first_level_proc/task_act_first_level.py" action="modify" />
      <description>Delete the 4-line unguarded censor-file preflight block (L705-708) and update the compute_dof call to pass `tr=config.tr`.</description>
      <spec>
Delete lines 705-708:
```python
    censor_data_preflight = np.loadtxt(config.censor_path)
    n_trs = len(censor_data_preflight)
    n_poly = 1 + int((n_trs * config.tr) / 150.0)
    n_regressors += n_poly
```

Change the compute_dof call (currently L709) from:
  `dof = compute_dof(config.censor_path, n_regressors, logger)`
to:
  `dof = compute_dof(config.censor_path, n_regressors, logger, tr=config.tr)`
      </spec>
      <dependencies>C1</dependencies>
      <risk>low - removing code and passing a new kwarg</risk>
      <rollback>Re-insert the 4-line block, remove the tr= kwarg from the call</rollback>
    </change>

    <change id="C3" priority="P0" source_item="P0 action item: delete task_conn preflight block">
      <file path="fmri_first_level_proc/task_conn_first_level.py" action="modify" />
      <description>Delete the 4-line unguarded censor-file preflight block (L762-765) and update the compute_dof call to pass `tr=config.tr`.</description>
      <spec>
Delete lines 762-765:
```python
    censor_data_preflight = np.loadtxt(config.censor_path)
    n_trs = len(censor_data_preflight)
    n_poly = 1 + int((n_trs * config.tr) / 150.0)
    n_regressors += n_poly
```

Change the compute_dof call (currently L766) from:
  `dof = compute_dof(config.censor_path, n_regressors, logger)`
to:
  `dof = compute_dof(config.censor_path, n_regressors, logger, tr=config.tr)`
      </spec>
      <dependencies>C1</dependencies>
      <risk>low - removing code and passing a new kwarg</risk>
      <rollback>Re-insert the 4-line block, remove the tr= kwarg from the call</rollback>
    </change>

    <change id="C4" priority="P1" source_item="P1 action item: re-express ValueError to ConfigError in test assertions">
      <file path="tests/test_utils_unit.py" action="modify" />
      <description>Re-express two test assertions from `pytest.raises(ValueError)` to `pytest.raises(ConfigError)` to match the approved v3.0.0 exception-type change in `build_hrf_string()`. Update the two associated docstrings. Add `ConfigError` to the exceptions import.</description>
      <spec>
At L18, change the import from:
  `from fmri_first_level_proc.exceptions import InputError`
to:
  `from fmri_first_level_proc.exceptions import ConfigError, InputError`

At L128, change the docstring from:
  `"""custom model with no custom_hrf raises ValueError."""`
to:
  `"""custom model with no custom_hrf raises ConfigError."""`

At L129, change:
  `with pytest.raises(ValueError):`
to:
  `with pytest.raises(ConfigError):`

At L133, change the docstring from:
  `"""Unknown model name raises ValueError."""`
to:
  `"""Unknown model name raises ConfigError."""`

At L135, change:
  `with pytest.raises(ValueError):`
to:
  `with pytest.raises(ConfigError):`
      </spec>
      <dependencies>none</dependencies>
      <risk>low - assertion re-expression preserving the same postcondition (invalid input raises), with a more specific exception type</risk>
      <rollback>Revert all 5 edits</rollback>
    </change>
  </changes>
  <execution_order>C1, then C2 and C3 (parallel, independent files), then C4</execution_order>
</implement_plan>
