# Operations: inference spend and the December judging period

## What protects spend today (application side)
| Control | Default | Where |
|---|---|---|
| Kill switch: no model calls at all | `AI_KILL_SWITCH=false` | Vercel env var → redeploy |
| Daily token budget per process (UTC day) | `AI_DAILY_TOKEN_BUDGET=1500000` | `app/core/budget.py` |
| Daily model-backed requests per process | `AI_DAILY_RUN_BUDGET=60` | same |
| Daily model-backed requests per client IP | `AI_PER_IP_DAILY_RUNS=12` | same |
| Per-minute rate per client IP | `RECOVER_RATE_PER_MINUTE=3` | `app/core/ratelimit.py` |
| Concurrent agent runs per process | `RECOVER_MAX_CONCURRENT=3` | same |
| Per run: model calls / verifier checks / tokens / seconds | 8 / 6 / 80,000 / 90 | `AGENT_*` env vars |
| Client IP taken from platform headers (`x-vercel-forwarded-for`, `x-real-ip`), not client-supplied `x-forwarded-for` | – | `agent_routes._client_key` |

Tokens are counted on every model call, so a client that disconnects mid-run is still charged to the
budget. When a budget is exhausted the API answers `503 AI_BUDGET_EXHAUSTED`, the UI says so and the
deterministic playbook search keeps working. Mock mode never touches the budget.

## What these controls do NOT guarantee
- **They are not a provider-level spending cap.** Counters live in process memory: each Vercel
  instance has its own, and a cold start resets them. Worst case per UTC day ≈ (instances) × budget.
- Upper bound per instance per day at the default budget: 1.5M tokens × $0.90/M (completion price,
  the more expensive side) ≈ **$1.35**. Measured runs are prompt-heavy: ~30k tokens ≈ **$0.011** per
  recovery; 60 runs ≈ **$0.66/day per instance**.
- Only Nebius-side settings (or the payment method on the account) can make charges impossible.

## Measured cost so far (list prices, prompt $0.30/M, completion $0.90/M)
- Two live 20-case evaluations: $0.2435 + $0.2207.
- Smoke tests and ~5 interactive live runs: well under $0.10.

## Account state
Account balances and trial details are kept out of the public repo. The owner checks them in the
Nebius console. Two rules hold regardless: keep the app's lifetime cap below the remaining credits, and
assume usage can continue on a linked card once credits reach zero.

## Running the live AI for a while without uncontrolled charges (owner decisions)
1. **Check Nebius-side controls first** (owner): whether the account offers a spending limit, budget
   alerts, or a setting that stops usage when credits run out. The dashboard warns that usage may
   continue on the linked card once the balance reaches zero — treat that as the default.
2. **Lower the daily budget**, e.g. `AI_DAILY_TOKEN_BUDGET=400000` and `AI_DAILY_RUN_BUDGET=15`
   → upper bound ≈ $0.36/day per instance.
3. **Emergency stop:** set `AI_KILL_SWITCH=true` in Vercel and redeploy (≈1 minute). The app stays
   usable (incidents, ripple, playbook search, apply/undo) but makes no model calls.
4. Never enable paid billing, buy credits or change billing preferences from this project; those are
   owner actions in the Nebius console.

## After the hackathon (not submitted)
The project was not submitted, so the post-deadline freeze does not apply. With no judges to serve,
the public demo does not need live AI:
1. **Default:** `AI_KILL_SWITCH=true` in Vercel (Production), then redeploy. `GET /api/health` should
   show `"status":"paused"`. The app stays usable without model calls.
2. **No key, no spend:** delete the Nebius API key in the Nebius console and remove `NEBIUS_API_KEY`
   from Vercel. Create a new key only when a live demo is needed, then delete it again.
3. To show the live agent: create a key, set it in Vercel, set `AI_KILL_SWITCH=false`, redeploy, demo,
   then undo all three.

## Runbook
- Health: `GET /api/health` → `ai.status` is `live`, `mock`, `paused`, `budget_exhausted` or `unconfigured`.
- Full judge path: `uv run python scripts/check_judge_demo.py https://ripple-room-five.vercel.app`
  (makes one live agent run and one interpretation call).
- Logs: Vercel dashboard → Logs (Hobby keeps about an hour). Agent events log model id, request id,
  latency and token usage; never prompts' secrets or raw reasoning.
