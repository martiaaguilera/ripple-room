"use client";

import { useId } from "react";
import type { Preferences, Scenario } from "@/lib/api/types";

type Level = Preferences["guest_experience"];

const LEVELS: { value: Level; label: string }[] = [
  { value: "protect", label: "Protect" },
  { value: "balanced", label: "Balance" },
  { value: "flexible", label: "Flexible" },
];

function Segmented({ label, value, onChange }: { label: string; value: Level; onChange: (v: Level) => void }) {
  return (
    <fieldset className="flex items-center justify-between gap-2">
      <legend className="sr-only">{label}</legend>
      <span className="text-xs text-muted" aria-hidden>
        {label}
      </span>
      <div className="inline-flex rounded-md border border-line p-0.5">
        {LEVELS.map((l) => (
          <label key={l.value} className={`cursor-pointer rounded px-2 py-0.5 text-xs ${value === l.value ? "bg-focus text-graphite font-bold" : "text-muted hover:text-porcelain"}`}>
            <input type="radio" name={label} value={l.value} checked={value === l.value} onChange={() => onChange(l.value)} className="sr-only" />
            {l.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/** Soft preferences only: they order verified options, they never relax hard constraints. */
export function PreferencesPanel({ scenario, value, onChange }: { scenario: Scenario; value: Preferences; onChange: (p: Preferences) => void }) {
  const set = (patch: Partial<Preferences>) => onChange({ ...value, ...patch, source: "structured" });
  const protectable = scenario.tasks.filter((t) => t.optional || t.min_duration != null);
  const protectedSet = new Set(value.protected_tasks ?? []);
  const protectId = useId();
  return (
    <div role="group" className="space-y-2" aria-label="Priorities">
      <Segmented label="Guest experience" value={value.guest_experience} onChange={(v) => set({ guest_experience: v })} />
      <Segmented label="Extra spend" value={value.spend} onChange={(v) => set({ spend: v })} />
      <Segmented label="Crew plan" value={value.crew_stability} onChange={(v) => set({ crew_stability: v })} />
      <div className="flex items-center justify-between gap-2 text-xs text-muted">
        <label htmlFor="budget">Budget cap (€)</label>
        <input
          id="budget"
          inputMode="numeric"
          value={value.budget_cap_cents == null ? "" : String(value.budget_cap_cents / 100)}
          onChange={(e) => {
            const n = e.target.value.replace(/[^0-9]/g, "");
            set({ budget_cap_cents: n ? Math.min(10000, Number(n)) * 100 : null });
          }}
          placeholder="none"
          className="w-20 rounded-md border border-line bg-raised px-2 py-1 text-right text-porcelain"
        />
      </div>
      <div className="flex items-center justify-between gap-2 text-xs text-muted">
        <label htmlFor="margin">Minutes spare before doors</label>
        <input
          id="margin"
          type="number"
          min={0}
          max={60}
          step={5}
          value={value.min_margin_minutes ?? 0}
          onChange={(e) => set({ min_margin_minutes: Math.max(0, Math.min(60, Number(e.target.value) || 0)) })}
          className="w-20 rounded-md border border-line bg-raised px-2 py-1 text-right text-porcelain"
        />
      </div>
      <div className="text-xs text-muted" role="group" aria-labelledby={protectId}>
        <span id={protectId}>Do not touch</span>
        <div className="mt-1 flex flex-wrap gap-1.5">
          {protectable.map((t) => {
            const on = protectedSet.has(t.id);
            return (
              <button
                key={t.id}
                type="button"
                aria-pressed={on}
                onClick={() => {
                  const next = new Set(protectedSet);
                  if (on) next.delete(t.id);
                  else next.add(t.id);
                  set({ protected_tasks: [...next] });
                }}
                className={`rounded-full border px-2 py-0.5 ${on ? "border-focus text-focus" : "border-line hover:text-porcelain"}`}
              >
                {t.label}
              </button>
            );
          })}
        </div>
      </div>
      <p className="text-[11px] leading-snug text-faint">
        These rank the verified options. They never bend the hard limits: doors at 18:00, skills, crew hours, one job per person at a time.
      </p>
    </div>
  );
}
