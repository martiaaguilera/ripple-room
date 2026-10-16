"""Crew change notice: who must be told what, and by when.

Facts only, derived deterministically by diffing the plan people currently hold
(the reference plan) against the recovery plan. Wording for messages can be
drafted by the model separately; it never changes these facts.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

from pydantic import Field

from app.domain.analysis import fmt_clock
from app.domain.effective import EffectiveProblem
from app.domain.models import ActivateResource, Frozen, Patch, Plan

NOTICE_LEAD_MINUTES = 15
"""People should hear about a change at least this long before the earlier of old and new start."""


class NoticeChange(Frozen):
    task_id: str
    task_label: str
    before: tuple[int, int] | None  # (start, end) in the plan they hold
    after: tuple[int, int] | None  # (start, end) in the recovery plan
    text: str


class NoticeItem(Frozen):
    recipient_id: str
    recipient_label: str
    kind: Literal["crew", "supplier"]
    notify_by: int
    changes: tuple[NoticeChange, ...]


class ChangeNotice(Frozen):
    items: tuple[NoticeItem, ...]
    unchanged: tuple[str, ...] = Field(description="People whose day does not change")


def _span(plan_entries: dict[str, tuple[int, int, dict[str, str]]], tid: str) -> tuple[int, int] | None:
    entry = plan_entries.get(tid)
    return None if entry is None else (entry[0], entry[1])


def build_notice(problem: EffectiveProblem, before: Plan, after: Plan, patch: Patch, now: int) -> ChangeNotice:
    scenario = problem.scenario
    durations = {t.id: t.duration for t in scenario.tasks}
    b = {e.task_id: (e.start, e.start + durations[e.task_id], e.assignments) for e in before.entries}
    a = {
        e.task_id: (e.start, e.start + problem.tasks[e.task_id].duration, e.assignments)
        for e in after.entries
        if e.task_id in problem.tasks
    }

    per_person: dict[str, list[NoticeChange]] = defaultdict(list)
    for task in scenario.tasks:
        if task.milestone:
            continue
        old = b.get(task.id)
        new = a.get(task.id)
        old_people = set(old[2].values()) if old else set()
        new_people = set(new[2].values()) if new else set()
        for rid in sorted(old_people | new_people):
            res = scenario.resource(rid)
            if res.kind == "space":
                continue
            was, now_span = (
                _span(b, task.id) if rid in old_people else None,
                _span(a, task.id) if rid in new_people else None,
            )
            if was == now_span:
                continue
            if was and now_span:
                text = f"{task.label} moves to {fmt_clock(now_span[0])}–{fmt_clock(now_span[1])} (was {fmt_clock(was[0])}–{fmt_clock(was[1])})."
            elif now_span:
                text = f"New job: {task.label} {fmt_clock(now_span[0])}–{fmt_clock(now_span[1])}."
            else:
                assert was is not None  # noqa: S101 - one side differs, so the old span exists
                reason = "moved after doors" if task.id in problem.deferred else "now done by someone else"
                text = f"No longer needed for {task.label} at {fmt_clock(was[0])} ({reason})."
            per_person[rid].append(
                NoticeChange(task_id=task.id, task_label=task.label, before=was, after=now_span, text=text)
            )

    items: list[NoticeItem] = []
    for rid, changes in per_person.items():
        res = scenario.resource(rid)
        earliest = min(min(c.before[0] if c.before else 10**6, c.after[0] if c.after else 10**6) for c in changes)
        items.append(
            NoticeItem(
                recipient_id=rid,
                recipient_label=res.label,
                kind="crew",
                notify_by=max(now, earliest - NOTICE_LEAD_MINUTES),
                changes=tuple(sorted(changes, key=lambda c: (c.after or c.before or (0, 0))[0])),
            )
        )
    for action in patch.actions:
        if isinstance(action, ActivateResource):
            res = scenario.resource(action.resource_id)
            used = [e for e in after.entries if action.resource_id in e.assignments.values()]
            first = min((e.start for e in used), default=now)
            items.append(
                NoticeItem(
                    recipient_id=f"book:{res.id}",
                    recipient_label=f"Book: {res.label}",
                    kind="supplier",
                    notify_by=max(now, first - 2 * NOTICE_LEAD_MINUTES),
                    changes=(
                        NoticeChange(
                            task_id=used[0].task_id if used else "",
                            task_label=res.label,
                            before=None,
                            after=(first, first),
                            text=f"Confirm {res.label.lower()} for {fmt_clock(first)}. {res.note}".strip(),
                        ),
                    ),
                )
            )
    items.sort(key=lambda i: (i.notify_by, i.kind != "supplier", i.recipient_label))
    people = {r.id for r in scenario.resources if r.kind == "person" and not r.standby}
    unchanged = tuple(sorted(scenario.resource(r).label for r in people - set(per_person)))
    return ChangeNotice(items=tuple(items), unchanged=unchanged)
