import type { PCRScorecard } from "@/lib/types";

function fmt(x: number | null, digits = 2) {
  return x === null || x === undefined ? "—" : x.toFixed(digits);
}
function pct(x: number | null) {
  return x === null || x === undefined ? "—" : `${(x * 100).toFixed(1)}%`;
}

export function PcrScorecardView({ pcr }: { pcr: PCRScorecard }) {
  const rows = [
    { k: "Total OI PCR", v: fmt(pcr.total_oi_pcr), hint: "Put OI / Call OI · existing positioning" },
    { k: "Change-in-OI PCR", v: fmt(pcr.change_oi_pcr), hint: "Fresh Put OI / Fresh Call OI · today's conviction" },
    { k: "Volume PCR", v: fmt(pcr.volume_pcr), hint: "Put Vol / Call Vol · intraday participation" },
    { k: "CE conversion", v: pct(pcr.ce_oi_to_volume), hint: "ΔOI / Volume · churn vs conviction" },
    { k: "PE conversion", v: pct(pcr.pe_oi_to_volume), hint: "ΔOI / Volume · churn vs conviction" },
  ];
  return (
    <div className="card">
      <div className="label mb-3">PCR Scorecards · Steps 5–6</div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        {rows.map((r) => (
          <div key={r.k} className="rounded-lg bg-slate-900/70 p-3" title={r.hint}>
            <div className="text-[11px] uppercase tracking-wide text-slate-400">{r.k}</div>
            <div className="mt-1 text-xl font-bold tabular-nums text-accent">{r.v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
