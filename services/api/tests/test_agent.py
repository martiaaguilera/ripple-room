"""Agent loop, tool boundary and Nebius adapter tests (no network: httpx MockTransport)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.agent.runner import AgentEvent, Budget, run_agent
from app.agent.tools import AgentContext, execute_tool
from app.core.config import Settings, get_settings
from app.domain.effective import compile_problem
from app.domain.models import Scenario
from app.domain.revision import Revision, baseline_revision
from app.fixtures import preset
from app.main import create_app
from app.providers.base import ProviderError
from app.providers.factory import planner_provider
from app.providers.mock import MockProvider
from app.providers.nebius import NebiusProvider
from app.services.workflow import add_shock

BUDGET = Budget(max_model_calls=8, max_total_tokens=50_000, timeout_seconds=30, max_output_tokens=1024)


def _shocked(scenario: Scenario, preset_id: str = "truck-delay-35") -> Revision:
    return add_shock(baseline_revision(scenario), preset(preset_id).shock).revision


def _ctx(scenario: Scenario, revision: Revision, max_evaluations: int = 6) -> AgentContext:
    problem, _ = compile_problem(scenario, revision.state.shocks, revision.state.committed)
    assert problem is not None
    return AgentContext.build(scenario, revision, problem, max_evaluations)


async def _collect(ctx: AgentContext, provider: Any, budget: Budget = BUDGET) -> list[AgentEvent]:
    return [ev async for ev in run_agent(ctx, provider, budget, "Keep costs low.", mode_label="test")]


# --- tool boundary -------------------------------------------------------------


def test_unknown_tool_is_rejected(scenario: Scenario) -> None:
    out = execute_tool(_ctx(scenario, _shocked(scenario)), "run_shell", '{"cmd": "ls"}')
    assert not out.ok and "unknown tool" in out.content["error"]


def test_invalid_json_arguments_are_rejected(scenario: Scenario) -> None:
    out = execute_tool(_ctx(scenario, _shocked(scenario)), "evaluate_patch", "{not json")
    assert not out.ok


def test_extra_fields_in_actions_are_rejected(scenario: Scenario) -> None:
    args = json.dumps(
        {"actions": [{"type": "activate_resource", "resource_id": "trolley-2", "sql": "drop"}], "rationale": "x"}
    )
    out = execute_tool(_ctx(scenario, _shocked(scenario)), "evaluate_patch", args)
    assert not out.ok and out.content["error"] == "invalid arguments"


def test_null_optional_fields_are_tolerated(scenario: Scenario) -> None:
    args = json.dumps(
        {
            "actions": [{"type": "activate_resource", "resource_id": "trolley-2", "task_id": None, "start": ""}],
            "rationale": "x",
        }
    )
    out = execute_tool(_ctx(scenario, _shocked(scenario)), "evaluate_patch", args)
    assert out.ok and out.content["status"] == "verified"


def test_pin_start_accepts_clock_strings(scenario: Scenario) -> None:
    args = json.dumps({"actions": [{"type": "pin_start", "task_id": "unload-av", "start": "14:35"}], "rationale": "x"})
    out = execute_tool(_ctx(scenario, _shocked(scenario)), "evaluate_patch", args)
    assert out.ok and out.content["status"] in ("verified", "infeasible")


def test_cannot_submit_unverified_candidates(scenario: Scenario) -> None:
    ctx = _ctx(scenario, _shocked(scenario))
    bad = execute_tool(
        ctx,
        "evaluate_patch",
        json.dumps({"actions": [{"type": "activate_resource", "resource_id": "backup-av"}], "rationale": "x"}),
    )
    assert bad.content["status"] == "infeasible"
    out = execute_tool(
        ctx,
        "submit_options",
        json.dumps({"options": [{"candidate_id": "c1", "title": "t", "why": "w"}], "summary": "s"}),
    )
    assert not out.ok and not out.terminal
    fake = execute_tool(
        ctx,
        "submit_options",
        json.dumps({"options": [{"candidate_id": "c99", "title": "t", "why": "w"}], "summary": "s"}),
    )
    assert not fake.ok


def test_evaluation_budget_is_enforced(scenario: Scenario) -> None:
    ctx = _ctx(scenario, _shocked(scenario), max_evaluations=1)
    args = json.dumps({"actions": [{"type": "activate_resource", "resource_id": "trolley-2"}], "rationale": "x"})
    assert execute_tool(ctx, "evaluate_patch", args).ok
    second = execute_tool(ctx, "evaluate_patch", args)
    assert not second.ok and "budget" in second.content["error"]


def test_situation_reports_breach(scenario: Scenario) -> None:
    out = execute_tool(_ctx(scenario, _shocked(scenario)), "get_situation", "{}")
    assert out.content["deadline"] == "18:00"
    assert out.content["minutes_late"] > 0
    assert out.content["driving_path"]


# --- loop with mock provider ------------------------------------------------------


async def test_mock_run_produces_only_verified_options(scenario: Scenario) -> None:
    events = await _collect(_ctx(scenario, _shocked(scenario)), MockProvider())
    kinds = [e.type for e in events]
    assert kinds[0] == "run_started" and kinds[-1] == "done"
    assert events[0].data["live"] is False
    options = next(e for e in events if e.type == "options")
    assert options.data["finalized_by_model"] is True
    assert options.data["options"], "mock should find at least one verified option"
    assert all(o["evaluation"]["status"] == "verified" for o in options.data["options"])
    assert next(e for e in events if e.type == "done").data["stop_reason"] == "submitted"


async def test_mock_run_on_impossible_case_returns_no_options(scenario: Scenario) -> None:
    events = await _collect(_ctx(scenario, _shocked(scenario, "truck-breakdown-90")), MockProvider(max_evaluations=6))
    options = next(e for e in events if e.type == "options")
    assert options.data["options"] == []


# --- loop with fake Nebius transport ----------------------------------------------


def _completion(
    tool_calls: list[tuple[str, dict[str, Any] | str]] | None = None, content: str | None = None
) -> dict[str, Any]:
    msg: dict[str, Any] = {
        "role": "assistant",
        "content": content,
        "reasoning_content": "Thinking about the driving path.",
    }
    if tool_calls:
        msg["tool_calls"] = [
            {
                "id": f"call_{i}",
                "type": "function",
                "function": {"name": n, "arguments": a if isinstance(a, str) else json.dumps(a)},
            }
            for i, (n, a) in enumerate(tool_calls)
        ]
    return {
        "id": "cmpl-test",
        "model": "nvidia/test-model",
        "choices": [{"index": 0, "message": msg, "finish_reason": "tool_calls" if tool_calls else "stop"}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
    }


def _transport(
    script: list[Callable[[httpx.Request], httpx.Response]],
) -> tuple[httpx.MockTransport, list[dict[str, Any]]]:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        assert request.headers["authorization"] == "Bearer test-key"
        return script[min(len(seen) - 1, len(script) - 1)](request)

    return httpx.MockTransport(handler), seen


def _ok(body: dict[str, Any]) -> Callable[[httpx.Request], httpx.Response]:
    return lambda _r: httpx.Response(200, json=body, headers={"x-request-id": "req-123"})


def _provider(transport: httpx.MockTransport, retries: int = 2) -> NebiusProvider:
    return NebiusProvider(
        api_key="test-key",
        base_url="https://example.invalid/v1/",
        model="nvidia/test-model",
        transport=transport,
        max_retries=retries,
    )


async def test_nebius_loop_revises_after_infeasible_candidate(
    scenario: Scenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.providers.nebius.asyncio.sleep", _no_sleep)
    transport, seen = _transport(
        [
            _ok(_completion([("get_situation", {})])),
            _ok(
                _completion(
                    [
                        (
                            "evaluate_patch",
                            {
                                "actions": [{"type": "activate_resource", "resource_id": "backup-av"}],
                                "rationale": "More AV hands.",
                            },
                        )
                    ]
                )
            ),
            _ok(
                _completion(
                    [
                        (
                            "evaluate_patch",
                            {
                                "actions": [{"type": "activate_resource", "resource_id": "trolley-2"}],
                                "rationale": "Parallel unloads.",
                            },
                        )
                    ]
                )
            ),
            _ok(
                _completion(
                    [
                        (
                            "submit_options",
                            {
                                "options": [
                                    {
                                        "candidate_id": "c2",
                                        "title": "Rent a second trolley",
                                        "why": "Unload truss and deck in parallel.",
                                    }
                                ],
                                "summary": "One option.",
                            },
                        )
                    ]
                )
            ),
        ]
    )
    events = await _collect(_ctx(scenario, _shocked(scenario)), _provider(transport))
    phases = [e.data["name"] for e in events if e.type == "phase"]
    assert "revise" in phases
    model_calls = [e for e in events if e.type == "model_call"]
    assert model_calls[0].data["request_id"] == "req-123"
    assert model_calls[0].data["reasoning_returned"] is True
    assert "Thinking about the driving path" not in json.dumps([e.model_dump() for e in events])
    options = next(e for e in events if e.type == "options").data["options"]
    by_id = {o["candidate_id"]: o for o in options}
    assert by_id["c2"]["model_rank"] == 1 and by_id["c2"]["origin"] == "model"
    assert {o["origin"] for o in options if o["candidate_id"] != "c2"} == {"playbook"}
    # Tool results are fed back to the model as tool messages.
    assert any(m.get("role") == "tool" for m in seen[-1]["messages"])
    assert seen[0]["tools"] and seen[0]["model"] == "nvidia/test-model"


async def test_nebius_loop_respects_model_call_budget(scenario: Scenario) -> None:
    transport, seen = _transport([_ok(_completion([("get_situation", {})]))])
    budget = Budget(max_model_calls=3, max_total_tokens=50_000, timeout_seconds=30, max_output_tokens=512)
    events = await _collect(_ctx(scenario, _shocked(scenario)), _provider(transport), budget)
    assert len(seen) == 3
    done = next(e for e in events if e.type == "done")
    assert done.data["stop_reason"] == "budget_exhausted"


async def test_nebius_loop_stops_when_model_will_not_use_tools(scenario: Scenario) -> None:
    transport, seen = _transport([_ok(_completion(content="I think you should rent a trolley."))])
    events = await _collect(_ctx(scenario, _shocked(scenario)), _provider(transport))
    assert len(seen) == 2  # one nudge, then stop
    assert next(e for e in events if e.type == "done").data["stop_reason"] == "no_tool_calls"
    # The model contributed nothing; only the verified playbook options are offered, labelled as such.
    options = next(e for e in events if e.type == "options").data["options"]
    assert options and {o["origin"] for o in options} == {"playbook"}


async def _no_sleep(_s: float) -> None:
    return None


@pytest.mark.parametrize(
    ("status", "body", "code"),
    [
        (401, {"error": "unauthorized"}, "MODEL_UNAVAILABLE"),
        (402, {"error": "insufficient balance"}, "CREDIT_EXHAUSTED"),
        (404, {"error": "model not found"}, "MODEL_UNAVAILABLE"),
        (429, {"error": "slow down"}, "RATE_LIMITED"),
        (503, {"error": "overloaded"}, "MODEL_UNAVAILABLE"),
    ],
)
async def test_nebius_error_mapping(
    status: int, body: dict[str, Any], code: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.providers.nebius.asyncio.sleep", _no_sleep)
    transport, seen = _transport([lambda _r: httpx.Response(status, json=body)])
    with pytest.raises(ProviderError) as info:
        await _provider(transport).complete([{"role": "user", "content": "hi"}])
    assert info.value.code == code
    retryable = status in (429, 503)
    assert len(seen) == (3 if retryable else 1)


async def test_nebius_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.providers.nebius.asyncio.sleep", _no_sleep)
    transport, seen = _transport([lambda _r: httpx.Response(429, json={}), _ok(_completion(content="hello"))])
    result = await _provider(transport).complete([{"role": "user", "content": "hi"}])
    assert result.content == "hello" and len(seen) == 2
    assert result.usage.total_tokens == 120


async def test_nebius_timeout_maps_to_model_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.providers.nebius.asyncio.sleep", _no_sleep)

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ProviderError) as info:
        await _provider(httpx.MockTransport(boom), retries=1).complete([{"role": "user", "content": "hi"}])
    assert info.value.code == "MODEL_TIMEOUT"


async def test_malformed_payload_is_bad_response() -> None:
    transport, _ = _transport([lambda _r: httpx.Response(200, json={"choices": []})])
    with pytest.raises(ProviderError) as info:
        await _provider(transport).complete([{"role": "user", "content": "hi"}])
    assert info.value.code == "BAD_RESPONSE"


async def test_provider_error_surfaces_as_error_event(scenario: Scenario) -> None:
    transport, _ = _transport([lambda _r: httpx.Response(401, json={})])
    events = await _collect(_ctx(scenario, _shocked(scenario)), _provider(transport))
    err = next(e for e in events if e.type == "error")
    assert err.data["code"] == "MODEL_UNAVAILABLE"
    assert next(e for e in events if e.type == "done").data["stop_reason"] == "provider_error"


# --- provider selection & HTTP stream --------------------------------------------


def test_live_mode_without_key_never_falls_back_to_mock() -> None:
    with pytest.raises(ProviderError):
        planner_provider(Settings(ai_mode="live", nebius_api_key=None))


def test_mock_mode_selects_labelled_mock() -> None:
    provider = planner_provider(Settings(ai_mode="mock"))
    assert provider.live is False and provider.name == "mock"


def test_recover_endpoint_streams_sse(scenario: Scenario) -> None:
    get_settings.cache_clear()
    client = TestClient(create_app())
    revision = _shocked(scenario)
    with client.stream(
        "POST", "/api/recover", json={"revision": revision.model_dump(mode="json"), "priorities": "cheap"}
    ) as res:
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/event-stream")
        body = "".join(res.iter_text())
    assert "event: run_started" in body and "event: done" in body
    assert "test-key" not in body


async def test_last_call_forces_submit_when_candidates_exist(scenario: Scenario) -> None:
    """The model keeps evaluating; on its final allowed call the runner forces submit_options."""
    evaluate = (
        "evaluate_patch",
        {"actions": [{"type": "activate_resource", "resource_id": "trolley-2"}], "rationale": "x"},
    )
    submit = (
        "submit_options",
        {"options": [{"candidate_id": "c1", "title": "Rent trolley", "why": "w"}], "summary": "s"},
    )

    def handler_factory():  # type: ignore[no-untyped-def]
        seen: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            seen.append(body)
            forced = isinstance(body.get("tool_choice"), dict)
            return httpx.Response(200, json=_completion([submit if forced else evaluate]))

        return handler, seen

    handler, seen = handler_factory()
    budget = Budget(max_model_calls=3, max_total_tokens=50_000, timeout_seconds=30, max_output_tokens=512)
    events = await _collect(_ctx(scenario, _shocked(scenario)), _provider(httpx.MockTransport(handler)), budget)
    assert seen[-1]["tool_choice"] == {"type": "function", "function": {"name": "submit_options"}}
    assert all(b["tool_choice"] == "auto" for b in seen[:-1])
    options = next(e for e in events if e.type == "options")
    assert options.data["finalized_by_model"] is True
    assert next(e for e in events if e.type == "done").data["stop_reason"] == "submitted"


def test_absorbed_incident_offers_verified_no_change_candidate(scenario: Scenario) -> None:
    ctx = _ctx(scenario, _shocked(scenario, "dock-delay-20"))
    assert "c0" in ctx.candidates
    assert ctx.candidates["c0"].evaluation.status.value == "verified"
    assert ctx.candidates["c0"].evaluation.patch.actions == ()
    assert execute_tool(ctx, "get_situation", "{}").content["no_change_candidate"] == "c0"
    first = execute_tool(
        ctx,
        "evaluate_patch",
        json.dumps({"actions": [{"type": "activate_resource", "resource_id": "trolley-2"}], "rationale": "x"}),
    )
    assert first.content["candidate_id"] == "c1"


def test_breaching_incident_has_no_change_candidate(scenario: Scenario) -> None:
    assert "c0" not in _ctx(scenario, _shocked(scenario)).candidates


async def test_no_change_option_is_always_offered_and_ranks_first_when_free(scenario: Scenario) -> None:
    """The model submits a change, but 'keep the current plan' (c0) is still offered and wins on penalty."""
    submit = (
        "submit_options",
        {"options": [{"candidate_id": "c1", "title": "Rent trolley", "why": "w"}], "summary": "s"},
    )
    evaluate = (
        "evaluate_patch",
        {"actions": [{"type": "activate_resource", "resource_id": "trolley-2"}], "rationale": "x"},
    )
    transport, _ = _transport([_ok(_completion([evaluate])), _ok(_completion([submit]))])
    events = await _collect(_ctx(scenario, _shocked(scenario, "dock-delay-20")), _provider(transport))
    options = next(e for e in events if e.type == "options").data["options"]
    assert {o["candidate_id"] for o in options} == {"c0", "c1"}
    assert options[0]["candidate_id"] == "c0" and options[0]["model_rank"] is None
