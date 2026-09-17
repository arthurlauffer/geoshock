"""Geocodificação de eventos por centróide de país.

Converte eventos sem coordenadas (ex.: vindos da GDELT) em pontos plotáveis no
mapa, usando uma tabela de centróides ISO 3166-1 alpha-2. Função pura e offline.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA = Path(__file__).resolve().parent.parent / "data" / "country_centroids.json"

# Nome de país (inglês, como a GDELT devolve em sourcecountry, ou como a UCDP
# nomeia em seu campo `country`) -> ISO2. Inclui variantes entre parênteses
# usadas pela UCDP (ex.: "Russia (Soviet Union)") já normalizadas antes do
# lookup por :func:`_strip_ucdp_suffix`.
_NAME_TO_ISO: dict[str, str] = {
    "ukraine": "UA", "russia": "RU", "poland": "PL", "belarus": "BY",
    "moldova": "MD", "romania": "RO", "iran": "IR", "iraq": "IQ",
    "saudi arabia": "SA", "israel": "IL", "syria": "SY", "yemen": "YE",
    "united arab emirates": "AE", "kuwait": "KW", "egypt": "EG", "libya": "LY",
    "algeria": "DZ", "morocco": "MA", "tunisia": "TN", "sudan": "SD",
    "nigeria": "NG", "ethiopia": "ET", "congo": "CD", "dr congo": "CD",
    "south africa": "ZA", "kenya": "KE", "china": "CN", "japan": "JP",
    "south korea": "KR", "north korea": "KP", "taiwan": "TW", "indonesia": "ID",
    "vietnam": "VN", "philippines": "PH", "malaysia": "MY", "thailand": "TH",
    "singapore": "SG", "brazil": "BR", "argentina": "AR", "venezuela": "VE",
    "colombia": "CO", "chile": "CL", "mexico": "MX", "united states": "US",
    "canada": "CA", "united kingdom": "GB",
    # Adicionados para cobrir os países mais frequentes na base UCDP GED
    # (conflitos armados) que ainda não apareciam via GDELT/eventos curados.
    "mali": "ML", "burkina faso": "BF", "lebanon": "LB", "pakistan": "PK",
    "somalia": "SO", "myanmar": "MM", "afghanistan": "AF", "ivory coast": "CI",
    "niger": "NE", "chad": "TD", "cameroon": "CM",
}

# Sufixos entre parênteses que a UCDP anexa a alguns nomes de país
# (ex.: "Yemen (North Yemen)", "Russia (Soviet Union)", "Myanmar (Burma)").
_PAREN_SUFFIX = re.compile(r"\s*\([^)]*\)\s*$")


@lru_cache(maxsize=1)
def _table() -> dict[str, list[float]]:
    with open(_DATA, encoding="utf-8") as fh:
        return json.load(fh)


def centroid(code: str) -> tuple[float, float] | None:
    """Centróide (lat, lon) de um código ISO2, ou None se desconhecido."""
    entry = _table().get((code or "").strip().upper())
    return (entry[0], entry[1]) if entry else None


def iso_from_country_name(name: str) -> str | None:
    """Resolve um nome de país (com ou sem sufixo entre parênteses) a ISO2.

    Cobre tanto o formato da GDELT (``sourcecountry``, nome simples) quanto o
    da UCDP (``country``, às vezes com sufixo histórico, ex.:
    ``"Russia (Soviet Union)"``).
    """
    cleaned = _PAREN_SUFFIX.sub("", (name or "")).strip().lower()
    return _NAME_TO_ISO.get(cleaned)


# Alias interno mantido para compatibilidade com o uso existente neste módulo.
_iso_from_name = iso_from_country_name


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
