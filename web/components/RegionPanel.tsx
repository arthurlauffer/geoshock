"use client";

import { ShieldCheck, ShieldWarning } from "@phosphor-icons/react";
import type { GeoEvent, RegionDetail } from "@/lib/types";
import { MARKER_COLORS } from "@/lib/markerColors";

const RISK_STYLE: Record<string, string> = {
  alto: "text-[color:var(--neg)] border-[color:var(--neg)]",
  "médio": "text-[color:var(--accent-2)] border-[color:var(--accent-2)]",
  baixo: "text-[color:var(--pos)] border-[color:var(--pos)]",
};

const RISK_LABEL: Record<string, string> = {
  alto: "Risco alto",
  "médio": "Risco médio",
  baixo: "Risco baixo",
};

export default function RegionPanel({
  detail,
  onSelectEvent,
}: {
  detail: RegionDetail;
  onSelectEvent: (e: GeoEvent) => void;
}) {
  const { sanctions_confirmed: sanctions } = detail;

  return (
    <div className="reveal flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">{detail.region.name}</h2>
        <span className={`chip ${RISK_STYLE[detail.risk_level] ?? ""}`}>
          {RISK_LABEL[detail.risk_level] ?? detail.risk_level}
        </span>
      </div>

      <p className="text-sm text-zinc-300 leading-relaxed">{detail.summary}</p>

      {sanctions.active && (
        <div className="panel-2 p-3 flex items-start gap-2.5">
          <ShieldWarning size={18} className="text-[color:var(--accent)] mt-0.5 shrink-0" />
          <div className="min-w-0">
            <p className="text-xs font-medium text-zinc-100">
              {sanctions.count} entidade{sanctions.count > 1 ? "s" : ""} sob sanção confirmada (OFAC)
            </p>
            {sanctions.programs.length > 0 && (
              <p className="text-[11px] text-zinc-500 mt-1 num">
                Programas: {sanctions.programs.slice(0, 4).join(", ")}
              </p>
            )}
          </div>
        </div>
      )}

      <div>
        <p className="eyebrow mb-2">Commodities mais expostas</p>
        <div className="flex flex-wrap gap-2">
          {detail.commodities_at_risk.slice(0, 6).map((c) => (
            <span key={c} className="chip">{c}</span>
          ))}
        </div>
      </div>

      {detail.verified_events.length > 0 && (
        <div>
          <p className="eyebrow mb-2 flex items-center gap-1.5">
            <ShieldCheck size={13} style={{ color: MARKER_COLORS.verified }} />
            Eventos verificados · UCDP ({detail.meta.n_verified})
          </p>
          <div className="flex flex-col">
            {detail.verified_events.map((e, i) => (
              <button
                key={`${e.id}_${i}`}
                onClick={() => onSelectEvent(e)}
                className={`text-left py-2.5 px-2 rounded-lg hover:bg-white/[0.03] transition ${i > 0 ? "border-t border-white/8" : ""}`}
              >
                <span className="block text-xs font-medium text-zinc-100 line-clamp-2 leading-snug">{e.title}</span>
                <span className="block text-[11px] text-zinc-500 mt-1 num">
                  {e.date}
                  {typeof e.fatalities_best === "number" && (
                    <> · {e.fatalities_best} fatalidade{e.fatalities_best === 1 ? "" : "s"} (estimativa)</>
                  )}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      <div>
        <p className="eyebrow mb-2">Eventos ao vivo · GDELT ({detail.meta.n_live})</p>
        {detail.live_events.length === 0 ? (
          <p className="text-xs text-zinc-500">Sem eventos ao vivo agora. Mostrando panorama da região.</p>
        ) : (
          <div className="flex flex-col">
            {detail.live_events.map((e, i) => (
              <button
                key={`${e.id}_${i}`}
                onClick={() => onSelectEvent(e)}
                className={`text-left py-2.5 px-2 rounded-lg hover:bg-white/[0.03] transition ${i > 0 ? "border-t border-white/8" : ""}`}
              >
                <span className="block text-xs font-medium text-zinc-100 line-clamp-2 leading-snug">{e.title}</span>
                <span className="block text-[11px] text-zinc-500 mt-1 num">{e.date} · {e.region}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
