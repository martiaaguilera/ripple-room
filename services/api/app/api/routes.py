"""HTTP routes. Thin: parse, delegate to services, return typed models."""

from __future__ import annotations

from importlib.metadata import version

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app import __version__
from app.core.config import get_settings
from app.core.errors import ApiError
from app.domain.models import Patch, Plan, Scenario, Shock
from app.domain.preferences import Preferences
from app.domain.reports import Evaluation
from app.domain.revision import Revision, baseline_revision
from app.fixtures import DEMO_SCENARIO_ID, SHOCK_PRESETS, ShockPreset, load_scenario, preset
from app.services import workflow
from app.solver.search import MenuItem, intervention_menu

router = APIRouter(prefix="/api")


class In(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AiStatus(BaseModel):
    mode: str
    provider: str
    planner_model: str
    fast_model: str
    configured: bool


class Health(BaseModel):
    status: str
    api_version: str
    ortools: str
    ai: AiStatus


class DemoPayload(BaseModel):
    scenario: Scenario
    presets: list[ShockPreset]
    menu: list[MenuItem]
    initial: workflow.RevisionView


class ShockRequest(In):
    revision: Revision
    preset_id: str | None = Field(default=None, max_length=48)
    shock: Shock | None = None


class RevisionRequest(In):
    revision: Revision


class SearchRequest(In):
    revision: Revision
    preferences: Preferences | None = None


class EvaluateRequest(In):
    revision: Revision
    patch: Patch


class ApplyRequest(In):
    revision: Revision
    base_revision_id: str = Field(max_length=40)
    patch: Patch
    plan: Plan


def ai_status() -> AiStatus:
    s = get_settings()
    live = s.live_ready
    return AiStatus(
        mode="live" if live else "mock",
        provider="nebius-token-factory" if live else "mock",
        planner_model=s.nebius_model_planner,
        fast_model=s.nebius_model_fast,
        configured=live,
    )


@router.get("/health")
def health() -> Health:
    return Health(status="ok", api_version=__version__, ortools=version("ortools"), ai=ai_status())


@router.get("/demo")
def demo() -> DemoPayload:
    scenario = load_scenario(DEMO_SCENARIO_ID)
    return DemoPayload(
        scenario=scenario,
        presets=list(SHOCK_PRESETS),
        menu=intervention_menu(scenario),
        initial=workflow.view(baseline_revision(scenario)),
    )


@router.post("/shock")
def shock(req: ShockRequest) -> workflow.RevisionView:
    if (req.preset_id is None) == (req.shock is None):
        raise ApiError(422, "INVALID_SHOCK", "Provide exactly one of preset_id or shock.")
    if req.preset_id is not None:
        try:
            chosen = preset(req.preset_id).shock
        except KeyError as exc:
            raise ApiError(422, "INVALID_SHOCK", f"Unknown preset {req.preset_id!r}.") from exc
    else:
        assert req.shock is not None  # noqa: S101 - narrowed by the check above
        chosen = req.shock
    return workflow.add_shock(req.revision, chosen)


@router.post("/view")
def view(req: RevisionRequest) -> workflow.RevisionView:
    return workflow.view(req.revision)


@router.post("/evaluate")
def evaluate(req: EvaluateRequest) -> Evaluation:
    return workflow.evaluate(req.revision, req.patch)


@router.post("/search")
def search(req: SearchRequest) -> workflow.SearchResponse:
    return workflow.search(req.revision, req.preferences)


@router.post("/apply")
def apply(req: ApplyRequest) -> workflow.RevisionView:
    return workflow.apply(req.revision, req.base_revision_id, req.patch, req.plan)
