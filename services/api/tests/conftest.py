from __future__ import annotations

import pytest

from app.domain.models import Scenario
from app.fixtures import load_scenario


@pytest.fixture(scope="session")
def scenario() -> Scenario:
    return load_scenario()
