#!/usr/bin/env bash
set -euo pipefail

# Local dev: postgres in docker, fastapi + vite watching, both proxied through vite at :5173.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ ! -f "$ROOT/.env" ]; then
  echo "ERROR: $ROOT/.env not found. Copy .env.example to .env and fill it in."
  exit 1
fi

echo "==> starting postgres"
docker compose -f "$ROOT/docker-compose.yml" up -d postgres

echo "==> applying migrations"
( cd "$ROOT/server" && uv run alembic upgrade head )

echo "==> starting backend on :8000"
( cd "$ROOT/server" && uv run uvicorn app.main:app --reload --port 8000 ) &
BACKEND_PID=$!

echo "==> starting frontend on :5173 (proxies /auth and /api to :8000)"
( cd "$ROOT/client" && bun run dev ) &
FRONTEND_PID=$!

trap 'kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true' EXIT
wait
