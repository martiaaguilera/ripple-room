"""Unit tests for validator, propagation, solver semantics and patch checks."""

from __future__ import annotations

import random

import pytest
from pydantic import ValidationError

from app.domain.analysis import impact_report, intervention_cost_cents
from app.domain.effective import InvalidShockError, compile_problem
from app.domain.graph import CycleError, topological_order
from app.domain.models import (
    ActivateResource,
    AssignResource,
    CompressTask,
    DeferTask,
    Patch,
    PinStart,
    Plan,
    PlanEntry,
    ResourceUnavailableShock,
    Scenario,
    TaskDelayShock,
    Window,
)
from app.domain.reports import EvaluationStatus, TaskStatus
from app.domain.validate import validate_plan
from app.fixtures import preset
from app.solver.cpsat import SolveConfig, solve
from app.solver.evaluate import evaluate_patch


def _with_entry(plan: Plan, task_id: str, **changes: object) -> Plan:
    return Plan(entries=tuple(e.model_copy(update=changes) if e.task_id == task_id else e for e in plan.entries))


def _codes(scenario: Scenario, plan: Plan) -> set[str]:
    problem, _ = compile_problem(scenario)
    assert problem is not None
    return {v.code for v in validate_plan(problem, plan)}


# --- graph ------------------------------------------------------------------


def test_topological_order_rejects_cycles() -> None:
    with pytest.raises(CycleError):
        topological_order(["a", "b", "c"], [("a", "b"), ("b", "c"), ("c", "a")])


def test_scenario_with_cycle_is_rejected(scenario: Scenario) -> None:
    raw = scenario.model_dump(mode="json")
    raw["dependencies"].append({"from_id": "doors-open", "to_id": "truck-arrival"})
    with pytest.raises(ValidationError, match="cycle"):
        Scenario.model_validate(raw)


def test_hhmm_parsing(scenario: Scenario) -> None:
    assert scenario.task("truck-arrival").release == 14 * 60
    assert scenario.task("doors-open").deadline == 18 * 60


# --- validator ----------------------------------------------------------------


def test_validator_detects_precedence(scenario: Scenario) -> None:
    plan = _with_entry(scenario.baseline, "lighting-focus", start=14 * 60 + 45)
    assert "PRECEDENCE" in _codes(scenario, plan)


def test_validator_detects_resource_overlap(scenario: Scenario) -> None:
    plan = _with_entry(scenario.baseline, "vendor-tables", start=15 * 60)  # setup team is rigging
    assert "RESOURCE_OVERLAP" in _codes(scenario, plan)


def test_validator_detects_skill_mismatch(scenario: Scenario) -> None:
    plan = _with_entry(scenario.baseline, "audio-setup", assignments={"tech": "light-tech"})
    assert "SKILL_MISMATCH" in _codes(scenario, plan)


def test_validator_detects_inactive_standby_resource(scenario: Scenario) -> None:
    plan = _with_entry(scenario.baseline, "audio-setup", assignments={"tech": "backup-av"})
    assert "RESOURCE_INACTIVE" in _codes(scenario, plan)


def test_validator_detects_deadline_and_release(scenario: Scenario) -> None:
    plan = _with_entry(scenario.baseline, "doors-open", start=18 * 60 + 5)
    plan = _with_entry(plan, "scanner-setup", start=14 * 60)
    codes = _codes(scenario, plan)
    assert {"DEADLINE", "RELEASE"} <= codes


def test_validator_detects_missing_task(scenario: Scenario) -> None:
    plan = Plan(entries=tuple(e for e in scenario.baseline.entries if e.task_id != "soundcheck"))
    assert "MISSING_TASK" in _codes(scenario, plan)


def test_validator_detects_unavailability_window(scenario: Scenario) -> None:
    problem, _ = compile_problem(scenario, [preset("av-tech-out").shock])
    assert problem is not None
    codes = {v.code for v in validate_plan(problem, scenario.baseline)}
    assert codes == {"RESOURCE_UNAVAILABLE"}


def test_validator_rejects_deferred_task_in_plan(scenario: Scenario) -> None:
    problem, _ = compile_problem(scenario, (), Patch(actions=(DeferTask(task_id="vendor-tables"),)))
    assert problem is not None
    assert "UNEXPECTED_TASK" in {v.code for v in validate_plan(problem, scenario.baseline)}


# --- shocks & propagation -------------------------------------------------------


def test_unknown_shock_target_is_rejected(scenario: Scenario) -> None:
    with pytest.raises(InvalidShockError):
        compile_problem(scenario, [TaskDelayShock(task_id="no-such-task", delay_minutes=10)])


def test_shock_bounds_enforced() -> None:
    with pytest.raises(ValidationError):
        TaskDelayShock(task_id="truck-arrival", delay_minutes=0)
    with pytest.raises(ValidationError):
        TaskDelayShock(task_id="truck-arrival", delay_minutes=10_000)


def test_at_risk_is_distinct_from_delayed(scenario: Scenario) -> None:
    """A dock delay absorbed by the later truck: descendants are at risk, not delayed."""
    problem, _ = compile_problem(scenario, [TaskDelayShock(task_id="dock-open", delay_minutes=5)])
    assert problem is not None
    report = impact_report(problem, scenario.baseline)
    statuses = {t.task_id: t.status for t in report.tasks}
    assert statuses["dock-open"] == TaskStatus.DELAYED
    assert statuses["unload-truss"] == TaskStatus.AT_RISK
    assert statuses["doors-open"] == TaskStatus.AT_RISK
    assert report.metrics.delayed_count == 1


def test_resource_window_in_idle_time_has_no_impact(scenario: Scenario) -> None:
    shock = ResourceUnavailableShock(resource_id="light-tech", window=Window(start=13 * 60, end=14 * 60))
    problem, _ = compile_problem(scenario, [shock])
    assert problem is not None
    report = impact_report(problem, scenario.baseline)
    assert report.sources == []
    assert all(t.status == TaskStatus.ON_TRACK for t in report.tasks)


def test_resource_gone_for_the_day_blocks_tasks(scenario: Scenario) -> None:
    shock = ResourceUnavailableShock(resource_id="light-tech", window=Window(start=13 * 60, end=24 * 60))
    problem, _ = compile_problem(scenario, [shock])
    assert problem is not None
    report = impact_report(problem, scenario.baseline)
    statuses = {t.task_id: t.status for t in report.tasks}
    assert statuses["lighting-focus"] == TaskStatus.BLOCKED
    assert statuses["doors-open"] == TaskStatus.BLOCKED


def test_causal_waves_follow_graph_order(scenario: Scenario) -> None:
    problem, _ = compile_problem(scenario, [preset("truck-delay-35").shock])
    assert problem is not None
    report = impact_report(problem, scenario.baseline)
    wave = {t.task_id: t.wave for t in report.tasks}
    for edge in report.causal_edges:
        assert wave[edge.to_id] == edge.wave
        assert wave[edge.from_id] is not None and wave[edge.from_id] == edge.wave - 1


# --- patches ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("action", "code"),
    [
        (ActivateResource(resource_id="av-tech"), "NOT_STANDBY"),
        (ActivateResource(resource_id="ghost"), "UNKNOWN_RESOURCE"),
        (CompressTask(task_id="stage-rigging", duration=30), "NOT_COMPRESSIBLE"),
        (CompressTask(task_id="soundcheck", duration=5), "DURATION_OUT_OF_RANGE"),
        (DeferTask(task_id="soundcheck"), "NOT_OPTIONAL"),
        (DeferTask(task_id="unload-vendor"), "DEFER_BREAKS_DEPENDENCY"),
        (AssignResource(task_id="audio-setup", requirement_id="tech", resource_id="light-tech"), "SKILL_MISMATCH"),
        (AssignResource(task_id="audio-setup", requirement_id="tech", resource_id="backup-av"), "RESOURCE_INACTIVE"),
        (AssignResource(task_id="audio-setup", requirement_id="nope", resource_id="av-tech"), "UNKNOWN_REQUIREMENT"),
        (PinStart(task_id="ghost-task", start=900), "UNKNOWN_TASK"),
    ],
)
def test_invalid_patches_are_rejected_before_solving(scenario: Scenario, action: object, code: str) -> None:
    patch = Patch(actions=(action,))  # type: ignore[arg-type]
    ev = evaluate_patch(scenario, [preset("truck-delay-35").shock], Patch(), patch, scenario.baseline)
    assert ev.status == EvaluationStatus.REJECTED
    assert code in {v.code for v in ev.violations}
    assert ev.solver.status == "NOT_RUN"


def test_duplicate_actions_rejected(scenario: Scenario) -> None:
    a = ActivateResource(resource_id="trolley-2")
    ev = evaluate_patch(scenario, [], Patch(), Patch(actions=(a, a)), scenario.baseline)
    assert ev.status == EvaluationStatus.REJECTED


def test_patch_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Patch.model_validate({"actions": [{"type": "activate_resource", "resource_id": "trolley-2", "sql": "drop"}]})
    with pytest.raises(ValidationError):
        Patch.model_validate({"actions": [{"type": "run_shell", "cmd": "rm -rf /"}]})


def test_pins_and_assignments_are_honoured(scenario: Scenario) -> None:
    shock = preset("av-tech-out").shock
    patch = Patch(
        actions=(
            ActivateResource(resource_id="backup-av"),
            AssignResource(task_id="soundcheck", requirement_id="tech", resource_id="backup-av"),
        )
    )
    ev = evaluate_patch(scenario, [shock], Patch(), patch, scenario.baseline)
    assert ev.status == EvaluationStatus.VERIFIED and ev.plan is not None
    assert ev.plan.by_task()["soundcheck"].assignments["tech"] == "backup-av"


def test_pin_before_release_is_infeasible(scenario: Scenario) -> None:
    patch = Patch(actions=(PinStart(task_id="scanner-setup", start=14 * 60),))
    ev = evaluate_patch(scenario, [], Patch(), patch, scenario.baseline)
    assert ev.status == EvaluationStatus.INFEASIBLE


def test_cost_is_fee_plus_hourly_for_minutes_worked(scenario: Scenario) -> None:
    patch = Patch(actions=(ActivateResource(resource_id="backup-av"),))
    ev = evaluate_patch(scenario, [preset("av-tech-out").shock], Patch(), patch, scenario.baseline)
    assert ev.plan is not None
    problem, _ = compile_problem(scenario, [preset("av-tech-out").shock], patch)
    assert problem is not None
    minutes = sum(problem.tasks[e.task_id].duration for e in ev.plan.entries if "backup-av" in e.assignments.values())
    assert minutes > 0
    assert ev.cost_cents == 9000 + round(4500 * minutes / 60)
    assert intervention_cost_cents(problem, ev.plan) == ev.cost_cents


# --- solver -------------------------------------------------------------------------


def test_solver_is_deterministic(scenario: Scenario) -> None:
    shock = preset("av-tech-out").shock
    patch = Patch(actions=(CompressTask(task_id="soundcheck", duration=15),))
    a = evaluate_patch(scenario, [shock], Patch(), patch, scenario.baseline)
    b = evaluate_patch(scenario, [shock], Patch(), patch, scenario.baseline)
    assert a.plan == b.plan
    assert a.solver.objective == b.solver.objective
    assert a.changes == b.changes


def test_solver_timeout_is_unknown_never_feasible(scenario: Scenario) -> None:
    """A feasible problem cut off before any solution must surface as UNKNOWN, not green."""
    tiny = SolveConfig(max_time_seconds=1e-6, max_deterministic_time=1e-9)
    problem, _ = compile_problem(scenario, [preset("dock-delay-20").shock])
    assert problem is not None
    result = solve(problem, scenario.baseline, config=tiny)
    assert result.status == "UNKNOWN"
    assert result.plan is None
    ev = evaluate_patch(scenario, [preset("dock-delay-20").shock], Patch(), Patch(), scenario.baseline, config=tiny)
    assert ev.status == EvaluationStatus.UNKNOWN
    assert ev.plan is None


def test_baseline_unchanged_when_no_shock(scenario: Scenario) -> None:
    ev = evaluate_patch(scenario, [], Patch(), Patch(), scenario.baseline)
    assert ev.status == EvaluationStatus.VERIFIED
    assert ev.disruption_minutes == 0
    assert ev.changes == []


def test_random_patches_never_yield_invalid_verified_plans(scenario: Scenario) -> None:
    """Fuzz: any verified plan must pass the independent validator (checked inside evaluate)."""
    rng = random.Random(1234)
    pool = [
        ActivateResource(resource_id="trolley-2"),
        ActivateResource(resource_id="backup-av"),
        CompressTask(task_id="soundcheck", duration=20),
        CompressTask(task_id="crew-briefing", duration=10),
        DeferTask(task_id="vendor-tables"),
        PinStart(task_id="unload-av", start=14 * 60),
        PinStart(task_id="vendor-tables", start=16 * 60 + 30),
        AssignResource(task_id="unload-truss", requirement_id="crew", resource_id="setup-team"),
    ]
    shocks = [preset(p).shock for p in ("truck-delay-35", "av-tech-out", "dock-delay-20")]
    for _ in range(30):
        actions = rng.sample(pool, rng.randint(0, 4))
        shock = rng.choice(shocks)
        ev = evaluate_patch(scenario, [shock], Patch(), Patch(actions=tuple(actions)), scenario.baseline)
        assert ev.status in set(EvaluationStatus)
        if ev.status == EvaluationStatus.VERIFIED:
            assert ev.plan is not None and ev.schedule is not None
            assert ev.schedule.deadline_delta is not None and ev.schedule.deadline_delta <= 0


def test_plan_entry_round_trip() -> None:
    entry = PlanEntry.model_validate({"task_id": "x", "start": "14:05"})
    assert entry.start == 14 * 60 + 5
