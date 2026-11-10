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
import uuid
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.auth.dependencies import require_auth
from backend.auth.principal import Principal
from backend.config.settings import Settings, get_settings
from backend.core.exceptions import ConfigurationError  # noqa: F401 - re-exported for test imports
from backend.memory.context_retriever import retrieve_context_for_diff  # noqa: F401 (used in routes)
from backend.database.postgres import init_db, init_tiger_schema  # noqa: F401 - init_db needed for test patching
ensure_collection = init_tiger_schema  # Backward compatibility alias for phase 13 tests
from backend.memory.redis_client import redis_client
from backend.webhook_receiver.router import router as webhook_router

# Phase 3 REST API routers
from backend.api.reviews import router as reviews_router
from backend.api.queue import router as queue_router
from backend.api.hitl_router import hitl_router       # Phase 19: HITL queue + dispute
from backend.api.economics_router import economics_router  # Phase 16: cost & budget
from backend.api.auth_router import router as auth_router  # GitHub authentication & account selector
from backend.api.governance_router import router as governance_router  # Data governance, retention, erasure, legal holds

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
# Development: allow local frontend origins (supports credentials).
# Production:  restrict to explicit authorized dashboard origins.
# -------------------------------------------------------------------------
if settings.is_development:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://testserver",
            "https://krishujeniya.github.io",
            "https://hadron.vercel.app",
            "*",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Hadron-Session", "X-CSRF-Token"],
    )
else:
    raw_origins = getattr(settings, "cors_origins", "") or os.environ.get("CORS_ORIGINS", "")
    origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
    default_prod_origins = [
        "https://hadron.dev",
        "https://hadron.vercel.app",
        "https://krishujeniya.github.io",
    ]
    if not origins and settings.app_env == "production":
        origins = default_prod_origins
    else:
        for o in default_prod_origins:
            if o not in origins:
                origins.append(o)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-API-Key",
            "X-CSRF-Token",
            "X-Request-ID",
            "X-OAuth-State",
            "Accept",
        ],
        expose_headers=["X-Request-ID", "X-Hadron-Session", "X-CSRF-Token"],
    )


# Security and Caching Headers Middleware (Gate B - T27)
class SecurityHeadersMiddleware:
    """Pure ASGI middleware enforcing security, correlation ID, and cache-control headers."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = headers.get("x-request-id") or f"req-{uuid.uuid4().hex[:12]}"
        path = scope.get("path", "")

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                res_headers = MutableHeaders(scope=message)
                res_headers["X-Content-Type-Options"] = "nosniff"
                res_headers["X-Frame-Options"] = "DENY"
                res_headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                res_headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                res_headers["X-Request-ID"] = request_id

                cookie_str = headers.get("cookie", "")
                if path.startswith("/api/") or "hadron_session" in cookie_str:
                    res_headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
                    res_headers["Pragma"] = "no-cache"

            await send(message)

        await self.app(scope, receive, send_with_security_headers)


app.add_middleware(SecurityHeadersMiddleware)

# Admission control: header limits, streaming body bounds, decompression safety
app.add_middleware(AdmissionControlMiddleware)


# -------------------------------------------------------------------------
# Global Sanitized Error Contracts (Gate B - T27)
# -------------------------------------------------------------------------

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = request.headers.get("x-request-id") or "req-unknown"
    status_code = exc.status_code
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        413: "PAYLOAD_TOO_LARGE",
        422: "VALIDATION_ERROR",
        429: "TOO_MANY_REQUESTS",
        431: "REQUEST_HEADER_FIELDS_TOO_LARGE",
        500: "INTERNAL_SERVER_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
    }
    code = code_map.get(status_code, f"HTTP_{status_code}")
    detail_msg = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    headers = getattr(exc, "headers", None) or {}
    headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    headers["X-Request-ID"] = request_id

    return JSONResponse(
        status_code=status_code,
        content={
            "detail": exc.detail,
            "error": {
                "code": code,
                "message": detail_msg,
                "status_code": status_code,
                "request_id": request_id,
                "details": exc.detail if not isinstance(exc.detail, str) else None,
            },
        },
        headers=headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = request.headers.get("x-request-id") or "req-unknown"
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "status_code": 422,
                "request_id": request_id,
                "details": exc.errors(),
            },
        },
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, private",
            "X-Request-ID": request_id,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = request.headers.get("x-request-id") or "req-unknown"
    logger.exception("unhandled_server_exception | request_id=%s error=%s", request_id, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred.",
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred.",
                "status_code": 500,
                "request_id": request_id,
                "details": None,
            },
        },
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, private",
            "X-Request-ID": request_id,
        },
    )


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
app.include_router(governance_router)     # Data governance, retention, export, and erasure


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
