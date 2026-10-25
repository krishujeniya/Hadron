# Dockerfile — Hardened Multi-Stage Container for Hadron PR Review Agent
#
# Stage 1: Dependency resolution and compilation
# Stage 2: Minimal non-root runtime image (<200MB, CIS Benchmark hardened)

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /install

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip uv \
    && uv pip install --system --no-cache -e .

# ── Stage 2: Hardened Runtime ────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Install runtime libraries only (libpq5 instead of libpq-dev, no compilers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Security: Create non-root unprivileged service user
RUN groupadd -r hadron && useradd -r -g hadron -u 1000 -d /app hadron

WORKDIR /app

# Copy compiled dependencies and wheels from builder
COPY --from=builder /usr/local /usr/local

# Copy project source with non-root ownership
COPY --chown=hadron:hadron . .

USER hadron

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
