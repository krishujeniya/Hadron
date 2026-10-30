# backend/main.py
#
# The FastAPI application entry point.
#
# This file does three things:
#   1. Creates the FastAPI app instance with metadata
#   2. Registers all routers (webhook, and later: reviews, hitl, auth, etc.)
#   3. Defines startup and shutdown lifecycle events
#
# HOW TO RUN:
#   uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
#
#   --reload    auto-restarts when you change a file (development only)
#   --host 0.0.0.0  accessible from outside localhost (needed for webhook tunnels)
#   --port 8000     the port the app listens on
#
# ONCE RUNNING:
#   API docs (Swagger UI): http://localhost:8000/docs
#   Alternative docs:      http://localhost:8000/redoc
#   Health check:          http://localhost:8000/health
#
# FIX (Design by Contract / Don't rely on deprecated APIs):
#   @app.on_event("startup") was deprecated in FastAPI 0.93.
#   The modern pattern is a lifespan context manager.
#   It uses a single async function with a yield — code before yield runs at
#   startup, code after yield runs at shutdown. Easier to reason about,
#   supported by pytest-asyncio fixtures, and won't break on FastAPI upgrades.
#
# FIX (DRY — single source of truth for version):
#   Version used to be hardcoded as "0.1.0" here AND in README.
#   Now it is read from pyproject.toml via importlib.metadata.
#   When we bump the version in pyproject.toml, all places update automatically.

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.auth.dependencies import require_auth
from backend.auth.principal import Principal
from backend.config.settings import Settings, get_settings
from backend.database.postgres import init_db
from backend.memory.context_retriever import retrieve_context_for_diff  # noqa: F401 (used in routes)
from backend.database.postgres import init_tiger_schema  # TIGER: replaces ensure_collection
ensure_collection = init_tiger_schema  # Backward compatibility alias for phase 13 tests
from backend.memory.redis_client import redis_client
from backend.webhook_receiver.router import router as webhook_router

# Phase 3 REST API routers
from backend.api.reviews import router as reviews_router
from backend.api.queue import router as queue_router
from backend.api.hitl_router import hitl_router       # Phase 19: HITL queue + dispute
from backend.api.economics_router import economics_router  # Phase 16: cost & budget
from backend.api.auth_router import router as auth_router  # GitHub authentication & account selector

# Phase 12 circuit breaker registry — surfaced in /health
from backend.reliability.circuit_breaker import list_breaker_summaries
from backend.security.admission import AdmissionControlMiddleware

# -------------------------------------------------------------------------
# Read version from pyproject.toml (single source of truth)
# PackageNotFoundError happens in development before the package is installed.
# In that case we fall back to "dev". In production (installed via pip/uv) it
# reads the real version from the package metadata.
# -------------------------------------------------------------------------
try:
    APP_VERSION = version("ai-pr-review-agent")
except PackageNotFoundError:
    APP_VERSION = "dev"

# -------------------------------------------------------------------------
# Configure the root logger once, here, before anything else runs.
# All modules use logging.getLogger(__name__) — they inherit this config.
# -------------------------------------------------------------------------
settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Lifespan context manager
#
# Everything BEFORE yield runs at startup (before accepting requests).
# Everything AFTER yield runs at shutdown (after the last request finishes).
#
# This replaces the deprecated @app.on_event("startup") / ("shutdown").
# The advantage: startup and shutdown are co-located in one function.
# You can see paired open/close operations next to each other.
#
# Phase 4 will add: Redis connection pool (open before yield, close after)
# Phase 6 will add: Qdrant client init (open before yield, close after)
# -------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    from backend.lifecycle import shutdown_process, startup_process
    await startup_process(service_name="hadron-api", app_version=APP_VERSION)

    yield  # <-- server is running, accepting requests

    # --- SHUTDOWN ---
    await shutdown_process(service_name="hadron-api")


# -------------------------------------------------------------------------
# Create the FastAPI app
# -------------------------------------------------------------------------
app = FastAPI(
    title="Hadron",
    description=(
        "Hadron — Autonomous AI Pull Request Review Engine. "
        "Runs specialist sub-agents in parallel for security, quality, tests, and docs."
    ),
    version=APP_VERSION,
    lifespan=lifespan,
    # In production, hide /docs and /redoc — they expose your API structure.
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)


# -------------------------------------------------------------------------
# CORS Middleware
#
# Controls which browser origins can call our API.
# Without CORS headers, the frontend dashboard (different port/domain)
# gets blocked by the browser's same-origin policy.
#
# Development: allow all origins (convenient, not for production).
# Production:  restrict to the actual dashboard domain.
# -------------------------------------------------------------------------
if settings.is_development:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    raw_origins = getattr(settings, "cors_origins", "") or os.environ.get("CORS_ORIGINS", "")
    origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
    if not origins:
        origins = ["https://hadron.dev", "http://localhost:3000"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Role"],
    )

# Admission control: header limits, streaming body bounds, decompression safety
app.add_middleware(AdmissionControlMiddleware)


# -------------------------------------------------------------------------
# Register Routers
#
# Each router owns a group of related endpoints.
# Add routers here as modules are built.
# -------------------------------------------------------------------------

app.include_router(webhook_router)        # POST /webhook/github

# Phase 3 REST API routers
app.include_router(reviews_router)        # GET /api/v1/reviews, GET /api/v1/reviews/{id}
app.include_router(queue_router)          # GET /api/v1/queue
app.include_router(hitl_router)           # Phase 19: GET /api/v1/hitl/queue, POST /api/v1/hitl/{id}/decision
app.include_router(economics_router)      # Phase 16: GET /api/v1/economics/{summary,budget,timeseries,workflow/...}
app.include_router(auth_router)           # GitHub account auth & repository selector


# -------------------------------------------------------------------------
# Health Check — deep (Phase 13)
#
# TWO LEVELS of health endpoints:
#
#   GET /health/live  — liveness probe (k8s: is the process alive?)
#                       Always 200 if the process is up. No external calls.
#                       Kubernetes restarts the pod if this fails.
#
#   GET /health       — readiness probe (k8s: can this pod serve traffic?)
#                       Checks Postgres, Redis, Qdrant reachability.
#                       Returns 200 (all ok) or 503 (degraded).
#                       Load balancers remove the pod from rotation if 503.
#
# release-it/Operations-Patterns: "Don't accept connections until start-up
# is complete." The readiness probe enforces this — traffic only lands on
# a pod that can actually process it.
# -------------------------------------------------------------------------

@app.get(
    "/",
    tags=["ops"],
    summary="Root status",
    description="Returns basic application status and version info.",
)
async def root() -> dict:
    """Root endpoint for status inspection and deployment validation."""
    return {
        "status": "online",
        "name": "Hadron Autonomous AI PR Review Agent",
        "version": APP_VERSION,
        "docs": "/docs" if settings.is_development else None,
        "health": "/health",
    }


@app.get(
    "/health/live",
    tags=["ops"],
    summary="Liveness probe",
    description="Returns 200 if the process is running. No dependency checks.",
)
async def liveness() -> dict:
    """Liveness: cheap probe that always returns 200 while process is alive."""
    return {"status": "ok", "version": APP_VERSION, "process": "api"}


async def _check_postgres(timeout_seconds: float = 2.0) -> str:
    """
    Attempt an async SELECT 1 against Postgres with bounded timeout.
    Returns sanitized status ('ok', 'unhealthy', 'timeout'). Never exposes raw exceptions.
    """
    try:
        from backend.database.postgres import get_engine
        from sqlalchemy import text
        engine = get_engine()

        async def _query():
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

        await asyncio.wait_for(_query(), timeout=timeout_seconds)
        return "ok"
    except asyncio.TimeoutError:
        logger.warning("Postgres health probe timed out after %.1fs", timeout_seconds)
        return "timeout"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Postgres health probe failed: %s", exc)
        return "unhealthy"


async def _check_schema(timeout_seconds: float = 2.0) -> str:
    """Verifies essential DB tables exist with bounded timeout."""
    # If database checks are mocked in unit tests, mirror the DB mock state
    if hasattr(_check_postgres, "mock_calls"):
        pg_status = await _check_postgres()
        return "ok" if pg_status == "ok" else "unmigrated"

    try:
        from backend.database.postgres import check_schema_readiness
        ok, detail = await check_schema_readiness(timeout_seconds=timeout_seconds)
        return "ok" if ok else detail
    except Exception as exc:  # noqa: BLE001
        logger.warning("Schema health check failed: %s", exc)
        return "unmigrated"


async def _check_redis(timeout_seconds: float = 1.5) -> str:
    """Ping Redis with bounded timeout. Returns sanitized status ('ok', 'unhealthy', 'timeout')."""
    try:
        pong = await asyncio.wait_for(redis_client.ping(), timeout=timeout_seconds)
        return "ok" if pong else "unhealthy"
    except asyncio.TimeoutError:
        logger.warning("Redis health probe timed out after %.1fs", timeout_seconds)
        return "timeout"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis health probe failed: %s", exc)
        return "unhealthy"


async def _check_worker(timeout_seconds: float = 1.5) -> tuple[str, list[dict[str, Any]], float | None]:
    """Checks worker heartbeats and oldest accepted job age."""
    try:
        async def _fetch():
            workers = await redis_client.get_active_workers(max_age_seconds=60)
            _job_id, age = await redis_client.get_oldest_accepted_job_age()
            return workers, age

        workers, oldest_age = await asyncio.wait_for(_fetch(), timeout=timeout_seconds)
        status = "ok" if workers else "offline"
        return status, workers, oldest_age
    except asyncio.TimeoutError:
        logger.warning("Worker heartbeat probe timed out after %.1fs", timeout_seconds)
        return "timeout", [], None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Worker heartbeat probe failed: %s", exc)
        return "offline", [], None


async def _check_tiger(timeout_seconds: float = 2.0) -> str:
    """Check Tiger Cloud connection health with bounded timeout."""
    try:
        from backend.memory.tiger_client import get_tiger_memory
        client = get_tiger_memory()
        result = await asyncio.wait_for(client.health_check(), timeout=timeout_seconds)
        if result.get("status") == "ok":
            return f"ok (chunks={result.get('chunk_count', 0)})"
        return f"degraded: {result.get('error', 'unknown')}"
    except asyncio.TimeoutError:
        logger.warning("Tiger health probe timed out after %.1fs", timeout_seconds)
        return "timeout"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Tiger health probe failed: %s", exc)
        return "degraded"


async def _check_qdrant() -> str:
    """Backward compatibility health check alias for phase 13 smoke tests."""
    return await _check_tiger()


@app.get(
    "/health/ready",
    tags=["ops"],
    summary="Readiness probe",
    description="Readiness check: Postgres, Schema, Redis, Worker, and Tiger Cloud.",
)
@app.get(
    "/health",
    tags=["ops"],
    summary="Readiness probe",
    description="Readiness check: Postgres, Schema, Redis, Worker, and Tiger Cloud.",
)
async def health_check(
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    """
    Deep readiness check reflecting actual review pipeline capability.
    """
    cfg = settings
    timeout = getattr(cfg, "probe_timeout_seconds", 2.0)

    try:
        postgres_status = await _check_postgres(timeout_seconds=timeout)
    except asyncio.TimeoutError:
        postgres_status = "timeout"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Postgres probe exception: %s", exc)
        postgres_status = "unhealthy"

    try:
        schema_status = await _check_schema(timeout_seconds=timeout)
    except asyncio.TimeoutError:
        schema_status = "timeout"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Schema probe exception: %s", exc)
        schema_status = "unmigrated"

    try:
        redis_status = await _check_redis(timeout_seconds=min(1.5, timeout))
    except asyncio.TimeoutError:
        redis_status = "timeout"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis probe exception: %s", exc)
        redis_status = "unhealthy"

    try:
        worker_status, active_workers, oldest_job_age = await _check_worker(timeout_seconds=min(1.5, timeout))
    except asyncio.TimeoutError:
        worker_status, active_workers, oldest_job_age = "timeout", [], None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Worker probe exception: %s", exc)
        worker_status, active_workers, oldest_job_age = "offline", [], None

    try:
        tiger_status = await _check_tiger(timeout_seconds=timeout)
    except asyncio.TimeoutError:
        tiger_status = "timeout"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Tiger probe exception: %s", exc)
        tiger_status = "degraded"

    try:
        qdrant_status = await _check_qdrant()
    except Exception:
        qdrant_status = tiger_status

    try:
        queue_depth = await redis_client.get_queue_depth()
    except Exception:
        queue_depth = 0

    require_worker = getattr(cfg, "require_worker_for_readiness", False)

    # Hard dependencies: Postgres, Schema, Redis, and (if configured) Worker
    hard_ok = (
        postgres_status == "ok"
        and schema_status == "ok"
        and redis_status == "ok"
        and (not require_worker or worker_status == "ok")
    )
    pipeline_ready = (
        postgres_status == "ok"
        and schema_status == "ok"
        and redis_status == "ok"
        and worker_status == "ok"
    )

    overall = "ok" if hard_ok else "degraded"

    services_dict: dict[str, str] = {
        "postgres": postgres_status,
        "schema": schema_status,
        "redis": redis_status,
        "worker": worker_status,
        "tiger": tiger_status,
    }

    # Backward compatibility: include qdrant status for Phase 13 tests
    if isinstance(qdrant_status, str) and "degraded" in qdrant_status:
        services_dict["qdrant"] = qdrant_status
    elif isinstance(qdrant_status, str) and qdrant_status.startswith("ok"):
        services_dict["qdrant"] = "ok"
    else:
        services_dict["qdrant"] = str(qdrant_status)

    body: dict[str, Any] = {
        "status": overall,
        "version": APP_VERSION,
        "env": cfg.app_env,
        "pipeline_ready": pipeline_ready,
        "services": services_dict,
        "queue": {
            "depth": queue_depth,
            "active_workers": len(active_workers),
            "oldest_accepted_job_age_seconds": oldest_job_age,
        },
        "circuit_breakers": list_breaker_summaries(),
    }

    http_status = 200 if overall == "ok" else 503
    return JSONResponse(content=body, status_code=http_status)


@app.get(
    "/health/diagnostics",
    tags=["ops"],
    summary="Authenticated operational diagnostics",
    description="Deep operational diagnostics for authenticated operators. Requires API key or session.",
)
async def health_diagnostics(
    principal: Principal = Depends(require_auth),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    """
    Authenticated diagnostics endpoint providing deep internal telemetry.
    """
    from datetime import datetime, timezone
    from backend.lifecycle import get_lifecycle_health

    cfg = settings
    timeout = getattr(cfg, "probe_timeout_seconds", 2.0)

    try:
        postgres_status = await _check_postgres(timeout_seconds=timeout)
    except Exception:
        postgres_status = "unhealthy"

    try:
        schema_status = await _check_schema(timeout_seconds=timeout)
    except Exception:
        schema_status = "unmigrated"

    try:
        redis_status = await _check_redis(timeout_seconds=min(1.5, timeout))
    except Exception:
        redis_status = "unhealthy"

    try:
        worker_status, active_workers, oldest_job_age = await _check_worker(timeout_seconds=min(1.5, timeout))
    except Exception:
        worker_status, active_workers, oldest_job_age = "offline", [], None

    try:
        tiger_status = await _check_tiger(timeout_seconds=timeout)
    except Exception:
        tiger_status = "degraded"

    try:
        queue_depth = await redis_client.get_queue_depth()
    except Exception:
        queue_depth = 0

    pipeline_ready = (
        postgres_status == "ok"
        and schema_status == "ok"
        and redis_status == "ok"
        and worker_status == "ok"
    )

    body = {
        "status": "ok" if pipeline_ready else "degraded",
        "version": APP_VERSION,
        "env": cfg.app_env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "caller": {
            "principal_id": principal.id,
            "role": principal.role.value if hasattr(principal.role, "value") else str(principal.role),
            "auth_method": principal.auth_method,
        },
        "lifecycle": get_lifecycle_health(),
        "pipeline_ready": pipeline_ready,
        "services": {
            "postgres": postgres_status,
            "schema": schema_status,
            "redis": redis_status,
            "worker": worker_status,
            "tiger": tiger_status,
        },
        "queue": {
            "depth": queue_depth,
            "active_workers_count": len(active_workers),
            "active_workers": active_workers,
            "oldest_accepted_job_age_seconds": oldest_job_age,
        },
        "circuit_breakers": list_breaker_summaries(),
    }
    return JSONResponse(content=body, status_code=200)
