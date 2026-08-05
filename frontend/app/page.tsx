"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchDemoVerdict, fetchLiveVerdict, fetchMeta, fetchScripts, fetchUniverse } from "@/lib/api";
import type { ScriptOption, Underlying, Verdict } from "@/lib/types";
import { ScriptPicker, buildItems, type PickItem } from "@/components/ScriptPicker";
import { VerdictCard } from "@/components/VerdictCard";
import { TradeSetupCard } from "@/components/TradeSetupCard";
import { ChainTable } from "@/components/ChainTable";
import { FactorBreakdown } from "@/components/FactorBreakdown";
import { PcrScorecardView } from "@/components/PcrScorecard";
import { EvidenceTrail } from "@/components/EvidenceTrail";
import { DataQualityBanner } from "@/components/DataQualityBanner";

export default function Home() {
  const [caseStudies, setCaseStudies] = useState<ScriptOption[]>([]);
  const [indices, setIndices] = useState<Underlying[]>([]);
  const [stocks, setStocks] = useState<Underlying[]>([]);
  const [selected, setSelected] = useState<PickItem | null>(null);
  const [token, setToken] = useState("");
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availableExpiries, setAvailableExpiries] = useState<string[]>([]);
  const [chosenExpiry, setChosenExpiry] = useState<string>("");
  const [needsUserToken, setNeedsUserToken] = useState(true);

  useEffect(() => {
    fetchMeta()
      .then((m) => setNeedsUserToken(m.needs_user_token))
      .catch(() => setNeedsUserToken(true));
    Promise.all([fetchScripts(), fetchUniverse()])
      .then(([s, u]) => {
        setCaseStudies(s);
        setIndices(u.indices);
        setStocks(u.stocks);
        setSelected({
          key: `demo:${s[0].id}`,
          label: s[0].label,
          group: "Case study",
          mode: "demo",
          symbol: s[0].id,
        });
      })
      .catch((e) => setError(`Could not reach the SOP engine. ${e.message}`));
    const saved = typeof window !== "undefined" ? localStorage.getItem("xts_token") : null;
    if (saved) setToken(saved);
  }, []);

  const items = useMemo(
    () => buildItems(caseStudies, indices, stocks),
    [caseStudies, indices, stocks]
  );

  const needsToken = selected?.mode === "live" && needsUserToken && !token.trim();

  function pickScript(item: PickItem) {
    setSelected(item);
    setChosenExpiry("");
    setAvailableExpiries([]);
  }

  async function analyze(expiryOverride?: string) {
    if (!selected) return;
    setLoading(true);
    setError(null);
    try {
      let v: Verdict;
      if (selected.mode === "demo") {
        v = await fetchDemoVerdict(selected.symbol);
      } else {
        if (typeof window !== "undefined") localStorage.setItem("xts_token", token.trim());
        v = await fetchLiveVerdict({
          underlying: selected.symbol,
          expiry: expiryOverride ?? chosenExpiry,
          spot: 0,
          segment: selected.segment,
          accessToken: token.trim(),
        });
        if (v.available_expiries) setAvailableExpiries(v.available_expiries);
        if (v.expiry_used) setChosenExpiry(v.expiry_used);
      }
      setVerdict(v);
    } catch (e: any) {
      setError(e.message ?? "Analysis failed");
      setVerdict(null);
    } finally {
      setLoading(false);
    }
  }

  function onExpiryChange(exp: string) {
    setChosenExpiry(exp);
    analyze(exp);
  }

  return (
    <main className="space-y-6">
      <div className="card space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <ScriptPicker items={items} value={selected} onSelect={pickScript} />
          {selected?.mode === "live" && availableExpiries.length > 0 && (
            <div className="sm:w-44">
              <label className="label" htmlFor="expiry">
                Expiry
              </label>
              <select
                id="expiry"
                value={chosenExpiry}
                onChange={(e) => onExpiryChange(e.target.value)}
                disabled={loading}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 focus:border-accent focus:outline-none disabled:opacity-50"
              >
                {availableExpiries.map((x) => (
                  <option key={x} value={x}>
                    {x}
                  </option>
                ))}
              </select>
            </div>
          )}
          <button
            onClick={() => analyze()}
            disabled={loading || !selected || needsToken}
            className="rounded-lg bg-accent px-5 py-2 font-semibold text-slate-950 transition hover:bg-orange-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Analyzing…" : "Run SOP Analysis"}
          </button>
        </div>

        {selected?.mode === "live" && needsUserToken && (
          <div>
            <label className="label" htmlFor="token">
              XTS gateway access token (required for live scripts)
            </label>
            <input
              id="token"
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="paste your quantapi access_token"
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-xs text-slate-100 focus:border-accent focus:outline-none"
            />
            {needsToken && (
              <p className="mt-1 text-xs text-amber-400">
                A gateway token is needed to fetch live option data.
              </p>
            )}
          </div>
        )}
      </div>

      {error && <div className="card border-bear/40 bg-bear/10 text-sm text-bear">{error}</div>}

      {!verdict && !error && (
        <div className="card text-sm text-slate-400">
          Search and pick any F&amp;O script — indices, or any of the {stocks.length} F&amp;O stocks —
          then run the analysis. The engine executes the full 9-step Professional Scanning
          Sequence and drafts a verdict with strategy, invalidation, and the evidence behind it.
        </div>
      )}

      {verdict && (
        <>
          <DataQualityBanner v={verdict} />
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="space-y-6 lg:col-span-2">
              <VerdictCard v={verdict} />
              {verdict.chain_table?.length > 0 && (
                <ChainTable
                  rows={verdict.chain_table}
                  sums={{ call: verdict.sum_call_chg_oi, put: verdict.sum_put_chg_oi }}
                  lotSize={verdict.lot_size}
                />
              )}
              <PcrScorecardView pcr={verdict.pcr} />
            </div>
            <div className="space-y-6">
              {verdict.trade_setup && <TradeSetupCard setup={verdict.trade_setup} />}
              {verdict.factors && verdict.factors.length > 0 && (
                <FactorBreakdown
                  factors={verdict.factors}
                  composite={verdict.composite_score ?? 0}
                  coverage={verdict.coverage ?? 0}
                />
              )}
              <EvidenceTrail evidence={verdict.evidence} />
            </div>
          </div>
        </>
      )}
    </main>
  );
}
