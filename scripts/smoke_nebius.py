"""Live smoke test for Nebius Token Factory. Never prints the API key.

Usage (from services/api so the project venv and .env are used):
    uv run python ../../scripts/smoke_nebius.py --list-models
    uv run python ../../scripts/smoke_nebius.py --probe            # plain + tool-calling probe
    uv run python ../../scripts/smoke_nebius.py --probe --model nvidia/Nemotron-3-Ultra-550b-a55b

Writes sanitized evidence (model id, request id, latency, usage, feature flags) to
docs/evidence/nebius-smoke-<UTC timestamp>.json. Costs a few cents at most.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.core.config import Settings  # noqa: E402
from app.providers.base import ProviderError  # noqa: E402
from app.providers.nebius import NebiusProvider  # noqa: E402

TOOL = {
    "type": "function",
    "function": {
        "name": "evaluate_patch",
        "description": "Verify a schedule patch.",
        "parameters": {
            "type": "object",
            "properties": {"actions": {"type": "array", "items": {"type": "object"}}, "rationale": {"type": "string"}},
            "required": ["actions", "rationale"],
        },
    },
}


def _settings() -> Settings:
    env = ROOT / "services" / "api" / ".env"
    return Settings(_env_file=env if env.exists() else None)  # type: ignore[call-arg]


async def list_models(settings: Settings) -> dict[str, Any]:
    assert settings.nebius_api_key is not None
    url = settings.nebius_base_url.rstrip("/") + "/models?verbose=true"
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(url, headers={"Authorization": f"Bearer {settings.nebius_api_key.get_secret_value()}"})
    res.raise_for_status()
    data = res.json().get("data", [])
    nvidia = [m for m in data if "nvidia" in str(m.get("id", "")).lower() or "nemotron" in str(m.get("id", "")).lower()]
    return {
        "total_models": len(data),
        "nvidia_models": [
            {k: m.get(k) for k in ("id", "status", "context_length", "pricing", "supported_features", "regions") if k in m}
            for m in nvidia
        ],
    }


async def probe(settings: Settings, model: str, extra: dict[str, Any]) -> dict[str, Any]:
    assert settings.nebius_api_key is not None
    provider = NebiusProvider(
        api_key=settings.nebius_api_key.get_secret_value(),
        base_url=settings.nebius_base_url,
        model=model,
        timeout_seconds=90,
        max_retries=1,
        extra_body=extra,
    )
    out: dict[str, Any] = {"model_requested": model, "extra_body": extra}
    plain = await provider.complete(
        [{"role": "user", "content": "Reply with exactly: READY"}], max_tokens=512, temperature=0.2
    )
    out["plain"] = {
        "model_reported": plain.model,
        "request_id": plain.request_id,
        "latency_ms": plain.latency_ms,
        "usage": plain.usage.__dict__,
        "content": (plain.content or "")[:80],
        "has_reasoning_field": plain.reasoning is not None,
        "finish_reason": plain.finish_reason,
    }
    tooled = await provider.complete(
        [
            {"role": "system", "content": "You must call the evaluate_patch tool."},
            {"role": "user", "content": "Propose activating resource trolley-2 and verify it with the tool."},
        ],
        tools=[TOOL],
        max_tokens=1024,
        temperature=0.2,
    )
    out["tool_calling"] = {
        "request_id": tooled.request_id,
        "latency_ms": tooled.latency_ms,
        "usage": tooled.usage.__dict__,
        "tool_calls": [{"name": c.name, "arguments": c.arguments[:200]} for c in tooled.tool_calls],
        "finish_reason": tooled.finish_reason,
        "has_reasoning_field": tooled.reasoning is not None,
    }
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-models", action="store_true")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--model", default=None)
    parser.add_argument("--extra-body", default=None, help='JSON, e.g. \'{"chat_template_kwargs":{"enable_thinking":false}}\'')
    args = parser.parse_args()
    settings = _settings()
    if settings.nebius_api_key is None or not settings.nebius_api_key.get_secret_value():
        print("NEBIUS_API_KEY is not set (env or services/api/.env). Nothing was called.")
        return 2
    report: dict[str, Any] = {"timestamp_utc": dt.datetime.now(dt.UTC).isoformat(), "base_url": settings.nebius_base_url}
    try:
        if args.list_models:
            report["models"] = asyncio.run(list_models(settings))
        if args.probe:
            extra = json.loads(args.extra_body) if args.extra_body else {}
            report["probe"] = asyncio.run(probe(settings, args.model or settings.nebius_model_planner, extra))
    except ProviderError as exc:
        report["error"] = {"code": exc.code, "status": exc.status, "message": str(exc)}
    except httpx.HTTPStatusError as exc:
        report["error"] = {"status": exc.response.status_code, "message": exc.response.text[:300]}
    evidence = ROOT / "docs" / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    path = evidence / f"nebius-smoke-{dt.datetime.now(dt.UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    text = json.dumps(report, indent=2)
    assert settings.nebius_api_key.get_secret_value() not in text
    path.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nEvidence written to {path.relative_to(ROOT)}")
    return 1 if "error" in report else 0


if __name__ == "__main__":
    raise SystemExit(main())
