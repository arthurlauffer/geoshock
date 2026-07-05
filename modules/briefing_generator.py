"""Módulo 5 — Geração de briefing via IA generativa.

Abstrai três provedores de LLM (Anthropic, OpenAI, Google Gemini) atrás de uma
única classe :class:`LLMClient`, monta o prompt dinâmico com todo o contexto
recuperado (evento atual, análogos históricos, impactos de preço) e gera um
briefing analítico em Markdown no formato fixo da seção 7.4.

Quando nenhuma chave de API está disponível, um briefing **offline** é montado
deterministicamente a partir do contexto estruturado — útil para demonstração e
testes sem credenciais. Esse modo é sinalizado em ``meta['offline'] = True``.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from utils.validators import EVENT_TYPES

logger = logging.getLogger("geoshock.briefing")

# Modelos padrão por provider (ver seção 7.1 da especificação).
_DEFAULT_MODELS = {
    "anthropic": "claude-3-5-haiku-20241022",
    "openai": "gpt-4o-mini",
    "google": "gemini-2.5-flash",
}

_ENV_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
}

SYSTEM_PROMPT = """Você é um analista sênior de risco geopolítico especializado em mercados de commodities.
Sua função é gerar briefings analíticos concisos, precisos e acessíveis a leitores sem
formação técnica em finanças.

REGRAS OBRIGATÓRIAS:
1. Fundamente TODAS as afirmações exclusivamente nos eventos históricos fornecidos como contexto.
2. Nunca especule além do que os dados permitem.
3. Nunca gere recomendações de investimento.
4. Nunca faça previsões quantitativas de preços.
5. Indique explicitamente quando os dados históricos são insuficientes para uma análise robusta.
6. Use linguagem clara, sem jargão técnico excessivo.
7. Estruture a resposta exatamente no formato solicitado."""


class LLMClient:
    """Cliente unificado de LLM com seleção de provider via ``LLM_PROVIDER``.

    Parameters
    ----------
    provider:
        Um de ``anthropic``, ``openai`` ou ``google``. Default: ``LLM_PROVIDER``
        do ambiente, ou ``anthropic``.
    api_key:
        Chave da API. Se ``None``, lida da variável de ambiente do provider.
    model:
        Sobrescreve o modelo padrão do provider.
    """

    def __init__(
        self,
        provider: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.provider = (provider or os.getenv("LLM_PROVIDER", "anthropic")).lower()
        if self.provider not in _DEFAULT_MODELS:
            raise ValueError(
                f"Provider inválido: {self.provider!r}. "
                f"Aceitos: {', '.join(_DEFAULT_MODELS)}"
            )
        self.api_key = api_key or os.getenv(_ENV_KEYS[self.provider], "")
        self.model = model or _DEFAULT_MODELS[self.provider]

    @property
    def is_live(self) -> bool:
        """True se há chave de API configurada para o provider escolhido."""
        return bool(self.api_key)

    def generate(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Gera uma resposta do LLM.

        Retorna um dict com ``text`` (resposta), ``provider``, ``model``,
        ``tokens`` (quando disponível), ``elapsed_s`` e ``offline``.
        """
        if not self.is_live:
            return {
                "text": "",
                "provider": self.provider,
                "model": self.model,
                "tokens": None,
                "elapsed_s": 0.0,
                "offline": True,
            }

        start = time.perf_counter()
        if self.provider == "anthropic":
            text, tokens = self._gen_anthropic(system_prompt, user_prompt)
        elif self.provider == "openai":
            text, tokens = self._gen_openai(system_prompt, user_prompt)
        else:
            text, tokens = self._gen_google(system_prompt, user_prompt)
        elapsed = time.perf_counter() - start

        logger.info(
            "Briefing gerado | provider=%s model=%s tokens=%s tempo=%.2fs",
            self.provider,
            self.model,
            tokens,
            elapsed,
        )
        return {
            "text": text,
            "provider": self.provider,
            "model": self.model,
            "tokens": tokens,
            "elapsed_s": round(elapsed, 2),
            "offline": False,
        }

    # ------------------------------------------------------------------ #
    # Implementações por provider
    # ------------------------------------------------------------------ #
    def _gen_anthropic(self, system_prompt: str, user_prompt: str) -> tuple[str, Any]:
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)
        resp = client.messages.create(
            model=self.model,
            max_tokens=1500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(block.text for block in resp.content if block.type == "text")
        tokens = resp.usage.input_tokens + resp.usage.output_tokens
        return text, tokens

    def _gen_openai(self, system_prompt: str, user_prompt: str) -> tuple[str, Any]:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        resp = client.chat.completions.create(
            model=self.model,
            max_tokens=1500,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        text = resp.choices[0].message.content or ""
        tokens = resp.usage.total_tokens if resp.usage else None
        return text, tokens

    def _gen_google(self, system_prompt: str, user_prompt: str) -> tuple[str, Any]:
        import google.generativeai as genai

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(
            model_name=self.model, system_instruction=system_prompt
        )
        resp = model.generate_content(user_prompt)
        text = resp.text or ""
        tokens = None
        try:
            tokens = resp.usage_metadata.total_token_count
        except AttributeError:
            pass
        return text, tokens


# --------------------------------------------------------------------------- #
# Construção do prompt dinâmico
# --------------------------------------------------------------------------- #
def build_user_prompt(
    current_event: dict[str, Any],
    similar_events: list[dict[str, Any]],
    price_impacts: dict[str, Any],
    commodities_at_risk: list[str],
) -> str:
    """Monta o prompt dinâmico com todo o contexto estruturado (seção 7.3)."""
    type_label = EVENT_TYPES.get(current_event.get("event_type", ""), current_event.get("event_type", ""))

    lines: list[str] = []
    lines.append("## EVENTO ATUAL")
    lines.append(f"- Título: {current_event.get('title')}")
    lines.append(f"- Data: {current_event.get('date')}")
    lines.append(f"- Região: {current_event.get('region')}")
    lines.append(f"- Tipo: {type_label}")
    lines.append(f"- Intensidade estimada: {current_event.get('intensity_score')}/10")
    lines.append(f"- Descrição: {current_event.get('description')}")
    lines.append("")

    lines.append("## EVENTOS HISTÓRICOS ANÁLOGOS")
    if similar_events:
        for i, ev in enumerate(similar_events, 1):
            verified = (ev.get("metadata") or {}).get("verified_outcomes") or {}
            impacts = "; ".join(f"{k}: {v}" for k, v in verified.items()) or "sem impactos registrados"
            lines.append(
                f"{i}. {ev.get('title')} ({ev.get('date')}) — Região: {ev.get('region')}, "
                f"Tipo: {EVENT_TYPES.get(ev.get('event_type', ''), ev.get('event_type', ''))}, "
                f"Similaridade: {ev.get('similarity_pct', '?')}%. "
                f"Impactos observados: {impacts}."
            )
    else:
        lines.append("Nenhum análogo histórico suficientemente próximo foi encontrado.")
    lines.append("")

    lines.append("## COMMODITIES IDENTIFICADAS EM RISCO")
    for commodity in commodities_at_risk:
        impact = price_impacts.get(commodity, {})
        change = impact.get("change_30d_pct")
        if change:
            offline_note = " [série offline — valor ilustrativo]" if impact.get("offline") else ""
            lines.append(f"- {commodity}: variação observada em 30d ≈ {change}{offline_note}")
        else:
            lines.append(f"- {commodity}: dados de preço indisponíveis para a data")
    lines.append("")

    lines.append("## FORMATO OBRIGATÓRIO DA RESPOSTA (Markdown)")
    lines.append(_OUTPUT_FORMAT_TEMPLATE)
    return "\n".join(lines)


_OUTPUT_FORMAT_TEMPLATE = """Retorne EXATAMENTE neste formato:

## Análise de Risco Geopolítico — [TÍTULO DO EVENTO]

**Data do evento:** [DATA]
**Região:** [REGIÃO]
**Tipo de evento:** [TIPO]
**Intensidade estimada:** [SCORE]/10

---

### Contexto Geopolítico
[2-3 parágrafos contextualizando o evento, sua região e seus atores]

### Commodities em Risco
[Lista com cada commodity identificada, explicando POR QUÊ está em risco com base no tipo de evento e na localização geográfica]

### Análogos Históricos
[Para cada evento histórico similar retornado, 1 parágrafo descrevendo o paralelo e os impactos observados nos preços de commodities à época]

### Síntese de Risco
[Parágrafo final integrando os três elementos anteriores, indicando fatores que podem ampliar ou atenuar o risco no evento atual em comparação com os precedentes. Concluir com disclaimer de que esta análise é educacional e não constitui recomendação de investimento.]"""


# --------------------------------------------------------------------------- #
# Geração de alto nível + controle de qualidade
# --------------------------------------------------------------------------- #
def generate(
    current_event: dict[str, Any],
    similar_events: list[dict[str, Any]],
    price_impacts: dict[str, Any],
    historical_summary: dict[str, Any],
    commodities_at_risk: list[str] | None = None,
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    """Gera o briefing completo e aplica controle de qualidade.

    Retorna um dict com:

    * ``markdown`` — o texto do briefing;
    * ``quality`` — ``"ok"`` ou ``"low"`` (menos de 200 palavras);
    * ``word_count``;
    * ``sources`` — eventos históricos usados como fontes (rastreabilidade);
    * ``meta`` — provider, modelo, tokens, tempo, flag ``offline``.
    """
    commodities_at_risk = commodities_at_risk or list(price_impacts.keys())
    client = llm_client or LLMClient()
    user_prompt = build_user_prompt(
        current_event, similar_events, price_impacts, commodities_at_risk
    )

    response = client.generate(SYSTEM_PROMPT, user_prompt)
    if response.get("offline") or not response.get("text"):
        markdown = _offline_briefing(
            current_event, similar_events, price_impacts, historical_summary, commodities_at_risk
        )
        response["offline"] = True
    else:
        markdown = response["text"]

    word_count = len(markdown.split())
    quality = "low" if word_count < 200 else "ok"
    if quality == "low":
        logger.warning("Briefing curto (%d palavras) — qualidade marcada como baixa.", word_count)

    sources = [
        {
            "id": ev.get("id"),
            "title": ev.get("title"),
            "date": ev.get("date"),
            "similarity_pct": ev.get("similarity_pct"),
        }
        for ev in similar_events
    ]

    return {
        "markdown": markdown,
        "quality": quality,
        "word_count": word_count,
        "sources": sources,
        "meta": {
            "provider": response.get("provider"),
            "model": response.get("model"),
            "tokens": response.get("tokens"),
            "elapsed_s": response.get("elapsed_s"),
            "offline": response.get("offline", False),
        },
    }


def _offline_briefing(
    event: dict[str, Any],
    similar_events: list[dict[str, Any]],
    price_impacts: dict[str, Any],
    historical_summary: dict[str, Any],
    commodities_at_risk: list[str],
) -> str:
    """Monta um briefing determinista a partir do contexto, sem chamar LLM.

    Segue o mesmo formato da saída do modelo. Serve a demonstrações e testes
    offline; a interface deixa claro que nenhum LLM foi consultado.
    """
    type_label = EVENT_TYPES.get(event.get("event_type", ""), event.get("event_type", ""))

    commodity_lines = []
    for c in commodities_at_risk:
        stats = historical_summary.get(c, {})
        n = stats.get("n_precedents", 0)
        if n:
            commodity_lines.append(
                f"- **{c}**: em risco por causa do tipo de evento "
                f"({type_label.lower()}) na região *{event.get('region')}*. "
                f"Em {n} precedente(s) análogo(s), a variação média em 30 dias foi de "
                f"{stats.get('mean_change_30d'):+.1f}% (intervalo "
                f"{stats.get('min_change_30d'):+.1f}% a {stats.get('max_change_30d'):+.1f}%); "
                f"confiança {stats.get('confidence')}."
            )
        else:
            commodity_lines.append(
                f"- **{c}**: identificada como exposta ao evento, mas sem precedentes "
                f"históricos suficientes na base para quantificar o impacto."
            )

    analog_lines = []
    for ev in similar_events:
        verified = (ev.get("metadata") or {}).get("verified_outcomes") or {}
        impacts = "; ".join(f"{k}: {v}" for k, v in verified.items()) or "sem impactos de preço registrados na base"
        analog_lines.append(
            f"- **{ev.get('title')}** ({ev.get('date')}, {ev.get('region')}) — "
            f"similaridade semântica de {ev.get('similarity_pct')}%. Impactos observados à época: {impacts}."
        )
    if not analog_lines:
        analog_lines.append("- Nenhum análogo histórico suficientemente próximo foi encontrado na base.")

    return f"""## Análise de Risco Geopolítico — {event.get('title')}

**Data do evento:** {event.get('date')}
**Região:** {event.get('region')}
**Tipo de evento:** {type_label}
**Intensidade estimada:** {event.get('intensity_score')}/10

---

### Contexto Geopolítico
O evento classificado como *{type_label.lower()}* na região de *{event.get('region')}* é avaliado, nesta análise, à luz de seus análogos históricos. {event.get('description')}

A intensidade estimada de {event.get('intensity_score')}/10 indica o grau de severidade atribuído ao evento no momento da inserção. A análise abaixo cruza essa caracterização com casos históricos semanticamente próximos recuperados da base do GeoShock.

### Commodities em Risco
{chr(10).join(commodity_lines)}

### Análogos Históricos
{chr(10).join(analog_lines)}

### Síntese de Risco
Com base nos análogos recuperados, eventos do tipo *{type_label.lower()}* nesta região tenderam a pressionar os preços das commodities listadas acima na direção observada nos precedentes. Fatores que podem **ampliar** o risco incluem a concentração da produção global nas áreas afetadas e a dependência de rotas logísticas vulneráveis; fatores que podem **atenuá-lo** incluem estoques reguladores, capacidade ociosa de produtores alternativos e a eventual rápida desescalada do evento. Onde a base histórica é limitada, as estimativas devem ser lidas com cautela.

> **Aviso:** Esta análise é de natureza **educacional** e baseia-se em analogias históricas. **Não** constitui previsão de preços nem recomendação de investimento.

*Briefing gerado em modo offline (sem consulta a LLM), a partir do contexto estruturado recuperado.*"""
