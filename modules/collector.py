"""Módulo 1 — Coleta e ingestão de dados.

Reúne três fontes de eventos geopolíticos e dados de mercado:

* a base local de eventos históricos validados (``data/historical_events.json``);
* artigos ao vivo da GDELT, convertidos em eventos estruturados parciais;
* séries de preços de commodities da FRED (delegadas ao :class:`FredClient`).

A função :func:`article_to_event` transforma um artigo GDELT cru num esqueleto
de evento que o usuário pode revisar e completar na interface antes da análise.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from utils.fred_client import FredClient
from utils.gdelt_client import GdeltClient, to_gdelt_datetime
from utils.validators import EVENT_TYPES, sanitize_text

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_HISTORICAL_PATH = _DATA_DIR / "historical_events.json"

# Palavras-chave (em inglês, idioma dominante na GDELT) para inferir o tipo de
# evento a partir do título de um artigo. Heurística simples e auditável.
_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "armed_conflict": ("invasion", "war", "attack", "offensive", "troops", "military strike"),
    "economic_sanction": ("sanction", "embargo", "ban on", "export ban"),
    "military_tension": ("tension", "mobiliz", "warship", "missile test", "standoff"),
    "diplomatic_crisis": ("expel", "diplomatic", "summon", "sever ties", "ambassador"),
    "institutional_disruption": ("pandemic", "lockdown", "coup", "collapse", "outbreak"),
    "trade_restriction": ("tariff", "trade war", "quota", "import duty"),
    "infrastructure_attack": ("pipeline", "refinery", "power grid", "sabotage", "drone strike"),
    "territorial_dispute": ("annex", "territorial", "border dispute", "occupation"),
}


class Collector:
    """Fachada de coleta de dados das três fontes do GeoShock."""

    def __init__(
        self,
        gdelt_client: GdeltClient | None = None,
        fred_client: FredClient | None = None,
        historical_path: Path | str | None = None,
    ) -> None:
        self.gdelt = gdelt_client or GdeltClient()
        self.fred = fred_client or FredClient()
        self.historical_path = Path(historical_path) if historical_path else _HISTORICAL_PATH

    # ------------------------------------------------------------------ #
    # Base histórica local
    # ------------------------------------------------------------------ #
    def load_historical_events(self) -> list[dict[str, Any]]:
        """Carrega os eventos históricos pré-validados do arquivo JSON."""
        with open(self.historical_path, encoding="utf-8") as fh:
            payload = json.load(fh)
        return payload.get("events", [])

    def get_event_by_id(self, event_id: str) -> dict[str, Any] | None:
        """Retorna um evento histórico pelo ``id``, ou None se inexistente."""
        for event in self.load_historical_events():
            if event.get("id") == event_id:
                return event
        return None

    # ------------------------------------------------------------------ #
    # GDELT ao vivo
    # ------------------------------------------------------------------ #
    def search_gdelt(
        self,
        query: str,
        max_records: int = 50,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Busca artigos recentes na GDELT para uma query de texto livre."""
        start_dt = to_gdelt_datetime(start_date) if start_date else None
        end_dt = to_gdelt_datetime(end_date) if end_date else None
        return self.gdelt.search_articles(
            query, max_records=max_records, start_datetime=start_dt, end_datetime=end_dt
        )

    # ------------------------------------------------------------------ #
    # FRED (delegação)
    # ------------------------------------------------------------------ #
    def get_price_series(
        self, commodity: str, start_date: str | None = None, end_date: str | None = None
    ):
        """Atalho para :meth:`FredClient.get_commodity_series`."""
        return self.fred.get_commodity_series(commodity, start_date, end_date)


def infer_event_type(text: str) -> str:
    """Infere o ``event_type`` a partir de palavras-chave no texto.

    Default conservador: ``military_tension`` quando nada combina, por ser o
    tipo de menor intensidade implícita entre os candidatos comuns.
    """
    lowered = text.lower()
    for event_type, keywords in _TYPE_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            return event_type
    return "military_tension"


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:48] or "evento"


def _parse_seendate(seendate: str) -> str:
    """Converte o ``seendate`` da GDELT (YYYYMMDDTHHMMSSZ) para ISO YYYY-MM-DD."""
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(seendate, fmt).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue
    return datetime.today().strftime("%Y-%m-%d")


def article_to_event(article: dict[str, Any]) -> dict[str, Any]:
    """Converte um artigo GDELT num esqueleto de evento estruturado.

    O resultado é **parcial**: campos como ``lat``/``lon`` e
    ``intensity_score`` recebem defaults e devem ser revisados pelo usuário na
    interface. ``commodities_affected`` é deixado vazio e preenchido depois pelo
    mapeamento do pré-processador.
    """
    title = sanitize_text(article.get("title", "Evento sem título"), max_length=300)
    source_country = article.get("sourcecountry", "")
    event_type = infer_event_type(title)

    return {
        "id": _slugify(title) + "_" + _parse_seendate(article.get("seendate", "")).replace("-", ""),
        "title": title,
        "date": _parse_seendate(article.get("seendate", "")),
        "region": source_country or "Não especificada",
        "country_codes": [],
        "lat": 0.0,
        "lon": 0.0,
        "event_type": event_type if event_type in EVENT_TYPES else "military_tension",
        "intensity_score": 5.0,
        "description": title,
        "commodities_affected": [],
        "source": f"GDELT — {article.get('domain', 'desconhecido')} ({article.get('url', '')})",
    }
