"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { ScriptOption, Underlying } from "@/lib/types";

export interface PickItem {
  key: string;
  label: string;
  group: "Case study" | "Index" | "Stock";
  mode: "demo" | "live";
  symbol: string;
  segment?: number;
  kind?: string;
}

export function buildItems(
  caseStudies: ScriptOption[],
  indices: Underlying[],
  stocks: Underlying[]
): PickItem[] {
  return [
    ...caseStudies.map((c) => ({
      key: `demo:${c.id}`,
      label: c.label,
      group: "Case study" as const,
      mode: "demo" as const,
      symbol: c.id,
    })),
    ...indices.map((u) => ({
      key: `live:${u.symbol}`,
      label: `${u.symbol} · ${u.label}`,
      group: "Index" as const,
      mode: "live" as const,
      symbol: u.symbol,
      segment: u.segment,
      kind: u.kind,
    })),
    ...stocks.map((u) => ({
      key: `live:${u.symbol}`,
      label: u.symbol,
      group: "Stock" as const,
      mode: "live" as const,
      symbol: u.symbol,
      segment: u.segment,
      kind: u.kind,
    })),
  ];
}

export function ScriptPicker({
  items,
  value,
  onSelect,
}: {
  items: PickItem[];
  value: PickItem | null;
  onSelect: (item: PickItem) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickAway(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickAway);
    return () => document.removeEventListener("mousedown", onClickAway);
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toUpperCase();
    const list = q
      ? items.filter((i) => i.symbol.toUpperCase().includes(q) || i.label.toUpperCase().includes(q))
      : items;
    return list.slice(0, 60); // cap render
  }, [items, query]);

  const grouped = useMemo(() => {
    const g: Record<string, PickItem[]> = {};
    for (const it of filtered) (g[it.group] ??= []).push(it);
    return g;
  }, [filtered]);

  return (
    <div className="relative flex-1" ref={boxRef}>
      <label className="label">Select script (search any F&amp;O symbol)</label>
      <input
        value={open ? query : value ? value.label : ""}
        placeholder={value ? value.label : "Type NIFTY, RELIANCE, TCS…"}
        onFocus={() => {
          setOpen(true);
          setQuery("");
        }}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 focus:border-accent focus:outline-none"
        aria-label="Select F&O script"
      />
      {open && (
        <div className="absolute z-20 mt-1 max-h-80 w-full overflow-y-auto rounded-lg border border-slate-700 bg-slate-900 shadow-xl">
          {filtered.length === 0 && (
            <div className="px-3 py-3 text-sm text-slate-500">No match. Try another symbol.</div>
          )}
          {Object.entries(grouped).map(([group, list]) => (
            <div key={group}>
              <div className="sticky top-0 bg-slate-950/90 px-3 py-1 text-[11px] uppercase tracking-wide text-slate-500">
                {group}
              </div>
              {list.map((it) => (
                <button
                  key={it.key + it.group}
                  onClick={() => {
                    onSelect(it);
                    setOpen(false);
                    setQuery("");
                  }}
                  className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-slate-800"
                >
                  <span>{it.label}</span>
                  {it.mode === "live" ? (
                    <span className="pill bg-emerald-500/15 text-emerald-400">live</span>
                  ) : (
                    <span className="pill bg-slate-700 text-slate-300">offline</span>
                  )}
                </button>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
