# Devpost submission draft (owner reviews and submits)

**Title:** Ripple Room — See the chain reaction. Fix the day.

**Tagline (one line):** A live operations simulator where NVIDIA Nemotron on Nebius proposes fixes for a
disrupted event day, and every fix is proven by a constraint solver before a human approves it.

**Track:** Best Apps and Agents

**Links**
- Live demo: https://ripple-room-five.vercel.app (no login; live NVIDIA Nemotron 3 Super via Nebius Token Factory)
- Code: https://github.com/martiaaguilera/ripple-room (MIT)
- Video: _(YouTube URL, public, < 3 min — to add after recording)_

## Inspiration
Small live events run on a fixed opening time and a dozen jobs that depend on each other. When a truck
is 35 minutes late, the coordinator has to work out — in minutes, often in their head — what else
slips, whether doors still open on time, and what to change. Spreadsheets show the plan; they don't
show the chain reaction.

## What it does
- Shows a fictional one-night event (Signal Night at Bay Hall) as a living venue scene, a dependency
  map and a timeline, all driven by the same scheduling engine.
- Lets you break the plan with a rehearsed incident or in your own words. Nemotron turns the words into
  structured incidents and priorities; you confirm before anything changes.
- Traces the consequences: which jobs are delayed, which are merely at risk, and when doors would be
  ready — explained in one plain sentence generated from the engine's results.
- Runs a bounded agent: Nemotron reads the situation through tools, proposes typed fixes (bring in
  standby crew or kit, shorten a task by a chosen amount, defer optional work, add a helper,
  resequence), and gets each one checked by an OR-Tools CP-SAT verifier. Rejected fixes come back with
  a reason ("…makes things worse: that crew is needed on unload AV gear…") and Nemotron revises.
- Ranks the verified options by your priorities (guest experience, spend, crew stability, budget cap,
  spare time, tasks not to touch) with a recomputable penalty breakdown, previews each option on the
  whole day, and applies it only when you approve — then lists who needs to be told what, by when.
- Says "no verified recovery" when there isn't one, with the earliest possible time.

## How we built it
- **Runtime AI:** `nvidia/nemotron-3-super-120b-a12b` on **Nebius Token Factory** (OpenAI-compatible
  API, native tool calling), called only from the server. Used for (1) the recovery agent's tool loop and
  (2) natural-language incident and priority interpretation. Raw model reasoning is never shown or stored.
- **Verifier:** Python, FastAPI, Pydantic v2, OR-Tools CP-SAT. Every solver plan is re-checked by an
  independent validator; timeouts are reported as "unknown", never as feasible.
- **Front end:** Next.js 16 (static export), TypeScript, Tailwind CSS, hand-built SVG scene, ripple map
  and timeline. API types generated from the backend's OpenAPI schema.
- **Deployment:** Vercel (two services on one domain). Stateless API: the browser holds content-hashed
  revisions and the server re-verifies any plan on apply (stale revisions get HTTP 409).
- **Quality:** 136 backend tests, web unit tests, Playwright journeys on desktop and mobile against the
  production build, CI with a full-history secret scan, and a production smoke script.
- Built with Claude Code as the development tool. Claude is not used at runtime.

## Evaluation (measured, not estimated)
Live NVIDIA Nemotron 3 Super on Nebius Token Factory, 20 fixed cases (incidents × priority profiles), one
run per agent version, compared with a deterministic playbook search, a greedy heuristic and an
exhaustive oracle over the same action space:
- Verified recovery found when one exists: agent 16/17 (both versions); playbook search 15/17; greedy 15/17.
- Honest "no verified recovery" when none exists: 3/3 for every method.
- Options failing independent re-validation: 0 for every method.
- Best option equals the oracle's: agent 9/17 (v2) and 7/17 (v4); playbook search 8/17; greedy 6/17.
  We do not claim better overall plan quality than the playbook; the samples are small.
- Where the agent adds something the baselines miss: in c19 (setup team away) it finds a verified,
  zero-cost recovery (a free person helps rig + a line check) that both baselines report as impossible.
- Median latency ~18–20 s per recovery; 20 runs cost $0.22–0.24 at list price.
- Still weak: fixes that need three simultaneous changes (c09).
Full data and per-case tables: `docs/evaluation/`.

## Challenges
- Making the model's output safe to act on: a strict tool boundary (allow-listed actions, extra fields
  rejected), a verifier that is the only authority, and server-side re-verification on apply.
- Giving the agent real room to help: early versions could only restrict the solver, so the agent was
  effectively choosing from a menu. Adding helpers and graded compression gave it levers the playbook
  doesn't have; the evaluation shows where that pays off and where it doesn't.
- Explaining infeasibility honestly ("does not touch what sets the doors time", "helps but not enough",
  "makes things worse than doing nothing").

## Accomplishments
_Only items verified in the running app or tests; link evidence in `docs/evidence/` and `docs/evaluation/`._

## What we learned
_Pull from `docs/feedback-nebius-nvidia.md` (empirical observations only)._

## What's next
Scenario import from real run-of-show sheets, multi-day productions (film shoots, festivals), shared
sessions for a production team, and calendar/messaging integration for the change notice.

## Feedback on Nebius and NVIDIA tools
See `docs/feedback-nebius-nvidia.md` — keep to observed facts, separate opinions.
