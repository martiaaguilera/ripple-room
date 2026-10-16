"use client";

import { useEffect, useMemo, useState } from "react";
import type { Scenario } from "@/lib/api/types";
import { clock } from "@/lib/format";
import { useReducedMotion } from "@/lib/useReducedMotion";
import type { RoomView, TaskView } from "@/lib/viewmodel";

/**
 * Illustrative floor plan of the venue, animated only by the plan's real times.
 * A scene clock sweeps the day: task bars fill as work progresses, crew tokens sit in
 * the room of the job they are doing, the truck reaches the dock at its scheduled
 * arrival and the doors open only if every job is done. Nothing here is telemetry.
 */

const W = 1000;
const H = 336;
const BUILDING = { x: 214, y: 10, w: 772, h: 318 };
const ROW = 40;
const CREW = { x: 12, y: 132, w: 190, h: 112 };
const SPEED_MIN_PER_S = 22;
const PERSON_KINDS = new Set(["person", "equipment"]);

const STATUS_COLOR: Record<string, string> = {
  on_track: "var(--signal)",
  at_risk: "var(--amber)",
  delayed: "var(--amber)",
  breach: "var(--coral)",
  blocked: "var(--coral)",
  deferred: "var(--faint)",
};

function initials(label: string): string {
  const words = label.replace(/technician/i, "tech").split(/\s+/);
  if (/^AV/i.test(label)) return label.toLowerCase().includes("backup") ? "AV2" : "AV";
  if (/trolley/i.test(label)) return label.toLowerCase().includes("rental") ? "T2" : "T1";
  return words
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

function Truck({ x, late }: { x: number; late: boolean }) {
  return (
    <g style={{ transform: `translate(${x}px, 284px)` }} className="scene-move" aria-hidden>
      <rect x={0} y={0} width={58} height={26} rx={3} fill="var(--raised)" stroke={late ? "var(--amber)" : "var(--muted)"} strokeWidth={1.5} />
      <rect x={58} y={8} width={18} height={18} rx={3} fill="var(--raised)" stroke={late ? "var(--amber)" : "var(--muted)"} strokeWidth={1.5} />
      <circle cx={14} cy={28} r={5} fill="var(--graphite)" stroke="var(--muted)" />
      <circle cx={62} cy={28} r={5} fill="var(--graphite)" stroke="var(--muted)" />
    </g>
  );
}

function TaskBar({ task, x, y, w, t, mode }: { task: TaskView; x: number; y: number; w: number; t: number; mode: RoomView["mode"] }) {
  const deferred = task.status === "deferred" || task.start == null || task.end == null;
  const start = task.start ?? 0;
  const end = task.end ?? 0;
  const progress = deferred ? 0 : Math.max(0, Math.min(1, (t - start) / Math.max(1, end - start)));
  const done = progress >= 1;
  const changed = Boolean(task.change && (task.shift || task.change.duration_to != null || task.change.reassigned.length));
  const color = mode === "preview" ? (changed ? "var(--focus)" : "var(--signal)") : (STATUS_COLOR[task.status] ?? "var(--signal)");
  const active = progress > 0 && progress < 1;
  const barW = w - 40;
  return (
    <g>
      {active && <rect x={x - 8} y={y - 4} width={w + 16} height={ROW - 4} rx={6} fill="var(--raised)" />}
      <text x={x} y={y + 10} fontSize={12} fill={active ? "var(--porcelain)" : "var(--muted)"} fontWeight={active ? 700 : 500}>
        {task.label}
      </text>
      <rect x={x} y={y + 17} width={barW} height={6} rx={3} fill="var(--graphite)" stroke="var(--line)" strokeWidth={0.75} strokeDasharray={deferred ? "3 3" : undefined} />
      {!deferred && <rect x={x} y={y + 17} width={barW * progress} height={6} rx={3} fill={color} opacity={done ? 0.55 : 1} />}
      <text x={x + w} y={y + 24} fontSize={11} fill={done ? "var(--faint)" : task.delay && task.delay > 0 && mode === "impact" ? "var(--amber)" : "var(--muted)"} textAnchor="end">
        {deferred ? "later" : done ? "done" : clock(start)}
      </text>
    </g>
  );
}

export function VenueScene({ scenario, room, rippleKey, previewKey }: { scenario: Scenario; room: RoomView; rippleKey: number; previewKey: string }) {
  const zones = useMemo(() => [...scenario.zones].sort((a, b) => a.order - b.order), [scenario]);
  const starts = room.tasks.flatMap((t) => (t.start != null ? [t.start] : []));
  const ends = room.tasks.flatMap((t) => (t.end != null ? [t.end] : []));
  const dayStart = Math.floor((Math.min(...starts) - 25) / 15) * 15;
  const dayEnd = Math.max(room.deadline, ...ends) + 10;

  const reduced = useReducedMotion();
  const [t, setT] = useState<number>(dayStart);
  const [playing, setPlaying] = useState(true);

  // Replay whenever the underlying plan changes (new incident, option preview, apply).
  const replayKey = `${rippleKey}|${previewKey}|${room.mode}`;
  const [seenKey, setSeenKey] = useState(replayKey);
  if (seenKey !== replayKey) {
    setSeenKey(replayKey);
    setT(dayStart);
    setPlaying(true);
  }

  // Reduced motion: no autoplay sweep, show the whole day at once.
  const effectivePlaying = playing && !reduced;
  const shownT = reduced && playing ? dayEnd : t;

  useEffect(() => {
    if (!effectivePlaying) return;
    let frame = 0;
    let prev: number | null = null;
    let travelled = 0;
    const span = dayEnd - dayStart;
    const step = (now: number) => {
      const dt = prev == null ? 0 : (now - prev) / 1000;
      prev = now;
      travelled += dt * SPEED_MIN_PER_S;
      setT((cur) => Math.min(dayEnd, cur + dt * SPEED_MIN_PER_S));
      if (travelled >= span) {
        setPlaying(false);
        return;
      }
      frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [effectivePlaying, dayEnd, dayStart]);

  const minute = Math.floor(shownT);
  const roomW = BUILDING.w / zones.length;
  const roomX = (i: number) => BUILDING.x + i * roomW;
  const zoneIndex = new Map(zones.map((z, i) => [z.id, i]));

  // Truck: approaches along the road and parks at the dock at its scheduled arrival.
  const truck = room.byId["truck-arrival"];
  const arrival = truck?.start ?? dayStart;
  const truckLate = (truck?.delay ?? 0) > 0 && room.mode !== "plan";
  // Waits at the road's far end, rolls in over the last 40 minutes, parks at the dock door.
  const approach = Math.max(0, Math.min(1, (minute - (arrival - 40)) / 40));
  const truckX = 6 + approach * (BUILDING.x - 96);

  // Crew tokens: in the room of the job they are doing right now, otherwise in the crew room.
  const resources = scenario.resources.filter((r) => PERSON_KINDS.has(r.kind));
  const busy = new Map<string, TaskView>();
  for (const task of room.tasks) {
    if (task.start == null || task.end == null || task.end === task.start) continue;
    if (minute >= task.start && minute < task.end) for (const rid of Object.values(task.assignments)) busy.set(rid, task);
  }
  const used = new Set(room.tasks.flatMap((t) => Object.values(t.assignments)));
  const tokens = resources.filter((r) => !r.standby || used.has(r.id));
  const perRoom = new Map<string, number>();
  let idleCount = 0;
  const placed = tokens.map((r) => {
    const task = busy.get(r.id);
    if (task) {
      const i = zoneIndex.get(task.zoneId) ?? 0;
      const n = perRoom.get(task.zoneId) ?? 0;
      perRoom.set(task.zoneId, n + 1);
      return { r, x: roomX(i) + 24 + n * 34, y: BUILDING.y + BUILDING.h - 24, task };
    }
    const n = idleCount++;
    return { r, x: CREW.x + 22 + (n % 5) * 36, y: CREW.y + 48 + Math.floor(n / 5) * 36, task: undefined };
  });

  const doorsTask = room.byId[scenario.deadline_task_id];
  const ready = room.readiness;
  const late = ready != null && ready > room.deadline;
  const doorsOpen = minute >= room.deadline && ready != null && ready <= room.deadline;
  const dockOpen = minute >= (room.byId["dock-open"]?.start ?? 0);

  return (
    <figure className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full min-w-[620px]" role="img" aria-label={`Illustrative venue scene at ${clock(minute)}. ${late ? `Doors would be ready at ${clock(ready!)}, after the ${clock(room.deadline)} opening.` : `Doors ready at ${ready != null ? clock(ready) : "unknown"}.`}`}>
        {/* road and dock apron */}
        <rect x={0} y={272} width={BUILDING.x} height={44} fill="#0e151d" />
        <line x1={0} x2={BUILDING.x} y1={294} y2={294} stroke="var(--line-strong)" strokeDasharray="14 12" />
        <text x={12} y={266} fontSize={11} fill="var(--faint)">
          Ring road
        </text>
        <Truck x={truckX} late={truckLate} />
        {truck?.start != null && (
          <text x={12} y={331} fontSize={11.5} fill={truckLate ? "var(--amber)" : "var(--muted)"} fontWeight={truckLate ? 700 : 400}>
            Truck due {clock(truck.start)}
            {truckLate ? ` (${truck.delay} min late)` : ""}
          </text>
        )}

        {/* building */}
        <rect x={BUILDING.x} y={BUILDING.y} width={BUILDING.w} height={BUILDING.h} rx={10} fill="#0c1219" stroke="var(--line-strong)" />
        {zones.map((z, i) => {
          const tasks = room.tasks.filter((tk) => tk.zoneId === z.id && !tk.milestone);
          const x = roomX(i);
          return (
            <g key={z.id}>
              {i > 0 && <line x1={x} x2={x} y1={BUILDING.y + 12} y2={BUILDING.y + BUILDING.h - 48} stroke="var(--line)" />}
              <text x={x + 14} y={BUILDING.y + 26} fontSize={13} fill="var(--muted)" className="font-display" style={{ fontWeight: 700, letterSpacing: "0.04em" }}>
                {z.label}
              </text>
              {tasks.map((task, k) => (
                <TaskBar key={task.id} task={task} x={x + 14} y={BUILDING.y + 40 + k * ROW} w={roomW - 28} t={minute} mode={room.mode} />
              ))}
            </g>
          );
        })}
        <line x1={BUILDING.x + 12} x2={BUILDING.x + BUILDING.w - 12} y1={BUILDING.y + BUILDING.h - 48} y2={BUILDING.y + BUILDING.h - 48} stroke="var(--line)" strokeDasharray="2 6" />

        {/* dock shutter */}
        <rect x={BUILDING.x - 4} y={274} width={8} height={40} fill={dockOpen ? "var(--signal)" : "var(--line-strong)"} />

        {/* entrance doors */}
        <g aria-hidden>
          <rect x={BUILDING.x + BUILDING.w - 5} y={120} width={10} height={80} fill={doorsOpen ? "var(--signal)" : late ? "var(--coral)" : "var(--amber)"} />
          <text x={BUILDING.x + BUILDING.w - 14} y={112} fontSize={12.5} textAnchor="end" fontWeight={700} fill={doorsOpen ? "var(--signal)" : late ? "var(--coral)" : "var(--amber)"}>
            {doorsOpen ? "Doors open" : `Doors ${clock(room.deadline)}`}
          </text>
          {doorsTask?.start != null && (
            <text x={BUILDING.x + BUILDING.w - 14} y={216} fontSize={12} textAnchor="end" fill={late ? "var(--coral)" : "var(--muted)"} fontWeight={late ? 700 : 400}>
              ready {clock(doorsTask.start)}
            </text>
          )}
        </g>

        {/* crew room */}
        <rect x={CREW.x} y={CREW.y} width={CREW.w} height={CREW.h} rx={8} fill="#0c1219" stroke="var(--line)" />
        <text x={CREW.x + 12} y={CREW.y + 20} fontSize={11.5} fill="var(--faint)">
          Crew room: free or waiting
        </text>
        {placed.map(({ r, x, y, task }) => (
          <g key={r.id} className="scene-move" style={{ transform: `translate(${x}px, ${y}px)` }}>
            <title>{task ? `${r.label}: ${task.label}` : `${r.label}: free`}</title>
            {r.kind === "equipment" ? (
              <rect x={-11} y={-11} width={22} height={22} rx={4} fill="var(--panel)" stroke={task ? "var(--porcelain)" : "var(--line-strong)"} />
            ) : (
              <circle r={13} fill={task ? "var(--raised)" : "var(--panel)"} stroke={task ? "var(--porcelain)" : "var(--line-strong)"} strokeWidth={task ? 1.6 : 1} />
            )}
            <text y={4} textAnchor="middle" fontSize={10.5} fontWeight={700} fill={task ? "var(--porcelain)" : "var(--faint)"}>
              {initials(r.label)}
            </text>
          </g>
        ))}

        {/* scene clock */}
        <text x={14} y={26} fontSize={12} fill="var(--faint)">
          Scene time
        </text>
        <text x={12} y={78} fontSize={56} fontWeight={800} className="font-display" fill="var(--porcelain)">
          {clock(minute)}
        </text>
        <text x={14} y={100} fontSize={11} fill="var(--faint)">
          Illustrative, driven by the
        </text>
        <text x={14} y={114} fontSize={11} fill="var(--faint)">
          plan&apos;s scheduled times
        </text>
      </svg>
      <figcaption className="flex flex-wrap items-center gap-3 px-3 pb-2 text-xs text-muted">
        <button type="button" onClick={() => {
            if (reduced) {
              setPlaying(false);
              setT(shownT >= dayEnd ? dayStart : dayEnd);
            } else if (shownT >= dayEnd) {
              setT(dayStart);
              setPlaying(true);
            } else setPlaying((p) => !p);
          }} className="rounded-md border border-line px-2.5 py-1 hover:border-porcelain">
          {effectivePlaying ? "Pause" : shownT >= dayEnd ? "Replay the day" : "Play"}
        </button>
        <label className="flex flex-1 items-center gap-2">
          <span className="sr-only">Scene time</span>
          <input
            type="range"
            min={dayStart}
            max={dayEnd}
            step={1}
            value={minute}
            onChange={(e) => {
              setPlaying(false);
              setT(Number(e.target.value));
            }}
            className="w-full accent-[var(--amber)]"
            aria-valuetext={clock(minute)}
          />
        </label>
        <span className="tabular-nums">
          {clock(dayStart)}–{clock(dayEnd)}
        </span>
      </figcaption>
    </figure>
  );
}
