import type { Scenario } from "./api/types";

/** Deterministic stage-plot layout: zones are floor columns, tasks stack by planned start. */

export const CANVAS = { width: 900, padX: 14, top: 50, cardH: 52, milestoneH: 30, doorsH: 50, gap: 12 } as const;
const CARD_W = 154;

export interface NodeBox {
  id: string;
  zoneId: string;
  x: number;
  y: number;
  w: number;
  h: number;
  milestone: boolean;
}

export interface ZoneBand {
  id: string;
  label: string;
  x: number;
  w: number;
}

export interface EdgePath {
  from: string;
  to: string;
  d: string;
  length: number;
}

export interface GraphLayout {
  nodes: Record<string, NodeBox>;
  zones: ZoneBand[];
  edges: EdgePath[];
  height: number;
}

type Pt = readonly [number, number];

function cubicLength(p0: Pt, p1: Pt, p2: Pt, p3: Pt, steps = 24): number {
  let len = 0;
  let prev = p0;
  for (let i = 1; i <= steps; i++) {
    const t = i / steps;
    const u = 1 - t;
    const x = u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0];
    const y = u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1];
    len += Math.hypot(x - prev[0], y - prev[1]);
    prev = [x, y];
  }
  return len;
}

export function edgePath(s: NodeBox, t: NodeBox): { d: string; length: number } {
  const sy = s.y + s.h / 2;
  const ty = t.y + t.h / 2;
  let p0: Pt;
  let p1: Pt;
  let p2: Pt;
  let p3: Pt;
  if (s.zoneId === t.zoneId) {
    // Same floor zone: loop out through the left gutter like a cable run.
    const bulge = 26 + Math.min(40, Math.abs(ty - sy) * 0.12);
    p0 = [s.x, sy];
    p3 = [t.x, ty];
    p1 = [s.x - bulge, sy];
    p2 = [t.x - bulge, ty];
  } else if (t.x > s.x) {
    p0 = [s.x + s.w, sy];
    p3 = [t.x, ty];
    const dx = (p3[0] - p0[0]) / 2;
    p1 = [p0[0] + dx, sy];
    p2 = [p3[0] - dx, ty];
  } else {
    // Backward edge (e.g. front of house feeding the stage): leave left, enter right.
    p0 = [s.x, sy];
    p3 = [t.x + t.w, ty];
    const dx = Math.max(40, (p0[0] - p3[0]) / 2);
    p1 = [p0[0] - dx, sy + 24];
    p2 = [p3[0] + dx, ty + 24];
  }
  const f = (p: Pt) => `${p[0].toFixed(1)} ${p[1].toFixed(1)}`;
  return { d: `M ${f(p0)} C ${f(p1)}, ${f(p2)}, ${f(p3)}`, length: Math.round(cubicLength(p0, p1, p2, p3)) };
}

export function layoutGraph(scenario: Scenario): GraphLayout {
  const zones = [...scenario.zones].sort((a, b) => a.order - b.order);
  const colW = (CANVAS.width - 2 * CANVAS.padX) / zones.length;
  const baseline = new Map(scenario.baseline.entries.map((e) => [e.task_id, e.start]));
  const nodes: Record<string, NodeBox> = {};
  const bands: ZoneBand[] = [];
  let maxY = 0;

  zones.forEach((zone, col) => {
    const x0 = CANVAS.padX + col * colW;
    bands.push({ id: zone.id, label: zone.label, x: x0, w: colW });
    const tasks = scenario.tasks
      .filter((t) => t.zone_id === zone.id)
      .sort((a, b) => (baseline.get(a.id) ?? 0) - (baseline.get(b.id) ?? 0) || a.id.localeCompare(b.id));
    let y: number = CANVAS.top;
    for (const task of tasks) {
      const milestone = Boolean(task.milestone);
      const h = task.id === scenario.deadline_task_id ? CANVAS.doorsH : milestone ? CANVAS.milestoneH : CANVAS.cardH;
      nodes[task.id] = { id: task.id, zoneId: zone.id, x: x0 + (colW - CARD_W) / 2 + 6, y, w: CARD_W, h, milestone };
      y += h + CANVAS.gap;
    }
    maxY = Math.max(maxY, y);
  });

  const edges: EdgePath[] = scenario.dependencies.flatMap((dep) => {
    const s = nodes[dep.from_id];
    const t = nodes[dep.to_id];
    return s && t ? [{ from: dep.from_id, to: dep.to_id, ...edgePath(s, t) }] : [];
  });
  return { nodes, zones: bands, edges, height: maxY + 8 };
}
