"""
fmri_first_level_proc: First-level fMRI analysis framework.

A general-purpose Python package for first-level (within-participant)
fMRI analyses including task activation, task connectivity (beta series),
and resting-state connectivity. Built on AFNI.
"""

__version__ = "4.0.0"

# Public API
from .first_level_config import (
    load_and_validate, load_and_validate_blocks, BlockResolution, ResolvedConfig,
)
from .first_level_utils import setup_logging, FirstLevelResult, graded_warning, get_warnings, clear_warnings
from .run_first_level import DISPATCH
from .exceptions import ToolVersionError

__all__ = [
    'load_and_validate', 'load_and_validate_blocks', 'BlockResolution', 'ResolvedConfig',
    'setup_logging', 'FirstLevelResult', 'graded_warning',
    'get_warnings', 'clear_warnings',
    'DISPATCH', 'ToolVersionError', '__version__',
]

# Pipeline-specific imports (importable but not in __all__)
from .task_act_first_level import run as run_task_act
from .task_conn_first_level import run as run_task_conn
from .rest_conn_first_level import run as run_rest_conn
