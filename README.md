# Ripple Room

**See the chain reaction. Fix the day.**

Ripple Room is an operations simulator for small live events. A one-day production plan is shown
as a living stage plot and timeline. Break it with a realistic incident (a late truck, a missing
technician) and watch the delay travel through the dependencies to the doors-open deadline. Then an
NVIDIA Nemotron agent running on **Nebius Token Factory** proposes recovery patches, and a
deterministic **OR-Tools CP-SAT** verifier decides which of them actually work. You compare the
verified options and choose what to apply. Nothing changes without you, and impossible situations
are reported as impossible.

> Built for the Nebius x NVIDIA Global AI Hackathon 2026 (track: Best Apps and Agents).
> The scenario, venue, people and costs are fictional test data. "Ripple Room" is a working title,
> unrelated to Ripple Labs / XRP or to other projects named "Ripple".

## Status (honest, updated 16 Oct 2026, evening)

| Area | State |
|---|---|
| Constraint engine, impact analysis, verifier | Working, 88 backend tests |
| Stateless API (shock, evaluate, search, apply) | Working |
| Agent loop, tool boundary, Nebius adapter | Working; unit-tested against a scripted mock and a faked HTTP transport |
| **Live Nemotron calls on Nebius Token Factory** | **Verified 16 Oct 2026** with `nvidia/nemotron-3-super-120b-a12b`: native tool calling, full recovery runs with verifier rejections and revisions (traces in `docs/evidence/`) |
| Web control room | Working; 14 unit tests, 10 Playwright E2E runs (desktop + mobile) |
| Public deployment | Not deployed yet |

When the server runs in mock mode (CI, local dev without a key) the UI labels every run "Simulated agent, no model calls".

## How it works

```text
Browser (Next.js static export)
  │  holds immutable, content-hashed revisions (undo/reset are client history)
  ▼
FastAPI (stateless)
  ├─ impact: right-shift propagation + causal waves (what slips, what is merely at risk)
  ├─ evaluate: patch checks → CP-SAT → independent validator → explanation facts
  ├─ search: deterministic menu search (labelled fallback, "no AI")
  ├─ apply: re-verifies the plan from scratch, rejects stale revisions (409)
  └─ recover (SSE): bounded agent loop
        perceive → diagnose → plan → verify → revise → present
        Nemotron on Nebius Token Factory proposes typed patches;
        only patches the verifier accepts can be shown as options.
```

- **The model never edits state.** It can call five allow-listed tools with strictly validated
  arguments (`get_situation`, `inspect_task`, `list_interventions`, `evaluate_patch`,
  `submit_options`). Unknown tools, extra fields and unverified submissions are rejected.
- **The solver is never trusted blindly either.** Every CP-SAT plan is re-checked by a plain-Python
  validator. A timeout is reported as *unknown*, never as feasible.
- **Why AI at all?** In this small scenario an exhaustive search finds the feasible patches in
  about 40 ms, so the model is not needed for raw search. It is used for what a solver cannot do:
  reading the coordinator's priorities in plain language, composing patches beyond the menu
  (resequencing, reassignment), revising after verifier feedback, and explaining trade-offs.
  See `docs/decisions/ADR-001-product-scope.md`.

**Claude Code is the development tool. At runtime the only AI is NVIDIA Nemotron served by Nebius
Token Factory.**

## Run locally

Prerequisites: Python 3.13 with [uv](https://docs.astral.sh/uv/), Node 24.

```bash
# API (mock agent by default)
cd services/api
uv sync
uv run uvicorn app.main:app --port 8000

# Web (second terminal)
cd apps/web
npm ci
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev   # http://localhost:3000
```

Live mode: copy `.env.example` to `services/api/.env`, set `AI_MODE=live` and `NEBIUS_API_KEY`, then
verify with `uv run python ../../scripts/smoke_nebius.py --list-models --probe` (writes sanitized
evidence to `docs/evidence/`). The key stays on the server.

## Tests

```bash
cd services/api && uv run pytest -q && uv run ruff check . && uv run mypy app
cd apps/web && npm run typecheck && npm run lint && npm test
cd apps/web && npm run build && npm run e2e     # FastAPI serves the static export on one origin
```

## Repository map

- `services/api/app/domain` pure scheduling domain, `app/solver` CP-SAT + verifier + search,
  `app/agent` tools/prompts/loop, `app/providers` Nebius adapter and labelled mock.
- `apps/web` Next.js app; `src/lib/api/schema.d.ts` is generated from the API's OpenAPI schema.
- `docs/` research, decisions (ADRs), project journal.

## License

MIT, see [LICENSE](LICENSE).
