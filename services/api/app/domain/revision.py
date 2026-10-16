"""Immutable, content-addressed scenario revisions (held by the client, verified by the server)."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import Field

from app.domain.models import (
    ActivateResource,
    CompressTask,
    DeferTask,
    Frozen,
    Intervention,
    Patch,
    Plan,
    Scenario,
    Shock,
)

MAX_SHOCKS = 4


class RevisionState(Frozen):
    scenario_id: str
    scenario_version: str
    shocks: tuple[Shock, ...] = Field(default=(), max_length=MAX_SHOCKS)
    committed: Patch = Patch()
    plan: Plan
    parent_id: str | None = None
    source: Literal["baseline", "shock", "apply"]


class Revision(Frozen):
    id: str
    state: RevisionState


def revision_id(state: RevisionState) -> str:
    canonical = json.dumps(state.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return "rev_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def make_revision(state: RevisionState) -> Revision:
    return Revision(id=revision_id(state), state=state)


def baseline_revision(scenario: Scenario) -> Revision:
    return make_revision(
        RevisionState(
            scenario_id=scenario.id,
            scenario_version=scenario.version,
            plan=scenario.baseline,
            source="baseline",
        )
    )


def structural_actions(patch: Patch) -> tuple[Intervention, ...]:
    """Actions that persist after apply. Pins/assignments are already encoded in the applied plan."""
    return tuple(a for a in patch.actions if isinstance(a, ActivateResource | CompressTask | DeferTask))


def merge_committed(committed: Patch, applied: Patch) -> Patch:
    merged: list[Intervention] = list(committed.actions)
    for action in structural_actions(applied):
        if action not in merged:
            merged.append(action)
    return Patch(actions=tuple(merged), rationale="")
