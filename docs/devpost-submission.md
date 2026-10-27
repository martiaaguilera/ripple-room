# Devpost submission draft (owner reviews and submits)

Every number below comes from `docs/evaluation/` or `docs/evidence/`, except the impact of the
35-minute truck delay (13 tasks slip, doors ready 18:15, truck at 14:35 instead of 14:00), which is the
deterministic engine's output, frozen in `apps/web/src/test/fixtures.json` (`shocked.impact.metrics`:
12 delayed + 1 breach) and shown on screen. Paste each section into the
matching Devpost field.

**Title:** Ripple Room: See the chain reaction. Fix the day.

**Tagline (under 200 characters):** One late truck: 13 tasks slip and the doors open late. Ripple Room
shows the chain reaction. NVIDIA Nemotron on Nebius proposes fixes, a solver verifies each one, you choose.

**Track:** Best Apps and Agents

**Links**
- Live demo: https://ripple-room-five.vercel.app (no login; NVIDIA Nemotron 3 Super via Nebius Token Factory)
- Code: https://github.com/martiaaguilera/ripple-room (MIT licence)
- Video: _(YouTube URL, public, under 3 minutes; add after recording)_

**Built with:** NVIDIA Nemotron 3 Super (`nvidia/nemotron-3-super-120b-a12b`), Nebius Token Factory,
Google OR-Tools CP-SAT, Python, FastAPI, Pydantic, Next.js, TypeScript, Tailwind CSS, Playwright, axe-core, Vercel.

**Image gallery** (upload in this order from `docs/submission/gallery/`; paste each caption):
1. `02-ripple.png`: "One truck 35 minutes late: 13 tasks slip and the doors would open 15 minutes late. Every time comes from a scheduling engine."
2. `04-verified-options.png`: "Every proposal goes to a constraint solver. Green holds, red is rejected with a reason. (Shown in simulated mode, as the badge says.)"
3. `07-architecture.png`: "The model proposes. The solver decides. You approve. The model can only submit typed patches."
4. `08-evaluation.png`: "Measured on live Nemotron 3 Super against a playbook search, a greedy heuristic and an exhaustive oracle, with the losses included."
5. `05-applied.png`: "Nothing changes until you approve. The server re-verifies the plan, then lists who needs to be told what, and by when."
6. `03-spread.png`: "How it spreads: each line is a dependency. Click any job to see what holds it in place."
7. `06-phone.png`: "Works on a phone: the venue reads top to bottom in the order the day runs."
8. `01-plan.png`: "The first screen names who does what before anything happens."

Replace image 2 with a live-mode capture if one is taken during recording (the badge must read
"Nemotron 3 Super on Nebius Token Factory").

## Try it in 60 seconds (for judges)
Open https://ripple-room-five.vercel.app. No login. Desktop browser recommended.
1. Check the top bar. The badge should read **"Nemotron 3 Super on Nebius Token Factory"**.
2. Click the amber button **"What if the truck arrives 35 minutes late?"**. The header now reads
   **"Ready for doors 18:15"**, **"15 min late"**, **"Doors open 18:00"**.
3. In the right column, under **"What matters most today?"**, set **Guest experience** to **Protect**.
   Click **"Find recovery options"**. Nemotron's proposals land on the **"Verifier board"**: kept
   (filled green) or rejected (red, with a reason). A run takes about 20 seconds (median 18.4–19.5 s
   in our benchmark).
4. Click the first option card (**"Preview on the plan"**). The whole day replays with the fix. Each card
   says where it came from: Nemotron or the playbook search.
5. Click **"Apply this plan"**. You get **"Recovery applied"** and **"Who needs to know"**. Click **"Undo"**.

Two more things to try (click **"Reset"** in the top bar first):
- **Beyond the playbook.** In the box under **"Or try another incident"**, type
  `Our setup team has to step out from 14:30 to 15:30.` Click **"Read the incident"**, then
  **"Apply to the plan"**. Leave all priorities on **Balance** and click **"Find recovery options"**.
  Our playbook search finds no fix here. In both benchmark runs Nemotron found one (a free person helps
  rig the stage, plus a shorter line check). Results can differ from run to run.
- **Honest "none".** Click **"Truck breakdown +90 min"**, then **"Find recovery options"**. Expect
  **"No verified recovery found."**

If the badge reads **"Live AI paused"** or **"Today's live AI budget used"**, the AI is off for spend
control. Use **"Or run the playbook search without AI"**: the solver, preview, apply and undo all still work.

If your system asks for reduced motion, the animations are off. To see the ripple, click **"Play animations"**
under the venue scene.

**New project:** built from scratch during the submission period (first commit 16 Oct 2026). The event,
people and costs in the demo are fictional.

## Inspiration
It is 13:50. Doors open at 18:00. The driver calls: the truck with the stage deck is stuck on the ring
road and will reach the dock at 14:35, not 14:00. The coordinator now has to work out, in their head and in minutes, what that
pushes. Unloading, rigging, lighting focus, soundcheck, the safety walk and the crew briefing all wait
on each other. Will the doors still open on time? And what is the cheapest change that saves them?

(The event is invented, and so are the people and the costs. The problem is not: anyone who has run
the day of a gig, a launch or a conference side event knows that moment.)

The plan lives in a spreadsheet. A spreadsheet shows the plan, but it does not show the chain reaction.
AI assistants will happily suggest a fix, but on show day nobody can afford a fix that only *sounds*
right. So we built Ripple Room around one rule: **the model proposes, a solver decides, and a person
approves.** No suggestion reaches the coordinator unless a constraint solver has checked it against the
real deadline, skills, crew hours and the rule that one person does one job at a time.

**Who it is for:** event coordinators and production managers of small live events, who run one fixed
doors time with a small crew and no operations-research team.

## What it does
**Who does what** (shown on the first screen, before you click anything):

| Role | Does | Cannot |
|---|---|---|
| NVIDIA Nemotron 3 Super on Nebius Token Factory | Reads the situation through tools, proposes typed fixes, revises after a rejection; turns your words into typed incidents | Change the plan, or call a fix "verified" |
| OR-Tools CP-SAT verifier + an independent validator | Decides whether a fix holds, and explains why not | Be overruled: a timeout is "unknown", never green |
| You | Set priorities, compare verified options, approve one or none | (Nothing changes until you approve) |

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
  Nemotron submitted zero options and named 18:30 as the earliest possible time. That refusal is the
  system working: a fake green plan on show day is worse than a clear "no".

## What is live, what is simulated, what is not done
- **Live:** every recovery and every free-text incident on the public demo calls Nemotron 3 Super on
  Nebius Token Factory, unless the badge says the AI is paused or the day's budget is used. The solver,
  ranking, apply and notice are deterministic code, always running.
- **Simulated:** the event, people and costs are fictional. The venue scene is illustrative and is
  driven by the plan's times, not by live tracking. Local development and our automated tests use a
  scripted mock agent, labelled "Simulated agent" everywhere it appears.
- **Not done:** one fixed scenario (no import of a real run-of-show yet); one user at a time (no shared
  sessions); the change notice is a list, not sent messages. The deployed hybrid agent (prompt v7) has
  not been measured live; the measured numbers below are for prompts v2 and v4.
- **Known failure:** fixes that need three changes at once (case c09, truck 65 minutes late) were found
  only by the exhaustive oracle, never by the agent, the playbook search or greedy.

## Accessibility
An automated axe gate (WCAG 2.0/2.1/2.2 A and AA) runs on five states of the journey, on desktop and on
mobile. Every control must be reachable by keyboard and have a name, and a keyboard-only test starts a
run, picks an option, applies it and undoes it. Status is always in words, never colour alone ("15 min
late", "holds", "rejected"). Animations follow the system's reduced-motion setting, with an in-app
"Play animations" button for viewers who still want to see the ripple.

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
- **Quality:** backend tests, web unit tests, Playwright journeys on desktop, mobile and Firefox, an
  accessibility gate, CI with a full-history secret scan, and a script that checks the full judge path
  on production.
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
- Measure the current hybrid agent (prompt v7, with verified playbook options always in the pool) live
  on the same 20 cases, with several runs per case so we can see run-to-run variation. It has not been
  measured live yet.
- Help the agent combine fixes (the c09 gap) and explore further before stopping.
- Import a real run-of-show sheet instead of a fixed fictional scenario.
- Multi-day productions, shared sessions for a team, and sending the change notice through calendar
  or messaging tools.

## Feedback on Nebius and NVIDIA tools
Paste from `docs/feedback-nebius-nvidia.md`.
