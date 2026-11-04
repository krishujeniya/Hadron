web: uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${UVICORN_WORKERS:-2}
worker: python3 -m arq backend.job_queue.arq_worker.WorkerSettings
