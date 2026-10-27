"use client";

import { useEffect, useMemo, useState } from "react";
import type { Scenario, Zone } from "@/lib/api/types";
import { clock } from "@/lib/format";
import { isChanged, roomLine, sceneFrame, sceneSpan, taskProgress, type RoomTagTone, type SceneFrame, type SceneToken } from "@/lib/scene";
import { setMotionOverride, useMotion } from "@/lib/useReducedMotion";
import type { RoomView, TaskView } from "@/lib/viewmodel";

/**
 * Illustrative floor plan of the venue, animated only by the plan's real times.
 * A scene clock sweeps the day: task bars fill as work progresses, crew tokens sit in
 * the room of the job they are doing, the truck reaches the dock at its scheduled
 * arrival and the doors open only if every job is done. Nothing here is telemetry.
 *
 * Wide screens get the floor plan; phones get the same building turned on its side and read
 * top to bottom, in the order the day flows: road, dock, rooms, doors.
 */

const W = 1000;
const H = 336;
const BUILDING = { x: 214, y: 10, w: 772, h: 318 };
const ROW = 40;
const CREW = { x: 12, y: 132, w: 190, h: 112 };
const SPEED_MIN_PER_S = 22;

const STATUS_COLOR: Record<string, string> = {
  on_track: "var(--signal)",
  at_risk: "var(--amber)",
  delayed: "var(--amber)",
  breach: "var(--coral)",
  blocked: "var(--coral)",
  deferred: "var(--faint)",
};

const TAG_TONE: Record<Exclude<RoomTagTone, null>, string> = {
  late: "border-amber/50 text-amber",
  breach: "border-coral/50 text-coral",
  changed: "border-focus/50 text-focus",
};

function barColor(task: TaskView, mode: RoomView["mode"]): string {
  return mode === "preview" ? (isChanged(task) ? "var(--focus)" : "var(--signal)") : (STATUS_COLOR[task.status] ?? "var(--signal)");
}

function doorsColor(doors: SceneFrame["doors"]): string {
  return doors.open ? "var(--signal)" : doors.late ? "var(--coral)" : "var(--amber)";
}

function Truck({ x, late }: { x: number; late: boolean }) {
  return (
    <g style={{ transform: `translate(${x}px, 284px)` }} className="scene-move" aria-hidden>
      <TruckShape late={late} />
    </g>
  );
}

function TruckShape({ late }: { late: boolean }) {
  const stroke = late ? "var(--amber)" : "var(--muted)";
  return (
    <>
      <rect x={0} y={0} width={58} height={26} rx={3} fill="var(--raised)" stroke={stroke} strokeWidth={1.5} />
      <rect x={58} y={8} width={18} height={18} rx={3} fill="var(--raised)" stroke={stroke} strokeWidth={1.5} />
      <circle cx={14} cy={28} r={5} fill="var(--graphite)" stroke="var(--muted)" />
      <circle cx={62} cy={28} r={5} fill="var(--graphite)" stroke="var(--muted)" />
    </>
  );
}

function TaskBar({ task, x, y, w, t, mode }: { task: TaskView; x: number; y: number; w: number; t: number; mode: RoomView["mode"] }) {
  const { deferred, progress, done, active } = taskProgress(task, t);
  const color = barColor(task, mode);
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
        {deferred ? "later" : done ? "done" : clock(task.start ?? 0)}
      </text>
    </g>
  );
}

interface LayoutProps {
  scenario: Scenario;
  room: RoomView;
  zones: Zone[];
  frame: SceneFrame;
  minute: number;
  rippleKey: number;
}

/** Wave of the cascade that first reaches a room (impact mode only), and whether it breaks the deadline there. */
function roomWave(tasks: TaskView[], mode: RoomView["mode"]): { first: number | null; hot: boolean } {
  const waves = mode === "impact" ? tasks.flatMap((tk) => (tk.wave != null && tk.status !== "on_track" ? [tk.wave] : [])) : [];
  return { first: waves.length ? Math.min(...waves) : null, hot: tasks.some((tk) => tk.status === "breach" || tk.status === "blocked") };
}

function FloorPlan({ scenario, room, zones, frame, minute, rippleKey }: LayoutProps) {
  const roomW = BUILDING.w / zones.length;
  const roomX = (i: number) => BUILDING.x + i * roomW;
  const zoneIndex = new Map(zones.map((z, i) => [z.id, i]));
  const truckX = 6 + frame.truck.approach * (BUILDING.x - 96);

  const perRoom = new Map<string, number>();
  let idleCount = 0;
  const placed = frame.tokens.map((tok) => {
    if (tok.task) {
      const i = zoneIndex.get(tok.task.zoneId) ?? 0;
      const n = perRoom.get(tok.task.zoneId) ?? 0;
      perRoom.set(tok.task.zoneId, n + 1);
      return { tok, x: roomX(i) + 24 + n * 34, y: BUILDING.y + BUILDING.h - 24 };
    }
    const n = idleCount++;
    return { tok, x: CREW.x + 22 + (n % 5) * 36, y: CREW.y + 48 + Math.floor(n / 5) * 36 };
  });
  const doorsTask = room.byId[scenario.deadline_task_id];
  const doorColor = doorsColor(frame.doors);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full min-w-[620px]" aria-hidden>
      {/* road and dock apron */}
      <rect x={0} y={272} width={BUILDING.x} height={44} fill="#0e151d" />
      <line x1={0} x2={BUILDING.x} y1={294} y2={294} stroke="var(--line-strong)" strokeDasharray="14 12" />
      <text x={12} y={266} fontSize={11} fill="var(--faint)">
        Ring road
      </text>
      <Truck x={truckX} late={frame.truck.late} />
      {frame.truck.due != null && (
        <text x={12} y={331} fontSize={11.5} fill={frame.truck.late ? "var(--amber)" : "var(--muted)"} fontWeight={frame.truck.late ? 700 : 400}>
          Truck due {clock(frame.truck.due)}
          {frame.truck.late ? ` (${frame.truck.delay} min late)` : ""}
        </text>
      )}

      {/* building */}
      <rect x={BUILDING.x} y={BUILDING.y} width={BUILDING.w} height={BUILDING.h} rx={10} fill="#0c1219" stroke="var(--line-strong)" />
      {zones.map((z, i) => {
        const tasks = room.tasks.filter((tk) => tk.zoneId === z.id && !tk.milestone);
        const x = roomX(i);
        const { first, hot } = roomWave(tasks, room.mode);
        return (
          <g key={z.id}>
            {first != null && (
              <rect
                key={`hit-${rippleKey}`}
                x={x + 2}
                y={BUILDING.y + 2}
                width={roomW - 4}
                height={BUILDING.h - 52}
                rx={8}
                fill={hot ? "var(--coral)" : "var(--amber)"}
                className="room-hit"
                style={{ "--wave-delay": `${first * 240}ms` } as React.CSSProperties}
              />
            )}
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
      <rect x={BUILDING.x - 4} y={274} width={8} height={40} fill={frame.dockOpen ? "var(--signal)" : "var(--line-strong)"} />

      {/* entrance doors */}
      <g>
        <rect x={BUILDING.x + BUILDING.w - 5} y={120} width={10} height={80} fill={doorColor} />
        <text x={BUILDING.x + BUILDING.w - 14} y={112} fontSize={12.5} textAnchor="end" fontWeight={700} fill={doorColor}>
          {frame.doors.open ? "Doors open" : `Doors ${clock(room.deadline)}`}
        </text>
        {doorsTask?.start != null && (
          <text x={BUILDING.x + BUILDING.w - 14} y={216} fontSize={12} textAnchor="end" fill={frame.doors.late ? "var(--coral)" : "var(--muted)"} fontWeight={frame.doors.late ? 700 : 400}>
            ready {clock(doorsTask.start)}
          </text>
        )}
      </g>

      {/* crew room */}
      <rect x={CREW.x} y={CREW.y} width={CREW.w} height={CREW.h} rx={8} fill="#0c1219" stroke="var(--line)" />
      <text x={CREW.x + 12} y={CREW.y + 20} fontSize={11.5} fill="var(--faint)">
        Crew room: free or waiting
      </text>
      {placed.map(({ tok, x, y }) => (
        <g key={tok.id} className="scene-move" style={{ transform: `translate(${x}px, ${y}px)` }}>
          <title>{tok.task ? `${tok.label}: ${tok.task.label}` : `${tok.label}: free`}</title>
          {tok.kind === "equipment" ? (
            <rect x={-11} y={-11} width={22} height={22} rx={4} fill="var(--panel)" stroke={tok.task ? "var(--porcelain)" : "var(--line-strong)"} />
          ) : (
            <circle r={13} fill={tok.task ? "var(--raised)" : "var(--panel)"} stroke={tok.task ? "var(--porcelain)" : "var(--line-strong)"} strokeWidth={tok.task ? 1.6 : 1} />
          )}
          <text y={4} textAnchor="middle" fontSize={10.5} fontWeight={700} fill={tok.task ? "var(--porcelain)" : "var(--faint)"}>
            {tok.initials}
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
  );
}

/** A crew member (round) or a piece of kit (square), bright when working, dim when free. */
function Token({ tok }: { tok: SceneToken }) {
  const busy = tok.task != null;
  return (
    <span
      title={busy ? `${tok.label}: ${tok.task!.label}` : `${tok.label}: free`}
      className={`token-in grid h-7 min-w-7 place-items-center px-1 text-xs leading-none font-bold ${tok.kind === "equipment" ? "rounded-md" : "rounded-full"} ${busy ? "border-[1.5px] border-porcelain bg-raised text-porcelain" : "border border-line-strong bg-panel text-muted"}`}
    >
      {tok.initials}
    </span>
  );
}

/** Phone layout: the building on its side. Same data as the floor plan, real text sizes, no sideways scroll. */
function Stacked({ scenario, room, zones, frame, minute, rippleKey }: LayoutProps) {
  const idle = frame.tokens.filter((t) => !t.task);
  const doorsTask = room.byId[scenario.deadline_task_id];
  const doorColor = doorsColor(frame.doors);
  const ready = doorsTask?.start ?? null;
  const lateBy = ready != null ? ready - room.deadline : null;
  // Road strip in its own coordinate space: the truck rolls left to right and parks at the dock shutter.
  const ROAD_W = 340;
  const truckX = 4 + frame.truck.approach * (ROAD_W - 92);

  return (
    <div className="space-y-2 px-3 pt-2.5 pb-3">
      <div className="rounded-lg border border-line bg-[#0e151d] px-3 py-1.5">
        <div className="flex items-baseline justify-between gap-2 text-xs">
          {frame.truck.due != null && (
            <span className={frame.truck.late ? "font-bold text-amber" : "text-muted"}>
              {frame.truck.late && <span aria-hidden>▲ </span>}
              Truck due {clock(frame.truck.due)}
              {frame.truck.late ? `, ${frame.truck.delay} min late` : ""}
            </span>
          )}
          <span className={frame.dockOpen ? "text-signal" : "text-muted"}>{frame.dockOpen ? "Dock open" : "Dock shut"}</span>
        </div>
        <svg viewBox={`0 0 ${ROAD_W} 36`} className="mt-0.5 block h-auto w-full" aria-hidden>
          <line x1={0} x2={ROAD_W - 10} y1={20} y2={20} stroke="var(--line-strong)" strokeDasharray="14 12" />
          <g style={{ transform: `translate(${truckX}px, 2px)` }} className="scene-move">
            <TruckShape late={frame.truck.late} />
          </g>
          <rect x={ROAD_W - 8} y={0} width={8} height={36} rx={1} fill={frame.dockOpen ? "var(--signal)" : "var(--line-strong)"} />
        </svg>
      </div>

      <div className="flex min-h-11 flex-wrap items-center gap-x-3 gap-y-1.5 rounded-lg border border-line px-3 py-1.5">
        <span className="text-[13px] text-muted">Crew room</span>
        {idle.length ? (
          <span className="flex flex-wrap gap-1.5">
            {idle.map((tok) => (
              <Token key={`${tok.id}-idle`} tok={tok} />
            ))}
          </span>
        ) : (
          <span className="text-xs text-muted">everyone is on a job</span>
        )}
      </div>

      <ol className="overflow-hidden rounded-lg border border-line-strong bg-[#0c1219]">
        {zones.map((z) => {
          const tasks = room.tasks.filter((tk) => tk.zoneId === z.id && !tk.milestone);
          const here = frame.tokens.filter((tok) => tok.task?.zoneId === z.id);
          const line = roomLine(tasks, minute, room.mode);
          const { first, hot } = roomWave(tasks, room.mode);
          return (
            <li key={z.id} className="relative border-b border-line px-3 py-2 last:border-b-0">
              {first != null && (
                <span
                  key={`hit-${rippleKey}`}
                  className="room-hit absolute inset-0"
                  style={{ background: hot ? "var(--coral)" : "var(--amber)", "--wave-delay": `${first * 240}ms` } as React.CSSProperties}
                />
              )}
              <div className="relative flex min-h-7 items-center gap-3">
                <span className="w-[6.75rem] shrink-0 font-display text-base leading-tight font-bold tracking-wide text-porcelain">{z.label}</span>
                <span className="flex min-w-0 flex-1 gap-1">
                  {tasks.map((task) => {
                    const p = taskProgress(task, minute);
                    return (
                      <span
                        key={task.id}
                        title={task.label}
                        className={`relative h-1.5 flex-1 overflow-hidden rounded-full bg-graphite ${p.deferred ? "border border-dashed border-faint" : "ring-1 ring-line"}`}
                      >
                        {!p.deferred && (
                          <span className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${p.progress * 100}%`, background: barColor(task, room.mode), opacity: p.done ? 0.55 : 1 }} />
                        )}
                      </span>
                    );
                  })}
                </span>
                {here.length > 0 && (
                  <span className="flex shrink-0 gap-1">
                    {here.map((tok) => (
                      <Token key={`${tok.id}-${z.id}`} tok={tok} />
                    ))}
                  </span>
                )}
              </div>
              <p className="relative mt-1 text-[13px] leading-snug text-muted">
                {line.text}
                {line.tag && line.tone && (
                  <span className={`ml-1.5 inline-block rounded border px-1 text-xs font-bold whitespace-nowrap ${TAG_TONE[line.tone]}`}>
                    {line.tone !== "changed" && <span aria-hidden>▲ </span>}
                    {line.tag}
                  </span>
                )}
              </p>
            </li>
          );
        })}
      </ol>

      <div className="flex items-center gap-3 rounded-lg border px-3 py-1.5" style={{ borderColor: `color-mix(in srgb, ${doorColor} 45%, transparent)` }}>
        <span aria-hidden className="h-8 w-2 shrink-0 rounded-sm" style={{ background: doorColor }} />
        <div className="min-w-0 flex-1">
          <p className="text-[15px] font-bold" style={{ color: doorColor }}>
            {frame.doors.open ? "Doors open" : `Doors open at ${clock(room.deadline)}`}
          </p>
          {ready != null && (
            <p className={`text-xs ${frame.doors.late ? "font-bold text-coral" : "text-muted"}`}>
              {frame.doors.late && lateBy != null ? `Ready ${clock(ready)}, ${lateBy} min after opening` : `Ready ${clock(ready)}`}
            </p>
          )}
        </div>
      </div>
      <p className="text-xs text-faint">Illustrative, driven by the plan&apos;s times. Not live tracking.</p>
    </div>
  );
}

/**
 * Animations follow the system's reduced-motion setting. Viewers whose system asks for less motion
 * can still opt in here (remembered in this browser); everyone else never sees the control.
 */
function MotionToggle({ system, reduced }: { system: boolean; reduced: boolean }) {
  if (!system) return null;
  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-1 px-3 pb-2 text-xs text-muted sm:px-0">
      <span>{reduced ? "Animations are off: your system asks for reduced motion." : "Animations on, despite your reduced-motion setting."}</span>
      <button
        type="button"
        onClick={() => setMotionOverride(reduced ? "full" : null)}
        className="rounded-md border border-line px-2.5 py-1 text-porcelain hover:border-porcelain"
      >
        {reduced ? "Play animations" : "Reduce motion"}
      </button>
    </p>
  );
}

export function VenueScene({ scenario, room, rippleKey, previewKey }: { scenario: Scenario; room: RoomView; rippleKey: number; previewKey: string }) {
  const zones = useMemo(() => [...scenario.zones].sort((a, b) => a.order - b.order), [scenario]);
  const { dayStart, dayEnd } = sceneSpan(room);

  const motion = useMotion();
  const reduced = motion.reduced;
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
  const frame = sceneFrame(scenario, room, minute, dayStart);
  const ready = room.readiness;
  const label = `Illustrative venue scene at ${clock(minute)}. ${frame.doors.late ? `Doors would be ready at ${clock(ready!)}, after the ${clock(room.deadline)} opening.` : `Doors ready at ${ready != null ? clock(ready) : "unknown"}.`}`;
  const layout: LayoutProps = { scenario, room, zones, frame, minute, rippleKey };
  const atEnd = shownT >= dayEnd;

  return (
    <figure className="relative flex flex-col">
      <div role="img" aria-label={label}>
        <div className="max-sm:hidden">
          <FloorPlan {...layout} />
        </div>
        <div className="sm:hidden">
          <Stacked {...layout} />
        </div>
      </div>
      <figcaption className="order-first flex items-center gap-3 border-b border-line px-3 py-2.5 text-xs text-muted sm:order-none sm:flex-wrap sm:border-0 sm:pt-0 sm:pb-2">
        <p className="shrink-0 sm:hidden" aria-hidden>
          <span className="block text-xs leading-none text-muted">Scene time</span>
          <span className="font-display text-[2rem] leading-none font-extrabold text-porcelain">{clock(minute)}</span>
        </p>
        <button
          type="button"
          onClick={() => {
            if (reduced) {
              setPlaying(false);
              setT(atEnd ? dayStart : dayEnd);
            } else if (atEnd) {
              setT(dayStart);
              setPlaying(true);
            } else setPlaying((p) => !p);
          }}
          className="min-h-10 shrink-0 rounded-md border border-line px-3 py-1.5 hover:border-porcelain max-sm:order-last sm:min-h-0 sm:px-2.5 sm:py-1"
        >
          {effectivePlaying ? "Pause" : atEnd ? "Replay the day" : "Play"}
        </button>
        <label className="flex min-w-0 flex-1 items-center gap-2">
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
            className="h-6 w-full accent-[var(--amber)]"
            aria-valuetext={clock(minute)}
          />
        </label>
        <span className="tabular-nums max-sm:hidden">
          {clock(dayStart)}–{clock(dayEnd)}
        </span>
      </figcaption>
      <MotionToggle system={motion.system} reduced={reduced} />
    </figure>
  );
}
