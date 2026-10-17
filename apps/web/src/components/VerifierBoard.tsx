"use client";

import type { AgentEvent } from "@/lib/api/sse";
import type { Evaluation } from "@/lib/api/types";
import { clock, eur } from "@/lib/format";

const W = 320;
const ROW = 30;
const LEFT = 30;
const RIGHT = 12;
const TOP = 24;
const AXIS = 20;

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

const VERDICT: Record<Evaluation["status"], { word: string; glyph: string; chip: string }> = {
  verified: { word: "holds", glyph: "✓", chip: "border-signal/50 bg-[#0d2422] text-signal" },
  infeasible: { word: "rejected", glyph: "×", chip: "border-coral/50 bg-[#2a1519] text-coral" },
  rejected: { word: "rejected", glyph: "×", chip: "border-coral/50 bg-[#2a1519] text-coral" },
  unknown: { word: "unproven", glyph: "?", chip: "border-amber/50 bg-[#251c0e] text-amber" },
};

function Legend() {
  return (
    <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted" aria-label="How to read the board">
      <li className="flex items-center gap-1">
        <svg aria-hidden width="10" height="10" viewBox="0 0 10 10">
          <circle cx="5" cy="5" r="4.5" fill="var(--signal)" />
        </svg>
        fits before doors
      </li>
      <li className="flex items-center gap-1">
        <svg aria-hidden width="10" height="10" viewBox="0 0 10 10">
          <circle cx="5" cy="5" r="3.8" fill="none" stroke="var(--coral)" strokeWidth="1.6" />
        </svg>
        best it could ever do
      </li>
      <li>
        <span aria-hidden className="text-amber">
          ▲
        </span>{" "}
        guest-facing trade-off
      </li>
    </ul>
  );
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
  const rowsEnd = TOP + points.length * ROW;
  const height = rowsEnd + AXIS;
  const verified = points.filter((p) => p.ev.status === "verified").length;
  // Right-align a bottom label when it would otherwise run off the board.
  const anchorEnd = (px: number) => px > W - 115;

  return (
    <figure className="rounded-xl border border-line bg-panel p-3">
      <figcaption>
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-sm font-semibold">Verifier board</span>
          <span className="font-display text-xl leading-none font-bold">
            <span className={verified ? "text-signal" : "text-coral"}>{verified}</span>
            <span className="text-muted"> of {points.length} proposals hold</span>
          </span>
        </div>
        <p className="mt-1 text-xs text-muted">Each AI proposal, placed where the solver says doors would be ready.</p>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${height}`} className="mt-2 block w-full" role="img" aria-label={`${points.length} proposals checked by the solver; ${verified} keep the ${clock(deadline)} deadline.`}>
        <rect x={LEFT} y={TOP - 4} width={x(deadline) - LEFT} height={rowsEnd - TOP + 8} rx={3} fill="var(--signal)" opacity={0.07} />
        <line x1={x(deadline)} x2={x(deadline)} y1={TOP - 8} y2={rowsEnd + 4} stroke="var(--amber)" strokeWidth={2} />
        <text x={x(deadline)} y={12} textAnchor="middle" fontSize={12} fill="var(--amber)" fontWeight={700}>
          Doors {clock(deadline)}
        </text>
        {doNothing != null && doNothing > deadline && (
          <g>
            <line x1={x(doNothing)} x2={x(doNothing)} y1={TOP - 4} y2={rowsEnd + 4} stroke="var(--coral)" strokeDasharray="3 3" />
            <text x={anchorEnd(x(doNothing)) ? x(doNothing) - 3 : x(doNothing) + 3} y={rowsEnd + 16} textAnchor={anchorEnd(x(doNothing)) ? "end" : "start"} fontSize={11} fill="var(--coral)">
              if nobody acts {clock(doNothing)}
            </text>
          </g>
        )}
        {points.map((p, i) => {
          const y = TOP + i * ROW + ROW / 2;
          const st = p.ev.status;
          return (
            <g key={p.id} className="verifier-point">
              <title>{`${p.id}: ${p.rationale}`}</title>
              <text x={0} y={y + 4} fontSize={12} fontWeight={700} fill="var(--muted)">
                {p.id}
              </text>
              <line x1={LEFT} x2={W - RIGHT} y1={y} y2={y} stroke="var(--line-strong)" strokeWidth={0.75} />
              {st === "verified" && p.minute != null && (
                <>
                  <circle cx={x(p.minute)} cy={y} r={7} fill="var(--signal)" />
                  <text x={x(p.minute) - 11} y={y + 4} textAnchor="end" fontSize={12} fontWeight={700} fill="var(--signal)">
                    {eur(p.ev.cost_cents)}
                    {p.ev.service_impacts.length ? " ▲" : ""}
                  </text>
                </>
              )}
              {st === "infeasible" && p.minute != null && (
                <>
                  <line x1={x(deadline)} x2={x(p.minute)} y1={y} y2={y} stroke="var(--coral)" strokeWidth={2} />
                  <circle cx={x(p.minute)} cy={y} r={6} fill="var(--panel)" stroke="var(--coral)" strokeWidth={2} />
                </>
              )}
              {(st === "rejected" || (st === "infeasible" && p.minute == null)) && (
                <text x={LEFT + 6} y={y + 4} fontSize={12} fill="var(--coral)" fontWeight={700}>
                  × {st === "rejected" ? "not permitted" : "no schedule"}
                </text>
              )}
              {st === "unknown" && (
                <text x={LEFT + 6} y={y + 4} fontSize={12} fill="var(--amber)">
                  ? timed out, not counted
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <Legend />
      <ol className="mt-3 space-y-2.5 border-t border-line pt-3 text-xs leading-relaxed" aria-label="Verifier verdicts">
        {points.map((p) => {
          const st = p.ev.status;
          const v = VERDICT[st];
          const reason =
            st === "rejected"
              ? (p.ev.violations[0]?.message ?? "Not a permitted change.")
              : st === "infeasible"
                ? (p.ev.infeasibility?.reasons[0] ?? "No schedule meets every hard rule.")
                : st === "unknown"
                  ? "The solver ran out of time; treated as not verified."
                  : `Fits: ready ${p.minute != null ? clock(p.minute) : "?"}, ${eur(p.ev.cost_cents)} extra${p.ev.service_impacts.length ? ", with a guest-facing trade-off" : ""}.`;
          return (
            <li key={p.id} className="verifier-point">
              <span className={`mr-1.5 inline-flex items-center gap-1 rounded border px-1.5 py-px font-bold ${v.chip}`}>
                <span aria-hidden>{v.glyph}</span>
                {p.id} {v.word}
              </span>
              {p.rationale && <span className="text-porcelain">{p.rationale} </span>}
              <span className={st === "verified" ? "text-signal" : "text-muted"}>{reason}</span>
            </li>
          );
        })}
      </ol>
    </figure>
  );
}
