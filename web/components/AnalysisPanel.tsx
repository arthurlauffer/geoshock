"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Article,
  ChartBar,
  CheckCircle,
  ClockCounterClockwise,
  DownloadSimple,
} from "@phosphor-icons/react";
import type { AnalyzeResponse } from "@/lib/types";

const EVENT_TYPE_LABELS: Record<string, string> = {
  armed_conflict: "Conflito armado",
  economic_sanction: "Sanção econômica",
  military_tension: "Tensão militar",
  diplomatic_crisis: "Crise diplomática",
  institutional_disruption: "Ruptura institucional",
  trade_restriction: "Restrição comercial",
  infrastructure_attack: "Ataque a infraestrutura",
  territorial_dispute: "Disputa territorial",
};

const VALIDATION: Record<
  string,
  { label: string; commodities: string; analogs: string; outcomes: string; criterion: string }
> = {
  ukraine_2022: {
    label: "Invasão Russa à Ucrânia (24 fev 2022)",
    commodities: "trigo, milho, fertilizantes, gás natural",
    analogs: "Golfo (1990), Embargo Árabe (1973)",
    outcomes: "trigo +32% (30d); gás natural EU +55% (30d); milho +18% (30d)",
    criterion: "≥3 das 4 commodities corretas + análogos de conflito em zonas produtoras.",
  },
  iran_sanctions_2012: {
    label: "Sanções ao Irã (jan 2012)",
    commodities: "petróleo bruto",
    analogs: "Embargo Árabe (1973), Ormuz (2019)",
    outcomes: "WTI +8% (30d)",
    criterion: "Identifica analogia com embargo de 1973 e/ou tensões no Ormuz.",
  },
  covid_lockdowns_2020: {
    label: "COVID-19 Lockdowns (mar 2020)",
    commodities: "petróleo, cobre, alumínio",
    analogs: "sem análogo direto na base",
    outcomes: "petróleo -55% (30d)",
    criterion: "Identifica caráter disruptivo sobre a demanda (não oferta).",
  },
};

const fmtPct = (v: number | null) =>
  v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;

type Tab = "briefing" | "commodities" | "analogs" | "validation";

const TABS: { id: Tab; label: string; Icon: typeof Article }[] = [
  { id: "briefing", label: "Briefing", Icon: Article },
  { id: "commodities", label: "Commodities", Icon: ChartBar },
  { id: "analogs", label: "Análogos", Icon: ClockCounterClockwise },
  { id: "validation", label: "Validação", Icon: CheckCircle },
];

export default function AnalysisPanel({ data }: { data: AnalyzeResponse }) {
  const [tab, setTab] = useState<Tab>("briefing");
  const { briefing, similar, historical_summary, event } = data;

  const chartData = Object.entries(historical_summary)
    .filter(([, s]) => s.mean_change_30d != null)
    .map(([name, s]) => ({ name, value: s.mean_change_30d as number }));

  return (
    <div className="flex flex-col gap-5">
      <div className="seg">
        {TABS.map(({ id, label, Icon }) => (
          <button
            key={id}
            className={`seg-item ${tab === id ? "seg-active" : ""}`}
            onClick={() => setTab(id)}
          >
            <Icon size={15} weight={tab === id ? "fill" : "regular"} />
            <span className="hidden sm:inline">{label}</span>
          </button>
        ))}
      </div>

      {/* -------- Briefing -------- */}
      {tab === "briefing" && (
        <div key={event.id} className="reveal flex flex-col gap-3">
          <div className="flex items-center justify-between gap-2 text-xs">
            {briefing.meta.offline ? (
              <span className="chip chip-off"><span className="chip-dot" />Template offline</span>
            ) : (
              <span className="num text-[11px] text-zinc-500">
                {briefing.meta.model} · {briefing.meta.tokens ?? "?"} tok · {briefing.meta.elapsed_s ?? "?"}s
              </span>
            )}
            {briefing.quality === "low" && (
              <span className="chip chip-off"><span className="chip-dot" />Briefing curto</span>
            )}
          </div>

          <div className="md">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{briefing.markdown}</ReactMarkdown>
          </div>

          <a
            className="btn btn-ghost no-underline"
            href={`data:text/plain;charset=utf-8,${encodeURIComponent(briefing.markdown)}`}
            download={`briefing_${event.id}.txt`}
          >
            <DownloadSimple size={16} /> Baixar briefing (.txt)
          </a>

          {briefing.sources.length > 0 && (
            <div className="mt-1">
              <p className="eyebrow mb-2">Fontes rastreáveis</p>
              <ul className="flex flex-col gap-1.5">
                {briefing.sources.map((s) => (
                  <li key={s.id} className="flex items-center justify-between text-sm text-zinc-300">
                    <span>{s.title} <span className="text-zinc-500">({s.date})</span></span>
                    <span className="num text-zinc-400">{s.similarity_pct}%</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* -------- Commodities -------- */}
      {tab === "commodities" && (
        <div className="reveal flex flex-col gap-6">
          <table className="dtable">
            <thead>
              <tr>
                <th>Commodity</th>
                <th className="text-right">Média 30d</th>
                <th className="text-right">Máx 30d</th>
                <th className="text-right">Prec.</th>
                <th className="text-right">Confiança</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(historical_summary).map(([name, s]) => (
                <tr key={name}>
                  <td className="font-medium">{name}</td>
                  <td className={`num text-right ${valueColor(s.mean_change_30d)}`}>{fmtPct(s.mean_change_30d)}</td>
                  <td className={`num text-right ${valueColor(s.max_change_30d)}`}>{fmtPct(s.max_change_30d)}</td>
                  <td className="num text-right text-zinc-400">{s.n_precedents}</td>
                  <td className="text-right text-zinc-400">{s.confidence}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {chartData.length > 0 && (
            <div>
              <p className="eyebrow mb-3">Variação média histórica · 30 dias</p>
              <ResponsiveContainer width="100%" height={Math.max(160, chartData.length * 40)}>
                <BarChart data={chartData} layout="vertical" margin={{ left: 6, right: 24 }}>
                  <XAxis type="number" stroke="#52525b" fontSize={11} tickFormatter={(v) => `${v}%`} />
                  <YAxis type="category" dataKey="name" stroke="#a1a1aa" fontSize={11} width={92} tickLine={false} axisLine={false} />
                  <Tooltip
                    cursor={{ fill: "rgba(255,255,255,0.04)" }}
                    contentStyle={{
                      background: "#141416",
                      border: "1px solid rgba(255,255,255,0.14)",
                      borderRadius: 10,
                      color: "#ededee",
                      fontSize: 12,
                    }}
                    formatter={(v) => [`${Number(v).toFixed(1)}%`, "Variação"]}
                  />
                  <Bar dataKey="value" radius={[0, 5, 5, 0]} barSize={16}>
                    {chartData.map((d, i) => (
                      <Cell key={i} fill={d.value >= 0 ? "#4ade80" : "#fb7185"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {/* -------- Analogs -------- */}
      {tab === "analogs" && (
        <div className="reveal flex flex-col">
          {similar.length === 0 && (
            <p className="text-zinc-400 text-sm">Nenhum análogo histórico suficientemente próximo foi encontrado.</p>
          )}
          {similar.map((a, i) => {
            const verified = a.metadata?.verified_outcomes ?? {};
            return (
              <div key={a.id} className={i > 0 ? "hairline pt-4 mt-4" : ""}>
                <div className="flex items-baseline justify-between gap-3">
                  <p className="font-medium text-zinc-100">{a.title}</p>
                  <span className="num text-sm text-[color:var(--accent-2)] shrink-0">{a.similarity_pct}%</span>
                </div>
                <p className="text-xs text-zinc-500 mt-1 num">
                  {a.date} · {a.region} · {EVENT_TYPE_LABELS[a.event_type] ?? a.event_type}
                </p>
                {Object.keys(verified).length > 0 && (
                  <div className="flex flex-wrap gap-x-5 gap-y-1 mt-2 text-sm">
                    {Object.entries(verified).map(([k, v]) => (
                      <span key={k} className="text-zinc-400">
                        {k.replace(/_/g, " ")} <span className="num text-zinc-200">{v}</span>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* -------- Validation -------- */}
      {tab === "validation" && (
        <div className="reveal">
          {VALIDATION[event.id] ? (
            <div className="flex flex-col gap-4">
              <div>
                <p className="eyebrow mb-1">Validação retroativa</p>
                <h3 className="font-semibold text-lg">{VALIDATION[event.id].label}</h3>
              </div>
              <p className="text-sm text-zinc-300 leading-relaxed">
                <span className="text-zinc-500">Critério de sucesso. </span>
                {VALIDATION[event.id].criterion}
              </p>
              <table className="dtable">
                <tbody>
                  <tr><td className="text-zinc-500 w-40 align-top">Commodities esperadas</td><td>{VALIDATION[event.id].commodities}</td></tr>
                  <tr><td className="text-zinc-500 align-top">Análogos esperados</td><td>{VALIDATION[event.id].analogs}</td></tr>
                  <tr><td className="text-zinc-500 align-top">Variações reais</td><td className="num">{VALIDATION[event.id].outcomes}</td></tr>
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-zinc-400 text-sm leading-relaxed">
              Aba disponível ao selecionar um dos eventos de validação retroativa:
              Ucrânia 2022, Sanções ao Irã 2012 ou COVID-19 2020.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function valueColor(v: number | null): string {
  if (v == null) return "text-zinc-500";
  return v >= 0 ? "text-[color:var(--pos)]" : "text-[color:var(--neg)]";
}
