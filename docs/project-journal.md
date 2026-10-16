# Project journal

Status legend: **PROVEN** (run and observed) · **NOT VERIFIED** · **BLOCKED** (needs owner)

## 2026-10-16 — Day 1: discovery + truth engine

### Done
- Read full owner brief; research agents produced `docs/research/{rules-snapshot,api-capabilities,competition,hosting}.md`.
- Environment: Windows 11, git 2.52, node 24.15, npm 11.12, Python 3.13.12, uv 0.12.17, gh 2.100 (authed as
  `martiaaguilera`). Missing: docker, gitleaks. pnpm shim broken → use npm.
- Truth engine (services/api): domain model, problem compiler, independent validator, right-shift propagation,
  impact analysis (at-risk vs delayed vs breach vs blocked, causal waves, binding constraints, slack, driving path),
  CP-SAT solver, evaluation pipeline, deterministic intervention search. **PROVEN:** 47 tests pass, ruff + mypy strict clean.
- Fixture `signal-night-v1` outcomes **PROVEN** by tests (see ADR-001 table).
- ADR-001 scope, ADR-002 stateless API / Vercel-first.

### Blockers / owner actions
| # | Item | Status |
|---|---|---|
| 1 | Nebius Token Factory account + API key (signup requires bank card per docs; apply promo `NEBIUS-DEVPOST-GLOBAL26`, Builders Program $25) | **BLOCKED** (owner) |
| 2 | Hosting account: Vercel Hobby (GitHub login) for judge demo | **BLOCKED** (owner) |
| 3 | Confirm public GitHub repo name/visibility + Devpost username | pending |

### Risk ledger
| Risk | P | I | Mitigation | Next check |
|---|---|---|---|---|
| Nebius credits/key not available | M | Critical | Mock harness labelled; ask owner day 1 | 17 Oct |
| Wrong model ID / tool-calling quirks | M | High | IDs in env; `smoke_nebius.py --list-models`; JSON-mode fallback | first key |
| OR-Tools cold start / size on Vercel | M | High | Smoke deploy early; Render Docker fallback | after account |
| Credits exhausted before 15 Dec | L-M | High | Super not Ultra by default; per-run caps; cache labelled | weekly |
| Fixture outcome drift | L | High | Regression tests pin properties | every commit |
| Competitor overlap (LLM+CP-SAT exists) | H | Med | Differentiate on cascade UX, visible rejection, change notice; no novelty claims | 25 Oct |
| Name collision "Ripple" | M | Low | Owner decision | before README final |

### Later on day 1 (same session)
- Stateless API (`/api/demo|shock|view|evaluate|search|apply`), typed errors, stale/tampered revision rejection.
- Agent: Nebius adapter (httpx, bounded jittered retries, error mapping, request-id capture), labelled scripted mock,
  strict tool boundary, budgeted loop, SSE `/api/recover`. `scripts/smoke_nebius.py` ready (exits 2 without key).
- Web: Next 16.4 static export; stage-plot canvas with causal ripple from server BFS waves, synced timeline, doors
  board, incident deck, inspector, recovery panel with real trace, option preview vs do-nothing plan, apply/undo/reset,
  JSON report export. OpenAPI-generated TS types.
- **PROVEN:** backend 88 tests + ruff + mypy strict; web 14 Vitest + tsc + eslint; Playwright 10/10 (desktop 1440x900 +
  mobile 390x844) against FastAPI serving the static build on one origin, mock agent. Screenshots inspected.
- CI workflow written (`.github/workflows/ci.yml`) — **NOT VERIFIED** (repo not pushed).
- Claude-in-Chrome extension not connected; visual QA done with Playwright screenshots instead.

### Next three actions
1. Owner: Nebius key → run `smoke_nebius.py --list-models --probe`, pin model IDs, run first live recovery, record evidence.
2. Landing section (P0-A) + "How it works" panel; evaluation harness (20 seeded cases, agent vs search vs greedy).
3. Owner: Vercel account → smoke-deploy OR-Tools on Vercel Python; fallback Render Docker.
