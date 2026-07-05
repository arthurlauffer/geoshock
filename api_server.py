"""GeoShock — Backend HTTP (FastAPI).

Expõe o pipeline RAG (em Python) como uma API REST consumida pelo frontend
Next.js. Toda a inteligência permanece em Python: ChromaDB, embeddings
(sentence-transformers), FRED, GDELT e o LLM (Gemini/OpenAI/Anthropic).

As chaves de API são lidas automaticamente do arquivo ``.env`` — o frontend
não precisa enviá-las.

Execução::

    uvicorn api_server:app --reload --port 8000
"""

from __future__ import annotations

import os
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from modules import briefing_generator, collector, impact_analyzer, preprocessor, regions as regions_mod
from modules import region_summarizer
from modules.briefing_generator import LLMClient
from modules.similarity_engine import SimilarityEngine
from utils.fred_client import FredClient
from utils.geocoder import geocode_event
from utils.validators import EVENT_TYPES, ValidationError

load_dotenv()

app = FastAPI(title="GeoShock API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev: liberado. Em produção, restringir ao domínio do front.
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singletons reaproveitados entre requisições (motor de similaridade é caro).
_engine: SimilarityEngine | None = None
_collector = collector.Collector()


def get_engine() -> SimilarityEngine:
    global _engine
    if _engine is None:
        _engine = SimilarityEngine()
        _engine.ensure_initialized()
    return _engine


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #
class AnalyzeRequest(BaseModel):
    event: Optional[dict[str, Any]] = None
    event_id: Optional[str] = None
    n_analogs: int = 3
    window: int = 30


# --------------------------------------------------------------------------- #
# Status / metadados
# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health() -> dict[str, Any]:
    provider = os.getenv("LLM_PROVIDER", "anthropic")
    llm = LLMClient(provider=provider)
    return {
        "status": "ok",
        "llm_provider": provider,
        "llm_live": llm.is_live,
        "fred_live": FredClient().is_live,
        "indexed_events": get_engine().count(),
    }


@app.get("/api/event_types")
def event_types() -> dict[str, str]:
    return EVENT_TYPES


@app.get("/api/events")
def list_events() -> dict[str, Any]:
    return {"events": _collector.load_historical_events()}


@app.get("/api/regions")
def list_regions() -> dict[str, Any]:
    return {"regions": regions_mod.load_regions()}


@app.get("/api/map_events")
def map_events() -> dict[str, Any]:
    return {"events": regions_mod.curated_map_events()}


@app.get("/api/region/{region_id}")
def region_detail(region_id: str) -> dict[str, Any]:
    region = regions_mod.get_region(region_id)
    if region is None:
        raise HTTPException(status_code=404, detail=f"Região desconhecida: {region_id}")

    articles = _collector.search_gdelt(region["gdelt_query"], max_records=12)
    live_events: list[dict[str, Any]] = []
    for art in articles:
        if not art.get("title"):
            continue
        ev = collector.article_to_event(art)
        # Sem país no artigo: usa o 1º país da região como fallback de coordenada.
        if not ev.get("country_codes"):
            ev["country_codes"] = region["countries"][:1]
        ev = geocode_event(ev)
        ev["kind"] = "live"
        live_events.append(ev)

    commodities = region_summarizer.aggregate_commodities(live_events, region)
    summary = region_summarizer.summarize_region(region, live_events, commodities)
    return {
        "region": region,
        "summary": summary["summary"],
        "risk_level": summary["risk_level"],
        "live_events": live_events,
        "commodities_at_risk": commodities,
        "meta": {"offline": summary["offline"], "n_live": len(live_events)},
    }


# --------------------------------------------------------------------------- #
# GDELT ao vivo
# --------------------------------------------------------------------------- #
@app.get("/api/gdelt/search")
def gdelt_search(
    query: str = Query(..., min_length=2),
    max_records: int = 25,
) -> dict[str, Any]:
    articles = _collector.search_gdelt(query, max_records=max_records)
    events = [collector.article_to_event(a) for a in articles if a.get("title")]
    return {"articles": articles, "events": events}


# --------------------------------------------------------------------------- #
# Pipeline principal
# --------------------------------------------------------------------------- #
@app.post("/api/analyze")
def analyze(req: AnalyzeRequest) -> dict[str, Any]:
    raw = req.event
    if raw is None and req.event_id:
        raw = _collector.get_event_by_id(req.event_id)
    if raw is None:
        raise HTTPException(status_code=400, detail="Informe 'event' ou 'event_id'.")

    fred = FredClient()          # lê FRED_API_KEY do .env
    llm = LLMClient()            # lê LLM_PROVIDER + chave do .env

    try:
        event = preprocessor.structure_event(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    event["embedding"] = preprocessor.embed_event(event)
    similar = get_engine().search_similar_events(event, n_results=req.n_analogs)
    commodities = preprocessor.map_commodities(event)
    price_data = impact_analyzer.get_price_impact(
        commodities, event["date"], window_days=[7, 30, 90], fred_client=fred
    )
    historical = impact_analyzer.analyze_historical_analogs(similar, commodities, fred_client=fred)
    briefing = briefing_generator.generate(
        event, similar, price_data, historical,
        commodities_at_risk=commodities, llm_client=llm,
    )

    event.pop("embedding", None)  # não serializar o vetor de 384 dims
    return {
        "event": event,
        "similar": similar,
        "commodities": commodities,
        "price_data": price_data,
        "historical_summary": historical,
        "briefing": briefing,
    }


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "GeoShock API", "docs": "/docs"}
