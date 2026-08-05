import type { FactorScore } from "@/lib/types";

function barColor(score: number) {
  return score >= 0 ? "bg-bull" : "bg-bear";
}

export function FactorBreakdown({
  factors,
  composite,
  coverage,
}: {
  factors: FactorScore[];
  composite: number;
  coverage: number;
}) {
  if (!factors?.length) return null;
  return (
    <div className="card">
      <div className="label mb-3">
        Weighted Scoring Model
        <span className="ml-2 normal-case text-slate-500">
          composite{" "}
          <b className={composite >= 0 ? "text-bull" : "text-bear"}>
            {composite > 0 ? "+" : ""}
            {composite.toFixed(2)}
          </b>{" "}
          · coverage {Math.round(coverage * 100)}%
        </span>
      </div>

      <div className="space-y-2">
        {factors.map((f) => {
          const pct = Math.abs(f.score) * 50; // half-width bar
          return (
            <div key={f.name} className="grid grid-cols-[1fr_auto] items-center gap-3">
              <div>
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-sm text-slate-200">
                    {f.name}
                    <span className="ml-1.5 text-[11px] text-slate-500">
                      {Math.round(f.weight * 100)}%
                    </span>
                  </span>
                  <span
                    className={`text-xs tabular-nums ${
                      !f.available ? "text-slate-500" : f.score >= 0 ? "text-bull" : "text-bear"
                    }`}
                  >
                    {f.available ? `${f.score > 0 ? "+" : ""}${f.score.toFixed(2)}` : "n/a"}
                  </span>
                </div>

                {/* centre-anchored bar: left = bearish, right = bullish */}
                <div className="relative mt-1 h-1.5 w-full rounded-full bg-slate-800">
                  <div className="absolute left-1/2 top-0 h-full w-px bg-slate-600" />
                  {f.available && (
                    <div
                      className={`absolute top-0 h-full rounded-full ${barColor(f.score)}`}
                      style={
                        f.score >= 0
                          ? { left: "50%", width: `${pct}%` }
                          : { right: "50%", width: `${pct}%` }
                      }
                    />
                  )}
                </div>
                <div className="mt-0.5 text-[11px] text-slate-500">{f.note}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
