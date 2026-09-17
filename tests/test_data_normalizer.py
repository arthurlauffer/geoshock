"""Testes do normalizador de dados externos (UCDP, OFAC) — offline, puro."""

from __future__ import annotations

from modules.data_normalizer import (
    _fatalities_to_intensity,
    normalize_ofac_check,
    normalize_ucdp_event,
    normalize_ucdp_events,
)


def test_fatalities_to_intensity_is_monotonic_and_bounded():
    values = [_fatalities_to_intensity(n) for n in (0, 1, 10, 100, 1000, 100000)]
    assert values == sorted(values)  # estritamente não-decrescente
    assert all(1.0 <= v <= 10.0 for v in values)


def test_fatalities_to_intensity_single_death_is_moderate_not_extreme():
    # Uma única morte não deve virar "risco máximo" nem "quase zero".
    v = _fatalities_to_intensity(1)
    assert 2.0 <= v <= 4.0


def test_normalize_ucdp_event_uses_conflict_name_when_available():
    row = {
        "id": "700001",
        "conflict_name": "Government of Ukraine - Government of Russia",
        "date_start": "2022-02-24 00:00:00.000",
        "source_headline": "Russian forces launched a large-scale invasion.",
        "country": "Ukraine",
        "latitude": "50.45",
        "longitude": "30.52",
        "best": "45",
    }
    event = normalize_ucdp_event(row)
    assert event["title"] == "Government of Ukraine - Government of Russia"
    assert event["date"] == "2022-02-24"
    assert event["lat"] == 50.45 and event["lon"] == 30.52
    assert event["country_codes"] == ["UA"]
    assert event["event_type"] == "armed_conflict"
    assert event["kind"] == "verified"
    assert event["fatalities_best"] == 45
    assert event["intensity_score"] > 5.0  # 45 mortes é um evento sério


def test_normalize_ucdp_event_falls_back_to_headline_for_placeholder_name():
    # Base "candidata" da UCDP: nomes ainda não revisados vêm como "XXX###".
    row = {
        "id": "612649",
        "conflict_name": "XXX365",
        "date_start": "2026-01-28 00:00:00.000",
        "source_headline": "Two people were killed in armed attacks.",
        "country": "Russia (Soviet Union)",
        "latitude": "42.595681",
        "longitude": "47.717372",
        "best": "2",
    }
    event = normalize_ucdp_event(row)
    assert event["title"] == "Two people were killed in armed attacks."
    assert event["country_codes"] == ["RU"]  # resolve apesar do sufixo entre parênteses


def test_normalize_ucdp_event_handles_missing_fields_gracefully():
    event = normalize_ucdp_event({"id": "1", "country": "Atlantis"})
    assert event["country_codes"] == []  # país desconhecido não quebra
    assert event["lat"] == 0.0 and event["lon"] == 0.0
    assert event["intensity_score"] >= 1.0


def test_normalize_ucdp_events_maps_a_list():
    rows = [{"id": "1", "country": "Mali"}, {"id": "2", "country": "Ukraine"}]
    events = normalize_ucdp_events(rows)
    assert len(events) == 2
    assert {e["id"] for e in events} == {"ucdp_1", "ucdp_2"}


def test_normalize_ofac_check_active_when_entities_present():
    entities = [
        {"name": "SAFAROV, Azamat", "programs": ["CYBER2"]},
        {"name": "SHADOW TRADING CO", "programs": ["CYBER2", "RUSSIA-EO14024"]},
    ]
    result = normalize_ofac_check(entities)
    assert result["active"] is True
    assert result["count"] == 2
    assert result["programs"] == ["CYBER2", "RUSSIA-EO14024"]
    assert "SAFAROV, Azamat" in result["sample_names"]


def test_normalize_ofac_check_inactive_when_empty():
    result = normalize_ofac_check([])
    assert result == {"active": False, "count": 0, "programs": [], "sample_names": []}
