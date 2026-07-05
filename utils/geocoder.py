"""Geocodificação de eventos por centróide de país.

Converte eventos sem coordenadas (ex.: vindos da GDELT) em pontos plotáveis no
mapa, usando uma tabela de centróides ISO 3166-1 alpha-2. Função pura e offline.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA = Path(__file__).resolve().parent.parent / "data" / "country_centroids.json"

# Nome de país (inglês, como a GDELT devolve em sourcecountry) -> ISO2.
_NAME_TO_ISO: dict[str, str] = {
    "ukraine": "UA", "russia": "RU", "poland": "PL", "belarus": "BY",
    "moldova": "MD", "romania": "RO", "iran": "IR", "iraq": "IQ",
    "saudi arabia": "SA", "israel": "IL", "syria": "SY", "yemen": "YE",
    "united arab emirates": "AE", "kuwait": "KW", "egypt": "EG", "libya": "LY",
    "algeria": "DZ", "morocco": "MA", "tunisia": "TN", "sudan": "SD",
    "nigeria": "NG", "ethiopia": "ET", "congo": "CD", "south africa": "ZA",
    "kenya": "KE", "china": "CN", "japan": "JP", "south korea": "KR",
    "north korea": "KP", "taiwan": "TW", "indonesia": "ID", "vietnam": "VN",
    "philippines": "PH", "malaysia": "MY", "thailand": "TH", "singapore": "SG",
    "brazil": "BR", "argentina": "AR", "venezuela": "VE", "colombia": "CO",
    "chile": "CL", "mexico": "MX", "united states": "US", "canada": "CA",
    "united kingdom": "GB",
}


@lru_cache(maxsize=1)
def _table() -> dict[str, list[float]]:
    with open(_DATA, encoding="utf-8") as fh:
        return json.load(fh)


def centroid(code: str) -> tuple[float, float] | None:
    """Centróide (lat, lon) de um código ISO2, ou None se desconhecido."""
    entry = _table().get((code or "").strip().upper())
    return (entry[0], entry[1]) if entry else None


def _iso_from_name(name: str) -> str | None:
    return _NAME_TO_ISO.get((name or "").strip().lower())


def geocode_event(event: dict[str, Any]) -> dict[str, Any]:
    """Devolve cópia do evento com lat/lon preenchidos quando possível."""
    out = dict(event)
    lat, lon = out.get("lat") or 0.0, out.get("lon") or 0.0
    if lat != 0.0 or lon != 0.0:
        return out

    for code in out.get("country_codes") or []:
        c = centroid(code)
        if c:
            out["lat"], out["lon"] = c
            return out

    iso = _iso_from_name(out.get("region", ""))
    if iso:
        c = centroid(iso)
        if c:
            out["lat"], out["lon"] = c
    return out
