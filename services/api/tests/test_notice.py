"""Crew change notice: deterministic who/what/by-when facts."""

from __future__ import annotations

from app.domain.effective import compile_problem
from app.domain.models import ActivateResource, AddHelper, Patch, Scenario
from app.domain.notice import NOTICE_LEAD_MINUTES, build_notice
from app.fixtures import preset
from app.solver.evaluate import evaluate_patch


def _notice(scenario: Scenario, patch: Patch):  # type: ignore[no-untyped-def]
    shocks = [preset("truck-delay-35").shock]
    ev = evaluate_patch(scenario, shocks, Patch(), patch, scenario.baseline)
    assert ev.plan is not None
    problem, _ = compile_problem(scenario, shocks, patch)
    assert problem is not None
    return build_notice(problem, scenario.baseline, ev.plan, patch, now=0)


def test_trolley_rental_produces_supplier_booking_and_crew_changes(scenario: Scenario) -> None:
    notice = _notice(scenario, Patch(actions=(ActivateResource(resource_id="trolley-2"),)))
    kinds = {i.kind for i in notice.items}
    assert "supplier" in kinds and "crew" in kinds
    booking = next(i for i in notice.items if i.kind == "supplier")
    assert "Rental trolley" in booking.recipient_label
    setup = next(i for i in notice.items if i.recipient_id == "setup-team")
    assert any("Stage rigging" in c.text for c in setup.changes)


def test_helper_tells_the_event_lead_about_the_new_job(scenario: Scenario) -> None:
    notice = _notice(scenario, Patch(actions=(AddHelper(task_id="stage-rigging", resource_id="event-lead"),)))
    lead = next(i for i in notice.items if i.recipient_id == "event-lead")
    assert any(c.text.startswith("New job: Stage rigging") for c in lead.changes)


def test_notify_by_precedes_first_change(scenario: Scenario) -> None:
    notice = _notice(scenario, Patch(actions=(ActivateResource(resource_id="trolley-2"),)))
    for item in notice.items:
        if item.kind != "crew":
            continue
        first = min(min(c.before[0] if c.before else 10**6, c.after[0] if c.after else 10**6) for c in item.changes)
        assert item.notify_by == max(0, first - NOTICE_LEAD_MINUTES)


def test_people_without_changes_are_listed_as_unchanged(scenario: Scenario) -> None:
    notice = _notice(scenario, Patch(actions=(ActivateResource(resource_id="trolley-2"),)))
    recipients = {i.recipient_id for i in notice.items}
    assert all(label for label in notice.unchanged)
    assert "event-lead" not in recipients or "Event lead" not in notice.unchanged


def test_equipment_is_never_a_recipient(scenario: Scenario) -> None:
    notice = _notice(scenario, Patch(actions=(ActivateResource(resource_id="trolley-2"),)))
    crew_ids = {i.recipient_id for i in notice.items if i.kind == "crew"}
    assert not crew_ids & {"trolley-1", "trolley-2", "stage"}
