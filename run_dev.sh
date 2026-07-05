#!/usr/bin/env bash
# Sobe backend (FastAPI) + frontend (Next.js) do GeoShock em desenvolvimento.
# Uso: ./run_dev.sh   (Ctrl+C encerra os dois)
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "▶ Backend FastAPI em http://localhost:8000 (docs em /docs)"
./venv/bin/python -m uvicorn api_server:app --port 8000 --reload &
API_PID=$!

echo "▶ Frontend Next.js em http://localhost:3100"
(cd web && npm run dev -- -p 3100) &
WEB_PID=$!

trap "echo; echo 'Encerrando...'; kill $API_PID $WEB_PID 2>/dev/null" INT TERM
wait
