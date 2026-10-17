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

### Live Nebius verification (16 Oct, ~23:15 CEST)
- Owner supplied key (pasted in chat → stored only in gitignored `services/api/.env`; recommend rotation after hackathon).
- **PROVEN** `GET /v1/models?verbose=true`: 28 models; NVIDIA: `nvidia/nemotron-3-super-120b-a12b` (256K ctx, $0.30/$0.90 per 1M, tools+reasoning, listed in us-central1; corrected 18 Oct), `nvidia/Nemotron-3-Ultra-550b-a55b` (us-central1 only, $1/$3), `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, `nvidia/Nemotron-3_5-Lightning` (both $0.06/$0.24).
- **PROVEN** Super: plain chat 649 ms; native tool call 933 ms; `reasoning_content` field present.
- **PROVEN** 3 live agent runs via real loop (`scripts/run_live_recovery.py`):
  - truck+35, "zero spend": 6 calls, 11.1 s, 21,978 tok; c2 rejected by verifier then revised; 2 verified options (both compress; trolley not explored).
  - truck+35, "guest first": 7 calls, 16.6 s, 27,432 tok; found trolley (€35) + 2 compress options; ranked a guest-impacting option first (priority-alignment miss → eval harness).
  - truck+90: model submitted 0 options citing the 18:30 bound (honest infeasibility).
- **PROVEN** UI live run (AV out, zero spend) at localhost with real request ids in trace.

### Next three actions
1. ~~Owner: Nebius key~~ DONE. Next: evaluation harness → run `smoke_nebius.py --list-models --probe`, pin model IDs, run first live recovery, record evidence.
2. Landing section (P0-A) + "How it works" panel; evaluation harness (20 seeded cases, agent vs search vs greedy).
3. Owner: Vercel account → smoke-deploy OR-Tools on Vercel Python; fallback Render Docker.

## 2026-10-17 — Priorities, intake, evaluation harness, Visual 2.0 (milestone A), production

### Done (all PROVEN unless marked)
- Repo public at github.com/martiaaguilera/ripple-room (MIT). History rewritten before first push: commit emails → GitHub
  noreply; raw model reasoning stripped from evidence; gitleaks over full history in CI: no leaks. CI green (api, web+E2E, secrets).
- Raw model reasoning never leaves the server (events carry `reasoning_returned: bool`).
- Preferences: typed soft priorities + deterministic, recomputable ranking (breaches first, then penalty points);
  agent options ranked deterministically with the model's own rank kept for audit.
- `/api/interpret`: free text → typed incidents + preferences via one forced tool call, fully validated; confirm before apply.
- New levers: `add_helper` (event lead helping rig fixes truck +35 at €0, no guest impact) and graded compression;
  extended exhaustive oracle over the same action space.
- Verifier explains near misses deterministically ("does not touch what sets the doors time", "helps but not enough",
  "makes things worse than doing nothing").
- Evaluation harness: 20 fixed cases × {agent, playbook search, greedy, oracle}; mock run validated the harness only.
  Deterministic finding: the oracle finds recoveries in c09 (truck +65) and c19 (setup team out) that playbook search
  and greedy miss (needs the helper lever).
- Web: venue scene (illustrative, driven by plan times), scene narration from impact data, step guide, action column,
  incident intake with confirm card, priority controls, verifier board + verdict list, ranked option cards with penalty
  breakdown, tweened doors clock, sliding timeline bars, reduced-motion support. Playwright 16/16 (desktop + mobile).
- Production https://ripple-room-five.vercel.app (Vercel Services): `scripts/check_judge_demo.py` 11/11 PASS
  (page, health, shock, search, apply re-verification, stale 409, SSE agent stream, interpret); browser journey on prod:
  no console errors. **AI mode in production: mock** (no key configured there yet).

### Blockers (owner)
| # | Item | Status |
|---|---|---|
| 1 | Rotate exposed Nebius key (local `.env` still holds it), revoke old key | **BLOCKED** (owner) |
| 2 | Put the NEW key + `AI_MODE=live` in Vercel env vars, redeploy | **BLOCKED** (after 1) |
| 3 | Nebius trial "stop usage when it expires": confirm expiry date, promo credits applied, model access through 15 Dec | **BLOCKED** (owner) |
| 4 | Live 20-case evaluation (needs 1) | waiting |

### Next actions
1. After rotation: smoke test, live 20-case evaluation, live production check, revoke-verify old key.
2. Visual 2.0 B/C: ripple synced into the scene, side-by-side before/after card, mobile pass, a11y audit.
3. Crew change notice; README/architecture/Devpost drafts; demo storyboard.

## 2026-10-17 (night) — Key rotation, live production, evaluation v2/v4, spend guard

- **PROVEN** key rotation: new key works (smoke 473 ms / tool call 1.29 s); old key returns 401 (revoked);
  local stash deleted. Vercel production env set by owner; production `ai.status=live`.
- **PROVEN** production judge path live (`check_judge_demo.py` 11/11): agent run 20.8 s streamed (first event
  70 ms), interpretation 1.5 s. Browser journey on prod: 5 proposals, 3 verified, transport-crew helper rejected
  with "makes things worse" explanation.
- **PROVEN** live evaluations v2 ($0.2435) and v4 ($0.2207): see `docs/evaluation/COMPARISON-v2-v4.md`.
  v4 removes budget exhaustion (7/20 → 0/20); option quality not improved (9/17 → 7/17 best = oracle; one run each).
- Spend guard: kill switch, per-process daily token/run budgets, per-IP daily caps, unforgeable client IP,
  per-call token accounting; `docs/operations.md`. Deployed; CI green.
- c0 ("keep the current plan") is now always offered when slack absorbs the incident (fixes the c14 miss;
  live re-measurement paused).
- **Live inference testing paused by owner** after the v4 run. Do not run live evals or smoke tests without approval.

### Critical risks
| Risk | Status |
|---|---|
| Nebius trial ends before judging; card may be charged when credits hit $0 | **OPEN** (owner: Nebius-side limits, organiser credits) |
| App-side budget is per process, not a hard cap | Documented; lower budgets for December recommended |
| Agent option quality ≈ playbook search (7–9/17 vs 8/17) | Prioritised fixes in comparison doc; needs authorised re-measure |

## 2026-10-18 — Post-benchmark priorities (no live inference)

- Audit: production still `ai.status=live` (public can trigger paid calls within per-instance caps).
  Recommendation to owner: set `AI_KILL_SWITCH=true` in Vercel until Nebius-side billing limits are confirmed.
- Global quota (Upstash Redis REST, free tier, no card; atomic Lua reservation, daily + lifetime budgets,
  refunds, `AI_REQUIRE_GLOBAL_QUOTA` fail-closed). Implemented + tested with a fake store; **inactive** until the
  owner approves creating an Upstash database and sets its env vars.
- Agent v5 (hybrid): idle people on the critical chain, minutes-gained feedback, verified playbook options p1..pn
  always in the pool (incl. "reschedule only"), origin labels in UI/reports, c0 always offered. Mock harness:
  hybrid best = oracle 8/17 (= playbook floor). **Not measured live.**
- Docs: CASES-c19-c09.md (reproducible tests), README + Devpost draft with measured numbers only.
- Tests: 155 backend, 14 web unit, 16/16 E2E; CI green.

### Next measurable milestone (needs owner approval, ~$0.25)
Live v5 run of the 20 cases; report "system best = oracle" and "model-proposed best = oracle" separately.

## 2026-10-18 — QA: failure states, keyboard journey, spend-guard accounting (no live inference)

- New E2E `apps/web/e2e/resilience.spec.ts` (12 tests x desktop + mobile), all AI failures faked with
  `page.route`: health `paused` / `budget_exhausted` (AI button disabled with reason, playbook recovers + applies,
  zero `/api/recover|interpret` calls); recover 503 `AI_PAUSED` / `AI_BUDGET_EXHAUSTED` / `MODEL_UNAVAILABLE`
  (message shown, revision unchanged, no Nemotron attribution, playbook recovers); interpret 503; apply failing by
  network drop / 409 stale / 502 HTML (banner, plan + revision unchanged, retry succeeds); keyboard-only
  start → find → option card → Apply → Undo with `:focus-visible` ring checked at each step.
- **Bugs found and fixed** (`apps/web/src/lib/api/sse.ts`, proven by failing E2E first):
  1. A recovery stream that closed without a `done` event (proxy/platform timeout) left the UI "working /
     Waiting for the next step…" forever with Undo disabled. Now rejects with `STREAM_CUT` and a recoverable message.
  2. A network failure on `/api/recover` showed the raw browser text "Failed to fetch". Now the same plain-language
     message as every other endpoint.
- New unit tests `src/lib/api/sse.test.ts` (4) and backend `tests/test_guards_and_revisions.py` (17): real-older and
  double-submit stale revisions (409), tampered revision precedes stale check, edited plan → PLAN_INVALID,
  `/api/notice` happy path + tampered + infeasible + schema validation, mock runs never touch the budget,
  per-client cap and rate limit refuse before any model call, BUSY refunds the global reservation, live run
  (fake Nebius transport) charges actual tokens and refunds the rest, interpret failure keeps worst-case charge.
- **PROVEN:** backend 172 tests, ruff, ruff format, mypy clean; web 18 unit, eslint, tsc clean; Playwright 40/40
  (and 72/72 with `--repeat-each=3` on the new spec). E2E ran on port 8031 because 8012 was in use by another process.
- Observed, not changed (product decisions): after a 503 from `/api/recover` the AI badge still says live and the
  composer still credits Nemotron until reload; `_guard` counts a local run before the global reservation, so a
  refused global reservation or BUSY still consumes one local daily run.

## 2026-10-18 — Specialist agents (project agents + skills)

- Added `.claude/agents/` (ux-designer, qa-engineer, agent-engineer, security-auditor, submission-writer) and
  `.claude/skills/` (visual-qa, solver-audit, submission-audit). New agent types register on the next session;
  this session ran them as general-purpose agents that load their definition and skills.
- Merged results (all tests green, CI green):
  - agent-engineer: prompt v6 — coverage gaps + combinable near-misses fed back to the model (10 tests). Live effect NOT VERIFIED.
  - security-auditor: 16 findings; fixed the reproduced /recover slot leak and budget-drain paths, overshoot
    charging, solver-endpoint rate limit, interpretation accounting, size limits, headers (regression tests).
  - qa-engineer: 2 real UI bugs fixed (hung run on truncated stream; raw "Failed to fetch"); resilience E2E,
    keyboard journey, guard/revision tests. Totals: backend 191, web unit 20, E2E 40/40.
  - ux-designer: doors-gap header, legible verifier board, compact option cards, mobile copy/step guide.
  - submission-writer: Devpost draft, feedback write-up, README; corrected c19-v2 claim and Super's region.
- Production still `ai.status=live` at time of writing (kill switch not yet set by owner).

### Open
- Owner: AI_KILL_SWITCH, Upstash approval, Nebius billing limits, live v6 re-measure (~$0.08 targeted / ~$0.25 full), video.
- UX leftovers: venue scene scrolls sideways on phones; two-row top bar on phones.
