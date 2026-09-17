// Paleta dos marcadores do mapa — fonte única, usada pelo WorldMap e pela
// legenda em page.tsx. Mantê-los no mesmo lugar evita a legenda "esquecer"
// uma cor quando um novo `kind` de evento é adicionado.

export type MarkerKind = "focused" | "verified" | "live" | "curated";

export const MARKER_COLORS: Record<MarkerKind, string> = {
  focused: "#fb7185", // evento selecionado no momento
  verified: "#dc2626", // UCDP — severidade real (fatalidades), alta confiança
  live: "#e9a94b", // GDELT — pulso em tempo real, não verificado
  curated: "#7dd3fc", // base histórica curada do GeoShock
};

export const MARKER_LABELS: Record<MarkerKind, string> = {
  focused: "Em foco",
  verified: "Verificado (UCDP)",
  live: "Ao vivo (GDELT)",
  curated: "Curado",
};

export function markerKindFor(kind: string | undefined, isFocused: boolean): MarkerKind {
  if (isFocused) return "focused";
  if (kind === "verified") return "verified";
  if (kind === "live") return "live";
  return "curated";
}
