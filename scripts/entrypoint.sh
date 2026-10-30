#!/usr/bin/env bash
# scripts/entrypoint.sh
#
# Process entrypoint for Hadron container.
# Decouples API server and background worker processes so they can be
# scheduled, scaled, and health-checked independently without duplicate workers.

set -e

CMD_MODE="${1:-api}"
PORT="${PORT:-8000}"

case "$CMD_MODE" in
  api)
    echo "[Hadron Entrypoint] Launching API server on port ${PORT}..."
    exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT}" --workers "${UVICORN_WORKERS:-1}"
    ;;

  worker)
    echo "[Hadron Entrypoint] Launching ARQ background worker process..."
    exec python3 -m arq backend.job_queue.arq_worker.WorkerSettings
    ;;

  combined|all|start)
    echo "[Hadron Entrypoint] Launching combined API and worker in single container..."
    exec /bin/bash /app/scripts/start.sh
    ;;

  *)
    # Arbitrary command execution (e.g. pytest, python script, bash)
    exec "$@"
    ;;
esac
