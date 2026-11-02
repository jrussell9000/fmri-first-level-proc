import logging

import pytest

from fmri_first_level_proc import afni
from fmri_first_level_proc.reporting import clear_warnings


@pytest.fixture
def logger():
    return logging.getLogger("fmri_first_level_proc.tests")


@pytest.fixture(autouse=True)
def _reset_module_state():
    clear_warnings()
    afni._3DINFO_CACHE.clear()
    yield
    clear_warnings()
    afni._3DINFO_CACHE.clear()
