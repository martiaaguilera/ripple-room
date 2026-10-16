"""Preference handling: soft, explicit, deterministic and auditable."""

from __future__ import annotations

import pytest

from app.domain.effective import compile_problem
from app.domain.models import ActivateResource, CompressTask, Patch, Scenario
from app.domain.preferences import Preferences, assess
from app.domain.ranking import do_nothing_plan, rank_options, touched_tasks
from app.domain.reports import Evaluation
from app.fixtures import preset
from app.solver.evaluate import evaluate_patch

TROLLEY = Patch(actions=(ActivateResource(resource_id="trolley-2"),))
LINE_CHECK = Patch(actions=(CompressTask(task_id="soundcheck", duration=15),))
BACKUP_AV = Patch(actions=(ActivateResource(resource_id="backup-av"),))


@pytest.fixture(scope="module")
def truck(scenario: Scenario) -> tuple[object, dict[str, Evaluation]]:
    shocks = [preset("truck-delay-35").shock]
    problem, _ = compile_problem(scenario, shocks)
    assert problem is not None
    evs = {
        "trolley": evaluate_patch(scenario, shocks, Patch(), TROLLEY, scenario.baseline),
        "line-check": evaluate_patch(scenario, shocks, Patch(), LINE_CHECK, scenario.baseline),
        "backup-av": evaluate_patch(scenario, shocks, Patch(), BACKUP_AV, scenario.baseline),
    }
    return problem, evs


def _ranked(scenario: Scenario, truck: tuple[object, dict[str, Evaluation]], prefs: Preferences) -> list[str]:
    problem, evs = truck
    return [r.id for r in rank_options(list(evs.items()), prefs, problem, scenario.baseline)]  # type: ignore[arg-type]


def test_infeasible_options_are_never_ranked(scenario: Scenario, truck: tuple[object, dict[str, Evaluation]]) -> None:
    assert "backup-av" not in _ranked(scenario, truck, Preferences())


def test_guest_first_prefers_paid_fix_without_guest_impact(
    scenario: Scenario, truck: tuple[object, dict[str, Evaluation]]
) -> None:
    prefs = Preferences(guest_experience="protect", spend="flexible")
    assert _ranked(scenario, truck, prefs)[0] == "trolley"


def test_zero_spend_prefers_free_fix(scenario: Scenario, truck: tuple[object, dict[str, Evaluation]]) -> None:
    prefs = Preferences(guest_experience="flexible", spend="protect")
    assert _ranked(scenario, truck, prefs)[0] == "line-check"


def test_budget_cap_is_a_flagged_breach_not_a_filter(
    scenario: Scenario, truck: tuple[object, dict[str, Evaluation]]
) -> None:
    problem, evs = truck
    prefs = Preferences(budget_cap_cents=2000, guest_experience="protect")
    ranked = rank_options(list(evs.items()), prefs, problem, scenario.baseline)  # type: ignore[arg-type]
    by_id = {r.id: r for r in ranked}
    assert "trolley" in by_id, "over-budget options stay visible"
    assert [b.kind for b in by_id["trolley"].report.breaches] == ["budget"]
    assert ranked[0].id == "line-check", "a breach outranks any penalty difference"


def test_protected_task_flags_compression(scenario: Scenario, truck: tuple[object, dict[str, Evaluation]]) -> None:
    _, evs = truck
    report = assess(evs["line-check"], Preferences(protected_tasks=("soundcheck",)), touched_tasks=3)
    assert [b.kind for b in report.breaches] == ["protected_task"]


def test_margin_preference(scenario: Scenario, truck: tuple[object, dict[str, Evaluation]]) -> None:
    _, evs = truck
    ev = evs["line-check"]  # ready exactly at 18:00, zero margin
    report = assess(ev, Preferences(min_margin_minutes=10), touched_tasks=1)
    assert [b.kind for b in report.breaches] == ["margin"]
    margin_line = next(p for p in report.penalties if p.dimension == "margin")
    assert margin_line.points == 10 * 20


def test_penalties_are_recomputable(scenario: Scenario, truck: tuple[object, dict[str, Evaluation]]) -> None:
    _, evs = truck
    report = assess(evs["trolley"], Preferences(spend="protect"), touched_tasks=4)
    spend = next(p for p in report.penalties if p.dimension == "spend")
    assert spend.points == pytest.approx(35 * 3)
    assert report.total_points == pytest.approx(sum(p.points for p in report.penalties))


def test_touched_excludes_forced_incident_shifts(
    scenario: Scenario, truck: tuple[object, dict[str, Evaluation]]
) -> None:
    problem, evs = truck
    baseline = do_nothing_plan(problem, scenario.baseline)  # type: ignore[arg-type]
    touched = touched_tasks(evs["line-check"], baseline)
    assert "soundcheck" in touched
    assert "truck-arrival" not in touched and "scanner-setup" not in touched


def test_ranking_is_deterministic(scenario: Scenario, truck: tuple[object, dict[str, Evaluation]]) -> None:
    prefs = Preferences()
    assert _ranked(scenario, truck, prefs) == _ranked(scenario, truck, prefs)


def test_preferences_reject_unknown_fields() -> None:
    with pytest.raises(ValueError):
        Preferences.model_validate({"spend": "protect", "ignore_deadline": True})
