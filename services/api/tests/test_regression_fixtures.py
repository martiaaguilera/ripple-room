"""The three mandatory regression fixtures: baseline, truck-delay-35, impossible-case.

These pin *properties* the demo story relies on, so that fixture tuning can never
silently turn the flagship incident into a non-event or a fake rescue.
"""

from __future__ import annotations

from app.domain.analysis import impact_report, schedule_timings
from app.domain.effective import compile_problem
from app.domain.models import ActivateResource, CompressTask, DeferTask, Patch, Scenario
from app.domain.reports import EvaluationStatus, TaskStatus
from app.domain.validate import validate_plan
from app.fixtures import preset
from app.solver.evaluate import evaluate_patch
from app.solver.search import search_recoveries

DOORS = 18 * 60


def test_baseline_has_zero_hard_violations(scenario: Scenario) -> None:
    problem, static = compile_problem(scenario)
    assert problem is not None and not static
    assert validate_plan(problem, scenario.baseline) == []


def test_baseline_meets_doors_with_slack(scenario: Scenario) -> None:
    problem, _ = compile_problem(scenario)
    assert problem is not None
    _, metrics = schedule_timings(problem, scenario.baseline)
    assert metrics.readiness is not None
    assert metrics.deadline_delta is not None and metrics.deadline_delta < 0
    assert metrics.driving_path[-1] == "doors-open"


def test_truck_delay_creates_nontrivial_breach(scenario: Scenario) -> None:
    problem, _ = compile_problem(scenario, [preset("truck-delay-35").shock])
    assert problem is not None
    report = impact_report(problem, scenario.baseline)
    doors = next(t for t in report.tasks if t.task_id == "doors-open")
    assert doors.status == TaskStatus.BREACH
    assert report.schedule.deadline_delta is not None and report.schedule.deadline_delta > 0
    assert report.metrics.delayed_count >= 5
    assert report.sources == ["truck-arrival"]
    # Tasks that do not depend on the truck stay untouched.
    untouched = {t.task_id for t in report.tasks if t.status == TaskStatus.ON_TRACK}
    assert {"dock-open", "scanner-setup"} <= untouched


def test_truck_delay_needs_an_intervention(scenario: Scenario) -> None:
    ev = evaluate_patch(scenario, [preset("truck-delay-35").shock], Patch(), Patch(), scenario.baseline)
    assert ev.status == EvaluationStatus.INFEASIBLE
    assert ev.infeasibility is not None and ev.infeasibility.best_delta is not None
    assert ev.infeasibility.best_delta > 0


def test_truck_delay_has_a_verified_recovery(scenario: Scenario) -> None:
    patch = Patch(actions=(ActivateResource(resource_id="trolley-2"),))
    ev = evaluate_patch(scenario, [preset("truck-delay-35").shock], Patch(), patch, scenario.baseline)
    assert ev.status == EvaluationStatus.VERIFIED
    assert ev.schedule is not None and ev.schedule.readiness is not None
    assert ev.schedule.readiness <= DOORS
    assert ev.cost_cents == 3500
    assert ev.service_impacts == []


def test_truck_delay_line_check_is_a_zero_cost_alternative(scenario: Scenario) -> None:
    patch = Patch(actions=(CompressTask(task_id="soundcheck", duration=15),))
    ev = evaluate_patch(scenario, [preset("truck-delay-35").shock], Patch(), patch, scenario.baseline)
    assert ev.status == EvaluationStatus.VERIFIED
    assert ev.cost_cents == 0
    assert [s.kind for s in ev.service_impacts] == ["compress"]


def test_backup_av_does_not_rescue_truck_delay(scenario: Scenario) -> None:
    """A plausible-sounding but wrong idea must be shown as infeasible, not green."""
    patch = Patch(actions=(ActivateResource(resource_id="backup-av"),))
    ev = evaluate_patch(scenario, [preset("truck-delay-35").shock], Patch(), patch, scenario.baseline)
    assert ev.status == EvaluationStatus.INFEASIBLE
    assert ev.plan is None


def test_impossible_case_reports_infeasibility_with_reasons(scenario: Scenario) -> None:
    every_lever = Patch(
        actions=(
            ActivateResource(resource_id="trolley-2"),
            ActivateResource(resource_id="backup-av"),
            CompressTask(task_id="soundcheck", duration=15),
            CompressTask(task_id="crew-briefing", duration=10),
            DeferTask(task_id="vendor-tables"),
            DeferTask(task_id="unload-vendor"),
        )
    )
    shock = preset("truck-breakdown-90").shock
    ev = evaluate_patch(scenario, [shock], Patch(), every_lever, scenario.baseline)
    assert ev.status == EvaluationStatus.INFEASIBLE
    assert ev.plan is None
    facts = ev.infeasibility
    assert facts is not None
    assert facts.precedence_bound > DOORS
    assert facts.best_delta is not None and facts.best_delta > 0
    assert facts.reasons and "18:00" in facts.reasons[0]
    assert search_recoveries(scenario, [shock], Patch(), scenario.baseline).verified == []


def test_dock_delay_is_absorbed_by_slack(scenario: Scenario) -> None:
    ev = evaluate_patch(scenario, [preset("dock-delay-20").shock], Patch(), Patch(), scenario.baseline)
    assert ev.status == EvaluationStatus.VERIFIED
    assert ev.schedule is not None and ev.schedule.deadline_delta is not None
    assert ev.schedule.deadline_delta <= 0


def test_av_outage_offers_paid_and_free_recoveries(scenario: Scenario) -> None:
    result = search_recoveries(scenario, [preset("av-tech-out").shock], Patch(), scenario.baseline)
    costs = {ev.cost_cents for ev in result.evaluations}
    assert 0 in costs and any(c > 0 for c in costs)
    for ev in result.evaluations:
        assert ev.schedule is not None and ev.schedule.readiness is not None
        assert ev.schedule.readiness <= DOORS
