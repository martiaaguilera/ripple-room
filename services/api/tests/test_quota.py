"""Global quota: atomic reservation, refunds, fail-closed behaviour."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import agent_routes
from app.core.config import Settings, get_settings
from app.core.quota import QuotaUnavailableError, UpstashQuota
from app.domain.models import Scenario
from app.domain.revision import baseline_revision
from app.main import create_app


class FakeUpstash:
    """Minimal in-memory Redis emulating the reservation script atomically."""

    def __init__(self) -> None:
        self.data: dict[str, int] = {}
        self.calls: list[list[str]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        cmd: list[str] = json.loads(request.content)
        self.calls.append(cmd)
        assert request.headers["authorization"] == "Bearer tok"
        op = cmd[0].upper()
        if op == "EVAL":
            day_key, total_key = cmd[3], cmd[4]
            tokens, daily, lifetime = int(cmd[5]), int(cmd[6]), int(cmd[7])
            day = self.data.get(day_key, 0) + tokens
            total = self.data.get(total_key, 0) + tokens
            if day > daily or total > lifetime:
                return httpx.Response(200, json={"result": -1})
            self.data[day_key], self.data[total_key] = day, total
            return httpx.Response(200, json={"result": day})
        if op == "INCRBY":
            self.data[cmd[1]] = self.data.get(cmd[1], 0) + int(cmd[2])
            return httpx.Response(200, json={"result": self.data[cmd[1]]})
        if op == "DECRBY":
            self.data[cmd[1]] = self.data.get(cmd[1], 0) - int(cmd[2])
            return httpx.Response(200, json={"result": self.data[cmd[1]]})
        if op == "GET":
            return httpx.Response(200, json={"result": self.data.get(cmd[1])})
        return httpx.Response(200, json={"error": "unknown command"})


def _quota(fake: FakeUpstash, daily: int = 100_000, lifetime: int = 150_000) -> UpstashQuota:
    return UpstashQuota(
        url="https://x.invalid",
        token="tok",
        daily_budget=daily,
        lifetime_budget=lifetime,
        transport=httpx.MockTransport(fake.handler),
    )


def test_reserve_and_refund() -> None:
    fake = FakeUpstash()
    q = _quota(fake)
    r = q.reserve(80_000)
    assert r is not None
    q.refund(r, used=30_000)
    usage = q.usage()
    assert usage["today"] == 30_000 and usage["total"] == 30_000


def test_reservation_refused_when_daily_budget_would_be_exceeded() -> None:
    q = _quota(FakeUpstash(), daily=100_000)
    assert q.reserve(80_000) is not None
    assert q.reserve(80_000) is None
    assert q.usage()["today"] == 80_000  # the refused reservation left no trace


def test_lifetime_budget_caps_total_spend_across_days() -> None:
    q = _quota(FakeUpstash(), daily=10**9, lifetime=100_000)
    assert q.reserve(60_000) is not None
    assert q.reserve(60_000) is None


def test_unreachable_store_raises_so_callers_fail_closed() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    q = UpstashQuota(
        url="https://x.invalid", token="tok", daily_budget=1, lifetime_budget=1, transport=httpx.MockTransport(down)
    )
    with pytest.raises(QuotaUnavailableError):
        q.reserve(10)


def test_store_error_payload_raises() -> None:
    q = UpstashQuota(
        url="https://x.invalid",
        token="tok",
        daily_budget=1,
        lifetime_budget=1,
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"error": "WRONGPASS"})),
    )
    with pytest.raises(QuotaUnavailableError):
        q.reserve(10)


@pytest.fixture
def live(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    def make(**overrides: Any) -> None:
        settings = Settings(ai_mode="live", nebius_api_key="test-key", **overrides)
        monkeypatch.setattr(agent_routes, "get_settings", lambda: settings)
        monkeypatch.setattr("app.api.routes.get_settings", lambda: settings)
        monkeypatch.setattr(agent_routes, "_quota", None)

    yield make
    get_settings.cache_clear()


def test_required_quota_missing_fails_closed(scenario: Scenario, live) -> None:  # type: ignore[no-untyped-def]
    live(ai_require_global_quota=True)
    client = TestClient(create_app())
    rev = baseline_revision(scenario).model_dump(mode="json")
    res = client.post("/api/recover", json={"revision": rev})
    assert res.status_code == 503 and res.json()["error"]["code"] == "AI_PAUSED"
    assert client.get("/api/health").json()["ai"]["status"] == "paused"
    assert client.post("/api/search", json={"revision": rev}).status_code == 200


def test_exhausted_global_quota_refuses_before_model_call(
    scenario: Scenario, live, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    live()
    monkeypatch.setattr(agent_routes, "_quota", _quota(FakeUpstash(), daily=1, lifetime=1))
    client = TestClient(create_app())
    rev = baseline_revision(scenario).model_dump(mode="json")
    res = client.post("/api/interpret", json={"revision": rev, "text": "truck 30 minutes late"})
    assert res.status_code == 503 and res.json()["error"]["code"] == "AI_BUDGET_EXHAUSTED"
