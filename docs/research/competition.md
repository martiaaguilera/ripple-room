# Ripple Room: competition and prior-art audit

Research date: 16 Oct 2026. All URLs were accessed on 2026-10-16 unless noted otherwise.
Vendor feature claims come from marketing pages and have not been tested hands-on.
"NOT VERIFIED" means I could not confirm the item from a primary source.

## 0. Hackathon context (this affects how we differentiate)

Source: https://nebiusglobalaihackathon.devpost.com/ and /rules, fetched with curl. WebFetch got a 403.

- Submission period: 26 Aug 2026 to **30 Oct 2026, 10:00 PT**. Judging period: 1 Dec to **15 Dec 2026, 12:00 PT**. Winners are announced around 11 Jan 2027.
- 24,065 participants were registered when I checked. Expect a lot of "multi-agent ops copilot" entries.
- Tracks: Coding and Agentic Engineering, **Best Apps and Agents** (best fit for us), Personal AI, Physical AI.
- Stage 2 has four equally weighted criteria:
  1. **Technological Implementation**: use of Token Factory and Nemotron.
  2. **Design**: "complete, coherent product experience not just a technical proof of concept".
  3. **Potential Impact**: "credible, specific case for solving a real problem for a real audience".
  4. **Quality of the Idea**: "creative, non-obvious use ... genuine understanding of the problem space".
- The Best Apps and Agents track text encourages "Nemotron 3 Ultra when you need serious reasoning, and ... Nano or Super [for] fast, everyday calls". It also suggests (does not require) Nebius Serverless Endpoints or Jobs.
- The project gallery at https://nebiusglobalaihackathon.devpost.com/project-gallery says: "The hackathon managers haven't published this gallery yet". **I could not audit competing entries in this hackathon.** I audited Devpost's global project search instead (section 2).

## 1. Commercial products and research

### 1. Shoflo Rundown (now part of LASSO)
- URL: https://www.lasso.io/rundown/ (evidence date: page as fetched 2026-10-16)
- Overlap: this is the incumbent run-of-show tool for live events. It covers per-item durations, "Changing duration or start time triggers automatic recalculation", live over/under tracking, and synced crew devices.
- Difference: it shifts times linearly in a list. The page describes no dependency graph, no cross-resource (truck, crew, venue) constraints, no what-if branch, no AI, and no verified intervention options.
- Take: this is the tool our target user already uses, so pitch Ripple Room as the "what do we do now?" layer on top of a rundown. Don't pitch it as a replacement.

### 2. Rundown Studio
- URL: https://rundownstudio.app/ (evidence date: 2026-10-16)
- Overlap: "Enter a cue duration and watch every future cue automatically update its start time". It has live auto-scroll and is priced for single events ($25 per event, plus a free Solo tier).
- Difference: the page mentions no dependencies, no AI, and no scenario comparison. Propagation is sequential, not graph-based.
- Take: this confirms that small-event producers will pay per event. It is evidence for the "small live events" audience in our impact pitch.

### 3. ALICE Technologies (generative construction scheduling)
- URL: https://alicetechnologies.com/ and https://blog.alicetechnologies.com/alice-and-generative-ai-whats-the-difference (evidence: vendor pages, 2026-10-16)
- Overlap: this is the closest commercial match to the "what-if" idea. ALICE's optimiser generates many feasible schedules from constraints and compares them on a time-vs-cost plot. Its FAQ cites an LLM "Insights Agent" that compares two solutions.
- Difference: it is enterprise construction (multi-month capital projects) software that needs heavy onboarding. Ours is one day, minutes-scale disruptions, a single injected shock, and small typed patches.
- Take: this proves the "optimiser + LLM explainer + scenario compare" pattern has commercial value. We can't claim we invented it, only that we brought it to day-of live operations.

### 4. Motion (AI project management and auto-scheduling)
- URL: https://www.usemotion.com/ (evidence: 2026-10-16). Third-party 2026 review: https://www.morgen.so/blog-posts/motion-review
- Overlap: "Automatically re-plan your day whenever anything changes". It weighs "priorities, dependencies, deadlines, durations". It has an AI Gantt chart, and reviews say it has project-manager agents.
- Difference: Motion re-plans automatically and opaquely for knowledge-work tasks. It does not show the cascade, does not offer alternative interventions, and does not give a solver-verified feasibility proof per option. Users also report wrong placements (per the Morgen review).
- Take: this is the "AI reschedules for you" baseline judges will know. We should position against it with "you see why, choose among options, and can undo".

### 5. Timefold (formerly OptaPlanner)
- URL: https://timefold.ai/. Funding news (June 2026): https://pulse2.com/timefold-raises-13-million-series-a-to-expand-routing-and-scheduling-apis/
- Overlap: "reschedule in real time when disruptions hit". It has built-in explainability and an open-source solver. Its 2026 positioning is "Optimization goes agentic". It argues that agents need deterministic optimisation, not LLM-generated schedules, and a 2026 Devoxx talk was titled "LLMs can't optimize schedules, but AI can!".
- Difference: Timefold is an API and solver for developers (field service, shifts, routing). It has no visual cascade studio and no LLM proposing interventions. The solver re-optimises globally instead of proposing small human-reviewable patches.
- Take: this validates our core thesis that "LLM proposes, solver verifies" is where the industry is heading. It also means the idea alone is not novel.

### 6. Simio (process digital twin and simulation-based scheduling)
- URL: https://www.simio.com/ (evidence: 2026-10-16)
- Overlap: the site says "Simulate what-if scenarios with confidence" and offers side-by-side scenario comparison, real-time rescheduling after disruptions, and risk-based planning.
- Difference: Simio is heavyweight manufacturing and logistics digital-twin software that needs modelling expertise. The page mentions no LLM features; its AI is DNN agents and ONNX models.
- Take: Simio is the "digital twin ops" category, built for experts. Ripple Room is a lightweight, single-day digital twin that a non-expert can operate in 3 minutes.

### 7. OptiGuide (Microsoft Research): LLM + solver for what-if questions
- URL: https://www.microsoft.com/en-us/research/publication/large-language-models-for-supply-chain-optimization/ (published July 2023). Paper: https://arxiv.org/abs/2307.03875. Package: https://pypi.org/project/OptiGuide/0.0.2
- Overlap: the key idea is "not to replace optimization technology by LLMs, but rather use optimization solvers in tandem with LLMs" to answer what-if questions. The paper says it was used in production by Microsoft cloud supply-chain planners.
- Difference: OptiGuide is a natural-language Q&A layer over a supply-chain MILP and is not visual. The LLM writes code to change the model and then explains the results. It does not generate typed intervention patches, has no cascade view, and has no apply/undo.
- Take: this is the canonical research precedent. We should cite it in our write-up as lineage; that shows judges we understand the problem space.

### 8. SchedulerRX: Constraint Debugger Agent (Google for Startups AI Agents Challenge)
- URL: https://github.com/tpinzzz/schedulerrx-constraint-agent (MIT; created 2026-06-09, last push 2026-06-10, 0 stars). Listing: https://glama.ai/mcp/servers/tu0ex3ird5
- Overlap: **very close on architecture.** OR-Tools CP-SAT is the ground truth. Gemini (Google ADK, over MCP) ranks candidate fixes, and "every recommendation is re-solved before it is shown". It runs FastAPI on Cloud Run.
- Difference: its domain is medical residency rosters, and it diagnoses INFEASIBLE models. It has no live disruption injection, no visual cascade, no Gantt before/after, and no apply/undo. Its README says the production solver is vendored and not in the open repo.
- Take: this is the strongest evidence that "LLM proposes fixes and CP-SAT verifies them" is already done in a hackathon. Our originality has to come from the domain, the interaction, and the visual cascade.

### 9. Agentic Film OS (Devpost, Agentic Cinema hackathon)
- URL: https://devpost.com/software/agentic-film-os (submitted around 2026-08-20; built with Gemini, Node.js, TypeScript)
- Overlap: **closest domain and story match.** A disruption (storm, actor in transit, gear failure) on a film set causes a "ripple effect". Agents "traverse the production dependency graph" and present recovery plans "with human approval".
- Difference: it is film production, not small live events. It uses multi-agent negotiation with external stakeholders. The write-up does not mention a deterministic solver or verifier.
- Take: judges who have seen Devpost entries will recognise the narrative. We win on verifiability ("we can prove each option is feasible"), not on the narrative.

### 10. Cascade (Devpost, WebMCP Challenge)
- URL: https://devpost.com/software/cascade-3k8zpi (submitted around 2026-09-03; Next.js, React, TypeScript)
- Overlap: a plan becomes a dependency map. An agent opens a **what-if branch**, applies a shock ("billing arrives three weeks late"), traces downstream effects, and stages responses as drafts. A human promotes the branch.
- Difference: it reasons qualitatively about assumptions and risks. It has no time-based schedule, no Gantt, and no quantitative feasibility check. Its "modeled downstream effects" are not solver-verified.
- Take: this is almost the same interaction model (inject shock, branch, review, promote). Our differentiator has to be numbers: minutes of slip, constraints violated, and an objective delta.

## 2. Other Devpost prior art (Devpost search API, 2026-10-16)

The query endpoint was `https://devpost.com/software/search?query=...` (JSON). None of these is in the Nebius gallery, which is unpublished.

| Project | Hackathon / date | What overlaps |
|---|---|---|
| **Ripple** https://devpost.com/software/ripple-0anqhk | Amazon Developer Hackathon, around 2026-09-07 | **Name collision.** It is about personal-travel cascades: "change → dependency analysis → consequences → economic exposure → optimized repair → exact approval". It uses FastAPI and MCP. |
| Apron https://devpost.com/software/apron-nu86yq | Agentic Cinema, around 2026-09-09 | Live sports broadcast "irregular operations desk". 8 Gemini agents re-route crew when a game runs long. Live-event ops domain. |
| Port Operations Dispatch Agent https://devpost.com/software/port-operations-dispatch-agent | All Things Agentic, around 2026-08-27 | Plans a day, injects "Wagon breakdown at 09:30", re-plans only what broke. Dock Gantt with "dashed ghosts" before/after, plus approve/override. |
| AeroFleet https://devpost.com/software/aerofleet-4u6wce | All Things Agentic, around 2026-08-31 | Airline disrupted-day recovery. Hard legality checks are done in code, not by the LLM. It compares against an agents-off counterfactual replay. |
| ClassShift https://devpost.com/software/classshift-ondmzi | Next Founders, around 2026-10-15 | One unavailable room triggers a "chain reaction". Minimal-change repair with OR-Tools (min-cost-flow). No LLM listed. |
| SupperShift https://devpost.com/software/suppershift-dinner-plans-that-survive-real-life | Amazon Developer Hackathon, around 2026-10-10 | A resource-constrained dinner schedule. "Oven busy 20 min" shifts the ETA, and the app compares two audited recovery options before commit. |

Research lineage worth citing:
- ALAS: disruption-aware multi-LLM planning with "history-aware local compensation", May 2025. https://arxiv.org/abs/2505.12501
- "Replan, Repair, or Edit?" (Sep 2026) found that local repairs "made fewer edits" and preserved more commitments than full replanning. https://arxiv.org/abs/2609.19654

The second paper directly supports our "small patch, not full re-solve" design.

## 3. Differentiation thesis (honest)

There is real competition. Each element of Ripple Room exists somewhere:
- cascade propagation: run-of-show tools, Agentic Film OS, Ripple
- what-if branching: Cascade, ALICE, Simio
- LLM proposes and solver verifies: OptiGuide, SchedulerRX, Timefold's positioning
- before/after Gantt with approve: Port Ops Dispatch Agent

What I did not find combined in one product is the following:
1. **The domain is small live events on the day itself.** Rundown tools serve this market but have no constraint model. Optimisers have constraint models but serve enterprises.
2. **The cascade is visible and quantified on a graph and a Gantt together**, showing exactly which tasks and resources move and by how many minutes.
3. **Interventions are typed, minimal patches** (shift, swap resource, compress duration, parallelise, drop optional) rather than a fresh global schedule. Each patch carries a **CP-SAT verdict** (feasible / infeasible plus the violated constraints) and an objective delta.
4. **The human stays in control.** You compare Before/After and apply or undo, which makes this a decision studio rather than an autopilot.

One-line thesis: *"Rundown tools show you that you're late; optimisers silently re-plan; Ripple Room shows the chain reaction and hands you three small, solver-proven ways out, and you pick one."*

## 4. Risks to originality

- **The pattern is not novel.** "LLM proposes, CP-SAT verifies" is shipped (SchedulerRX, June 2026) and is industry consensus (Timefold, OptiGuide). Judges scoring "creative, non-obvious" may see it as standard.
- **The narrative is crowded.** At least 6 Devpost projects from Aug to Oct 2026 tell the "one disruption → downstream cascade → agent repair → human approves" story. Several of them have before/after Gantt views (Port Ops) or what-if branches (Cascade).
- **There is a name collision with "Ripple"** (Amazon hackathon, Sep 2026, same "ripple/cascade" metaphor). Searches will surface it.
- **The Nebius gallery is unpublished**, so we can't see same-hackathon entries. With 24k registrants, near-duplicates are likely.
- **Weak LLM role.** If Nemotron only ranks or explains while the solver does the real work, judges may score "use of Nemotron" low. The opposite failure is the LLM doing work it shouldn't (AeroFleet's write-up criticises exactly this).

### Concrete suggestions to sharpen differentiation

1. **Make "verified minimal patch" the headline and show it numerically.** For each proposal, display: patch size (number of tasks touched), minutes recovered, hard constraints checked (count), and a CP-SAT verdict badge. Also show one *rejected* LLM proposal with its violated constraint. This visibly beats Agentic Film OS and Cascade, which have no proof, and Motion, which is opaque. Cite the Sep 2026 "Replan, Repair, or Edit?" finding to justify minimality.
2. **Give Nemotron a job the solver can't do, and use model tiering to show it.** Nemotron Super or Ultra turns messy real-world disruption text into a typed shock, and also proposes *operational* interventions the solver's model doesn't enumerate (e.g. "use the side dock", "move speaker Q&A after lunch"). Nano drafts the crew-facing comms for the chosen patch. CP-SAT only verifies and scores. This matches the track text exactly ("Ultra for serious reasoning, Nano or Super for fast calls") and answers "creative use of Nemotron".
3. **Own a concrete small-event persona and an artifact competitors lack.** Example: a 300-person conference or wedding day with vendors, AV, catering, and a load-in dock. The artifact is a one-click "change notice" listing who must be told what by when, generated from the applied patch diff. Also rename the internal "ripple" vocabulary in public copy (e.g. "chain reaction") to avoid confusion with the Amazon "Ripple" entry. Mention lineage (OptiGuide, Timefold) in the README to show problem-space understanding.
