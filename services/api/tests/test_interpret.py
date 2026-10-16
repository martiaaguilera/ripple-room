"""Natural-language incident interpretation: model output is untrusted and validated."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.agent.interpret import interpret
from app.agent.runner import Budget, run_agent
from app.agent.tools import AgentContext
from app.domain.effective import compile_problem
from app.domain.models import ResourceUnavailableShock, Scenario, TaskDelayShock
from app.domain.preferences import Preferences
from app.domain.revision import baseline_revision
from app.fixtures import preset
from app.main import create_app
from app.providers.base import ProviderError
from app.providers.mock import MockProvider
from app.providers.nebius import NebiusProvider
from app.services.workflow import add_shock


def _provider(arguments: dict[str, Any] | None, seen: list[dict[str, Any]]) -> NebiusProvider:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        message: dict[str, Any] = {"role": "assistant", "content": ""}
        if arguments is not None:
            message["tool_calls"] = [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "report_situation", "arguments": json.dumps(arguments)},
                }
            ]
        body = {
            "model": "nvidia/test",
            "choices": [{"message": message, "finish_reason": "tool_calls"}],
            "usage": {"total_tokens": 50},
        }
        return httpx.Response(200, json=body)

    return NebiusProvider(
        api_key="k", base_url="https://x.invalid/v1", model="nvidia/test", transport=httpx.MockTransport(handler)
    )


async def test_valid_incidents_and_priorities_become_typed(scenario: Scenario) -> None:
    seen: list[dict[str, Any]] = []
    args = {
        "incidents": [
            {
                "kind": "task_delay",
                "task_id": "truck-arrival",
                "delay_minutes": 40,
                "evidence": "driver says 40 more minutes",
            },
            {
                "kind": "resource_unavailable",
                "resource_id": "av-tech",
                "start": "15:30",
                "end": "16:15",
                "evidence": "AV leaves",
            },
        ],
        "priorities": {"spend": "protect", "budget_cap_eur": 50, "protected_tasks": ["vendor-tables"]},
        "unclear": [],
        "summary": "Truck 40 min late; AV tech away mid-afternoon.",
    }
    result = await interpret(
        scenario, "Driver says 40 more minutes. AV leaves 15:30-16:15. No extra spend, max €50.", _provider(args, seen)
    )
    assert [type(i.shock) for i in result.incidents] == [TaskDelayShock, ResourceUnavailableShock]
    assert result.incidents[0].shock == TaskDelayShock(task_id="truck-arrival", delay_minutes=40)
    assert "14:40" in result.incidents[0].restatement
    assert result.preferences.spend == "protect"
    assert result.preferences.budget_cap_cents == 5000
    assert result.preferences.protected_tasks == ("vendor-tables",)
    assert result.preferences.source == "model"
    assert result.live is True and result.rejected == []
    assert seen[0]["tool_choice"] == {"type": "function", "function": {"name": "report_situation"}}


@pytest.mark.parametrize(
    ("incident", "reason"),
    [
        ({"kind": "task_delay", "task_id": "helicopter", "delay_minutes": 10, "evidence": "x"}, "Unknown task"),
        ({"kind": "task_delay", "task_id": "truck-arrival", "evidence": "late"}, "No delay length"),
        ({"kind": "task_delay", "task_id": "truck-arrival", "delay_minutes": 9999, "evidence": "x"}, "Out of bounds"),
        ({"kind": "resource_unavailable", "resource_id": "av-tech", "start": "soon", "evidence": "x"}, "window"),
        (
            {
                "kind": "resource_unavailable",
                "resource_id": "backup-av",
                "start": "15:00",
                "end": "16:00",
                "evidence": "x",
            },
            "Unknown resource",
        ),
        ({"kind": "teleport", "evidence": "x"}, "Malformed"),
        (
            {"kind": "task_delay", "task_id": "truck-arrival", "delay_minutes": 5, "evidence": "x", "sql": "drop"},
            "Malformed",
        ),
    ],
)
async def test_invalid_incidents_are_rejected_with_reasons(
    scenario: Scenario, incident: dict[str, Any], reason: str
) -> None:
    args = {"incidents": [incident], "priorities": {}, "unclear": [], "summary": ""}
    result = await interpret(scenario, "something happened", _provider(args, []))
    assert result.incidents == []
    assert len(result.rejected) == 1 and reason in result.rejected[0].reason


async def test_bad_priorities_fall_back_to_defaults(scenario: Scenario) -> None:
    args = {"incidents": [], "priorities": {"spend": "extreme", "ignore_deadline": True}, "unclear": [], "summary": ""}
    result = await interpret(scenario, "truck late", _provider(args, []))
    assert result.preferences.spend == "balanced"
    assert any("Priorities ignored" in u for u in result.unclear)


async def test_missing_tool_call_is_a_bad_response(scenario: Scenario) -> None:
    with pytest.raises(ProviderError) as info:
        await interpret(scenario, "truck late", _provider(None, []))
    assert info.value.code == "BAD_RESPONSE"


async def test_mock_interpreter_is_labelled(scenario: Scenario) -> None:
    result = await interpret(
        scenario, "Truck stuck in traffic, 45 minutes. Protect the guest experience.", MockProvider()
    )
    assert result.live is False and result.preferences.source == "mock"
    assert result.incidents[0].shock == TaskDelayShock(task_id="truck-arrival", delay_minutes=45)
    assert result.preferences.guest_experience == "protect"


def test_interpret_endpoint_applies_nothing(scenario: Scenario) -> None:
    client = TestClient(create_app())
    rev = baseline_revision(scenario)
    res = client.post(
        "/api/interpret", json={"revision": rev.model_dump(mode="json"), "text": "The truck is 35 minutes late."}
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["incidents"][0]["shock"] == {"kind": "task_delay", "task_id": "truck-arrival", "delay_minutes": 35}
    assert "revision" not in body  # interpretation never creates a revision


async def test_agent_ranks_by_confirmed_preferences(scenario: Scenario) -> None:
    revision = add_shock(baseline_revision(scenario), preset("truck-delay-35").shock).revision
    problem, _ = compile_problem(scenario, revision.state.shocks, revision.state.committed)
    assert problem is not None
    budget = Budget(max_model_calls=10, max_total_tokens=10_000, timeout_seconds=30, max_output_tokens=512)

    async def top(prefs: Preferences) -> dict[str, Any]:
        ctx = AgentContext.build(scenario, revision, problem, 6, prefs)
        events = [e async for e in run_agent(ctx, MockProvider(max_evaluations=6), budget, "", mode_label="mock")]
        options = next(e for e in events if e.type == "options").data["options"]
        assert [o["rank"] for o in options] == list(range(1, len(options) + 1))
        return options[0]

    guest_first = await top(Preferences(guest_experience="protect", spend="flexible"))
    assert guest_first["evaluation"]["service_impacts"] == []
    money_first = await top(Preferences(spend="protect", guest_experience="flexible"))
    assert money_first["evaluation"]["cost_cents"] == 0
    assert money_first["model_rank"] is not None
