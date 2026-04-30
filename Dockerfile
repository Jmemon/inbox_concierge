# ---- Stage 1: build the SPA with bun ----
FROM oven/bun:1.3 AS frontend
WORKDIR /build
# Copy ONLY the client/ context — never `COPY . .` here, or repo-root .env
# could leak into the build context. .dockerignore covers this defensively.
COPY client/package.json client/bun.lock* ./
RUN bun install --frozen-lockfile
COPY client/ ./
RUN VITE_OUT_DIR=/build/dist bun run build

# Fail the build if any secret-shaped string leaked into the bundle.
# Mirrors scripts/check_bundle_secrets.sh but enforced on every Railway deploy.
RUN if grep -rEi "client_secret|session_secret|encryption_key|GOCSPX-" /build/dist >/dev/null; then \
      echo "FAIL: secret-like string found in built bundle"; \
      grep -rEni "client_secret|session_secret|encryption_key|GOCSPX-" /build/dist; \
      exit 1; \
    fi

# ---- Stage 2: python runtime ----
FROM python:3.13-slim AS runtime

# Install uv (Astral's installer), make it globally available.
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && ln -s /root/.local/bin/uv /usr/local/bin/uv

WORKDIR /app

# Install python deps first for layer caching.
COPY server/pyproject.toml server/uv.lock /app/
RUN uv sync --frozen --no-dev

# Copy backend source + migrations.
COPY server/ /app/

# Bring in the built frontend bundle.
COPY --from=frontend /build/dist /app/app/static

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENV=production \
    PORT=8000

# No EXPOSE — Railway routes traffic to whatever port the app binds to via $PORT,
# and the actual runtime PORT is decided by Railway, not us.

# Apply migrations on every boot, then start uvicorn.
# WORKDIR=/app puts /app on sys.path so `app.main` resolves.
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
