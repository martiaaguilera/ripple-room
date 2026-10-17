"use client";

/** The first action, impossible to miss. Disappears once the plan has been broken. */
export function StartCard({ onTruck, disabled }: { onTruck: () => void; disabled: boolean }) {
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
    </section>
  );
}
