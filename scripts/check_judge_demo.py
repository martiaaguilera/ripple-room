"""Smoke-test a deployed Ripple Room end to end, as a judge would use it.

    uv run python ../../scripts/check_judge_demo.py https://ripple-room-five.vercel.app

Runs: page load, health, demo, preset shock, playbook search, apply (server re-verification),
stale-revision rejection, streaming agent run (SSE), and incident interpretation. Prints
timings and the AI mode the server reports. Exit code 1 on any failed check.
In live mode the agent run makes real (cheap) Nemotron calls.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any

import httpx


def main(base: str) -> int:
    base = base.rstrip("/")
    failures: list[str] = []
    client = httpx.Client(timeout=120, follow_redirects=True)

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")
        if not ok:
            failures.append(name)

    def timed(method: str, path: str, **kw: Any) -> tuple[httpx.Response, float]:
        t0 = time.perf_counter()
        res = client.request(method, base + path, **kw)
        return res, (time.perf_counter() - t0) * 1000

    res, ms = timed("GET", "/")
    check("page loads", res.status_code == 200 and "Ripple Room" in res.text, f"{res.status_code} {ms:.0f}ms")

    res, ms = timed("GET", "/api/health")
    health = res.json()
    check("health", res.status_code == 200 and health.get("status") == "ok", f"{ms:.0f}ms ai={health.get('ai', {}).get('mode')} model={health.get('ai', {}).get('planner_model')}")
    check("no secrets in health", "key" not in json.dumps(health).lower())

    res, ms = timed("GET", "/api/demo")
    demo = res.json()
    check("demo verified baseline", res.status_code == 200 and demo["initial"]["verified"], f"{ms:.0f}ms")
    base_rev = demo["initial"]["revision"]

    res, ms = timed("POST", "/api/shock", json={"revision": base_rev, "preset_id": "truck-delay-35"})
    shocked = res.json()
    delta = shocked.get("impact", {}).get("schedule", {}).get("deadline_delta")
    check("shock propagates", res.status_code == 200 and delta is not None and delta > 0, f"{ms:.0f}ms doors {delta:+} min")
    rev = shocked["revision"]

    res, ms = timed("POST", "/api/search", json={"revision": rev})
    search = res.json()
    options = search.get("options", [])
    check("playbook search finds verified options", res.status_code == 200 and len(options) > 0, f"{ms:.0f}ms options={len(options)}")

    if options:
        ev = options[0]["evaluation"]
        res, ms = timed("POST", "/api/apply", json={"revision": rev, "base_revision_id": rev["id"], "patch": ev["patch"], "plan": ev["plan"]})
        check("apply re-verifies and commits", res.status_code == 200 and res.json().get("verified") is True, f"{ms:.0f}ms")
        res, _ = timed("POST", "/api/apply", json={"revision": rev, "base_revision_id": "rev_0000000000000000", "patch": ev["patch"], "plan": ev["plan"]})
        check("stale revision rejected", res.status_code == 409)

    t0 = time.perf_counter()
    events: list[str] = []
    first_byte: float | None = None
    with client.stream("POST", base + "/api/recover", json={"revision": rev, "priorities": "Keep spend low."}) as stream:
        check("recover streams", stream.status_code == 200 and stream.headers.get("content-type", "").startswith("text/event-stream"), f"status={stream.status_code}")
        for line in stream.iter_lines():
            if line.startswith("event:"):
                if first_byte is None:
                    first_byte = (time.perf_counter() - t0) * 1000
                events.append(line.split(":", 1)[1].strip())
    total = (time.perf_counter() - t0) * 1000
    check("agent run completes", "done" in events and "options" in events, f"first event {first_byte or 0:.0f}ms, total {total:.0f}ms, events={len(events)}")

    res, ms = timed("POST", "/api/interpret", json={"revision": base_rev, "text": "The truck is 35 minutes late."})
    body = res.json() if res.status_code == 200 else {}
    check("incident interpretation", res.status_code == 200 and len(body.get("incidents", [])) == 1, f"{ms:.0f}ms live={body.get('live')}")

    print(f"\n{len(failures)} failure(s)" if failures else "\nAll checks passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "https://ripple-room-five.vercel.app"))
