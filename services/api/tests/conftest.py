from __future__ import annotations

import os

import pytest

# Tests are hermetic: never read live credentials from a developer's .env, never call Nebius.
os.environ["AI_MODE"] = "mock"
os.environ["NEBIUS_API_KEY"] = ""

from app.domain.models import Scenario
from app.fixtures import load_scenario


@pytest.fixture(scope="session")
def scenario() -> Scenario:
    return load_scenario()
