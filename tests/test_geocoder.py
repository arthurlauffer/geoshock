"""Testes do geocodificador de eventos (offline, puros)."""

from utils import geocoder


def test_centroid_known_country():
    lat, lon = geocoder.centroid("UA")
    assert 45.0 < lat < 53.0
    assert 25.0 < lon < 40.0


def test_centroid_unknown_returns_none():
    assert geocoder.centroid("ZZ") is None


def test_geocode_event_keeps_existing_coords():
    ev = {"lat": 10.0, "lon": 20.0, "country_codes": ["RU"], "region": "x"}
    out = geocoder.geocode_event(ev)
    assert (out["lat"], out["lon"]) == (10.0, 20.0)


def test_geocode_event_uses_country_code():
    ev = {"lat": 0.0, "lon": 0.0, "country_codes": ["IR"], "region": "x"}
    out = geocoder.geocode_event(ev)
    assert out["lat"] != 0.0 and out["lon"] != 0.0


def test_geocode_event_uses_region_name():
    ev = {"lat": 0.0, "lon": 0.0, "country_codes": [], "region": "Ukraine"}
    out = geocoder.geocode_event(ev)
    assert out["lat"] != 0.0


def test_geocode_event_unresolvable_stays_zero():
    ev = {"lat": 0.0, "lon": 0.0, "country_codes": [], "region": "Atlantis"}
    out = geocoder.geocode_event(ev)
    assert (out["lat"], out["lon"]) == (0.0, 0.0)
