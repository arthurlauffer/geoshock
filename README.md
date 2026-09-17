# GeoShock

**Protótipo de RAG (Retrieval-Augmented Generation) para monitoramento de risco geopolítico em commodities globais.**

> Protótipo acadêmico — TCC, FAE Centro Universitário, Curitiba, 2026.
> **Autores:** Arthur da Silva Lauffer, Davi Jacomeli Kemper, João Antonio de Assis Niquele, Marcelo Augusto Capraro Filho.

Este documento assume que você nunca viu este projeto antes. Siga na ordem.

---

## 1. O que é isto

O GeoShock é um explorador de risco geopolítico por região do mundo. Você abre uma região (ex.: Oriente Médio, Europa Oriental) e o sistema:

1. Busca eventos geopolíticos recentes na região (notícias via **GDELT** + conflitos armados verificados via **UCDP** + sanções confirmadas via **OFAC**).
2. Identifica quais commodities globais estão em risco por causa desses eventos.
3. Cruza com séries de preço reais da **FRED** (Federal Reserve).
4. Recupera análogos históricos semanticamente parecidos (ex.: a invasão da Ucrânia em 2022 puxa o embargo árabe de 1973 como precedente).
5. Gera um briefing em linguagem natural via IA generativa (Gemini, Claude ou GPT — você escolhe).
6. Mostra tudo num mapa interativo, com um modo "Simples" (linguagem leiga) e um modo "Analista" (métricas técnicas completas).

**O que o GeoShock não faz:** não prevê preços futuros, não recomenda compra/venda de nada, não analisa ações ou câmbio, não é uma ferramenta de trading. É uma ferramenta educacional que raciocina por analogia histórica.

---

## 2. Arquitetura (leia antes de rodar)

O projeto tem **dois servidores separados que rodam ao mesmo tempo**:

```
┌─────────────────────┐         ┌──────────────────────────┐
│  Frontend (Next.js)  │  HTTP   │  Backend (Python/FastAPI) │
│  porta 3100           │ ──────▶ │  porta 8000                │
│  o que você abre no   │         │  toda a lógica de RAG,     │
│  navegador             │         │  embeddings, IA e dados     │
└─────────────────────┘         └──────────────────────────┘
```

- **Backend** (`api_server.py` + `modules/` + `utils/`): 100% Python. Tem o banco vetorial (ChromaDB), os embeddings (sentence-transformers), e os clientes de dados externos.
- **Frontend** (`web/`): Next.js + React + Tailwind. É só interface — não tem lógica de negócio, só consome a API do backend.

**Os dois precisam estar rodando ao mesmo tempo** para o site funcionar. Se você só subir o frontend, ele vai mostrar erro de conexão.

> **Nota:** existe também um `app.py` na raiz do projeto — é uma interface **Streamlit legada**, de uma versão anterior do protótipo, mantida só como referência histórica. **Não é isso que você deve rodar.** A interface atual é o `web/` (Next.js), seguindo os passos abaixo.

### Fontes de dados usadas

| Fonte | Para quê | Precisa de chave? |
|---|---|---|
| **GDELT** | Notícias recentes por região (pulso em tempo real) | Não — API aberta |
| **UCDP** | Eventos de conflito armado verificados, com severidade real (mortes estimadas) e coordenadas precisas | Não — arquivo público |
| **OFAC** | Lista oficial de sanções dos EUA (confirma se há sanção ativa num país) | Não — dado público |
| **FRED** | Preços reais de commodities (petróleo, trigo, gás, etc.) | Sim — grátis, ver seção 4 |
| **Gemini / Claude / GPT** | Escreve o briefing em linguagem natural | Sim — grátis, ver seção 4 |

Sem nenhuma chave, o sistema **ainda funciona**: preços caem para uma série sintética ilustrativa e o briefing vira um texto de template determinístico, sempre deixando claro na tela que está em "modo offline". Com as chaves, tudo fica real.

---

## 3. Pré-requisitos

Instale antes de começar:

- **Python 3.9 ou superior** (`python3 --version`)
- **Node.js 20 ou superior** (`node --version`)
- **git**

Não precisa de Docker, banco de dados externo, nem nada pago.

---

## 4. Passo a passo de instalação

### 4.1. Clonar e entrar na pasta

```bash
git clone <URL_DESTE_REPOSITORIO>
cd geoshock
```

### 4.2. Backend (Python)

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

A primeira instalação baixa `sentence-transformers`/`torch`, que é pesado (alguns minutos e ~1-2GB). É normal.

### 4.3. Frontend (Next.js)

```bash
cd web
npm install
cd ..
```

### 4.4. Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Abra `.env` num editor e preencha **pelo menos uma chave de LLM** e a **chave da FRED** (ambas gratuitas, sem cartão de crédito):

| Variável | Onde conseguir | Grátis? |
|---|---|---|
| `GOOGLE_API_KEY` | https://aistudio.google.com/app/apikey | Sim |
| `ANTHROPIC_API_KEY` | https://console.anthropic.com | Sim (tem cota gratuita) |
| `OPENAI_API_KEY` | https://platform.openai.com | Sim (tem cota gratuita) |
| `FRED_API_KEY` | https://fredaccount.stlouisfed.org/apikey | Sim |

Defina `LLM_PROVIDER=google` (ou `anthropic`/`openai`) de acordo com qual chave você preencheu. GDELT, UCDP e OFAC **não precisam de chave** — já funcionam prontos.

Se pular esta etapa, o sistema roda em modo offline (ver seção 2).

### 4.5. Rodar

Forma mais simples — sobe os dois servidores juntos:

```bash
chmod +x run_dev.sh
./run_dev.sh
```

Ou manualmente, em dois terminais separados:

```bash
# Terminal 1 — backend
./venv/bin/python -m uvicorn api_server:app --port 8000 --reload

# Terminal 2 — frontend
cd web && npm run dev -- -p 3100
```

Abra **http://localhost:3100** no navegador. `Ctrl+C` encerra ambos (se usou `run_dev.sh`).

---

## 5. Primeira execução: o que esperar

- Na primeira vez que você clica numa região, o backend baixa em segundo plano as bases da UCDP (~8MB) e da OFAC (~100MB). Isso já começa a acontecer sozinho assim que o backend sobe (não precisa fazer nada), mas pode levar 1-2 minutos até a resposta da região ficar rápida se você clicar muito cedo. Depois disso fica em cache local (`data/_ucdp_cache/`, `data/_ofac_cache/`) por 24h.
- A GDELT é uma API pública gratuita com limite de **1 requisição a cada 5 segundos**. Se você testar rápido demais (várias buscas seguidas), ela pode devolver poucos ou nenhum resultado por alguns minutos — não é bug, é o limite deles. O resto do sistema (UCDP, OFAC, FRED) continua funcionando normalmente mesmo se a GDELT estiver de folga.
- O modo "Simples" (padrão) mostra linguagem leiga. O botão "Analista" no topo mostra tokens, similaridade %, validação retroativa etc.

---

## 6. Testes

```bash
# Suíte completa do backend (roda 100% offline, sem precisar de nenhuma chave)
./venv/bin/python -m pytest tests/ -v

# Validação retroativa dos 3 casos históricos do TCC
./venv/bin/python -m tests.validation.ukraine_2022

# Build de produção do frontend (verifica erros de tipo)
cd web && npm run build
```

---

## 7. Estrutura do projeto

```
geoshock/
├── api_server.py                 # Backend FastAPI — todos os endpoints HTTP
├── run_dev.sh                    # Sobe backend + frontend juntos
├── modules/
│   ├── collector.py              # Coleta de eventos (GDELT, base histórica)
│   ├── preprocessor.py           # Embeddings + mapeamento evento → commodities
│   ├── similarity_engine.py      # Busca por similaridade (ChromaDB)
│   ├── impact_analyzer.py        # Variação de preços em torno de um evento (FRED)
│   ├── briefing_generator.py     # Geração do briefing via LLM
│   ├── regions.py                # As 8 regiões do mundo monitoradas
│   ├── region_summarizer.py      # Resumo de região (agrega GDELT+UCDP+OFAC)
│   └── data_normalizer.py        # Converte dados da UCDP/OFAC pro formato interno
├── utils/
│   ├── fred_client.py            # Cliente FRED (+ fallback offline)
│   ├── gdelt_client.py           # Cliente GDELT (rate limit + retry)
│   ├── ucdp_client.py            # Cliente UCDP (conflitos armados verificados)
│   ├── ofac_client.py            # Cliente OFAC (sanções confirmadas)
│   ├── geocoder.py               # País → coordenadas
│   └── validators.py             # Validação/sanitização de eventos
├── data/                         # Dados estáticos + caches (gerados em runtime)
├── tests/                        # Testes automatizados (todos offline)
└── web/                          # Frontend Next.js
    ├── app/page.tsx              # Página principal
    ├── components/               # Mapa, painel de região, painel de análise
    └── lib/                      # Cliente HTTP da API + tipos TypeScript
```

---

## 8. Solução de problemas

**"Não consigo falar com o backend na porta 8000"** (mensagem no frontend)
→ O backend não está rodando. Confira o terminal onde você rodou `uvicorn` ou `run_dev.sh`.

**Backend demora muito pra responder na primeira vez que abro uma região**
→ Normal (ver seção 5) — está baixando UCDP/OFAC em segundo plano. Espere ~1-2 min e tente de novo.

**GDELT não retorna nada / poucos resultados**
→ Rate limit deles (1 req/5s). Espere alguns minutos. Não afeta UCDP, OFAC nem FRED.

**Erro ao instalar `sentence-transformers`/`torch`**
→ Confirme que está usando Python 3.9+ e que o `pip` está atualizado (`pip install --upgrade pip`).

**Quero rodar sem nenhuma chave de API**
→ Funciona. Pule a seção 4.4. Tudo cai em modo offline/sintético, sinalizado na interface.

---

## 9. Referências técnicas

- **RAG:** Lewis et al. (2020), NeurIPS.
- **ChromaDB:** Chroma (2024), https://www.trychroma.com
- **GDELT:** Leetaru & Schrodt (2013), ISA Annual Convention.
- **UCDP:** Uppsala Conflict Data Program, https://ucdp.uu.se
- **OFAC:** U.S. Department of the Treasury, https://ofac.treasury.gov
- **FRED:** Federal Reserve Bank of St. Louis, https://fred.stlouisfed.org
- **Risco geopolítico:** Caldara & Iacoviello (2022), American Economic Review.
- **Commodities e choques:** Hamilton (1983), Journal of Political Economy.
- **Event Study:** MacKinlay (1997), Journal of Economic Literature.

---

## Licença

MIT — ver [LICENSE](LICENSE). Sem dependências pagas.
