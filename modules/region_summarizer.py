"""Resumo simples da situação de uma região, para o modo público.

Agrega commodities em risco, estima um nível de risco heurístico e gera um
resumo em linguagem clara via LLM, com fallback offline determinista. Não
produz previsão de preço nem recomendação de investimento.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from modules import preprocessor
from modules.briefing_generator import LLMClient

_MAPPING = Path(__file__).resolve().parent.parent / "data" / "commodity_mapping.json"

_REGION_SUMMARY_SYSTEM = (
    "Você é um analista de risco geopolítico. Explique, em português claro e sem "
    "jargão, a situação atual de uma região para um leitor leigo. Máximo 3 frases. "
    "Não faça previsão de preços nem recomendação de investimento."
)


def aggregate_commodities(live_events: list[dict[str, Any]], region: dict[str, Any]) -> list[str]:
    """União das commodities dos eventos; fallback para o default da região."""
    ordered: list[str] = []
    seen: set[str] = set()
    for ev in live_events:
        for c in preprocessor.map_commodities(ev):
            if c not in seen:
                seen.add(c)
                ordered.append(c)
    if ordered:
        return ordered

    # Sem eventos: usa o tipo predominante (ou o 1º mapeamento) da região.
    with open(_MAPPING, encoding="utf-8") as fh:
        mapping = json.load(fh)
    for etype in ("armed_conflict", "economic_sanction", "military_tension"):
        default = mapping.get(etype, {}).get("default")
        if default:
            return list(default)
    return ["crude_oil", "gold"]


def risk_level(live_events: list[dict[str, Any]]) -> str:
    """Heurística simples de risco por volume e intensidade (não é previsão)."""
    n = len(live_events)
    intensities = [float(e.get("intensity_score", 5.0)) for e in live_events]
    avg = sum(intensities) / n if n else 0.0
    if n >= 5 or avg >= 8.0:
        return "alto"
    if n >= 2 or avg >= 6.0:
        return "médio"
    return "baixo"


def summarize_region(
    region: dict[str, Any],
    live_events: list[dict[str, Any]],
    commodities: list[str],
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    """Gera o resumo simples da região (LLM ou template offline)."""
    level = risk_level(live_events)
    client = llm_client or LLMClient()
    titles = "; ".join(e.get("title", "") for e in live_events[:6]) or "sem eventos recentes"
    user = (
        f"Região: {region['name']}. Nível de risco estimado: {level}. "
        f"Eventos recentes: {titles}. Commodities mais expostas: {', '.join(commodities[:5])}. "
        "Escreva o resumo."
    )
    resp = client.generate(_REGION_SUMMARY_SYSTEM, user)
    if resp.get("offline") or not resp.get("text"):
        summary = _offline_summary(region, live_events, commodities, level)
        return {"summary": summary, "risk_level": level, "offline": True}
    return {"summary": resp["text"].strip(), "risk_level": level, "offline": False}


def _offline_summary(region, live_events, commodities, level) -> str:
    n = len(live_events)
    comm = ", ".join(commodities[:4]) or "diversas commodities"
    if n:
        situacao = f"há {n} evento(s) recente(s) monitorado(s)"
    else:
        situacao = "não há eventos recentes destacados no momento"
    return (
        f"Na região {region['name']}, {situacao}, com nível de risco estimado {level}. "
        f"As commodities mais expostas historicamente são {comm}. "
        "Este é um panorama educacional e não constitui recomendação de investimento."
    )
