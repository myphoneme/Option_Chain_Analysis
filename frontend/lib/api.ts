import type { ScriptOption, Underlying, Verdict } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export async function fetchScripts(): Promise<ScriptOption[]> {
  const r = await fetch(`${BASE}/scripts`, { cache: "no-store" });
  if (!r.ok) throw new Error(`scripts ${r.status}`);
  const data = await r.json();
  return data.scripts as ScriptOption[];
}

export interface Meta {
  xts_mode: string;
  needs_user_token: boolean;
  engine_version?: string;
}

export async function fetchMeta(): Promise<Meta> {
  const r = await fetch(`${BASE}/meta`, { cache: "no-store" });
  if (!r.ok) throw new Error(`meta ${r.status}`);
  return (await r.json()) as Meta;
}

export interface Universe {
  indices: Underlying[];
  stocks: Underlying[];
  count: number;
}

export async function fetchUniverse(): Promise<Universe> {
  const r = await fetch(`${BASE}/fno/underlyings`, { cache: "no-store" });
  if (!r.ok) throw new Error(`fno/underlyings ${r.status}`);
  return (await r.json()) as Universe;
}

export async function fetchDemoVerdict(caseId: string): Promise<Verdict> {
  const r = await fetch(`${BASE}/demo/${caseId}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`demo/${caseId} ${r.status}`);
  return (await r.json()) as Verdict;
}

export interface LiveParams {
  underlying: string;
  expiry: string;
  spot: number;
  segment?: number;
  accessToken?: string;
}

export async function fetchLiveVerdict(p: LiveParams): Promise<Verdict> {
  const q = new URLSearchParams({
    underlying: p.underlying,
    segment: String(p.segment ?? 2),
  });
  if (p.expiry) q.set("expiry", p.expiry);
  if (p.spot) q.set("spot", String(p.spot));
  if (p.accessToken) q.set("access_token", p.accessToken);
  const r = await fetch(`${BASE}/live/verdict?${q.toString()}`, { cache: "no-store" });
  if (!r.ok) {
    const body = await r.text();
    throw new Error(`live verdict ${r.status}: ${body}`);
  }
  return (await r.json()) as Verdict;
}
