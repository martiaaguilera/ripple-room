"use client";

import type { AgentEvent } from "@/lib/api/sse";
import type { Evaluation } from "@/lib/api/types";
import { clock, eur } from "@/lib/format";

const W = 320;
const ROW = 26;
const LEFT = 34;
const RIGHT = 10;
const TOP = 26;

interface Point {
  id: string;
  rationale: string;
  ev: Evaluation;
  minute: number | null;
}

function pointOf(e: AgentEvent): Point {
  const ev = e.data.evaluation as Evaluation;
  const minute =
    ev.status === "verified"
      ? (ev.schedule?.readiness ?? null)
      : ev.status === "infeasible"
        ? (ev.infeasibility?.best_readiness ?? null)
        : null;
  return { id: String(e.data.candidate_id), rationale: String(e.data.rationale ?? ""), ev, minute };
}

/**
 * Every candidate the model proposed, placed where the verifier says doors would be ready.
 * Filled = verified feasible; hollow = proven infeasible (plotted at the best it could do);
 * cross = rejected as malformed or not permitted. Built only from real candidate events.
 */
export function VerifierBoard({ events, deadline, doNothing }: { events: AgentEvent[]; deadline: number; doNothing: number | null }) {
  const points = events.filter((e) => e.type === "candidate").map(pointOf);
  if (points.length === 0) return null;
  const minutes = points.flatMap((p) => (p.minute != null ? [p.minute] : []));
  const lo = Math.floor((Math.min(deadline - 30, ...minutes) - 5) / 15) * 15;
  const hi = Math.ceil((Math.max(deadline + 20, doNothing ?? deadline, ...minutes) + 5) / 15) * 15;
  const x = (m: number) => LEFT + ((m - lo) / (hi - lo)) * (W - LEFT - RIGHT);
  const height = TOP + points.length * ROW + 18;
  const verified = points.filter((p) => p.ev.status === "verified").length;

  return (
    <figure className="rounded-xl border border-line bg-panel p-3">
      <figcaption className="flex items-baseline justify-between text-sm">
        <span className="font-semibold">Verifier board</span>
        <span className="text-xs text-muted">
          {verified} of {points.length} proposals hold
        </span>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${height}`} className="mt-2 block w-full" role="img" aria-label={`${points.length} proposals checked by the solver; ${verified} keep the ${clock(deadline)} deadline.`}>
        <rect x={LEFT} y={TOP - 8} width={x(deadline) - LEFT} height={height - TOP + 4} fill="var(--signal)" opacity={0.06} />
        <line x1={x(deadline)} x2={x(deadline)} y1={8} y2={height - 2} stroke="var(--amber)" strokeWidth={2} />
        <text x={x(deadline)} y={12} textAnchor="middle" fontSize={10.5} fill="var(--amber)" fontWeight={700}>
          Doors {clock(deadline)}
        </text>
        {doNothing != null && doNothing > deadline && (
          <g>
            <line x1={x(doNothing)} x2={x(doNothing)} y1={TOP - 6} y2={height - 2} stroke="var(--coral)" strokeDasharray="3 3" />
            <text x={Math.min(x(doNothing) + 3, W - 2)} y={height - 4} textAnchor={x(doNothing) > W - 60 ? "end" : "start"} fontSize={9.5} fill="var(--coral)">
              no action {clock(doNothing)}
            </text>
          </g>
        )}
        {points.map((p, i) => {
          const y = TOP + i * ROW + ROW / 2;
          const st = p.ev.status;
          return (
            <g key={p.id} className="verifier-point">
              <title>{`${p.id}: ${p.rationale}`}</title>
              <text x={0} y={y + 4} fontSize={11} fill="var(--muted)">
                {p.id}
              </text>
              <line x1={LEFT} x2={W - RIGHT} y1={y} y2={y} stroke="var(--line)" strokeWidth={0.5} />
              {st === "verified" && p.minute != null && (
                <>
                  <circle cx={x(p.minute)} cy={y} r={6} fill="var(--signal)" />
                  <text x={x(p.minute) - 9} y={y + 4} textAnchor="end" fontSize={10} fill="var(--signal)">
                    {eur(p.ev.cost_cents)}
                    {p.ev.service_impacts.length ? " ▲" : ""}
                  </text>
                </>
              )}
              {st === "infeasible" && p.minute != null && (
                <>
                  <line x1={x(deadline)} x2={x(p.minute)} y1={y} y2={y} stroke="var(--coral)" strokeWidth={1.5} />
                  <circle cx={x(p.minute)} cy={y} r={5.5} fill="var(--graphite)" stroke="var(--coral)" strokeWidth={2} />
                </>
              )}
              {(st === "rejected" || (st === "infeasible" && p.minute == null)) && (
                <text x={LEFT + 4} y={y + 4} fontSize={11} fill="var(--coral)" fontWeight={700}>
                  × {st === "rejected" ? "not permitted" : "no schedule"}
                </text>
              )}
              {st === "unknown" && (
                <text x={LEFT + 4} y={y + 4} fontSize={11} fill="var(--amber)">
                  ? timed out, not counted
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <p className="mt-1 text-[11px] text-faint">Filled: fits before doors. Hollow: the best that proposal could ever do. ▲ marks a guest-facing trade-off.</p>
    </figure>
  );
}
