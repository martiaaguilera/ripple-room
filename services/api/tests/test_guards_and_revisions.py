"""Gaps around stale revisions, /api/notice validation and spend-guard accounting.

No network: live-mode runs use an httpx MockTransport standing in for Nebius, and the
global quota is the in-memory FakeUpstash from test_quota.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import agent_routes
from app.core.budget import BudgetLimits, InferenceBudget
from app.core.config import Settings, get_settings
from app.core.quota import UpstashQuota
from app.core.ratelimit import ConcurrencyGate, SlidingWindowLimiter
from app.domain.models import Scenario
from app.domain.revision import baseline_revision
from app.main import create_app
from app.providers.nebius import NebiusProvider
from tests.test_quota import FakeUpstash

Json = dict[str, Any]


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def _demo_revision(client: TestClient) -> Json:
    rev: Json = client.get("/api/demo").json()["initial"]["revision"]
    return rev


def _shocked(client: TestClient, preset_id: str = "truck-delay-35") -> Json:
    res = client.post("/api/shock", json={"revision": _demo_revision(client), "preset_id": preset_id})
    assert res.status_code == 200, res.text
    rev: Json = res.json()["revision"]
    return rev


def _first_option(client: TestClient, rev: Json) -> Json:
    option: Json = client.post("/api/search", json={"revision": rev}).json()["options"][0]["evaluation"]
    assert option["status"] == "verified"
    return option


def _apply(client: TestClient, rev: Json, base_id: str, option: Json) -> httpx.Response:
    return client.post(
        "/api/apply",
        json={"revision": rev, "base_revision_id": base_id, "patch": option["patch"], "plan": option["plan"]},
    )


# --- stale revisions ----------------------------------------------------------------


def test_option_from_the_pre_shock_revision_is_stale(client: TestClient) -> None:
    """A real, older revision id (not a made-up one) is still refused with 409."""
    parent = _demo_revision(client)
    rev = _shocked(client)
    option = _first_option(client, rev)
    res = _apply(client, rev, parent["id"], option)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "STALE_REVISION"


def test_applying_the_same_option_twice_is_stale(client: TestClient) -> None:
    """Double submit: the second apply carries the new revision but the option's old base id."""
    rev = _shocked(client)
    option = _first_option(client, rev)
    first = _apply(client, rev, rev["id"], option)
    assert first.status_code == 200, first.text
    applied = first.json()["revision"]
    second = _apply(client, applied, rev["id"], option)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "STALE_REVISION"


def test_tampered_revision_is_refused_before_the_stale_check(client: TestClient) -> None:
    rev = _shocked(client)
    option = _first_option(client, rev)
    rev["state"]["shocks"] = []  # pretend the incident never happened, keep the old id
    res = _apply(client, rev, rev["id"], option)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_REVISION"


def test_apply_refuses_a_plan_edited_after_verification(client: TestClient) -> None:
    rev = _shocked(client)
    option = _first_option(client, rev)
    entries = option["plan"]["entries"]
    doors = next(e for e in entries if e["task_id"] == "doors-open")
    doors["start"] = 0  # claims doors open at midnight, before anything is built
    res = _apply(client, rev, rev["id"], option)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "PLAN_INVALID"


# --- /api/notice validation ------------------------------------------------------------


def _notice(client: TestClient, body: Json) -> httpx.Response:
    return client.post("/api/notice", json=body)


def test_notice_happy_path_lists_who_must_be_told(client: TestClient) -> None:
    rev = _shocked(client)
    option = _first_option(client, rev)
    res = _notice(client, {"revision": rev, "patch": option["patch"], "plan": option["plan"]})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["items"], "a recovery that moves work must notify someone"
    assert all(item["notify_by"] >= 0 for item in body["items"])


def test_notice_rejects_a_tampered_revision(client: TestClient) -> None:
    rev = _shocked(client)
    option = _first_option(client, rev)
    rev["state"]["plan"]["entries"][0]["start"] += 5
    res = _notice(client, {"revision": rev, "patch": option["patch"], "plan": option["plan"]})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_REVISION"


def test_notice_refuses_an_infeasible_plan(client: TestClient) -> None:
    """No crew notice is ever produced for a plan the validator rejects."""
    rev = _shocked(client)
    res = _notice(client, {"revision": rev, "patch": {"actions": []}, "plan": rev["state"]["plan"]})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "PLAN_INVALID"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: b["patch"].update(actions=[{"type": "exec", "cmd": "ls"}]),
        lambda b: b.update(extra="nope"),
        lambda b: b.pop("plan"),
        lambda b: b["patch"]["actions"].append({"type": "activate_resource", "resource_id": "trolley-2", "sql": "x"}),
    ],
    ids=["unknown-action", "extra-field", "missing-plan", "extra-action-field"],
)
def test_notice_body_is_schema_validated(client: TestClient, mutate: Any) -> None:
    rev = _shocked(client)
    option = _first_option(client, rev)
    body: Json = {"revision": rev, "patch": option["patch"], "plan": option["plan"]}
    mutate(body)
    res = _notice(client, body)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


# --- spend guard ----------------------------------------------------------------------------


@pytest.fixture
def live(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """Live settings with fresh, isolated guard state (budget, limiter, gate, quota)."""

    def make(**overrides: Any) -> InferenceBudget:
        settings = Settings(ai_mode="live", nebius_api_key="test-key", **overrides)
        budget = InferenceBudget(BudgetLimits(daily_tokens=10**9, daily_runs=1_000, per_ip_daily_runs=1_000))
        monkeypatch.setattr(agent_routes, "get_settings", lambda: settings)
        monkeypatch.setattr("app.api.routes.get_settings", lambda: settings)
        monkeypatch.setattr(agent_routes, "inference_budget", budget)
        monkeypatch.setattr("app.api.routes.inference_budget", budget)
        monkeypatch.setattr(agent_routes, "_limiter", SlidingWindowLimiter(100))
        monkeypatch.setattr(agent_routes, "_gate", ConcurrencyGate(4))
        monkeypatch.setattr(agent_routes, "_quota", None)
        return budget

    yield make
    get_settings.cache_clear()


def _fake_nebius(monkeypatch: pytest.MonkeyPatch, body: Json) -> list[Json]:
    """Route every live provider to a MockTransport; returns the requests it saw."""
    seen: list[Json] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=body)

    def provider(settings: Settings, *, model: str | None = None) -> NebiusProvider:
        return NebiusProvider(
            api_key="test-key",
            base_url="https://example.invalid/v1/",
            model=model or "nvidia/test-model",
            transport=httpx.MockTransport(handler),
            max_retries=0,
        )

    monkeypatch.setattr(agent_routes, "planner_provider", provider)
    monkeypatch.setattr(agent_routes, "fast_provider", lambda s: provider(s))
    return seen


def _quota(fake: FakeUpstash, daily: int = 10**7) -> UpstashQuota:
    return UpstashQuota(
        url="https://x.invalid",
        token="tok",
        daily_budget=daily,
        lifetime_budget=daily,
        transport=httpx.MockTransport(fake.handler),
    )


_NO_TOOLS: Json = {
    "id": "cmpl-test",
    "model": "nvidia/test-model",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "Rent a trolley."}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
}


def test_mock_runs_never_touch_the_live_budget(scenario: Scenario, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(ai_mode="mock", ai_kill_switch=True)
    budget = InferenceBudget(BudgetLimits(daily_tokens=0, daily_runs=0, per_ip_daily_runs=0))
    monkeypatch.setattr(agent_routes, "get_settings", lambda: settings)
    monkeypatch.setattr(agent_routes, "inference_budget", budget)
    client = TestClient(create_app())
    rev = baseline_revision(scenario).model_dump(mode="json")
    with client.stream("POST", "/api/recover", json={"revision": rev}) as res:
        assert res.status_code == 200
        assert "event: done" in "".join(res.iter_text())
    assert budget.snapshot()["runs"] == 0 and budget.snapshot()["tokens"] == 0
    get_settings.cache_clear()


def test_per_client_daily_cap_refuses_with_429(scenario: Scenario, live: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    live()
    capped = InferenceBudget(BudgetLimits(daily_tokens=10**9, daily_runs=1_000, per_ip_daily_runs=0))
    monkeypatch.setattr(agent_routes, "inference_budget", capped)
    seen = _fake_nebius(monkeypatch, _NO_TOOLS)
    client = TestClient(create_app())
    rev = baseline_revision(scenario).model_dump(mode="json")
    res = client.post("/api/recover", json={"revision": rev})
    assert res.status_code == 429 and res.json()["error"]["code"] == "RATE_LIMITED"
    assert seen == [], "no model call may happen after a refusal"


def test_rate_limit_refuses_before_any_model_call(
    scenario: Scenario, live: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    live()
    limiter = SlidingWindowLimiter(1)
    assert limiter.allow("interpret:testclient")  # this client already used its one request this minute
    monkeypatch.setattr(agent_routes, "_limiter", limiter)
    seen = _fake_nebius(monkeypatch, _NO_TOOLS)
    client = TestClient(create_app())
    rev = baseline_revision(scenario).model_dump(mode="json")
    res = client.post("/api/interpret", json={"revision": rev, "text": "truck 30 minutes late"})
    assert res.status_code == 429 and res.json()["error"]["code"] == "RATE_LIMITED"
    assert seen == []


def test_busy_engine_refunds_the_global_reservation(
    scenario: Scenario, live: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    live()
    fake = FakeUpstash()
    quota = _quota(fake)
    monkeypatch.setattr(agent_routes, "_quota", quota)
    monkeypatch.setattr(agent_routes, "_gate", ConcurrencyGate(0))
    seen = _fake_nebius(monkeypatch, _NO_TOOLS)
    client = TestClient(create_app())
    rev = baseline_revision(scenario).model_dump(mode="json")
    res = client.post("/api/recover", json={"revision": rev})
    assert res.status_code == 503 and res.json()["error"]["code"] == "BUSY"
    assert seen == []
    assert quota.usage()["today"] == 0, "a refused run must not keep its token reservation"


def test_live_run_charges_actual_tokens_and_refunds_the_rest(
    scenario: Scenario, live: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    budget = live()
    fake = FakeUpstash()
    quota = _quota(fake)
    monkeypatch.setattr(agent_routes, "_quota", quota)
    seen = _fake_nebius(monkeypatch, _NO_TOOLS)
    client = TestClient(create_app())
    shocked = client.post(
        "/api/shock",
        json={"revision": baseline_revision(scenario).model_dump(mode="json"), "preset_id": "truck-delay-35"},
    ).json()["revision"]
    with client.stream("POST", "/api/recover", json={"revision": shocked}) as res:
        assert res.status_code == 200
        body = "".join(res.iter_text())
    assert "event: done" in body
    used = 120 * len(seen)
    assert len(seen) >= 1
    assert budget.snapshot()["tokens"] == used and budget.snapshot()["runs"] == 1
    assert quota.usage()["today"] == used, "the 80k reservation is refunded down to what was really used"
    assert agent_routes._gate.try_acquire(), "the concurrency slot is released after the stream ends"


def test_interpret_failure_keeps_the_worst_case_charge(
    scenario: Scenario, live: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A model call that fails after reservation is charged at the reservation (usage unknown)."""
    live()
    fake = FakeUpstash()
    quota = _quota(fake)
    monkeypatch.setattr(agent_routes, "_quota", quota)
    _fake_nebius(monkeypatch, _NO_TOOLS)  # no tool call: interpret raises BAD_RESPONSE
    client = TestClient(create_app())
    rev = baseline_revision(scenario).model_dump(mode="json")
    res = client.post("/api/interpret", json={"revision": rev, "text": "truck 30 minutes late"})
    assert res.status_code == 503 and res.json()["error"]["code"] == "MODEL_UNAVAILABLE"
    assert quota.usage()["today"] == Settings().ai_interpret_token_reservation
