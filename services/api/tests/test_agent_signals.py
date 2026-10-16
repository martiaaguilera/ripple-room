"""Facts the agent receives (idle people, partial progress) and reproductions of benchmark cases c19, c09."""

from __future__ import annotations

import json

from app.agent.tools import AgentContext, execute_tool, idle_people
from app.domain.effective import compile_problem
from app.domain.models import (
    ActivateResource,
    AddHelper,
    CompressTask,
    Patch,
    ResourceUnavailableShock,
    Scenario,
    Shock,
    TaskDelayShock,
    Window,
)
from app.domain.reports import EvaluationStatus
from app.domain.revision import Revision, baseline_revision
from app.services.workflow import add_shock
from app.solver.evaluate import evaluate_patch
from app.solver.greedy import greedy_recovery
from app.solver.search import extended_menu, search_recoveries

C19 = [ResourceUnavailableShock(resource_id="setup-team", window=Window(start=14 * 60 + 30, end=15 * 60 + 30))]
C09 = [TaskDelayShock(task_id="truck-arrival", delay_minutes=65)]


def _ctx(scenario: Scenario, shocks: list[Shock]) -> AgentContext:
    rev: Revision = baseline_revision(scenario)
    for s in shocks:
        rev = add_shock(rev, s).revision
    problem, _ = compile_problem(scenario, rev.state.shocks, rev.state.committed)
    assert problem is not None
    return AgentContext.build(scenario, rev, problem, 6)


def test_idle_event_lead_is_shown_as_possible_rigging_helper(scenario: Scenario) -> None:
    ctx = _ctx(scenario, [TaskDelayShock(task_id="truck-arrival", delay_minutes=35)])
    lead = next(p for p in idle_people(ctx) if p["person"] == "event-lead")
    assert any(h["task"] == "stage-rigging" and h["as"].startswith("helper") for h in lead["could_help_on_chain"])
    situation = execute_tool(ctx, "get_situation", "{}").content
    assert situation["idle_people_during_critical_chain"]
    assert all(o["candidate_id"].startswith("p") for o in situation["verified_playbook_options"])


def test_partial_progress_is_reported_for_near_misses(scenario: Scenario) -> None:
    ctx = _ctx(scenario, [TaskDelayShock(task_id="truck-arrival", delay_minutes=35)])
    useless = execute_tool(
        ctx,
        "evaluate_patch",
        json.dumps({"actions": [{"type": "activate_resource", "resource_id": "backup-av"}], "rationale": "x"}),
    )
    helps = execute_tool(
        ctx,
        "evaluate_patch",
        json.dumps(
            {"actions": [{"type": "compress_task", "task_id": "crew-briefing", "duration": 10}], "rationale": "x"}
        ),
    )
    assert useless.content["minutes_gained_vs_doing_nothing"] == 0
    assert helps.content["minutes_gained_vs_doing_nothing"] == 5


def test_c19_recovery_exists_only_beyond_the_playbook(scenario: Scenario) -> None:
    """Setup team away 14:30-15:30: the playbook and greedy find nothing; a helper + line check works."""
    base = baseline_revision(scenario)
    assert search_recoveries(scenario, C19, Patch(), base.state.plan).verified == []
    assert greedy_recovery(scenario, C19, Patch(), base.state.plan).evaluation is None
    patch = Patch(
        actions=(
            AddHelper(task_id="stage-rigging", resource_id="event-lead"),
            CompressTask(task_id="soundcheck", duration=15),
        )
    )
    ev = evaluate_patch(scenario, C19, Patch(), patch, base.state.plan)
    assert ev.status == EvaluationStatus.VERIFIED and ev.cost_cents == 0
    lead = next(p for p in idle_people(_ctx(scenario, C19)) if p["person"] == "event-lead")
    assert any(h["task"] == "stage-rigging" for h in lead["could_help_on_chain"])


def test_c09_needs_three_simultaneous_changes(scenario: Scenario) -> None:
    """Truck +65: no single or double change from the extended space works; the oracle's triple does."""
    base = baseline_revision(scenario)
    triple = (
        ActivateResource(resource_id="trolley-2"),
        AddHelper(task_id="stage-rigging", resource_id="event-lead"),
        CompressTask(task_id="soundcheck", duration=20),
    )
    assert (
        evaluate_patch(scenario, C09, Patch(), Patch(actions=triple), base.state.plan).status
        == EvaluationStatus.VERIFIED
    )
    doubles = search_recoveries(scenario, C09, Patch(), base.state.plan, max_size=2, menu=extended_menu(scenario))
    assert doubles.verified == []
    for action in triple:
        assert (
            evaluate_patch(scenario, C09, Patch(), Patch(actions=(action,)), base.state.plan).status
            == EvaluationStatus.INFEASIBLE
        )


def test_reschedule_only_option_is_offered_when_doing_nothing_fails(scenario: Scenario) -> None:
    """c20: transport crew away 14:00-15:00. Doing nothing is late, but resequencing alone works."""
    shocks: list[Shock] = [
        ResourceUnavailableShock(resource_id="transport-crew", window=Window(start=14 * 60, end=15 * 60))
    ]
    ctx = _ctx(scenario, shocks)
    assert ctx.impact.schedule.deadline_delta is not None and ctx.impact.schedule.deadline_delta > 0
    empty = [c for c in ctx.candidates.values() if c.origin == "playbook" and not c.evaluation.patch.actions]
    assert len(empty) == 1 and empty[0].rationale.startswith("Reschedule only")
    assert "c0" not in ctx.candidates
