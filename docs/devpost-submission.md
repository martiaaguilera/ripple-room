# Devpost submission draft (owner reviews and submits)

Every number below comes from `docs/evaluation/` or `docs/evidence/`. Paste each section into the
matching Devpost field.

**Title:** Ripple Room: See the chain reaction. Fix the day.

**Tagline:** NVIDIA Nemotron on Nebius Token Factory proposes fixes for a disrupted event day. A
constraint solver checks every fix before a human approves it.

**Track:** Best Apps and Agents

**Links**
- Live demo: https://ripple-room-five.vercel.app (no login; NVIDIA Nemotron 3 Super via Nebius Token Factory)
- Code: https://github.com/martiaaguilera/ripple-room (MIT licence)
- Video: _(YouTube URL, public, under 3 minutes; add after recording)_

**Built with:** NVIDIA Nemotron 3 Super (`nvidia/nemotron-3-super-120b-a12b`), Nebius Token Factory,
Google OR-Tools CP-SAT, Python, FastAPI, Pydantic, Next.js, TypeScript, Tailwind CSS, Playwright, Vercel.

**New project:** built from scratch during the submission period (first commit 16 Oct 2026). The event,
people and costs in the demo are fictional.

## Inspiration
A small live event runs on one fixed opening time and a set of jobs that depend on each other. When
the truck is late, the coordinator has to work out, fast and often in their head, what else slips,
whether doors still open on time, and what to change. A spreadsheet shows the plan. It does not show
the chain reaction. We also wanted an AI helper whose suggestions a coordinator can trust, so we made
sure no suggestion reaches the user unless a solver has checked it.

## What it does
- Shows a fictional one-night event (Signal Night at Bay Hall) as a venue scene, a dependency map and
  a timeline. All three come from the same scheduling engine.
- Lets you break the plan with a prepared incident ("the truck arrives 35 minutes late") or in your
  own words. Nemotron turns your words into typed incidents and priorities. You confirm before
  anything changes.
- Traces the consequences: which jobs are delayed, which are only at risk, and when doors would be
  ready. For the 35-minute truck delay: doors ready at 18:15 instead of 18:00.
- Runs a bounded agent. Nemotron reads the situation through tools and proposes typed fixes: bring in
  standby crew or kit, shorten a task by a chosen amount, defer optional work, add a helper, or
  resequence. An OR-Tools CP-SAT verifier checks each fix. Rejected fixes come back with a reason
  (for example "makes things worse than doing nothing") and Nemotron revises.
- Ranks the verified options by your priorities (guest experience, spend, crew stability, budget cap,
  spare time, tasks not to touch). Each card shows a penalty breakdown you can recompute. You can
  preview any option on the whole day.
- Changes the plan only when you approve. Then it lists who needs to be told what, and by when.
  Undo is one click.
- Says "no verified recovery" when there is none. In a live run with a 90-minute truck breakdown,
  Nemotron submitted zero options and named 18:30 as the earliest possible time.

## How we built it
- **Runtime AI:** `nvidia/nemotron-3-super-120b-a12b` on **Nebius Token Factory**, through its
  OpenAI-compatible API with native tool calling. It is called only from the server. Two uses:
  (1) the recovery agent's tool loop, with five allow-listed tools (`get_situation`, `inspect_task`,
  `list_interventions`, `evaluate_patch`, `submit_options`); (2) turning free text into typed incidents
  and priorities with one forced tool call. Raw model reasoning is never shown or stored.
- **How Token Factory helped:** the OpenAI-compatible endpoint worked with a plain HTTP client. The
  verbose model list (`GET /v1/models?verbose=true`) gave us model IDs, prices, context length and
  supported features in one call, so we picked the model and computed cost per run from data. Two
  full 20-case benchmarks cost $0.2435 and $0.2207 at list price.
- **Verifier:** Python, FastAPI, Pydantic v2, OR-Tools CP-SAT. Every solver plan is re-checked by an
  independent validator. A timeout is reported as "unknown", never as feasible.
- **Hybrid design:** verified options from a deterministic playbook search always join the pool, and
  every option is labelled by origin (Nemotron, playbook, or no change).
- **Front end:** Next.js (static export), TypeScript, Tailwind CSS, hand-built SVG scene, ripple map and
  timeline. API types are generated from the backend's OpenAPI schema.
- **Deployment:** Vercel. The API is stateless: the browser holds content-hashed revisions, and the
  server re-verifies any plan on apply. A stale revision gets HTTP 409.
- **Quality:** backend tests, web unit tests, Playwright journeys on desktop and mobile, CI with a
  full-history secret scan, and a script that checks the full judge path on production.
- **Spend controls:** a kill switch, daily token and run budgets, and per-IP limits.
- Claude Code was our development tool. Claude is not used at runtime.

## Challenges
- **Making model output safe to act on.** We used a strict tool boundary (allow-listed actions, extra
  fields rejected), a verifier that is the only authority on feasibility, and re-verification on apply.
- **Giving the agent real room to help.** Early versions could only restrict the solver, so the agent
  was picking from a menu. Adding helpers and graded shortening gave it options the playbook does
  not have. The evaluation shows where that pays off and where it does not.
- **Explaining "no".** The verifier explains near misses from its own results: "does not touch what
  sets the doors time", "helps but not enough", "makes things worse than doing nothing".
- **Measuring honestly.** We compared the agent against a deterministic playbook search, a greedy
  heuristic and an exhaustive oracle on the same 20 cases, and published where the agent loses.

## Accomplishments that we're proud of
- **Live end to end.** 40 benchmark runs on live Nemotron 3 Super (two versions × 20 cases) made 283
  model calls. No run ended with an error.
- **Nothing unverified reaches the user.** Across both runs and all four methods, 0 options failed
  independent re-validation.
- **Honest "none".** In the 3 cases with no possible recovery, every method said so (3/3).
- **One recovery outside the playbook.** In case c19 (setup team away 14:30–15:30), the playbook search
  and the greedy heuristic found no verified recovery. Nemotron found a verified, zero-cost one in
  both runs: a free person helps rig the stage, plus a shorter line check. Its score matched the
  exhaustive oracle's best. In the second run it needed 2 verifier checks; the oracle tried 123
  combinations.
- **A reliability fix that worked.** Forcing `submit_options` on the last allowed model call cut runs
  that ended by running out of budget from 7/20 to 0/20. p95 latency fell from 49.3 s to 33.4 s.
- **Cheap to run.** About one US cent per recovery: $0.2207 for 20 runs at list price.

## What we learned
- **Precise tool schemas matter.** With a loose schema, Nemotron 3 Super invented field names
  (`action`, `resource`). With explicit enum-typed schemas, all 19 tool calls in our three recorded
  agent runs were valid.
- **Reliability is not quality.** The prompt change that fixed budget exhaustion did not improve the
  options: best option equal to the oracle's went from 9/17 to 7/17. With one run per version, we read
  that as "no improvement", not as a real drop.
- **The agent is not better overall than the playbook.** On best-option quality, the agent scored 9/17
  and 7/17; the playbook search scored 8/17. The agent found a recovery in one more case (16/17 vs 15/17).
- **The agent stops early.** In the second run it made 3.5 verifier checks per case on average. Under
  "protect the guests" priorities it often missed a free fix. That is why verified playbook options
  are now always in the pool.
- **Three-change fixes are still hard.** Case c09 (truck 65 minutes late) needs three changes at once.
  No agent run, no playbook search and no greedy run found it; only the exhaustive oracle did.
- **A verifier changes the trust question.** Because nothing reaches the user unchecked, we could give
  the model more ways to act without making the product less safe.

## What's next
- Measure the current hybrid agent (v5) live on the same 20 cases, with several runs per case so we
  can see run-to-run variation. It has not been measured live yet.
- Help the agent combine fixes (the c09 gap) and explore further before stopping.
- Import a real run-of-show sheet instead of a fixed fictional scenario.
- Multi-day productions, shared sessions for a team, and sending the change notice through calendar
  or messaging tools.

## Feedback on Nebius and NVIDIA tools
Paste from `docs/feedback-nebius-nvidia.md`.
