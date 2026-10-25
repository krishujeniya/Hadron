#!/usr/bin/env bash
set -e

PORT="${PORT:-8000}"
echo "=================================================="
echo " Starting Hadron Autonomous PR Review Agent"
echo " Web Port: ${PORT}"
echo " Environment: ${APP_ENV:-production}"
echo "=================================================="

# Start ARQ background review worker in the background
echo "[Hadron] Starting ARQ background review worker..."
python3 -m arq backend.job_queue.arq_worker.WorkerSettings &
ARQ_PID=$!

# Start FastAPI Uvicorn web server
echo "[Hadron] Starting FastAPI Uvicorn web server on 0.0.0.0:${PORT}..."
uvicorn backend.main:app --host 0.0.0.0 --port "${PORT}" --workers 1 &
UVICORN_PID=$!

# Handle shutdown signals
cleanup() {
    echo "[Hadron] Received shutdown signal. Terminating child processes..."
    kill -TERM "$ARQ_PID" "$UVICORN_PID" 2>/dev/null || true
    wait "$ARQ_PID" "$UVICORN_PID" 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

# Wait for any process to terminate
wait -n "$ARQ_PID" "$UVICORN_PID"
EXIT_CODE=$?

echo "[Hadron] A service terminated with status ${EXIT_CODE}. Shutting down container..."
kill -TERM "$ARQ_PID" "$UVICORN_PID" 2>/dev/null || true
exit "${EXIT_CODE}"
