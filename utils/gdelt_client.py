"""Cliente da API GDELT 2.0 (Global Database of Events, Language, and Tone).

Suporta o modo ``ArtList`` (listagem de artigos) e ``TimelineVol`` (volume
temporal de cobertura) do endpoint DOC 2.0. Implementa rate limiting de 1
requisição por segundo, retry com backoff exponencial e cache local por sessão.
Quando a rede está indisponível, devolve um conjunto vazio sem quebrar o fluxo.

Referência: Leetaru & Schrodt (2013), GDELT 2.0, ISA Annual Convention.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
_DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "_gdelt_cache"


class GdeltClient:
    """Cliente da GDELT DOC 2.0 com rate limiting e cache de sessão.

    Parameters
    ----------
    rate_limit_rps:
        Máximo de requisições por segundo (default lido de
        ``GDELT_RATE_LIMIT_RPS`` ou 1).
    max_retries:
        Tentativas em caso de falha de rede (default 3).
    cache_dir:
        Diretório de cache em JSON. Default ``data/_gdelt_cache``.
    """

    def __init__(
        self,
        rate_limit_rps: float | None = None,
        max_retries: int = 3,
        cache_dir: Path | str | None = None,
    ) -> None:
        self.rate_limit_rps = (
            rate_limit_rps
            if rate_limit_rps is not None
            else float(os.getenv("GDELT_RATE_LIMIT_RPS", "1"))
        )
        self.max_retries = max_retries
        self.cache_dir = Path(cache_dir) if cache_dir else _DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._min_interval = 1.0 / self.rate_limit_rps if self.rate_limit_rps > 0 else 0
        self._last_request_ts = 0.0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Rate limiting
    # ------------------------------------------------------------------ #
    def _throttle(self) -> None:
        """Garante o intervalo mínimo entre requisições (1 req/s default)."""
        with self._lock:
            elapsed = time.monotonic() - self._last_request_ts
            wait = self._min_interval - elapsed
            if wait > 0:
                time.sleep(wait)
            self._last_request_ts = time.monotonic()

    # ------------------------------------------------------------------ #
    # HTTP com retry + cache
    # ------------------------------------------------------------------ #
    def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        cache_key = json.dumps(params, sort_keys=True)
        cache_path = self.cache_dir / f"{abs(hash(cache_key))}.json"
        if cache_path.exists():
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        backoff = 2.0
        for attempt in range(1, self.max_retries + 1):
            self._throttle()
            try:
                resp = requests.get(_DOC_URL, params=params, timeout=30)
                resp.raise_for_status()
                # GDELT às vezes devolve HTML de erro com status 200.
                if not resp.text.strip().startswith("{"):
                    raise ValueError("Resposta GDELT não-JSON")
                data = resp.json()
                try:
                    cache_path.write_text(
                        json.dumps(data, ensure_ascii=False), encoding="utf-8"
                    )
                except OSError:
                    pass
                return data
            except (requests.RequestException, ValueError):
                if attempt == self.max_retries:
                    return {}
                time.sleep(backoff)  # 2s, 4s, 8s
                backoff *= 2
        return {}

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #
    def search_articles(
        self,
        query: str,
        max_records: int = 50,
        start_datetime: str | None = None,
        end_datetime: str | None = None,
    ) -> list[dict[str, Any]]:
        """Lista artigos recentes para uma query (modo ``ArtList``).

        ``start_datetime``/``end_datetime`` devem estar no formato GDELT
        ``YYYYMMDDHHMMSS``. Retorna lista de dicts com ``url``, ``title``,
        ``seendate``, ``socialimage``, ``domain``, ``language`` e
        ``sourcecountry``.
        """
        params: dict[str, Any] = {
            "query": query,
            "mode": "ArtList",
            "maxrecords": min(max_records, 250),  # limite duro da GDELT
            "format": "json",
            "sort": "datedesc",
        }
        if start_datetime:
            params["startdatetime"] = start_datetime
        if end_datetime:
            params["enddatetime"] = end_datetime

        data = self._request(params)
        articles = data.get("articles", []) if isinstance(data, dict) else []
        return [
            {
                "url": a.get("url", ""),
                "title": a.get("title", ""),
                "seendate": a.get("seendate", ""),
                "socialimage": a.get("socialimage", ""),
                "domain": a.get("domain", ""),
                "language": a.get("language", ""),
                "sourcecountry": a.get("sourcecountry", ""),
            }
            for a in articles
        ]

    def timeline_volume(
        self,
        query: str,
        start_datetime: str | None = None,
        end_datetime: str | None = None,
    ) -> list[dict[str, Any]]:
        """Volume temporal de cobertura para uma query (modo ``TimelineVol``).

        Retorna lista de pontos ``{"date": ..., "value": ...}`` representando a
        intensidade da cobertura midiática ao longo do tempo.
        """
        params: dict[str, Any] = {
            "query": query,
            "mode": "TimelineVol",
            "format": "json",
        }
        if start_datetime:
            params["startdatetime"] = start_datetime
        if end_datetime:
            params["enddatetime"] = end_datetime

        data = self._request(params)
        timeline = data.get("timeline", []) if isinstance(data, dict) else []
        points: list[dict[str, Any]] = []
        for series in timeline:
            for point in series.get("data", []):
                points.append(
                    {"date": point.get("date"), "value": point.get("value")}
                )
        return points


def to_gdelt_datetime(value: str | datetime) -> str:
    """Converte uma data ISO (ou ``datetime``) para o formato GDELT YYYYMMDDHHMMSS."""
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.strptime(value, "%Y-%m-%d")
    return dt.strftime("%Y%m%d%H%M%S")
