import type { Verdict } from "@/lib/types";

const biasStyle: Record<string, string> = {
  BULLISH: "bg-bull/15 text-bull border-bull/40",
  BEARISH: "bg-bear/15 text-bear border-bear/40",
  NEUTRAL: "bg-flat/15 text-flat border-flat/40",
  NO_TRADE: "bg-amber-500/15 text-amber-400 border-amber-500/40",
};

export function VerdictCard({ v }: { v: Verdict }) {
  const style = biasStyle[v.bias] ?? biasStyle.NEUTRAL;
  const conf = Math.round(v.confidence * 100);
  return (
    <div className={`card border ${style} flex flex-col gap-4`}>
      <div className="flex items-start justify-between">
        <div>
          <div className="label">Verdict · {v.underlying}</div>
          <div className="mt-1 text-3xl font-bold">{v.bias.replace("_", " ")}</div>
          <div className="text-sm opacity-80">{v.premium_direction}</div>
        </div>
        <div className="text-right">
          <div className="label">Confidence</div>
          <div className="text-3xl font-bold tabular-nums">{conf}%</div>
        </div>
      </div>

      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
        <div
          className="h-full rounded-full bg-current transition-all"
          style={{ width: `${conf}%` }}
        />
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <Stat label="Spot" value={v.spot.toLocaleString("en-IN")} />
        <Stat label="ATM" value={String(v.atm)} />
        <Stat label="Support" value={v.support_strike ? String(v.support_strike) : "—"} />
        <Stat label="Resistance" value={v.resistance_strike ? String(v.resistance_strike) : "—"} />
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-900/70 px-3 py-2">
      <div className="label">{label}</div>
      <div className="text-lg font-semibold tabular-nums text-slate-100">{value}</div>
    </div>
  );
}
