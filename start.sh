#!/bin/sh
set -eu

PORT_VALUE="${PORT:-${WEB_PORT:-5000}}"
WORKER_COUNT="${WEB_CONCURRENCY:-2}"
TIMEOUT_VALUE="${GUNICORN_TIMEOUT:-120}"

if command -v gunicorn >/dev/null 2>&1; then
  exec gunicorn app:app \
    --bind "0.0.0.0:${PORT_VALUE}" \
    --workers "${WORKER_COUNT}" \
    --threads "${GUNICORN_THREADS:-2}" \
    --timeout "${TIMEOUT_VALUE}"
fi

exec python3 app.py
