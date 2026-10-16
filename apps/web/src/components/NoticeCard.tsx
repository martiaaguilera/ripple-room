"use client";

import { useState } from "react";
import type { ChangeNotice } from "@/lib/api/types";
import { clock } from "@/lib/format";

function asText(notice: ChangeNotice): string {
  const lines = notice.items.map(
    (i) => `${i.recipient_label} (tell by ${clock(i.notify_by)}):\n${i.changes.map((c) => `  - ${c.text}`).join("\n")}`,
  );
  if (notice.unchanged.length) lines.push(`No change for: ${notice.unchanged.join(", ")}.`);
  return lines.join("\n\n");
}

/** Who must be told what, by when. Deterministic facts from the verified plan diff. */
export function NoticeCard({ notice }: { notice: ChangeNotice }) {
  const [copied, setCopied] = useState(false);
  return (
    <section aria-labelledby="notice-h" className="rounded-xl border border-line bg-panel p-3 text-sm">
      <div className="flex items-baseline justify-between gap-2">
        <h3 id="notice-h" className="font-semibold">
          Who needs to know
        </h3>
        <button
          type="button"
          onClick={() => {
            void navigator.clipboard?.writeText(asText(notice)).then(() => setCopied(true));
          }}
          className="text-xs text-muted underline underline-offset-2 hover:text-porcelain"
        >
          {copied ? "Copied" : "Copy as text"}
        </button>
      </div>
      <ol className="mt-2 space-y-2">
        {notice.items.map((item) => (
          <li key={item.recipient_id}>
            <p className="flex justify-between gap-2">
              <span className="font-semibold">{item.recipient_label}</span>
              <span className={item.kind === "supplier" ? "text-amber" : "text-muted"}>tell by {clock(item.notify_by)}</span>
            </p>
            <ul className="mt-0.5 space-y-0.5 text-xs text-muted">
              {item.changes.map((c) => (
                <li key={`${item.recipient_id}-${c.task_id}-${c.text}`}>{c.text}</li>
              ))}
            </ul>
          </li>
        ))}
      </ol>
      {notice.unchanged.length > 0 && <p className="mt-2 text-xs text-faint">No change for {notice.unchanged.join(", ")}.</p>}
    </section>
  );
}
