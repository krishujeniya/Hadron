# Dockerfile — Multi-Stage Container for Hadron Autonomous Review Agent
#
# Declared process topology: API and Worker can be executed independently
# via the entrypoint script without duplicate workers or privilege elevation.
#
# Stage 1: Builder — dependency compilation and wheel building
# Stage 2: Runtime — minimal unprivileged non-root execution image

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy package metadata and source for dependency resolution
COPY pyproject.toml ./
COPY backend/ ./backend/
COPY scripts/ ./scripts/

RUN pip install --no-cache-dir --upgrade pip uv \
    && uv pip install --system --no-cache .

# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Security: Create non-root unprivileged service user
RUN groupadd -r hadron && useradd -r -g hadron -u 1000 -d /app -m hadron

WORKDIR /app

# Copy compiled dependencies and wheels from builder
COPY --from=builder /usr/local /usr/local

# Copy allowlisted application source files only
COPY --chown=hadron:hadron pyproject.toml ./
COPY --chown=hadron:hadron backend/ ./backend/
COPY --chown=hadron:hadron scripts/ ./scripts/

USER hadron

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health/live || exit 1

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["api"]
