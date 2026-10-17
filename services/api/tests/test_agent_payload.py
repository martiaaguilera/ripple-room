"""Compact tool payloads keep every decision-relevant fact (offline; no model is called).

The situation, menu and evaluation results were shrunk to cut prompt tokens per run. These tests pin
the facts the system prompt relies on, across all 20 benchmark cases, plus a size guard so the
payload does not silently grow back.
"""

from __future__ import annotations

import json
import statistics
from typing import Any

import pytest

from app.agent.prompts import SYSTEM_PROMPT, user_prompt
from app.agent.runner import Budget, run_agent
from app.agent.tools import AgentContext, execute_tool, idle_people, preferences_view, tool_content_json
from app.domain.analysis import fmt_clock
from app.domain.effective import compile_problem
from app.domain.models import Patch, Scenario
from app.domain.ranking import touched_tasks
from app.domain.reports import Evaluation
from app.domain.revision import baseline_revision
from app.domain.validate import validate_plan
from app.evaluation.cases import CASES, Case
from app.evaluation.payload import build_context, measure_all, report, run_estimate_chars
from app.fixtures import SHOCK_PRESETS
from app.providers.mock import MockProvider
from app.services.workflow import add_shock

# Measured with app.evaluation.payload before the compaction (prompt rr-agent-v6).
BASELINE_SITUATION_CHARS = 6818
BASELINE_RUN_CHARS = 96604


def _situation(ctx: AgentContext) -> dict[str, Any]:
    out = execute_tool(ctx, "get_situation", "{}")
    assert out.ok
    return out.content


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_situation_keeps_every_decision_fact(scenario: Scenario, case: Case) -> None:
    ctx = build_context(scenario, case)
    s = _situation(ctx)
    sched = ctx.impact.schedule
    timings = {t.task_id: t for t in ctx.impact.timings}

    assert s["deadline"] == fmt_clock(sched.deadline)
    assert s["minutes_late"] == sched.deadline_delta
    assert ("no_change_candidate" in s) == ("c0" in ctx.candidates)
    # Driving path: every chain task, in order, with its start time and why it cannot start earlier.
    chain = [tid for tid in sched.driving_path if tid in timings]
    assert len(s["driving_path"]) == len(chain)
    for line, tid in zip(s["driving_path"], chain, strict=True):
        assert line == f"{tid} {fmt_clock(timings[tid].start)}: {timings[tid].binding.text}"

    rows = {r["id"]: r for r in s["tasks"]}
    assert list(rows) == [t.id for t in scenario.tasks if t.id in ctx.problem.tasks]
    # Dependencies are carried on the successor ("after") and none is lost or invented.
    edges = {(d.from_id, d.to_id) for d in ctx.problem.dependencies}
    assert {(p, tid) for tid, r in rows.items() for p in r.get("after", [])} == edges
    for task in scenario.tasks:
        if task.id not in rows:
            continue
        row = rows[task.id]
        assert row.get("label", task.id.replace("-", " ")).lower() == task.label.lower()
        assert row["duration"] == ctx.problem.tasks[task.id].duration
        assert row.get("needs", []) == [r.skill for r in task.requirements]
        if task.id in timings:
            t = timings[task.id]
            assert row["time"].startswith(fmt_clock(t.start)) and row["time"].endswith(fmt_clock(t.end))
            assert row.get("assigned", {}) == t.assignments
        assert row.get("can_shorten_to") == task.min_duration
        if task.helper is not None:
            assert row["helper"]["shortens_to"] == task.helper.duration
            assert row["helper"]["qualified"] == [r.id for r in scenario.resources if task.helper.skill in r.skills]
        assert row.get("optional", False) == task.optional
    statuses = {t.task_id: t.status.value for t in ctx.impact.tasks}
    assert {tid: r.get("status", "on_track") for tid, r in rows.items()} == {
        tid: statuses.get(tid, "on_track") for tid in rows
    }

    res = {r["id"]: r for r in s["resources"]}
    assert list(res) == [r.id for r in scenario.resources]
    for r in scenario.resources:
        blocked = ctx.problem.resources[r.id].blocked if r.id in ctx.problem.resources else ()
        assert len(res[r.id].get("blocked", [])) == len(blocked)
        assert res[r.id].get("standby", False) == (r.standby and r.id not in ctx.problem.activated)
        assert res[r.id]["skills"] == list(r.skills)

    assert s["idle_people_during_critical_chain"] == idle_people(ctx)
    playbook = [c for c in ctx.candidates.values() if c.origin == "playbook"]
    views = s["verified_playbook_options"]
    assert [v["candidate_id"] for v in views] == [c.id for c in playbook]
    for view, cand in zip(views, playbook, strict=True):
        ev = cand.evaluation
        assert view["what"] == cand.rationale
        assert view["cost_eur"] == ev.cost_cents / 100
        assert view["service_impacts"] == [x.text for x in ev.service_impacts]
        assert ev.schedule is not None and view["minutes_before_deadline"] == -(ev.schedule.deadline_delta or 0)
        assert view["tasks_changed_vs_doing_nothing"] == len(touched_tasks(ev, ctx.do_nothing))
        assert {"doors_ready", "reassignments", "disruption_minutes"} <= view.keys()

    # Preferences are sent once, in the user message, not repeated in every situation.
    assert "coordinator_preferences" not in s
    assert json.dumps(preferences_view(ctx.preferences), separators=(",", ":"), ensure_ascii=False) in user_prompt(
        case.profile.text, preferences_view(ctx.preferences)
    )


@pytest.mark.parametrize("case", CASES[:3] + CASES[8:9], ids=lambda c: c.id)
def test_payloads_are_valid_stable_json(scenario: Scenario, case: Case) -> None:
    for name in ("get_situation", "list_interventions"):
        a = tool_content_json(execute_tool(build_context(scenario, case), name, "{}").content)
        b = tool_content_json(execute_tool(build_context(scenario, case), name, "{}").content)
        assert a == b, f"{name} is not deterministic"
        assert tool_content_json(json.loads(a)) == a
        assert "\\u" not in a  # UTF-8 text, not 6-character escapes


def test_menu_keeps_actions_costs_and_rules(scenario: Scenario) -> None:
    ctx = build_context(scenario, CASES[0])
    menu = execute_tool(ctx, "list_interventions", "{}").content
    assert len(menu["menu"]) == len(ctx.menu)
    for item, m in zip(menu["menu"], ctx.menu, strict=True):
        assert item == {
            "label": m.label,
            "actions": [a.model_dump() for a in m.actions],
            "cost": m.cost_hint,
            "tradeoff": m.tradeoff,
        }
    rules = " ".join(menu["free_form_rules"])
    for action in ("assign_resource", "pin_start", "add_helper", "compress_task"):
        assert action in rules
    assert menu["evaluations_remaining"] == ctx.max_evaluations


def test_evaluation_result_keeps_decision_facts_and_notes_live_in_the_prompt(scenario: Scenario) -> None:
    c09 = next(c for c in CASES if c.id == "c09")
    ctx = build_context(scenario, c09)
    trolley = {"type": "activate_resource", "resource_id": "trolley-2"}
    helper = {"type": "add_helper", "task_id": "stage-rigging", "resource_id": "event-lead"}
    cut = {"type": "compress_task", "task_id": "soundcheck", "duration": 20}
    results = [
        execute_tool(ctx, "evaluate_patch", json.dumps({"actions": acts, "rationale": "x"})).content
        for acts in ([trolley], [helper], [cut], [trolley, helper, cut])
    ]
    near_miss, combined = results[2], results[3]
    assert near_miss["status"] == "infeasible" and near_miss["minutes_gained_vs_doing_nothing"] > 0
    assert near_miss["why_infeasible"] and "best_possible_readiness_with_this_patch" in near_miss
    # Groups only: the explanation is stated once in the system prompt.
    assert set(near_miss["combinable_partial_fixes"]) == {"groups"}
    assert near_miss["combinable_partial_fixes"]["groups"][0]["candidate_ids"] == ["c1", "c2", "c3"]
    assert combined["status"] == "verified"
    assert {"breaches", "penalty_points", "tasks_changed_vs_doing_nothing"} == combined["preference_check"].keys()
    assert {"doors_ready", "minutes_before_deadline", "cost_eur", "service_impacts", "reassignments"} <= combined.keys()
    cov = combined["coverage_of_your_verified_options"]
    assert set(cov) == {"your_verified_options", "not_yet_covered_by_your_options"}
    # The two notes removed from every result are stated once in the system prompt instead.
    assert "gains are not additive" in SYSTEM_PROMPT
    assert "whether such an option exists is" in SYSTEM_PROMPT


def test_payload_size_does_not_grow_back(scenario: Scenario) -> None:
    payloads = measure_all(scenario)
    assert len(payloads) == len(CASES)
    situation = statistics.mean(p.chars["situation"] for p in payloads)
    run = statistics.mean(run_estimate_chars(p) for p in payloads)
    # Guards with a little headroom over the measured compact sizes (4960 / 84733 chars).
    assert situation <= 0.78 * BASELINE_SITUATION_CHARS
    assert run <= 0.90 * BASELINE_RUN_CHARS
    table = report(payloads)
    for component in ("system", "user", "tools", "situation", "menu", "evaluate", "run estimate"):
        assert component in table


def _revalidates(scenario: Scenario, shocks: Any, ev: Evaluation) -> bool:
    problem, _ = compile_problem(scenario, shocks, Patch(actions=ev.patch.actions))
    return problem is not None and ev.plan is not None and not validate_plan(problem, ev.plan)


@pytest.mark.parametrize("preset", SHOCK_PRESETS, ids=[p.id for p in SHOCK_PRESETS])
async def test_mock_loop_completes_on_compact_payloads(scenario: Scenario, preset: Any) -> None:
    revision = add_shock(baseline_revision(scenario), preset.shock).revision
    problem, _ = compile_problem(scenario, revision.state.shocks, revision.state.committed)
    assert problem is not None
    ctx = AgentContext.build(scenario, revision, problem, 6)
    # The scripted walker needs 2 reads + up to 6 evaluations + 1 submit.
    budget = Budget(max_model_calls=10, max_total_tokens=50_000, timeout_seconds=30, max_output_tokens=512)
    events = [ev async for ev in run_agent(ctx, MockProvider(max_evaluations=6), budget, "", mode_label="test")]
    done = next(e for e in events if e.type == "done").data
    assert done["stop_reason"] == "submitted"
    options = next(e for e in events if e.type == "options").data
    assert options["finalized_by_model"] is True
    if preset.id == "truck-breakdown-90":
        assert options["options"] == []  # provably infeasible: nothing is ever shown as a recovery
        return
    assert options["options"], preset.id
    for o in options["options"]:
        ev = Evaluation.model_validate(o["evaluation"])
        assert ev.status.value == "verified" and _revalidates(scenario, revision.state.shocks, ev)
        assert (o["origin"] == "model") == (ctx.candidates[o["candidate_id"]].origin == "model")
