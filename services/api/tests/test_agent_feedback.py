"""Progress facts fed back to the model: preference coverage gaps and untried combinations.

Both are computed only from the model's own candidates (origin == "model"); no live model is called.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.agent.feedback import combinable_partials, coverage
from app.agent.runner import Budget, run_agent
from app.agent.tools import AgentContext, Candidate, execute_tool
from app.domain.effective import compile_problem
from app.domain.models import Scenario, Shock, TaskDelayShock
from app.domain.preferences import Preferences
from app.domain.revision import Revision, baseline_revision
from app.providers.nebius import NebiusProvider
from app.services.workflow import add_shock

GUEST = Preferences(guest_experience="protect", spend="flexible", source="structured")
BUDGET_PROFILE = Preferences(budget_cap_cents=5000, min_margin_minutes=10, source="structured")

TROLLEY = {"type": "activate_resource", "resource_id": "trolley-2"}
HELPER = {"type": "add_helper", "task_id": "stage-rigging", "resource_id": "event-lead"}
SOUNDCHECK_15 = {"type": "compress_task", "task_id": "soundcheck", "duration": 15}
SOUNDCHECK_20 = {"type": "compress_task", "task_id": "soundcheck", "duration": 20}
BACKUP_AV = {"type": "activate_resource", "resource_id": "backup-av"}


def _ctx(scenario: Scenario, shocks: list[Shock], prefs: Preferences | None = None) -> AgentContext:
    rev: Revision = baseline_revision(scenario)
    for s in shocks:
        rev = add_shock(rev, s).revision
    problem, _ = compile_problem(scenario, rev.state.shocks, rev.state.committed)
    assert problem is not None
    return AgentContext.build(scenario, rev, problem, 8, prefs)


def _truck(minutes: int) -> list[Shock]:
    return [TaskDelayShock(task_id="truck-arrival", delay_minutes=minutes)]


def _evaluate(ctx: AgentContext, *actions: dict[str, Any]) -> dict[str, Any]:
    out = execute_tool(ctx, "evaluate_patch", json.dumps({"actions": list(actions), "rationale": "test"}))
    assert out.ok
    return out.content


def _gap_ids(content: dict[str, Any]) -> list[str]:
    return [g["id"] for g in content["coverage_of_your_verified_options"]["not_yet_covered_by_your_options"]]


# --- coverage ------------------------------------------------------------------


def test_server_options_alone_never_produce_coverage(scenario: Scenario) -> None:
    """Playbook and no-change candidates are not the model's: no coverage fact is attributed to it."""
    for shocks in (_truck(35), [TaskDelayShock(task_id="dock-open", delay_minutes=20)]):
        ctx = _ctx(scenario, shocks, GUEST)
        assert any(c.origin != "model" for c in ctx.candidates.values())
        situation = execute_tool(ctx, "get_situation", "{}").content
        assert "coverage_of_your_verified_options" not in situation
        assert "combinable_partial_fixes" not in situation


def test_infeasible_proposals_alone_produce_no_coverage(scenario: Scenario) -> None:
    ctx = _ctx(scenario, _truck(35), GUEST)
    content = _evaluate(ctx, BACKUP_AV)
    assert content["status"] == "infeasible"
    assert "coverage_of_your_verified_options" not in content


def test_guest_priority_gap_is_reported_after_a_cut_only_option(scenario: Scenario) -> None:
    """c01 pattern: the model verifies a soundcheck cut under "protect guests" and would stop there."""
    ctx = _ctx(scenario, _truck(35), GUEST)
    cut = _evaluate(ctx, SOUNDCHECK_15)
    assert cut["status"] == "verified" and cut["service_impacts"]
    cov = cut["coverage_of_your_verified_options"]
    assert cov["your_verified_options"] == ["c1"]
    gaps = cov["not_yet_covered_by_your_options"]
    assert gaps[0]["id"] == "no_guest_impact" and gaps[0]["priority"] == "protect"
    # The only server option with no cut is the playbook trolley; it is named as such, never as the model's.
    assert all(cid.startswith("p") for cid in gaps[0]["already_met_by_server_options"])
    # spend is "flexible" in this profile, so zero cost is not a goal.
    assert "zero_cost" not in _gap_ids(cut)

    helper = _evaluate(ctx, HELPER)
    assert helper["status"] == "verified" and not helper["service_impacts"]
    assert helper["coverage_of_your_verified_options"]["your_verified_options"] == ["c1", "c2"]
    assert "no_guest_impact" not in _gap_ids(helper)
    # The same fact is visible if the model re-reads the situation.
    situation = execute_tool(ctx, "get_situation", "{}").content
    assert situation["coverage_of_your_verified_options"]["your_verified_options"] == ["c1", "c2"]


def test_joint_goal_appears_only_when_each_half_is_covered_separately(scenario: Scenario) -> None:
    ctx = _ctx(scenario, _truck(35), Preferences(source="structured"))
    paid = _evaluate(ctx, TROLLEY)
    assert paid["status"] == "verified" and paid["cost_eur"] > 0 and not paid["service_impacts"]
    assert _gap_ids(paid) == ["zero_cost"]
    free_cut = _evaluate(ctx, SOUNDCHECK_15)
    assert free_cut["status"] == "verified" and free_cut["cost_eur"] == 0 and free_cut["service_impacts"]
    assert _gap_ids(free_cut) == ["no_guest_impact_and_zero_cost"]
    both = _evaluate(ctx, HELPER)
    assert both["status"] == "verified" and both["cost_eur"] == 0 and not both["service_impacts"]
    assert _gap_ids(both) == []


def test_stated_limits_come_first(scenario: Scenario) -> None:
    ctx = _ctx(scenario, _truck(35), BUDGET_PROFILE)
    content = _evaluate(ctx, SOUNDCHECK_15)
    # Soundcheck cut leaves 0 min spare against the 10 min asked for: a stated-limit breach.
    assert content["status"] == "verified" and content["preference_check"]["breaches"]
    assert _gap_ids(content) == ["all_preferences", "no_guest_impact"]
    # Without stated limits there is no "all preferences" goal.
    plain = _evaluate(_ctx(scenario, _truck(35), GUEST), SOUNDCHECK_15)
    assert "all_preferences" not in _gap_ids(plain)


def test_coverage_ignores_non_verified_and_reports_nothing_without_model_options(scenario: Scenario) -> None:
    ctx = _ctx(scenario, _truck(35), GUEST)
    server = [(c.id, c.evaluation) for c in ctx.candidates.values()]
    assert coverage([], server, GUEST, ctx.do_nothing) is None
    _evaluate(ctx, BACKUP_AV)
    mine = [(c.id, c.evaluation) for c in ctx.candidates.values() if c.origin == "model"]
    assert coverage(mine, server, GUEST, ctx.do_nothing) is None


# --- combinations ----------------------------------------------------------------


def test_c09_near_misses_are_listed_as_combinable(scenario: Scenario) -> None:
    """Truck +65: each of the oracle's three changes alone gains minutes but fails; the fact names them."""
    ctx = _ctx(scenario, _truck(65))
    first = _evaluate(ctx, TROLLEY)
    assert first["status"] == "infeasible" and first["minutes_gained_vs_doing_nothing"] > 0
    assert "combinable_partial_fixes" not in first
    _evaluate(ctx, HELPER)
    third = _evaluate(ctx, SOUNDCHECK_20)
    assert third["status"] == "infeasible" and third["minutes_gained_vs_doing_nothing"] > 0
    groups = third["combinable_partial_fixes"]["groups"]
    assert groups[0]["candidate_ids"] == ["c1", "c2", "c3"]
    assert len(groups) <= 3
    ids = {cid for g in groups for cid in g["candidate_ids"]}
    assert ids <= {c.id for c in ctx.candidates.values() if c.origin == "model"}

    combined = _evaluate(ctx, TROLLEY, HELPER, SOUNDCHECK_20)
    assert combined["status"] == "verified"
    # A group already tried together is not suggested again.
    after = combined.get("combinable_partial_fixes", {"groups": []})["groups"]
    assert ["c1", "c2", "c3"] not in [g["candidate_ids"] for g in after]
    assert all(len(set(g["candidate_ids"]) & {"c1", "c2", "c3"}) < 3 for g in after)


def test_combinations_skip_same_task_zero_gain_and_verified(scenario: Scenario) -> None:
    ctx = _ctx(scenario, _truck(65))
    a = _evaluate(ctx, SOUNDCHECK_20)
    b = _evaluate(ctx, SOUNDCHECK_15)
    c = _evaluate(ctx, BACKUP_AV)
    assert a["minutes_gained_vs_doing_nothing"] > 0 and b["minutes_gained_vs_doing_nothing"] > 0
    assert c["minutes_gained_vs_doing_nothing"] == 0
    # Two cuts of the same task cannot be combined; the zero-gain proposal is never suggested.
    assert "combinable_partial_fixes" not in c
    mine = [(x.id, x.evaluation) for x in ctx.candidates.values() if x.origin == "model"]
    assert combinable_partials(mine, None) == []


def test_server_candidates_are_never_combined_or_credited(scenario: Scenario) -> None:
    """A non-model near-miss with the same data as the model's is never listed as the model's."""
    ctx = _ctx(scenario, _truck(65))
    _evaluate(ctx, TROLLEY)
    near_miss = ctx.candidates["c1"].evaluation
    ctx.candidates["p9"] = Candidate(id="p9", evaluation=near_miss, rationale="server", origin="playbook")
    _evaluate(ctx, HELPER)
    situation = execute_tool(ctx, "get_situation", "{}").content
    groups = situation["combinable_partial_fixes"]["groups"]
    assert [g["candidate_ids"] for g in groups] == [["c1", "c2"]]
    # And a verified server option never shows up as "your" verified option.
    ctx.candidates["p8"] = Candidate(
        id="p8", evaluation=_ctx(scenario, _truck(35)).candidates["p1"].evaluation, rationale="s", origin="playbook"
    )
    assert "coverage_of_your_verified_options" not in execute_tool(ctx, "get_situation", "{}").content


# --- loop with a fake Nebius transport -------------------------------------------


def _completion(name: str, arguments: dict[str, Any], n: int) -> dict[str, Any]:
    return {
        "id": f"cmpl-{n}",
        "model": "nvidia/test-model",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": f"call_{n}",
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(arguments)},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
    }


async def test_loop_feeds_combination_fact_back_and_model_uses_it(scenario: Scenario) -> None:
    """Scripted c09 run: the fourth request carries the fact; the combined patch verifies as the model's."""
    script: list[tuple[str, dict[str, Any]]] = [
        ("get_situation", {}),
        ("evaluate_patch", {"actions": [TROLLEY], "rationale": "parallel unload"}),
        ("evaluate_patch", {"actions": [HELPER], "rationale": "faster rigging"}),
        ("evaluate_patch", {"actions": [SOUNDCHECK_20], "rationale": "shorter soundcheck"}),
        ("evaluate_patch", {"actions": [TROLLEY, HELPER, SOUNDCHECK_20], "rationale": "combine c1+c2+c3"}),
        (
            "submit_options",
            {
                "options": [{"candidate_id": "c4", "title": "Trolley, helper, short soundcheck", "why": "w"}],
                "summary": "s",
            },
        ),
    ]
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        name, args = script[len(seen) - 1]
        return httpx.Response(200, json=_completion(name, args, len(seen)))

    provider = NebiusProvider(
        api_key="test-key",
        base_url="https://example.invalid/v1/",
        model="nvidia/test-model",
        transport=httpx.MockTransport(handler),
        max_retries=0,
    )
    budget = Budget(max_model_calls=8, max_total_tokens=50_000, timeout_seconds=30, max_output_tokens=512)
    ctx = _ctx(scenario, _truck(65))
    events = [ev async for ev in run_agent(ctx, provider, budget, "", mode_label="test")]

    assert events[0].data["prompt_version"] == "rr-agent-v6"
    last_tool = json.loads([m for m in seen[4]["messages"] if m.get("role") == "tool"][-1]["content"])
    assert last_tool["combinable_partial_fixes"]["groups"][0]["candidate_ids"] == ["c1", "c2", "c3"]
    options = next(e for e in events if e.type == "options").data["options"]
    by_id = {o["candidate_id"]: o for o in options}
    assert by_id["c4"]["origin"] == "model" and by_id["c4"]["model_rank"] == 1
    assert all(o["origin"] != "model" for o in options if o["candidate_id"] != "c4")
    assert next(e for e in events if e.type == "done").data["stop_reason"] == "submitted"
