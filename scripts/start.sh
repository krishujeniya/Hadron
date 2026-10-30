#!/usr/bin/env bash
# scripts/start.sh — Process manager for combined or standalone container execution.
set -e

PORT="${PORT:-8000}"
MODE="${1:-all}"

echo "=================================================="
echo " Starting Hadron Autonomous PR Review Agent"
echo " Mode: ${MODE}"
echo " Port: ${PORT}"
echo " Environment: ${APP_ENV:-production}"
echo "=================================================="

ARQ_PID=""
UVICORN_PID=""

cleanup() {
    echo "[Hadron] Received shutdown signal. Terminating child processes..."
    if [ -n "$ARQ_PID" ]; then
        kill -TERM "$ARQ_PID" 2>/dev/null || true
    fi
    if [ -n "$UVICORN_PID" ]; then
        kill -TERM "$UVICORN_PID" 2>/dev/null || true
    fi
    wait 2>/dev/null || true
    echo "[Hadron] All processes terminated cleanly."
    exit 0
}

trap cleanup SIGINT SIGTERM

if [ "$MODE" = "all" ] || [ "$MODE" = "worker" ]; then
    echo "[Hadron] Starting ARQ background review worker..."
    python3 -m arq backend.job_queue.arq_worker.WorkerSettings &
    ARQ_PID=$!
fi

if [ "$MODE" = "all" ] || [ "$MODE" = "api" ]; then
    echo "[Hadron] Starting FastAPI Uvicorn web server on 0.0.0.0:${PORT}..."
    uvicorn backend.main:app --host 0.0.0.0 --port "${PORT}" --workers "${UVICORN_WORKERS:-1}" &
    UVICORN_PID=$!
fi

# Wait for active processes
if [ -n "$ARQ_PID" ] && [ -n "$UVICORN_PID" ]; then
    wait -n "$ARQ_PID" "$UVICORN_PID"
    EXIT_CODE=$?
elif [ -n "$ARQ_PID" ]; then
    wait "$ARQ_PID"
    EXIT_CODE=$?
elif [ -n "$UVICORN_PID" ]; then
    wait "$UVICORN_PID"
    EXIT_CODE=$?
else
    echo "[Hadron] No service started for mode=${MODE}"
    exit 1
fi

echo "[Hadron] A process terminated with status ${EXIT_CODE}. Shutting down..."
cleanup
exit "${EXIT_CODE}"
