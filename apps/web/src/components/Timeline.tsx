"use client";

import { memo, useMemo } from "react";
import type { Scenario } from "@/lib/api/types";
import { clock } from "@/lib/format";
import type { RoomView, TaskView } from "@/lib/viewmodel";

const W = 900;
const LABEL_W = 150;
const ROW = 20;
const TOP = 30;

interface Props {
  scenario: Scenario;
  room: RoomView;
  focusTaskId: string | null;
  onFocus: (taskId: string | null) => void;
}

function barColor(task: TaskView, mode: RoomView["mode"]): string {
  if (mode === "preview") return task.change ? "var(--focus)" : "var(--signal)";
  switch (task.status) {
    case "breach":
    case "blocked":
      return "var(--coral)";
    case "delayed":
    case "at_risk":
      return "var(--amber)";
    default:
      return "var(--signal)";
  }
}

function TimelineImpl({ scenario, room, focusTaskId, onFocus }: Props) {
  const baseline = useMemo(() => new Map(scenario.baseline.entries.map((e) => [e.task_id, e.start])), [scenario]);
  const rows = useMemo(
    () => [...room.tasks].sort((a, b) => (baseline.get(a.id) ?? 0) - (baseline.get(b.id) ?? 0) || a.id.localeCompare(b.id)),
    [room.tasks, baseline],
  );
  const times = rows.flatMap((t) => [t.start, t.end, t.ghost?.start, t.ghost?.end]).filter((v): v is number => v != null);
  const t0 = Math.floor((Math.min(...times, room.deadline) - 15) / 30) * 30;
  const t1 = Math.ceil((Math.max(...times, room.deadline) + 15) / 30) * 30;
  const x = (m: number) => LABEL_W + ((m - t0) / (t1 - t0)) * (W - LABEL_W - 16);
  const height = TOP + rows.length * ROW + 10;
  const ticks: number[] = [];
  for (let m = t0; m <= t1; m += 30) ticks.push(m);
  const late = room.readiness != null && room.readiness > room.deadline;

  return (
    <svg viewBox={`0 0 ${W} ${height}`} className="block h-auto w-full min-w-[680px]" role="img" aria-label={`Timeline from ${clock(t0)} to ${clock(t1)}. Doors deadline ${clock(room.deadline)}.`}>
      {ticks.map((m) => (
        <g key={m}>
          <line x1={x(m)} y1={TOP - 8} x2={x(m)} y2={height - 6} stroke="var(--line)" strokeWidth={m % 60 === 0 ? 1 : 0.5} />
          {Math.abs(m - room.deadline) >= 20 && (
            <text x={x(m)} y={14} textAnchor="middle" fill="var(--faint)" fontSize={12}>
              {clock(m)}
            </text>
          )}
        </g>
      ))}

      {rows.map((task, i) => {
        const y = TOP + i * ROW;
        const focused = focusTaskId === task.id;
        const color = barColor(task, room.mode);
        return (
          <g key={task.id} onMouseEnter={() => onFocus(task.id)} className="cursor-pointer">
            {focused && <rect x={0} y={y - 2} width={W} height={ROW} fill="var(--raised)" />}
            <text x={8} y={y + 11} fill={focused ? "var(--porcelain)" : "var(--muted)"} fontSize={12.5} fontWeight={task.critical ? 700 : 400}>
              {task.label}
            </text>
            {task.ghost && task.ghost.end > task.ghost.start && (
              <rect x={x(task.ghost.start)} y={y + 2} width={Math.max(2, x(task.ghost.end) - x(task.ghost.start))} height={ROW - 8} rx={3} fill="none" stroke="var(--faint)" strokeDasharray="3 3" />
            )}
            {task.start != null && task.end != null && task.end > task.start && (
              <rect x={x(task.start)} y={y + 2} width={Math.max(2, x(task.end) - x(task.start))} height={ROW - 8} rx={3} fill={color} fillOpacity={task.critical ? 0.95 : 0.6} />
            )}
            {task.start != null && task.end === task.start && (
              <path d={`M ${x(task.start)} ${y + 1} l 6 6 l -6 6 l -6 -6 z`} fill={task.id === scenario.deadline_task_id ? (late ? "var(--coral)" : "var(--amber)") : "var(--muted)"} />
            )}
            {task.status === "deferred" && (
              <text x={LABEL_W + 6} y={y + 11} fill="var(--faint)" fontSize={11}>
                deferred until after doors
              </text>
            )}
          </g>
        );
      })}

      <line x1={x(room.deadline)} y1={TOP - 10} x2={x(room.deadline)} y2={height - 4} stroke="var(--amber)" strokeWidth={2} />
      <text x={x(room.deadline)} y={14} textAnchor="middle" fill="var(--amber)" fontSize={12} fontWeight={700}>
        Doors {clock(room.deadline)}
      </text>
      {room.readiness != null && room.readiness !== room.deadline && (
        <g>
          <line x1={x(room.readiness)} y1={TOP - 4} x2={x(room.readiness)} y2={height - 4} stroke={late ? "var(--coral)" : "var(--signal)"} strokeWidth={1.5} strokeDasharray="4 3" />
        </g>
      )}
    </svg>
  );
}

export const Timeline = memo(TimelineImpl);
