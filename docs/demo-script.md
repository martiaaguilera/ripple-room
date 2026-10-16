# Demo video storyboard (target 2:40, hard limit < 3:00)

Recording rules: real screen capture of https://ripple-room-five.vercel.app in **live mode** (header badge
must read "Nemotron 3 Super on Nebius Token Factory"), 1920×1080, browser zoom 100 %, cursor visible.
No music without a licence, no mock runs presented as live, no edited-in results. If a live run
differs from this script (different proposals, different rejections), narrate what actually happens.

| Time | Screen | Narration (English) |
|---|---|---|
| 0:00–0:12 | Landing on the control room. Scene clock sweeps: truck rolls in at 14:00, task bars fill, crew tokens move, doors ready 17:40. Pointer rests on "What if the truck arrives 35 minutes late?" | "Signal Night opens its doors at 18:00. Fifteen connected jobs, six people, one truck. What happens when one thing goes wrong?" |
| 0:12–0:30 | Click the button. Rooms flash in order, the ripple runs through the dependency map, doors clock tweens 17:40 → 18:15 (coral). Header sentence appears. | "The truck is 35 minutes late. Ripple Room traces the chain: unloading, rigging, lighting, soundcheck, the safety walk, the briefing. Doors would be ready at 18:15: fifteen minutes late. Every number here comes from the scheduling engine, not from animation." |
| 0:30–0:45 | Scroll the scene: crew sitting in the crew room waiting for the truck; point at Stage rigging in "How it spreads" → inspector shows "Waits for Unload stage deck". | "You can see why: the crew is idle until the truck arrives, and every job explains what holds it in place." |
| 0:45–1:00 | Right column: set Extra spend = Protect, Guest experience = Protect. Click "Find recovery options". | "Now I ask for a recovery. I care about guests and I'd rather not spend money. These are preferences; the deadline, skills and crew hours are hard rules nobody can bend." |
| 1:00–1:35 | Verifier board fills live: model calls with request ids, proposals c1…c5, filled and hollow dots, verdict list. Hover a rejected verdict. | "NVIDIA Nemotron 3 Super, running on Nebius Token Factory, reads the situation and proposes fixes through tools. It can't change the plan itself. Every proposal goes to a constraint solver. Here it suggested putting the transport crew on rigging — the solver rejects it: that crew is needed to unload the AV gear, so doors would open even later. Nemotron revises." *(Use the actual rejection shown.)* |
| 1:35–2:00 | Option cards ranked 1–3; click option 2 to preview: scene replays, before/after strip shows 17:40 / 18:15 / 17:55; timeline bars slide. | "What's left are verified plans, ranked by my priorities with the trade-offs spelled out: cost, guest impact, which jobs change. I can preview each one: the whole day replays with the recovery." |
| 2:00–2:18 | Click "Apply this plan". "Recovery applied" + "Who needs to know" list with tell-by times. Click Undo, then re-apply. | "Nothing changes until I approve. When I do, the server re-verifies the plan and tells me exactly who needs to know what, and by when. Undo is always one click away." |
| 2:18–2:32 | Quick cut: breakdown +90 → "No verified recovery found" with the 18:30 bound. Then the evaluation table from the README. | "And when there's no way to make it, it says so — no fake green plan. On twenty test cases, every option every method returned passed independent re-validation." *(Quote only numbers from docs/evaluation.)* |
| 2:32–2:45 | Architecture card (from README) → product title + URL. | "Nemotron on Nebius to reason, a CP-SAT solver to prove, and a human to decide. Ripple Room: see the chain reaction, fix the day." |

## Checklist before recording
- [ ] `/api/health` reports `"mode":"live"`; run `scripts/check_judge_demo.py` first.
- [ ] Fresh browser profile (no cached state), 1920×1080.
- [ ] Do one warm-up run to avoid a cold start on camera; then Reset.
- [ ] Keep model calls on screen long enough to read one request id.
- [ ] Video says "NVIDIA Nemotron" and "Nebius Token Factory" out loud (organiser advice).
- [ ] Upload to YouTube as **Public**; check length < 3:00; add English captions.
