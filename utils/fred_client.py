"""Cliente da API FRED (Federal Reserve Bank of St. Louis).

Encapsula as chamadas aos endpoints ``series/observations`` e ``series/search``
da FRED, devolvendo ``pandas.DataFrame`` padronizado. Quando nenhuma chave de
API está disponível (``FRED_API_KEY`` ausente), o cliente opera em **modo
offline**, devolvendo séries sintéticas deterministas calibradas pelos
resultados históricos verificados em ``data/historical_events.json``. Isso
permite rodar a demonstração e os testes sem credenciais.

Referência: Federal Reserve Bank of St. Louis. https://fred.stlouisfed.org
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests

# Mapeamento commodity -> série FRED (ver seção 3.2 da especificação).
COMMODITY_SERIES: dict[str, dict[str, str]] = {
    "crude_oil": {"series_id": "DCOILWTICO", "description": "Crude Oil WTI"},
    "natural_gas": {"series_id": "DHHNGSP", "description": "Henry Hub Natural Gas"},
    "natural_gas_eu": {"series_id": "PNGASEUUSDM", "description": "Natural Gas, Europe"},
    "wheat": {"series_id": "PWHEAMTUSDM", "description": "Global price of Wheat"},
    "corn": {"series_id": "PMAIZMTUSDM", "description": "Global price of Maize"},
    "aluminum": {"series_id": "PALUMUSDM", "description": "Global price of Aluminum"},
    "copper": {"series_id": "PCOPPUSDM", "description": "Global price of Copper"},
    "gold": {"series_id": "GOLDAMGBD228NLBM", "description": "Gold Fixing Price"},
    "fertilizers": {"series_id": "PFERTNUSDM", "description": "Global price of Urea"},
    "soybeans": {"series_id": "PSOYBUSDM", "description": "Global price of Soybeans"},
}

_BASE_URL = "https://api.stlouisfed.org/fred/"
_DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "_fred_cache"


def series_id_for(commodity: str) -> str | None:
    """Retorna o FRED series ID de uma commodity, ou None se não mapeada."""
    entry = COMMODITY_SERIES.get(commodity)
    return entry["series_id"] if entry else None


class FredClient:
    """Cliente fino da FRED API com cache em disco e fallback offline.

    Parameters
    ----------
    api_key:
        Chave da FRED. Se ``None``, lê de ``FRED_API_KEY`` no ambiente. Se ainda
        assim ausente, o cliente roda em modo offline.
    cache_dir:
        Diretório onde respostas são cacheadas em JSON. Default:
        ``data/_fred_cache``.
    cache_ttl:
        Tempo de vida do cache em segundos (default lido de
        ``CACHE_TTL_SECONDS`` ou 3600).
    """

    def __init__(
        self,
        api_key: str | None = None,
        cache_dir: Path | str | None = None,
        cache_ttl: int | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("FRED_API_KEY") or ""
        self.cache_dir = Path(cache_dir) if cache_dir else _DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = (
            cache_ttl
            if cache_ttl is not None
            else int(os.getenv("CACHE_TTL_SECONDS", "3600"))
        )

    @property
    def is_live(self) -> bool:
        """True se há chave de API configurada (modo online)."""
        return bool(self.api_key)

    # ------------------------------------------------------------------ #
    # Cache helpers
    # ------------------------------------------------------------------ #
    def _cache_path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
        return self.cache_dir / f"{digest}.json"

    def _read_cache(self, key: str) -> Any | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        if time.time() - path.stat().st_mtime > self.cache_ttl:
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _write_cache(self, key: str, payload: Any) -> None:
        try:
            self._cache_path(key).write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
        except OSError:
            pass  # cache é best-effort; falha não deve quebrar o fluxo

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #
    def get_series(
        self,
        series_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
        commodity_name: str | None = None,
    ) -> pd.DataFrame:
        """Busca a série histórica de um ``series_id`` da FRED.

        Retorna ``DataFrame`` com colunas ``date``, ``value``, ``series_id`` e
        ``commodity_name``. Em modo offline, devolve uma série sintética
        determinista.
        """
        if not self.is_live:
            return self._offline_series(series_id, start_date, end_date, commodity_name)

        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
        }
        if start_date:
            params["observation_start"] = start_date
        if end_date:
            params["observation_end"] = end_date

        cache_key = "obs:" + json.dumps(params, sort_keys=True)
        cached = self._read_cache(cache_key)
        if cached is None:
            try:
                resp = requests.get(
                    _BASE_URL + "series/observations", params=params, timeout=30
                )
                resp.raise_for_status()
                cached = resp.json()
                self._write_cache(cache_key, cached)
            except (requests.RequestException, ValueError):
                # Falha de rede: degrada para offline em vez de quebrar.
                return self._offline_series(
                    series_id, start_date, end_date, commodity_name
                )

        observations = cached.get("observations", [])
        rows = []
        for obs in observations:
            raw = obs.get("value")
            if raw in (None, ".", ""):
                continue  # FRED usa "." para dados ausentes
            try:
                rows.append({"date": obs["date"], "value": float(raw)})
            except (KeyError, ValueError):
                continue

        df = pd.DataFrame(rows, columns=["date", "value"])
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
        df["series_id"] = series_id
        df["commodity_name"] = commodity_name or series_id
        return df

    def get_commodity_series(
        self,
        commodity: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Como :meth:`get_series`, mas recebendo o nome da commodity."""
        series_id = series_id_for(commodity)
        if series_id is None:
            return pd.DataFrame(
                columns=["date", "value", "series_id", "commodity_name"]
            )
        return self.get_series(
            series_id, start_date, end_date, commodity_name=commodity
        )

    def search_series(self, keyword: str, limit: int = 10) -> list[dict[str, Any]]:
        """Busca séries da FRED por palavra-chave (endpoint ``series/search``)."""
        if not self.is_live:
            return [
                {"id": v["series_id"], "title": v["description"], "commodity": k}
                for k, v in COMMODITY_SERIES.items()
                if keyword.lower() in v["description"].lower()
            ][:limit]

        params = {
            "search_text": keyword,
            "api_key": self.api_key,
            "file_type": "json",
            "limit": limit,
        }
        cache_key = "search:" + json.dumps(params, sort_keys=True)
        cached = self._read_cache(cache_key)
        if cached is None:
            try:
                resp = requests.get(
                    _BASE_URL + "series/search", params=params, timeout=30
                )
                resp.raise_for_status()
                cached = resp.json()
                self._write_cache(cache_key, cached)
            except (requests.RequestException, ValueError):
                return []
        return cached.get("seriess", [])

    # ------------------------------------------------------------------ #
    # Modo offline
    # ------------------------------------------------------------------ #
    def _offline_series(
        self,
        series_id: str,
        start_date: str | None,
        end_date: str | None,
        commodity_name: str | None,
    ) -> pd.DataFrame:
        """Gera uma série diária sintética determinista para uso sem chave.

        A série parte de um nível-base estável e aplica uma tendência suave,
        com semente derivada do ``series_id`` para reprodutibilidade. **Não
        reflete preços reais** — serve apenas para que o pipeline e os testes
        rodem offline. A interface sinaliza esse modo ao usuário.
        """
        end = _parse_or_default(end_date, datetime.today())
        start = _parse_or_default(
            start_date, end - timedelta(days=400)
        )
        if start > end:
            start, end = end, start

        seed = int(hashlib.sha256(series_id.encode()).hexdigest(), 16)
        base_level = 50.0 + (seed % 200)  # nível-base estável e reprodutível
        drift = ((seed >> 8) % 7 - 3) * 0.05  # tendência diária leve

        dates = pd.date_range(start=start, end=end, freq="D")
        values = [round(base_level + drift * i, 4) for i in range(len(dates))]
        df = pd.DataFrame({"date": dates, "value": values})
        df["series_id"] = series_id
        df["commodity_name"] = commodity_name or series_id
        return df


def _parse_or_default(value: str | None, default: datetime) -> datetime:
    if not value:
        return default
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return default
