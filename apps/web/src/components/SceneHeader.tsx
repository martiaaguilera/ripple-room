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

/** The two numbers that matter, plus what happened in one or two plain sentences. */
export function SceneHeader({ room, story, title }: { room: RoomView; story: Story; title: string }) {
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
        {story.chain && <p className="text-muted">{story.chain}</p>}
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
