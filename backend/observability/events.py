"""Typed event vocabulary for the PR Review Agent observability layer.

WHY A TYPED ENUM?
  Unstructured string event names drift over time -- 'review.started' becomes
  'review_started' becomes 'ReviewStarted' in different parts of the codebase.
  A StrEnum is the single source of truth: every emitted event, every log entry,
  every audit record uses ReviewEvent.X so grep finds everything.

  Borrowed pattern from opensre analytics/events.py (analytics/events.py:8-60),
  which uses the same StrEnum approach for all lifecycle events.

  Wiki: "Emit every log entry as a JSON object with a consistent schema" --
  typed events are the schema anchor that makes the promise enforceable.

NAMING CONVENTION
  Format: <resource>.<action>  (lowercase, dot-separated)
  resource: webhook | review | agent | llm | tool | verdict | hitl | audit
  action:   past-tense verb (received, started, completed, failed, escalated, ...)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import asyncpg

# StrEnum was added in Python 3.11; provide a compat shim for 3.10.
try:
    from enum import StrEnum
except ImportError:
    from enum import Enum

    class StrEnum(str, Enum):  # type: ignore[no-redef]
        pass

logger = logging.getLogger(__name__)


class ReviewEvent(StrEnum):
    # ── Webhook lifecycle ────────────────────────────────────────────────────
    # Fired by the webhook receiver when a GitHub PR event arrives.
    WEBHOOK_RECEIVED = "webhook.received"

    # Fired after HMAC-SHA256 validation passes and the event is deduplicated.
    WEBHOOK_VALIDATED = "webhook.validated"

    # ── Review workflow lifecycle ────────────────────────────────────────────
    # Fired when the ARQ worker picks up a review job and begins the workflow.
    REVIEW_STARTED = "review.started"

    # Fired when all 4 agents have returned and aggregate_results() has run.
    REVIEW_COMPLETED = "review.completed"

    # Fired when the workflow raises an unhandled exception.
    REVIEW_FAILED = "review.failed"

    # ── Per-agent lifecycle ──────────────────────────────────────────────────
    # Fired at the start of each specialist agent's analyze() call.
    AGENT_INVOKED = "agent.invoked"

    # Fired when an agent's analyze() returns successfully with an AgentOutput.
    AGENT_COMPLETED = "agent.completed"

    # Fired when an agent raises an exception (caught by the node, not re-raised).
    AGENT_FAILED = "agent.failed"

    # ── LLM call lifecycle ───────────────────────────────────────────────────
    # Fired on every call to LLMClient.call() -- carries token counts + cost.
    # Wiki: "Attach cost_usd and token counts as span tags on every LLM call."
    LLM_CALLED = "llm.called"

    # Fired when the LLM call fails (timeout, rate-limit, provider error).
    LLM_FAILED = "llm.failed"

    # ── Tool call lifecycle ──────────────────────────────────────────────────
    # Fired on every tool execution through the ToolRegistry.
    TOOL_CALLED = "tool.called"

    # Fired when a tool execution raises an exception.
    TOOL_FAILED = "tool.failed"

    # ── Verdict lifecycle ────────────────────────────────────────────────────
    # Fired when aggregate_results() produces a final ReviewVerdict.
    VERDICT_EMITTED = "verdict.emitted"

    # Fired when the Safety-Threshold Rule triggers HITL escalation
    # (2+ CRITICAL_BLOCK agents -> human review queue).
    HITL_ESCALATED = "hitl.escalated"

    # ── Evaluation lifecycle ─────────────────────────────────────────────────
    # Fired when the regression gate runs (Phase 9 integration).
    EVAL_GATE_RUN = "eval.gate.run"

    # Fired when the regression gate blocks a deployment.
    EVAL_GATE_BLOCKED = "eval.gate.blocked"


# =============================================================================
# AgentEvent — Tiger Cloud hypertable row
#
# Every span start/end, LLM call, tool call, and decision emits one row
# into the agent_events hypertable. This is the spine of observability:
# the trace viewer, audit trail, and cost ledger all read from it.
#
# Design principles:
#   - Fire-and-forget: emit_agent_event() is a background task.
#     Never awaited on the hot path. A write failure does NOT fail the review.
#   - Immutable: rows are never updated after insert. Append-only log.
#   - Cheap: asyncpg executemany, no ORM overhead, no SQLAlchemy session.
#
# event_type vocabulary (mirrors ReviewEvent but coarser-grained for the spine):
#   "span.start"   -- agent execution begins
#   "span.end"     -- agent execution ends (with outcome + confidence)
#   "llm.call"     -- single LLM API call (with tokens_in, tokens_out, cost_usd)
#   "tool.call"    -- tool registry invocation
#   "decision"     -- aggregator verdict decision
#   "escalation"   -- HITL queue insertion
# =============================================================================
@dataclass
class AgentEvent:
    """
    A single row in the agent_events hypertable.

    Maps directly to the schema in scripts/migrations/2026-06-tiger-init.sql.
    All time is UTC. span_id is auto-generated if not supplied.
    """
    review_id: str
    agent: str                       # "security" | "quality" | "tests" | "docs" | "aggregator" | "system"
    event_type: str                  # "span.start" | "span.end" | "llm.call" | "tool.call" | "decision" | "escalation"
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    span_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_span: str | None = None
    model: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    latency_ms: int | None = None
    outcome: str | None = None       # "approved" | "request_changes" | "critical_block" | "escalated"
    confidence: float | None = None  # 0.000 to 1.000
    payload: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# emit_agent_event
#
# Fire-and-forget write to the agent_events hypertable.
# Called from orchestrator/nodes.py and tools/llm_client.py.
#
# WHY NOT USE SQLAlchemy here?
# The agent_events table is the hot write path — every LLM call, every span.
# SQLAlchemy ORM adds ~2ms per-row from Python-side hydration. asyncpg
# execute() is sub-millisecond. At 50 LLM calls per PR review, that is
# 100ms of pure ORM overhead per review. Not worth it.
#
# WHY FIRE-AND-FORGET?
# A failed telemetry write must never fail the review. The user gets their
# review comment either way. We log the error and continue.
# (Reliability Engineering: "observability failures are non-fatal")
# ---------------------------------------------------------------------------
_INSERT_SQL = """
    INSERT INTO agent_events
        (ts, review_id, agent, span_id, parent_span, event_type,
         model, tokens_in, tokens_out, cost_usd, latency_ms,
         outcome, confidence, payload)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
"""

_PENDING_EVENT_TASKS: set[asyncio.Task] = set()


def dispatch_agent_event(event: AgentEvent, pool: asyncpg.Pool | None = None) -> asyncio.Task:
    """
    Schedules an agent event insertion in the background and registers it
    so it can be reliably flushed before process shutdown.
    """
    task = asyncio.create_task(emit_agent_event(pool=pool, event=event))
    _PENDING_EVENT_TASKS.add(task)
    task.add_done_callback(_PENDING_EVENT_TASKS.discard)
    return task


async def flush_agent_events(timeout_s: float = 3.0) -> None:
    """
    Awaits all in-flight background agent event writes.
    Called during process shutdown to ensure no telemetry rows are dropped.
    """
    if not _PENDING_EVENT_TASKS:
        return
    tasks = list(_PENDING_EVENT_TASKS)
    logger.info("flush_agent_events | flushing %d pending event writes", len(tasks))
    done, pending = await asyncio.wait(tasks, timeout=timeout_s)
    if pending:
        logger.warning(
            "flush_agent_events | %d event writes still pending after %.1fs timeout",
            len(pending),
            timeout_s,
        )
        for t in pending:
            t.cancel()
    else:
        logger.info("flush_agent_events | all pending event writes flushed successfully")


async def emit_agent_event(pool: asyncpg.Pool | None = None, event: AgentEvent | None = None) -> None:
    """
    Write one AgentEvent row to the agent_events hypertable.

    Fire-and-forget: exceptions are caught and logged, never re-raised.
    Pass pool=None to fall back to the active Tiger Cloud pool or silently skip.

    Args:
        pool:  asyncpg connection pool for Tiger Cloud. None = auto-detect.
        event: The AgentEvent row to insert.
    """
    if event is None:
        return
    if pool is None:
        try:
            from backend.database.postgres import get_tiger_pool
            pool = get_tiger_pool()
        except Exception:  # pragma: no cover
            pool = None
    if pool is None:
        return
    try:
        # Robust UUID handling for span_id and parent_span
        span_uuid = None
        if event.span_id:
            try:
                span_uuid = uuid.UUID(event.span_id) if isinstance(event.span_id, str) else event.span_id
            except (ValueError, TypeError):
                span_uuid = uuid.uuid4()
        else:
            span_uuid = uuid.uuid4()

        parent_uuid = None
        if event.parent_span:
            try:
                parent_uuid = uuid.UUID(event.parent_span) if isinstance(event.parent_span, str) else event.parent_span
            except (ValueError, TypeError):
                parent_uuid = None

        async with pool.acquire() as conn:
            await conn.execute(
                _INSERT_SQL,
                event.ts,
                str(event.review_id),
                event.agent,
                span_uuid,
                parent_uuid,
                event.event_type,
                event.model,
                event.tokens_in,
                event.tokens_out,
                event.cost_usd,
                event.latency_ms,
                event.outcome,
                event.confidence,
                event.payload,   # asyncpg serializes dict -> JSONB automatically
            )
    except Exception as exc:  # noqa: BLE001
        # Never let observability failures crash the review workflow.
        logger.error(
            "emit_agent_event failed (non-fatal) | review_id=%s agent=%s event=%s error=%s",
            event.review_id, event.agent, event.event_type, exc,
        )
