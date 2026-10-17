---
name: visual-qa
description: Capture and review real browser screenshots of the Ripple Room journey (desktop 1440x900 and mobile 390x844) and run the Playwright E2E suite. Use after any UI change, before claiming a visual or UX improvement.
allowed-tools: Bash(npx playwright *) Bash(node *) Bash(npx next build*) Bash(curl *)
---

# Visual QA for Ripple Room

Never claim a UI change works without looking at it.

1. Make sure a mock API and the web app are running:
   - API: `cd services/api && AI_MODE=mock NEBIUS_API_KEY= CORS_ORIGINS=http://localhost:3000 uv run uvicorn app.main:app --port 8000`
   - Web: `cd apps/web && NEXT_PUBLIC_API_BASE=http://localhost:8000 npx next dev --port 3000`
   - If port 3000/8000 is taken by a stale process, reuse it only after `curl localhost:8000/api/health` shows `"mode":"mock"`.
2. Screenshot journey (from `apps/web`, so `@playwright/test` resolves):
   `cp ../../scripts/shoot.mjs shoot.tmp.mjs && node shoot.tmp.mjs <scratchpad>/shots && rm shoot.tmp.mjs`
   It saves ready / intake / impact / options / applied for desktop and mobile and prints console errors.
3. Read every screenshot. Check: first screen explains itself in 10 s; no clipped or overlapping text;
   status not conveyed by colour alone; mobile has no horizontal page overflow and the next action is
   one scroll away; nothing labelled as Nemotron unless it came from a live model.
4. Production-equivalent E2E: `npx next build && npx playwright test` (serves the static build from
   FastAPI with the mock agent). All tests must pass.
5. Report what you saw, with file paths of the screenshots. Never use live inference for QA.
