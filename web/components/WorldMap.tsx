"use client";

import { ComposableMap, Geographies, Geography, Marker } from "react-simple-maps";
import type { GeoEvent, SimilarEvent } from "@/lib/types";

const GEO_URL =
  "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

interface Props {
  event: GeoEvent | null;
  analogs: SimilarEvent[];
}

export default function WorldMap({ event, analogs }: Props) {
  const hasEvent = event && (event.lat !== 0 || event.lon !== 0);

  return (
    <div className="w-full overflow-hidden rounded-xl">
      <ComposableMap
        projection="geoEqualEarth"
        projectionConfig={{ scale: 168 }}
        style={{ width: "100%", height: "auto" }}
      >
        <Geographies geography={GEO_URL}>
          {({ geographies }) =>
            geographies.map((geo) => (
              <Geography
                key={geo.rsmKey}
                geography={geo}
                style={{
                  default: {
                    fill: "rgba(255,255,255,0.05)",
                    stroke: "rgba(255,255,255,0.12)",
                    strokeWidth: 0.4,
                    outline: "none",
                  },
                  hover: {
                    fill: "rgba(233,169,75,0.16)",
                    stroke: "rgba(233,169,75,0.4)",
                    outline: "none",
                  },
                  pressed: { fill: "rgba(233,169,75,0.22)", outline: "none" },
                }}
              />
            ))
          }
        </Geographies>

        {analogs.map((a) => (
          <Marker key={a.id} coordinates={[a.lon, a.lat]}>
            <circle
              r={4.5}
              fill="#e9a94b"
              stroke="rgba(11,11,12,0.9)"
              strokeWidth={1.2}
            />
            <text
              y={-9}
              textAnchor="middle"
              style={{
                fill: "#f2bd6b",
                fontSize: 7.5,
                fontWeight: 600,
                pointerEvents: "none",
              }}
            >
              {a.title.length > 20 ? a.title.slice(0, 20) + "…" : a.title}
            </text>
          </Marker>
        ))}

        {hasEvent && (
          <Marker coordinates={[event!.lon, event!.lat]}>
            <circle className="pulse-marker" r={7} fill="#fb7185" opacity={0.5} />
            <circle
              r={6}
              fill="#fb7185"
              stroke="rgba(255,255,255,0.9)"
              strokeWidth={1.4}
            />
          </Marker>
        )}
      </ComposableMap>
    </div>
  );
}
