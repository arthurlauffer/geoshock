"""Testes do Módulo 1 (coleta) e dos utilitários de validação/FRED/GDELT.

Todos os testes rodam offline (sem chaves de API nem rede).
"""

from __future__ import annotations

import pytest

from modules import collector
from utils import validators
from utils.fred_client import FredClient, series_id_for
from utils.gdelt_client import to_gdelt_datetime


# --------------------------------------------------------------------------- #
# Base histórica
# --------------------------------------------------------------------------- #
def test_load_historical_events_has_six_base_events():
    events = collector.Collector().load_historical_events()
    ids = {e["id"] for e in events}
    assert {"ukraine_2022", "gulf_war_1990", "arab_oil_embargo_1973"} <= ids
    assert len(events) >= 6


def test_get_event_by_id_returns_expected_event():
    event = collector.Collector().get_event_by_id("ukraine_2022")
    assert event is not None
    assert event["event_type"] == "armed_conflict"


def test_get_event_by_id_unknown_returns_none():
    assert collector.Collector().get_event_by_id("inexistente_999") is None


# --------------------------------------------------------------------------- #
# Conversão de artigo GDELT -> evento
# --------------------------------------------------------------------------- #
def test_article_to_event_infers_type_and_date():
    article = {
        "title": "Russia launches large-scale invasion of neighboring country",
        "seendate": "20220224T060000Z",
        "domain": "example.com",
        "url": "https://example.com/x",
        "sourcecountry": "Ukraine",
    }
    event = collector.article_to_event(article)
    assert event["event_type"] == "armed_conflict"
    assert event["date"] == "2022-02-24"
    assert event["source"].startswith("GDELT")


def test_infer_event_type_defaults_to_military_tension():
    assert collector.infer_event_type("a perfectly neutral headline") == "military_tension"


def test_infer_event_type_detects_sanctions():
    assert collector.infer_event_type("EU announces new sanction package") == "economic_sanction"


# --------------------------------------------------------------------------- #
# Validators
# --------------------------------------------------------------------------- #
def test_validate_event_normalizes_fields():
    raw = {
        "id": "x",
        "title": "  Título   com   espaços  ",
        "date": "2022-02-24",
        "region": "Europa Oriental",
        "event_type": "armed_conflict",
        "intensity_score": "9.5",
        "description": "desc",
        "country_codes": ["ua", "RU", "bad_code"],
        "lat": 200.0,  # inválida -> cai para 0
        "lon": 32.0,
    }
    norm = validators.validate_event(raw)
    assert norm["title"] == "Título com espaços"
    assert norm["intensity_score"] == 9.5
    assert norm["country_codes"] == ["UA", "RU"]
    assert norm["lat"] == 0.0  # latitude inválida zerada


def test_validate_event_rejects_bad_type():
    with pytest.raises(validators.ValidationError):
        validators.validate_event(
            {
                "id": "x",
                "title": "t",
                "date": "2022-02-24",
                "region": "r",
                "event_type": "not_a_type",
                "intensity_score": 5,
                "description": "d",
            }
        )


def test_validate_event_missing_fields():
    with pytest.raises(validators.ValidationError):
        validators.validate_event({"title": "só título"})


# --------------------------------------------------------------------------- #
# FRED offline
# --------------------------------------------------------------------------- #
def test_series_id_lookup():
    assert series_id_for("crude_oil") == "DCOILWTICO"
    assert series_id_for("commodity_inexistente") is None


def test_fred_offline_series_is_deterministic():
    client = FredClient(api_key="")  # força modo offline
    assert client.is_live is False
    df1 = client.get_commodity_series("wheat", "2022-01-01", "2022-06-01")
    df2 = client.get_commodity_series("wheat", "2022-01-01", "2022-06-01")
    assert not df1.empty
    assert list(df1["value"]) == list(df2["value"])  # reprodutível


# --------------------------------------------------------------------------- #
# GDELT helpers
# --------------------------------------------------------------------------- #
def test_to_gdelt_datetime_formats_correctly():
    assert to_gdelt_datetime("2022-02-24") == "20220224000000"
