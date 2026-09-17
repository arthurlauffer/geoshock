"use client";

import { ComposableMap, Geographies, Geography, Marker } from "react-simple-maps";
import type { GeoEvent } from "@/lib/types";
import { MARKER_COLORS, markerKindFor } from "@/lib/markerColors";

const GEO_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

interface Props {
  events: GeoEvent[];
  focused: GeoEvent | null;
  onSelectEvent: (e: GeoEvent) => void;
}

export default function WorldMap({ events, focused, onSelectEvent }: Props) {
  return (
    <div className="w-full overflow-hidden rounded-xl">
      <ComposableMap projection="geoEqualEarth" projectionConfig={{ scale: 168 }} style={{ width: "100%", height: "auto" }}>
        <Geographies geography={GEO_URL}>
          {({ geographies }) =>
            geographies.map((geo) => (
              <Geography
                key={geo.rsmKey}
                geography={geo}
                style={{
                  default: { fill: "rgba(255,255,255,0.05)", stroke: "rgba(255,255,255,0.12)", strokeWidth: 0.4, outline: "none" },
                  hover: { fill: "rgba(233,169,75,0.16)", stroke: "rgba(233,169,75,0.4)", outline: "none" },
                  pressed: { fill: "rgba(233,169,75,0.22)", outline: "none" },
                }}
              />
            ))
          }
        </Geographies>

        {events
          .filter((e) => e.lat !== 0 || e.lon !== 0)
          // Desenha eventos verificados (UCDP) por cima dos demais, já que
          // carregam dado de severidade real e merecem destaque visual.
          .map((e, i) => ({ e, i, kind: markerKindFor(e.kind, focused?.id === e.id) }))
          .sort((a, b) => (a.kind === "focused" ? 1 : b.kind === "focused" ? -1 : a.kind === "verified" ? 1 : b.kind === "verified" ? -1 : 0))
          .map(({ e, i, kind }) => {
            const isFocused = kind === "focused";
            const isVerified = kind === "verified";
            return (
              <Marker key={`${e.id}_${i}`} coordinates={[e.lon, e.lat]} onClick={() => onSelectEvent(e)} style={{ default: { cursor: "pointer" } }}>
                {isFocused && <circle className="pulse-marker" r={7} fill={MARKER_COLORS.focused} opacity={0.5} />}
                <circle
                  r={isFocused ? 6 : isVerified ? 5.5 : 4.5}
                  fill={MARKER_COLORS[kind]}
                  stroke="rgba(11,11,12,0.9)"
                  strokeWidth={1.2}
                />
              </Marker>
            );
          })}
      </ComposableMap>
    </div>
  );
}
