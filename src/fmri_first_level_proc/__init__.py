"""
fmri_first_level_proc — First-level fMRI analysis framework.

A general-purpose Python package for first-level (within-participant)
fMRI analyses including task activation, task connectivity (beta series),
and resting-state connectivity. Built on AFNI.
"""

__version__ = "3.1.0"

# Public API
from .config import load_and_validate, ResolvedConfig
from .reporting import setup_logging, FirstLevelResult, graded_warning, get_warnings, clear_warnings
from .pipelines import DISPATCH
from .exceptions import ToolVersionError

__all__ = [
    'load_and_validate', 'ResolvedConfig',
    'setup_logging', 'FirstLevelResult', 'graded_warning',
    'get_warnings', 'clear_warnings',
    'DISPATCH', 'ToolVersionError', '__version__',
]

# Pipeline-specific imports — importable but not in __all__
from .pipelines import run_task_act, run_task_conn, run_rest_conn  # noqa: F401
