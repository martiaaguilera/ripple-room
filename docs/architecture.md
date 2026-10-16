# Architecture

Ripple Room is a stateless FastAPI service (scheduling truth + agent orchestration) behind a static
Next.js app, deployed as two Vercel Services on one domain. The only runtime AI is NVIDIA Nemotron 3
Super served by Nebius Token Factory.

```text
Browser (Next.js static export, TypeScript)
│  holds immutable, content-hashed revisions; undo/reset = client history of verified revisions
│  venue scene, ripple map, timeline: all rendered from server results, nothing recomputed
▼
FastAPI  (services/api, stateless, one process per request)
├─ /api/demo        scenario + presets + verified baseline
├─ /api/shock       new revision; impact report (right-shift, causal BFS waves, slack, driving path)
├─ /api/interpret   free text → typed incidents + preferences (Nemotron, one forced tool call) → human confirms
├─ /api/recover     SSE stream of the bounded agent loop  ─────────────┐
├─ /api/search      playbook search (deterministic fallback, "no AI")    │
├─ /api/evaluate    one patch → verdict                                  │
├─ /api/apply       re-verifies the plan from scratch; stale → 409       │
└─ /api/notice      who must be told what, by when (deterministic diff)  │
                                                                         ▼
                         Agent loop (app/agent)  perceive → diagnose → plan → verify → revise → present
                         tools: get_situation · inspect_task · list_interventions · evaluate_patch · submit_options
                         budgets: model calls, verifier checks, tokens, wall time; last call forces submit_options
                                │ OpenAI-compatible HTTPS (server-side key)
                                ▼
                         Nebius Token Factory  →  nvidia/nemotron-3-super-120b-a12b
                                │ typed patch (allow-listed actions, extra fields rejected)
                                ▼
                         Verifier (app/solver/evaluate.py)
                         static patch checks → CP-SAT (hard deadline) → independent validator → explanation
                         infeasible → relaxed solve: best achievable time + why (chain not touched / not enough / worse)
```

## Module map (services/api/app)

| Module | Responsibility |
|---|---|
| `domain/models.py` | Scenario, tasks, resources, shocks, intervention union (`activate_resource`, `compress_task`, `defer_task`, `assign_resource`, `pin_start`, `add_helper`) |
| `domain/effective.py` | Compiles scenario + shocks + patch into the one problem both solver and validator use |
| `domain/validate.py` | Independent plan validator (no OR-Tools) |
| `domain/propagate.py`, `domain/analysis.py` | Do-nothing right-shift, impact statuses (at risk / delayed / breach / blocked), causal waves, slack, binding constraints, driving path, cost, diffs |
| `domain/preferences.py`, `domain/ranking.py` | Soft preferences and the deterministic, recomputable ranking |
| `domain/notice.py` | Crew change notice |
| `solver/cpsat.py` | CP-SAT model (single worker, fixed seed, deterministic time limit) |
| `solver/evaluate.py` | Authoritative verdict + plain-language near-miss explanations |
| `solver/search.py`, `solver/greedy.py` | Playbook search, extended oracle, greedy baseline |
| `agent/*` | Tools, prompts, runner, NL interpretation |
| `providers/*` | Nebius adapter (retries, error mapping, request ids), labelled mock |
| `evaluation/*` | 20-case harness and report |

## Invariants

1. Solver and validator share one compiled problem; every solver plan is re-validated; disagreement raises.
2. Only `verified` evaluations can be options. `unknown` (timeout) is never shown as feasible.
3. The model never writes state; it proposes patches. The human applies; the server re-verifies on apply.
4. Preferences are soft: they rank verified options and flag breaches, never relax hard constraints.
5. Raw model reasoning never leaves the server; events carry `reasoning_returned: bool` only.
6. Mock mode is labelled everywhere and never used silently when live mode is configured.

## Deployment

`vercel.json` defines two services (`web`: Next.js static export, `api`: FastAPI) with `/api/*` routed to
the API. Secrets live only in Vercel environment variables. `scripts/check_judge_demo.py <url>` runs
the full judge path against any deployment (page, health, shock, search, apply + stale rejection,
streamed agent run, interpretation).
