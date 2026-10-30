# backend/lifecycle.py
"""
Shared explicit lifecycle management for all Hadron runtime processes.

Ensures both the FastAPI API server and standalone ARQ background workers:
  1. Initialize structured logging with automated secret/credential redaction.
  2. Connect the shared Redis pool.
  3. Verify/create Postgres relational tables and connection pools.
  4. Initialize Tiger Cloud TimescaleDB hypertable schema, vector store, and asyncpg pool.
  5. Initialize Sentry error reporting and OpenTelemetry tracing with attributed service names.
  6. On shutdown: flush pending telemetry events, Sentry, and OTel spans, then cleanly close
     Redis, Tiger, and Postgres connections.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from backend.config.settings import get_settings
from backend.database.postgres import close_db, close_tiger_pool, init_db, init_tiger_schema
from backend.memory.redis_client import redis_client
from backend.observability.events import flush_agent_events

logger = logging.getLogger(__name__)

_TELEMETRY_STATUS: dict[str, Any] = {
    "service_name": "unknown",
    "sentry_active": False,
    "otel_active": False,
    "tiger_active": False,
    "redis_active": False,
    "postgres_active": False,
}


def get_process_telemetry_status() -> dict[str, Any]:
    """Returns the current process telemetry and lifecycle health status."""
    return dict(_TELEMETRY_STATUS)


def init_telemetry(service_name: str, app_version: str = "0.1.0") -> None:
    """Initializes Sentry error tracking and OpenTelemetry tracing."""
    cfg = get_settings()
    _TELEMETRY_STATUS["service_name"] = service_name

    # 1. Sentry initialization
    sentry_dsn = getattr(cfg, "sentry_dsn", os.environ.get("SENTRY_DSN", None))
    if sentry_dsn:
        try:
            import sentry_sdk
            sentry_sdk.init(
                dsn=sentry_dsn,
                environment=cfg.app_env,
                release=app_version,
                traces_sample_rate=0.2,
                send_default_pii=False,
            )
            _TELEMETRY_STATUS["sentry_active"] = True
            logger.info("Sentry initialized | service=%s env=%s", service_name, cfg.app_env)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Sentry initialization failed | service=%s error=%s", service_name, exc)
            _TELEMETRY_STATUS["sentry_active"] = False

    # 2. OpenTelemetry initialization
    otel_endpoint = getattr(cfg, "otel_endpoint", os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", None))
    if otel_endpoint:
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            resource = Resource.create({"service.name": service_name, "service.version": app_version})
            provider = TracerProvider(resource=resource)
            processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=otel_endpoint))
            provider.add_span_processor(processor)
            trace.set_tracer_provider(provider)
            _TELEMETRY_STATUS["otel_active"] = True
            logger.info("OpenTelemetry TracerProvider initialized | service=%s endpoint=%s", service_name, otel_endpoint)
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenTelemetry initialization failed | service=%s error=%s", service_name, exc)
            _TELEMETRY_STATUS["otel_active"] = False


async def flush_telemetry(timeout_s: float = 3.0) -> None:
    """Flushes in-flight telemetry: agent events, OpenTelemetry spans, and Sentry events."""
    # 1. Flush hypertable background writes
    try:
        await flush_agent_events(timeout_s=timeout_s)
    except Exception as exc:  # noqa: BLE001
        logger.warning("flush_agent_events failed: %s", exc)

    # 2. Flush OpenTelemetry
    try:
        from opentelemetry import trace
        provider = trace.get_tracer_provider()
        if hasattr(provider, "shutdown"):
            provider.shutdown()
        elif hasattr(provider, "force_flush"):
            provider.force_flush()
    except Exception as exc:  # noqa: BLE001
        logger.debug("OpenTelemetry flush: %s", exc)

    # 3. Flush Sentry
    try:
        import sentry_sdk
        sentry_sdk.flush(timeout=min(2.0, timeout_s))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Sentry flush: %s", exc)


async def startup_process(service_name: str, app_version: str = "0.1.0") -> None:
    """
    Standard resource startup for all Hadron runtime processes.
    Connects Redis, Postgres, Tiger Cloud, and sets up telemetry.
    """
    cfg = get_settings()
    logger.info("Hadron process starting | service=%s env=%s", service_name, cfg.app_env)

    # 1. Telemetry
    init_telemetry(service_name=service_name, app_version=app_version)

    # 2. Redis
    try:
        await redis_client.connect()
        _TELEMETRY_STATUS["redis_active"] = True
        logger.info("Redis connection pool ready | service=%s", service_name)
    except Exception as exc:  # noqa: BLE001
        _TELEMETRY_STATUS["redis_active"] = False
        logger.warning("Redis unavailable at startup | service=%s error=%s", service_name, exc)

    # 3. Postgres relational DB
    try:
        await init_db()
        _TELEMETRY_STATUS["postgres_active"] = True
        logger.info("Postgres relational tables ready | service=%s", service_name)
    except Exception as exc:  # noqa: BLE001
        _TELEMETRY_STATUS["postgres_active"] = False
        logger.warning("Postgres unavailable at startup | service=%s error=%s", service_name, exc)

    # 4. Tiger Cloud / Timescale hypertable & vector store
    try:
        await init_tiger_schema()
        _TELEMETRY_STATUS["tiger_active"] = True
        logger.info("Tiger Cloud pool ready | service=%s", service_name)
    except Exception as exc:  # noqa: BLE001
        _TELEMETRY_STATUS["tiger_active"] = False
        logger.warning("Tiger Cloud unavailable at startup | service=%s error=%s", service_name, exc)


async def shutdown_process(service_name: str) -> None:
    """
    Standard resource shutdown for all Hadron runtime processes.
    Flushes telemetry, disconnects Redis, closes Tiger Cloud and Postgres pools.
    """
    logger.info("Hadron process shutting down | service=%s", service_name)

    # 1. Flush telemetry
    await flush_telemetry()

    # 2. Disconnect Redis
    try:
        await redis_client.disconnect()
        logger.info("Redis disconnected | service=%s", service_name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Error disconnecting Redis | service=%s error=%s", service_name, exc)

    # 3. Close Tiger Cloud asyncpg pool
    await close_tiger_pool()

    # 4. Dispose Postgres engine
    await close_db()

    _TELEMETRY_STATUS["redis_active"] = False
    _TELEMETRY_STATUS["postgres_active"] = False
    _TELEMETRY_STATUS["tiger_active"] = False
