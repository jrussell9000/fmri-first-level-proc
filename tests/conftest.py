import logging

import pytest

from fmri_first_level_proc.reporting import clear_warnings


@pytest.fixture
def logger():
    return logging.getLogger("fmri_first_level_proc.tests")


@pytest.fixture(autouse=True)
def _clear_warning_accumulator():
    clear_warnings()
    yield
    clear_warnings()
