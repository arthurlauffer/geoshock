# GeoShock — Explorador Geopolítico por Região (Design)

**Data:** 2026-07-05
**Projeto:** GeoShock (`/Users/arthurlauffer/Downloads/geoshock`)
**Autores:** Arthur Lauffer (product) · assistido por Claude Code

---

## 1. Visão e objetivo

Transformar o GeoShock de uma **ferramenta de análise de um evento por vez** em uma
**plataforma map-first que mostra, de maneira simples, informações geopolíticas por
região do mundo**. O mapa-múndi é a tela principal; o usuário explora regiões, vê o
que está acontecendo em cada uma e, quando quiser, aprofunda na análise de risco de
commodities que o motor RAG já produz.

### Decisões travadas (do brainstorming)
- **Mapa:** ao vivo + curado, com clique que dispara a análise RAG existente.
- **Escopo por região:** resumo geral simples da situação **+** a camada de commodities
  que já existe (o escopo do TCC é preservado, não descartado).
- **Público:** modo **simples** por padrão (mapa + resumo claro, sem jargão), com um
  **toggle "detalhes analíticos"** que revela a UI técnica atual (similaridade, análogos,
  tokens, validação).
- **Fonte ao vivo:** **por região** (uma busca GDELT por região), carregada **sob demanda**
  ao abrir a região (não todas de uma vez).
- **Resumo de região:** gerado pelo LLM (Gemini, grátis) a cada abertura de região, com
  fallback offline por template.

### Visão de futuro (fora do escopo deste ciclo, mas o design não pode impedir)
Eventualmente: clicar em **cada país** e ver **todos os conflitos históricos daquele país**
e **o que aconteceu com certas commodities**. Por isso o modelo de dados é **país-cêntrico
por baixo** (regiões são grupos de países; o geocoder usa centróides de país). O drill-down
por país é um passo natural depois, sem reescrever a base.

---

## 2. Objetivos e não-objetivos

### Objetivos (deste ciclo)
1. Mapa mostra **vários eventos ao mesmo tempo** (curados + ao vivo), clicáveis.
2. Eventos da GDELT **aparecem no mapa** (hoje chegam sem coordenadas) via geocodificação.
3. **~8 regiões** navegáveis; abrir uma região mostra um **resumo simples** + eventos ao
   vivo daquela região + commodities agregadas em risco.
4. **Modo simples/analista** por toggle. Simples é o padrão.
5. Não quebrar o pipeline atual (27 testes Python passando; build Next limpo).

### Não-objetivos (agora)
- Drill-down por país individual (futuro).
- Persistência de eventos ao vivo em banco (fetch fresco + cache curto basta).
- Previsão de preços / recomendação de investimento (proibido por design, como já é).
- Autenticação / multiusuário.

---

## 3. Arquitetura

Mantém a separação atual: **backend FastAPI (Python, todo o RAG)** + **frontend Next.js**.
Nenhuma inteligência migra para JS.

```
Frontend (Next.js)                         Backend (FastAPI, Python)
------------------                         -------------------------
Mapa multi-evento  ──GET /api/map_events──▶ eventos curados (rápido, sem GDELT)
Clique em região   ──GET /api/region/{id}─▶ GDELT da região + geocode + resumo LLM + commodities
Clique em evento   ──POST /api/analyze────▶ pipeline RAG existente (inalterado)
Toggle analista    (só UI)
```

---

## 4. Backend — componentes novos

### 4.1 Geocodificador (`utils/geocoder.py`)
- Tabela **ISO 3166-1 alpha-2 → (lat, lon)** de centróides de país (`data/country_centroids.json`),
  cobrindo ao menos todos os países usados nas regiões e nos eventos históricos.
- `centroid(code: str) -> tuple[float, float] | None`.
- `geocode_event(event: dict) -> dict`: se `lat/lon` forem 0/ausentes, tenta pelo primeiro
  `country_codes`; se não houver, tenta mapear `sourcecountry` (nome em inglês) → código via
  um dicionário nome→ISO2. Retorna o evento com `lat/lon` preenchidos quando possível.
- Função pura, testável offline.

### 4.2 Modelo de região (`data/regions.json`)
Schema de cada região:
```json
{
  "id": "middle_east",
  "name": "Oriente Médio",
  "name_en": "Middle East",
  "center": { "lat": 29.0, "lon": 45.0 },
  "countries": ["IR", "IQ", "SA", "IL", "SY", "YE", "AE", "KW"],
  "gdelt_query": "(sanctions OR strike OR conflict OR oil OR blockade) (Iran OR Israel OR Iraq OR Saudi OR Yemen)"
}
```
~8 regiões: Europa Oriental, Oriente Médio, Norte da África, África Subsaariana,
Ásia Oriental, Sudeste Asiático, América Latina, América do Norte. Os `countries`
casam com o mapeamento de commodities existente sempre que possível.

### 4.3 `GET /api/regions`
Lista as regiões (id, nome, center, countries) para o frontend montar a navegação.

### 4.4 `GET /api/map_events`
Retorna os **eventos curados** (históricos), cada um já geocodificado, para plotar o
mapa imediatamente. **Não** chama a GDELT (rápido). Formato: `{ "events": [GeoEvent...] }`.

### 4.5 `GET /api/region/{region_id}`
Sob demanda, para a região aberta:
1. Busca eventos ao vivo na GDELT com o `gdelt_query` da região (reusa `GdeltClient`,
   rate-limit e cache já existentes).
2. Converte artigos em eventos (`article_to_event`) e **geocodifica** (centróide do país
   da região quando o artigo não tiver país; distribui levemente para não empilhar).
3. Agrega as **commodities em risco** da região: para cada evento ao vivo roda
   `preprocessor.map_commodities` e faz a **união** (preservando ordem, sem duplicatas);
   se não houver eventos ao vivo, usa as commodities default da região a partir do
   `event_type` predominante em `commodity_mapping.json`.
4. Gera um **resumo simples** em pt-BR (`region_summarizer`, usando `LLMClient`): 2–3
   frases claras sobre a situação da região, sem jargão. Fallback offline por template.
Resposta:
```json
{
  "region": { "id": "...", "name": "...", "center": {...} },
  "summary": "texto simples...",
  "risk_level": "alto|médio|baixo",
  "live_events": [GeoEvent...],
  "commodities_at_risk": ["crude_oil", "natural_gas", ...],
  "meta": { "offline": false, "n_live": 7 }
}
```
- `risk_level`: heurística simples a partir do volume/intensidade de eventos (documentada no
  código; não é previsão de mercado).

### 4.6 `region_summarizer` (novo módulo `modules/region_summarizer.py`)
- `summarize_region(region, live_events, commodities) -> {summary, risk_level, offline}`.
- System prompt curto: analista explicando a situação regional para leigo, sem recomendação
  de investimento, sem previsão de preço. Reusa as regras/guardrails do system prompt atual.

---

## 5. Frontend — mudanças

### 5.1 Mapa multi-evento (`components/WorldMap.tsx`)
- Passa a receber e plotar **uma lista de eventos** (curados + ao vivo da região aberta),
  todos clicáveis (`onSelectEvent`).
- Marcadores por tipo: evento curado vs ao vivo (cor/opacidade), evento em foco destacado.
- Ao clicar num marcador → dispara `POST /api/analyze` (fluxo atual).

### 5.2 Navegação e painel de região
- Lista/menu de **regiões** (do `/api/regions`); clicar centraliza o mapa e chama
  `/api/region/{id}`.
- **Painel de região (modo simples):** nome da região, `risk_level` como selo, o **resumo**
  em texto claro, e "Commodities mais expostas" como chips com uma linha de explicação.
  Lista enxuta dos eventos ao vivo (título + data), cada um clicável para analisar.

### 5.3 Modo simples / analista (toggle global)
- Estado `viewMode: "simple" | "analyst"` no topo.
- **Simples (padrão):** mapa + painel de região + (ao analisar um evento) um briefing curto
  em linguagem clara e "top 3 commodities". Esconde similaridade %, tokens, aba de validação.
- **Analista:** revela o `AnalysisPanel` atual completo (briefing, commodities, análogos,
  validação, metadados do LLM).
- Persistir a escolha em `localStorage`.

### 5.4 Tipos e API client
- `lib/types.ts`: adicionar `Region`, `RegionDetail`.
- `lib/api.ts`: `fetchRegions()`, `fetchMapEvents()`, `fetchRegion(id)`.

---

## 6. Escopo do TCC preservado
A camada de commodities, os análogos e a validação **continuam existindo** — apenas ficam
atrás do toggle "analista". A defesa da monografia usa o modo analista; o público usa o
modo simples. Nada do trabalho atual é descartado.

---

## 7. Testes
- **Python (offline, sem chaves):**
  - `geocoder`: centróide por código; `geocode_event` preenche lat/lon; código desconhecido
    retorna None sem quebrar.
  - `/api/map_events`: retorna eventos curados todos com lat/lon != (0,0).
  - `/api/region/{id}`: com GDELT/LLM offline, retorna estrutura completa (summary por
    template, `live_events` possivelmente vazio, `commodities_at_risk` não vazio).
  - `region_summarizer`: fallback offline produz resumo não vazio; região inválida → 404.
  - Regressão: os 27 testes atuais continuam passando.
- **Frontend:** `npm run build` passa (type-check). Verificação manual do mapa multi-evento
  e do toggle.

---

## 8. Decomposição em tarefas (para execução por subagentes)

Cada tarefa é razoavelmente independente e entrega valor testável.

1. **Geocoder** — `data/country_centroids.json` + `utils/geocoder.py` + testes.
2. **Regiões + map_events** — `data/regions.json`, `GET /api/regions`, `GET /api/map_events`
   (curados geocodificados) + testes.
3. **Detalhe de região** — `region_summarizer` + `GET /api/region/{id}` (GDELT por região,
   geocode, agregação de commodities, resumo LLM com fallback) + testes.
4. **Frontend — mapa multi-evento** — `WorldMap` plota N eventos clicáveis; `map_events` no
   carregamento; tipos + api client.
5. **Frontend — região + modo simples/analista** — painel de região, navegação de regiões,
   toggle de modo com persistência.
6. **Integração + revisão final** — fluxo ponta a ponta, regressão dos testes, build.

### Restrições globais (para implementadores e revisores)
- Todo o RAG permanece em Python; frontend só consome a API.
- Nenhuma função pode quebrar os 27 testes existentes nem o `npm run build`.
- Sem previsão de preço nem recomendação de investimento em nenhum texto gerado.
- Modo simples é o padrão; nada técnico aparece nele.
- Funções de dados (geocoder, agregação) são puras e testáveis offline.
- Chaves lidas do `.env` pelo backend; o frontend nunca recebe chave.

---

## 9. Pré-requisito de execução
A pasta `geoshock/` **não é um repositório git**. O fluxo de subagentes faz um commit por
tarefa e revisa via `git diff`. Antes de executar: `git init` no projeto + `.gitignore`
(venv, `web/node_modules`, `web/.next`, `data/chroma_db`, `data/_*_cache`, `.env`).

---

## 10. Riscos e mitigações
- **GDELT lenta/instável ao abrir região:** cache curto + carregamento sob demanda + estado
  de loading; se vazio, mostra só o resumo e os curados.
- **Geocodificação imprecisa (país→centróide):** aceitável para visão regional; o refino por
  cidade fica para o drill-down por país (futuro).
- **Custo de LLM por clique de região:** Gemini free tier; cache do resumo por região por
  sessão reduz repetição.
