import type { Verdict } from "@/lib/types";

export function DataQualityBanner({ v }: { v: Verdict }) {
  const dq = v.data_quality;
  if (!dq) return null; // demo/case-study path: full data

  let title: string;
  let cls: string;
  if (!dq.oi_available) {
    title = "Live · limited data";
    cls = "border-amber-500/40 bg-amber-500/10 text-amber-100/90";
  } else if (!dq.delta_oi_available) {
    title = "Live · OI active (ΔOI baselining)";
    cls = "border-sky-500/40 bg-sky-500/10 text-sky-100/90";
  } else {
    title = "Live · full SOP";
    cls = "border-bull/40 bg-bull/10 text-bull";
  }

  return (
    <div className={`card text-sm ${cls}`}>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="font-semibold">{title}</span>
        {v.expiry_used && <span>Expiry: {v.expiry_used}</span>}
        {v.spot_source && <span>Spot: {v.spot_source.replace(/_/g, " ")}</span>}
      </div>
      <p className="mt-1">{dq.note}</p>
    </div>
  );
}
