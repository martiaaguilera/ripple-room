/** Who this is for and why verification matters. No market claims, no invented numbers. */
export function WhyItMatters() {
  return (
    <section aria-labelledby="why-h" className="rounded-2xl border border-line px-4 py-4">
      <h2 id="why-h" className="font-display text-xl font-bold">
        See the consequences before they happen. Act on plans you can trust.
      </h2>
      <div className="mt-3 grid gap-4 text-sm text-muted sm:grid-cols-3">
        <p>
          <span className="font-semibold text-porcelain">For the people who run the day.</span> Stage managers, event coordinators, festival and
          production crews: a fixed opening time, a dozen linked jobs and a handful of people.
        </p>
        <p>
          <span className="font-semibold text-porcelain">One delay is never one delay.</span> A late truck pushes unloading, rigging, lighting,
          soundcheck and the safety walk. Spreadsheets hide that chain; this room draws it.
        </p>
        <p>
          <span className="font-semibold text-porcelain">The AI proposes, the solver checks, you decide.</span> Every fix the agent suggests is re-checked
          against every hard rule before you see it, and nothing changes until you approve it.
        </p>
      </div>
      <p className="mt-3 text-[11px] text-faint">The venue, crew and costs shown are a fictional demonstration scenario.</p>
    </section>
  );
}
