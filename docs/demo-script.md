# Demo video: shot-by-shot recording script

**Target 2:48. Hard limit: under 3:00 (aim to finish under 2:50).** English narration. No music.

Record the real site, https://ripple-room-five.vercel.app, in **live mode**. The badge in the top bar
must read **"Nemotron 3 Super on Nebius Token Factory"**. If it reads "Simulated agent, no model calls",
"Live AI paused" or "Today's live AI budget used", stop: do not record (see the fallback plan).

Ground rules
- Every result on screen comes from a real live run. Never edit, paste or composite results.
- You may cut idle waiting time. When you do, show the caption **"Waiting trimmed"** for the cut.
- Shots 5 to 7 must come from **one continuous run** (the board, the cards and the applied plan match).
  Shots 8 and 9 are separate runs.
- Narrate what the screen actually shows. Lines in *[brackets]* depend on the run: read the real text.
- The UI labels below are the exact current copy, in **bold quotes**.

## Shots

| # | Time | On-screen action (exact) | Narration | Caption (burned in) |
|---|---|---|---|---|
| 1 | 0:00–0:10 (10 s) | Page freshly loaded. Do nothing. Let the venue scene play. Pointer rests near the amber card **"Every job in this plan is connected."** | "This is Signal Night, a fictional event. Doors open at six. Every job depends on other jobs. So what happens when one thing goes wrong?" | Signal Night: a fictional event. Doors open 18:00. |
| 2 | 0:10–0:26 (16 s) | Click **"What if the truck arrives 35 minutes late?"**. Let the ripple run. Header flips to **"If nobody acts"**: **"Ready for doors" 18:15**, chip **"15 min late"**, **"Doors open" 18:00**. | "The truck is thirty-five minutes late. Ripple Room traces the chain: unloading, rigging, lighting, soundcheck, the safety walk, the briefing. Doors would be ready at 18:15. That is fifteen minutes late. These times come from a scheduling engine, not an animation." | One late truck. Doors 15 minutes late. |
| 3 | 0:26–0:36 (10 s) | Scroll to **"How it spreads"**. Click the **Stage rigging** node. Hold on the inspector line **"Why not earlier:"**. | "Click any job, and it tells you what holds it in place. *[Read the 'Why not earlier' line.]*" | Every job explains its delay. |
| 4 | 0:36–0:48 (12 s) | Right column, under **"What matters most today?"**: set **Guest experience** to **Protect**. Leave everything else on **Balance**. Point at the small line **"NVIDIA Nemotron on Nebius Token Factory proposes fixes…"**. Click **"Find recovery options"**. | "Now I ask for a recovery. I want to protect the guests. That is a preference. The doors time, skills and crew hours are hard rules. Nobody can bend them." | Priorities rank fixes. Hard rules never bend. |
| 5 | 0:48–1:22 (34 s) | The **"Verifier board"** fills. Open the trace panel **"Nemotron 3 Super on Nebius"** and point at one **"Model call N: … request …"** row. Then point at a red **"× cN rejected"** verdict and its reason. | "NVIDIA Nemotron 3 Super, running on Nebius Token Factory, reads the situation through tools. It proposes fixes, but it cannot change the plan. Every proposal goes to a constraint solver. Filled green dots hold. Red ones are rejected, with a reason. *[Read the rejection reason on screen.]* Nemotron reads that reason and tries again." | Nemotron proposes. The solver checks every proposal. |
| 6 | 1:22–1:42 (20 s) | Point at **"Ranked by your priorities: fewest breaches first, then fewest penalty points."** Point at each card's origin line (**"Nemotron's own first choice"**, **"Nemotron listed it #N"** or **"Standard fix from the playbook search, verified"**). Click card **1** (**"Preview on the plan"**). Header reads **"With the selected recovery"** with **"Before the incident → If nobody acts → With this recovery"**. | "What is left are verified plans, ranked by my priorities. Each card says where it came from: Nemotron, or our standard playbook. Cost, guest impact and the jobs it touches are spelled out. Preview replays the whole day with the fix." | Only verified plans reach you. |
| 7 | 1:42–2:00 (18 s) | Click **"Apply this plan"**. Heading **"Recovery applied"** and the **"Who needs to know"** list with **"tell by"** times. Then click **"Undo"** in that panel. | "Nothing changes until I approve. On apply, the server checks the plan again from scratch. Then it tells me who needs to know what, and by when. And undo is one click." | You approve. The server re-checks. |
| 8 | 2:00–2:24 (24 s) | Click **"Reset"** (top bar). In the box under **"Or try another incident"**, type: `Our setup team has to step out from 14:30 to 15:30.` Click **"Read the incident"**. Hold on **"Read by Nemotron on Nebius, request …"**. Click **"Apply to the plan"**. Set all three priorities to **Balance**. Click **"Find recovery options"** (trim the wait). Click the card whose origin line names Nemotron (**"Nemotron's own first choice"** or **"Nemotron listed it #N"**). | "A harder case. The setup team is away for an hour. Nemotron turns my words into a typed incident, and I confirm it. Here our playbook search finds nothing. *[If the card shows it:]* Nemotron found a fix the playbook cannot express: a free person helps rig the stage, plus a shorter line check. The solver verified it, at zero cost." | Beyond the playbook: a fix it cannot express. |
| 9 | 2:24–2:34 (10 s) | Click **"Reset"**. Under **"Or try another incident"**, click **"Truck breakdown +90 min"**. Click **"Find recovery options"** (trim the wait). Hold on **"No verified recovery found."** and the summary naming 18:30. | "And when there is no way to make it, it says so. No fake green plan." | No fix? It says so. |
| 10 | 2:34–2:44 (10 s) | **Architecture card** (static slide, text below). | "Nemotron on Nebius proposes. A solver checks. A person decides. In twenty test cases, no option ever failed re-checking. The agent is not better than our playbook overall. But it found one fix the playbook cannot." | (card text) |
| 11 | 2:44–2:48 (4 s) | **Closing card:** "Ripple Room" + https://ripple-room-five.vercel.app | "Ripple Room. See the chain reaction. Fix the day." | Ripple Room. See the chain reaction. Fix the day. |

### Architecture card (10 seconds, static)

> **NVIDIA Nemotron 3 Super on Nebius Token Factory** proposes typed fixes through tools.
> **OR-Tools CP-SAT** checks each fix. An **independent validator** checks again. **A person approves.**
>
> Measured on 20 fixed cases, one run per agent version:
> 0 options failed re-validation · honest "none" in 3/3 impossible cases ·
> best option matched the exhaustive search in 9/17 and 7/17 cases (playbook search: 8/17).
> Not better overall than the playbook. Found one fix it cannot express (case c19).
>
> Fictional event. Built with Claude Code as the development tool; the only runtime AI is Nemotron.

### Closing line
"Ripple Room. See the chain reaction. Fix the day."

### Where the numbers come from
- 35 min, 18:15, 18:00 (shot 2): `docs/evidence/live-run-truck-delay-35-20261016T211726Z.json`
  ("doors ready 18:15 vs deadline 18:00").
- 18:30 (shot 9): `docs/evidence/live-run-truck-breakdown-90-20261016T211755Z.json`.
- Zero cost and the c19 fix (shot 8, card): `docs/evaluation/CASES-c19-c09.md`.
- 20 cases, 0 failed re-validation, 3/3, 9/17, 7/17, 8/17, one run per version (shot 10, card):
  `docs/evaluation/COMPARISON-v2-v4.md`.
- Never add a number to the narration that is not on screen or in these files.

## Fallback plan (re-take; never edit results)

| Problem in a take | What to do |
|---|---|
| No rejection on the verifier board (shot 5) | Click **"Reset"** and re-take shots 2 to 7. Try **Guest experience: Protect** and **Extra spend: Protect**. After three takes with no rejection, keep the best take and say instead: *"This time every proposal held. When one fails, the solver says why."* Do not borrow a rejection from another take. |
| No Nemotron card beyond the playbook (shot 8) | Re-take shot 8 (each run costs about one cent). After three takes without it, narrate what is on screen, for example: *"This time Nemotron found no fix. In our benchmark it found one in both runs."* Then show the line on the architecture card. Never claim the fix happened in this take. |
| A playbook card ranks first in shot 8 | Fine. Narrate it as it is. Only call a fix "beyond the playbook" if its card says it came from Nemotron. |
| Intake misreads the sentence (shot 8) | Click **"Discard"**, retype the sentence exactly, and re-take. |
| "The recovery agent could not finish." or a run hangs | Stop. Check `/api/health`. Re-take later. Do not record **"Run the playbook search without AI"** as if it were the AI. |
| Badge is not live, or reads **"Today's live AI budget used"** | Stop recording. Wait for the daily reset (midnight UTC) or ask the owner. Never record simulated output as live. |
| Total runs over 2:50 | Trim waiting time first (with the "Waiting trimmed" caption), then shorten shot 3 or drop it. Keep shots 2, 5, 6, 7, 10 and 11. |

## Recording checklist

- [ ] **Browser:** Chrome, window 1920×1080, zoom 100 %, bookmarks bar hidden, one tab, cursor visible.
      Fresh profile or incognito, so no old state.
- [ ] **Health is live:** open https://ripple-room-five.vercel.app/api/health and confirm `"mode":"live"`
      and `"status":"live"`. Optional, owner-approved (makes real calls):
      `uv run python scripts/check_judge_demo.py https://ripple-room-five.vercel.app`.
- [ ] **Warm-up run:** do shots 2, 4 and 5 once off camera, so the first take does not hit a cold start.
- [ ] **Reset:** click **"Reset"**, then reload the page, before each take.
- [ ] **Mic:** quiet room, headset or USB mic, one test clip played back. No background music.
- [ ] **Captions:** burn in the short captions above. Upload English subtitles made from the narration
      column (YouTube Studio → Subtitles).
- [ ] **Say it out loud:** "NVIDIA Nemotron" and "Nebius Token Factory" (shot 5) and "fictional" (shot 1).
- [ ] **Length:** final export under 3:00 (target 2:48). Check the length again in YouTube Studio.
- [ ] **YouTube:** visibility **Public** (not Unlisted), English title, for example
      "Ripple Room: NVIDIA Nemotron on Nebius Token Factory, verified by a solver". Paste the link into
      `README.md` and `docs/devpost-submission.md`.
