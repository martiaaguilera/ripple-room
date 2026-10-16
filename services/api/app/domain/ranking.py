"""Deterministic ranking of verified options under coordinator preferences."""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.effective import EffectiveProblem
from app.domain.models import Frozen, Plan
from app.domain.preferences import PreferenceReport, Preferences, assess
from app.domain.propagate import right_shift
from app.domain.reports import Evaluation, EvaluationStatus


class RankedOption(Frozen):
    id: str
    rank: int
    evaluation: Evaluation
    report: PreferenceReport
    touched: tuple[str, ...]


def do_nothing_plan(problem: EffectiveProblem, reference: Plan) -> Plan:
    """What the floor ends up doing if nobody intervenes (right-shift of the reference)."""
    return right_shift(problem, reference).plan


def touched_tasks(ev: Evaluation, do_nothing: Plan) -> tuple[str, ...]:
    """Tasks an option actually changes relative to doing nothing."""
    before = do_nothing.by_task()
    out: set[str] = set()
    for change in ev.changes:
        if change.deferred or change.duration_to is not None or change.reassigned:
            out.add(change.task_id)
    if ev.plan is not None:
        for entry in ev.plan.entries:
            prior = before.get(entry.task_id)
            if prior is not None and (prior.start != entry.start or prior.assignments != entry.assignments):
                out.add(entry.task_id)
    return tuple(sorted(out))


def rank_options(
    options: Sequence[tuple[str, Evaluation]],
    prefs: Preferences,
    problem: EffectiveProblem,
    reference: Plan,
) -> list[RankedOption]:
    """Rank verified options; non-verified evaluations are never ranked (they are not options)."""
    baseline = do_nothing_plan(problem, reference)
    scored: list[tuple[tuple[int, float, int, str], str, Evaluation, PreferenceReport, tuple[str, ...]]] = []
    for oid, ev in options:
        if ev.status != EvaluationStatus.VERIFIED:
            continue
        touched = touched_tasks(ev, baseline)
        report = assess(ev, prefs, len(touched))
        # Tie-breaks keep the order deterministic: fewer touched tasks, then id.
        scored.append(((*report.key, len(touched), oid), oid, ev, report, touched))
    scored.sort(key=lambda s: s[0])
    return [
        RankedOption(id=oid, rank=i + 1, evaluation=ev, report=report, touched=touched)
        for i, (_, oid, ev, report, touched) in enumerate(scored)
    ]
