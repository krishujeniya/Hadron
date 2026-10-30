# backend/job_queue/arq_worker.py
#
# ARQ async job queue — the bridge between webhook receipt and review execution.
#
# THE PROBLEM THIS SOLVES:
# GitHub sends a webhook and expects a response within 10 seconds.
# A full PR review (4 agents, LLM calls) takes 60-120 seconds.
# If we ran the review synchronously inside the webhook handler, GitHub would
# time out and retry, creating duplicate reviews.
#
# THE SOLUTION:
# Webhook handler -> enqueues a job in Redis (< 100ms) -> returns 200 to GitHub
# ARQ worker      -> picks up the job from Redis -> runs the full review
#
# HOW ARQ WORKS:
# ARQ uses two Redis operations:
#   PRODUCER side (webhook router): LPUSH arq:queue:default [job_payload_json]
#   CONSUMER side (this worker):    BRPOP arq:queue:default [blocks until job appears]
#
# BRPOP is "blocking pop" — the worker sleeps at Redis waiting for a job.
# When a job appears, Redis wakes the worker immediately (no polling loop).
# This is the "push-based notification" pattern from Stream-Processing-Patterns.md
# (as opposed to the anti-pattern of polling a database for new rows).
#
# WORKER FUNCTIONS:
# An ARQ worker function is a coroutine that ARQ calls when a job is dequeued.
# It receives a Context object (ARQ-provided) plus any arguments the producer sent.
# It returns any value (ARQ logs it) or raises an exception (ARQ retries).
#
# RETRY BEHAVIOR:
# By default, ARQ retries a failed job 5 times with exponential backoff.
# Our job is idempotent (idempotency key in Redis prevents duplicate reviews)
# so retries are safe.
#
# FROM Fault-Tolerance.md (distributed-systems wiki):
# "Combine checkpointing with message logging."
# ARQ + LangGraph checkpointing together mean:
#   - ARQ: if the worker crashes, the job is requeued (message logging)
#   - LangGraph: if the review was mid-graph, resume() continues from the checkpoint
# Together: exactly-once review semantics despite worker crashes.

import logging

# Configure logging for the ARQ worker process.
# main.py configures logging for the API process, but the worker is a separate
# process that never imports main.py — so we configure it here directly.
# Without this, all logger.info/error calls in this file are silently dropped.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

from typing import Any

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings

from backend.config import get_settings
from backend.core import (
    DuplicateWebhookError,
    MemoryStoreError,
    QueueOverloadedError,
    TenantConcurrencyLimitError,
)
from backend.models.enums import ReviewStatus
from backend.memory.redis_client import redis_client
from backend.orchestrator.langgraph_engine import LangGraphEngine

logger = logging.getLogger(__name__)

# Module-level engine instance.
# LangGraphEngine is stateless (no per-review state) — safe to share.
_engine = LangGraphEngine()


# =============================================================================
# WORKER FUNCTION: run_pr_review
#
# This is the function ARQ calls when it dequeues a PR review job.
# ARQ passes `ctx` (ARQ context dict) as the first argument automatically.
# The remaining arguments match what enqueue_review_job() passes.
# =============================================================================

MAX_WORKER_RETRIES = 3


def is_retryable_error(exc: Exception | None, error_msg: str = "") -> bool:
    """Identifies transient errors that should trigger an ARQ retry."""
    if exc is not None:
        from backend.core.exceptions import RetryableWorkflowError
        import httpx
        if isinstance(exc, (RetryableWorkflowError, httpx.TimeoutException, httpx.ConnectError, ConnectionError)):
            return True
    msg = (str(exc) if exc else error_msg).lower()
    retry_markers = [
        "timeout",
        "connection refused",
        "connection dropped",
        "rate limit",
        "503",
        "502",
        "temporarily unavailable",
    ]
    return any(marker in msg for marker in retry_markers)


async def run_pr_review(
    ctx: dict[str, Any],
    workflow_id: str,
    input_data: dict[str, Any],
) -> dict[str, Any]:
    """
    ARQ worker function: runs a full PR review with durable checkpointing,
    exponential retry backoff for transient failures, and dead-letter queueing for poison jobs.
    """
    from arq.worker import Retry

    job_id = ctx.get("job_id", "unknown")
    retry_count = ctx.get("job_try", ctx.get("retry", 0))

    logger.info(
        "job_start | workflow_id=%s job_id=%s retry=%d",
        workflow_id,
        job_id,
        retry_count,
    )

    await redis_client.record_job_dequeued(workflow_id)
    await redis_client.set_workflow_status(workflow_id, "in_progress")

    repo_name = input_data.get("repo_full_name", "")
    tenant = repo_name.split("/")[0] if "/" in repo_name else (repo_name or "default")
    await redis_client.increment_tenant_active(tenant)

    try:
        result = await _engine.run(workflow_id, input_data)
    except Exception as e:
        logger.error(
            "run_pr_review | engine_exception | workflow_id=%s retry=%d error=%s",
            workflow_id, retry_count, e, exc_info=True,
        )
        if is_retryable_error(e) and retry_count < MAX_WORKER_RETRIES:
            defer_time = 2 ** retry_count
            await redis_client.set_workflow_status(workflow_id, "retrying")
            logger.info("job_transient_error_deferring | workflow_id=%s defer=%ds", workflow_id, defer_time)
            raise Retry(defer=defer_time) from e

        # Terminal engine exception -> DLQ
        reason = "max_retries_exceeded" if retry_count >= MAX_WORKER_RETRIES else "unhandled_engine_exception"
        await redis_client.record_dead_letter(
            workflow_id=workflow_id,
            reason=reason,
            details={"error": str(e), "retry_count": retry_count, "job_id": job_id},
        )
        await redis_client.set_workflow_status(workflow_id, "failed")
        return {
            "workflow_id": workflow_id,
            "status": "failed",
            "verdict": None,
            "findings_count": 0,
            "error": str(e),
        }
    finally:
        await redis_client.decrement_tenant_active(tenant)

    # Handle workflow failure status returned by engine
    if result.status == ReviewStatus.FAILED:
        err_msg = result.error_message or "Workflow marked as failed"
        if is_retryable_error(None, err_msg) and retry_count < MAX_WORKER_RETRIES:
            defer_time = 2 ** retry_count
            await redis_client.set_workflow_status(workflow_id, "retrying")
            logger.info("job_failed_transient_deferring | workflow_id=%s defer=%ds", workflow_id, defer_time)
            raise Retry(defer=defer_time)

        # Permanent workflow failure or max retries -> DLQ
        reason = "max_retries_exceeded" if retry_count >= MAX_WORKER_RETRIES else "workflow_execution_failed"
        await redis_client.record_dead_letter(
            workflow_id=workflow_id,
            reason=reason,
            details={"error": err_msg, "retry_count": retry_count, "job_id": job_id},
        )
        await redis_client.set_workflow_status(workflow_id, "failed")
        return {
            "workflow_id": workflow_id,
            "status": "failed",
            "verdict": None,
            "findings_count": len(result.findings),
            "error": err_msg,
        }

    # Workflow succeeded or completed (including HITL routing)
    await redis_client.set_workflow_status(workflow_id, result.status.value)

    logger.info(
        "job_complete | workflow_id=%s status=%s verdict=%s findings=%d",
        workflow_id,
        result.status.value,
        result.verdict.value if result.verdict else "none",
        len(result.findings),
    )

    # -------------------------------------------------------------------------
    # Step 5: Trigger background repository ingestion (Phase 14)
    #
    # After a successful review, we kick off ingestion of the repo's codebase
    # into Qdrant. This runs as a separate ARQ job — non-blocking, best-effort.
    #
    # WHY HERE (not in the review pipeline):
    #   Ingestion is a background maintenance operation, not part of the review
    #   flow. If ingestion fails, the review result is unaffected.
    #   (Batch-Processing-Patterns.md: "composable stages, no shared state.")
    #
    # WHY ONLY ON SUCCESS:
    #   If the review failed (status != "completed"), the diff/context was likely
    #   unusable. No point indexing a repo we couldn't review anyway.
    #
    # GRACEFUL: if enqueueing ingestion fails (Redis hiccup), we log and continue.
    # The review result has already been saved — nothing is lost.
    # -------------------------------------------------------------------------
    if result.status.value == "completed":
        repo_full_name = input_data.get("repo_full_name", "")  # flat key set by webhook router
        if repo_full_name:
            try:
                # Build settings inline — WorkerSettings is defined later in this
                # file, so we can't reference it here without a forward reference.
                arq_redis = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
                await arq_redis.enqueue_job(
                    "ingest_repository_job",
                    repo_full_name,
                )
                await arq_redis.aclose()
                logger.info(
                    "ingestion_enqueued | repo=%s workflow_id=%s",
                    repo_full_name, workflow_id,
                )
            except Exception as e:
                # Non-fatal: review is already saved. Ingestion will happen
                # on the NEXT successful review for this repo.
                logger.warning(
                    "ingestion_enqueue_failed | repo=%s error=%s: %s",
                    repo_full_name, type(e).__name__, e,
                )

    # Return a summary dict — ARQ logs this. Phase 10 will send this to traces.
    return {
        "workflow_id": workflow_id,
        "status": result.status.value,
        "verdict": result.verdict.value if result.verdict else None,
        "findings_count": len(result.findings),
        "agents_completed": result.agents_completed,
        "agents_failed": result.agents_failed,
    }


# =============================================================================
# PRODUCER HELPER: enqueue_review_job
#
# Called by the webhook router to enqueue a job.
# The router does NOT import ARQ directly — it calls this function.
# (Law of Demeter: router talks to this module, not to ARQ directly.)
# =============================================================================

async def enqueue_review_job(
    workflow_id: str,
    input_data: dict[str, Any],
    delivery_id: str | None = None,
) -> None:
    """
    Enqueues a PR review job in the ARQ Redis queue.

    Called by backend/webhook_receiver/router.py after webhook validation.
    Returns immediately — the review runs asynchronously in a worker process.

    Steps:
      1. Check idempotency key in Redis -> raise DuplicateWebhookError if already queued
      2. Push job payload to ARQ queue in Redis (_job_id=workflow_id)
      3. On successful enqueue: set idempotency key and record delivery receipt
      4. On failure: clean up any tentative state so future retries are not falsely blocked

    Raises:
        DuplicateWebhookError: if this exact review is already queued.
        MemoryStoreError: if Redis is unavailable.
    """
    cfg = get_settings()

    # Step 1: Check idempotency BEFORE enqueueing
    already_exists = await redis_client.check_idempotency_key(workflow_id)
    if already_exists:
        logger.info(
            "enqueue_skip_duplicate | workflow_id=%s",
            workflow_id,
        )
        raise DuplicateWebhookError(
            f"Review already queued: {workflow_id}",
            idempotency_key=workflow_id,
        )

    # Step 1b: Backpressure guard — check queue depth
    queue_depth = await redis_client.get_queue_depth()
    max_depth = getattr(cfg, "max_queue_depth", 100)
    if queue_depth >= max_depth:
        logger.warning("enqueue_backpressure | queue_depth=%d max=%d", queue_depth, max_depth)
        raise QueueOverloadedError(
            f"Queue capacity exceeded ({queue_depth} >= {max_depth}). Backpressure active.",
            queue_depth=queue_depth,
            retry_after=30,
        )

    # Step 1c: Tenant quota guard — check active concurrent reviews for this tenant
    repo_name = input_data.get("repo_full_name", "")
    tenant = repo_name.split("/")[0] if "/" in repo_name else (repo_name or "default")
    max_active = getattr(cfg, "max_active_per_tenant", 3)
    active_count = await redis_client.get_tenant_active(tenant)
    if active_count >= max_active:
        logger.warning(
            "enqueue_tenant_throttled | tenant=%s active=%d max=%d",
            tenant, active_count, max_active,
        )
        raise TenantConcurrencyLimitError(
            f"Tenant '{tenant}' active review limit reached ({active_count} >= {max_active}).",
            tenant_id=tenant,
            retry_after=30,
        )

    # Step 2: Connect to ARQ pool and enqueue the job
    redis_settings = RedisSettings.from_dsn(cfg.redis_url)
    try:
        arq_pool: ArqRedis = await create_pool(redis_settings)
    except Exception as e:
        raise MemoryStoreError(f"Failed to connect to queue pool: {e}", store="redis") from e

    try:
        job = await arq_pool.enqueue_job(
            "run_pr_review",           # the worker function name (as string)
            workflow_id,               # positional arg 1
            input_data,                # positional arg 2
            _job_id=workflow_id,       # ARQ job ID = workflow_id (for deduplication within ARQ)
        )
        # Step 3: Persist idempotency and delivery receipt only on confirmed enqueue
        await redis_client.set_idempotency_key(workflow_id)
        await redis_client.record_job_enqueued(workflow_id)
        if delivery_id:
            try:
                await redis_client.record_receipt(delivery_id, workflow_id)
            except Exception as e:
                logger.warning("Failed to record delivery receipt %s: %s", delivery_id, e)
        logger.info(
            "job_enqueued | workflow_id=%s arq_job_id=%s delivery_id=%s",
            workflow_id,
            job.job_id if job else "unknown",
            delivery_id,
        )
    except Exception as e:
        # Enqueue failed: ensure idempotency key does not block future redeliveries
        try:
            await redis_client.delete_idempotency_key(workflow_id)
            await redis_client.record_job_dequeued(workflow_id)
        except Exception:
            pass
        raise
    finally:
        await arq_pool.aclose()


# =============================================================================
# WORKER FUNCTION: ingest_repository_job  (Phase 14)
#
# Background ingestion job — indexes a repo's source files into Qdrant.
# Enqueued by run_pr_review after a successful review completes.
#
# ARQ contract: first arg is ctx (ARQ dict), rest are the job payload args.
# =============================================================================

async def ingest_repository_job(ctx: dict, repo_full_name: str) -> dict:
    """
    ARQ job: index all source files from a GitHub repository into Qdrant.

    Called automatically after every successful PR review.
    Runs in the background — review result is already saved before this starts.

    Returns a summary dict that ARQ logs:
      repo, total_files, stale_files, embedded, skipped_fresh, errors
    """
    # Import here (not at module top) to avoid circular imports at worker startup.
    # data/ imports database/ and memory/ — both are safe at this point since
    # on_startup has already run. But the import is deferred to keep the
    # worker startup path clean and testable.
    from backend.data.ingestion import ingest_repository

    logger.info("ingest_repository_job | start | repo=%s", repo_full_name)

    summary = await ingest_repository(repo_full_name)

    logger.info(
        "ingest_repository_job | complete | repo=%s "
        "total=%d stale=%d embedded=%d skipped=%d errors=%d",
        repo_full_name,
        summary.get("total_files", 0),
        summary.get("stale_files", 0),
        summary.get("embedded", 0),
        summary.get("skipped_fresh", 0),
        summary.get("errors", 0),
    )

    return {"repo": repo_full_name, **summary}


# =============================================================================
# ARQ WORKER SETTINGS
#
# ARQ uses this class to configure the worker process.
# When we run `arq backend.job_queue.arq_worker.WorkerSettings`
# ARQ reads this class to know: which functions to run, Redis URL, concurrency.
# =============================================================================

class WorkerSettings:
    """
    ARQ worker process configuration.

    Start the worker with:
      arq backend.job_queue.arq_worker.WorkerSettings

    ARQ lifecycle hooks (on_startup / on_shutdown) replace FastAPI's lifespan
    for the worker process. Redis must be connected here — the worker does not
    run FastAPI's lifespan handler.
    """

    functions = [run_pr_review, ingest_repository_job]

    redis_settings: RedisSettings = RedisSettings.from_dsn(get_settings().redis_url)

    max_jobs = 10
    job_timeout = 300
    max_tries = 3

    @staticmethod
    async def on_startup(ctx: dict) -> None:
        """Initialize all worker process resources: DB, Tiger Cloud, Redis, and Telemetry."""
        from backend.lifecycle import startup_process
        from backend.job_queue.heartbeat import start_worker_heartbeat
        await startup_process(service_name="hadron-worker")
        await start_worker_heartbeat()
        logger.info("ARQ worker full resource lifecycle online.")

    @staticmethod
    async def on_shutdown(ctx: dict) -> None:
        """Gracefully flush telemetry and disconnect DB, Tiger Cloud, and Redis."""
        from backend.job_queue.heartbeat import stop_worker_heartbeat
        from backend.lifecycle import shutdown_process
        await stop_worker_heartbeat()
        await shutdown_process(service_name="hadron-worker")
        logger.info("ARQ worker full resource lifecycle cleanly shut down.")
