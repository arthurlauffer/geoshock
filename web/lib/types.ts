// Tipos das respostas da API GeoShock (FastAPI).

export interface GeoEvent {
  id: string;
  title: string;
  date: string;
  region: string;
  country_codes: string[];
  lat: number;
  lon: number;
  event_type: string;
  intensity_score: number;
  description: string;
  commodities_affected: string[];
  source: string;
  verified_outcomes?: Record<string, string>;
}

export interface SimilarEvent {
  id: string;
  title: string;
  date: string;
  region: string;
  event_type: string;
  intensity_score: number;
  commodities_affected: string[];
  lat: number;
  lon: number;
  distance: number;
  similarity_pct: number;
  document: string;
  metadata: Record<string, unknown> & {
    verified_outcomes?: Record<string, string>;
  };
}

export interface CommodityStats {
  n_precedents: number;
  mean_change_30d: number | null;
  median_change_30d: number | null;
  min_change_30d: number | null;
  max_change_30d: number | null;
  confidence: string;
  sources: string[];
}

export interface BriefingSource {
  id: string;
  title: string;
  date: string;
  similarity_pct: number;
}

export interface Briefing {
  markdown: string;
  quality: "ok" | "low";
  word_count: number;
  sources: BriefingSource[];
  meta: {
    provider: string;
    model: string;
    tokens: number | null;
    elapsed_s: number | null;
    offline: boolean;
  };
}

export interface AnalyzeResponse {
  event: GeoEvent;
  similar: SimilarEvent[];
  commodities: string[];
  price_data: Record<string, Record<string, unknown>>;
  historical_summary: Record<string, CommodityStats>;
  briefing: Briefing;
}

export interface Health {
  status: string;
  llm_provider: string;
  llm_live: boolean;
  fred_live: boolean;
  indexed_events: number;
}

export type InputMode = "historical" | "manual" | "gdelt";
