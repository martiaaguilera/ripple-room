"use client";

import type { Health } from "@/lib/api/types";
import { modelName } from "./RecoveryPanel";

/** Who does what, named before anything happens: the model proposes, the solver decides, you approve. */
function Roles({ health }: { health: Health | null }) {
  const live = health?.ai.mode === "live";
  const agent = live && health ? `${modelName(health.ai.planner_model)} on Nebius Token Factory` : "Simulated agent (no model calls)";
  const rows: [string, string][] = [
    [agent, "reads the situation and proposes fixes."],
    ["Constraint solver (OR-Tools CP-SAT)", "checks every fix. Only it can say a plan holds."],
    ["You", "compare the verified options and approve one, or none."],
  ];
  return (
    <dl className="mt-3 space-y-1 text-xs text-muted">
      {rows.map(([who, what]) => (
        <div key={who}>
          <dt className="inline font-semibold text-porcelain">{who}</dt> <dd className="inline">{what}</dd>
        </div>
      ))}
    </dl>
  );
}

/** The first action, impossible to miss. Disappears once the plan has been broken. */
export function StartCard({ onTruck, disabled, health }: { onTruck: () => void; disabled: boolean; health: Health | null }) {
  return (
    <section aria-labelledby="start-h" className="rounded-2xl border border-amber/50 bg-[#17130b] p-4">
      <h2 id="start-h" className="font-display text-[1.7rem] leading-tight font-extrabold">
        Every job in this plan is connected.
      </h2>
      <p className="mt-1 text-sm text-muted">Break one thing and watch the delay ripple through to the doors.</p>
      <button
        type="button"
        onClick={onTruck}
        disabled={disabled}
        className="mt-3 w-full rounded-xl bg-amber px-4 py-3 text-left text-[17px] leading-snug font-bold text-graphite hover:brightness-110 disabled:opacity-60"
      >
        What if the truck arrives 35 minutes late?
      </button>
      <Roles health={health} />
    </section>
  );
}
