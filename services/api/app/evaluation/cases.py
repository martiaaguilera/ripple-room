"""The 20 fixed evaluation cases: incidents x coordinator preference profiles.

Cases are defined up front and never filtered by outcome. Every method sees the
same scenario, shocks and structured preferences; the agent additionally gets the
coordinator's words (``text``) exactly as a user would type them.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.domain.models import ResourceUnavailableShock, Shock, TaskDelayShock, Window
from app.domain.preferences import Preferences


class Profile(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    text: str
    preferences: Preferences


class Case(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    shocks: tuple[Shock, ...]
    profile: Profile


def _hm(h: int, m: int = 0) -> int:
    return h * 60 + m


PROFILES = {
    "guest": Profile(
        id="guest",
        text="Protect the guest experience; spending some money is fine.",
        preferences=Preferences(guest_experience="protect", spend="flexible", source="structured"),
    ),
    "money": Profile(
        id="money",
        text="No extra spend today. Small quality cuts are acceptable.",
        preferences=Preferences(spend="protect", guest_experience="flexible", source="structured"),
    ),
    "balanced": Profile(id="balanced", text="", preferences=Preferences(source="structured")),
    "crew": Profile(
        id="crew",
        text="Keep the crew plan as stable as possible; people are already briefed.",
        preferences=Preferences(crew_stability="protect", source="structured"),
    ),
    "budget": Profile(
        id="budget",
        text="Keep it under €50 and leave us at least 10 minutes of slack before doors.",
        preferences=Preferences(budget_cap_cents=5000, min_margin_minutes=10, source="structured"),
    ),
    "sponsor": Profile(
        id="sponsor",
        text="Sponsors need the vendor tables ready. Protect the guest experience.",
        preferences=Preferences(guest_experience="protect", protected_tasks=("vendor-tables",), source="structured"),
    ),
}


def _truck(minutes: int) -> TaskDelayShock:
    return TaskDelayShock(task_id="truck-arrival", delay_minutes=minutes)


def _away(resource: str, start: int, end: int) -> ResourceUnavailableShock:
    return ResourceUnavailableShock(resource_id=resource, window=Window(start=start, end=end))


_SPECS: list[tuple[str, str, tuple[Shock, ...], str]] = [
    ("c01", "Truck +35", (_truck(35),), "guest"),
    ("c02", "Truck +35", (_truck(35),), "money"),
    ("c03", "Truck +35", (_truck(35),), "balanced"),
    ("c04", "Truck +25", (_truck(25),), "money"),
    ("c05", "Truck +25", (_truck(25),), "guest"),
    ("c06", "Truck +45", (_truck(45),), "guest"),
    ("c07", "Truck +45", (_truck(45),), "money"),
    ("c08", "Truck +55", (_truck(55),), "balanced"),
    ("c09", "Truck +65", (_truck(65),), "balanced"),
    ("c10", "Truck breakdown +90", (_truck(90),), "guest"),
    ("c11", "AV tech out 15:30-16:30", (_away("av-tech", _hm(15, 30), _hm(16, 30)),), "money"),
    ("c12", "AV tech out 15:30-16:30", (_away("av-tech", _hm(15, 30), _hm(16, 30)),), "guest"),
    ("c13", "AV tech out 15:00-16:30", (_away("av-tech", _hm(15), _hm(16, 30)),), "crew"),
    ("c14", "Dock +20", (TaskDelayShock(task_id="dock-open", delay_minutes=20),), "balanced"),
    ("c15", "Dock +40", (TaskDelayShock(task_id="dock-open", delay_minutes=40),), "budget"),
    ("c16", "Truck +25 and AV out 15:30-16:15", (_truck(25), _away("av-tech", _hm(15, 30), _hm(16, 15))), "crew"),
    ("c17", "Lighting tech out 15:30-16:30", (_away("light-tech", _hm(15, 30), _hm(16, 30)),), "balanced"),
    ("c18", "Event lead out 16:45-17:30", (_away("event-lead", _hm(16, 45), _hm(17, 30)),), "sponsor"),
    ("c19", "Setup team out 14:30-15:30", (_away("setup-team", _hm(14, 30), _hm(15, 30)),), "balanced"),
    ("c20", "Transport crew out 14:00-15:00", (_away("transport-crew", _hm(14), _hm(15)),), "guest"),
]

CASES: tuple[Case, ...] = tuple(
    Case(id=cid, title=title, shocks=shocks, profile=PROFILES[profile]) for cid, title, shocks, profile in _SPECS
)
