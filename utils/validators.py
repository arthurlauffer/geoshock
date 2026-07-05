"""Validações e sanitização de inputs do GeoShock.

Centraliza a verificação de eventos geopolíticos estruturados, datas, scores de
intensidade e o vocabulário controlado de tipos de evento. Todas as funções são
puras (sem efeitos colaterais) e não dependem de APIs externas, o que as torna
trivialmente testáveis offline.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

# Vocabulário controlado de tipos de evento (ver seção 4.3 da especificação).
EVENT_TYPES: dict[str, str] = {
    "armed_conflict": "Conflito armado / invasão militar",
    "economic_sanction": "Sanção econômica / embargo",
    "military_tension": "Tensão militar / mobilização",
    "diplomatic_crisis": "Crise diplomática / ruptura de relações",
    "institutional_disruption": "Ruptura institucional / pandemia / colapso de governo",
    "trade_restriction": "Restrição comercial / guerra tarifária",
    "infrastructure_attack": "Ataque a infraestrutura crítica",
    "territorial_dispute": "Disputa territorial / anexação",
}

# Campos mínimos que um evento estruturado precisa ter para ser processado.
REQUIRED_EVENT_FIELDS: tuple[str, ...] = (
    "id",
    "title",
    "date",
    "region",
    "event_type",
    "intensity_score",
    "description",
)

_ISO_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Erro de validação de input do usuário ou de dados carregados."""


def is_valid_date(value: str) -> bool:
    """Retorna True se ``value`` for uma data ISO 8601 (YYYY-MM-DD) válida."""
    if not isinstance(value, str) or not _DATE_RE.match(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def normalize_date(value: str | date | datetime) -> str:
    """Converte uma data (string, ``date`` ou ``datetime``) para ISO 8601.

    Levanta :class:`ValidationError` se a data for inválida.
    """
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    if is_valid_date(value):
        return value
    raise ValidationError(f"Data inválida: {value!r} (esperado YYYY-MM-DD)")


def validate_event_type(event_type: str) -> str:
    """Valida o tipo de evento contra o vocabulário controlado."""
    if event_type not in EVENT_TYPES:
        raise ValidationError(
            f"Tipo de evento inválido: {event_type!r}. "
            f"Valores aceitos: {', '.join(EVENT_TYPES)}"
        )
    return event_type


def validate_intensity(score: Any) -> float:
    """Garante que o score de intensidade é um número entre 0.0 e 10.0."""
    try:
        value = float(score)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Intensidade não numérica: {score!r}") from exc
    if not 0.0 <= value <= 10.0:
        raise ValidationError(
            f"Intensidade fora do intervalo [0, 10]: {value}"
        )
    return value


def sanitize_text(text: str, max_length: int = 4000) -> str:
    """Remove espaços redundantes e trunca textos longos.

    Usado para higienizar descrições e queries antes de enviá-las a embeddings
    ou a APIs de LLM, evitando payloads excessivos.
    """
    if not isinstance(text, str):
        text = str(text)
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rsplit(" ", 1)[0] + "…"
    return cleaned


def normalize_country_codes(codes: Any) -> list[str]:
    """Normaliza uma lista de códigos ISO 3166-1 alpha-2.

    Códigos inválidos são descartados silenciosamente (a localização do evento
    não é obrigatória para a análise semântica).
    """
    if not codes:
        return []
    if isinstance(codes, str):
        codes = [codes]
    result: list[str] = []
    for code in codes:
        candidate = str(code).strip().upper()
        if _ISO_COUNTRY_RE.match(candidate):
            result.append(candidate)
    return result


def validate_coordinates(lat: Any, lon: Any) -> tuple[float, float]:
    """Valida latitude/longitude, retornando (0.0, 0.0) para eventos globais.

    Coordenadas ausentes ou inválidas caem para a origem (eventos globais como
    a pandemia de COVID-19), em vez de levantar erro.
    """
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return 0.0, 0.0
    if not (-90.0 <= lat_f <= 90.0) or not (-180.0 <= lon_f <= 180.0):
        return 0.0, 0.0
    return lat_f, lon_f


def validate_event(event: dict[str, Any]) -> dict[str, Any]:
    """Valida e normaliza um evento estruturado completo.

    Retorna uma cópia normalizada do evento. Levanta :class:`ValidationError`
    se algum campo obrigatório estiver ausente ou inválido.
    """
    if not isinstance(event, dict):
        raise ValidationError("Evento deve ser um dicionário.")

    missing = [f for f in REQUIRED_EVENT_FIELDS if f not in event or event[f] in (None, "")]
    if missing:
        raise ValidationError(
            f"Campos obrigatórios ausentes no evento: {', '.join(missing)}"
        )

    normalized = dict(event)
    normalized["title"] = sanitize_text(event["title"], max_length=300)
    normalized["date"] = normalize_date(event["date"])
    normalized["region"] = sanitize_text(event["region"], max_length=200)
    normalized["event_type"] = validate_event_type(event["event_type"])
    normalized["intensity_score"] = validate_intensity(event["intensity_score"])
    normalized["description"] = sanitize_text(event["description"])
    normalized["country_codes"] = normalize_country_codes(event.get("country_codes"))
    normalized["lat"], normalized["lon"] = validate_coordinates(
        event.get("lat"), event.get("lon")
    )
    normalized["commodities_affected"] = list(event.get("commodities_affected") or [])
    normalized.setdefault("source", "Inserido pelo usuário")
    return normalized
