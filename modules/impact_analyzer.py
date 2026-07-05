"""Módulo 4 — Motor de análise de impacto de preços (FRED).

Duas responsabilidades:

* :func:`get_price_impact` — para uma lista de commodities e uma data de
  referência, calcula a variação percentual de preço em janelas de 7, 30 e 90
  dias (event study simplificado, na linha de MacKinlay, 1997);
* :func:`analyze_historical_analogs` — agrega as variações observadas nos
  eventos históricos análogos (a partir dos ``verified_outcomes`` e/ou da FRED)
  em estatísticas por commodity (média, mediana e intervalo).

Tolerante a séries mensais: quando não há observação exata na data desejada,
usa a observação válida mais próxima dentro de uma janela de busca.
"""

from __future__ import annotations

import re
import statistics
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from utils.fred_client import FredClient, series_id_for

_PCT_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*%")
# Tolerância (em dias) para casar uma data com a observação FRED mais próxima.
# Generosa o bastante para cobrir séries mensais de commodities.
_NEAREST_TOLERANCE_DAYS = 45


def parse_pct(text: str) -> float | None:
    """Extrai um valor percentual de strings como ``"+32%"`` ou ``"-55%"``."""
    if text is None:
        return None
    match = _PCT_RE.search(str(text))
    return float(match.group(1)) if match else None


def _nearest_value(df: pd.DataFrame, target: datetime, direction: str) -> float | None:
    """Valor da observação mais próxima de ``target`` na direção indicada.

    ``direction='before'`` busca a última observação em ``<= target``;
    ``'after'`` busca a primeira em ``>= target``. Respeita
    :data:`_NEAREST_TOLERANCE_DAYS`.
    """
    if df.empty:
        return None
    target_ts = pd.Timestamp(target)
    tolerance = pd.Timedelta(days=_NEAREST_TOLERANCE_DAYS)

    if direction == "before":
        subset = df[df["date"] <= target_ts]
        if subset.empty:
            return None
        row = subset.iloc[-1]
    else:  # after
        subset = df[df["date"] >= target_ts]
        if subset.empty:
            return None
        row = subset.iloc[0]

    if abs(row["date"] - target_ts) > tolerance:
        return None
    return float(row["value"])


def get_price_impact(
    commodity_list: list[str],
    reference_date: str,
    window_days: list[int] | None = None,
    fred_client: FredClient | None = None,
) -> dict[str, Any]:
    """Calcula a variação de preço de cada commodity em torno de uma data.

    Ver assinatura e formato de retorno na seção 6.1 da especificação.
    """
    window_days = window_days or [7, 30, 90]
    client = fred_client or FredClient()
    ref = datetime.strptime(reference_date, "%Y-%m-%d")

    # Busca uma janela folgada antes e depois para acomodar séries mensais.
    start = (ref - timedelta(days=120)).strftime("%Y-%m-%d")
    end = (ref + timedelta(days=max(window_days) + 120)).strftime("%Y-%m-%d")

    result: dict[str, Any] = {}
    for commodity in commodity_list:
        series_id = series_id_for(commodity)
        if series_id is None:
            result[commodity] = {"series_id": None, "data_available": False}
            continue

        df = client.get_commodity_series(commodity, start, end)
        price_before = _nearest_value(df, ref, "before")

        entry: dict[str, Any] = {
            "series_id": series_id,
            "price_before": price_before,
            "data_available": price_before is not None,
            "offline": not client.is_live,
        }

        for window in window_days:
            after_date = ref + timedelta(days=window)
            price_after = _nearest_value(df, after_date, "after")
            entry[f"price_after_{window}d"] = price_after
            if price_before and price_after and price_before != 0:
                change = (price_after - price_before) / price_before * 100
                entry[f"change_{window}d_pct"] = f"{change:+.1f}%"
                entry[f"change_{window}d_value"] = round(change, 1)
            else:
                entry[f"change_{window}d_pct"] = None
                entry[f"change_{window}d_value"] = None

        result[commodity] = entry

    return result


# Mapeia prefixos de chaves de ``verified_outcomes`` para nomes de commodity.
_OUTCOME_PREFIX = {
    "wheat": "wheat",
    "corn": "corn",
    "natural_gas_eu": "natural_gas_eu",
    "natural_gas": "natural_gas",
    "crude_oil": "crude_oil",
    "copper": "copper",
    "aluminum": "aluminum",
    "gold": "gold",
    "soybeans": "soybeans",
    "fertilizers": "fertilizers",
}


def _commodity_from_outcome_key(key: str) -> str | None:
    """Resolve o nome da commodity a partir de uma chave de verified_outcomes."""
    for prefix, commodity in _OUTCOME_PREFIX.items():
        if key.startswith(prefix):
            return commodity
    return None


def analyze_historical_analogs(
    similar_events: list[dict[str, Any]],
    current_commodities: list[str],
    fred_client: FredClient | None = None,
) -> dict[str, Any]:
    """Agrega as variações observadas nos análogos por commodity.

    Para cada análogo, usa primeiro os ``verified_outcomes`` registrados (mais
    confiáveis) e, na ausência, consulta a FRED na data do análogo. Retorna,
    por commodity relevante, estatísticas agregadas (média, mediana, mínimo,
    máximo) e o número de precedentes que sustentam cada estimativa.
    """
    client = fred_client or FredClient()
    # commodity -> lista de variações (% em 30d) observadas nos análogos
    observations: dict[str, list[float]] = {c: [] for c in current_commodities}
    # commodity -> lista de fontes/eventos que sustentam cada observação
    provenance: dict[str, list[str]] = {c: [] for c in current_commodities}

    for event in similar_events:
        verified = (event.get("metadata") or {}).get("verified_outcomes") or {}
        event_label = event.get("title", event.get("id", "análogo"))

        used_commodities: set[str] = set()
        for key, value in verified.items():
            commodity = _commodity_from_outcome_key(key)
            if commodity and commodity in observations:
                pct = parse_pct(value)
                if pct is not None:
                    observations[commodity].append(pct)
                    provenance[commodity].append(f"{event_label} ({value})")
                    used_commodities.add(commodity)

        # Para commodities relevantes sem outcome verificado, tenta a FRED.
        for commodity in current_commodities:
            if commodity in used_commodities or not event.get("date"):
                continue
            impact = get_price_impact(
                [commodity], event["date"], window_days=[30], fred_client=client
            ).get(commodity, {})
            pct = impact.get("change_30d_value")
            if pct is not None:
                observations[commodity].append(pct)
                provenance[commodity].append(f"{event_label} (FRED {pct:+.1f}%)")

    summary: dict[str, Any] = {}
    for commodity in current_commodities:
        values = observations[commodity]
        if values:
            summary[commodity] = {
                "n_precedents": len(values),
                "mean_change_30d": round(statistics.mean(values), 1),
                "median_change_30d": round(statistics.median(values), 1),
                "min_change_30d": round(min(values), 1),
                "max_change_30d": round(max(values), 1),
                "confidence": _confidence_label(len(values)),
                "sources": provenance[commodity],
            }
        else:
            summary[commodity] = {
                "n_precedents": 0,
                "mean_change_30d": None,
                "median_change_30d": None,
                "min_change_30d": None,
                "max_change_30d": None,
                "confidence": "insuficiente",
                "sources": [],
            }
    return summary


def _confidence_label(n: int) -> str:
    """Rótulo de confiança baseado no número de precedentes."""
    if n >= 3:
        return "alta"
    if n == 2:
        return "média"
    if n == 1:
        return "baixa"
    return "insuficiente"
