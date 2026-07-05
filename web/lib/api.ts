// Cliente HTTP do frontend para a API GeoShock (FastAPI).

import type { AnalyzeResponse, GeoEvent, Health } from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

export async function fetchHealth(): Promise<Health> {
  return getJSON<Health>("/api/health");
}

export async function fetchEvents(): Promise<GeoEvent[]> {
  const data = await getJSON<{ events: GeoEvent[] }>("/api/events");
  return data.events;
}

export async function fetchEventTypes(): Promise<Record<string, string>> {
  return getJSON<Record<string, string>>("/api/event_types");
}

export async function searchGdelt(
  query: string,
  maxRecords = 25
): Promise<GeoEvent[]> {
  const data = await getJSON<{ events: GeoEvent[] }>(
    `/api/gdelt/search?query=${encodeURIComponent(query)}&max_records=${maxRecords}`
  );
  return data.events;
}

export interface AnalyzeArgs {
  event?: Partial<GeoEvent>;
  eventId?: string;
  nAnalogs?: number;
  window?: number;
}

export async function analyze(args: AnalyzeArgs): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      event: args.event ?? null,
      event_id: args.eventId ?? null,
      n_analogs: args.nAnalogs ?? 3,
      window: args.window ?? 30,
    }),
  });
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<AnalyzeResponse>;
}
