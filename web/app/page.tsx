"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import {
  ArrowsClockwise,
  GlobeHemisphereWest,
  MagnifyingGlass,
  Warning,
} from "@phosphor-icons/react";
import {
  analyze,
  fetchEvents,
  fetchEventTypes,
  fetchHealth,
  fetchMapEvents,
  searchGdelt,
} from "@/lib/api";
import type {
  AnalyzeResponse,
  GeoEvent,
  Health,
  InputMode,
} from "@/lib/types";
import AnalysisPanel from "@/components/AnalysisPanel";

// O mapa usa APIs de browser (SVG/medições), carrega só no cliente.
const WorldMap = dynamic(() => import("@/components/WorldMap"), { ssr: false });

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [events, setEvents] = useState<GeoEvent[]>([]);
  const [eventTypes, setEventTypes] = useState<Record<string, string>>({});
  const [mapEvents, setMapEvents] = useState<GeoEvent[]>([]);
  const [mode, setMode] = useState<InputMode>("historical");

  const [selected, setSelected] = useState<GeoEvent | null>(null);
  const [nAnalogs, setNAnalogs] = useState(3);

  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runId = useRef(0);

  useEffect(() => {
    (async () => {
      try {
        const [h, evs, types, mapEvs] = await Promise.all([
          fetchHealth(),
          fetchEvents(),
          fetchEventTypes(),
          fetchMapEvents(),
        ]);
        setHealth(h);
        setEvents(evs);
        setEventTypes(types);
        setMapEvents(mapEvs);
        if (evs.length > 0) setSelected(evs[0]);
      } catch (e) {
        setError("Não consegui falar com o backend na porta 8000. Ele está rodando?");
        console.error(e);
      }
    })();
  }, []);

  const runAnalysis = useCallback(
    async (ev: GeoEvent, analogs: number) => {
      const id = ++runId.current;
      setLoading(true);
      setError(null);
      try {
        const isHistorical = events.some((e) => e.id === ev.id);
        const res = await analyze(
          isHistorical
            ? { eventId: ev.id, nAnalogs: analogs }
            : { event: ev, nAnalogs: analogs }
        );
        if (id === runId.current) setResult(res);
      } catch (e) {
        if (id === runId.current)
          setError(e instanceof Error ? e.message : "Falha na análise.");
      } finally {
        if (id === runId.current) setLoading(false);
      }
    },
    [events]
  );

  useEffect(() => {
    if (selected) runAnalysis(selected, nAnalogs);
  }, [selected, nAnalogs, runAnalysis]);

  return (
    <div className="min-h-[100dvh] px-4 py-5 md:px-8 md:py-7 flex flex-col gap-5 max-w-[1480px] mx-auto w-full">
      <Header health={health} />

      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-5 items-start">
        <Sidebar
          mode={mode}
          setMode={setMode}
          events={events}
          eventTypes={eventTypes}
          selected={selected}
          setSelected={setSelected}
          nAnalogs={nAnalogs}
          setNAnalogs={setNAnalogs}
          onRegenerate={() => selected && runAnalysis(selected, nAnalogs)}
          loading={loading}
        />

        <div className="grid grid-cols-1 xl:grid-cols-[1.02fr_0.98fr] gap-5 items-start">
          <section className="panel p-4">
            <div className="flex items-center justify-between mb-3 px-1">
              <p className="eyebrow flex items-center gap-2">
                <GlobeHemisphereWest size={14} className="text-[color:var(--accent)]" />
                Distribuição geográfica
              </p>
              <div className="flex gap-4 text-xs num text-zinc-400">
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-[#fb7185]" /> Em foco
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-[#7dd3fc]" /> Curados
                </span>
              </div>
            </div>
            <WorldMap
              events={mapEvents}
              focused={result?.event ?? selected}
              onSelectEvent={(e) => setSelected(e)}
            />
          </section>

          <section className="panel p-5 min-h-[340px]">
            {error ? (
              <div className="flex items-start gap-2 text-[color:var(--neg)] text-sm">
                <Warning size={18} className="mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            ) : loading ? (
              <AnalysisSkeleton />
            ) : result ? (
              <AnalysisPanel data={result} />
            ) : (
              <p className="text-zinc-400 text-sm">Selecione um evento para gerar a análise.</p>
            )}
          </section>
        </div>
      </div>

      <Footer />
    </div>
  );
}

// --------------------------------------------------------------------------- //
function Header({ health }: { health: Health | null }) {
  return (
    <header className="panel px-5 py-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl grid place-items-center bg-[color:var(--accent-tint)] border border-[color:var(--line-2)]">
          <GlobeHemisphereWest size={22} weight="fill" className="text-[color:var(--accent)]" />
        </div>
        <div>
          <h1 className="text-xl md:text-2xl font-bold tracking-tight leading-none">GeoShock</h1>
          <p className="text-xs text-zinc-400 mt-1">
            Risco geopolítico em commodities · motor RAG · protótipo acadêmico
          </p>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <StatusChip on={!!health?.llm_live} label={`${health?.llm_provider ?? "llm"} ${health?.llm_live ? "conectado" : "offline"}`} />
        <StatusChip on={!!health?.fred_live} label={`FRED ${health?.fred_live ? "conectado" : "offline"}`} />
        <StatusChip on label="GDELT aberta" />
      </div>
    </header>
  );
}

function StatusChip({ on, label }: { on: boolean; label: string }) {
  return (
    <span className={`chip ${on ? "chip-on" : "chip-off"}`}>
      <span className="chip-dot" />
      {label}
    </span>
  );
}

// --------------------------------------------------------------------------- //
interface SidebarProps {
  mode: InputMode;
  setMode: (m: InputMode) => void;
  events: GeoEvent[];
  eventTypes: Record<string, string>;
  selected: GeoEvent | null;
  setSelected: (e: GeoEvent | null) => void;
  nAnalogs: number;
  setNAnalogs: (n: number) => void;
  onRegenerate: () => void;
  loading: boolean;
}

function Sidebar(props: SidebarProps) {
  const { mode, setMode, events, eventTypes, selected, setSelected, nAnalogs, setNAnalogs, onRegenerate, loading } = props;

  return (
    <aside className="panel p-5 flex flex-col gap-6 lg:sticky lg:top-5">
      <div>
        <p className="eyebrow mb-2">Fonte do evento</p>
        <div className="seg">
          {([
            ["historical", "Histórico"],
            ["manual", "Manual"],
            ["gdelt", "GDELT"],
          ] as [InputMode, string][]).map(([m, label]) => (
            <button
              key={m}
              className={`seg-item ${mode === m ? "seg-active" : ""}`}
              onClick={() => setMode(m)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {mode === "historical" && (
        <div>
          <label className="eyebrow">Evento histórico</label>
          <select
            className="gs-select mt-2"
            value={selected?.id ?? ""}
            onChange={(e) => setSelected(events.find((ev) => ev.id === e.target.value) ?? null)}
          >
            {events.map((ev) => (
              <option key={ev.id} value={ev.id}>
                {ev.title} ({ev.date})
              </option>
            ))}
          </select>
        </div>
      )}

      {mode === "manual" && <ManualForm eventTypes={eventTypes} onSubmit={setSelected} />}
      {mode === "gdelt" && <GdeltSearch onSelect={setSelected} />}

      <div>
        <div className="flex items-center justify-between">
          <label className="eyebrow">Eventos análogos</label>
          <span className="num text-sm text-[color:var(--accent-2)]">{nAnalogs}</span>
        </div>
        <input
          type="range"
          min={1}
          max={10}
          value={nAnalogs}
          onChange={(e) => setNAnalogs(Number(e.target.value))}
          className="w-full mt-3 accent-[#e9a94b]"
        />
      </div>

      <button className="btn btn-primary" onClick={onRegenerate} disabled={loading || !selected}>
        <ArrowsClockwise size={16} weight="bold" className={loading ? "animate-spin" : ""} />
        {loading ? "Gerando…" : "Gerar análise"}
      </button>

      {selected && (
        <div className="panel-2 p-3.5">
          <p className="font-medium text-zinc-100 text-sm leading-snug">{selected.title}</p>
          <p className="mt-2 text-xs text-zinc-400 num">{selected.date} · {selected.region}</p>
          <div className="mt-2 flex items-center gap-2">
            <div className="flex-1 h-1 rounded-full bg-white/8 overflow-hidden">
              <div
                className="h-full bg-[color:var(--accent)]"
                style={{ width: `${(selected.intensity_score / 10) * 100}%` }}
              />
            </div>
            <span className="num text-xs text-zinc-400">{selected.intensity_score}/10</span>
          </div>
        </div>
      )}
    </aside>
  );
}

// --------------------------------------------------------------------------- //
function ManualForm({
  eventTypes,
  onSubmit,
}: {
  eventTypes: Record<string, string>;
  onSubmit: (e: GeoEvent) => void;
}) {
  const [title, setTitle] = useState("");
  const [date, setDate] = useState("2024-01-01");
  const [region, setRegion] = useState("");
  const [type, setType] = useState("armed_conflict");
  const [intensity, setIntensity] = useState(5);
  const [description, setDescription] = useState("");

  const submit = () => {
    if (!title || !description) return;
    onSubmit({
      id: "manual_" + date.replace(/-/g, ""),
      title,
      date,
      region: region || "Não especificada",
      country_codes: [],
      lat: 0,
      lon: 0,
      event_type: type,
      intensity_score: intensity,
      description,
      commodities_affected: [],
      source: "Inserido pelo usuário",
    });
  };

  return (
    <div className="flex flex-col gap-2.5">
      <div>
        <label className="eyebrow">Título</label>
        <input className="gs-input mt-1.5" placeholder="Ex: Bloqueio no Estreito de Malaca" value={title} onChange={(e) => setTitle(e.target.value)} />
      </div>
      <div className="grid grid-cols-2 gap-2.5">
        <div>
          <label className="eyebrow">Data</label>
          <input className="gs-input mt-1.5" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>
        <div>
          <label className="eyebrow">Região</label>
          <input className="gs-input mt-1.5" placeholder="Sudeste Asiático" value={region} onChange={(e) => setRegion(e.target.value)} />
        </div>
      </div>
      <div>
        <label className="eyebrow">Tipo de evento</label>
        <select className="gs-select mt-1.5" value={type} onChange={(e) => setType(e.target.value)}>
          {Object.entries(eventTypes).map(([k, label]) => (
            <option key={k} value={k}>{label}</option>
          ))}
        </select>
      </div>
      <div>
        <div className="flex items-center justify-between">
          <label className="eyebrow">Intensidade</label>
          <span className="num text-xs text-[color:var(--accent-2)]">{intensity}/10</span>
        </div>
        <input type="range" min={1} max={10} value={intensity} onChange={(e) => setIntensity(Number(e.target.value))} className="w-full mt-2 accent-[#e9a94b]" />
      </div>
      <div>
        <label className="eyebrow">Descrição</label>
        <textarea className="gs-textarea mt-1.5" rows={3} placeholder="Contexto do evento" value={description} onChange={(e) => setDescription(e.target.value)} />
      </div>
      <button className="btn btn-primary mt-1" onClick={submit} disabled={!title || !description}>
        Usar este evento
      </button>
    </div>
  );
}

// --------------------------------------------------------------------------- //
function GdeltSearch({ onSelect }: { onSelect: (e: GeoEvent) => void }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<GeoEvent[]>([]);
  const [searching, setSearching] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const doSearch = async () => {
    if (query.trim().length < 2) return;
    setSearching(true);
    setErr(null);
    try {
      const evs = await searchGdelt(query);
      setResults(evs);
      if (evs.length === 0) setErr("Nenhum artigo utilizável retornado.");
    } catch {
      setErr("Falha ao consultar a GDELT.");
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="flex flex-col gap-2.5">
      <label className="eyebrow">Busca ao vivo</label>
      <input
        className="gs-input"
        placeholder="russia ukraine grain"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && doSearch()}
      />
      <button className="btn btn-primary" onClick={doSearch} disabled={searching}>
        <MagnifyingGlass size={16} weight="bold" />
        {searching ? "Buscando…" : "Buscar no GDELT"}
      </button>
      {err && <p className="text-xs text-[color:var(--accent-2)]">{err}</p>}
      <div className="flex flex-col max-h-72 overflow-y-auto -mx-1 px-1">
        {results.map((ev, i) => (
          <button
            key={i}
            className={`text-left py-2.5 hover:bg-white/[0.03] rounded-lg px-2 transition ${i > 0 ? "border-t border-white/8" : ""}`}
            onClick={() => onSelect(ev)}
          >
            <span className="block text-xs font-medium text-zinc-100 line-clamp-2 leading-snug">{ev.title}</span>
            <span className="block text-[11px] text-zinc-500 mt-1 num">{ev.date} · {ev.region}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
function AnalysisSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <div className="skeleton h-9 w-full" />
      <div className="skeleton h-5 w-2/3" />
      <div className="flex flex-col gap-2 mt-2">
        <div className="skeleton h-3 w-full" />
        <div className="skeleton h-3 w-full" />
        <div className="skeleton h-3 w-5/6" />
        <div className="skeleton h-3 w-11/12" />
      </div>
      <div className="skeleton h-3 w-1/3 mt-3" />
      <div className="flex flex-col gap-2">
        <div className="skeleton h-3 w-full" />
        <div className="skeleton h-3 w-4/5" />
      </div>
      <p className="text-xs text-zinc-500 mt-2">Consultando base histórica e redigindo briefing…</p>
    </div>
  );
}

// --------------------------------------------------------------------------- //
function Footer() {
  return (
    <footer className="text-center text-xs text-zinc-600 py-3">
      GeoShock · Protótipo acadêmico · FAE Centro Universitário, 2026 · Análise
      educacional, não constitui recomendação de investimento.
    </footer>
  );
}
