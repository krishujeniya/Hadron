# backend/database/postgres.py
#
# Async SQLAlchemy engine, session factory, and dependency injection.
#
# WHY ASYNC SQLALCHEMY?
# (From Storage-Engines.md wiki, "Async Database Patterns"):
#   "Synchronous sessions block the event loop — every DB query pauses ALL
#    incoming requests until it completes. In an async framework like FastAPI,
#    this means one slow query can stall the entire server."
#   Solution: create_async_engine() + AsyncSession. Every DB call becomes a
#   coroutine that yields control while waiting for I/O.
#
# CONNECTION POOL DESIGN:
# (From Storage-Engines.md wiki, "Connection Pooling"):
#   "Pool exhaustion under load is a common failure mode. Size the pool to
#    match your expected concurrency, then add max_overflow as a safety valve."
#   pool_size=5:      5 persistent connections always open, ready to serve
#   max_overflow=10:  up to 10 extra connections allowed under burst load
#   pool_timeout=30:  wait up to 30s for a connection before raising an error
#   pool_recycle=1800: recycle connections every 30 min (avoids stale TCP issue
#                      where DB has closed a connection the pool thinks is alive)
#
# SESSION FACTORY PATTERN:
# (From Orthogonality.md, Pragmatic Programmer wiki):
#   "Eliminate the effects between unrelated things."
#   Each request gets its own session. Sessions do not cross request boundaries.
#   expire_on_commit=False: prevents SQLAlchemy from invalidating ORM objects
#   after commit. Without this, accessing obj.field after commit raises
#   MissingGreenlet because SQLAlchemy tries to lazy-load in an async context.
#
# get_db() DEPENDENCY:
# (From Design-by-Contract.md wiki):
#   "The session is opened before yield, closed after — guaranteed."
#   FastAPI's dependency injection calls get_db() as an async generator.
#   yield gives the session to the route handler.
#   The finally block ensures the session is always closed, even on exception.
#   This is the contract: every caller gets a clean session, and it is always
#   returned to the pool when done.

import logging
import os
import pathlib
import re

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ORM Base class
#
# All ORM models in database/models.py inherit from this Base.
# SQLAlchemy uses it to track the metadata (table names, columns, indexes)
# needed for create_all() / migrate operations.
#
# WHY MODULE-LEVEL BASE AND NOT IN models.py?
# postgres.py is the "engine room". models.py is the "schema room".
# If Base lived in models.py, postgres.py would import from models.py,
# creating a circular dependency: postgres.py <- models.py <- postgres.py.
# By defining Base here and having models.py import it from postgres.py,
# the dependency flows in one direction only.
# (Orthogonality principle: no circular imports.)
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.

    Inheriting from DeclarativeBase (SQLAlchemy 2.0 style) gives each model
    class a __tablename__, column definitions, and automatic metadata tracking.
    """
    pass


# ---------------------------------------------------------------------------
# Engine and session factory (module-level, created once)
#
# WHY MODULE-LEVEL?
# The engine is expensive to create (sets up connection pool, reads settings).
# We create it once when this module is first imported and reuse it for the
# lifetime of the process. This is safe because SQLAlchemy engines are
# thread-safe and coroutine-safe.
#
# LAZY INITIALIZATION:
# We call get_settings() here at module load time. This is acceptable because
# postgres.py is only imported by main.py (lifespan) and repository.py —
# never imported speculatively at startup before settings are configured.
# ---------------------------------------------------------------------------

class MigrationError(Exception):
    """Raised when an essential database migration fails."""
    pass


def _build_ssl_context(dsn: str):
    """
    Builds a secure SSLContext verifying server certificates and hostname.
    Loads system default CAs plus any custom CA bundle from POSTGRES_CA_CERT.
    """
    if not any(h in dsn for h in ("supabase.co", "pooler.supabase.com", "sslmode=require")):
        return None

    import ssl
    ctx = ssl.create_default_context()
    ca_file = os.getenv("POSTGRES_CA_CERT") or os.getenv("SSL_CERT_FILE")
    if ca_file and pathlib.Path(ca_file).exists():
        ctx.load_verify_locations(cafile=ca_file)

    # Insecure bypass allowed ONLY when explicitly configured by operator
    if os.getenv("POSTGRES_INSECURE_DISABLE_TLS_VERIFY", "").lower() in ("true", "1"):
        logger.warning(
            "INSECURE TLS: Server certificate verification explicitly disabled via "
            "POSTGRES_INSECURE_DISABLE_TLS_VERIFY!"
        )
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    else:
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED

    return ctx


def parse_sql_script(sql: str) -> list[str]:
    """
    Parses a SQL script into individual executable statements.
    Properly strips comments (-- and /* */) without dropping statements.
    """
    # Remove block comments /* ... */
    cleaned = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    # Remove single line comments
    lines = []
    for line in cleaned.splitlines():
        line_no_comment = re.sub(r"--.*$", "", line).strip()
        if line_no_comment:
            lines.append(line_no_comment)
    cleaned_sql = "\n".join(lines)
    # Split on semicolons
    raw_statements = cleaned_sql.split(";")
    return [s.strip() for s in raw_statements if s.strip()]


def _build_engine():
    """
    Builds the async SQLAlchemy engine from current settings.

    Separated into a function (rather than module-level statements) so that
    tests can import postgres.py without needing a real DATABASE_URL in the
    environment — as long as they don't call this function, no engine is made.

    For tests: SQLite in-memory URL works:
        "sqlite+aiosqlite:////:memory:"
    For production: PostgreSQL async URL:
        "postgresql+asyncpg://user:pass@host:5432/dbname"
    """
    cfg = get_settings()
    db_url = cfg.database_url

    # Normalize standard postgres connection strings to asyncpg driver
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # SQLite connection handling
    if "sqlite" in db_url.lower():
        from sqlalchemy.pool import StaticPool
        return create_async_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )

    connect_args = {}
    ssl_ctx = _build_ssl_context(db_url)
    if ssl_ctx is not None:
        connect_args["ssl"] = ssl_ctx

    is_serverless = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
    pool_size = 1 if is_serverless else 5
    max_overflow = 2 if is_serverless else 10

    engine = create_async_engine(
        db_url,
        connect_args=connect_args,
        pool_size=pool_size,
        max_overflow=max_overflow,

        # pool_timeout=30: wait up to 30s for a free connection.
        # Prevents requests piling up forever if the DB is overwhelmed.
        pool_timeout=30,

        # pool_recycle=1800: discard and recreate connections every 30 minutes.
        # Prevents "connection reset" errors from DB-side TCP keepalive timeouts.
        # (From Production-Hardening.md wiki: "stale connections cause silent failures")
        pool_recycle=1800,

        # pool_pre_ping=True: before handing a connection from the pool, issue
        # a "SELECT 1" ping. If the connection is dead (Neon closed it after
        # idle timeout), SQLAlchemy discards it and opens a fresh one.
        # WHY: Neon serverless Postgres aggressively closes idle connections.
        # Without pre_ping, the worker gets an InterfaceError("connection is closed")
        # on the first query after idle — exactly the error seen in Phase 14 demo.
        # Cost: one extra round-trip per acquired connection, negligible vs LLM latency.
        pool_pre_ping=True,

        # echo=False in production. echo=True would print every SQL statement
        # to logs — useful for debugging but too noisy for production.
        echo=False,
    )

    logger.info(
        "PostgreSQL async engine created | url=%s pool_size=%d max_overflow=%d",
        # Never log the full URL — it contains the password.
        cfg.database_url.split("@")[-1] if "@" in cfg.database_url else "sqlite://...",
        5,
        10,
    )

    return engine


# The module-level engine instance.
# LAZY: Initialized to None; built on first call to get_engine() or init_db().
# This ensures importing postgres.py never calls get_settings() at import time,
# which would require env vars to be set even in test environments that override
# DATABASE_URL via a custom engine.
# (Pragmatic Programmer wiki, "Decoupling": "don't build side effects into imports.")
_engine = None


def get_engine():
    """
    Returns the module-level async engine, building it if needed (lazy init).

    Tests that want to use a custom engine (e.g. SQLite in-memory) should
    build their own engine directly — they do NOT call this function.
    This function is used by the session factory and init_db() in production.
    """
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


# ---------------------------------------------------------------------------
# Async session factory
#
# async_sessionmaker is the SQLAlchemy 2.0 way to create sessions.
# It is a factory: each call produces a new AsyncSession bound to our engine.
#
# expire_on_commit=False:
#   After session.commit(), SQLAlchemy normally marks all loaded ORM objects
#   as "expired" so it can lazy-reload them on next access. In async code,
#   this lazy-reload would try to run a SQL query outside an async context,
#   which raises a MissingGreenlet error.
#   Solution: disable expiration on commit. The object keeps its values.
#   If we need fresh data after commit, we explicitly call session.refresh(obj).
# ---------------------------------------------------------------------------
AsyncSessionLocal = async_sessionmaker(
    # get_engine() is called LAZILY here — but async_sessionmaker(bind=...) evaluates
    # the bind argument at module-level when Python parses this line.
    # To prevent import-time settings loading, we use a placeholder and rebuild
    # the factory on first call to get_db(). The factory itself is cheap to create.
    # See get_db() below which rebuilds the session if _engine is None.
    bind=None,   # will be set on first get_db() call (lazy)
    class_=AsyncSession,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# FastAPI dependency: get_db()
#
# Usage in route handlers:
#   from backend.database.postgres import AsyncSession, get_db
#   from fastapi import Depends
#
#   @router.get("/reviews/{review_id}")
#   async def get_review(
#       review_id: str,
#       db: AsyncSession = Depends(get_db),
#   ):
#       return await repository.get_review(db, review_id)
#
# The session is automatically closed when the request finishes.
# Even if the handler raises an exception, the finally block closes it.
# ---------------------------------------------------------------------------
async def get_db():
    """
    FastAPI dependency that yields a database session per request.

    LAZY INIT: The first call builds the real session factory bound to the
    actual engine (which reads DATABASE_URL from settings at that point).
    This ensures postgres.py can be imported without env vars present
    (needed for smoke tests that build their own engine independently).

    Follows the Design-by-Contract principle:
      Precondition:  DATABASE_URL is set in environment (checked at engine build)
      Postcondition: session is always closed, even on exception
      Invariant:     one session per request, never shared between requests
    """
    # Build the real session factory bound to the production engine (lazy).
    # In tests, callers build their own async_sessionmaker with a test engine.
    factory = async_sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )
    session: AsyncSession = factory()
    try:
        yield session
    finally:
        await session.close()


# ---------------------------------------------------------------------------
# create_all_tables()
#
# Called once at application startup (from main.py lifespan).
# Creates all tables that don't exist yet.
#
# THIS IS FOR DEV/TEST ONLY.
# Production uses Alembic migrations (Phase 15 TODO).
# (From Pragmatic Programmer wiki, Estimation.md:
#  "Don't ship what isn't ready. Note TODO items honestly.")
# create_all() is idempotent: running it twice does not drop existing tables.
# It only creates tables that are missing.
# ---------------------------------------------------------------------------
async def create_all_tables() -> None:
    """
    Creates all ORM-defined tables in the database.

    IMPORTANT: This imports backend.database.models to register ORM classes
    with Base.metadata. Without that import, Base.metadata is empty and
    create_all() does nothing.

    Called from: main.py lifespan(), before yielding.
    Safe to call in tests with SQLite in-memory.

    PRODUCTION NOTE (TODO — Phase 15 Alembic):
    create_all() is fine for dev and testing but NOT for production schema
    management. In production, use Alembic migrations so that schema changes
    are versioned, reversible, and auditable. This TODO is explicit technical
    debt, not a broken window — it is logged here for traceability.
    (Broken-Window-Theory.md: explicit debt is acceptable; silent drift is not.)
    """
    # Import models here (not at module top) to avoid circular import.
    # This import registers PRReviewRecord and FindingRecord with Base.metadata.
    from backend.database import models as _models  # noqa: F401 — side-effect import

    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created (or already exist.")


# Alias: main.py calls init_db() (clearer name in a startup context)
init_db = create_all_tables


# ---------------------------------------------------------------------------
# get_session_factory()
#
# Returns a bound async_sessionmaker for use OUTSIDE FastAPI request context.
# (i.e. background jobs, worker tasks, batch ingestion pipelines.)
#
# WHY NOT USE get_db() for background work:
#   get_db() is an async generator (yield) — it is a FastAPI Depends() helper.
#   Calling `async with get_db()` raises AttributeError: __aenter__ (Bug #2
#   from demo-day-readiness skill). Background jobs must use this factory directly.
#
# USAGE:
#   factory = get_session_factory()
#   async with factory() as session:
#       await do_something(session)
# ---------------------------------------------------------------------------
def get_session_factory() -> async_sessionmaker:
    """
    Return an async_sessionmaker bound to the production engine.

    For use in background jobs and workers that run outside FastAPI's
    request/response cycle and cannot use get_db() as a Depends().

    Returns:
        async_sessionmaker configured with expire_on_commit=False.
    """
    return async_sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )


# ---------------------------------------------------------------------------
# Tiger Cloud: asyncpg pool + schema init
#
# Tiger Cloud (TimescaleDB) runs alongside the existing SQLAlchemy engine.
# They share the same physical instance (same TIGER_DATABASE_URL) but use
# different drivers:
#   - SQLAlchemy/asyncpg: structured tables (pr_review_records, findings, etc.)
#   - bare asyncpg pool:  hot paths (agent_events inserts, code_chunks upserts)
#
# WHY TWO POOLS?
# SQLAlchemy's ORM session adds ~2ms overhead per row — fine for structured
# queries, too expensive for the 50+ telemetry rows emitted per review.
# The bare asyncpg pool is used only for high-throughput insert paths.
# ---------------------------------------------------------------------------
import asyncpg as _asyncpg
from pgvector.asyncpg import register_vector as _register_vector

_tiger_pool: "_asyncpg.Pool | None" = None


def get_tiger_pool() -> "_asyncpg.Pool | None":
    """
    Returns the module-level Tiger Cloud asyncpg pool.
    None if init_tiger_schema() has not been called yet.
    """
    return _tiger_pool


async def init_tiger_schema() -> None:
    """
    Creates the Tiger Cloud asyncpg pool and runs the full schema DDL.

    Called once at startup from main.py lifespan, after init_db().
    Reads the SQL migration from scripts/migrations/2026-06-tiger-init.sql
    and executes it idempotently (all statements use IF NOT EXISTS).

    The pool is stored at module level (_tiger_pool) and retrieved via
    get_tiger_pool() by any module that needs raw asyncpg access.
    """
    global _tiger_pool
    cfg = get_settings()
    dsn = cfg.tiger_database_url or cfg.database_url

    # Check for SQLite or offline dev fallback
    if not dsn or "sqlite" in dsn.lower():
        logger.info("Tiger Cloud using SQLite in-memory fallback | dsn=%s", dsn)
        from backend.memory.tiger_client import MockAsyncpgPool, TigerMemoryClient
        _tiger_pool = MockAsyncpgPool()
        try:
            from backend.memory import tiger_client as _tc
            if _tc.tiger_memory is None:
                _tc.tiger_memory = TigerMemoryClient(_tiger_pool)
                logger.info("TigerMemoryClient in-memory fallback singleton initialized.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("TigerMemoryClient mock init warning: %s", exc)
        return

    # asyncpg wants plain postgresql:// not postgresql+asyncpg:// (that's SQLAlchemy syntax)
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://").replace("postgres+asyncpg://", "postgresql://")

    # SSL context for Supabase / hosted cloud PostgreSQL
    ssl_arg = _build_ssl_context(dsn)

    # Build the pool with pgvector codec registered on every new connection.
    # We wrap in try/except so pool creation doesn't crash if pgvector isn't installed yet.
    async def _init_conn(conn):
        try:
            await _register_vector(conn)
        except Exception as exc:
            logger.debug("pgvector codec registration deferred: %s", exc)

    is_serverless = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
    _tiger_pool = await _asyncpg.create_pool(
        dsn=dsn,
        ssl=ssl_arg,
        min_size=1 if is_serverless else 2,
        max_size=2 if is_serverless else 10,
        command_timeout=60,
        init=_init_conn,
    )

    # Run the idempotent migration SQL using robust comment-aware parsing.
    migration_path = (
        pathlib.Path(__file__).resolve().parent.parent.parent
        / "scripts" / "migrations" / "2026-06-tiger-init.sql"
    )
    if migration_path.exists():
        sql = migration_path.read_text()
        statements = parse_sql_script(sql)
        async with _tiger_pool.acquire() as conn:
            for stmt in statements:
                try:
                    await conn.execute(stmt)
                except Exception as exc:  # noqa: BLE001
                    is_optional = any(
                        opt in stmt.upper()
                        for opt in ("CREATE EXTENSION", "HYPERTABLE", "CONTINUOUS AGGREGATE", "ADD_JOB")
                    )
                    if is_optional:
                        logger.warning("Tiger migration optional stmt warning (non-fatal): %s", exc)
                    else:
                        logger.error("Tiger migration critical DDL failed: %s | sql=%s", exc, stmt)
                        raise MigrationError(f"Required DDL statement failed: {stmt} -> {exc}") from exc
        logger.info("Tiger Cloud schema migration applied (%d statements) | path=%s", len(statements), migration_path)
    else:
        logger.warning("Tiger migration file not found at %s — skipping DDL", migration_path)

    # Wire the singleton into tiger_client module so get_tiger_memory() works.
    try:
        from backend.memory import tiger_client as _tc
        if _tc.tiger_memory is None:
            from backend.memory.tiger_client import TigerMemoryClient
            _tc.tiger_memory = TigerMemoryClient(_tiger_pool)
            logger.info("TigerMemoryClient singleton initialized.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("TigerMemoryClient init warning: %s", exc)

    logger.info(
        "Tiger Cloud pool ready | host=%s",
        dsn.split("@")[-1].split("/")[0] if "@" in dsn else "local",
    )


async def close_tiger_pool() -> None:
    """Closes the module-level Tiger Cloud asyncpg pool."""
    global _tiger_pool
    if _tiger_pool is not None:
        try:
            if hasattr(_tiger_pool, "close"):
                await _tiger_pool.close()
            logger.info("Tiger Cloud asyncpg pool closed.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error closing Tiger Cloud pool: %s", exc)
        finally:
            _tiger_pool = None


async def close_db() -> None:
    """Disposes the SQLAlchemy async engine connection pool."""
    global _engine
    if _engine is not None:
        try:
            await _engine.dispose()
            logger.info("SQLAlchemy database engine disposed.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error disposing database engine: %s", exc)
        finally:
            _engine = None


