export function EvidenceTrail({ evidence }: { evidence: string[] }) {
  return (
    <div className="card">
      <div className="label mb-3">9-Step Evidence Trail · why this verdict</div>
      <ol className="space-y-2">
        {evidence.map((line, i) => {
          // lines look like "[1] Spot ... " — split the step tag.
          const m = line.match(/^\[(\d+)\]\s*(.*)$/);
          const step = m ? m[1] : String(i + 1);
          const text = m ? m[2] : line;
          return (
            <li key={i} className="flex gap-3">
              <span className="mt-0.5 flex h-6 w-6 flex-none items-center justify-center rounded-full bg-slate-800 text-xs font-semibold text-accent">
                {step}
              </span>
              <span className="text-sm text-slate-300">{text}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
