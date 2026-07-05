"""Testes do modelo de regiões e dos eventos curados do mapa (offline)."""

from modules import regions


def test_load_regions_has_eight():
    regs = regions.load_regions()
    assert len(regs) == 8
    ids = {r["id"] for r in regs}
    assert "middle_east" in ids and "eastern_europe" in ids


def test_get_region_known_and_unknown():
    assert regions.get_region("middle_east")["name"] == "Oriente Médio"
    assert regions.get_region("nao_existe") is None


def test_curated_map_events_all_geocoded():
    events = regions.curated_map_events()
    assert len(events) >= 5
    for ev in events:
        assert ev["lat"] != 0.0 or ev["lon"] != 0.0
        assert "embedding" not in ev


def test_endpoint_functions():
    import api_server
    assert len(api_server.list_regions()["regions"]) == 8
    assert len(api_server.map_events()["events"]) >= 5
