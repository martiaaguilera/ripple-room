"""Deterministic progress facts about the model's own proposals.

Two facts, both computed only from candidates the model itself proposed (``origin == "model"``)
and from data the model has already seen; neither reveals whether a better option exists:

* coverage: which preference dimensions none of the model's verified options covers yet
  (measured weakness: narrow exploration under "protect guests" priorities, c01/c05/c06/c20);
* combinations: which of the model's own near-misses (infeasible, but each gaining minutes)
  touch different work and have not been tried together (measured weakness: c09).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import combinations
from typing import Any

from app.domain.models import Intervention, Plan
from app.domain.preferences import LEVEL_WEIGHT, Preferences, assess
from app.domain.ranking import touched_tasks
from app.domain.reports import Evaluation, EvaluationStatus

MAX_COMBINATIONS = 3
MAX_COMBINATION_SIZE = 3
MAX_PATCH_ACTIONS = 8  # same cap as evaluate_patch accepts


@dataclass(frozen=True)
class _Goal:
    key: str
    text: str
    weight: float
    priority: str
    met: Callable[[Evaluation, bool], bool]  # (evaluation, has no preference breaches)


def _goals(prefs: Preferences) -> list[_Goal]:
    """Preference goals worth covering, most important first (stated limits, then by level weight).

    Dimensions the coordinator marked "flexible" are not goals. Crew stability is a goal only under
    "protect": nearly every non-cut fix (helper, extra kit) moves someone, so under "balanced" a
    "no reassignment" gap would mostly steer the model back to guest-facing cuts.
    """
    flexible = "flexible"
    goals: list[_Goal] = []
    if prefs.budget_cap_cents is not None or prefs.min_margin_minutes or prefs.protected_tasks:
        goals.append(
            _Goal(
                "all_preferences",
                "respects every stated preference (no preference breaches)",
                10.0,
                "stated",
                lambda _ev, clean: clean,
            )
        )
    guest, spend = prefs.guest_experience != flexible, prefs.spend != flexible
    gw, sw = LEVEL_WEIGHT[prefs.guest_experience], LEVEL_WEIGHT[prefs.spend]
    if guest:
        goals.append(
            _Goal(
                "no_guest_impact",
                "no guest-facing cut (no service impacts)",
                gw,
                prefs.guest_experience,
                lambda ev, _c: not ev.service_impacts,
            )
        )
    if spend:
        goals.append(_Goal("zero_cost", "zero extra spend", sw, prefs.spend, lambda ev, _c: ev.cost_cents == 0))
    if guest and spend:
        # Listed after both halves (weight = the lower one), so coverage() can tell if it adds anything.
        goals.append(
            _Goal(
                "no_guest_impact_and_zero_cost",
                "no guest-facing cut AND zero extra spend",
                min(gw, sw),
                "combined",
                lambda ev, _c: not ev.service_impacts and ev.cost_cents == 0,
            )
        )
    if prefs.crew_stability == "protect":
        goals.append(
            _Goal(
                "no_reassignment",
                "no crew reassignments",
                LEVEL_WEIGHT["protect"],
                "protect",
                lambda ev, _c: ev.reassignments == 0,
            )
        )
    # Stable sort: equal weights keep the order above.
    return sorted(goals, key=lambda g: -g.weight)


def coverage(
    model_verified: Sequence[tuple[str, Evaluation]],
    server_verified: Sequence[tuple[str, Evaluation]],
    prefs: Preferences,
    do_nothing: Plan,
) -> dict[str, Any] | None:
    """Which preference goals none of the model's verified options meets yet.

    ``server_verified`` (playbook / no-change options the model has already been shown) is only used
    to say which gaps are already covered by them. Returns None until the model has a verified option.
    """
    mine = [(cid, ev) for cid, ev in model_verified if ev.status == EvaluationStatus.VERIFIED]
    if not mine:
        return None

    def clean(ev: Evaluation) -> bool:
        return not assess(ev, prefs, len(touched_tasks(ev, do_nothing))).breaches

    server = [(cid, ev, clean(ev)) for cid, ev in server_verified if ev.status == EvaluationStatus.VERIFIED]
    flags = [(ev, clean(ev)) for _, ev in mine]
    gaps: list[dict[str, Any]] = []
    missing: set[str] = set()
    for goal in _goals(prefs):
        if any(goal.met(ev, ok) for ev, ok in flags):
            continue
        missing.add(goal.key)
        # The joint goal only adds information when each half is covered separately (e.g. a paid
        # no-cut option and a free option with a cut, but nothing that is both).
        if goal.key == "no_guest_impact_and_zero_cost" and missing & {"no_guest_impact", "zero_cost"}:
            continue
        gap: dict[str, Any] = {"id": goal.key, "goal": goal.text, "priority": goal.priority}
        covered = [cid for cid, ev, ok in server if goal.met(ev, ok)]
        if covered:
            gap["already_met_by_server_options"] = covered[:3]
        gaps.append(gap)
    return {
        "your_verified_options": [cid for cid, _ in mine],
        "not_yet_covered_by_your_options": gaps,
        "note": "Gaps in your own verified options only. Whether an option filling a gap exists is unknown;"
        " only evaluate_patch can tell.",
    }


def _targets(action: Intervention) -> set[str]:
    task = getattr(action, "task_id", None)
    resource = getattr(action, "resource_id", None)
    out = {f"task:{task}"} if task is not None else set()
    if action.type in ("activate_resource", "add_helper", "assign_resource") and resource is not None:
        out.add(f"resource:{resource}")
    return out


def _key(action: Intervention) -> str:
    return action.model_dump_json()


def combinable_partials(
    model_tried: Sequence[tuple[str, Evaluation]],
    no_action_readiness: int | None,
) -> list[dict[str, Any]]:
    """Groups of the model's own infeasible proposals that each gained minutes and touch different work.

    Deterministic: candidates in proposal order, combinations ranked by total minutes gained (a
    rough ordering only; gains are not additive), then smaller groups, then ids. Groups whose union
    the model already tried (as one patch or inside a larger one) are skipped.
    """
    if no_action_readiness is None:
        return []
    partials: list[tuple[str, int, int | None, tuple[Intervention, ...]]] = []
    for cid, ev in model_tried:
        if ev.status != EvaluationStatus.INFEASIBLE or ev.infeasibility is None:
            continue
        best = ev.infeasibility.best_readiness
        if best is None or not ev.patch.actions:
            continue
        gained = no_action_readiness - best
        if gained > 0:
            partials.append((cid, gained, ev.infeasibility.best_delta, ev.patch.actions))
    tried = [{_key(a) for a in ev.patch.actions} for _, ev in model_tried]
    groups: list[tuple[tuple[int, int, tuple[str, ...]], dict[str, Any]]] = []
    for size in range(2, MAX_COMBINATION_SIZE + 1):
        for group in combinations(partials, size):
            target_sets = [set().union(*(_targets(a) for a in actions)) for _, _, _, actions in group]
            if any(target_sets[i] & target_sets[j] for i, j in combinations(range(size), 2)):
                continue
            union = {_key(a) for _, _, _, actions in group for a in actions}
            if len(union) > MAX_PATCH_ACTIONS or any(union <= t for t in tried):
                continue
            ids = tuple(cid for cid, _, _, _ in group)
            total = sum(g for _, g, _, _ in group)
            groups.append(
                (
                    (-total, size, ids),
                    {
                        "candidate_ids": list(ids),
                        "minutes_gained_each": [g for _, g, _, _ in group],
                        "still_late_by_each": [d for _, _, d, _ in group],
                    },
                )
            )
    groups.sort(key=lambda g: g[0])
    return [g for _, g in groups[:MAX_COMBINATIONS]]


COMBINE_NOTE = (
    "Your own infeasible proposals that each gained minutes and change different tasks, not yet tried"
    " together. Gains are not additive; put their actions in one evaluate_patch call to find out."
)
