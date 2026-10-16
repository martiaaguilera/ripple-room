"""Run the 20-case evaluation (from services/api).

    uv run python ../../scripts/evaluate.py --agent live      # real Nemotron calls (costs cents)
    uv run python ../../scripts/evaluate.py --agent mock      # harness check, scripted agent
    uv run python ../../scripts/evaluate.py --agent skip --cases c01,c02

Writes docs/evaluation/results-<mode>-<UTC>.json and RESULTS-<mode>-<UTC>.md. Live mode
records the model id and per-token prices read from the Nebius /v1/models endpoint.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.agent.prompts import PROMPT_VERSION  # noqa: E402
from app.agent.runner import Budget  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.evaluation.cases import CASES  # noqa: E402
from app.evaluation.harness import CaseResult, run_agent_case, run_greedy, run_search  # noqa: E402
from app.evaluation.report import summarize  # noqa: E402
from app.fixtures import load_scenario  # noqa: E402
from app.providers.factory import planner_provider  # noqa: E402
from app.providers.mock import MockProvider  # noqa: E402


async def _pricing(settings: Settings) -> dict[str, tuple[float, float]]:
    assert settings.nebius_api_key is not None
    url = settings.nebius_base_url.rstrip("/") + "/models?verbose=true"
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(url, headers={"Authorization": f"Bearer {settings.nebius_api_key.get_secret_value()}"})
    res.raise_for_status()
    out: dict[str, tuple[float, float]] = {}
    for m in res.json().get("data", []):
        pricing = m.get("pricing") or {}
        try:
            out[m["id"]] = (float(pricing.get("prompt") or 0), float(pricing.get("completion") or 0))
        except (TypeError, ValueError):
            continue
    return out


async def main_async(args: argparse.Namespace) -> int:
    env = ROOT / "services" / "api" / ".env"
    settings = Settings(_env_file=env if env.exists() else None)  # type: ignore[call-arg]
    scenario = load_scenario()
    cases = [c for c in CASES if not args.cases or c.id in args.cases.split(",")]
    pricing: dict[str, tuple[float, float]] = {}
    provider = None
    if args.agent == "live":
        live_settings = settings.model_copy(update={"ai_mode": "live"})
        provider = planner_provider(live_settings)
        pricing = await _pricing(settings)
    elif args.agent == "mock":
        provider = MockProvider(max_evaluations=settings.agent_max_evaluations)
    budget = Budget(
        max_model_calls=settings.agent_max_model_calls,
        max_total_tokens=settings.agent_max_total_tokens,
        timeout_seconds=settings.agent_timeout_seconds,
        max_output_tokens=settings.agent_max_output_tokens,
    )
    results: list[CaseResult] = []
    for case in cases:
        methods = {
            "oracle": run_search(scenario, case, oracle=True),
            "playbook_search": run_search(scenario, case, oracle=False),
            "greedy": run_greedy(scenario, case),
        }
        if provider is not None:
            methods["agent"] = await run_agent_case(scenario, case, provider, budget, settings.agent_max_evaluations, pricing)
        result = CaseResult(case_id=case.id, title=case.title, profile=case.profile.id, methods=methods)
        results.append(result)
        a = methods.get("agent")
        print(
            f"{case.id} {case.title:34s} oracle={'yes' if methods['oracle'].found else 'none':4s} "
            f"playbook={'yes' if methods['playbook_search'].found else 'none':4s} greedy={'yes' if methods['greedy'].found else 'none':4s} "
            + (f"agent={'yes' if a.found else 'none'} calls={a.model_calls} tok={a.prompt_tokens + a.completion_tokens} {a.elapsed_ms}ms err={a.error}" if a else "")
        , flush=True)
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    meta: dict[str, object] = {
        "generated_utc": stamp,
        "agent_mode": args.agent,
        "agent_model": provider.model if provider else "n/a",
        "agent_prompt_version": PROMPT_VERSION,
        "budget": f"{budget.max_model_calls} model calls, {settings.agent_max_evaluations} verifier checks, {budget.max_total_tokens} tokens, {budget.timeout_seconds}s",
        "pricing_usd_per_token": json.dumps({k: v for k, v in pricing.items() if provider and k == provider.model}) or "n/a",
        "scenario": "signal-night v1 (fictional)",
    }
    out_dir = ROOT / "docs" / "evaluation"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"results-{args.agent}-{stamp}.json").write_text(
        json.dumps({"meta": meta, "results": [r.model_dump(mode="json") for r in results]}, indent=1), encoding="utf-8"
    )
    report = summarize(results, meta)
    (out_dir / f"RESULTS-{args.agent}-{stamp}.md").write_text(report, encoding="utf-8")
    print("\n" + report)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", choices=["live", "mock", "skip"], default="skip")
    parser.add_argument("--cases", default="")
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
