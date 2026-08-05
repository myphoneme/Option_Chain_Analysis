// Mirrors the backend Verdict serialization (app/serialize.py).

export type Bias = "BULLISH" | "BEARISH" | "NEUTRAL" | "NO_TRADE";

export interface PCRScorecard {
  total_oi_pcr: number | null;
  change_oi_pcr: number | null;
  volume_pcr: number | null;
  ce_oi_to_volume: number | null;
  pe_oi_to_volume: number | null;
}

export interface StrikeClassification {
  strike: number;
  call_type: string;
  put_type: string;
  is_support: boolean;
  is_resistance: boolean;
  notes: string[];
}

export interface StrategySuggestion {
  trader_type: string;
  action: string;
  risk_note: string;
}

export interface Invalidation {
  direction: string;
  level: number;
  condition: string;
}

export interface DataQuality {
  oi_available: boolean;
  delta_oi_available?: boolean;
  spot_source?: string;
  note: string;
}

export interface FactorScore {
  name: string;
  weight: number;
  score: number;
  available: boolean;
  note: string;
  contribution: number;
}

export interface ChainRow {
  strike: number;
  call_oi: number;
  call_chg_oi: number;
  call_pct_chg: number;
  put_oi: number;
  put_chg_oi: number;
  put_pct_chg: number;
  is_atm: boolean;
  is_support: boolean;
  is_resistance: boolean;
}

export interface TradeSetup {
  signal: string;
  option_type: string;
  selected_strike: number | null;
  alt_strike: number | null;
  entry_rule: string;
  spot_stop_loss: number | null;
  hard_premium_sl_pct: number | null;
  target1: number | null;
  target2: number | null;
  rr_note: string;
  option_ltp: number | null;
  option_vwap: number | null;
  entry_state: string;
  spot_confirms: boolean | null;
}

export interface Verdict {
  underlying: string;
  spot: number;
  atm: number;
  expiry: string;
  bias: Bias;
  confidence: number;
  premium_direction: string;
  support_strike: number | null;
  resistance_strike: number | null;
  pcr: PCRScorecard;
  classifications: StrikeClassification[];
  strategies: StrategySuggestion[];
  invalidation: Invalidation | null;
  evidence: string[];
  timestamp: string | null;
  // Redesign_OCA
  direction: string;
  delta_pcr: number | null;
  pcr_basis: string;
  sum_call_oi: number;
  sum_put_oi: number;
  sum_call_chg_oi: number;
  sum_put_chg_oi: number;
  chain_table: ChainRow[];
  trade_setup: TradeSetup | null;
  spot_ltp: number | null;
  spot_vwap: number | null;
  spot_prev_close?: number | null;
  spot_change_pct?: number | null;
  oi_direction?: string | null;
  price_direction?: string | null;
  agreement?: string;
  factors?: FactorScore[];
  composite_score?: number;
  coverage?: number;
  lot_size?: number | null;
  oi_unit?: string;
  // live-only fields
  expiry_used?: string;
  available_expiries?: string[];
  spot_source?: string;
  data_quality?: DataQuality;
}

export interface ScriptOption {
  id: string;
  label: string;
  mode: "demo" | "live";
  segment: number;
}

// F&O universe underlying
export interface Underlying {
  symbol: string;
  label: string;
  segment: number;
  kind: "index" | "stock";
  strike: number | null;
}
