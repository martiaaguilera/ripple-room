"use client";

import { clock } from "@/lib/format";
import type { Story } from "@/lib/story";
import { useTween } from "@/lib/useTween";
import type { RoomView } from "@/lib/viewmodel";

const CAPTION: Record<RoomView["mode"], string> = {
  plan: "Today's plan",
  impact: "If nobody acts",
  preview: "With the selected recovery",
};

function Moment({ label, minute, tone }: { label: string; minute: number | null; tone: string }) {
  return (
    <div>
      <div className="text-xs text-faint">{label}</div>
      <div className={`font-display text-2xl leading-none font-bold ${tone}`}>{minute != null ? clock(minute) : "—"}</div>
    </div>
  );
}

/** The two numbers that matter, plus what happened in one or two plain sentences. */
export function SceneHeader({
  room,
  story,
  title,
  beforeIncident,
  doNothing,
}: {
  room: RoomView;
  story: Story;
  title: string;
  beforeIncident: number | null;
  doNothing: number | null;
}) {
  const ready = useTween(room.readiness);
  const late = story.late;
  return (
    <div className="flex flex-wrap items-start gap-x-8 gap-y-3 border-b border-line px-4 py-3">
      <div className="min-w-[230px]">
        <h2 id="scene-h" className="text-sm text-muted">
          {title}: <span className="text-porcelain">{CAPTION[room.mode]}</span>
        </h2>
        <div className="mt-1 flex items-end gap-6" aria-live="polite">
          <div>
            <div className="text-xs text-faint">Ready for doors</div>
            <div className={`font-display text-5xl leading-none font-extrabold ${late ? "text-coral" : "text-porcelain"}`}>{ready != null ? clock(ready) : "—"}</div>
          </div>
          <div>
            <div className="text-xs text-faint">Doors open</div>
            <div className="font-display text-5xl leading-none font-extrabold text-amber">{clock(room.deadline)}</div>
          </div>
        </div>
      </div>
      <div className="min-w-0 flex-1 basis-80 text-[15px] leading-snug" aria-live="polite">
        {story.cause && <p className="font-semibold text-porcelain">{story.cause}</p>}
        {room.mode === "preview" ? (
          <div className="mt-2 flex flex-wrap gap-x-6 gap-y-2" aria-label="Before and after">
            <Moment label="Before the incident" minute={beforeIncident} tone="text-muted" />
            <Moment label="If nobody acts" minute={doNothing} tone={doNothing != null && doNothing > room.deadline ? "text-coral" : "text-muted"} />
            <Moment label="With this recovery" minute={room.readiness} tone={late ? "text-coral" : "text-signal"} />
          </div>
        ) : (
          story.chain && <p className="text-muted">{story.chain}</p>
        )}
        <p className={`mt-1 font-semibold ${late ? "text-coral" : "text-signal"}`}>
          <span aria-hidden className="mr-1.5">
            {late ? "▲" : "●"}
          </span>
          {story.outcome}
        </p>
      </div>
    </div>
  );
}
