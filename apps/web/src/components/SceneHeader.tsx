"use client";

import { Fragment } from "react";
import { clock, doorsGap, type GapTone } from "@/lib/format";
import type { Story } from "@/lib/story";
import { useTween } from "@/lib/useTween";
import type { RoomView } from "@/lib/viewmodel";

const CAPTION: Record<RoomView["mode"], string> = {
  plan: "Today's plan",
  impact: "If nobody acts",
  preview: "With the selected recovery",
};

const MODE_TONE: Record<RoomView["mode"], string> = {
  plan: "border-line-strong text-muted",
  impact: "border-coral/50 text-coral",
  preview: "border-focus/60 text-focus",
};

const GAP_STYLE: Record<GapTone, { chip: string; line: string; glyph: string }> = {
  late: { chip: "border-coral/60 bg-[#2a1519] text-coral", line: "border-coral/70 border-dashed", glyph: "▲" },
  blocked: { chip: "border-coral/60 bg-[#2a1519] text-coral", line: "border-coral/70 border-dashed", glyph: "■" },
  tight: { chip: "border-amber/60 bg-[#251c0e] text-amber", line: "border-amber/60", glyph: "●" },
  spare: { chip: "border-signal/50 bg-[#0d2422] text-signal", line: "border-signal/50", glyph: "●" },
};

function Clock({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="shrink-0">
      <div className="text-xs text-muted">{label}</div>
      <div className={`font-display text-[2.75rem] leading-none font-extrabold sm:text-6xl ${tone}`}>{value}</div>
    </div>
  );
}

/** The gap between "ready" and "doors open", stated in words on the line that joins them. */
function Gap({ readiness, deadline }: { readiness: number | null; deadline: number }) {
  const gap = doorsGap(readiness, deadline);
  const style = GAP_STYLE[gap.tone];
  return (
    <div className="relative flex min-w-[6.5rem] flex-1 items-center self-stretch pt-4" aria-hidden>
      <span className={`absolute inset-x-0 top-[calc(50%+0.5rem)] border-t-2 ${style.line}`} />
      <span className={`relative mx-auto rounded-full border px-2.5 py-1 text-xs font-bold whitespace-nowrap sm:text-sm ${style.chip}`}>
        <span className="mr-1">{style.glyph}</span>
        {gap.text}
      </span>
    </div>
  );
}

function Moment({ label, minute, tone }: { label: string; minute: number | null; tone: string }) {
  return (
    <div>
      <div className="text-xs text-muted">{label}</div>
      <div className={`font-display text-2xl leading-none font-bold ${tone}`}>{minute != null ? clock(minute) : "—"}</div>
    </div>
  );
}

/** The two numbers that matter, the verdict between them, and what happened in plain sentences. */
export function SceneHeader({
  room,
  story,
  beforeIncident,
  doNothing,
}: {
  room: RoomView;
  story: Story;
  beforeIncident: number | null;
  doNothing: number | null;
}) {
  const ready = useTween(room.readiness);
  const late = story.late;
  const moments = [
    { label: "Before the incident", minute: beforeIncident, tone: "text-muted" },
    { label: "If nobody acts", minute: doNothing, tone: doNothing != null && doNothing > room.deadline ? "text-coral" : "text-muted" },
    { label: "With this recovery", minute: room.readiness, tone: late ? "text-coral" : "text-signal" },
  ];
  return (
    <div className="flex flex-wrap items-start gap-x-10 gap-y-4 border-b border-line px-4 py-4">
      <div className="w-full sm:w-auto sm:min-w-[25rem]">
        <h2 id="scene-h" className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-bold ${MODE_TONE[room.mode]}`}>
          <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-current" />
          {CAPTION[room.mode]}
        </h2>
        <div className="mt-3 flex items-stretch gap-3" aria-live="polite">
          <Clock label="Ready for doors" value={ready != null ? clock(ready) : "—"} tone={late || room.readiness == null ? "text-coral" : "text-porcelain"} />
          <Gap readiness={room.readiness} deadline={room.deadline} />
          <Clock label="Doors open" value={clock(room.deadline)} tone="text-amber" />
        </div>
      </div>
      <div className="min-w-0 flex-1 basis-80 text-[15px] leading-snug" aria-live="polite">
        {story.cause && <p className="font-semibold text-porcelain">{story.cause}</p>}
        {room.mode === "preview" ? (
          <ol className="mt-2 grid max-w-md grid-cols-[1fr_auto_1fr_auto_1fr] items-end gap-x-2" aria-label="Before and after">
            {moments.map((m, i) => (
              <Fragment key={m.label}>
                {i > 0 && (
                  <li aria-hidden className="pb-0.5 text-muted">
                    →
                  </li>
                )}
                <li>
                  <Moment {...m} />
                </li>
              </Fragment>
            ))}
          </ol>
        ) : (
          story.chain && <p className="text-muted">{story.chain}</p>
        )}
        <p className={`mt-2 font-semibold ${late ? "text-coral" : "text-signal"}`}>
          <span aria-hidden className="mr-1.5">
            {late ? "▲" : "●"}
          </span>
          {story.outcome}
        </p>
      </div>
    </div>
  );
}
