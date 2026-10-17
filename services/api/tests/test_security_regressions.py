"""Regressions for the security audit findings (slot leak, budget ordering, overshoot, limits)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.agent.interpret import interpret
from app.api import agent_routes
from app.core.budget import BudgetLimits, InferenceBudget
from app.core.config import Settings, get_settings
from app.core.quota import Reservation
from app.domain.models import Plan, Scenario
from app.domain.revision import RevisionState, baseline_revision, make_revision
from app.main import create_app
from app.providers.base import ProviderError
from app.providers.nebius import NebiusProvider
from tests.test_quota import FakeUpstash, _quota


def _forged_empty_plan(scenario: Scenario) -> dict[str, Any]:
    state = baseline_revision(scenario).state.model_copy(update={"plan": Plan(entries=())})
    return make_revision(RevisionState.model_validate(state.model_dump())).model_dump(mode="json")


def test_forged_plan_is_rejected_before_taking_a_slot(scenario: Scenario) -> None:
    client = TestClient(create_app())
    before = agent_routes._gate._active
    for _ in range(5):
        res = client.post("/api/recover", json={"revision": _forged_empty_plan(scenario)})
        assert res.status_code == 400 and res.json()["error"]["code"] == "INVALID_REVISION"
    assert agent_routes._gate._active == before


def test_forged_plan_rejected_by_solver_endpoints_too(scenario: Scenario) -> None:
    client = TestClient(create_app())
    for path in ("/api/view", "/api/search"):
        res = client.post(path, json={"revision": _forged_empty_plan(scenario)})
        assert res.status_code == 400, path


def test_completed_stream_releases_the_slot(scenario: Scenario) -> None:
    client = TestClient(create_app())
    before = agent_routes._gate._active
    rev = baseline_revision(scenario).model_dump(mode="json")
    with client.stream("POST", "/api/recover", json={"revision": rev}) as res:
        assert res.status_code == 200
        "".join(res.iter_text())
    assert agent_routes._gate._active == before


def test_busy_instance_does_not_consume_the_daily_allowance(
    scenario: Scenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(ai_mode="live", nebius_api_key="test-key")
    monkeypatch.setattr(agent_routes, "get_settings", lambda: settings)
    budget = InferenceBudget(BudgetLimits(daily_tokens=10**9, daily_runs=100, per_ip_daily_runs=100))
    monkeypatch.setattr(agent_routes, "inference_budget", budget)
    monkeypatch.setattr(agent_routes._gate, "_active", agent_routes._gate._limit)  # instance full
    try:
        res = TestClient(create_app()).post(
            "/api/recover", json={"revision": baseline_revision(scenario).model_dump(mode="json")}
        )
        assert res.status_code == 503 and res.json()["error"]["code"] == "BUSY"
        assert budget.snapshot()["runs"] == 0
    finally:
        get_settings.cache_clear()


def test_quota_overshoot_is_charged() -> None:
    fake = FakeUpstash()
    q = _quota(fake)
    reservation = q.reserve(10_000)
    assert isinstance(reservation, Reservation)
    q.refund(reservation, used=12_500)
    assert q.usage()["today"] == 12_500


def test_solver_endpoints_are_rate_limited(scenario: Scenario, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import routes
    from app.core.ratelimit import SlidingWindowLimiter

    monkeypatch.setattr(routes, "_solver_limiter", SlidingWindowLimiter(2))
    client = TestClient(create_app())
    rev = baseline_revision(scenario).model_dump(mode="json")
    codes = [client.post("/api/search", json={"revision": rev}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


async def test_non_list_incidents_is_a_bad_response(scenario: Scenario) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        args = {"incidents": "truck late", "priorities": {}, "unclear": [], "summary": ""}
        msg = {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "c", "type": "function", "function": {"name": "report_situation", "arguments": json.dumps(args)}}
            ],
        }
        return httpx.Response(200, json={"model": "m", "choices": [{"message": msg}], "usage": {"total_tokens": 9}})

    provider = NebiusProvider(
        api_key="k", base_url="https://x.invalid/v1", model="m", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(ProviderError) as info:
        await interpret(scenario, "truck late", provider)
    assert info.value.code == "BAD_RESPONSE"


def test_client_supplied_preference_source_is_ignored(scenario: Scenario) -> None:
    client = TestClient(create_app())
    rev = baseline_revision(scenario).model_dump(mode="json")
    res = client.post("/api/search", json={"revision": rev, "preferences": {"source": "model"}})
    assert res.status_code == 200


def test_correlation_id_is_sanitised() -> None:
    client = TestClient(create_app())
    assert client.get("/api/health", headers={"x-correlation-id": "abc-123"}).headers["x-correlation-id"] == "abc-123"
    weird = client.get("/api/health", headers={"x-correlation-id": "<script>" * 50}).headers["x-correlation-id"]
    assert "<" not in weird and len(weird) <= 64


def test_kill_switch_refuses_recover_before_any_solver_work(
    scenario: Scenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(ai_mode="live", nebius_api_key="test-key", ai_kill_switch=True)
    monkeypatch.setattr(agent_routes, "get_settings", lambda: settings)

    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("context build (playbook search) must not run when AI is paused")

    monkeypatch.setattr(agent_routes.AgentContext, "build", boom)
    try:
        res = TestClient(create_app()).post(
            "/api/recover", json={"revision": baseline_revision(scenario).model_dump(mode="json")}
        )
        assert res.status_code == 503 and res.json()["error"]["code"] == "AI_PAUSED"
    finally:
        get_settings.cache_clear()


def test_recover_is_rate_limited_before_solver_work(scenario: Scenario, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.ratelimit import SlidingWindowLimiter

    monkeypatch.setattr(agent_routes, "_limiter", SlidingWindowLimiter(1))
    client = TestClient(create_app())
    rev = baseline_revision(scenario).model_dump(mode="json")
    with client.stream("POST", "/api/recover", json={"revision": rev}) as first:
        assert first.status_code == 200
        "".join(first.iter_text())
    assert client.post("/api/recover", json={"revision": rev}).status_code == 429


def test_unknown_resource_in_forged_plan_is_400_everywhere(scenario: Scenario) -> None:
    state = baseline_revision(scenario).state
    entries = tuple(
        e.model_copy(update={"assignments": {"crew": "ghost-crew"}}) if e.task_id == "unload-truss" else e
        for e in state.plan.entries
    )
    forged = make_revision(state.model_copy(update={"plan": Plan(entries=entries)})).model_dump(mode="json")
    client = TestClient(create_app())
    for path, extra in (("/api/view", {}), ("/api/search", {})):
        assert client.post(path, json={"revision": forged, **extra}).status_code == 400, path
    assert client.post("/api/shock", json={"revision": forged, "preset_id": "truck-delay-35"}).status_code == 400
    plan = baseline_revision(scenario).state.plan.model_dump(mode="json")
    assert (
        client.post("/api/notice", json={"revision": forged, "patch": {"actions": []}, "plan": plan}).status_code == 400
    )


def test_failed_live_run_keeps_its_whole_reservation(scenario: Scenario, monkeypatch: pytest.MonkeyPatch) -> None:
    """A provider error may follow a billed call: the global quota must not refund it."""
    settings = Settings(ai_mode="live", nebius_api_key="test-key", agent_max_total_tokens=50_000)
    monkeypatch.setattr(agent_routes, "get_settings", lambda: settings)
    fake = FakeUpstash()
    monkeypatch.setattr(agent_routes, "_quota", _quota(fake, daily=10**9, lifetime=10**9))
    failing = NebiusProvider(
        api_key="k",
        base_url="https://x.invalid/v1",
        model="m",
        max_retries=0,
        transport=httpx.MockTransport(lambda r: httpx.Response(500, json={})),
    )
    monkeypatch.setattr(agent_routes, "planner_provider", lambda _s: failing)
    try:
        rev = baseline_revision(scenario).model_dump(mode="json")
        with TestClient(create_app()).stream("POST", "/api/recover", json={"revision": rev}) as res:
            assert res.status_code == 200
            body = "".join(res.iter_text())
        assert "event: error" in body
        assert agent_routes._quota is not None
        assert agent_routes._quota.usage()["today"] == 50_000
    finally:
        get_settings.cache_clear()


async def test_rejected_interpretation_items_are_not_a_free_text_channel(scenario: Scenario) -> None:
    long_text = "x" * 5000
    args = {
        "incidents": [
            {"kind": "task_delay", "task_id": "ghost", "delay_minutes": 5, "evidence": long_text, "essay": long_text}
        ],
        "priorities": {},
        "unclear": 7,
        "summary": "",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        msg = {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "c", "type": "function", "function": {"name": "report_situation", "arguments": json.dumps(args)}}
            ],
        }
        return httpx.Response(200, json={"model": "m", "choices": [{"message": msg}], "usage": {"total_tokens": 9}})

    provider = NebiusProvider(
        api_key="k", base_url="https://x.invalid/v1", model="m", transport=httpx.MockTransport(handler)
    )
    result = await interpret(scenario, "late", provider)
    raw = result.rejected[0].raw
    assert "essay" not in raw and len(raw["evidence"]) <= 120
    assert result.unclear[0] == "7"
