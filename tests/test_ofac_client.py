"""Testes do cliente OFAC (offline; parsing puro sobre XML fixo).

O XML de exemplo replica o schema real validado manualmente contra o
endpoint público da OFAC em 2026-09 (ver utils/ofac_client.py).
"""

from __future__ import annotations

import requests

from utils.ofac_client import OfacClient

_NS = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/ENHANCED_XML"

_SAMPLE_XML = f"""<?xml version="1.0" encoding="utf-8"?>
<sanctionsData xmlns="{_NS}">
  <entities>
    <entity id="26686">
      <generalInfo>
        <entityType>Individual</entityType>
      </generalInfo>
      <sanctionsLists>
        <sanctionsList id="27058">SDN List</sanctionsList>
      </sanctionsLists>
      <sanctionsPrograms>
        <sanctionsProgram id="28362">CYBER2</sanctionsProgram>
      </sanctionsPrograms>
      <names>
        <name id="42110">
          <translations>
            <translation id="35917">
              <formattedFullName>SAFAROV, Azamat</formattedFullName>
            </translation>
          </translations>
        </name>
      </names>
      <addresses>
        <address id="40462">
          <country>Russia</country>
        </address>
      </addresses>
    </entity>
    <entity id="26687">
      <generalInfo>
        <entityType>Entity</entityType>
      </generalInfo>
      <sanctionsLists>
        <sanctionsList id="27059">SDN List</sanctionsList>
      </sanctionsLists>
      <sanctionsPrograms>
        <sanctionsProgram id="28363">IRAN</sanctionsProgram>
      </sanctionsPrograms>
      <names>
        <name id="42111">
          <translations>
            <translation id="35918">
              <formattedFullName>SHADOW TRADING CO</formattedFullName>
            </translation>
          </translations>
        </name>
      </names>
      <addresses>
        <address id="40463">
          <country>Iran</country>
        </address>
      </addresses>
    </entity>
  </entities>
</sanctionsData>
"""


def test_parse_xml_returns_expected_entities():
    entities = OfacClient.parse_xml(_SAMPLE_XML.encode("utf-8"))
    assert len(entities) == 2
    names = {e["name"] for e in entities}
    assert names == {"SAFAROV, Azamat", "SHADOW TRADING CO"}


def test_parse_xml_extracts_countries_and_programs():
    entities = OfacClient.parse_xml(_SAMPLE_XML.encode("utf-8"))
    safarov = next(e for e in entities if e["name"] == "SAFAROV, Azamat")
    assert safarov["countries"] == ["Russia"]
    assert safarov["programs"] == ["CYBER2"]
    assert safarov["entity_type"] == "Individual"


def test_search_by_country_filters_correctly(tmp_path):
    client = OfacClient(cache_dir=tmp_path)
    (tmp_path / "sdn_entities.xml").write_bytes(_SAMPLE_XML.encode("utf-8"))
    russia_hits = client.search_by_country("Russia")
    assert len(russia_hits) == 1
    assert russia_hits[0]["name"] == "SAFAROV, Azamat"


def test_search_by_country_is_case_insensitive(tmp_path):
    client = OfacClient(cache_dir=tmp_path)
    (tmp_path / "sdn_entities.xml").write_bytes(_SAMPLE_XML.encode("utf-8"))
    assert len(client.search_by_country("russia")) == 1


def test_search_by_country_no_match_returns_empty(tmp_path):
    client = OfacClient(cache_dir=tmp_path)
    (tmp_path / "sdn_entities.xml").write_bytes(_SAMPLE_XML.encode("utf-8"))
    assert client.search_by_country("Brazil") == []


def test_search_without_cache_or_network_returns_empty(tmp_path, monkeypatch):
    def _raise(*args, **kwargs):
        raise requests.ConnectionError("sem rede (simulado)")

    monkeypatch.setattr(requests, "get", _raise)
    client = OfacClient(cache_dir=tmp_path)
    assert client.search_by_country("Russia") == []


def test_search_by_country_reparses_xml_only_once_per_instance(tmp_path, monkeypatch):
    """Guarda de regressão: consultar vários países não deve reprocessar o
    XML inteiro a cada chamada (bug real medido em produção: 6 países no
    mesmo request levavam ~24s por reparse repetido de um arquivo de
    ~100MB; com o cache em memória, cai para uma única passada).
    """
    (tmp_path / "sdn_entities.xml").write_bytes(_SAMPLE_XML.encode("utf-8"))
    client = OfacClient(cache_dir=tmp_path)

    calls = {"n": 0}
    original_parse = OfacClient.parse_xml

    def _counting_parse(xml_bytes):
        calls["n"] += 1
        return original_parse(xml_bytes)

    monkeypatch.setattr(OfacClient, "parse_xml", staticmethod(_counting_parse))

    client.search_by_country("Russia")
    client.search_by_country("Iran")
    client.search_by_country("Brazil")

    assert calls["n"] == 1
