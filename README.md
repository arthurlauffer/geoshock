# GeoShock 🌍

**Protótipo baseado em Retrieval-Augmented Generation (RAG) para monitoramento de risco geopolítico em commodities globais.**

GeoShock conecta eventos geopolíticos a impactos históricos e esperados sobre commodities. Dado um evento (histórico, manual ou recuperado ao vivo da GDELT), o sistema recupera casos análogos por similaridade semântica, cruza com variações de preço observadas na FRED e gera um briefing analítico em linguagem natural via IA generativa.

> Protótipo acadêmico — TCC, FAE Centro Universitário, Curitiba, 2026.
> **Autores:** Arthur da Silva Lauffer, Davi Jacomeli Kemper, João Antonio de Assis Niquele, Marcelo Augusto Capraro Filho.

---

## O que o GeoShock faz

1. Coleta/carrega um evento geopolítico estruturado.
2. Converte o evento em embedding semântico (`all-MiniLM-L6-v2`).
3. Consulta o ChromaDB pelos casos históricos mais similares.
4. Cruza esses casos com variações de preço de séries da FRED.
5. Envia o contexto estruturado a uma API de IA generativa.
6. Gera um briefing analítico em Markdown.
7. Exibe tudo numa interface Streamlit com mapa interativo.

## O que o GeoShock **NÃO** faz

- ❌ Não faz previsão quantitativa de preços futuros.
- ❌ Não gera recomendações de compra/venda de ativos.
- ❌ Não analisa renda variável (ações, câmbio).
- ❌ Não acessa dados em tempo real de bolsas.
- ❌ Não é plataforma de trading algorítmico.

É um **protótipo acadêmico** para fins educacionais e de pesquisa. Toda análise baseia-se em **analogias históricas**.

---

## Arquitetura

```
geoshock/
├── app.py                        # Interface Streamlit (integra tudo)
├── modules/
│   ├── collector.py              # Módulo 1: coleta (GDELT, FRED, base local)
│   ├── preprocessor.py           # Módulo 2: embeddings + mapeamento de commodities
│   ├── similarity_engine.py      # Módulo 3: similaridade histórica (ChromaDB)
│   ├── impact_analyzer.py        # Módulo 4: análise de impacto de preços (FRED)
│   └── briefing_generator.py     # Módulo 5: geração de briefing via IA
├── data/
│   ├── commodity_mapping.json    # Mapeamento evento → commodities
│   ├── historical_events.json    # Base de eventos históricos validados
│   └── chroma_db/                # Banco vetorial (gerado em runtime)
├── utils/
│   ├── fred_client.py            # Cliente FRED API (+ fallback offline)
│   ├── gdelt_client.py           # Cliente GDELT API (rate limit + retry)
│   └── validators.py             # Validações e sanitização
└── tests/
    ├── test_collector.py
    ├── test_similarity.py
    ├── test_briefing.py
    └── validation/ukraine_2022.py  # Validação retroativa (3 casos)
```

---

## Instalação

1. Clone o repositório: `git clone https://github.com/geoshock/geoshock`
2. Crie o ambiente virtual: `python -m venv venv && source venv/bin/activate`
3. Instale as dependências: `pip install -r requirements.txt`
4. Configure as variáveis: `cp .env.example .env` (preencha as API keys)
5. Inicialize o banco vetorial: `python -m modules.similarity_engine --init`
6. Execute a aplicação: `streamlit run app.py`

### Modo offline (sem chaves de API)

O GeoShock roda **sem nenhuma chave**, com degradação graciosa:

- **Sem `FRED_API_KEY`** → séries de preço sintéticas/ilustrativas (deterministas).
- **Sem chave de LLM** → briefing montado por template determinista a partir do contexto recuperado.
- **GDELT** é gratuita e não exige chave; o modo ao vivo depende apenas de conexão.

Isso garante reprodutibilidade: qualquer pesquisador consegue rodar a demo e os testes imediatamente. Os modos offline são sinalizados na interface.

---

## Chaves de API (todas gratuitas)

| Serviço | Onde obter | Variável |
|---------|-----------|----------|
| FRED | https://fred.stlouisfed.org | `FRED_API_KEY` |
| Anthropic | https://console.anthropic.com | `ANTHROPIC_API_KEY` |
| OpenAI | https://platform.openai.com | `OPENAI_API_KEY` |
| Google Gemini | https://aistudio.google.com | `GOOGLE_API_KEY` |

Selecione o provider de LLM em `LLM_PROVIDER` (`anthropic` | `openai` | `google`).

---

## Testes e validação

```bash
# Testes unitários (rodam offline; testes do ChromaDB são pulados se a lib faltar)
pytest tests/

# Validação retroativa dos 3 casos do TCC
python -m tests.validation.ukraine_2022
```

Casos de validação retroativa:

| Caso | Commodities esperadas | Variação real conhecida |
|------|----------------------|--------------------------|
| Invasão da Ucrânia (2022) | trigo, milho, fertilizantes, gás natural | trigo +32% (30d), gás natural EU +55% (30d) |
| Sanções ao Irã (2012) | petróleo bruto | WTI +8% (30d) |
| COVID-19 Lockdowns (2020) | petróleo, cobre, alumínio | petróleo −55% (30d) |

---

## Referências técnicas

- **RAG:** Lewis et al. (2020), NeurIPS.
- **ChromaDB:** Chroma (2024), https://www.trychroma.com
- **GDELT:** Leetaru & Schrodt (2013), ISA Annual Convention.
- **FRED:** Federal Reserve Bank of St. Louis, https://fred.stlouisfed.org
- **Risco geopolítico:** Caldara & Iacoviello (2022), American Economic Review.
- **Commodities e choques:** Hamilton (1983), Journal of Political Economy.
- **Event Study:** MacKinlay (1997), Journal of Economic Literature.

---

## Licença

MIT — ver [LICENSE](LICENSE). Sem dependências pagas.
