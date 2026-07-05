"""Módulos do pipeline GeoShock.

1. ``collector``          — coleta e ingestão de dados (GDELT, FRED, base local)
2. ``preprocessor``       — pré-processamento e geração de embeddings
3. ``similarity_engine``  — motor de similaridade histórica (ChromaDB)
4. ``impact_analyzer``    — motor de análise de impacto de preços (FRED)
5. ``briefing_generator`` — geração de briefing via IA generativa
"""
