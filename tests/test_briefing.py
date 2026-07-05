"""Testes do Módulo 4 (impacto) e do Módulo 5 (briefing), além da avaliação
de validação. Rodam offline (sem chaves de API).
"""

from __future__ import annotations

from modules import briefing_generator, impact_analyzer
from modules.briefing_generator import LLMClient
from tests.validation import ukraine_2022 as validation
from utils.fred_client import FredClient


# --------------------------------------------------------------------------- #
# Impact analyzer
# --------------------------------------------------------------------------- #
def test_parse_pct():
    assert impact_analyzer.parse_pct("+32%") == 32.0
    assert impact_analyzer.parse_pct("-55%") == -55.0
    assert impact_analyzer.parse_pct("sem valor") is None


def test_get_price_impact_offline_returns_windows():
    fred = FredClient(api_key="")
    result = impact_analyzer.get_price_impact(
        ["crude_oil"], "2022-02-24", window_days=[7, 30, 90], fred_client=fred
    )
    entry = result["crude_oil"]
    assert entry["series_id"] == "DCOILWTICO"
    assert entry["data_available"] is True
    assert "change_30d_pct" in entry


def test_get_price_impact_unknown_commodity():
    fred = FredClient(api_key="")
    result = impact_analyzer.get_price_impact(["xyz_unknown"], "2022-02-24", fred_client=fred)
    assert result["xyz_unknown"]["data_available"] is False


def test_analyze_historical_analogs_aggregates_verified_outcomes():
    fred = FredClient(api_key="")
    similar = [
        {
            "id": "gulf_war_1990",
            "title": "Invasão do Kuwait",
            "date": "1990-08-02",
            "metadata": {"verified_outcomes": {"crude_oil_change_30d": "+47%"}},
        }
    ]
    summary = impact_analyzer.analyze_historical_analogs(similar, ["crude_oil"], fred_client=fred)
    assert summary["crude_oil"]["n_precedents"] >= 1
    assert summary["crude_oil"]["mean_change_30d"] is not None


# --------------------------------------------------------------------------- #
# Briefing generator (modo offline)
# --------------------------------------------------------------------------- #
def _sample_inputs():
    event = {
        "id": "ukraine_2022",
        "title": "Invasão russa à Ucrânia",
        "date": "2022-02-24",
        "region": "Europa Oriental",
        "event_type": "armed_conflict",
        "intensity_score": 9.5,
        "description": "Conflito armado com impacto em grãos e energia.",
    }
    similar = [
        {
            "id": "gulf_war_1990",
            "title": "Invasão do Kuwait pelo Iraque",
            "date": "1990-08-02",
            "region": "Oriente Médio",
            "event_type": "armed_conflict",
            "similarity_pct": 72.0,
            "metadata": {"verified_outcomes": {"crude_oil_change_30d": "+47%"}},
        }
    ]
    commodities = ["wheat", "corn", "natural_gas", "fertilizers"]
    return event, similar, commodities


def test_offline_briefing_follows_format_and_is_substantial():
    event, similar, commodities = _sample_inputs()
    fred = FredClient(api_key="")
    price = impact_analyzer.get_price_impact(commodities, event["date"], fred_client=fred)
    hist = impact_analyzer.analyze_historical_analogs(similar, commodities, fred_client=fred)
    result = briefing_generator.generate(
        event, similar, price, hist, commodities_at_risk=commodities,
        llm_client=LLMClient(provider="anthropic", api_key=""),
    )
    md = result["markdown"]
    assert result["meta"]["offline"] is True
    assert "## Análise de Risco Geopolítico" in md
    assert "### Commodities em Risco" in md
    assert "recomendação de investimento" in md.lower()
    assert result["word_count"] > 100


def test_build_user_prompt_contains_context():
    event, similar, commodities = _sample_inputs()
    prompt = briefing_generator.build_user_prompt(event, similar, {}, commodities)
    assert "EVENTO ATUAL" in prompt
    assert "Invasão russa à Ucrânia" in prompt
    assert "Invasão do Kuwait pelo Iraque" in prompt


def test_llm_client_rejects_bad_provider():
    import pytest

    with pytest.raises(ValueError):
        LLMClient(provider="not_a_provider")


# --------------------------------------------------------------------------- #
# Avaliação de validação
# --------------------------------------------------------------------------- #
def test_evaluate_briefing_computes_commodity_recall():
    text = "O trigo e o milho subiram; o gás natural disparou em alta."
    expected = validation.VALIDATION_CASES["ukraine_2022"]
    metrics = validation.evaluate_briefing(text, expected)
    assert metrics["commodity_recall"] >= 0.75
    assert metrics["passed"] is True
