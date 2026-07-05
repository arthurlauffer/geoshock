"""Módulo 2 — Pré-processamento e geração de embeddings.

Responsável por:

* estruturar e validar eventos vindos das três fontes de entrada;
* montar o texto canônico de cada evento e convertê-lo num vetor semântico
  (``all-MiniLM-L6-v2`` local por padrão, ou ``text-embedding-3-small`` da
  OpenAI quando ``EMBEDDING_PROVIDER=openai``);
* mapear cada evento ao conjunto de commodities em risco via
  ``commodity_mapping.json``.

O modelo de embeddings é carregado de forma preguiçosa (lazy) e reaproveitado
entre chamadas, evitando o custo de inicialização repetida.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from utils.validators import validate_event

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_MAPPING_PATH = _DATA_DIR / "commodity_mapping.json"

_LOCAL_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_OPENAI_MODEL_NAME = "text-embedding-3-small"
_EMBEDDING_DIM = 384  # dimensão do all-MiniLM-L6-v2

# Ponte entre os nomes de região (em pt-BR) usados nos eventos e as chaves de
# região (em inglês) do commodity_mapping.json.
_REGION_ALIASES: dict[str, str] = {
    "europa oriental": "Eastern Europe",
    "leste europeu": "Eastern Europe",
    "oriente médio": "Middle East",
    "oriente medio": "Middle East",
    "golfo pérsico": "Middle East",
    "estreito de ormuz": "Strait of Hormuz",
    "áfrica subsaariana": "Sub-Saharan Africa",
    "africa subsaariana": "Sub-Saharan Africa",
    "américa latina": "Latin America",
    "america latina": "Latin America",
    "ásia oriental": "East Asia",
    "asia oriental": "East Asia",
    "mar do sul da china": "South China Sea",
    "estreito de taiwan": "Taiwan Strait",
    "rússia": "Russia",
    "russia": "Russia",
    "china": "China",
}


@lru_cache(maxsize=1)
def _load_mapping() -> dict[str, Any]:
    with open(_MAPPING_PATH, encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- #
# Embeddings
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _get_local_model():
    """Carrega (uma única vez) o modelo local de sentence-transformers."""
    from sentence_transformers import SentenceTransformer  # import tardio (pesado)

    return SentenceTransformer(_LOCAL_MODEL_NAME)


def _embed_local(text: str) -> list[float]:
    model = _get_local_model()
    vector = model.encode(text, normalize_embeddings=True)
    return np.asarray(vector, dtype=float).tolist()


def _embed_openai(text: str) -> list[float]:
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    resp = client.embeddings.create(model=_OPENAI_MODEL_NAME, input=text)
    vector = np.asarray(resp.data[0].embedding, dtype=float)
    # Normalização L2 explícita para consistência com o modo local.
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return vector.tolist()


def build_event_text(event: dict[str, Any]) -> str:
    """Monta o texto canônico embedado de um evento.

    Formato (ver seção 4.1 da especificação)::

        title + ". " + description + ". Região: " + region + ". Tipo: " + event_type
    """
    return (
        f"{event.get('title', '')}. "
        f"{event.get('description', '')}. "
        f"Região: {event.get('region', '')}. "
        f"Tipo: {event.get('event_type', '')}"
    )


def embed_text(text: str) -> list[float]:
    """Gera o embedding L2-normalizado de um texto, conforme o provider."""
    provider = os.getenv("EMBEDDING_PROVIDER", "local").lower()
    if provider == "openai":
        return _embed_openai(text)
    return _embed_local(text)


def embed_event(event: dict[str, Any]) -> list[float]:
    """Gera o embedding do texto canônico de um evento."""
    return embed_text(build_event_text(event))


# --------------------------------------------------------------------------- #
# Estruturação de eventos
# --------------------------------------------------------------------------- #
def structure_event(raw: dict[str, Any]) -> dict[str, Any]:
    """Valida e normaliza um evento cru (de qualquer fonte de entrada).

    Delega a validação de campos a :func:`utils.validators.validate_event` e
    garante a presença das chaves opcionais usadas adiante no pipeline.
    """
    event = validate_event(raw)
    event.setdefault("intensity_score", 5.0)
    event.setdefault("commodities_affected", [])
    return event


# --------------------------------------------------------------------------- #
# Mapeamento de commodities
# --------------------------------------------------------------------------- #
def _normalize_region(region: str) -> str | None:
    """Traduz um nome de região (pt-BR) para a chave do mapping (inglês)."""
    key = region.strip().lower()
    # Tenta casar por substring para regiões compostas ("Oriente Médio / ...").
    for alias, canonical in _REGION_ALIASES.items():
        if alias in key:
            return canonical
    return None


def map_commodities(event: dict[str, Any]) -> list[str]:
    """Identifica as commodities em risco para um evento.

    Combina, sem duplicatas e preservando a ordem:

    1. commodities específicas da região (se mapeada para o tipo de evento);
    2. as commodities default do tipo de evento;
    3. quaisquer ``commodities_affected`` já declaradas no próprio evento.
    """
    mapping = _load_mapping()
    event_type = event.get("event_type", "")
    type_map = mapping.get(event_type, {})

    commodities: list[str] = []

    canonical_region = _normalize_region(event.get("region", ""))
    if canonical_region and canonical_region in type_map.get("regions", {}):
        commodities.extend(type_map["regions"][canonical_region])

    commodities.extend(type_map.get("default", []))
    commodities.extend(event.get("commodities_affected", []))

    # Dedup preservando ordem de prioridade.
    seen: set[str] = set()
    ordered: list[str] = []
    for item in commodities:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered
