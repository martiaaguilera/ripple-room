"""Run one recovery through the real agent loop and save a sanitized trace as evidence.

    uv run python ../../scripts/run_live_recovery.py --preset truck-delay-35 --priorities "Keep spend at zero."

Uses services/api/.env (AI_MODE=live + NEBIUS_API_KEY). Prints a compact transcript and
writes docs/evidence/live-run-<preset>-<UTC>.json. Each run costs well under one cent on
Nemotron 3 Super at current list prices (verify in the Nebius billing console).
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.agent.runner import Budget, run_agent  # noqa: E402
from app.agent.tools import AgentContext  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.domain.effective import compile_problem  # noqa: E402
from app.domain.revision import baseline_revision  # noqa: E402
from app.fixtures import load_scenario, preset  # noqa: E402
from app.providers.factory import planner_provider  # noqa: E402
from app.services.workflow import add_shock  # noqa: E402


async def run(preset_id: str, priorities: str, model: str | None) -> dict[str, Any]:
    env = ROOT / "services" / "api" / ".env"
    settings = Settings(_env_file=env if env.exists() else None)  # type: ignore[call-arg]
    if model:
        settings = settings.model_copy(update={"nebius_model_planner": model})
    scenario = load_scenario()
    revision = add_shock(baseline_revision(scenario), preset(preset_id).shock).revision
    problem, _ = compile_problem(scenario, revision.state.shocks, revision.state.committed)
    assert problem is not None
    ctx = AgentContext.build(scenario, revision, problem, settings.agent_max_evaluations)
    provider = planner_provider(settings)
    budget = Budget(
        max_model_calls=settings.agent_max_model_calls,
        max_total_tokens=settings.agent_max_total_tokens,
        timeout_seconds=settings.agent_timeout_seconds,
        max_output_tokens=settings.agent_max_output_tokens,
    )
    events = []
    async for ev in run_agent(ctx, provider, budget, priorities, mode_label="live" if provider.live else "mock"):
        events.append(ev.model_dump(mode="json"))
        d = ev.data
        if ev.type == "model_call":
            print(f"[{ev.at_ms:>6}ms] model call {d['n']}: {d['latency_ms']}ms tokens={d['usage']['total_tokens']} tools={d['tool_calls']} req={d['request_id']}")
        elif ev.type == "tool_result":
            print(f"[{ev.at_ms:>6}ms]   {d['name']}: {d['summary']}{'' if d['ok'] else '  (REJECTED)'}")
        elif ev.type == "candidate":
            evaluation = d["evaluation"]
            reason = ""
            if evaluation.get("infeasibility"):
                reason = " | " + "; ".join(evaluation["infeasibility"]["reasons"])[:160]
            elif evaluation.get("violations"):
                reason = " | " + evaluation["violations"][0]["message"]
            print(f"             candidate {d['candidate_id']}: {evaluation['status']} :: {d['rationale'][:120]}{reason}")
        elif ev.type == "options":
            print(f"options (finalized_by_model={d['finalized_by_model']}): {d.get('summary')}")
            for o in d["options"]:
                e = o["evaluation"]
                print(f"   - {o['candidate_id']} {o['title']!r} ready={e['schedule']['readiness']} cost={e['cost_cents']} :: {o['why'][:160]}")
        elif ev.type in ("error", "done"):
            print(f"{ev.type}: {json.dumps(d)}")
    return {
        "timestamp_utc": dt.datetime.now(dt.UTC).isoformat(),
        "preset": preset_id,
        "priorities": priorities,
        "base_revision_id": revision.id,
        "events": events,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", default="truck-delay-35")
    parser.add_argument("--priorities", default="")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()
    report = asyncio.run(run(args.preset, args.priorities, args.model))
    out = ROOT / "docs" / "evidence" / f"live-run-{args.preset}-{dt.datetime.now(dt.UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"\nTrace written to {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
