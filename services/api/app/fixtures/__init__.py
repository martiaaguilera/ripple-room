"""Versioned, fictional demo fixtures and their disruption presets."""

from __future__ import annotations

from functools import cache
from importlib import resources

from pydantic import BaseModel, ConfigDict

from app.domain.models import ResourceUnavailableShock, Scenario, Shock, TaskDelayShock, Window

DEMO_SCENARIO_ID = "signal-night"


@cache
def load_scenario(scenario_id: str = DEMO_SCENARIO_ID) -> Scenario:
    if scenario_id != DEMO_SCENARIO_ID:
        raise KeyError(scenario_id)
    raw = resources.files(__package__).joinpath("signal_night_v1.json").read_text(encoding="utf-8")
    return Scenario.model_validate_json(raw)


class ShockPreset(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    title: str
    subtitle: str
    shock: Shock


SHOCK_PRESETS: tuple[ShockPreset, ...] = (
    ShockPreset(
        id="truck-delay-35",
        title="Truck delayed +35 min",
        subtitle="Traffic on the ring road. Load-in starts late.",
        shock=TaskDelayShock(task_id="truck-arrival", delay_minutes=35),
    ),
    ShockPreset(
        id="av-tech-out",
        title="AV technician out 15:30–16:30",
        subtitle="Called away to another venue for an hour.",
        shock=ResourceUnavailableShock(resource_id="av-tech", window=Window(start=930, end=990)),
    ),
    ShockPreset(
        id="dock-delay-20",
        title="Dock access delayed +20 min",
        subtitle="Previous delivery still occupying the bay.",
        shock=TaskDelayShock(task_id="dock-open", delay_minutes=20),
    ),
    ShockPreset(
        id="truck-breakdown-90",
        title="Truck breakdown +90 min",
        subtitle="Replacement vehicle dispatched. Stress test.",
        shock=TaskDelayShock(task_id="truck-arrival", delay_minutes=90),
    ),
)


def preset(preset_id: str) -> ShockPreset:
    for p in SHOCK_PRESETS:
        if p.id == preset_id:
            return p
    raise KeyError(preset_id)
