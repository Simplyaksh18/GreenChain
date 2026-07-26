#!/usr/bin/env bash
# GreenChain backend — production start script.
#
# Used by Render / Railway / Docker as the container start command.
# Runs Alembic migrations, then serves the app with Gunicorn + Uvicorn workers.
# Migration failures are NOT hidden — the process exits non-zero if they fail.
set -euo pipefail

: "${PORT:=8000}"
: "${WEB_CONCURRENCY:=2}"
: "${WEB_TIMEOUT:=120}"

echo "▶ GreenChain backend starting on port ${PORT} (workers=${WEB_CONCURRENCY})"

# Run migrations first. If this fails, the container will exit so the
# platform surfaces the error instead of serving a broken schema.
echo "▶ Running Alembic migrations…"
alembic upgrade head

echo "▶ Launching Gunicorn (uvicorn worker)…"
exec gunicorn app.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers "${WEB_CONCURRENCY}" \
    --bind "0.0.0.0:${PORT}" \
    --timeout "${WEB_TIMEOUT}" \
    --access-logfile - \
    --error-logfile -
