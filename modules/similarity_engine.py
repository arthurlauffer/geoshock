"""Módulo 3 — Motor de similaridade histórica (ChromaDB).

Mantém uma collection persistente (``geoshock_events``) de eventos históricos
vetorizados e oferece busca semântica por proximidade. Na primeira execução, a
collection é populada automaticamente a partir de ``data/historical_events.json``.

Uso por linha de comando para (re)inicializar o banco::

    python -m modules.similarity_engine --init
    python -m modules.similarity_engine --reset   # apaga e repopula
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from modules import preprocessor

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CHROMA_PATH = _DATA_DIR / "chroma_db"
_HISTORICAL_PATH = _DATA_DIR / "historical_events.json"

_COLLECTION_NAME = "geoshock_events"
_MAX_DISTANCE = 1.5  # acima disso, considera-se irrelevante (seção 5.2)

# Campos de lista serializados como string separada por vírgula, pois o ChromaDB
# só aceita metadados escalares (str/int/float/bool).
_LIST_FIELDS = ("country_codes", "commodities_affected")


class SimilarityEngine:
    """Motor de similaridade sobre uma collection persistente do ChromaDB."""

    def __init__(self, persist_path: Path | str | None = None) -> None:
        import chromadb  # import tardio para acelerar quem não usa o motor

        self.persist_path = Path(persist_path) if persist_path else _CHROMA_PATH
        self.persist_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self.persist_path))
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )

    # ------------------------------------------------------------------ #
    # Inicialização
    # ------------------------------------------------------------------ #
    def count(self) -> int:
        """Número de eventos atualmente indexados."""
        return self._collection.count()

    def ensure_initialized(self, historical_path: Path | str | None = None) -> int:
        """Popula a collection a partir da base histórica se estiver vazia.

        Retorna o número total de eventos indexados após a operação.
        """
        if self.count() > 0:
            return self.count()
        return self.load_historical(historical_path)

    def load_historical(self, historical_path: Path | str | None = None) -> int:
        """Carrega e indexa todos os eventos da base histórica."""
        path = Path(historical_path) if historical_path else _HISTORICAL_PATH
        with open(path, encoding="utf-8") as fh:
            events = json.load(fh).get("events", [])
        for event in events:
            self.add_event(event)
        return self.count()

    def reset(self) -> None:
        """Apaga e recria a collection (uso em desenvolvimento/testes)."""
        self._client.delete_collection(_COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )

    # ------------------------------------------------------------------ #
    # Indexação
    # ------------------------------------------------------------------ #
    def add_event(self, event: dict[str, Any]) -> None:
        """Indexa um único evento, gerando o embedding se necessário."""
        embedding = event.get("embedding") or preprocessor.embed_event(event)
        document = preprocessor.build_event_text(event)
        self._collection.upsert(
            ids=[event["id"]],
            embeddings=[embedding],
            documents=[document],
            metadatas=[_to_metadata(event)],
        )

    # ------------------------------------------------------------------ #
    # Busca
    # ------------------------------------------------------------------ #
    def search_similar_events(
        self, query_event: dict[str, Any], n_results: int = 5
    ) -> list[dict[str, Any]]:
        """Retorna os eventos históricos mais próximos de ``query_event``.

        O evento de consulta deve conter ``embedding``; se ausente, ele é gerado
        on-the-fly. Resultados com ``distance > 1.5`` são descartados. A lista
        volta ordenada por distância crescente (mais similar primeiro), e exclui
        o próprio evento de consulta caso ele já esteja indexado.
        """
        if self.count() == 0:
            self.ensure_initialized()

        embedding = query_event.get("embedding") or preprocessor.embed_event(query_event)
        n_fetch = min(n_results + 1, self.count())  # +1 para descartar o próprio
        raw = self._collection.query(
            query_embeddings=[embedding],
            n_results=n_fetch,
            include=["documents", "metadatas", "distances"],
        )

        ids = raw.get("ids", [[]])[0]
        metadatas = raw.get("metadatas", [[]])[0]
        distances = raw.get("distances", [[]])[0]
        documents = raw.get("documents", [[]])[0]

        query_id = query_event.get("id")
        results: list[dict[str, Any]] = []
        for idx, meta in zip(ids, metadatas):
            position = ids.index(idx)
            distance = distances[position]
            if idx == query_id:
                continue  # não retornar o próprio evento
            if distance > _MAX_DISTANCE:
                continue
            parsed = _from_metadata(meta)
            results.append(
                {
                    "id": idx,
                    "title": parsed.get("title", ""),
                    "date": parsed.get("date", ""),
                    "region": parsed.get("region", ""),
                    "event_type": parsed.get("event_type", ""),
                    "intensity_score": parsed.get("intensity_score", 0.0),
                    "commodities_affected": parsed.get("commodities_affected", []),
                    "lat": parsed.get("lat", 0.0),
                    "lon": parsed.get("lon", 0.0),
                    "distance": float(distance),
                    "similarity_pct": _distance_to_similarity(distance),
                    "document": documents[position] if position < len(documents) else "",
                    "metadata": parsed,
                }
            )

        results.sort(key=lambda r: r["distance"])
        return results[:n_results]


# --------------------------------------------------------------------------- #
# Serialização de metadados
# --------------------------------------------------------------------------- #
def _to_metadata(event: dict[str, Any]) -> dict[str, Any]:
    """Converte um evento em metadados escalares aceitos pelo ChromaDB."""
    meta: dict[str, Any] = {
        "id": event.get("id", ""),
        "title": event.get("title", ""),
        "date": event.get("date", ""),
        "region": event.get("region", ""),
        "event_type": event.get("event_type", ""),
        "intensity_score": float(event.get("intensity_score", 0.0)),
        "lat": float(event.get("lat", 0.0)),
        "lon": float(event.get("lon", 0.0)),
        "source": event.get("source", ""),
    }
    for field in _LIST_FIELDS:
        meta[field] = ",".join(event.get(field, []) or [])
    verified = event.get("verified_outcomes")
    if verified:
        meta["verified_outcomes"] = json.dumps(verified, ensure_ascii=False)
    return meta


def _from_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    """Inverte :func:`_to_metadata`, reconstruindo listas e dicts."""
    parsed = dict(meta)
    for field in _LIST_FIELDS:
        raw = meta.get(field, "")
        parsed[field] = [item for item in raw.split(",") if item] if raw else []
    if "verified_outcomes" in meta:
        try:
            parsed["verified_outcomes"] = json.loads(meta["verified_outcomes"])
        except (json.JSONDecodeError, TypeError):
            parsed["verified_outcomes"] = {}
    return parsed


def _distance_to_similarity(distance: float) -> float:
    """Converte distância de cosseno (0–2) em similaridade percentual (0–100)."""
    similarity = max(0.0, 1.0 - float(distance) / 2.0)
    return round(similarity * 100, 1)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _main() -> None:
    parser = argparse.ArgumentParser(description="Gerenciamento do banco vetorial GeoShock.")
    parser.add_argument("--init", action="store_true", help="Inicializa a collection se vazia.")
    parser.add_argument("--reset", action="store_true", help="Apaga e repopula a collection.")
    args = parser.parse_args()

    engine = SimilarityEngine()
    if args.reset:
        engine.reset()
        total = engine.load_historical()
        print(f"Collection recriada com {total} eventos.")
    elif args.init:
        total = engine.ensure_initialized()
        print(f"Collection pronta com {total} eventos indexados.")
    else:
        print(f"Collection '{_COLLECTION_NAME}' contém {engine.count()} eventos.")


if __name__ == "__main__":
    _main()
