"""Testes do resumidor de região (offline; LLM e GDELT não são chamados)."""

from modules import region_summarizer as rs
from modules.briefing_generator import LLMClient
from modules.regions import get_region


def _events():
    return [
        {"title": "Ataque em zona de grãos", "event_type": "armed_conflict",
         "region": "Europa Oriental", "commodities_affected": [], "intensity_score": 8.0},
        {"title": "Sanções ao setor de energia", "event_type": "economic_sanction",
         "region": "Europa Oriental", "commodities_affected": [], "intensity_score": 6.0},
    ]


def test_aggregate_commodities_union_no_dupes():
    region = get_region("eastern_europe")
    commodities = rs.aggregate_commodities(_events(), region)
    assert len(commodities) == len(set(commodities))
    assert "wheat" in commodities or "natural_gas" in commodities


def test_aggregate_commodities_empty_falls_back_to_region_default():
    region = get_region("middle_east")
    commodities = rs.aggregate_commodities([], region)
    assert commodities  # não vazio


def test_risk_level_scales_with_volume():
    assert rs.risk_level([]) == "baixo"
    many = _events() * 4
    assert rs.risk_level(many) in {"médio", "alto"}


def test_summarize_region_offline_has_text(monkeypatch):
    # Remove quaisquer chaves reais do ambiente (vindas do .env do backend)
    # para garantir que o teste nunca dependa de rede, independentemente da
    # ordem de coleta dos testes.
    for env_var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(env_var, raising=False)

    region = get_region("eastern_europe")
    events = _events()
    commodities = rs.aggregate_commodities(events, region)
    out = rs.summarize_region(region, events, commodities, llm_client=LLMClient(api_key=""))
    assert out["offline"] is True
    assert len(out["summary"]) > 40
    assert "investimento" not in out["summary"].lower() or "não" in out["summary"].lower()


def test_region_endpoint_unknown_404():
    import api_server
    from fastapi import HTTPException
    import pytest
    with pytest.raises(HTTPException) as exc:
        api_server.region_detail("inexistente")
    assert exc.value.status_code == 404


def test_region_endpoint_structure(monkeypatch):
    import api_server

    # GDELT offline determinista: sem artigos.
    monkeypatch.setattr(api_server._collector, "search_gdelt", lambda *a, **k: [])
    # region_detail() não recebe llm_client explícito, então summarize_region()
    # monta um LLMClient() por conta própria a partir do ambiente. Removemos
    # as chaves reais do .env do backend para garantir que o teste nunca
    # dependa de rede, independentemente de quais credenciais existam.
    for env_var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(env_var, raising=False)

    out = api_server.region_detail("middle_east")
    assert out["region"]["id"] == "middle_east"
    assert out["commodities_at_risk"]
    assert "summary" in out and len(out["summary"]) > 20
    assert out["meta"]["n_live"] == 0
    assert out["meta"]["offline"] is True
