import type { Invalidation, StrategySuggestion } from "@/lib/types";

export function StrategyList({
  strategies,
  invalidation,
}: {
  strategies: StrategySuggestion[];
  invalidation: Invalidation | null;
}) {
  return (
    <div className="card">
      <div className="label mb-3">Strategy &amp; Invalidation · Steps 8–9</div>
      <div className="space-y-3">
        {strategies.map((s, i) => (
          <div key={i} className="rounded-lg bg-slate-900/70 p-3">
            <div className="flex items-center gap-2">
              <span className="pill bg-accent/20 text-accent">{s.trader_type}</span>
              <span className="font-medium">{s.action}</span>
            </div>
            <div className="mt-1 text-xs text-slate-400">{s.risk_note}</div>
          </div>
        ))}
      </div>
      {invalidation && (
        <div className="mt-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
          <span className="font-semibold text-amber-400">Invalidation · </span>
          <span className="text-amber-100/90">{invalidation.condition}</span>
        </div>
      )}
    </div>
  );
}
