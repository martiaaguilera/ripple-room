export const clock = (minute: number): string =>
  `${String(Math.floor(minute / 60)).padStart(2, "0")}:${String(minute % 60).padStart(2, "0")}`;

/** "+35 min" / "−5 min" / "on time" — uses a true minus sign for typographic clarity. */
export function delta(minutes: number | null | undefined): string {
  if (minutes == null) return "—";
  if (minutes === 0) return "on time";
  return `${minutes > 0 ? "+" : "−"}${Math.abs(minutes)} min`;
}

export const eur = (cents: number): string =>
  cents === 0 ? "€0" : `€${(cents / 100).toLocaleString("en-IE", { minimumFractionDigits: cents % 100 ? 2 : 0 })}`;

export const shortId = (id: string, n = 6): string => id.replace(/^rev_/, "").slice(0, n);

export type GapTone = "late" | "tight" | "spare" | "blocked";

/** The one-glance verdict between when doors are ready and when they open, in words. */
export function doorsGap(readiness: number | null, deadline: number): { text: string; tone: GapTone } {
  if (readiness == null) return { text: "blocked", tone: "blocked" };
  const gap = readiness - deadline;
  if (gap > 0) return { text: `${gap} min late`, tone: "late" };
  if (gap === 0) return { text: "on time", tone: "tight" };
  return { text: `${-gap} min spare`, tone: "spare" };
}
