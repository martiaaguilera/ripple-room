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


@pytest.fixture(autouse=True)
def fresh_process_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rate limiters, budgets and the concurrency gate are per-process singletons; give each test fresh ones."""
    from app.api import agent_routes, routes
    from app.core.budget import BudgetLimits, InferenceBudget
    from app.core.ratelimit import ConcurrencyGate, SlidingWindowLimiter

    settings = agent_routes.get_settings()
    monkeypatch.setattr(routes, "_solver_limiter", SlidingWindowLimiter(settings.solver_rate_per_minute))
    monkeypatch.setattr(agent_routes, "_limiter", SlidingWindowLimiter(settings.recover_rate_per_minute))
    monkeypatch.setattr(agent_routes, "_gate", ConcurrencyGate(settings.recover_max_concurrent))
    budget = InferenceBudget(
        BudgetLimits(
            daily_tokens=settings.ai_daily_token_budget,
            daily_runs=settings.ai_daily_run_budget,
            per_ip_daily_runs=settings.ai_per_ip_daily_runs,
        )
    )
    monkeypatch.setattr(agent_routes, "inference_budget", budget)
    monkeypatch.setattr(routes, "inference_budget", budget)
    monkeypatch.setattr(agent_routes, "_quota", None)
