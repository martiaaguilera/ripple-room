# Ripple Room — working notes for Claude Code

**North star:** a disrupted one-day event plan becomes a living graph; NVIDIA Nemotron on
Nebius Token Factory proposes typed intervention patches; a deterministic CP-SAT verifier is
the only authority on feasibility; the human compares and applies. Truthful working
functionality beats visual flourish. Hackathon: Nebius x NVIDIA 2026, track *Best Apps and
Agents*, deadline **30 Oct 2026 18:00 Europe/Madrid** (target submit 29 Oct).

Read on demand (do not paste into context wholesale):
- `docs/project-journal.md` — status, blockers, next actions. **Update it at the end of every work unit.**
- `docs/decisions/` — ADRs. `docs/research/` — rules snapshot, API capabilities, competition, hosting.
- `docs/architecture.md` — request flow and module map.

## Layout
- `services/api/` — Python 3.13, FastAPI, Pydantic v2, OR-Tools CP-SAT (uv-managed).
  - `app/domain/` pure domain: `models` (scenario, shocks, interventions), `effective` (compile scenario+shocks+patch),
    `validate` (independent plan validator, no OR-Tools), `propagate` (right-shift impact), `analysis` (slack, binding
    constraints, impact report, cost, diffs), `graph`.
  - `app/solver/` `cpsat` (model), `evaluate` (authoritative verdict pipeline), `search` (deterministic menu search).
  - `app/fixtures/` versioned fictional scenario `signal_night_v1.json` + shock presets.
  - `app/agent/`, `app/providers/` — bounded agent loop, Nebius adapter + labelled mock.
- `apps/web/` — Next.js (App Router, static export), TypeScript strict, Tailwind.

## Commands (run from `services/api`)
- Tests: `uv run pytest -q` · Lint: `uv run ruff check . && uv run ruff format --check .` · Types: `uv run mypy app`
- Dev server: `uv run uvicorn app.main:app --reload --port 8000`
- Web (from `apps/web`): `npm run dev`, `npm run build`, `npm run lint`, `npm run typecheck`, `npm test`

## Invariants (never break)
1. Times are integer minutes since scenario epoch (00:00 local on scenario date, tz in scenario). Money is integer cents.
2. Solver and validator consume the same `EffectiveProblem`; every solver plan is re-validated; a validator rejection
   raises `VerifierInconsistencyError` — it is never shown as feasible.
3. Statuses: `verified` / `infeasible` / `rejected` / `unknown`. UNKNOWN (timeout) is never green. FEASIBLE is not "optimal".
4. The LLM only proposes `Patch` objects (allowlisted discriminated union, `extra="forbid"`). It never writes state.
5. Server is stateless: the client holds content-hashed revision state; the server re-verifies any plan on apply and
   rejects stale revisions (hash mismatch → 409).
6. AI mode is always visible. Mock output is labelled "simulated" everywhere; never presented as live Nemotron output.
7. No secrets in code, logs, traces or responses. `NEBIUS_API_KEY` is server-side only.
8. Demo data is fictional; never imply real customers, incidents or measured ROI.

## Definition of Done for a change
Code + tests pass + ruff/mypy (and web lint/typecheck) clean + behaviour verified (CLI, test, or browser screenshot)
+ journal updated + concise conventional commit. Say "NOT VERIFIED" for anything not actually run.

## Conventions
- Small single-purpose modules; pure functions in `domain/`; no business logic in routers or JSX.
- Pydantic at API boundaries; Zod at the web boundary. No `any`, no silent excepts, no placeholder TODOs.
- Platform is Windows (Git Bash + PowerShell). Set `PYTHONIOENCODING=utf-8` when printing non-ASCII from scripts.
- Do not publish, deploy, spend money, or submit to Devpost without explicit owner approval.
