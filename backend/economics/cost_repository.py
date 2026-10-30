# backend/economics/cost_repository.py
#
# Phase 16 — Persistence + aggregation for LLM cost data.
#
# DESIGN:
#   - record_llm_call():    Fire-and-forget insert. Errors logged, never raised.
#                           Cost telemetry must never break the review pipeline.
#   - get_*():              Read aggregations for the economics API.
#
# WHY FIRE-AND-FORGET?
# (LLMOps-Essentials.md: "Telemetry that fails the request is anti-telemetry.")
# If Postgres is down, we still want the LLM call to succeed and the review to
# proceed. We log the failure to stderr/structured logs and move on.
#
# ASYNC SESSION PATTERN:
# We use the module-level async_sessionmaker via get_engine() — same pattern as
# the rest of the codebase. Every public function is async and acquires its own
# short-lived session.

from __future__ import annotations

import asyncpg  # noqa: F401 — used in type hints
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.database.models import LLMCallLog
from backend.database.postgres import get_engine

logger = logging.getLogger(__name__)


def _new_session() -> AsyncSession:
    """Return a new async session bound to the module-level engine."""
    factory = async_sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return factory()


# ---------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------
async def record_llm_call(
    *,
    workflow_id: Optional[str],
    tenant_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    agent_type: str,
    call_type: str = "llm",
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    latency_ms: float,
    is_valid_json: bool = True,
    status: str = "settled",
) -> None:
    """
    Persist one LLM/embedding/judge call row with idempotency deduplication.
    Never raises on failure.
    """
    try:
        async with _new_session() as session:
            # Replay and duplicate safety via idempotency key
            if idempotency_key:
                stmt = select(LLMCallLog.id).where(LLMCallLog.idempotency_key == idempotency_key)
                existing = (await session.execute(stmt)).scalar()
                if existing:
                    logger.debug(
                        "llm_call_log_duplicate_ignored | idempotency_key=%s",
                        idempotency_key,
                    )
                    return

            row = LLMCallLog(
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                agent_type=agent_type or "system",
                call_type=call_type,
                model=model,
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens),
                cost_usd=float(cost_usd),
                latency_ms=float(latency_ms),
                is_valid_json=1 if is_valid_json else 0,
                status=status,
            )
            session.add(row)
            try:
                await session.commit()
            except IntegrityError:
                # Race condition duplicate insert caught safely
                logger.debug("llm_call_log_race_duplicate_caught | key=%s", idempotency_key)
                await session.rollback()
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning(
            "llm_call_log_persist_failed | agent=%s model=%s cost=%.6f error=%s",
            agent_type, model, cost_usd, exc,
        )


# ---------------------------------------------------------------------------
# Read path — aggregations
# ---------------------------------------------------------------------------
def _utc_today_start() -> datetime:
    """Return midnight UTC of the current day."""
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, now.day, tzinfo=timezone.utc)


async def query_daily_spend_db(
    *,
    tenant_id: Optional[str] = None,
    at: Optional[datetime] = None,
) -> float:
    """
    Executes the direct daily spend query against Postgres.
    Raises on database error so the caller can distinguish DB outage from $0.00 spend.
    """
    target = at or datetime.now(timezone.utc)
    day_start = datetime(target.year, target.month, target.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    async with _new_session() as session:
        stmt = select(func.coalesce(func.sum(LLMCallLog.cost_usd), 0.0)).where(
            LLMCallLog.created_at >= day_start,
            LLMCallLog.created_at < day_end,
        )
        if tenant_id and tenant_id != "default":
            stmt = stmt.where(LLMCallLog.tenant_id == tenant_id)

        result = await session.execute(stmt)
        return float(result.scalar() or 0.0)


async def get_daily_spend(
    *,
    tenant_id: Optional[str] = None,
    at: Optional[datetime] = None,
) -> float:
    """
    Total USD spent so far in the current UTC day (or the day containing `at`).
    Uses CostLedger to guarantee distinction between DB outage and zero spend.
    """
    try:
        from backend.economics.ledger import get_cost_ledger
        spend, _ = await get_cost_ledger().get_daily_spend(tenant_id=tenant_id, at=at)
        return spend
    except Exception as exc:
        logger.warning("get_daily_spend_failed | tenant=%s error=%s", tenant_id, exc)
        return 0.0


@dataclass
class WorkflowCost:
    """Cost rollup for a single workflow (one PR review run)."""
    workflow_id: str
    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    call_count: int
    by_agent: dict[str, float]   # agent_type -> cost_usd
    by_model: dict[str, float]   # model -> cost_usd


async def get_workflow_cost(workflow_id: str) -> WorkflowCost:
    """Cost rollup for one workflow, broken down by agent and model."""
    try:
        async with _new_session() as session:
            stmt = select(LLMCallLog).where(LLMCallLog.workflow_id == workflow_id)
            rows = (await session.execute(stmt)).scalars().all()
    except Exception as exc:
        logger.warning("workflow_cost_query_failed | wf=%s error=%s", workflow_id, exc)
        rows = []

    by_agent: dict[str, float] = defaultdict(float)
    by_model: dict[str, float] = defaultdict(float)
    total_cost = 0.0
    total_in = 0
    total_out = 0
    for r in rows:
        by_agent[r.agent_type] += r.cost_usd
        by_model[r.model] += r.cost_usd
        total_cost += r.cost_usd
        total_in += r.input_tokens
        total_out += r.output_tokens

    return WorkflowCost(
        workflow_id=workflow_id,
        total_cost_usd=round(total_cost, 6),
        total_input_tokens=total_in,
        total_output_tokens=total_out,
        call_count=len(rows),
        by_agent={k: round(v, 6) for k, v in by_agent.items()},
        by_model={k: round(v, 6) for k, v in by_model.items()},
    )


@dataclass
class EconomicsSummary:
    """Aggregate spend snapshot for the economics summary endpoint."""
    today_usd: float
    last_7d_usd: float
    last_30d_usd: float
    by_model_30d: dict[str, float]
    by_agent_30d: dict[str, float]
    call_count_30d: int
    total_input_tokens_30d: int
    total_output_tokens_30d: int


async def get_summary() -> EconomicsSummary:
    """
    Top-level spend snapshot: today, 7d, 30d totals + 30d breakdowns.

    The dashboard's primary cost card consumes this single endpoint.
    """
    today_start = _utc_today_start()
    d7_start = today_start - timedelta(days=6)   # inclusive of today = 7 days
    d30_start = today_start - timedelta(days=29) # inclusive of today = 30 days

    try:
        async with _new_session() as session:
            # 30d window — pull all rows once and bucket in Python.
            # At expected volumes (≤ 10k calls/30d) this is faster than 5 round-trips.
            stmt = select(LLMCallLog).where(LLMCallLog.created_at >= d30_start)
            rows = (await session.execute(stmt)).scalars().all()
    except Exception as exc:
        logger.warning("economics_summary_query_failed | error=%s", exc)
        rows = []

    today = 0.0
    d7 = 0.0
    d30 = 0.0
    by_model: dict[str, float] = defaultdict(float)
    by_agent: dict[str, float] = defaultdict(float)
    in_tok = 0
    out_tok = 0
    for r in rows:
        d30 += r.cost_usd
        by_model[r.model] += r.cost_usd
        by_agent[r.agent_type] += r.cost_usd
        in_tok += r.input_tokens
        out_tok += r.output_tokens
        if r.created_at >= d7_start:
            d7 += r.cost_usd
        if r.created_at >= today_start:
            today += r.cost_usd

    return EconomicsSummary(
        today_usd=round(today, 6),
        last_7d_usd=round(d7, 6),
        last_30d_usd=round(d30, 6),
        by_model_30d={k: round(v, 6) for k, v in by_model.items()},
        by_agent_30d={k: round(v, 6) for k, v in by_agent.items()},
        call_count_30d=len(rows),
        total_input_tokens_30d=in_tok,
        total_output_tokens_30d=out_tok,
    )


@dataclass
class DailyPoint:
    date: str            # ISO YYYY-MM-DD (UTC)
    cost_usd: float
    call_count: int


async def get_daily_timeseries(days: int = 30) -> list[DailyPoint]:
    """
    Per-UTC-day totals for the last `days` days. Fills zeros for missing days
    so the FE chart axis is dense.
    """
    days = max(1, min(days, 365))
    today_start = _utc_today_start()
    window_start = today_start - timedelta(days=days - 1)

    try:
        async with _new_session() as session:
            stmt = select(LLMCallLog).where(LLMCallLog.created_at >= window_start)
            rows = (await session.execute(stmt)).scalars().all()
    except Exception as exc:
        logger.warning("daily_timeseries_query_failed | error=%s", exc)
        rows = []

    buckets: dict[str, list[float]] = defaultdict(lambda: [0.0, 0])  # [cost, count]
    for r in rows:
        key = r.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
        buckets[key][0] += r.cost_usd
        buckets[key][1] += 1

    points: list[DailyPoint] = []
    for i in range(days):
        d = window_start + timedelta(days=i)
        key = d.strftime("%Y-%m-%d")
        cost, count = buckets.get(key, [0.0, 0])
        points.append(DailyPoint(date=key, cost_usd=round(cost, 6), call_count=int(count)))
    return points


# ---------------------------------------------------------------------------
# Tiger Cloud continuous-aggregate read methods
# ---------------------------------------------------------------------------

async def get_agent_health(
    pool: "asyncpg.Pool",
    minutes: int = 60,
) -> list[dict]:
    """
    Read per-agent health from the agent_health_1m continuous aggregate.
    Sub-millisecond at any scale — pre-materialized by TimescaleDB.
    """
    sql = """
        SELECT
            bucket,
            agent,
            llm_calls,
            cost_usd,
            tokens_in,
            tokens_out,
            p95_ms,
            p50_ms,
            rejection_rate,
            escalation_rate
        FROM agent_health_1m
        WHERE bucket >= now() - make_interval(mins => $1)
        ORDER BY bucket DESC, agent
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, minutes)
    return [dict(r) for r in rows]


async def get_pr_cost(
    pool: "asyncpg.Pool",
    review_id: str,
) -> dict | None:
    """
    Read per-PR cost from the pr_cost_hourly continuous aggregate.
    Returns total cost, tokens, agents used, and wall time for a review.
    """
    sql = """
        SELECT
            review_id,
            sum(total_cost_usd)    AS total_cost_usd,
            sum(total_tokens)       AS total_tokens,
            max(agents_used)        AS agents_used,
            max(max_confidence)     AS max_confidence,
            sum(wall_time)          AS wall_time
        FROM pr_cost_hourly
        WHERE review_id = $1
        GROUP BY review_id
    """
    import uuid
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, uuid.UUID(review_id))
    return dict(row) if row else None


async def get_daily_cost_from_tiger(
    pool: "asyncpg.Pool",
) -> float:
    """
    Total LLM cost over the last 24h from the agent_health_1m aggregate.
    Used by budget.py BudgetGuard as the authoritative daily spend figure.
    """
    sql = """
        SELECT COALESCE(sum(cost_usd), 0.0) AS total
        FROM agent_health_1m
        WHERE bucket >= now() - INTERVAL '24 hours'
    """
    async with pool.acquire() as conn:
        return float(await conn.fetchval(sql))
