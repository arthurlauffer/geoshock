"""GeoShock — Interface Streamlit (tema Liquid Glass).

Ponto de entrada da aplicação. Integra os cinco módulos do pipeline RAG numa
interface web com estética *liquid glass*, mapa interativo e painel de análise
em abas. O briefing e as commodities em risco são gerados **automaticamente** ao
abrir/selecionar um evento (sem necessidade de clicar em botão).

Execução::

    streamlit run app.py
"""

from __future__ import annotations

import hashlib
import os

import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from modules import briefing_generator, collector, impact_analyzer, preprocessor
from modules.briefing_generator import LLMClient
from modules.similarity_engine import SimilarityEngine
from utils.fred_client import FredClient
from utils.validators import EVENT_TYPES, ValidationError

load_dotenv()

APP_VERSION = "1.1.0"
REPO_URL = "https://github.com/geoshock/geoshock"

st.set_page_config(page_title="GeoShock", layout="wide", page_icon="🌍")


# --------------------------------------------------------------------------- #
# Estética Liquid Glass (CSS injetado)
# --------------------------------------------------------------------------- #
_GLASS_CSS = """
<style>
/* Fundo aurora + gradiente profundo */
.stApp {
  background:
    radial-gradient(1200px 800px at 8% 6%, rgba(56,189,248,0.20), transparent 55%),
    radial-gradient(1000px 700px at 92% 14%, rgba(168,85,247,0.20), transparent 55%),
    radial-gradient(1100px 900px at 50% 105%, rgba(16,185,129,0.16), transparent 55%),
    linear-gradient(135deg, #070b16 0%, #0c1326 55%, #070b16 100%);
  background-attachment: fixed;
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"] { right: 1rem; }

/* Sidebar em vidro fosco */
section[data-testid="stSidebar"] > div {
  background: rgba(255,255,255,0.06);
  backdrop-filter: blur(20px) saturate(160%);
  -webkit-backdrop-filter: blur(20px) saturate(160%);
  border-right: 1px solid rgba(255,255,255,0.12);
}

/* Cartões de vidro (containers com borda) */
div[data-testid="stVerticalBlockBorderWrapper"] {
  background: rgba(255,255,255,0.07);
  backdrop-filter: blur(16px) saturate(160%);
  -webkit-backdrop-filter: blur(16px) saturate(160%);
  border: 1px solid rgba(255,255,255,0.16) !important;
  border-radius: 22px !important;
  box-shadow: 0 8px 32px rgba(0,0,0,0.30), inset 0 1px 0 rgba(255,255,255,0.18);
  padding: 8px 18px;
}

/* Título com gradiente */
h1 {
  background: linear-gradient(90deg,#7dd3fc,#a78bfa 55%,#34d399);
  -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent;
  font-weight: 800; letter-spacing: -0.5px;
}
h2, h3 { color: #eef3ff; }

/* Botões de vidro */
.stButton > button, .stDownloadButton > button {
  background: linear-gradient(135deg, rgba(125,211,252,0.28), rgba(167,139,250,0.28));
  border: 1px solid rgba(255,255,255,0.28);
  border-radius: 14px;
  color: #f6f9ff; font-weight: 600;
  backdrop-filter: blur(8px);
  transition: all .2s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover {
  border-color: rgba(125,211,252,0.75);
  box-shadow: 0 0 22px rgba(125,211,252,0.45);
  transform: translateY(-1px);
}

/* Inputs / selects / textareas frosted */
.stTextInput input, .stTextArea textarea, .stDateInput input,
[data-baseweb="select"] > div {
  background: rgba(255,255,255,0.08) !important;
  border: 1px solid rgba(255,255,255,0.18) !important;
  border-radius: 12px !important;
  color: #eaf0ff !important;
}

/* Abas de vidro */
[data-baseweb="tab-list"] {
  gap: 6px;
  background: rgba(255,255,255,0.05);
  padding: 6px; border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.10);
}
[data-baseweb="tab"] { border-radius: 11px; color: #c7d2e5; }
button[aria-selected="true"][data-baseweb="tab"] {
  background: rgba(125,211,252,0.22); color: #fff;
}

/* Tabelas e alertas translúcidos */
[data-testid="stDataFrame"] {
  border-radius: 14px; overflow: hidden;
  border: 1px solid rgba(255,255,255,0.12);
}
[data-testid="stAlert"] {
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.16);
  border-radius: 14px; backdrop-filter: blur(8px);
}

/* Sliders / radios na cor de acento */
[data-testid="stSlider"] [role="slider"] { box-shadow: 0 0 10px rgba(125,211,252,0.6); }

/* Texto base mais claro */
.stApp, .stMarkdown, p, span, label, li { color: #e8edf5; }

/* Chip de status */
.geo-chip {
  display:inline-block; padding:4px 12px; margin:2px 6px 2px 0;
  border-radius:999px; font-size:0.78rem; font-weight:600;
  border:1px solid rgba(255,255,255,0.2); backdrop-filter: blur(6px);
}
.geo-chip.live   { background: rgba(52,211,153,0.18); color:#a7f3d0; }
.geo-chip.off    { background: rgba(251,191,36,0.16); color:#fde68a; }
</style>
"""


def inject_css() -> None:
    st.markdown(_GLASS_CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Recursos cacheados
# --------------------------------------------------------------------------- #
@st.cache_resource(show_spinner=False)
def get_engine() -> SimilarityEngine:
    engine = SimilarityEngine()
    engine.ensure_initialized()
    return engine


@st.cache_resource(show_spinner=False)
def get_collector() -> collector.Collector:
    return collector.Collector()


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
def render_sidebar() -> dict:
    st.sidebar.title("🌍 GeoShock")
    st.sidebar.caption("Análise de Risco Geopolítico em Commodities")

    st.sidebar.markdown("### ⚙️ Configuração")
    provider = st.sidebar.selectbox(
        "Provider LLM", ["anthropic", "openai", "google"],
        index=["anthropic", "openai", "google"].index(
            os.getenv("LLM_PROVIDER", "anthropic")
        ),
    )
    api_key = st.sidebar.text_input(
        "API Key do LLM", type="password",
        value=os.getenv(
            {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY",
             "google": "GOOGLE_API_KEY"}[provider], ""
        ),
    )
    fred_key = st.sidebar.text_input(
        "FRED API Key", type="password", value=os.getenv("FRED_API_KEY", "")
    )

    # Chips de status das conexões
    llm_chip = ("live", "LLM conectado") if api_key else ("off", "LLM offline (template)")
    fred_chip = ("live", "FRED conectado") if fred_key else ("off", "FRED offline (ilustrativo)")
    st.sidebar.markdown(
        f'<span class="geo-chip {llm_chip[0]}">{llm_chip[1]}</span>'
        f'<span class="geo-chip {fred_chip[0]}">{fred_chip[1]}</span>'
        f'<span class="geo-chip live">GDELT aberta (sem chave)</span>',
        unsafe_allow_html=True,
    )

    st.sidebar.markdown("### 🧭 Modo de entrada")
    mode = st.sidebar.radio(
        "Como definir o evento?",
        ["Selecionar evento histórico", "Inserir evento manualmente", "Buscar no GDELT (ao vivo)"],
        label_visibility="collapsed",
    )

    st.sidebar.markdown("### 🎚️ Filtros")
    window = st.sidebar.select_slider("Janela temporal (dias)", options=[7, 30, 90], value=30)
    n_analogs = st.sidebar.slider("Eventos análogos", 1, 10, 3)

    st.sidebar.markdown("### ⚡ Análise")
    auto = st.sidebar.toggle("Gerar automaticamente ao abrir o evento", value=True)

    return {
        "provider": provider, "api_key": api_key, "fred_key": fred_key,
        "mode": mode, "window": window, "n_analogs": n_analogs, "auto": auto,
    }


# --------------------------------------------------------------------------- #
# Modos de entrada
# --------------------------------------------------------------------------- #
def input_historical(container) -> dict | None:
    events = get_collector().load_historical_events()
    options = {f"{e['title']} ({e['date']})": e for e in events}
    label = container.selectbox("Evento histórico", list(options.keys()))
    return options.get(label)


def input_manual(container) -> dict | None:
    with container.form("manual_event"):
        title = st.text_input("Título do evento")
        date = st.date_input("Data do evento")
        region = st.text_input("País / Região")
        event_type = st.selectbox(
            "Tipo de evento", list(EVENT_TYPES.keys()),
            format_func=lambda k: EVENT_TYPES[k],
        )
        intensity = st.slider("Intensidade", 1.0, 10.0, 5.0, 0.5)
        description = st.text_area("Descrição")
        submitted = st.form_submit_button("Usar este evento")
    if submitted and title and description:
        return {
            "id": "manual_" + date.strftime("%Y%m%d"),
            "title": title, "date": date.strftime("%Y-%m-%d"),
            "region": region or "Não especificada", "country_codes": [],
            "lat": 0.0, "lon": 0.0, "event_type": event_type,
            "intensity_score": intensity, "description": description,
            "commodities_affected": [], "source": "Inserido pelo usuário",
        }
    return None


def input_gdelt(container) -> dict | None:
    query = container.text_input(
        "Busca livre na GDELT", placeholder="ex: russia ukraine grain export"
    )
    if container.button("🔎 Buscar no GDELT", use_container_width=True) and query:
        with st.spinner("Consultando GDELT..."):
            st.session_state["gdelt_articles"] = get_collector().search_gdelt(query, max_records=25)
    articles = st.session_state.get("gdelt_articles", [])
    if not articles:
        container.caption("Faça uma busca para listar eventos recentes.")
        return None
    options = {f"{a['title'][:90]} — {a['domain']}": a for a in articles if a.get("title")}
    if not options:
        container.warning("A busca não retornou artigos utilizáveis.")
        return None
    label = container.selectbox("Selecione um artigo", list(options.keys()))
    event = collector.article_to_event(options[label])
    container.caption("Esqueleto gerado a partir do artigo — revise região/intensidade se quiser.")
    return event


# --------------------------------------------------------------------------- #
# Mapa
# --------------------------------------------------------------------------- #
def render_map(event: dict, similar_events: list[dict]) -> None:
    fig = go.Figure()
    if similar_events:
        fig.add_trace(go.Scattergeo(
            lat=[e.get("lat", 0.0) for e in similar_events],
            lon=[e.get("lon", 0.0) for e in similar_events],
            mode="markers+text",
            marker=dict(size=12, color="#fb923c", line=dict(width=1, color="rgba(255,255,255,0.6)")),
            text=[e.get("title", "") for e in similar_events],
            textposition="top center", textfont=dict(color="#fcd9b6", size=10),
            name="Análogos históricos",
        ))
    fig.add_trace(go.Scattergeo(
        lat=[event.get("lat", 0.0)], lon=[event.get("lon", 0.0)],
        mode="markers",
        marker=dict(size=22, color="#f43f5e", symbol="circle",
                    line=dict(width=2, color="rgba(255,255,255,0.8)")),
        name="Evento atual",
    ))
    fig.update_layout(
        geo=dict(
            bgcolor="rgba(0,0,0,0)",
            showland=True, landcolor="rgba(255,255,255,0.14)",
            showocean=True, oceancolor="rgba(125,211,252,0.10)",
            showlakes=True, lakecolor="rgba(125,211,252,0.10)",
            showcoastlines=True, coastlinecolor="rgba(255,255,255,0.30)",
            showcountries=True, countrycolor="rgba(255,255,255,0.18)",
            showframe=False, projection_type="natural earth",
        ),
        paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#e8edf5"),
        height=500, margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.0,
                    bgcolor="rgba(0,0,0,0)"),
    )
    st.plotly_chart(fig, use_container_width=True)


# --------------------------------------------------------------------------- #
# Painel de análise
# --------------------------------------------------------------------------- #
def render_analysis(result: dict) -> None:
    tab_brief, tab_comm, tab_analog, tab_valid = st.tabs(
        ["📝 Briefing", "📊 Commodities em Risco", "🕓 Análogos Históricos", "✅ Validação"]
    )

    with tab_brief:
        briefing = result["briefing"]
        meta = briefing["meta"]
        if briefing["quality"] == "low":
            st.warning("Briefing curto (< 200 palavras) — qualidade marcada como baixa.")
        if meta.get("offline"):
            st.info("Briefing em **modo offline** (template). Conecte uma chave de LLM para análise completa via IA.")
        else:
            st.caption(
                f"Provider: {meta.get('provider')} · Modelo: {meta.get('model')} · "
                f"Tokens: {meta.get('tokens')} · Tempo: {meta.get('elapsed_s')}s"
            )
        st.markdown(briefing["markdown"])
        st.download_button(
            "⬇️ Baixar briefing (.txt)", data=briefing["markdown"],
            file_name=f"briefing_{result['event']['id']}.txt", mime="text/plain",
        )
        if briefing["sources"]:
            st.markdown("**Fontes (rastreabilidade):**")
            for src in briefing["sources"]:
                st.markdown(f"- {src['title']} ({src['date']}) — similaridade {src['similarity_pct']}%")

    with tab_comm:
        summary = result["historical_summary"]
        rows, chart_labels, chart_values = [], [], []
        for commodity, stats in summary.items():
            rows.append({
                "Commodity": commodity,
                "Variação média 30d": _fmt_pct(stats.get("mean_change_30d")),
                "Variação máxima 30d": _fmt_pct(stats.get("max_change_30d")),
                "Precedentes": stats.get("n_precedents", 0),
                "Confiança": stats.get("confidence", "—"),
            })
            if stats.get("mean_change_30d") is not None:
                chart_labels.append(commodity)
                chart_values.append(stats["mean_change_30d"])
        st.dataframe(rows, use_container_width=True, hide_index=True)
        if chart_values:
            bar = go.Figure(go.Bar(
                x=chart_values, y=chart_labels, orientation="h",
                marker_color=["#34d399" if v >= 0 else "#f43f5e" for v in chart_values],
            ))
            bar.update_layout(
                title="Variação média histórica em 30 dias (%)",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e8edf5"), height=350, margin=dict(l=0, r=0, t=40, b=0),
            )
            st.plotly_chart(bar, use_container_width=True)

    with tab_analog:
        for ev in result["similar"]:
            with st.container(border=True):
                st.markdown(f"**{ev['title']}** — {ev['date']}")
                st.caption(
                    f"Região: {ev['region']} · Tipo: {EVENT_TYPES.get(ev['event_type'], ev['event_type'])} · "
                    f"Similaridade: {ev['similarity_pct']}%"
                )
                verified = (ev.get("metadata") or {}).get("verified_outcomes") or {}
                if verified:
                    for k, v in verified.items():
                        st.markdown(f"- {k}: **{v}**")
                else:
                    st.caption("Sem impactos de preço registrados na base.")
        if not result["similar"]:
            st.info("Nenhum análogo histórico suficientemente próximo foi encontrado.")

    with tab_valid:
        render_validation_tab(result["event"])


def render_validation_tab(event: dict) -> None:
    from tests.validation import ukraine_2022 as validation

    case = validation.VALIDATION_CASES.get(event.get("id"))
    if not case:
        st.info(
            "Aba de validação disponível ao selecionar um dos eventos de validação "
            "retroativa (Ucrânia 2022, Sanções ao Irã 2012, COVID-19 2020)."
        )
        return
    st.markdown(f"### Validação retroativa — {case['label']}")
    st.markdown(f"**Critério de sucesso:** {case['success_criterion']}")
    st.dataframe(
        [
            {"Métrica": "Commodities esperadas", "Valor": ", ".join(case["expected_commodities"])},
            {"Métrica": "Análogos esperados", "Valor": ", ".join(case["expected_analogs"]) or "—"},
            {"Métrica": "Variações reais conhecidas",
             "Valor": "; ".join(f"{k}: {v}" for k, v in case["real_outcomes"].items())},
        ],
        use_container_width=True, hide_index=True,
    )


def _fmt_pct(value) -> str:
    return f"{value:+.1f}%" if value is not None else "—"


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #
def run_pipeline(raw_event: dict, config: dict) -> dict:
    fred = FredClient(api_key=config["fred_key"] or None)
    llm = LLMClient(provider=config["provider"], api_key=config["api_key"] or None)

    event = preprocessor.structure_event(raw_event)
    event["embedding"] = preprocessor.embed_event(event)

    engine = get_engine()
    similar = engine.search_similar_events(event, n_results=config["n_analogs"])

    commodities = preprocessor.map_commodities(event)
    price_data = impact_analyzer.get_price_impact(
        commodities, event["date"], window_days=[7, 30, 90], fred_client=fred
    )
    historical = impact_analyzer.analyze_historical_analogs(similar, commodities, fred_client=fred)
    briefing = briefing_generator.generate(
        event, similar, price_data, historical, commodities_at_risk=commodities, llm_client=llm
    )
    return {
        "event": event, "similar": similar, "commodities": commodities,
        "price_data": price_data, "historical_summary": historical, "briefing": briefing,
    }


def _analysis_signature(raw_event: dict, config: dict) -> str:
    """Assinatura que dispara nova análise quando o evento ou a config muda."""
    parts = [
        raw_event.get("id", ""), raw_event.get("date", ""),
        raw_event.get("event_type", ""), raw_event.get("region", ""),
        str(raw_event.get("intensity_score", "")),
        config["provider"], "k" if config["api_key"] else "",
        "f" if config["fred_key"] else "", str(config["n_analogs"]),
    ]
    return hashlib.sha1("|".join(parts).encode()).hexdigest()


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    inject_css()
    config = render_sidebar()

    st.title("Análise de Risco Geopolítico em Commodities")
    st.caption(
        "Protótipo acadêmico baseado em RAG. Ao abrir um evento, o GeoShock recupera "
        "análogos históricos, mapeia commodities em risco e gera um briefing — "
        "**sem** previsão de preços nem recomendação de investimento."
    )

    left, right = st.columns([0.6, 0.4])

    # ---- Coluna esquerda: definição do evento ----
    with left:
        with st.container(border=True):
            st.subheader("🧩 Definição do evento")
            if config["mode"] == "Selecionar evento histórico":
                raw_event = input_historical(st)
            elif config["mode"] == "Inserir evento manualmente":
                raw_event = input_manual(st)
            else:
                raw_event = input_gdelt(st)
            if raw_event:
                st.session_state["raw_event"] = raw_event

    raw_event = st.session_state.get("raw_event")

    # ---- Disparo da análise (automático + botão manual) ----
    with right:
        with st.container(border=True):
            st.subheader("🚀 Análise")
            force = st.button("🔄 Gerar / Regenerar análise", type="primary", use_container_width=True)

    should_run = False
    if raw_event:
        sig = _analysis_signature(raw_event, config)
        changed = st.session_state.get("analysis_sig") != sig
        if force or (config["auto"] and changed):
            should_run = True
            st.session_state["analysis_sig"] = sig

    if should_run:
        try:
            with st.spinner("Consultando base histórica e gerando briefing..."):
                st.session_state["result"] = run_pipeline(raw_event, config)
        except ValidationError as exc:
            st.session_state["result"] = None
            with right:
                st.error(f"Evento inválido: {exc}")

    result = st.session_state.get("result")

    # ---- Render ----
    with left:
        with st.container(border=True):
            st.markdown("##### 🗺️ Mapa")
            render_map(
                result["event"] if result else (raw_event or {"lat": 0.0, "lon": 0.0}),
                result["similar"] if result else [],
            )
    with right:
        if result:
            with st.container(border=True):
                render_analysis(result)
        else:
            with st.container(border=True):
                st.info("Selecione ou abra um evento à esquerda para gerar a análise.")

    st.divider()
    st.caption(
        f"GeoShock v{APP_VERSION} · [Repositório]({REPO_URL}) · "
        "Protótipo acadêmico — FAE Centro Universitário, 2026. "
        "Análise educacional; não constitui recomendação de investimento."
    )


if __name__ == "__main__":
    main()
