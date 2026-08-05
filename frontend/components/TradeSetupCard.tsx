import type { TradeSetup } from "@/lib/types";

function fnum(n: number | null) {
  return n === null || n === undefined ? "—" : n.toLocaleString("en-IN");
}

export function TradeSetupCard({ setup }: { setup: TradeSetup }) {
  const blocked = setup.blocked === true;
  const isTrade = setup.option_type !== "" && !blocked;
  const tone = blocked
    ? "border-amber-500/50 bg-amber-500/10"
    : isTrade
    ? setup.option_type === "CE"
      ? "border-bull/40 bg-bull/10"
      : "border-bear/40 bg-bear/10"
    : "border-amber-500/40 bg-amber-500/10";

  return (
    <div className={`card border ${tone}`}>
      <div className="label mb-2">Actionable Trade Setup · Steps 3–5</div>
      <div className="text-xl font-bold">{setup.signal}</div>

      {blocked && (
        <div className="mt-3 rounded-lg border border-amber-500/50 bg-amber-500/10 p-3 text-sm">
          <div className="flex items-center gap-2">
            <span className="rounded px-2 py-0.5 text-xs font-bold tracking-wide ring-1 ring-current text-amber-300">
              BLOCKED
            </span>
            <span className="font-medium text-amber-200">Execution gate · level check failed</span>
          </div>
          <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs text-amber-100/90">
            {(setup.validation_failures ?? []).map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-slate-400">{setup.entry_rule}</p>
        </div>
      )}

      {isTrade ? (
        <>
          {setup.entry_state && <EntrySignal setup={setup} />}
          <div className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
            <Field label="Buy (ATM)" value={`${fnum(setup.selected_strike)} ${setup.option_type}`} strong />
            <Field label="Alt (slight ITM)" value={`${fnum(setup.alt_strike)} ${setup.option_type}`} />
            <Field label="Spot stop-loss" value={fnum(setup.spot_stop_loss)} />
            <Field label="Hard premium SL" value={setup.hard_premium_sl_pct ? `${setup.hard_premium_sl_pct}%` : "—"} />
            <Field label="Target 1 (70%)" value={fnum(setup.target1)} />
            <Field label="Target 2 (30%)" value={fnum(setup.target2)} />
            <Field
              label="Reward : Risk"
              value={setup.reward_risk != null ? `${setup.reward_risk.toFixed(2)} : 1` : "—"}
            />
          </div>
          <div className="mt-3 rounded-lg bg-slate-900/70 p-3 text-sm">
            <div className="text-slate-300">
              <span className="font-semibold text-slate-100">Entry · </span>
              {setup.entry_rule}
            </div>
            {setup.rr_note && <div className="mt-1 text-xs text-slate-400">{setup.rr_note}</div>}
          </div>
        </>
      ) : (
        <p className="mt-2 text-sm text-amber-100/90">{setup.entry_rule}</p>
      )}
    </div>
  );
}

function EntrySignal({ setup }: { setup: TradeSetup }) {
  const state = setup.entry_state || "";
  const isEnter = state.startsWith("ENTER");
  const isWait = state.startsWith("WAIT");
  const cls = isEnter
    ? "border-bull/50 bg-bull/15 text-bull"
    : isWait
    ? "border-amber-500/50 bg-amber-500/15 text-amber-300"
    : "border-slate-700 bg-slate-900/70 text-slate-400";
  const badge = isEnter ? "ENTER" : isWait ? "WAIT" : "N/A";

  return (
    <div className={`mt-3 rounded-lg border p-3 ${cls}`}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="rounded px-2 py-0.5 text-xs font-bold tracking-wide ring-1 ring-current">
          {badge}
        </span>
        <span className="text-sm font-medium">Step 4 · VWAP entry timing</span>
      </div>
      <p className="mt-1.5 text-sm opacity-90">{state}</p>
      <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs tabular-nums opacity-90">
        {setup.option_ltp != null && (
          <span>
            Premium <b>{setup.option_ltp}</b> vs Option-VWAP <b>{setup.option_vwap}</b>
          </span>
        )}
        {setup.spot_confirms != null && (
          <span>
            Spot vs Spot-VWAP:{" "}
            <b>{setup.spot_confirms ? "confirms ✓" : "does not confirm ✗"}</b>
          </span>
        )}
      </div>
    </div>
  );
}

function Field({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="rounded-lg bg-slate-900/70 px-3 py-2">
      <div className="label">{label}</div>
      <div className={`tabular-nums ${strong ? "text-lg font-bold text-slate-100" : "text-slate-200"}`}>
        {value}
      </div>
    </div>
  );
}
