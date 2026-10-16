"""Coordinator preferences and deterministic, auditable option ranking.

Hard constraints (deadline, skills, capacity, precedence, availability) belong to
the scenario and are enforced by the solver; nothing here can make an infeasible
plan acceptable. Preferences are *soft*: they only order verified options and flag
where an option departs from what the coordinator asked for.

Ranking key (lexicographic):
  1. number of preference breaches (over budget cap, below desired margin,
     touches a protected task);
  2. total penalty points, an explicit weighted sum shown to the user.

Penalty units (documented so every number on screen can be recomputed):
  guest   100 points per guest-facing severity unit (compress = 1, defer = 2)
  spend     1 point per euro of intervention cost
  crew     10 points per task touched + 15 per reassignment
  margin   20 points per minute short of the desired spare time
Weights per level: protect = 3, balanced = 1, flexible = 0.25.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.domain.models import Frozen, Identifier
from app.domain.reports import Evaluation

Level = Literal["protect", "balanced", "flexible"]
LEVEL_WEIGHT: dict[str, float] = {"protect": 3.0, "balanced": 1.0, "flexible": 0.25}

GUEST_POINTS_PER_SEVERITY = 100
SPEND_POINTS_PER_EURO = 1
CREW_POINTS_PER_TASK = 10
CREW_POINTS_PER_REASSIGNMENT = 15
MARGIN_POINTS_PER_MINUTE = 20


class Preferences(Frozen):
    guest_experience: Level = "balanced"
    spend: Level = "balanced"
    crew_stability: Level = "balanced"
    budget_cap_cents: int | None = Field(default=None, ge=0, le=1_000_000)
    min_margin_minutes: int = Field(default=0, ge=0, le=60)
    protected_tasks: tuple[Identifier, ...] = Field(default=(), max_length=8)
    source: Literal["default", "structured", "model", "mock"] = "default"
    summary: str = Field(default="", max_length=300)


class PreferenceBreach(Frozen):
    kind: Literal["budget", "margin", "protected_task"]
    text: str


class PenaltyLine(Frozen):
    dimension: Literal["guest", "spend", "crew", "margin"]
    raw: float
    weight: float
    points: float
    text: str


class PreferenceReport(Frozen):
    breaches: tuple[PreferenceBreach, ...]
    penalties: tuple[PenaltyLine, ...]
    total_points: float

    @property
    def key(self) -> tuple[int, float]:
        return (len(self.breaches), round(self.total_points, 3))


def assess(ev: Evaluation, prefs: Preferences, touched_tasks: int) -> PreferenceReport:
    """Score one verified evaluation against preferences. Pure and deterministic."""
    breaches: list[PreferenceBreach] = []
    margin = -(ev.schedule.deadline_delta or 0) if ev.schedule and ev.schedule.deadline_delta is not None else 0

    if prefs.budget_cap_cents is not None and ev.cost_cents > prefs.budget_cap_cents:
        breaches.append(
            PreferenceBreach(
                kind="budget",
                text=f"Costs €{ev.cost_cents / 100:.2f}, above the €{prefs.budget_cap_cents / 100:.2f} budget.",
            )
        )
    if margin < prefs.min_margin_minutes:
        breaches.append(
            PreferenceBreach(
                kind="margin", text=f"Leaves {margin} min spare; you asked for at least {prefs.min_margin_minutes}."
            )
        )
    touched_protected = sorted({s.task_id for s in ev.service_impacts} & set(prefs.protected_tasks))
    for tid in touched_protected:
        breaches.append(PreferenceBreach(kind="protected_task", text=f"Changes protected task '{tid}'."))

    severity = sum(s.severity for s in ev.service_impacts)
    euros = ev.cost_cents / 100
    shortfall = max(0, prefs.min_margin_minutes - margin)
    gw = LEVEL_WEIGHT[prefs.guest_experience]
    sw = LEVEL_WEIGHT[prefs.spend]
    cw = LEVEL_WEIGHT[prefs.crew_stability]
    crew_raw = touched_tasks * CREW_POINTS_PER_TASK + ev.reassignments * CREW_POINTS_PER_REASSIGNMENT
    lines = (
        PenaltyLine(
            dimension="guest",
            raw=severity,
            weight=gw,
            points=severity * GUEST_POINTS_PER_SEVERITY * gw,
            text=f"{severity} guest-facing severity unit(s)",
        ),
        PenaltyLine(
            dimension="spend",
            raw=euros,
            weight=sw,
            points=euros * SPEND_POINTS_PER_EURO * sw,
            text=f"€{euros:.2f} extra spend",
        ),
        PenaltyLine(
            dimension="crew",
            raw=crew_raw,
            weight=cw,
            points=crew_raw * cw,
            text=f"{touched_tasks} task(s) changed, {ev.reassignments} reassignment(s)",
        ),
        PenaltyLine(
            dimension="margin",
            raw=shortfall,
            weight=1.0,
            points=shortfall * MARGIN_POINTS_PER_MINUTE,
            text=f"{shortfall} min short of desired margin",
        ),
    )
    return PreferenceReport(
        breaches=tuple(breaches), penalties=lines, total_points=round(sum(p.points for p in lines), 3)
    )
