# Ripple Room

**See the chain reaction. Fix the day.**

When one thing goes wrong at a live event, Ripple Room shows everything it affects and helps you find a
recovery plan you can trust: **NVIDIA Nemotron on Nebius Token Factory proposes, an OR-Tools CP-SAT
verifier proves, and a human approves.**

- **Live demo:** https://ripple-room-five.vercel.app (no login)
- **Video:** _to be added_
- Built for the Nebius x NVIDIA Global AI Hackathon 2026, track *Best Apps and Agents*.
- The event (Signal Night at Bay Hall), people and costs are fictional. "Ripple Room" is a working title,
  unrelated to Ripple Labs / XRP or other projects named "Ripple".

## What you can do in 60 seconds
1. Watch the day run: an illustrative venue scene driven by the plan's real times, doors at 18:00.
2. Press **"What if the truck arrives 35 minutes late?"** (or describe an incident in your own words).
   The delay ripples through the dependency map; the header explains it: *doors would be ready at
   18:15, 15 minutes late.*
3. Set what matters (guest experience, spend, crew stability, budget, spare time) and press
   **Find recovery options**. Watch Nemotron's proposals land on the verifier board — kept or
   rejected, each with a reason.
4. Preview an option (the whole day replays with it), approve it, and get the list of who needs to be
   told what, by when. Undo is one click.

## How it works
```text
Browser ──▶ FastAPI (stateless; client holds content-hashed revisions)
             ├─ impact: do-nothing propagation, causal waves, slack, driving path
             ├─ interpret: free text → typed incidents + priorities (Nemotron, one forced tool call) → human confirms
             ├─ recover (SSE): bounded agent loop ───▶ Nebius Token Factory ─▶ nvidia/nemotron-3-super-120b-a12b
             │     tools: get_situation · inspect_task · list_interventions · evaluate_patch · submit_options
             │     every proposal ─▶ verifier: patch checks → CP-SAT → independent validator → explanation
             ├─ playbook search (deterministic, labelled "no AI") and verified alternatives in the same pool
             └─ apply: re-verifies from scratch; stale revision → 409; change notice
```
- **The model never edits the plan.** It calls five allow-listed tools with strictly validated
  arguments. Only patches the verifier accepts can become options; a timeout is "unknown", never green.
- **Rejections are explained** from the solver's own results: *"Bringing in the backup AV technician
  does not touch what sets the doors time…"*, *"…makes things worse than doing nothing (18:15)"*.
- **Priorities are soft, deadlines are hard.** Options are ranked by preference breaches, then a
  recomputable penalty breakdown shown on each card.
- **Hybrid by design.** Verified playbook options are always in the pool, so the system never ranks
  below the deterministic playbook; options are labelled by origin (Nemotron / playbook / no change).
- Raw model reasoning never leaves the server.

**Claude Code was the development tool. At runtime the only AI is NVIDIA Nemotron served by Nebius
Token Factory.**

## Measured results (live Nemotron 3 Super, 20 fixed cases, one run per version)
| | Agent v2 | Agent v4 | Playbook search | Greedy |
|---|---|---|---|---|
| Verified recovery found when one exists | 16/17 | 16/17 | 15/17 | 15/17 |
| Honest "none" when none exists | 3/3 | 3/3 | 3/3 | 3/3 |
| Options failing independent re-validation | 0 | 0 | 0 | 0 |
| Best option equals the exhaustive oracle's | 9/17 | 7/17 | 8/17 | 6/17 |
| Median latency | 19.5 s | 18.4 s | 0.08 s | 0.11 s |
| Cost of the 20 runs (list price) | $0.24 | $0.22 | 0 | 0 |

What this does and does not show:
- The agent found a recovery in c19 (setup team away) that both deterministic baselines miss, using
  a helper plus a line check — see `docs/evaluation/CASES-c19-c09.md`.
- It does **not** show better overall plan quality than the deterministic playbook; samples are tiny
  (one run each), and combined three-change fixes (c09) are still missed.
- Full data: `docs/evaluation/`. The current agent (v5, hybrid) has not yet been re-measured live.

## Run locally
Prerequisites: Python 3.13 with [uv](https://docs.astral.sh/uv/), Node 24.
```bash
cd services/api && uv sync && uv run uvicorn app.main:app --port 8000          # mock agent by default
cd apps/web && npm ci && NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev  # http://localhost:3000
```
Live mode: copy `.env.example` to `services/api/.env`, set `AI_MODE=live` and `NEBIUS_API_KEY`, then
`uv run python ../../scripts/smoke_nebius.py --probe`. Spend controls and the kill switch are
documented in `docs/operations.md`.

## Tests
```bash
cd services/api && uv run pytest -q && uv run ruff check . && uv run mypy app
cd apps/web && npm run typecheck && npm run lint && npm test && npm run build && npm run e2e
uv run python scripts/check_judge_demo.py https://ripple-room-five.vercel.app   # production judge path (makes live calls)
```

## Repository map
`services/api/app/domain` scheduling domain · `app/solver` CP-SAT, verifier, playbook search, greedy ·
`app/agent` tools, prompts, loop, interpretation · `app/providers` Nebius adapter + labelled mock ·
`app/evaluation` 20-case harness · `apps/web` Next.js app · `docs/` architecture, decisions,
evaluation, operations, journal.

## License
MIT — see [LICENSE](LICENSE).
