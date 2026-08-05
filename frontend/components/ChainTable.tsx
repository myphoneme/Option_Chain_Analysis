import type { ChainRow } from "@/lib/types";

function nfmt(n: number) {
  return n.toLocaleString("en-IN");
}
function chg(n: number) {
  const s = n > 0 ? "+" : "";
  return `${s}${nfmt(n)}`;
}

export function ChainTable({
  rows,
  sums,
  lotSize,
}: {
  rows: ChainRow[];
  sums: { call: number; put: number };
  lotSize?: number | null;
}) {
  return (
    <div className="card overflow-x-auto">
      <div className="label mb-3">
        Option Chain · ATM window (Call ← Strike → Put)
        <span className="ml-2 normal-case text-slate-500">
          OI &amp; volume in contracts{lotSize && lotSize > 1 ? ` · lot ${lotSize}` : ""} — matches NSE
        </span>
      </div>
      <table className="w-full min-w-[640px] text-sm tabular-nums">
        <thead>
          <tr className="text-xs uppercase tracking-wide text-slate-400">
            <th className="py-2 pr-3 text-right text-bull">Call OI</th>
            <th className="py-2 pr-3 text-right text-bull">Call Δ</th>
            <th className="py-2 pr-3 text-right text-bull">%</th>
            <th className="py-2 px-3 text-center">Strike</th>
            <th className="py-2 pl-3 text-left">%</th>
            <th className="py-2 pl-3 text-left text-bear">Put Δ</th>
            <th className="py-2 pl-3 text-left text-bear">Put OI</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.strike}
              className={`border-t border-slate-800 ${r.is_atm ? "bg-accent/5" : ""}`}
            >
              <td className="py-1.5 pr-3 text-right">{nfmt(r.call_oi)}</td>
              <td className={`py-1.5 pr-3 text-right ${r.call_chg_oi >= 0 ? "text-bull" : "text-bear"}`}>
                {chg(r.call_chg_oi)}
              </td>
              <td className="py-1.5 pr-3 text-right text-slate-400">{r.call_pct_chg}</td>
              <td className="py-1.5 px-3 text-center font-semibold">
                <span className="inline-flex items-center gap-1">
                  {r.strike}
                  {r.is_atm && <span className="pill bg-accent/20 text-accent">ATM</span>}
                  {r.is_support && <span className="pill bg-bull/15 text-bull">S</span>}
                  {r.is_resistance && <span className="pill bg-bear/15 text-bear">R</span>}
                </span>
              </td>
              <td className="py-1.5 pl-3 text-left text-slate-400">{r.put_pct_chg}</td>
              <td className={`py-1.5 pl-3 text-left ${r.put_chg_oi >= 0 ? "text-bull" : "text-bear"}`}>
                {chg(r.put_chg_oi)}
              </td>
              <td className="py-1.5 pl-3 text-left">{nfmt(r.put_oi)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t-2 border-slate-700 font-semibold">
            <td className="py-2 pr-3 text-right text-bull" colSpan={2}>
              Σ Call Δ {nfmt(sums.call)}
            </td>
            <td colSpan={3}></td>
            <td className="py-2 pl-3 text-left text-bear" colSpan={2}>
              Σ Put Δ {nfmt(sums.put)}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
