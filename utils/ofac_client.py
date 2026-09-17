"""Cliente da lista de sanções OFAC (Tesouro dos EUA — SDN List).

Ao contrário da GDELT ("a palavra 'sanction' apareceu numa manchete"), a
OFAC é uma lista oficial e estruturada: uma entidade está sancionada ou não
está, com programa e base legal registrados. Usa o endpoint de exportação
"Publication Preview", que a própria OFAC rotula como voltado a "pesquisa e
auditoria" (não para triagem de transações financeiras) — exatamente o uso
que o GeoShock faz dele: confirmar, para fins educacionais, se existe sanção
formal em vigor associada a um país.

Validado manualmente em 2026-09: exige header ``User-Agent`` (a API responde
403 sem ele) e um timeout generoso — o arquivo tem ~100MB.
"""

from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import requests

_ENTITIES_URL = "https://sanctionslistservice.ofac.treas.gov/entities"
_DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "_ofac_cache"
_CACHE_FILENAME = "sdn_entities.xml"

_NS = {"o": "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/ENHANCED_XML"}


class OfacClient:
    """Cliente da lista SDN da OFAC (sanções dos EUA), com cache local.

    Parameters
    ----------
    cache_dir:
        Diretório de cache. Default: ``data/_ofac_cache``.
    cache_ttl:
        Tempo de vida do cache em segundos. Default 24h — o arquivo é enorme
        (~100MB) e sanções novas não são publicadas a cada requisição.
    """

    def __init__(
        self,
        cache_dir: Path | str | None = None,
        cache_ttl: int = 86400,
    ) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else _DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = cache_ttl

    # ------------------------------------------------------------------ #
    # Download + cache
    # ------------------------------------------------------------------ #
    def _cache_path(self) -> Path:
        return self.cache_dir / _CACHE_FILENAME

    def _fetch_xml_bytes(self) -> bytes | None:
        """Baixa (ou reaproveita do cache) o XML cru da OFAC.

        Retorna ``None`` em qualquer falha de rede — nunca fabrica dados de
        sanções (diferente do fallback sintético de preços da FRED, aqui o
        dado é binário — sancionado ou não — e não há substituto honesto).
        """
        path = self._cache_path()
        if path.exists() and time.time() - path.stat().st_mtime < self.cache_ttl:
            return path.read_bytes()

        try:
            resp = requests.get(
                _ENTITIES_URL,
                headers={"User-Agent": "GeoShock-TCC-Research/1.0"},
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.content
        except requests.RequestException:
            if path.exists():
                return path.read_bytes()
            return None

        try:
            path.write_bytes(data)
        except OSError:
            pass
        return data

    # ------------------------------------------------------------------ #
    # Parsing (função pura, testável com XML fixo)
    # ------------------------------------------------------------------ #
    @staticmethod
    def parse_xml(xml_bytes: bytes) -> list[dict[str, Any]]:
        """Converte o XML cru da OFAC numa lista de entidades sancionadas."""
        root = ET.fromstring(xml_bytes)
        results: list[dict[str, Any]] = []
        for ent in root.findall(".//o:entity", _NS):
            countries = [
                c.text for c in ent.findall(".//o:country", _NS) if c.text
            ]
            programs = [
                p.text for p in ent.findall(".//o:sanctionsProgram", _NS) if p.text
            ]
            lists = [
                s.text for s in ent.findall(".//o:sanctionsList", _NS) if s.text
            ]
            names = [
                n.text
                for n in ent.findall(".//o:name/o:translations/o:translation/o:formattedFullName", _NS)
                if n.text
            ]
            entity_type = ent.find(".//o:entityType", _NS)
            results.append(
                {
                    "id": ent.get("id"),
                    "name": names[0] if names else None,
                    "entity_type": entity_type.text if entity_type is not None else None,
                    "countries": countries,
                    "programs": programs,
                    "sanctions_lists": lists,
                }
            )
        return results

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #
    def search_by_country(self, country_name: str) -> list[dict[str, Any]]:
        """Entidades sancionadas associadas a um país (nome em inglês)."""
        data = self._fetch_xml_bytes()
        if not data:
            return []
        entities = self.parse_xml(data)
        target = country_name.strip().lower()
        return [
            e for e in entities
            if any((c or "").strip().lower() == target for c in e["countries"])
        ]
