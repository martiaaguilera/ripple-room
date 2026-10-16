# Rules snapshot: Nebius x NVIDIA Global AI Hackathon 2026

All sources accessed **2026-10-16**. Devpost pages were fetched with curl (the WebFetch tool got HTTP 403).
Source keys used below:

- [R] Official Rules: https://nebiusglobalaihackathon.devpost.com/rules
- [H] Overview page: https://nebiusglobalaihackathon.devpost.com/
- [F] FAQs: https://nebiusglobalaihackathon.devpost.com/details/faqs
- [RES] Resources: https://nebiusglobalaihackathon.devpost.com/resources
- [D] Schedule: https://nebiusglobalaihackathon.devpost.com/details/dates
- [U-J] Update "Here's how judging works": https://nebiusglobalaihackathon.devpost.com/updates/46204-here-s-how-judging-works
- [U-W] Update "How to build a winning project": https://nebiusglobalaihackathon.devpost.com/updates/46205-how-to-build-a-winning-project
- [U-P] Update "Did someone say... prizes?": https://nebiusglobalaihackathon.devpost.com/updates/46206-did-someone-say-prizes
- [U-K] Update "Kickoff Tips": https://nebiusglobalaihackathon.devpost.com/updates/46203-kickoff-tips
- [U-B] Update "Build Session Recording & Resources": https://nebiusglobalaihackathon.devpost.com/updates/46337-build-session-recording-resources-available-live-coding-your-first-app-with-nebius
- [B] Nebius Builders Program: https://dev.nebius.com/builders

If the Official Rules and other hackathon materials disagree, the Rules win: "the terms and conditions of the Official Rules shall prevail." [R §11]

---

## 1. Dates and deadline

| Item | Official time (PT) | Europe/Madrid |
|---|---|---|
| Submission Period opens | Wed 26 Aug 2026, 09:00 PDT [R §1] | 18:00 CEST |
| **Submission deadline** | **Fri 30 Oct 2026, 10:00 PDT** [R §1][D] | **Fri 30 Oct 2026, 18:00 CET** |
| Judging Period | 1 Dec 2026 09:00 PST to 15 Dec 2026 12:00 PST [R §1][D] | to 15 Dec 21:00 CET |
| Winners announced | "On or around Monday, January 11, 2027 (12:00 pm Pacific Time)" [R §1] | |

- Timezone check (my own calculation, not from the source): on 30 Oct 2026 the US is still on PDT (UTC-7, DST ends 1 Nov 2026), while Spain has moved to CET (UTC+1, DST ends 25 Oct 2026). 10:00 PDT is therefore 17:00 UTC, which is **18:00 Madrid**. That matches the project's stated deadline.
- After the deadline: "you may not make any changes or alterations to your Submission" [R §5]. Drafts can be saved before then.
- [U-P] advises: "Submit early ... video uploads and last-minute debugging always take longer than expected."

## 2. Eligibility

- Open to "Individuals who are at least the age of majority where they reside", Teams of such individuals, and Organizations [R §3].
- Not open to residents of places where US or local law prohibits participation, "including, but not limited to, Brazil, Quebec, Russia, Crimea, Cuba, Iran, and North Korea", and other OFAC-sanctioned countries [R §3]. **Spain is not excluded.**
- Also excluded: the Sponsor (Nebius B.V.), Devpost, their employees and families, Judges and their employers, and affiliates [R §3].
- Team size: "The Official Rules don't set a maximum team size" [F].
- Multiple submissions are allowed only if each one is "unique and substantially different" [R §4].
- Country gap: Token Factory billing does not support every country. "This is an account-provisioning gap on Nebius's side, not a hackathon eligibility rule" [F].

## 3. Core requirement: "runs on Nebius Token Factory or Nebius AI Cloud"

- What to create: "a working software application that runs on either Nebius Token Factory or Nebius AI Cloud and uses at least one NVIDIA open source model, and that fits into one of the four hackathon tracks" [R §4].
- **Definition (verbatim):** "Runs on Nebius Token Factory or Nebius AI Cloud" means the project makes a **runtime call to the Token Factory inference API**, or is deployed/run using Nebius AI Cloud compute (Serverless Jobs, Serverless Endpoints, or DevPods). [R §4]
- Hosting: "Calling an NVIDIA model through Token Factory ... satisfies this - the rest of your app (web frontend, unrelated backend processing) doesn't also need to be hosted on Nebius AI Cloud." [F]
- **Disqualifier:** an NVIDIA model reached through another provider does not count. "Using an NVIDIA open-source model through a different provider (HuggingFace, OpenRouter, etc.) wouldn't satisfy the platform requirement, and there's no approved workaround" [F].

## 4. Eligible NVIDIA models

- **The Rules give no exhaustive list.** They require "at least one NVIDIA open source model" [R §4].
- Kickoff update: "at least one NVIDIA open source model (Nemotron, GR00T, Cosmos, or Sonic)" [U-K].
- The Best Apps and Agents track names specific models: "Power it with Nemotron models on Nebius through Token Factory. Reach for **Nemotron 3 Ultra** when you need serious reasoning, and let **Nano or Super** handle the fast, everyday calls" [R §4][H].
- FAQ: NVIDIA Alpamayo "or other NVIDIA open models beyond Nemotron/GR00T/Cosmos/Sonic" are "Yes, allowed" (asked in the context of the Physical AI track) [F].
- The Judging Criteria on the overview page say "NVIDIA Nemotron", while the Rules say "NVIDIA Nemotron or other NVIDIA open source models" [H][R §6]. **Using Nemotron is the safest choice.**
- For the exact model IDs currently served, see `api-capabilities.md`.

## 5. Tracks and prizes

Tracks [R §4][H]:

1. Coding and Agentic Engineering: "agents that write, run, and test code in Token Factory."
2. **Best Apps and Agents:** "Build any app or agent someone would actually use, from a productivity tool or copilot to a workflow that runs itself." Deploying on Nebius Serverless Endpoints or Jobs is "encouraged ... though neither is required."
3. Personal AI: an always-on private assistant with persistent memory and tools. NemoClaw, OpenShell, Hermes Agent and Nebius Serverless are suggested.
4. Physical AI: embodied or edge agents. The video needs ≥1 minute of hardware footage (or of the key modules if there is no hardware). Simulation is OK [F].

Judging guidance for Best Apps and Agents: "a single API call demo works; a multi-step autonomous workflow that chains tools end to end stands out more." [U-J]

Prizes [R §8][H][U-P]. The total is "$50,000+".

| Prize | Award | Qty |
|---|---|---|
| Grand Prize | $20,000 | 1 |
| 2nd Place | $10,000 | 1 |
| 3rd Place | $6,000 | 1 |
| Track winner (each of the 4 tracks, incl. Best Apps and Agents) | NVIDIA Jetson Orin Nano | 1 per track |
| Best Use of Tavily (bonus) | $3,000 | 1 |
| City Winner (Builders & Brews IRL attendees only) | $500 | 20 |
| Most Valuable Feedback | $100 + NVIDIA swag pack | 10 |

- **Stacking rule:** "Each Project is eligible for one (1) Overall Award OR one (1) Track Award and one (1) Bonus Award." [R §8]
- City Winner: attending in person is required ("Yes") [F]. The listed cities are Tokyo through LA, and **Madrid and Barcelona are not on the list** [R §8]. All events took place between 9 Sep and 13 Oct [RES]. NOT VERIFIED whether any event remains. This prize is effectively unavailable to us.

## 6. Tavily bonus

- Eligibility (verbatim): "All Eligible Submissions that make a **functional, runtime call to the Tavily API** as part of its solution." [R §8]
- No other criteria are published for "Best Use". NOT VERIFIED how it is judged beyond the general criteria.
- Credits: Tavily promo code **`BBDEVPOST`** [U-B]. The Builders Program adds $25 of Tavily credit [B].

## 7. Submission requirements (checklist) [R §4][H]

- [ ] A working Project that meets the Project Requirements and uses the required tools.
- [ ] **URL to a working demo, hosted application, or test build** (not required for Physical AI).
- [ ] A text description of features and functionality.
- [ ] A **public repo on GitHub, GitLab or Bitbucket** with all the source, assets and instructions needed to run it.
- [ ] An **open source license file** (e.g. Apache 2.0, MIT, MPL 2.0) that is "detectable and visible at the top of the repository page (in the About section)."
- [ ] A **README** with setup instructions and clear guidance for running the project.
- [ ] A highlight of "how you've used NVIDIA Nemotron or other NVIDIA open source models and where Token Factory accelerated your workflow and any other Nebius Tools or Services used."
- [ ] A **demo video "less than three (3) minutes"** that is public on **YouTube**. "Judges are not required to watch beyond three minutes". It must show the project functioning and must not use third-party trademarks or copyrighted music without permission.
- [ ] The chosen track.
- [ ] **Feedback** on Token Factory, AI Cloud and any NVIDIA tools or models used. This is required for every submission [U-W].
- [ ] If the project pre-existed: a written explanation of what was significantly updated.
- [ ] (Optional) The Builders & Brews city attended.
- [ ] Materials in English, or English translations [R §4].

**Testing access:** "The Entrant must make the Project available **free of charge and without any restriction**, for testing, evaluation and use by the Sponsor, Administrator and Judges **until the Judging Period ends**." If the site is private, login credentials go in the testing instructions [R §4]. In practice the **demo and its API credits must stay live until at least 15 Dec 2026, 12:00 PST**. Judges "may choose to judge based solely on the text description, images, and video" [R §4].

**Feedback form content** [U-W]: say what you used each tool for, what worked well, what needs work, how onboarding felt ("zero to hello world"), and whether you'd build with it again and why. "Be specific." The feedback itself is scored "based on the completeness, viability, and potential impact of the feedback" [R §6].

## 8. Judging [R §6][U-J]

- **Stage One (pass/fail):** "whether the ideas meet a baseline level of viability, in that the Project reasonably fits the theme and reasonably applies the required APIs/SDKs". Fitting the theme means "a genuine attempt at the track's stated goal, **not a superficial rebrand of an unrelated idea**."
- **Stage Two:** four **equally weighted** criteria, each "scored 1–5" [U-J]:
  1. **Technological Implementation:** "How well is the project built, and how effectively does it use Nebius Token Factory or AI Cloud model(s), and NVIDIA Nemotron or other NVIDIA open source models".
  2. **Design:** "a complete, coherent product experience not just a technical proof of concept".
  3. **Potential Impact:** "a credible, specific case for solving a real problem for a real audience ... based on what's demonstrated".
  4. **Quality of the Idea:** "a creative, non-obvious use of ... and does the team show genuine understanding of the problem space".
- Tie-break: criteria are compared in the order listed (Tech Implementation first) [R §6].
- There are 23 judges listed from NVIDIA, Nebius and Tavily [H].

## 9. Credits / promo

- **$25 Token Factory credits:** fill in the form at https://nebius.com/promo-code?utm_promo_event_code=2026-devpost-global-ai-hack&utm_promo_code_type=Token_Factory&utm_promo_activation_code=NEBIUS-DEVPOST-GLOBAL26 with the activation code **`NEBIUS-DEVPOST-GLOBAL26`** [RES][U-K].
- **Another $25 Token Factory credits** come from joining the free Nebius Builders Program (https://dev.nebius.com/builders) [RES]. The Builders page also lists $25 Tavily, $100 LangSmith, Toloka and Tandem credits, and a $1 certification [B].
- "the official promotional credits ... are Token Factory credits specifically; there isn't a separate published AI Cloud credit grant" [F].
- If the credits don't arrive, the FAQ says it is "handled case by case with Nebius", via Discord https://discord.com/invite/eXYTGhgnhK [F].
- Token Factory itself requires a bank card for onboarding and gives "$1 in trial credit, valid for 30 days" (see `api-capabilities.md`).

## 10. AI coding assistants

- The Rules don't mention AI coding assistants explicitly. NOT VERIFIED whether there is any formal policy.
- Official update: "You don't have to be a developer to win. **Pair with AI tools like Claude, Copilot, or Cursor** — your video and writeup matter just as much as the code." [U-W]
- Related IP clause: "An Entrant may contract with a third party for technical assistance to create the Submission provided the Submission components are solely the Entrant's work product and the result of the Entrant's ideas and creativity" [R §4].
- Open-source use is allowed if licenses are respected and the Submission "creates software that enhances and builds upon" it [R §4].

## 11. Pre-existing projects

- "Projects must be either newly created by the Entrant or, if the Entrant's Project existed prior to the Hackathon Submission Period, must have been **significantly updated after the start** of the Hackathon Submission Period" (26 Aug 2026), with a written explanation [R §4].
- Not allowed: projects developed "with financial or preferential support from the Sponsor or Administrator" (funding, contract, commercial license) [R §4].

## 12. Gotchas and disqualifiers

1. **Calling Nemotron via OpenRouter or HuggingFace instead of Token Factory fails Stage One** [F]. Every NVIDIA model call has to go to the Token Factory API.
2. The video **must be under 3 minutes**, on **YouTube**, public, with no copyrighted music [R §4].
3. The **license must be visible in the repo About section**. A public repo alone is not enough [R §4].
4. **Hide API keys.** Use env vars and `.gitignore`, and "check your repo before you submit" [U-W].
5. **"Make the required tools impossible to miss."** Name Token Factory and the NVIDIA model in the description and in Built With, and call them out "with audio" in the video [U-W].
6. Keep the demo free and unrestricted **until 15 Dec 2026**. Budget for Token Factory credits and rate limits during judging [R §4].
7. No changes are allowed after 30 Oct 18:00 Madrid [R §5].
8. Stage One rejects anything that looks like "a superficial rebrand of an unrelated idea" [R §6].
9. Tavily bonus: the call has to happen at runtime and be functional, not just appear in the code [R §8].
10. Prize stacking: max 1 Overall, OR 1 Track + 1 Bonus [R §8].
11. Winners must pass identity and role verification and return affidavits within 10 business days [R §8].
12. Submission materials must not include third-party trademarks without permission [R §4].
13. The video should be "a pitch, not a tutorial": problem, then the solution working, then who it is for, then how it uses Nebius and NVIDIA [U-W].
