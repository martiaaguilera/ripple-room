# What winning hackathon projects have in common, and what we changed because of it

Research date: 27 Oct 2026. Sample sizes are small, so treat every pattern as a heuristic, not a law.

## Sources
1. **This hackathon's judges.** The "Will It Ship?" session: six judges from Nebius, Tavily and NVIDIA
   reviewed four real submissions live. Devpost update 47163 summarised it:
   https://nebiusglobalaihackathon.devpost.com/updates/47163-recording-will-your-project-ship
   Also update 46205, "How to build a winning project", and update 46207, the submission checklist.
2. **All Things Agentic Hackathon (Devpost, Aug 2026): all 16 winners vs 16 random non-winners.**
   Gallery: https://allthingsagentichackathon.devpost.com/project-gallery. I scraped the project pages
   on 27 Oct 2026. YouTube durations came from each video's watch page.
3. **NVIDIA NeMo Agent Toolkit hackathon (2025).** First place was a NeMo Agent Toolkit agent plus the cuOpt
   optimiser for fleet routing, an LLM-plus-solver pattern like ours. Criteria were real-world
   applicability, technical execution, and "agentic AI in action".
   https://developer.nvidia.com/blog/hackathon-winners-bring-agentic-ai-to-life-with-the-nvidia-nemo-agent-toolkit/
4. **Other winner lists**, for context only:
   - Gemini API Developer Competition 2024: https://developers.googleblog.com/en/announcing-the-winners-of-the-gemini-api-developer-competition/
   - Microsoft AI Agents Hackathon 2025: https://microsoft.github.io/AI_Agents_Hackathon/es/winners/
   - Google ADK Hackathon 2025: https://cloud.google.com/blog/products/ai-machine-learning/adk-hackathon-results-winners-and-highlights
5. No previous edition of this hackathon has published winners yet, so there is nothing to compare
   with directly. The lablab.ai "Nebius AI Studio" event listed no projects.

## Measured: winners vs non-winners (All Things Agentic, n = 16 each)
| Signal in the Devpost page | Winners | Random non-winners |
|---|---|---|
| Write-up length (median words) | 1,856 | 682 |
| Images in the write-up (median) | 5 | 2 |
| Quantified claims (median count) | 2 | 0 |
| Says hard limits live in code, not in the prompt ("guardrail", "cannot", "in code") | 16/16 | 6/16 |
| Has an architecture section or diagram | 12/16 | 8/16 |
| Evaluation, benchmark or baseline | 11/16 | 8/16 |
| Human approval for critical actions | 9/16 | 5/16 |
| Has a live demo link besides the repo | 12/16 | 9/16 |
| Video length (median) | 239 s | 203 s |

The keyword matching is crude, and the comparison is descriptive, not causal. Winners' videos used
almost the full time limit.

What the top write-ups do, from reading them in full:
- **The Grand Prize write-up (Plant Debugger)** has a section called "What is simulated and what is
  live". It says, in its own words, that "deterministic code alone proves recovery" and that the model
  "never receives authority to declare RESOLVED".
- **Overturn** opens with one specific patient and one real statistic with a cited source. It then
  admits that the patient is invented. It presents **refusals as the system working** ("three are
  refusals the system chose to make"). Every screenshot caption makes a claim.
- **Latch** uses negative controls, holdout evaluation and sealed evidence. It shows rigour, not just
  features.
- **The taglines are concrete:** a specific user, a specific failure and a number. Two examples:
  "the last meter has no API" and "verify every citation before a human sees it".

## Stated by this hackathon's judges (update 47163)
- Solve a real problem for a real audience.
- Get to the aha moment fast: within 2 minutes in the app, and 30 seconds in the video.
- One thing done well beats a big stack.
- Put the action first. Add a little onboarding, and **show which model is doing what**.
- **Publish your limitations:** "documented failure cases" read as rigour. If you built for
  accessibility, say so.
- Budget extra time for packaging.
- Also, from update 46207: **do not edit the repo, the video or any materials after the deadline.**

## The algorithm (score each item 0–2, fix the lowest first)
1. **Problem in one sentence**, with a specific user and a specific failure.
2. **Aha in 30 s of the video** and in under 2 minutes of the app. The action comes first.
3. **One core loop done well.** Every integration serves it.
4. **The authority boundary is explicit:** the model proposes and deterministic code decides. Say it,
   and show it on screen.
5. **Show which model does what**, in the app and in the video, with audio.
6. **Evidence:** measured against baselines, with the losses published and refusals shown as features.
7. **Limitations section,** including "what is simulated and what is live".
8. **Packaging:** a write-up of about 1,500–2,000 words, at least 5 images whose captions make claims,
   an architecture diagram, and a video close to the limit (here under 3:00).
9. **Accessibility called out**, with proof.
10. **Sponsor tech impossible to miss:** in the text, in Built With and in the narration.

## Ripple Room against the algorithm
| # | Before (27 Oct) | Change made |
|---|---|---|
| 1 | Good: the coordinator, one doors time, the chain reaction | Inspiration now opens with one concrete (fictional, labelled) moment and names the audience |
| 2 | Ripple aha at 0:10–0:26; the action is the first thing on screen | First shot now states the user and the roles; the inspector shot is shortened |
| 3 | Good: one loop (break → propose → verify → approve) | No new features |
| 4 | In the text, not on the first screen | The start card now names who does what (model, solver, you); new architecture image |
| 5 | Only in the badge | The start card names the live model and labels mock mode as simulated |
| 6 | Strong: baselines, oracle, losses published | Evaluation image with wins **and** losses; the honest "none" is framed as a feature |
| 7 | Scattered across docs | New Devpost section "What is live, what is simulated, what is not done" |
| 8 | 0 images, text architecture | 8 gallery images with claim captions (`docs/submission/gallery`) |
| 9 | Axe gate existed, not mentioned | Accessibility section; in-app override for reduced motion |
| 10 | Good | Kept |

Still open (owner):
- A live screenshot of the verifier board for the gallery. The current one is from mock mode and
  labelled as such.
- Talking to one or two real event coordinators before submitting. Any quote must be real.
- The live re-measurement of the deployed hybrid agent (v7), if authorised.
