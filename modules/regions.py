"""Modelo de regiões e composição dos eventos curados do mapa."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from modules.collector import Collector
from utils.geocoder import geocode_event

_DATA = Path(__file__).resolve().parent.parent / "data" / "regions.json"


@lru_cache(maxsize=1)
def load_regions() -> list[dict[str, Any]]:
    with open(_DATA, encoding="utf-8") as fh:
        return json.load(fh)["regions"]


def get_region(region_id: str) -> dict[str, Any] | None:
    for region in load_regions():
        if region["id"] == region_id:
            return region
    return None


def curated_map_events() -> list[dict[str, Any]]:
    """Eventos históricos geocodificados, sem embedding, prontos para o mapa."""
    events = []
    for ev in Collector().load_historical_events():
        geo = geocode_event(ev)
        geo.pop("embedding", None)
        geo["kind"] = "curated"
        events.append(geo)
    return events
