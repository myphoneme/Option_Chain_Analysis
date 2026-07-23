import type { StrikeClassification } from "@/lib/types";

function tone(label: string): string {
  const bull = ["Long Build-up", "Put Writing", "Short Covering"];
  const bear = ["Call Writing", "Put Long Build-up", "Long Unwinding"];
  if (label.startsWith("Call Long") || label === "Put Writing" || label.includes("Short Covering"))
    return "text-bull";
  if (label.includes("Writing") || label.includes("Put Long") || label.includes("Unwinding"))
    return label === "Put Writing" ? "text-bull" : "text-bear";
  return "text-slate-400";
}

export function ClassificationTable({
  rows,
  atm,
}: {
  rows: StrikeClassification[];
  atm: number;
}) {
  return (
    <div className="card overflow-x-auto">
      <div className="label mb-3">Change-in-OI Classification · Step 4</div>
      <table className="w-full min-w-[520px] text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wide text-slate-400">
            <th className="py-2 pr-3">Strike</th>
            <th className="py-2 pr-3">Call side</th>
            <th className="py-2 pr-3">Put side</th>
            <th className="py-2 pr-3">Zone</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const isAtm = r.strike === atm;
            return (
              <tr
                key={r.strike}
                className={`border-t border-slate-800 ${isAtm ? "bg-accent/5" : ""}`}
              >
                <td className="py-2 pr-3 font-semibold tabular-nums">
                  {r.strike}
                  {isAtm && <span className="ml-2 pill bg-accent/20 text-accent">ATM</span>}
                </td>
                <td className={`py-2 pr-3 ${tone(r.call_type)}`}>{r.call_type}</td>
                <td className={`py-2 pr-3 ${tone(r.put_type)}`}>{r.put_type}</td>
                <td className="py-2 pr-3">
                  {r.is_support && <span className="pill bg-bull/15 text-bull">Support</span>}
                  {r.is_resistance && (
                    <span className="pill bg-bear/15 text-bear">Resistance</span>
                  )}
                  {r.notes.length > 0 && (
                    <span className="ml-1 text-xs text-amber-400" title={r.notes.join(" ")}>
                      ⚠
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
