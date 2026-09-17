"""Testes do cliente UCDP (offline; parsing puro sobre CSV fixo).

O CSV de exemplo replica o cabeçalho e o formato reais validados manualmente
contra o arquivo público da UCDP em 2026-09 (ver utils/ucdp_client.py).
"""

from __future__ import annotations

import requests

from utils.ucdp_client import UcdpClient

_SAMPLE_CSV = """id,type_of_violence,conflict_name,side_a,side_b,date_start,source_headline,country,region,latitude,longitude,where_prec,best,high,low
612649,1,XXX365,XXX365,XXX365,2026-01-28 00:00:00.000,"Two people were killed in armed attacks in the North Caucasus.",Russia (Soviet Union),Europe,42.595681,47.717372,1,2,2,2
700001,1,Government of Ukraine - Government of Russia,Government of Russia,Government of Ukraine,2022-02-24 00:00:00.000,"Russian forces launched a large-scale invasion of Ukraine.",Ukraine,Europe,50.45,30.52,1,45,60,30
700002,3,XXX999,XXX999,XXX999,2020-06-10 00:00:00.000,"Civilians killed in an attack in Mali.",Mali,Africa,17.6,-4.0,2,8,10,6
"""


def test_parse_csv_returns_expected_rows():
    rows = UcdpClient.parse_csv(_SAMPLE_CSV)
    assert len(rows) == 3
    assert rows[0]["id"] == "612649"
    assert rows[0]["country"] == "Russia (Soviet Union)"
    assert rows[1]["best"] == "45"


def test_search_events_filters_by_country(tmp_path):
    client = UcdpClient(cache_dir=tmp_path)
    (tmp_path / "ged_candidate.csv").write_text(_SAMPLE_CSV, encoding="utf-8")
    events = client.search_events(countries=["UA"])
    assert len(events) == 1
    assert events[0]["country"] == "Ukraine"


def test_search_events_resolves_parenthetical_country_name(tmp_path):
    client = UcdpClient(cache_dir=tmp_path)
    (tmp_path / "ged_candidate.csv").write_text(_SAMPLE_CSV, encoding="utf-8")
    events = client.search_events(countries=["RU"])
    assert len(events) == 1
    assert events[0]["id"] == "612649"


def test_search_events_filters_by_min_date(tmp_path):
    client = UcdpClient(cache_dir=tmp_path)
    (tmp_path / "ged_candidate.csv").write_text(_SAMPLE_CSV, encoding="utf-8")
    events = client.search_events(min_date="2022-01-01")
    dates = {e["id"] for e in events}
    assert dates == {"612649", "700001"}  # Mali (2020) fica de fora


def test_search_events_no_filters_returns_all(tmp_path):
    client = UcdpClient(cache_dir=tmp_path)
    (tmp_path / "ged_candidate.csv").write_text(_SAMPLE_CSV, encoding="utf-8")
    assert len(client.search_events()) == 3


def test_search_events_without_cache_or_network_returns_empty(tmp_path, monkeypatch):
    def _raise(*args, **kwargs):
        raise requests.ConnectionError("sem rede (simulado)")

    monkeypatch.setattr(requests, "get", _raise)
    client = UcdpClient(cache_dir=tmp_path)
    assert client.search_events() == []
