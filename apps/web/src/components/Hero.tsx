"use client";

/** First-visit framing: one sentence of stakes, one obvious action. Disappears after the first incident. */
export function Hero({ onTruck, onDescribe, live }: { onTruck: () => void; onDescribe: () => void; live: boolean }) {
  return (
    <section aria-labelledby="hero-h" className="border-b border-line px-4 py-5 lg:px-6">
      <div className="flex flex-wrap items-end justify-between gap-x-10 gap-y-4">
        <div className="max-w-4xl">
          <h1 id="hero-h" className="font-display text-[2.1rem] leading-[0.95] font-extrabold tracking-wide sm:text-[3.4rem]">
            <span className="block">One late truck. Fifteen linked jobs.</span>
            <span className="block text-amber">Doors at 18:00.</span>
          </h1>
          <p className="mt-3 max-w-2xl text-[15px] text-muted">
            Break today&apos;s plan and watch the delay travel through it. {live ? "NVIDIA Nemotron on Nebius" : "A recovery agent"} proposes fixes, a
            constraint solver proves which ones really work, and you decide what changes.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={onTruck} className="rounded-lg bg-amber px-4 py-2.5 font-bold text-graphite hover:brightness-110">
            Delay the truck 35 min
          </button>
          <button type="button" onClick={onDescribe} className="rounded-lg border border-line px-4 py-2.5 font-semibold hover:border-porcelain">
            Describe your own incident
          </button>
        </div>
      </div>
    </section>
  );
}
