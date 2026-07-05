# GeoShock — Explorador Geopolítico por Região — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar o GeoShock em uma plataforma map-first que mostra informação geopolítica por região do mundo (mapa multi-evento + resumo simples por região), preservando o motor RAG de commodities atrás de um modo analista.

**Architecture:** Backend FastAPI em Python expõe o RAG; frontend Next.js consome. Novos endpoints `/api/regions`, `/api/map_events`, `/api/region/{id}`. Um geocoder converte eventos GDELT (sem coordenadas) em pontos no mapa. Um resumidor de região gera texto simples via LLM com fallback offline.

**Tech Stack:** Python 3.9 · FastAPI · sentence-transformers · ChromaDB · GDELT · FRED · Gemini · Next.js 16 · React 19 · Tailwind v4 · react-simple-maps · @phosphor-icons/react.

## Global Constraints

- Todo o RAG e a lógica de dados permanecem em Python; o frontend só consome a API.
- Não quebrar os 27 testes Python existentes (`./venv/bin/python -m pytest tests/`) nem o `cd web && npm run build`.
- Nenhum texto gerado pode conter previsão de preço ou recomendação de investimento.
- O modo simples é o padrão da UI; nada técnico (tokens, similaridade %, validação) aparece nele.
- Funções de dados (geocoder, agregação de commodities) são puras e testáveis offline (sem rede, sem chaves).
- Chaves de API são lidas do `.env` pelo backend; o frontend nunca recebe chave.
- Comandos Python rodam com o venv do projeto: `./venv/bin/python`. Testes com `./venv/bin/python -m pytest`.
- Idioma de docstrings, comentários e textos de UI: português brasileiro.

---

## Pré-execução (controller, uma vez)

O projeto ainda não é repositório git. Antes da Task 1, o controlador executa:

```bash
cd /Users/arthurlauffer/Downloads/geoshock
git init
cat > .gitignore <<'EOF'
venv/
__pycache__/
*.pyc
.env
data/chroma_db/
data/_fred_cache/
data/_gdelt_cache/
web/node_modules/
web/.next/
web/out/
.DS_Store
EOF
git add -A
git commit -m "chore: baseline antes do explorador regional"
git checkout -b feat/explorador-regional
```

Todas as tarefas commitam nessa branch. `git diff` para revisão usa como BASE o commit anterior a cada tarefa.

---

## Task 1: Geocoder (centróides de país)

**Files:**
- Create: `data/country_centroids.json`
- Create: `utils/geocoder.py`
- Test: `tests/test_geocoder.py`

**Interfaces:**
- Produces:
  - `utils.geocoder.centroid(code: str) -> tuple[float, float] | None` — centróide (lat, lon) do código ISO 3166-1 alpha-2, ou None.
  - `utils.geocoder.geocode_event(event: dict) -> dict` — devolve cópia do evento com `lat`/`lon` preenchidos quando (a) já não forem 0/ausentes, senão (b) pelo primeiro `country_codes`, senão (c) por `region`/`sourcecountry` (nome em inglês) mapeado a ISO2. Mantém 0.0/0.0 se nada resolver.

- [ ] **Step 1: Criar `data/country_centroids.json`**

Conteúdo (cobre países das regiões e dos eventos históricos):

```json
{
  "UA": [49.0, 32.0], "RU": [61.5, 105.3], "PL": [51.9, 19.1], "BY": [53.7, 27.9],
  "MD": [47.4, 28.4], "RO": [45.9, 24.9], "IR": [32.4, 53.7], "IQ": [33.2, 43.7],
  "SA": [23.9, 45.1], "IL": [31.0, 34.9], "SY": [34.8, 38.9], "YE": [15.5, 48.5],
  "AE": [23.4, 53.8], "KW": [29.3, 47.5], "EG": [26.8, 30.8], "LY": [26.3, 17.2],
  "DZ": [28.0, 1.7], "MA": [31.8, -7.1], "TN": [33.9, 9.6], "SD": [12.9, 30.2],
  "NG": [9.1, 8.7], "ET": [9.1, 40.5], "CD": [-4.0, 21.8], "ZA": [-30.6, 22.9],
  "KE": [-0.0, 37.9], "CN": [35.9, 104.2], "JP": [36.2, 138.3], "KR": [35.9, 127.8],
  "KP": [40.3, 127.5], "TW": [23.7, 121.0], "ID": [-0.8, 113.9], "VN": [14.1, 108.3],
  "PH": [12.9, 121.8], "MY": [4.2, 101.9], "TH": [15.9, 100.9], "SG": [1.35, 103.8],
  "BR": [-14.2, -51.9], "AR": [-38.4, -63.6], "VE": [6.4, -66.6], "CO": [4.6, -74.3],
  "CL": [-35.7, -71.5], "MX": [23.6, -102.5], "US": [39.8, -98.6], "CA": [56.1, -106.3],
  "GB": [54.0, -2.0]
}
```

- [ ] **Step 2: Escrever o teste que falha (`tests/test_geocoder.py`)**

```python
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
```

- [ ] **Step 3: Rodar o teste e confirmar que falha**

Run: `cd /Users/arthurlauffer/Downloads/geoshock && ./venv/bin/python -m pytest tests/test_geocoder.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'utils.geocoder'`.

- [ ] **Step 4: Implementar `utils/geocoder.py`**

```python
"""Geocodificação de eventos por centróide de país.

Converte eventos sem coordenadas (ex.: vindos da GDELT) em pontos plotáveis no
mapa, usando uma tabela de centróides ISO 3166-1 alpha-2. Função pura e offline.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA = Path(__file__).resolve().parent.parent / "data" / "country_centroids.json"

# Nome de país (inglês, como a GDELT devolve em sourcecountry) -> ISO2.
_NAME_TO_ISO: dict[str, str] = {
    "ukraine": "UA", "russia": "RU", "poland": "PL", "belarus": "BY",
    "moldova": "MD", "romania": "RO", "iran": "IR", "iraq": "IQ",
    "saudi arabia": "SA", "israel": "IL", "syria": "SY", "yemen": "YE",
    "united arab emirates": "AE", "kuwait": "KW", "egypt": "EG", "libya": "LY",
    "algeria": "DZ", "morocco": "MA", "tunisia": "TN", "sudan": "SD",
    "nigeria": "NG", "ethiopia": "ET", "congo": "CD", "south africa": "ZA",
    "kenya": "KE", "china": "CN", "japan": "JP", "south korea": "KR",
    "north korea": "KP", "taiwan": "TW", "indonesia": "ID", "vietnam": "VN",
    "philippines": "PH", "malaysia": "MY", "thailand": "TH", "singapore": "SG",
    "brazil": "BR", "argentina": "AR", "venezuela": "VE", "colombia": "CO",
    "chile": "CL", "mexico": "MX", "united states": "US", "canada": "CA",
    "united kingdom": "GB",
}


@lru_cache(maxsize=1)
def _table() -> dict[str, list[float]]:
    with open(_DATA, encoding="utf-8") as fh:
        return json.load(fh)


def centroid(code: str) -> tuple[float, float] | None:
    """Centróide (lat, lon) de um código ISO2, ou None se desconhecido."""
    entry = _table().get((code or "").strip().upper())
    return (entry[0], entry[1]) if entry else None


def _iso_from_name(name: str) -> str | None:
    return _NAME_TO_ISO.get((name or "").strip().lower())


def geocode_event(event: dict[str, Any]) -> dict[str, Any]:
    """Devolve cópia do evento com lat/lon preenchidos quando possível."""
    out = dict(event)
    lat, lon = out.get("lat") or 0.0, out.get("lon") or 0.0
    if lat != 0.0 or lon != 0.0:
        return out

    for code in out.get("country_codes") or []:
        c = centroid(code)
        if c:
            out["lat"], out["lon"] = c
            return out

    iso = _iso_from_name(out.get("region", ""))
    if iso:
        c = centroid(iso)
        if c:
            out["lat"], out["lon"] = c
    return out
```

- [ ] **Step 5: Rodar os testes e confirmar que passam**

Run: `cd /Users/arthurlauffer/Downloads/geoshock && ./venv/bin/python -m pytest tests/test_geocoder.py -v`
Expected: PASS (6 passed).

- [ ] **Step 6: Confirmar regressão**

Run: `./venv/bin/python -m pytest tests/ -q`
Expected: todos passam (33 no total).

- [ ] **Step 7: Commit**

```bash
git add data/country_centroids.json utils/geocoder.py tests/test_geocoder.py
git commit -m "feat: geocoder de eventos por centroide de pais"
```

---

## Task 2: Regiões + endpoints `/api/regions` e `/api/map_events`

**Files:**
- Create: `data/regions.json`
- Create: `modules/regions.py`
- Modify: `api_server.py` (adicionar dois endpoints, importar helpers)
- Test: `tests/test_regions.py`

**Interfaces:**
- Consumes: `utils.geocoder.geocode_event`; `modules.collector.Collector.load_historical_events`.
- Produces:
  - `modules.regions.load_regions() -> list[dict]` — lista das regiões do `regions.json`.
  - `modules.regions.get_region(region_id: str) -> dict | None`.
  - `modules.regions.curated_map_events() -> list[dict]` — eventos históricos geocodificados (todos com lat/lon != 0,0), sem embedding.
  - Endpoint `GET /api/regions -> {"regions": [...]}`.
  - Endpoint `GET /api/map_events -> {"events": [GeoEvent...]}`.

- [ ] **Step 1: Criar `data/regions.json`**

```json
{
  "regions": [
    { "id": "eastern_europe", "name": "Europa Oriental", "name_en": "Eastern Europe",
      "center": { "lat": 50.0, "lon": 30.0 },
      "countries": ["UA", "RU", "PL", "BY", "MD", "RO"],
      "gdelt_query": "(war OR invasion OR sanctions OR grain OR gas) (Ukraine OR Russia OR Poland OR Belarus)" },
    { "id": "middle_east", "name": "Oriente Médio", "name_en": "Middle East",
      "center": { "lat": 29.0, "lon": 45.0 },
      "countries": ["IR", "IQ", "SA", "IL", "SY", "YE", "AE", "KW"],
      "gdelt_query": "(sanctions OR strike OR conflict OR oil OR blockade) (Iran OR Israel OR Iraq OR Saudi OR Yemen)" },
    { "id": "north_africa", "name": "Norte da África", "name_en": "North Africa",
      "center": { "lat": 28.0, "lon": 18.0 },
      "countries": ["EG", "LY", "DZ", "MA", "TN", "SD"],
      "gdelt_query": "(conflict OR coup OR oil OR gas OR unrest) (Egypt OR Libya OR Algeria OR Sudan)" },
    { "id": "subsaharan_africa", "name": "África Subsaariana", "name_en": "Sub-Saharan Africa",
      "center": { "lat": 0.0, "lon": 22.0 },
      "countries": ["NG", "ET", "CD", "ZA", "KE"],
      "gdelt_query": "(conflict OR coup OR mining OR cobalt OR gold) (Nigeria OR Ethiopia OR Congo OR Kenya)" },
    { "id": "east_asia", "name": "Ásia Oriental", "name_en": "East Asia",
      "center": { "lat": 34.0, "lon": 118.0 },
      "countries": ["CN", "JP", "KR", "KP", "TW"],
      "gdelt_query": "(tension OR missile OR trade OR chips OR blockade) (China OR Taiwan OR Korea OR Japan)" },
    { "id": "southeast_asia", "name": "Sudeste Asiático", "name_en": "Southeast Asia",
      "center": { "lat": 5.0, "lon": 110.0 },
      "countries": ["ID", "VN", "PH", "MY", "TH", "SG"],
      "gdelt_query": "(dispute OR strait OR shipping OR palm oil OR conflict) (South China Sea OR Malacca OR Philippines OR Vietnam)" },
    { "id": "latin_america", "name": "América Latina", "name_en": "Latin America",
      "center": { "lat": -15.0, "lon": -60.0 },
      "countries": ["BR", "AR", "VE", "CO", "CL", "MX"],
      "gdelt_query": "(unrest OR sanctions OR oil OR copper OR soy) (Venezuela OR Brazil OR Argentina OR Chile)" },
    { "id": "north_america", "name": "América do Norte", "name_en": "North America",
      "center": { "lat": 45.0, "lon": -100.0 },
      "countries": ["US", "CA", "MX"],
      "gdelt_query": "(tariff OR trade war OR sanctions OR energy) (United States OR Canada OR Mexico)" }
  ]
}
```

- [ ] **Step 2: Escrever o teste que falha (`tests/test_regions.py`)**

```python
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
    assert len(events) >= 6
    for ev in events:
        assert ev["lat"] != 0.0 or ev["lon"] != 0.0
        assert "embedding" not in ev
```

- [ ] **Step 3: Rodar e confirmar falha**

Run: `./venv/bin/python -m pytest tests/test_regions.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'modules.regions'`.

- [ ] **Step 4: Implementar `modules/regions.py`**

```python
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
```

- [ ] **Step 5: Rodar e confirmar que passa**

Run: `./venv/bin/python -m pytest tests/test_regions.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Adicionar endpoints em `api_server.py`**

Após a linha de import `from modules import briefing_generator, collector, impact_analyzer, preprocessor`, adicionar:

```python
from modules import regions as regions_mod
```

Após o endpoint `list_events` (por volta da linha 88), adicionar:

```python
@app.get("/api/regions")
def list_regions() -> dict[str, Any]:
    return {"regions": regions_mod.load_regions()}


@app.get("/api/map_events")
def map_events() -> dict[str, Any]:
    return {"events": regions_mod.curated_map_events()}
```

- [ ] **Step 7: Testar os endpoints chamando as funções diretamente**

Adicionar ao final de `tests/test_regions.py`:

```python
def test_endpoint_functions():
    import api_server
    assert len(api_server.list_regions()["regions"]) == 8
    assert len(api_server.map_events()["events"]) >= 6
```

Run: `./venv/bin/python -m pytest tests/test_regions.py -v`
Expected: PASS (4 passed).

- [ ] **Step 8: Regressão + commit**

```bash
./venv/bin/python -m pytest tests/ -q
git add data/regions.json modules/regions.py api_server.py tests/test_regions.py
git commit -m "feat: modelo de regioes e endpoints /api/regions e /api/map_events"
```

---

## Task 3: Resumidor de região + `GET /api/region/{id}`

**Files:**
- Create: `modules/region_summarizer.py`
- Modify: `api_server.py` (endpoint `/api/region/{region_id}`)
- Test: `tests/test_region_summarizer.py`

**Interfaces:**
- Consumes: `modules.regions.get_region`; `modules.collector.Collector.search_gdelt` e `collector.article_to_event`; `utils.geocoder.geocode_event`; `modules.preprocessor.map_commodities`; `modules.briefing_generator.LLMClient`.
- Produces:
  - `modules.region_summarizer.aggregate_commodities(live_events: list[dict], region: dict) -> list[str]` — união (sem duplicatas, ordem preservada) das commodities dos eventos; se vazio, default do `event_type` predominante via `commodity_mapping.json`.
  - `modules.region_summarizer.risk_level(live_events: list[dict]) -> str` — "alto" | "médio" | "baixo" por volume/intensidade.
  - `modules.region_summarizer.summarize_region(region, live_events, commodities, llm_client=None) -> dict` — `{"summary": str, "risk_level": str, "offline": bool}`. Offline → template determinista.
  - Endpoint `GET /api/region/{region_id} -> {region, summary, risk_level, live_events, commodities_at_risk, meta}` ou 404.

- [ ] **Step 1: Escrever o teste que falha (`tests/test_region_summarizer.py`)**

```python
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


def test_summarize_region_offline_has_text():
    region = get_region("eastern_europe")
    events = _events()
    commodities = rs.aggregate_commodities(events, region)
    out = rs.summarize_region(region, events, commodities, llm_client=LLMClient(api_key=""))
    assert out["offline"] is True
    assert len(out["summary"]) > 40
    assert "investimento" not in out["summary"].lower() or "não" in out["summary"].lower()
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `./venv/bin/python -m pytest tests/test_region_summarizer.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'modules.region_summarizer'`.

- [ ] **Step 3: Implementar `modules/region_summarizer.py`**

```python
"""Resumo simples da situação de uma região, para o modo público.

Agrega commodities em risco, estima um nível de risco heurístico e gera um
resumo em linguagem clara via LLM, com fallback offline determinista. Não
produz previsão de preço nem recomendação de investimento.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from modules import preprocessor
from modules.briefing_generator import LLMClient

_MAPPING = Path(__file__).resolve().parent.parent / "data" / "commodity_mapping.json"

_REGION_SUMMARY_SYSTEM = (
    "Você é um analista de risco geopolítico. Explique, em português claro e sem "
    "jargão, a situação atual de uma região para um leitor leigo. Máximo 3 frases. "
    "Não faça previsão de preços nem recomendação de investimento."
)


def aggregate_commodities(live_events: list[dict[str, Any]], region: dict[str, Any]) -> list[str]:
    """União das commodities dos eventos; fallback para o default da região."""
    ordered: list[str] = []
    seen: set[str] = set()
    for ev in live_events:
        for c in preprocessor.map_commodities(ev):
            if c not in seen:
                seen.add(c)
                ordered.append(c)
    if ordered:
        return ordered

    # Sem eventos: usa o tipo predominante (ou o 1º mapeamento) da região.
    with open(_MAPPING, encoding="utf-8") as fh:
        mapping = json.load(fh)
    for etype in ("armed_conflict", "economic_sanction", "military_tension"):
        default = mapping.get(etype, {}).get("default")
        if default:
            return list(default)
    return ["crude_oil", "gold"]


def risk_level(live_events: list[dict[str, Any]]) -> str:
    """Heurística simples de risco por volume e intensidade (não é previsão)."""
    n = len(live_events)
    intensities = [float(e.get("intensity_score", 5.0)) for e in live_events]
    avg = sum(intensities) / n if n else 0.0
    if n >= 5 or avg >= 8.0:
        return "alto"
    if n >= 2 or avg >= 6.0:
        return "médio"
    return "baixo"


def summarize_region(
    region: dict[str, Any],
    live_events: list[dict[str, Any]],
    commodities: list[str],
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    """Gera o resumo simples da região (LLM ou template offline)."""
    level = risk_level(live_events)
    client = llm_client or LLMClient()
    titles = "; ".join(e.get("title", "") for e in live_events[:6]) or "sem eventos recentes"
    user = (
        f"Região: {region['name']}. Nível de risco estimado: {level}. "
        f"Eventos recentes: {titles}. Commodities mais expostas: {', '.join(commodities[:5])}. "
        "Escreva o resumo."
    )
    resp = client.generate(_REGION_SUMMARY_SYSTEM, user)
    if resp.get("offline") or not resp.get("text"):
        summary = _offline_summary(region, live_events, commodities, level)
        return {"summary": summary, "risk_level": level, "offline": True}
    return {"summary": resp["text"].strip(), "risk_level": level, "offline": False}


def _offline_summary(region, live_events, commodities, level) -> str:
    n = len(live_events)
    comm = ", ".join(commodities[:4]) or "diversas commodities"
    if n:
        situacao = f"há {n} evento(s) recente(s) monitorado(s)"
    else:
        situacao = "não há eventos recentes destacados no momento"
    return (
        f"Na região {region['name']}, {situacao}, com nível de risco estimado {level}. "
        f"As commodities mais expostas historicamente são {comm}. "
        "Este é um panorama educacional e não constitui recomendação de investimento."
    )
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `./venv/bin/python -m pytest tests/test_region_summarizer.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Adicionar o endpoint em `api_server.py`**

Adicionar o import perto dos outros de módulos:

```python
from modules import region_summarizer
from utils.geocoder import geocode_event
```

Após o endpoint `map_events`, adicionar:

```python
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
```

- [ ] **Step 6: Testar 404 e estrutura (sem rede) via monkeypatch**

Adicionar ao final de `tests/test_region_summarizer.py`:

```python
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
    out = api_server.region_detail("middle_east")
    assert out["region"]["id"] == "middle_east"
    assert out["commodities_at_risk"]
    assert "summary" in out and len(out["summary"]) > 20
    assert out["meta"]["n_live"] == 0
```

Run: `./venv/bin/python -m pytest tests/test_region_summarizer.py -v`
Expected: PASS (6 passed).

- [ ] **Step 7: Regressão + commit**

```bash
./venv/bin/python -m pytest tests/ -q
git add modules/region_summarizer.py api_server.py tests/test_region_summarizer.py
git commit -m "feat: resumo de regiao e endpoint /api/region/{id}"
```

---

## Task 4: Frontend — mapa multi-evento clicável

**Files:**
- Modify: `web/lib/types.ts` (tipos `Region`, `RegionDetail`, campo `kind` em evento)
- Modify: `web/lib/api.ts` (`fetchRegions`, `fetchMapEvents`, `fetchRegion`)
- Modify: `web/components/WorldMap.tsx` (plotar lista de eventos clicáveis)

**Interfaces:**
- Consumes: `GET /api/regions`, `GET /api/map_events`, `GET /api/region/{id}`.
- Produces:
  - `lib/api.ts`: `fetchRegions(): Promise<Region[]>`, `fetchMapEvents(): Promise<GeoEvent[]>`, `fetchRegion(id: string): Promise<RegionDetail>`.
  - `WorldMap` aceita props `events: GeoEvent[]`, `focused: GeoEvent | null`, `onSelectEvent: (e: GeoEvent) => void`.

- [ ] **Step 1: Adicionar tipos em `web/lib/types.ts`**

Adicionar ao final do arquivo:

```ts
export interface Region {
  id: string;
  name: string;
  name_en: string;
  center: { lat: number; lon: number };
  countries: string[];
}

export interface RegionDetail {
  region: Region & { gdelt_query?: string };
  summary: string;
  risk_level: "alto" | "médio" | "baixo";
  live_events: GeoEvent[];
  commodities_at_risk: string[];
  meta: { offline: boolean; n_live: number };
}
```

E no `interface GeoEvent`, adicionar o campo opcional:

```ts
  kind?: "curated" | "live";
```

- [ ] **Step 2: Adicionar funções em `web/lib/api.ts`**

Após `fetchEventTypes`, adicionar:

```ts
import type { Region, RegionDetail } from "./types";

export async function fetchRegions(): Promise<Region[]> {
  const data = await getJSON<{ regions: Region[] }>("/api/regions");
  return data.regions;
}

export async function fetchMapEvents(): Promise<GeoEvent[]> {
  const data = await getJSON<{ events: GeoEvent[] }>("/api/map_events");
  return data.events;
}

export async function fetchRegion(id: string): Promise<RegionDetail> {
  return getJSON<RegionDetail>(`/api/region/${id}`);
}
```

(Se `Region`/`RegionDetail` já forem importados no topo com os outros tipos, mesclar o import em vez de duplicar.)

- [ ] **Step 3: Reescrever `web/components/WorldMap.tsx` para lista clicável**

```tsx
"use client";

import { ComposableMap, Geographies, Geography, Marker } from "react-simple-maps";
import type { GeoEvent } from "@/lib/types";

const GEO_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

interface Props {
  events: GeoEvent[];
  focused: GeoEvent | null;
  onSelectEvent: (e: GeoEvent) => void;
}

export default function WorldMap({ events, focused, onSelectEvent }: Props) {
  return (
    <div className="w-full overflow-hidden rounded-xl">
      <ComposableMap projection="geoEqualEarth" projectionConfig={{ scale: 168 }} style={{ width: "100%", height: "auto" }}>
        <Geographies geography={GEO_URL}>
          {({ geographies }) =>
            geographies.map((geo) => (
              <Geography
                key={geo.rsmKey}
                geography={geo}
                style={{
                  default: { fill: "rgba(255,255,255,0.05)", stroke: "rgba(255,255,255,0.12)", strokeWidth: 0.4, outline: "none" },
                  hover: { fill: "rgba(233,169,75,0.16)", stroke: "rgba(233,169,75,0.4)", outline: "none" },
                  pressed: { fill: "rgba(233,169,75,0.22)", outline: "none" },
                }}
              />
            ))
          }
        </Geographies>

        {events.filter((e) => e.lat !== 0 || e.lon !== 0).map((e) => {
          const isFocused = focused?.id === e.id;
          const live = e.kind === "live";
          return (
            <Marker key={e.id} coordinates={[e.lon, e.lat]} onClick={() => onSelectEvent(e)} style={{ default: { cursor: "pointer" } }}>
              {isFocused && <circle className="pulse-marker" r={7} fill="#fb7185" opacity={0.5} />}
              <circle
                r={isFocused ? 6 : 4.5}
                fill={isFocused ? "#fb7185" : live ? "#e9a94b" : "#7dd3fc"}
                stroke="rgba(11,11,12,0.9)"
                strokeWidth={1.2}
              />
            </Marker>
          );
        })}
      </ComposableMap>
    </div>
  );
}
```

- [ ] **Step 4: Ajustar a chamada de `WorldMap` em `web/app/page.tsx`**

Localizar o `<WorldMap ... />` (hoje recebe `event`/`analogs`) e trocar por:

```tsx
<WorldMap
  events={mapEvents}
  focused={result?.event ?? selected}
  onSelectEvent={(e) => setSelected(e)}
/>
```

Adicionar o estado e a carga inicial no componente `Home` (junto aos outros `useState`):

```tsx
const [mapEvents, setMapEvents] = useState<GeoEvent[]>([]);
```

No `useEffect` de carga inicial, após `fetchEventTypes()`, incluir `fetchMapEvents()` no `Promise.all` e `setMapEvents(...)`. Importar `fetchMapEvents` de `@/lib/api`.

- [ ] **Step 5: Verificar o build**

Run: `cd /Users/arthurlauffer/Downloads/geoshock/web && npm run build`
Expected: `Compiled successfully` + `Finished TypeScript` sem erros.

- [ ] **Step 6: Commit**

```bash
cd /Users/arthurlauffer/Downloads/geoshock
git add web/lib/types.ts web/lib/api.ts web/components/WorldMap.tsx web/app/page.tsx
git commit -m "feat(web): mapa multi-evento clicavel + api client de regioes"
```

---

## Task 5: Frontend — painel de região + modo simples/analista

**Files:**
- Create: `web/components/RegionPanel.tsx`
- Modify: `web/app/page.tsx` (navegação de regiões, estado de região, toggle de modo, render condicional)

**Interfaces:**
- Consumes: `fetchRegions`, `fetchRegion` (Task 4); `RegionDetail`, `Region` (Task 4); componente `AnalysisPanel` existente.
- Produces: `RegionPanel` (props: `detail: RegionDetail`, `onSelectEvent: (e: GeoEvent) => void`).

- [ ] **Step 1: Criar `web/components/RegionPanel.tsx`**

```tsx
"use client";

import type { GeoEvent, RegionDetail } from "@/lib/types";

const RISK_STYLE: Record<string, string> = {
  alto: "text-[color:var(--neg)] border-[color:var(--neg)]",
  "médio": "text-[color:var(--accent-2)] border-[color:var(--accent-2)]",
  baixo: "text-[color:var(--pos)] border-[color:var(--pos)]",
};

export default function RegionPanel({
  detail,
  onSelectEvent,
}: {
  detail: RegionDetail;
  onSelectEvent: (e: GeoEvent) => void;
}) {
  return (
    <div className="reveal flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">{detail.region.name}</h2>
        <span className={`chip ${RISK_STYLE[detail.risk_level] ?? ""}`}>risco {detail.risk_level}</span>
      </div>

      <p className="text-sm text-zinc-300 leading-relaxed">{detail.summary}</p>

      <div>
        <p className="eyebrow mb-2">Commodities mais expostas</p>
        <div className="flex flex-wrap gap-2">
          {detail.commodities_at_risk.slice(0, 6).map((c) => (
            <span key={c} className="chip">{c}</span>
          ))}
        </div>
      </div>

      <div>
        <p className="eyebrow mb-2">Eventos recentes ({detail.meta.n_live})</p>
        {detail.live_events.length === 0 ? (
          <p className="text-xs text-zinc-500">Sem eventos ao vivo agora. Mostrando panorama da região.</p>
        ) : (
          <div className="flex flex-col">
            {detail.live_events.map((e, i) => (
              <button
                key={e.id}
                onClick={() => onSelectEvent(e)}
                className={`text-left py-2.5 px-2 rounded-lg hover:bg-white/[0.03] transition ${i > 0 ? "border-t border-white/8" : ""}`}
              >
                <span className="block text-xs font-medium text-zinc-100 line-clamp-2 leading-snug">{e.title}</span>
                <span className="block text-[11px] text-zinc-500 mt-1 num">{e.date} · {e.region}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Em `web/app/page.tsx`, adicionar estados de região e modo**

Junto aos outros `useState` de `Home`:

```tsx
const [regions, setRegions] = useState<Region[]>([]);
const [regionDetail, setRegionDetail] = useState<RegionDetail | null>(null);
const [regionLoading, setRegionLoading] = useState(false);
const [viewMode, setViewMode] = useState<"simple" | "analyst">("simple");
```

Importar de `@/lib/api`: `fetchRegions`, `fetchRegion`. De `@/lib/types`: `Region`, `RegionDetail`. Importar `RegionPanel` de `@/components/RegionPanel`.

Persistência do modo (adicionar um `useEffect`):

```tsx
useEffect(() => {
  const saved = localStorage.getItem("geoshock_view");
  if (saved === "simple" || saved === "analyst") setViewMode(saved);
}, []);
useEffect(() => {
  localStorage.setItem("geoshock_view", viewMode);
}, [viewMode]);
```

Na carga inicial (`Promise.all`), incluir `fetchRegions()` e `setRegions(...)`.

- [ ] **Step 3: Adicionar seletor de regiões e handler**

Handler de clique em região (dentro de `Home`):

```tsx
const openRegion = useCallback(async (id: string) => {
  setRegionLoading(true);
  setSelected(null);      // sai do modo evento
  setResult(null);
  try {
    setRegionDetail(await fetchRegion(id));
  } finally {
    setRegionLoading(false);
  }
}, []);
```

Na barra lateral, acima do seletor de evento histórico, adicionar um grupo de botões de região:

```tsx
<div>
  <p className="eyebrow mb-2">Regiões</p>
  <div className="grid grid-cols-2 gap-1.5">
    {regions.map((r) => (
      <button key={r.id} className="seg-item" onClick={() => openRegion(r.id)}>
        {r.name}
      </button>
    ))}
  </div>
</div>
```

- [ ] **Step 4: Render condicional do painel direito + toggle de modo**

No cabeçalho (`Header`), adicionar um toggle. Passe `viewMode`/`setViewMode` como props ao `Header` e renderize:

```tsx
<div className="seg w-auto">
  <button className={`seg-item ${viewMode === "simple" ? "seg-active" : ""}`} onClick={() => setViewMode("simple")}>Simples</button>
  <button className={`seg-item ${viewMode === "analyst" ? "seg-active" : ""}`} onClick={() => setViewMode("analyst")}>Analista</button>
</div>
```

No painel direito (a `<section className="panel p-5 ...">`), a lógica de render passa a ser:

```tsx
{error ? (
  <div className="flex items-start gap-2 text-[color:var(--neg)] text-sm"><Warning size={18} className="mt-0.5 shrink-0" /><span>{error}</span></div>
) : regionLoading || loading ? (
  <AnalysisSkeleton />
) : result ? (
  viewMode === "analyst" ? <AnalysisPanel data={result} /> : <SimpleBriefing data={result} />
) : regionDetail ? (
  <RegionPanel detail={regionDetail} onSelectEvent={(e) => setSelected(e)} />
) : (
  <p className="text-zinc-400 text-sm">Escolha uma região ou um evento para começar.</p>
)}
```

Adicionar o componente `SimpleBriefing` (resumo do evento em linguagem simples, sem métricas técnicas) no final de `page.tsx`:

```tsx
function SimpleBriefing({ data }: { data: AnalyzeResponse }) {
  const first = data.briefing.markdown.split("\n").find((l) => l.trim() && !l.startsWith("#")) ?? "";
  return (
    <div className="reveal flex flex-col gap-4">
      <h2 className="text-lg font-semibold">{data.event.title}</h2>
      <p className="text-sm text-zinc-300 leading-relaxed">{first}</p>
      <div>
        <p className="eyebrow mb-2">Commodities em risco</p>
        <div className="flex flex-wrap gap-2">
          {data.commodities.slice(0, 5).map((c) => (<span key={c} className="chip">{c}</span>))}
        </div>
      </div>
      <p className="text-xs text-zinc-500">Ative o modo Analista para ver análogos, variações e detalhes.</p>
    </div>
  );
}
```

- [ ] **Step 5: Verificar o build**

Run: `cd /Users/arthurlauffer/Downloads/geoshock/web && npm run build`
Expected: `Compiled successfully` + `Finished TypeScript` sem erros.

- [ ] **Step 6: Commit**

```bash
cd /Users/arthurlauffer/Downloads/geoshock
git add web/components/RegionPanel.tsx web/app/page.tsx
git commit -m "feat(web): painel de regiao + modo simples/analista"
```

---

## Task 6: Integração + revisão final

**Files:**
- Modify: conforme necessário para correções de integração (documentar no relatório)
- Test: suíte completa

**Interfaces:** nenhuma nova; valida o conjunto.

- [ ] **Step 1: Subir backend e frontend**

```bash
cd /Users/arthurlauffer/Downloads/geoshock
pkill -f "uvicorn api_server" 2>/dev/null; nohup ./venv/bin/python -m uvicorn api_server:app --port 8000 > /tmp/geoshock_api.log 2>&1 & disown
sleep 9
curl -s http://localhost:8000/api/health
```

Expected: JSON com `"status":"ok"`.

- [ ] **Step 2: Testar os novos endpoints ao vivo**

```bash
curl -s http://localhost:8000/api/regions | ./venv/bin/python -c "import sys,json;print(len(json.load(sys.stdin)['regions']),'regioes')"
curl -s http://localhost:8000/api/map_events | ./venv/bin/python -c "import sys,json;e=json.load(sys.stdin)['events'];print(len(e),'eventos; geocoded=',all(x['lat'] or x['lon'] for x in e))"
curl -s http://localhost:8000/api/region/middle_east | ./venv/bin/python -c "import sys,json;d=json.load(sys.stdin);print('risco',d['risk_level'],'| n_live',d['meta']['n_live'],'| commodities',d['commodities_at_risk'][:3])"
```

Expected: 8 regiões; eventos todos geocodificados; região com resumo, risco e commodities.

- [ ] **Step 3: Regressão completa dos testes Python**

Run: `./venv/bin/python -m pytest tests/ -q`
Expected: todos passam (43 no total: 27 originais + 16 novos).

- [ ] **Step 4: Build do frontend**

Run: `cd web && npm run build`
Expected: sucesso, sem erros de tipo.

- [ ] **Step 5: Verificação manual do fluxo**

Subir `cd web && npm run dev -- -p 3100`, abrir http://localhost:3100 e confirmar:
- mapa mostra vários pontos (curados em azul);
- clicar numa região abre o painel simples (resumo + commodities + eventos recentes) e plota os eventos ao vivo (âmbar);
- clicar num evento gera a análise; toggle "Analista" revela o `AnalysisPanel` completo.

- [ ] **Step 6: Commit final de integração (se houver ajustes)**

```bash
git add -A
git commit -m "chore: integracao do explorador regional"
```

---

## Self-Review (preenchido)

**Cobertura do spec:** §4.1 geocoder → Task 1. §4.2/4.3/4.4 regiões e map_events → Task 2. §4.5/4.6 região e resumidor → Task 3. §5.1 mapa multi-evento → Task 4. §5.2/5.3/5.4 painel de região, modo simples/analista, tipos/api → Tasks 4-5. §7 testes → em cada task + Task 6. §9 git init → Pré-execução.

**Placeholders:** nenhum; todo passo tem código/comando reais.

**Consistência de tipos:** `geocode_event`, `centroid`, `load_regions`, `get_region`, `curated_map_events`, `aggregate_commodities`, `risk_level`, `summarize_region` usados com a mesma assinatura em tasks posteriores e nos endpoints. Props de `WorldMap` (`events`/`focused`/`onSelectEvent`) e `RegionPanel` (`detail`/`onSelectEvent`) consistentes entre Task 4 e 5.
