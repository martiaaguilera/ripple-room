"use client";

import { useState } from "react";
import type { Interpretation, Preferences, ShockPreset } from "@/lib/api/types";
import { eur } from "@/lib/format";

const EXAMPLES = [
  "Driver just called: stuck on the ring road, 40 more minutes. Sponsors need the vendor tables, keep spend under €60.",
  "Our AV tech has to leave 15:30 to 16:30 for another venue. No extra spend today.",
];

const LEVEL: Record<string, string> = { protect: "protect", balanced: "balance", flexible: "flexible" };

function prefChips(p: Preferences): string[] {
  const chips: string[] = [];
  if (p.guest_experience !== "balanced") chips.push(`Guest experience: ${LEVEL[p.guest_experience]}`);
  if (p.spend !== "balanced") chips.push(`Extra spend: ${LEVEL[p.spend]}`);
  if (p.crew_stability !== "balanced") chips.push(`Crew plan: ${LEVEL[p.crew_stability]}`);
  if (p.budget_cap_cents != null) chips.push(`Budget up to ${eur(p.budget_cap_cents)}`);
  if (p.min_margin_minutes) chips.push(`At least ${p.min_margin_minutes} min spare`);
  for (const t of p.protected_tasks ?? []) chips.push(`Protect ${t.replace(/-/g, " ")}`);
  return chips;
}

function ConfirmCard({
  result,
  busy,
  onConfirm,
  onDiscard,
}: {
  result: Interpretation;
  busy: boolean;
  onConfirm: () => void;
  onDiscard: () => void;
}) {
  const chips = prefChips(result.preferences);
  return (
    <div className="rounded-xl border border-focus/50 bg-[#111a28] p-3 text-sm" role="region" aria-label="Interpretation to confirm">
      <p className="text-xs text-focus">
        {result.live ? "Read by Nemotron on Nebius" : "Read by the mock interpreter (no model call)"}
        {result.request_id ? `, request ${result.request_id.slice(0, 8)}` : ""}
      </p>
      {result.incidents.length > 0 ? (
        <ul className="mt-2 space-y-1.5">
          {result.incidents.map((i, n) => (
            <li key={n}>
              <span className="font-semibold">{i.restatement}</span>
              {i.evidence && <span className="block text-xs text-muted">from “{i.evidence}”</span>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 font-semibold text-amber">No incident I can map to this plan.</p>
      )}
      {result.rejected.map((r, n) => (
        <p key={n} className="mt-1.5 text-xs text-coral">
          Not applied: {r.reason}
        </p>
      ))}
      {result.unclear.map((u, n) => (
        <p key={n} className="mt-1 text-xs text-amber">
          {u}
        </p>
      ))}
      {chips.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Priorities understood">
          {chips.map((c) => (
            <li key={c} className="rounded-full border border-line px-2 py-0.5 text-xs text-muted">
              {c}
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={onConfirm}
          disabled={busy || result.incidents.length === 0}
          className="flex-1 rounded-lg bg-amber px-3 py-2 text-sm font-bold text-graphite hover:brightness-110 disabled:opacity-50"
        >
          {busy ? "Applying…" : result.incidents.length > 1 ? `Apply ${result.incidents.length} incidents` : "Apply to the plan"}
        </button>
        <button type="button" onClick={onDiscard} className="rounded-lg border border-line px-3 py-2 text-sm hover:border-porcelain">
          Discard
        </button>
      </div>
    </div>
  );
}

export function IncidentDesk({
  presets,
  disabled,
  intake,
  onInterpret,
  onConfirm,
  onDiscard,
  onPreset,
  live,
}: {
  presets: ShockPreset[];
  disabled: boolean;
  intake: { status: string; result: Interpretation | null; error: string | null };
  onInterpret: (text: string) => void;
  onConfirm: (result: Interpretation) => void;
  onDiscard: () => void;
  onPreset: (id: string) => void;
  live: boolean;
}) {
  const [text, setText] = useState("");
  const interpreting = intake.status === "interpreting";
  return (
    <section aria-labelledby="break-h" className="space-y-3">
      <div>
        <h2 id="break-h" className="font-display text-2xl font-bold">
          Break the plan
        </h2>
        <p className="mt-0.5 text-sm text-muted">Say what happened in your own words, or pick a rehearsed incident.</p>
      </div>

      {intake.status === "ready" && intake.result ? (
        <ConfirmCard result={intake.result} busy={disabled} onConfirm={() => onConfirm(intake.result!)} onDiscard={onDiscard} />
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (text.trim().length >= 3) onInterpret(text.trim());
          }}
          className="space-y-2"
        >
          <label htmlFor="incident" className="sr-only">
            Describe the incident
          </label>
          <textarea
            id="incident"
            value={text}
            onChange={(e) => setText(e.target.value.slice(0, 600))}
            rows={3}
            placeholder="e.g. The truck is stuck in traffic, 40 more minutes."
            className="w-full resize-none rounded-lg border border-line bg-raised px-2.5 py-2 text-sm placeholder:text-faint focus:border-amber"
          />
          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={disabled || interpreting || text.trim().length < 3}
              className="rounded-lg border border-amber/70 px-3 py-1.5 text-sm font-semibold text-amber hover:bg-amber/10 disabled:opacity-50"
            >
              {interpreting ? "Reading…" : "Read the incident"}
            </button>
            <button type="button" onClick={() => setText(EXAMPLES[text === EXAMPLES[0] ? 1 : 0]!)} className="text-xs text-muted underline underline-offset-2 hover:text-porcelain">
              Example
            </button>
          </div>
          {!live && <p className="text-[11px] text-faint">Mock mode: a keyword reader stands in for the model.</p>}
          {intake.status === "failed" && (
            <p role="alert" className="text-xs text-coral">
              {intake.error} Use a rehearsed incident below instead.
            </p>
          )}
        </form>
      )}

      <ul className="grid gap-1.5" aria-label="Rehearsed incidents">
        {presets.map((p) => (
          <li key={p.id}>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onPreset(p.id)}
              className="group w-full rounded-lg border border-line bg-raised px-3 py-2 text-left transition-colors hover:border-amber disabled:cursor-not-allowed disabled:opacity-50"
            >
              <span className="block text-[14px] font-semibold group-hover:text-amber">{p.title}</span>
              <span className="block text-xs text-muted">{p.subtitle}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
