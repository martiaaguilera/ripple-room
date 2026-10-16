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

### Next three actions
1. Stateless FastAPI layer (`/api/demo`, `/impact`, `/evaluate`, `/search`, `/apply`) + API tests.
2. Nebius provider adapter + mock provider + bounded agent loop with SSE; `scripts/smoke_nebius.py`.
3. Next.js app: operations canvas + timeline vertical slice wired to the API.
