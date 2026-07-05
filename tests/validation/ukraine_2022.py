"""Validação retroativa — casos do TCC (seção 9 da especificação).

Define os três casos de validação obrigatórios e a função de avaliação de
briefings. O caso principal é a invasão russa à Ucrânia (24 fev 2022), tratado
como se fosse um "novo evento": o evento é removido da base antes da busca, de
modo que o motor recupere apenas precedentes genuínos.

Execução direta::

    python -m tests.validation.ukraine_2022
"""

from __future__ import annotations

import re
import tempfile
from typing import Any

from modules import briefing_generator, impact_analyzer, preprocessor
from modules.similarity_engine import SimilarityEngine
from utils.fred_client import FredClient

# --------------------------------------------------------------------------- #
# Casos de validação
# --------------------------------------------------------------------------- #
VALIDATION_CASES: dict[str, dict[str, Any]] = {
    "ukraine_2022": {
        "label": "Invasão Russa à Ucrânia (24 fev 2022)",
        "expected_commodities": ["wheat", "corn", "fertilizers", "natural_gas"],
        "expected_analogs": ["gulf_war_1990", "arab_oil_embargo_1973"],
        "real_outcomes": {
            "wheat_30d": "+32%",
            "natural_gas_eu_30d": "+55%",
            "corn_30d": "+18%",
        },
        "success_criterion": (
            "O briefing menciona ao menos 3 das 4 commodities corretas e "
            "identifica análogos de conflitos em zonas produtoras/exportadoras."
        ),
        "min_commodity_recall": 0.75,
    },
    "iran_sanctions_2012": {
        "label": "Sanções ao Irã (jan 2012)",
        "expected_commodities": ["crude_oil"],
        "expected_analogs": ["arab_oil_embargo_1973", "hormuz_tensions_2019"],
        "real_outcomes": {"crude_oil_30d": "+8%"},
        "success_criterion": (
            "Identifica analogia com o embargo árabe de 1973 e/ou tensões no "
            "Estreito de Ormuz."
        ),
        "min_commodity_recall": 1.0,
    },
    "covid_lockdowns_2020": {
        "label": "COVID-19 Lockdowns (mar 2020)",
        "expected_commodities": ["crude_oil", "copper", "aluminum"],
        "expected_analogs": [],
        "real_outcomes": {"crude_oil_30d": "-55%"},
        "success_criterion": (
            "Identifica o caráter disruptivo sobre a demanda (não a oferta)."
        ),
        "min_commodity_recall": 0.66,
    },
}

# Nomes legíveis das commodities para o cálculo de recall textual.
_COMMODITY_ALIASES: dict[str, tuple[str, ...]] = {
    "wheat": ("wheat", "trigo"),
    "corn": ("corn", "maize", "milho"),
    "fertilizers": ("fertilizer", "fertilizante", "urea", "ureia"),
    "natural_gas": ("natural gas", "gás natural", "gas natural"),
    "crude_oil": ("crude oil", "petróleo", "petroleo", "wti", "oil"),
    "copper": ("copper", "cobre"),
    "aluminum": ("aluminum", "aluminium", "alumínio", "aluminio"),
    "soybeans": ("soybean", "soja"),
    "gold": ("gold", "ouro"),
}


def evaluate_briefing(briefing: str, expected: dict[str, Any]) -> dict[str, Any]:
    """Avalia um briefing contra o gabarito de um caso de validação.

    Retorna:
    - ``commodity_recall``: fração das commodities esperadas mencionadas;
    - ``analog_relevance``: score 1-5 da relevância dos análogos citados;
    - ``direction_correct``: se a direção (alta/baixa) bate com os outcomes reais;
    - ``sources_cited``: número de fontes históricas rastreáveis citadas.
    """
    text = briefing.lower()

    expected_commodities = expected["expected_commodities"]
    hits = 0
    for commodity in expected_commodities:
        aliases = _COMMODITY_ALIASES.get(commodity, (commodity,))
        if any(alias in text for alias in aliases):
            hits += 1
    commodity_recall = hits / len(expected_commodities) if expected_commodities else 0.0

    # Relevância dos análogos: proporção de eventos-fonte conhecidos citados,
    # mapeada para uma escala 1-5.
    analog_titles = {
        "gulf_war_1990": ("kuwait", "iraque", "golfo"),
        "arab_oil_embargo_1973": ("embargo", "opep", "1973", "árabe", "arabe"),
        "hormuz_tensions_2019": ("ormuz", "hormuz"),
    }
    expected_analogs = expected.get("expected_analogs", [])
    if expected_analogs:
        cited = sum(
            1
            for a in expected_analogs
            if any(token in text for token in analog_titles.get(a, (a,)))
        )
        analog_relevance = 1 + round(4 * cited / len(expected_analogs))
    else:
        analog_relevance = 3  # neutro quando não há análogos esperados

    # Direção do impacto: compara o sinal dos outcomes reais com o texto.
    real = expected.get("real_outcomes", {})
    directions_ok = 0
    for value in real.values():
        match = re.search(r"([+-])\s*\d", value)
        if not match:
            continue
        is_negative = match.group(1) == "-"
        mentions_drop = any(w in text for w in ("queda", "redução", "reducao", "caiu", "baixa", "colapso", "-"))
        mentions_rise = any(w in text for w in ("alta", "aumento", "elevação", "elevacao", "subiu", "disparo"))
        if is_negative and mentions_drop:
            directions_ok += 1
        elif not is_negative and mentions_rise:
            directions_ok += 1
    direction_correct = directions_ok > 0 if real else None

    sources_cited = len(re.findall(r"\d{4}", briefing))

    return {
        "commodity_recall": round(commodity_recall, 2),
        "analog_relevance": analog_relevance,
        "direction_correct": direction_correct,
        "sources_cited": sources_cited,
        "passed": commodity_recall >= expected.get("min_commodity_recall", 0.5),
    }


def run_case(case_id: str) -> dict[str, Any]:
    """Roda o pipeline para um caso de validação como se fosse evento novo.

    O evento-alvo é removido da collection antes da busca, garantindo que os
    análogos recuperados sejam precedentes genuínos.
    """
    # Usa uma collection isolada e temporária para não mutar a base de produção
    # (data/chroma_db). Cada caso parte de um banco limpo e determinista.
    tmp_dir = tempfile.mkdtemp(prefix="geoshock_validation_")
    engine = SimilarityEngine(persist_path=tmp_dir)
    fred = FredClient()  # offline por padrão; usa chave se presente no ambiente

    from modules.collector import Collector

    target = Collector().get_event_by_id(case_id)
    if target is None:
        raise ValueError(f"Evento de validação desconhecido: {case_id}")

    # Indexa todos os eventos EXCETO o alvo (simula um evento inédito).
    for event in Collector().load_historical_events():
        if event["id"] != case_id:
            engine.add_event(event)

    event = preprocessor.structure_event(target)
    event["embedding"] = preprocessor.embed_event(event)
    similar = engine.search_similar_events(event, n_results=5)

    commodities = preprocessor.map_commodities(event)
    price_data = impact_analyzer.get_price_impact(commodities, event["date"], fred_client=fred)
    historical = impact_analyzer.analyze_historical_analogs(similar, commodities, fred_client=fred)

    briefing = briefing_generator.generate(
        event, similar, price_data, historical, commodities_at_risk=commodities
    )

    metrics = evaluate_briefing(briefing["markdown"], VALIDATION_CASES[case_id])
    return {
        "case_id": case_id,
        "similar_ids": [e["id"] for e in similar],
        "commodities": commodities,
        "metrics": metrics,
        "briefing": briefing["markdown"],
    }


def _main() -> None:
    for case_id in VALIDATION_CASES:
        print("=" * 72)
        print(f"CASO: {VALIDATION_CASES[case_id]['label']}")
        result = run_case(case_id)
        print(f"Análogos recuperados: {result['similar_ids']}")
        print(f"Commodities mapeadas: {result['commodities']}")
        print(f"Métricas: {result['metrics']}")
        status = "✅ PASSOU" if result["metrics"]["passed"] else "❌ FALHOU"
        print(f"Status: {status}")


if __name__ == "__main__":
    _main()
