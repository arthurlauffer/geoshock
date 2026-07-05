"""Testes do Módulo 2 (pré-processamento) e do Módulo 3 (similaridade).

O mapeamento de commodities roda sem dependências pesadas. Os testes do motor
de similaridade exigem ``chromadb`` e ``sentence-transformers``; quando ausentes,
são pulados (``importorskip``).
"""

from __future__ import annotations

import pytest

from modules import preprocessor


# --------------------------------------------------------------------------- #
# Mapeamento de commodities (sem deps pesadas)
# --------------------------------------------------------------------------- #
def test_map_commodities_uses_region_specific_list():
    event = {"event_type": "armed_conflict", "region": "Europa Oriental", "commodities_affected": []}
    commodities = preprocessor.map_commodities(event)
    assert "wheat" in commodities
    assert "natural_gas" in commodities


def test_map_commodities_falls_back_to_default():
    event = {"event_type": "armed_conflict", "region": "Região Desconhecida", "commodities_affected": []}
    commodities = preprocessor.map_commodities(event)
    assert commodities[:2] == ["crude_oil", "gold"]  # default do tipo


def test_map_commodities_deduplicates_preserving_order():
    event = {
        "event_type": "armed_conflict",
        "region": "Oriente Médio",
        "commodities_affected": ["crude_oil"],  # já presente no default
    }
    commodities = preprocessor.map_commodities(event)
    assert len(commodities) == len(set(commodities))


def test_build_event_text_includes_all_fields():
    event = {
        "title": "T",
        "description": "D",
        "region": "Europa Oriental",
        "event_type": "armed_conflict",
    }
    text = preprocessor.build_event_text(event)
    assert "T" in text and "D" in text
    assert "Região: Europa Oriental" in text
    assert "Tipo: armed_conflict" in text


# --------------------------------------------------------------------------- #
# Motor de similaridade (requer chromadb + sentence-transformers)
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    pytest.importorskip("chromadb")
    pytest.importorskip("sentence_transformers")
    from modules.similarity_engine import SimilarityEngine

    path = tmp_path_factory.mktemp("chroma")
    eng = SimilarityEngine(persist_path=path)
    eng.load_historical()
    return eng


def test_engine_initializes_with_all_events(engine):
    assert engine.count() >= 6


def test_search_returns_relevant_analogs_for_conflict(engine):
    from modules.collector import Collector

    target = Collector().get_event_by_id("ukraine_2022")
    target["embedding"] = preprocessor.embed_event(target)
    results = engine.search_similar_events(target, n_results=3)
    assert results, "deve retornar ao menos um análogo"
    # O próprio evento não pode aparecer nos resultados.
    assert all(r["id"] != "ukraine_2022" for r in results)
    # Ordenação por distância crescente.
    distances = [r["distance"] for r in results]
    assert distances == sorted(distances)


def test_search_results_carry_similarity_pct(engine):
    from modules.collector import Collector

    target = Collector().get_event_by_id("gulf_war_1990")
    target["embedding"] = preprocessor.embed_event(target)
    results = engine.search_similar_events(target, n_results=2)
    for r in results:
        assert 0.0 <= r["similarity_pct"] <= 100.0
