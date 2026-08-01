#!/bin/sh
set -eu

PORT_VALUE="${PORT:-${WEB_PORT:-5000}}"
WORKER_COUNT="${WEB_CONCURRENCY:-2}"
THREAD_COUNT="${GUNICORN_THREADS:-2}"
TIMEOUT_VALUE="${GUNICORN_TIMEOUT:-120}"
VENV_DIR="${VENV_DIR:-.venv}"

if [ -x "$VENV_DIR/bin/python" ]; then
  if "$VENV_DIR/bin/python" -m gunicorn --version >/dev/null 2>&1; then
    exec "$VENV_DIR/bin/python" -m gunicorn app:app \
      --bind "0.0.0.0:${PORT_VALUE}" \
      --workers "${WORKER_COUNT}" \
      --threads "${THREAD_COUNT}" \
      --timeout "${TIMEOUT_VALUE}"
  fi

  exec "$VENV_DIR/bin/python" app.py
fi

if command -v python3 >/dev/null 2>&1; then
  if python3 -m gunicorn --version >/dev/null 2>&1; then
    exec python3 -m gunicorn app:app \
      --bind "0.0.0.0:${PORT_VALUE}" \
      --workers "${WORKER_COUNT}" \
      --threads "${THREAD_COUNT}" \
      --timeout "${TIMEOUT_VALUE}"
  fi

  exec python3 app.py
fi

echo "ไม่พบ python ที่ใช้งานได้"
exit 1
