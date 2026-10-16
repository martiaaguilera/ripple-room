"use client";

import { memo, useMemo } from "react";
import type { Scenario } from "@/lib/api/types";
import { clock, delta } from "@/lib/format";
import { CANVAS, edgePath, layoutGraph, type NodeBox } from "@/lib/layout";
import { STATUS_TEXT, type RoomView, type TaskView } from "@/lib/viewmodel";

const WAVE_MS = 240;

interface Props {
  scenario: Scenario;
  room: RoomView;
  rippleKey: number;
  focusTaskId: string | null;
  onFocus: (taskId: string | null) => void;
  resourceLabel: (id: string) => string;
}

function tone(task: TaskView, mode: RoomView["mode"]): { stroke: string; fill: string; dash?: string; width: number } {
  if (mode === "preview") {
    if (task.status === "deferred") return { stroke: "var(--faint)", fill: "var(--panel)", dash: "4 4", width: 1.2 };
    if (task.change && (task.shift || task.change.reassigned.length || task.change.duration_to != null))
      return { stroke: "var(--focus)", fill: "#141e2d", width: 1.8 };
    return { stroke: "var(--line-strong)", fill: "var(--raised)", width: 1 };
  }
  switch (task.status) {
    case "breach":
      return { stroke: "var(--coral)", fill: "#2a1519", width: 2.2 };
    case "blocked":
      return { stroke: "var(--coral)", fill: "url(#hatch)", dash: "6 3", width: 2 };
    case "delayed":
      return { stroke: "var(--amber)", fill: "#251f14", width: 1.8 };
    case "at_risk":
      return { stroke: "var(--amber)", fill: "var(--raised)", dash: "2 4", width: 1.6 };
    default:
      return { stroke: "var(--line-strong)", fill: "var(--raised)", width: 1 };
  }
}

function badge(task: TaskView, mode: RoomView["mode"]): { text: string; color: string } | null {
  if (mode === "preview") {
    const c = task.change;
    if (!c) return null;
    if (c.deferred) return { text: "deferred", color: "var(--faint)" };
    if (c.duration_to != null) return { text: `now ${c.duration_to} min`, color: "var(--focus)" };
    if (c.reassigned.length) return { text: "new crew", color: "var(--focus)" };
    if (task.shift) return { text: delta(task.shift), color: "var(--focus)" };
    return null;
  }
  if (task.status === "blocked") return { text: "blocked", color: "var(--coral)" };
  if (task.delay && task.delay > 0) return { text: delta(task.delay), color: task.status === "breach" ? "var(--coral)" : "var(--amber)" };
  if (task.status === "at_risk") return { text: "at risk", color: "var(--amber)" };
  return null;
}

function Card({
  box,
  task,
  mode,
  focused,
  waveDelay,
  animate,
  subtitle,
  onFocus,
}: {
  box: NodeBox;
  task: TaskView;
  mode: RoomView["mode"];
  focused: boolean;
  waveDelay: number;
  animate: boolean;
  subtitle: string;
  onFocus: (id: string | null) => void;
}) {
  const t = tone(task, mode);
  const b = badge(task, mode);
  const style = { "--wave-delay": `${waveDelay}ms` } as React.CSSProperties;
  const label = `${task.label}. ${task.start != null ? `${clock(task.start)} to ${clock(task.end ?? task.start)}` : "not scheduled"}. ${STATUS_TEXT[task.status]}${b ? `, ${b.text}` : ""}.`;
  return (
    <g
      role="button"
      tabIndex={0}
      aria-label={label}
      aria-pressed={focused}
      style={style}
      className={`cursor-pointer outline-none ${animate ? "node-hit" : ""}`}
      onMouseEnter={() => onFocus(task.id)}
      onFocus={() => onFocus(task.id)}
      onClick={() => onFocus(task.id)}
    >
      <rect
        x={box.x}
        y={box.y}
        width={box.w}
        height={box.h}
        rx={7}
        className="node-status"
        fill={t.fill}
        stroke={focused ? "var(--focus)" : t.stroke}
        strokeWidth={focused ? 2.4 : t.width}
        strokeDasharray={t.dash}
      />
      {task.status === "breach" && mode !== "preview" && (
        <path d={`M ${box.x + box.w - 14} ${box.y} L ${box.x + box.w} ${box.y} L ${box.x + box.w} ${box.y + 14} Z`} fill="var(--coral)" />
      )}
      <text x={box.x + 11} y={box.y + 22} fill="var(--porcelain)" fontSize={14} fontWeight={700}>
        {task.label}
      </text>
      <text x={box.x + 11} y={box.y + 40} fill="var(--muted)" fontSize={12}>
        {subtitle}
      </text>
      {b && (
        <g>
          <rect x={box.x + box.w - 6 - (14 + b.text.length * 6.4)} y={box.y - 9} width={14 + b.text.length * 6.4} height={18} rx={9} fill="var(--graphite)" stroke={b.color} strokeWidth={1} />
          <text x={box.x + box.w - 6 - (14 + b.text.length * 6.4) / 2} y={box.y + 4} textAnchor="middle" fill={b.color} fontSize={11} fontWeight={700}>
            {b.text}
          </text>
        </g>
      )}
    </g>
  );
}

function Milestone({
  box,
  task,
  mode,
  deadline,
  focused,
  waveDelay,
  animate,
  onFocus,
}: {
  box: NodeBox;
  task: TaskView;
  mode: RoomView["mode"];
  deadline: number | null;
  focused: boolean;
  waveDelay: number;
  animate: boolean;
  onFocus: (id: string | null) => void;
}) {
  const t = tone(task, mode);
  const isDoors = deadline != null;
  const late = isDoors && task.start != null && task.start > deadline;
  const color = isDoors ? (late ? "var(--coral)" : "var(--amber)") : t.stroke === "var(--line-strong)" ? "var(--muted)" : t.stroke;
  const cx = box.x + (isDoors ? 14 : 12);
  const cy = box.y + box.h / 2;
  const time = task.start != null ? clock(task.start) : "—";
  const text = isDoors ? `Doors ${clock(deadline)}` : task.label;
  const sub = time;
  return (
    <g
      role="button"
      tabIndex={0}
      aria-label={`${task.label} at ${time}. ${STATUS_TEXT[task.status]}.`}
      style={{ "--wave-delay": `${waveDelay}ms` } as React.CSSProperties}
      className={`cursor-pointer outline-none ${animate ? "node-hit" : ""}`}
      onMouseEnter={() => onFocus(task.id)}
      onFocus={() => onFocus(task.id)}
      onClick={() => onFocus(task.id)}
    >
      <rect x={box.x} y={box.y} width={box.w} height={box.h} rx={box.h / 2} fill={isDoors ? "#211a10" : "var(--panel)"} stroke={focused ? "var(--focus)" : isDoors ? color : "var(--line)"} strokeWidth={focused ? 2.2 : isDoors ? 1.6 : 1} />
      <path d={`M ${cx} ${cy - 6} L ${cx + 6} ${cy} L ${cx} ${cy + 6} L ${cx - 6} ${cy} Z`} fill={color} className="node-status" />
      {isDoors ? (
        <>
          <text x={box.x + 28} y={box.y + 21} fill="var(--amber)" fontSize={15} fontWeight={700}>
            {text}
          </text>
          <text x={box.x + 28} y={box.y + 39} fill={late ? "var(--coral)" : "var(--muted)"} fontSize={12.5} fontWeight={late ? 700 : 400}>
            {`Ready ${time}`}
          </text>
        </>
      ) : (
        <>
          <text x={box.x + 26} y={cy + 4} fill="var(--porcelain)" fontSize={13} fontWeight={600}>
            {text}
          </text>
          <text x={box.x + box.w - 12} y={cy + 4} textAnchor="end" fill="var(--muted)" fontSize={12}>
            {sub}
          </text>
        </>
      )}
    </g>
  );
}

function OperationsCanvasImpl({ scenario, room, rippleKey, focusTaskId, onFocus, resourceLabel }: Props) {
  const layout = useMemo(() => layoutGraph(scenario), [scenario]);
  const animate = room.mode === "impact";
  const driving = useMemo(() => {
    const set = new Set<string>();
    for (let i = 1; i < room.drivingPath.length; i++) set.add(`${room.drivingPath[i - 1]}>${room.drivingPath[i]}`);
    return set;
  }, [room.drivingPath]);
  const causal = useMemo(() => new Map(room.causalEdges.map((e) => [`${e.from_id}>${e.to_id}`, e])), [room.causalEdges]);
  const resourceEdges = room.causalEdges.filter((e) => e.kind === "resource");

  return (
    <svg
      viewBox={`0 0 ${CANVAS.width} ${layout.height}`}
      className="block h-auto w-full min-w-[680px] select-none"
      role="group"
      aria-label="Operations graph: tasks grouped by venue zone, connected by dependencies"
    >
      <defs>
        <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="6" height="6" fill="#2a1519" />
          <line x1="0" y1="0" x2="0" y2="6" stroke="#f06f72" strokeOpacity="0.35" strokeWidth="2" />
        </pattern>
        <marker id="arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0 0 L8 4 L0 8 z" fill="var(--line-strong)" />
        </marker>
      </defs>

      {layout.zones.map((z, i) => (
        <g key={z.id}>
          {i > 0 && <line x1={z.x} y1={18} x2={z.x} y2={layout.height - 10} stroke="var(--line)" strokeDasharray="2 6" />}
          <text x={z.x + 14} y={34} fill="var(--faint)" fontSize={12.5} className="font-display" style={{ fontWeight: 600, letterSpacing: "0.06em" }}>
            {z.label}
          </text>
        </g>
      ))}

      <g fill="none">
        {layout.edges.map((e) => {
          const key = `${e.from}>${e.to}`;
          const onPath = driving.has(key);
          return (
            <path
              key={key}
              d={e.d}
              stroke={onPath ? "var(--muted)" : "var(--line)"}
              strokeWidth={onPath ? 1.8 : 1.1}
              markerEnd="url(#arrow)"
              opacity={focusTaskId && focusTaskId !== e.from && focusTaskId !== e.to ? 0.45 : 1}
            />
          );
        })}
      </g>

      {animate && (
        <g key={`pulse-${rippleKey}`} fill="none">
          {layout.edges
            .filter((e) => causal.has(`${e.from}>${e.to}`))
            .map((e) => {
              const c = causal.get(`${e.from}>${e.to}`)!;
              const hot = room.byId[e.to]?.status === "breach" || room.byId[e.to]?.status === "blocked";
              return (
                <path
                  key={`p-${e.from}-${e.to}`}
                  d={e.d}
                  className="edge-pulse"
                  stroke={hot ? "var(--coral)" : "var(--amber)"}
                  strokeWidth={2.2}
                  style={{ "--edge-len": e.length, "--wave-delay": `${c.wave * WAVE_MS - 140}ms` } as React.CSSProperties}
                />
              );
            })}
          {resourceEdges.map((e) => {
            const s = layout.nodes[e.from_id];
            const t = layout.nodes[e.to_id];
            if (!s || !t) return null;
            const p = edgePath(s, t);
            return (
              <path
                key={`r-${e.from_id}-${e.to_id}`}
                d={p.d}
                stroke="var(--amber)"
                strokeWidth={1.4}
                strokeDasharray="3 5"
                opacity={0.8}
                aria-hidden
              >
                <title>{`${room.byId[e.to_id]?.label} waits for the same crew or equipment as ${room.byId[e.from_id]?.label}`}</title>
              </path>
            );
          })}
        </g>
      )}

      <g>
        {room.tasks.map((task) => {
          const box = layout.nodes[task.id];
          if (!box) return null;
          const waveDelay = (task.wave ?? 0) * WAVE_MS;
          const hit = animate && task.wave != null;
          if (box.milestone) {
            return (
              <Milestone
                key={`${task.id}-${rippleKey}`}
                box={box}
                task={task}
                mode={room.mode}
                deadline={task.id === scenario.deadline_task_id ? room.deadline : null}
                focused={focusTaskId === task.id}
                waveDelay={waveDelay}
                animate={hit}
                onFocus={onFocus}
              />
            );
          }
          const who = Object.values(task.assignments)
            .map(resourceLabel)
            .filter((l) => !/space|trolley/i.test(l))
            .map((l) => l.split(" ")[0])
            .join(", ");
          const time = task.start != null ? `${clock(task.start)}–${clock(task.end ?? task.start)}` : "not scheduled";
          return (
            <Card
              key={`${task.id}-${rippleKey}`}
              box={box}
              task={task}
              mode={room.mode}
              focused={focusTaskId === task.id}
              waveDelay={waveDelay}
              animate={hit}
              subtitle={who ? `${time}  ${who}` : time}
              onFocus={onFocus}
            />
          );
        })}
      </g>

      {animate && (
        <g key={`ring-${rippleKey}`} fill="none" aria-hidden>
          {room.sources.map((id) => {
            const box = layout.nodes[id];
            if (!box) return null;
            const cx = box.milestone ? box.x + 12 : box.x + box.w / 2;
            return <circle key={id} className="ripple-ring" cx={cx} cy={box.y + box.h / 2} r={10} stroke="var(--amber)" />;
          })}
        </g>
      )}
    </svg>
  );
}

export const OperationsCanvas = memo(OperationsCanvasImpl);
