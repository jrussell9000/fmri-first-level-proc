<implement_plan>
  <meta project="fmri_first_level_proc" mode="implement" submodule="plan" timestamp="2026-08-24T12:10:00-04:00" />
  <input_reports>
    <report path="fmri_first_level_proc_brainstorm_20260824_120000.md" mode="brainstorm" key_items="1" />
  </input_reports>
  <changes>
    <change id="C1" priority="P0" source_item="T1/A1">
      <file path="fmri_first_level_proc/task_act_first_level.py" action="modify" />
      <description>Replace non-low severity gate and "success_with_warnings" vocabulary with high-only gate and "warning" vocabulary at the run() return site.</description>
      <spec>
At lines 763-765, replace:

```python
    # Determine overall result status
    has_non_low = any(w.get("severity") != "low" for w in _warnings)
    status = "success_with_warnings" if has_non_low else "success"
```

With:

```python
    # Determine overall result status
    status = "warning" if any(w.get("severity") == "high" for w in _warnings) else "success"
```

Collapses two lines to one (intermediate variable eliminated). Gate logic changes from `!= "low"` to `== "high"`. Retains defensive `.get()` access.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - single-expression replacement; no test asserts on "success_with_warnings"</risk>
      <rollback>Revert the two lines to original.</rollback>
    </change>
    <change id="C2" priority="P0" source_item="T1/A1">
      <file path="fmri_first_level_proc/task_conn_first_level.py" action="modify" />
      <description>Same gate and vocabulary harmonization as C1, applied to task_conn run() return site.</description>
      <spec>
At lines 832-837, replace:

```python
    # Determine final status
    status = (
        "success_with_warnings"
        if any(w["severity"] != "low" for w in warnings)
        else "success"
    )
```

With:

```python
    # Determine final status
    status = "warning" if any(w.get("severity") == "high" for w in warnings) else "success"
```

Collapses multi-line expression to one line. Changes direct `["severity"]` access to defensive `.get("severity")` for consistency with C1. Gate logic changes from `!= "low"` to `== "high"`.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - same pattern as C1</risk>
      <rollback>Revert to original multi-line expression.</rollback>
    </change>
    <change id="C3" priority="P0" source_item="T1/A1">
      <file path="fmri_first_level_proc/rest_conn_first_level.py" action="modify" />
      <description>Same gate and vocabulary harmonization as C1/C2, applied to rest_conn run() return site.</description>
      <spec>
At lines 777-779, replace:

```python
    # Determine result status
    has_high_warning = any(w["severity"] != 'low' for w in warnings)
    status = "success_with_warnings" if has_high_warning else "success"
```

With:

```python
    # Determine result status
    status = "warning" if any(w.get("severity") == "high" for w in warnings) else "success"
```

Collapses two lines to one. Eliminates misleadingly-named `has_high_warning` variable (which actually checked `!= 'low'`). Changes direct `["severity"]` access to defensive `.get("severity")`. Gate logic changes from `!= "low"` to `== "high"`.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - same pattern as C1/C2</risk>
      <rollback>Revert to original two lines.</rollback>
    </change>
    <change id="C4" priority="P0" source_item="T2/A1">
      <file path="fmri_first_level_proc/task_act_first_level.py" action="modify" />
      <description>Update run() docstring to reflect new status vocabulary.</description>
      <spec>
At line 510, replace:

```python
        Structured result with status ('success' or 'success_with_warnings'),
```

With:

```python
        Structured result with status ('success' or 'warning'),
```
      </spec>
      <dependencies>C1 (same file; vocabulary must match the code change)</dependencies>
      <risk>low - single-line docstring edit</risk>
      <rollback>Revert the line.</rollback>
    </change>
    <change id="C5" priority="P0" source_item="T2/A1">
      <file path="fmri_first_level_proc/rest_conn_first_level.py" action="modify" />
      <description>Update run() docstring to reflect new status vocabulary.</description>
      <spec>
At line 594, replace:

```python
        Pipeline result with status ('success' or 'success_with_warnings'),
```

With:

```python
        Pipeline result with status ('success' or 'warning'),
```
      </spec>
      <dependencies>C3 (same file; vocabulary must match the code change)</dependencies>
      <risk>low - single-line docstring edit</risk>
      <rollback>Revert the line.</rollback>
    </change>
  </changes>
  <execution_order>C1, C4, C2, C3, C5</execution_order>
</implement_plan>
