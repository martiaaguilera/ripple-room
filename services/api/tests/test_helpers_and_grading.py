"""add_helper semantics, graded compression and the extended oracle."""

from __future__ import annotations

import pytest

from app.domain.effective import HELPER_REQUIREMENT, compile_problem
from app.domain.models import ActivateResource, AddHelper, CompressTask, Patch, Scenario
from app.domain.reports import EvaluationStatus
from app.domain.revision import merge_committed
from app.fixtures import preset
from app.solver.evaluate import evaluate_patch
from app.solver.search import extended_menu, intervention_menu, search_recoveries

LEAD_HELPS = Patch(actions=(AddHelper(task_id="stage-rigging", resource_id="event-lead"),))


def _ev(scenario: Scenario, preset_id: str, patch: Patch):  # type: ignore[no-untyped-def]
    return evaluate_patch(scenario, [preset(preset_id).shock], Patch(), patch, scenario.baseline)


def test_idle_lead_helping_rigging_rescues_truck_delay_for_free(scenario: Scenario) -> None:
    ev = _ev(scenario, "truck-delay-35", LEAD_HELPS)
    assert ev.status == EvaluationStatus.VERIFIED
    assert ev.cost_cents == 0 and ev.service_impacts == []
    assert ev.plan is not None
    rigging = ev.plan.by_task()["stage-rigging"]
    assert rigging.assignments[HELPER_REQUIREMENT] == "event-lead"
    change = next(c for c in ev.changes if c.task_id == "stage-rigging")
    assert change.duration_to == 45


def test_busy_helper_can_make_things_worse(scenario: Scenario) -> None:
    """Pulling the transport crew onto rigging starves the AV unload: verifier says no."""
    patch = Patch(actions=(AddHelper(task_id="stage-rigging", resource_id="transport-crew"),))
    assert _ev(scenario, "truck-delay-35", patch).status == EvaluationStatus.INFEASIBLE


@pytest.mark.parametrize(
    ("action", "code"),
    [
        (AddHelper(task_id="soundcheck", resource_id="event-lead"), "NO_HELPER_SLOT"),
        (AddHelper(task_id="stage-rigging", resource_id="av-tech"), "SKILL_MISMATCH"),
        (AddHelper(task_id="stage-rigging", resource_id="ghost"), "UNKNOWN_RESOURCE"),
    ],
)
def test_invalid_helpers_rejected(scenario: Scenario, action: AddHelper, code: str) -> None:
    ev = _ev(scenario, "truck-delay-35", Patch(actions=(action,)))
    assert ev.status == EvaluationStatus.REJECTED
    assert code in {v.code for v in ev.violations}


def test_helper_cannot_combine_with_compression_of_same_task(scenario: Scenario) -> None:
    problem, violations = compile_problem(
        scenario,
        (),
        Patch(
            actions=(
                CompressTask(task_id="soundcheck", duration=20),
                AddHelper(task_id="soundcheck", resource_id="event-lead"),
            )
        ),
    )
    assert problem is None and violations


def test_helper_persists_after_apply(scenario: Scenario) -> None:
    committed = merge_committed(Patch(), LEAD_HELPS)
    assert committed.actions == LEAD_HELPS.actions


def test_compression_severity_is_graded(scenario: Scenario) -> None:
    partial = _ev(scenario, "av-tech-out", Patch(actions=(CompressTask(task_id="soundcheck", duration=25),)))
    full = _ev(scenario, "av-tech-out", Patch(actions=(CompressTask(task_id="soundcheck", duration=15),)))
    assert partial.status == full.status == EvaluationStatus.VERIFIED
    assert partial.service_impacts[0].severity == pytest.approx(1 / 3, abs=0.01)
    assert full.service_impacts[0].severity == pytest.approx(1.0)


def test_extended_oracle_is_a_superset_of_the_playbook(scenario: Scenario) -> None:
    playbook = {m.id for m in intervention_menu(scenario)}
    extended = {m.id for m in extended_menu(scenario)}
    assert playbook < extended
    assert any(i.startswith("helper:") for i in extended)
    assert any(i.startswith("compress:soundcheck:") for i in extended)


def test_extended_oracle_finds_free_no_compromise_fix(scenario: Scenario) -> None:
    result = search_recoveries(
        scenario, [preset("truck-delay-35").shock], Patch(), scenario.baseline, max_size=2, menu=extended_menu(scenario)
    )
    assert any(ev.cost_cents == 0 and not ev.service_impacts for ev in result.evaluations)
    playbook = search_recoveries(scenario, [preset("truck-delay-35").shock], Patch(), scenario.baseline)
    assert not any(ev.cost_cents == 0 and not ev.service_impacts for ev in playbook.evaluations)


def test_rejection_explains_untouched_chain(scenario: Scenario) -> None:
    ev = _ev(scenario, "truck-delay-35", Patch(actions=(ActivateResource(resource_id="backup-av"),)))
    assert ev.infeasibility is not None
    reason = ev.infeasibility.reasons[0]
    assert reason.startswith("Bringing in the backup AV technician does not touch what sets the doors time")
    assert "stage rigging" in reason and "18:15" in reason


def test_rejection_explains_insufficient_help(scenario: Scenario) -> None:
    ev = _ev(scenario, "truck-delay-35", Patch(actions=(CompressTask(task_id="crew-briefing", duration=10),)))
    assert ev.infeasibility is not None
    assert ev.infeasibility.reasons[0].startswith("This helps the chain that sets the doors time")


def test_rejection_explains_when_a_change_makes_it_worse(scenario: Scenario) -> None:
    ev = _ev(
        scenario, "truck-delay-35", Patch(actions=(AddHelper(task_id="stage-rigging", resource_id="transport-crew"),))
    )
    assert ev.infeasibility is not None
    reason = ev.infeasibility.reasons[0]
    assert "makes things worse" in reason and "later than doing nothing (18:15)" in reason
