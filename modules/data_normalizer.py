"""Normalização de dados externos (UCDP, OFAC) para o schema interno do GeoShock.

A GDELT já produz eventos "soltos" (via ``collector.article_to_event``), sem
severidade real nem geolocalização precisa. Este módulo converte as duas
fontes de maior confiança validadas para o projeto:

* **UCDP GED** — eventos de conflito armado, com fatalidades estimadas e
  coordenadas reais. Vira um evento (``kind="verified"``) no mesmo formato
  dos eventos GDELT/curados, só que com intensidade calculada a partir de
  mortes reais em vez do valor fixo ``5.0`` usado para eventos da GDELT.
* **OFAC SDN** — lista de entidades sancionadas. Não vira "evento" (não tem
  data/local no mesmo sentido); vira uma confirmação binária anexada ao
  resumo da região.
"""

from __future__ import annotations

import math
from typing import Any

from utils.geocoder import iso_from_country_name
from utils.validators import sanitize_text

# type_of_violence da UCDP: 1=conflito estatal, 2=conflito não-estatal,
# 3=violência unilateral contra civis. O vocabulário do GeoShock não tem essa
# granularidade; todos mapeiam para "armed_conflict" (a distinção mais fina
# fica disponível em `raw.type_of_violence` para quem quiser usá-la depois).
_UCDP_EVENT_TYPE = "armed_conflict"

# Placeholder que a base "candidata" da UCDP usa para nomes de conflito/lado
# ainda não revisados editorialmente (ex.: "XXX365"). Quando presente,
# usamos a manchete-fonte como título em vez do nome do conflito.
_UCDP_PLACEHOLDER_PREFIX = "XXX"


def _fatalities_to_intensity(best: int) -> float:
    """Converte a estimativa de mortes (``best``) da UCDP numa intensidade 0-10.

    Escala logarítmica (mortes têm distribuição extremamente assimétrica: a
    maioria dos eventos tem 1-5 mortes, poucos têm centenas/milhares).
    ``best=1`` -> ~2.6, ``best=20`` -> ~4.6, ``best=100`` -> ~6.0,
    ``best=1000`` -> ~8.0. Clampado em [1.0, 10.0].
    """
    value = 2.0 + 2.0 * math.log10(max(best, 0) + 1)
    return round(min(10.0, max(1.0, value)), 1)


def normalize_ucdp_event(row: dict[str, Any]) -> dict[str, Any]:
    """Converte uma linha crua do CSV da UCDP no formato interno de evento.

    Espera um dict com as chaves produzidas por
    :meth:`utils.ucdp_client.UcdpClient.parse_csv`.
    """
    conflict_name = (row.get("conflict_name") or "").strip()
    headline = sanitize_text(row.get("source_headline") or "", max_length=300)
    if conflict_name and not conflict_name.startswith(_UCDP_PLACEHOLDER_PREFIX):
        title = conflict_name
    else:
        title = headline or "Evento de conflito armado (UCDP)"

    try:
        best = int(float(row.get("best") or 0))
    except (TypeError, ValueError):
        best = 0

    try:
        lat = float(row.get("latitude") or 0.0)
        lon = float(row.get("longitude") or 0.0)
    except (TypeError, ValueError):
        lat, lon = 0.0, 0.0

    country = (row.get("country") or "").strip()
    iso = iso_from_country_name(country)

    return {
        "id": f"ucdp_{row.get('id', '')}",
        "title": sanitize_text(title, max_length=300),
        "date": (row.get("date_start") or "")[:10] or "1970-01-01",
        "region": country or "Não especificada",
        "country_codes": [iso] if iso else [],
        "lat": lat,
        "lon": lon,
        "event_type": _UCDP_EVENT_TYPE,
        "intensity_score": _fatalities_to_intensity(best),
        "description": headline or title,
        "commodities_affected": [],
        "source": "UCDP Georeferenced Event Dataset (candidato)",
        "kind": "verified",
        "fatalities_best": best,
    }


def normalize_ucdp_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aplica :func:`normalize_ucdp_event` a uma lista de linhas cruas."""
    return [normalize_ucdp_event(row) for row in rows]


def normalize_ofac_check(entities: list[dict[str, Any]]) -> dict[str, Any]:
    """Resume uma lista de entidades OFAC numa confirmação de sanções.

    Não descreve eventos individuais (a lista de sanções não tem "quando
    aconteceu" no sentido de um evento) — descreve se há, e quantas,
    sanções ativas confirmadas.
    """
    programs: set[str] = set()
    names: list[str] = []
    for ent in entities:
        for p in ent.get("programs") or []:
            if p:
                programs.add(p)
        if ent.get("name"):
            names.append(ent["name"])

    return {
        "active": len(entities) > 0,
        "count": len(entities),
        "programs": sorted(programs),
        "sample_names": names[:5],
    }
