<implement_plan>
  <meta project="fmri-first-level-proc" mode="implement" submodule="plan" timestamp="2026-08-19T14:51:36Z" />
  <input_reports>
    <report path="fmri-proc-orchestrator:fmri-proc-orchestrator_brainstorm_20260819_144504.md" mode="brainstorm" key_items="1" />
  </input_reports>
  <changes>
    <change id="C1" priority="P0" source_item="T9c">
      <file path="fmri_first_level_proc/task_act_first_level.py" action="modify" />
      <description>Fix status vocabulary and severity gating. Currently uses "success_with_warnings" (non-standard) and a non-low severity gate. Must change to "warning" vocabulary and high-only severity gating.</description>
      <spec>
At lines 764-765, replace:

```python
has_non_low = any(w.get("severity") != "low" for w in _warnings)
status = "success_with_warnings" if has_non_low else "success"
```

With:

```python
status = "warning" if any(w.get("severity") == "high" for w in _warnings) else "success"
```

Changes:
1. Status vocabulary: "success_with_warnings" -> "warning" (harmonized contract).
2. Severity gate: non-low (catches medium AND high) -> high-only (only high triggers status="warning").
3. Collapsed from two lines to one (intermediate variable `has_non_low` is no longer needed).
      </spec>
      <dependencies>none</dependencies>
      <risk>low - vocabulary and gate change; the run_first_level.py dispatcher already uses high-only gating for exit code 3</risk>
      <rollback>Revert the two lines.</rollback>
    </change>
    <change id="C2" priority="P0" source_item="T9c">
      <file path="fmri_first_level_proc/task_conn_first_level.py" action="modify" />
      <description>Same fix as C1: status vocabulary and severity gating standardization.</description>
      <spec>
At lines 833-837, replace:

```python
status = (
    "success_with_warnings"
    if any(w["severity"] != "low" for w in warnings)
    else "success"
)
```

With:

```python
status = "warning" if any(w.get("severity") == "high" for w in warnings) else "success"
```

Changes:
1. Status vocabulary: "success_with_warnings" -> "warning".
2. Severity gate: non-low -> high-only.
3. Defensive `.get("severity")` instead of direct `["severity"]` access (consistency with C1).
4. Collapsed from multi-line to single line.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - same pattern as C1</risk>
      <rollback>Revert the lines.</rollback>
    </change>
    <change id="C3" priority="P0" source_item="T9c">
      <file path="fmri_first_level_proc/rest_conn_first_level.py" action="modify" />
      <description>Same fix as C1/C2: status vocabulary and severity gating standardization.</description>
      <spec>
At lines 778-779, replace:

```python
has_high_warning = any(w["severity"] != 'low' for w in warnings)
status = "success_with_warnings" if has_high_warning else "success"
```

With:

```python
status = "warning" if any(w.get("severity") == "high" for w in warnings) else "success"
```

Changes:
1. Status vocabulary: "success_with_warnings" -> "warning".
2. Severity gate: non-low -> high-only. Note: the variable was named `has_high_warning` but actually checked `!= 'low'` (i.e., medium OR high). The fix corrects both the logic and eliminates the misleading variable name.
3. Defensive `.get("severity")` access.
4. Collapsed from two lines to one.
      </spec>
      <dependencies>none</dependencies>
      <risk>low - same pattern as C1/C2</risk>
      <rollback>Revert the two lines.</rollback>
    </change>
  </changes>
  <execution_order>C1, C2, C3</execution_order>
</implement_plan>
