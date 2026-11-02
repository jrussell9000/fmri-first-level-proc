"""Analysis pipelines and the analysis-type dispatch table."""

from .rest_conn import run as run_rest_conn
from .task_act import run as run_task_act
from .task_conn import run as run_task_conn

# Dispatch table: analysis_type string -> pipeline run() function
DISPATCH = {
    "task_act": run_task_act,
    "task_conn": run_task_conn,
    "rest_conn": run_rest_conn,
}

__all__ = ["DISPATCH", "run_task_act", "run_task_conn", "run_rest_conn"]
