#!/usr/bin/env bash
set -euo pipefail

# Local dev: postgres + redis in docker, fastapi + vite + celery worker + beat.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ ! -f "$ROOT/.env" ]; then
  echo "ERROR: $ROOT/.env not found. Copy .env.example to .env and fill it in."
  exit 1
fi

echo "==> starting postgres + redis"
docker compose -f "$ROOT/docker-compose.yml" up -d --wait postgres redis

echo "==> applying migrations"
( cd "$ROOT/server" && uv run alembic upgrade head )

echo "==> starting backend on :8000"
( cd "$ROOT/server" && uv run uvicorn app.main:app --reload --port 8000 ) &
BACKEND_PID=$!

echo "==> starting celery worker"
( cd "$ROOT/server" && uv run celery -A app.workers.celery_app worker --loglevel=info --concurrency=2 ) &
WORKER_PID=$!

echo "==> starting celery beat"
( cd "$ROOT/server" && uv run celery -A app.workers.celery_app beat --loglevel=info --schedule=/tmp/celerybeat-schedule ) &
BEAT_PID=$!

echo "==> starting frontend on :5173 (proxies /auth and /api to :8000)"
( cd "$ROOT/client" && bun run dev ) &
FRONTEND_PID=$!

trap 'kill $BACKEND_PID $WORKER_PID $BEAT_PID $FRONTEND_PID 2>/dev/null || true' EXIT
wait
