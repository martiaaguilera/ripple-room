---
name: submission-audit
description: Rule-by-rule hackathon compliance and honesty audit for Ripple Room's public materials (README, Devpost draft, demo script, docs). Use before publishing or editing any submission text or metric.
allowed-tools: Bash(git *) Bash(grep *)
---

# Submission audit

1. Rules (docs/research/rules-snapshot.md): live NVIDIA model via Nebius Token Factory at runtime; public
   repo with visible OSI licence; working public demo free for judges until 15 Dec 2026; YouTube video
   < 3 min, public, English, names NVIDIA Nemotron and Nebius; English description; feedback section.
2. Every number in README / docs/devpost-submission.md / docs/demo-script.md must trace to a file in
   `docs/evaluation/` or `docs/evidence/`. Flag any number without a source. One run per version: never
   claim statistical significance or that the agent is "better" overall.
3. Attribution: Claude Code is the dev tool only; runtime AI is Nemotron on Nebius. Mock output never
   described as live. Fictional scenario stated.
4. Secrets: `git grep -nE "NEBIUS_API_KEY=.{8,}|v1\.CmQK|Bearer [A-Za-z0-9]{20,}"` must be empty;
   `.env` files untracked.
5. Output a PASS / FIX / BLOCKED table with file:line references. Do not submit anything to Devpost.
