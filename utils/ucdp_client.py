"""Cliente da base UCDP GED (Uppsala Conflict Data Program).

Diferente da GDELT (busca de texto em notícias), a UCDP é um banco de eventos
de violência organizada **curado por analistas**, com estimativa real de
fatalidades e coordenadas geográficas precisas por evento — por isso serve
como camada de *verificação* de severidade para eventos de conflito armado,
complementar à camada de *pulso em tempo real* da GDELT.

Usa o arquivo público "candidato" (dados recentes, ainda sem revisão
editorial anual completa), publicado sem necessidade de token de API:
https://ucdp.uu.se/downloads/

Validado manualmente em 2026-09: o download não exige autenticação, apenas
tempo suficiente (o arquivo tem ~8MB). Quando a rede falha ou o arquivo não
está disponível, o cliente devolve uma lista vazia — ao contrário do
:class:`~utils.fred_client.FredClient`, esta classe **não fabrica dados
sintéticos**, pois inventar contagens de fatalidades de conflitos armados
seria eticamente inaceitável, mesmo como placeholder.
"""

from __future__ import annotations

import csv
import io
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from utils.geocoder import iso_from_country_name

# URL do arquivo CSV "candidato" mais recente (dados de eventos ainda não
# consolidados na revisão editorial anual). A UCDP versiona esse nome de
# arquivo periodicamente; sobrescreva via UCDP_GED_URL se ele mudar.
_DEFAULT_GED_URL = (
    "https://ucdp.uu.se/downloads/candidateged/GEDEvent_v26_01_26_06.csv"
)
_DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "_ucdp_cache"
_CACHE_FILENAME = "ged_candidate.csv"

# Campos usados do CSV da UCDP (há dezenas de colunas; só extraímos as que
# importam para o GeoShock).
_FIELDS = (
    "id", "type_of_violence", "conflict_name", "side_a", "side_b",
    "date_start", "source_headline", "country", "region",
    "latitude", "longitude", "where_prec", "best", "high", "low",
)


class UcdpClient:
    """Cliente do banco de eventos de conflito armado da UCDP.

    Parameters
    ----------
    ged_url:
        URL do CSV candidato. Default: :data:`_DEFAULT_GED_URL`, ou a
        variável de ambiente ``UCDP_GED_URL`` quando definida.
    cache_dir:
        Diretório de cache local. Default: ``data/_ucdp_cache``.
    cache_ttl:
        Tempo de vida do cache em segundos. Default 24h — o arquivo é grande
        (~8MB) e a UCDP não atualiza a base candidata com frequência maior
        que isso.
    """

    def __init__(
        self,
        ged_url: str | None = None,
        cache_dir: Path | str | None = None,
        cache_ttl: int = 86400,
    ) -> None:
        self.ged_url = ged_url or os.getenv("UCDP_GED_URL", _DEFAULT_GED_URL)
        self.cache_dir = Path(cache_dir) if cache_dir else _DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = cache_ttl

    # ------------------------------------------------------------------ #
    # Download + cache
    # ------------------------------------------------------------------ #
    def _cache_path(self) -> Path:
        return self.cache_dir / _CACHE_FILENAME

    def _fetch_csv_text(self) -> str | None:
        """Baixa (ou reaproveita do cache) o CSV cru da UCDP.

        Retorna ``None`` em qualquer falha de rede — nunca fabrica dados.
        """
        path = self._cache_path()
        if path.exists() and time.time() - path.stat().st_mtime < self.cache_ttl:
            return path.read_text(encoding="utf-8")

        try:
            # Arquivo de ~8MB: precisa de um timeout generoso (validado
            # manualmente — downloads curtos (<30s) cortam o arquivo).
            resp = requests.get(self.ged_url, timeout=90)
            resp.raise_for_status()
            text = resp.text
        except requests.RequestException:
            if path.exists():
                return path.read_text(encoding="utf-8")  # cache velho > nada
            return None

        try:
            path.write_text(text, encoding="utf-8")
        except OSError:
            pass  # cache é best-effort
        return text

    # ------------------------------------------------------------------ #
    # Parsing (função pura, testável com texto fixo)
    # ------------------------------------------------------------------ #
    @staticmethod
    def parse_csv(csv_text: str) -> list[dict[str, Any]]:
        """Converte o texto CSV cru da UCDP numa lista de dicts crus.

        Mantém apenas os campos em :data:`_FIELDS`; não faz nenhuma
        normalização de schema (isso é responsabilidade de
        ``modules.data_normalizer``).
        """
        reader = csv.DictReader(io.StringIO(csv_text))
        rows: list[dict[str, Any]] = []
        for row in reader:
            rows.append({field: row.get(field, "") for field in _FIELDS})
        return rows

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #
    def search_events(
        self,
        countries: list[str] | None = None,
        min_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Eventos de conflito armado, opcionalmente filtrados.

        Parameters
        ----------
        countries:
            Códigos ISO2. Quando informado, só retorna eventos cujo país
            (resolvido via :func:`utils.geocoder.iso_from_country_name`)
            esteja na lista.
        min_date:
            Data ISO (YYYY-MM-DD); só retorna eventos com ``date_start`` a
            partir dela.
        """
        text = self._fetch_csv_text()
        if not text:
            return []

        rows = self.parse_csv(text)
        wanted = {c.upper() for c in countries} if countries else None
        min_dt = datetime.strptime(min_date, "%Y-%m-%d") if min_date else None

        results: list[dict[str, Any]] = []
        for row in rows:
            iso = iso_from_country_name(row.get("country", ""))
            if wanted is not None and iso not in wanted:
                continue
            if min_dt is not None:
                try:
                    row_dt = datetime.strptime(row["date_start"][:10], "%Y-%m-%d")
                except (ValueError, KeyError):
                    continue
                if row_dt < min_dt:
                    continue
            results.append(row)
        return results
