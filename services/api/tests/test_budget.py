"""Spend controls: kill switch, daily budgets, per-client caps, unforgeable client key."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.api import agent_routes
from app.core.budget import BudgetLimits, InferenceBudget
from app.core.config import Settings, get_settings
from app.domain.models import Scenario
from app.domain.revision import baseline_revision
from app.main import create_app


def test_daily_run_budget() -> None:
    b = InferenceBudget(BudgetLimits(daily_tokens=10_000, daily_runs=2, per_ip_daily_runs=10))
    assert b.try_start("a") is None and b.try_start("b") is None
    assert b.try_start("c") == "budget" and b.exhausted()


def test_daily_token_budget() -> None:
    b = InferenceBudget(BudgetLimits(daily_tokens=1_000, daily_runs=100, per_ip_daily_runs=100))
    assert b.try_start("a") is None
    b.record_tokens(1_200)
    assert b.try_start("a") == "budget"


def test_per_client_cap() -> None:
    b = InferenceBudget(BudgetLimits(daily_tokens=10**9, daily_runs=100, per_ip_daily_runs=1))
    assert b.try_start("a") is None
    assert b.try_start("a") == "client"
    assert b.try_start("b") is None


def _request(headers: dict[str, str]) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "headers": raw, "client": ("10.0.0.9", 1234)})


def test_client_key_prefers_platform_headers_over_forgeable_ones() -> None:
    forged = {"x-forwarded-for": "1.2.3.4, 9.9.9.9", "x-vercel-forwarded-for": "5.6.7.8"}
    assert agent_routes._client_key(_request(forged)) == "5.6.7.8"
    assert agent_routes._client_key(_request({"x-forwarded-for": "1.2.3.4, 9.9.9.9"})) == "9.9.9.9"
    assert agent_routes._client_key(_request({})) == "10.0.0.9"


@pytest.fixture
def live_settings(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    def make(**overrides: object) -> None:
        settings = Settings(ai_mode="live", nebius_api_key="test-key", **overrides)  # type: ignore[arg-type]
        monkeypatch.setattr(agent_routes, "get_settings", lambda: settings)
        monkeypatch.setattr("app.api.routes.get_settings", lambda: settings)

    yield make
    get_settings.cache_clear()


def test_kill_switch_blocks_live_ai_before_any_model_call(scenario: Scenario, live_settings) -> None:  # type: ignore[no-untyped-def]
    live_settings(ai_kill_switch=True)
    client = TestClient(create_app())
    rev = baseline_revision(scenario).model_dump(mode="json")
    for path, body in (
        ("/api/recover", {"revision": rev}),
        ("/api/interpret", {"revision": rev, "text": "truck late 30 minutes"}),
    ):
        res = client.post(path, json=body)
        assert res.status_code == 503 and res.json()["error"]["code"] == "AI_PAUSED"
    assert client.get("/api/health").json()["ai"]["status"] == "paused"
    # Deterministic features keep working.
    assert client.post("/api/search", json={"revision": rev}).status_code == 200


def test_exhausted_budget_refuses_live_runs(scenario: Scenario, live_settings, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    live_settings()
    exhausted = InferenceBudget(BudgetLimits(daily_tokens=0, daily_runs=0, per_ip_daily_runs=0))
    monkeypatch.setattr(agent_routes, "inference_budget", exhausted)
    monkeypatch.setattr("app.api.routes.inference_budget", exhausted)
    client = TestClient(create_app())
    rev = baseline_revision(scenario).model_dump(mode="json")
    res = client.post("/api/recover", json={"revision": rev})
    assert res.status_code == 503 and res.json()["error"]["code"] == "AI_BUDGET_EXHAUSTED"
    assert client.get("/api/health").json()["ai"]["status"] == "budget_exhausted"
