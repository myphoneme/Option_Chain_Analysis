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
