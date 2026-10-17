"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";

/**
 * Phone-only overflow for the top bar: what the plan is about and the secondary actions
 * that do not earn a place in a 390px row. Closes on Escape, outside tap, or after an action.
 */
export function HeaderMenu({ children }: { children: (close: () => void) => ReactNode }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (root.current && !root.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setOpen(false);
      trigger.current?.focus();
    };
    document.addEventListener("pointerdown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={root} className="relative sm:hidden">
      <button
        ref={trigger}
        type="button"
        aria-expanded={open}
        aria-controls={id}
        aria-label="More"
        onClick={() => setOpen((o) => !o)}
        className={`grid h-10 w-10 place-items-center rounded-md border ${open ? "border-porcelain" : "border-line"}`}
      >
        <svg aria-hidden width="16" height="4" viewBox="0 0 16 4" fill="currentColor">
          <circle cx="2" cy="2" r="1.6" />
          <circle cx="8" cy="2" r="1.6" />
          <circle cx="14" cy="2" r="1.6" />
        </svg>
      </button>
      {open && (
        <div id={id} className="absolute top-full right-0 z-40 mt-2 w-64 rounded-xl border border-line-strong bg-raised p-3 text-sm shadow-[0_12px_32px_rgb(0_0_0/0.45)]">
          {children(() => setOpen(false))}
        </div>
      )}
    </div>
  );
}
