"""Regenerate apps/web/src/test/fixtures.json from the real API (run from services/api).

    uv run python ../../scripts/freeze_web_fixtures.py

Web unit tests consume genuine server payloads instead of hand-written mocks.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402


def main() -> None:
    client = TestClient(create_app())
    demo = client.get("/api/demo").json()
    shocked = client.post("/api/shock", json={"revision": demo["initial"]["revision"], "preset_id": "truck-delay-35"}).json()
    search = client.post("/api/search", json={"revision": shocked["revision"]}).json()
    out = ROOT / "apps" / "web" / "src" / "test" / "fixtures.json"
    out.write_text(json.dumps({"demo": demo, "shocked": shocked, "search": search}), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
