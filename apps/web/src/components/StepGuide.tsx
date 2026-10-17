import type { Phase } from "@/state/room";

const STEPS = ["See the plan", "Break it", "Recover with AI", "Compare and approve", "Done"] as const;

function stepOf(phase: Phase, shocked: boolean): number {
  switch (phase) {
    case "boot":
      return 0;
    case "ready":
      return shocked ? 4 : 0;
    case "impact":
      return 2;
    case "running":
      return 2;
    case "options":
      return 3;
    case "applied":
      return 4;
  }
}

/**
 * Where you are in the story. The next action itself always lives in the right-hand column.
 * On phones only the current step keeps its label, so the guide stays on one line.
 */
export function StepGuide({ phase, shocked }: { phase: Phase; shocked: boolean }) {
  const active = stepOf(phase, shocked);
  return (
    <nav aria-label="Progress" className="border-b border-line px-4 py-2 lg:px-6">
      <ol className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs sm:gap-x-5">
        {STEPS.map((label, i) => (
          <li key={label} aria-current={i === active ? "step" : undefined} className={`flex items-center gap-1.5 ${i === active ? "font-bold text-porcelain" : i < active ? "text-muted" : "text-faint"}`}>
            <span aria-hidden className={`grid h-5 w-5 place-items-center rounded-full text-[11px] ${i === active ? "bg-amber text-graphite" : i < active ? "bg-line-strong text-porcelain" : "border border-line-strong"}`}>
              {i < active ? "✓" : i + 1}
            </span>
            <span className={i === active ? "" : "max-sm:sr-only"}>{label}</span>
          </li>
        ))}
      </ol>
    </nav>
  );
}
