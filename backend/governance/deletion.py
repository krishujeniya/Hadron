# backend/governance/deletion.py
#
# Tenant data erasure and offboarding lifecycle (GDPR Art. 17 / CCPA).
# Idempotently and safely deletes tenant data across Postgres, Timescale/pgvector, and Redis.

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import (
    FindingRecord,
    HITLFeedback,
    HITLReview,
    LLMCallLog,
    PRReviewRecord,
    RepoFileIndexRecord,
)
from backend.database.postgres import get_tiger_pool
from backend.governance.legal_hold import LegalHoldActiveError, is_tenant_on_legal_hold
from backend.memory.redis_client import redis_client
from backend.observability.audit import record_audit_event

logger = logging.getLogger(__name__)


async def delete_tenant_data(
    session: AsyncSession,
    tenant_id: str,
    actor: str = "system",
) -> dict[str, Any]:
    """
    Deletes all operational and contextual data belonging to a tenant.
    Prevents execution if the tenant is under an active legal hold.
    Retries are safe and idempotent.
    """
    if not tenant_id or not tenant_id.strip():
        raise ValueError("tenant_id must be provided")

    tenant_id = tenant_id.strip()

    # 1. Enforce Legal Hold Boundary
    if await is_tenant_on_legal_hold(session, tenant_id):
        logger.warning("Tenant deletion aborted due to active legal hold | tenant=%s actor=%s", tenant_id, actor)
        raise LegalHoldActiveError(tenant_id, reason="Active legal hold prevents data destruction")

    logger.info("Starting tenant data erasure | tenant=%s actor=%s", tenant_id, actor)
    tenant_prefix = f"{tenant_id}/%"

    # 2. Delete from PostgreSQL
    # Find all review IDs for this tenant
    review_ids_stmt = select(PRReviewRecord.id).where(
        (PRReviewRecord.repo_full_name.like(tenant_prefix)) | (PRReviewRecord.repo_full_name == tenant_id)
    )
    review_ids_res = await session.execute(review_ids_stmt)
    review_ids = [r[0] for r in review_ids_res.fetchall()]

    # Delete findings
    findings_deleted = 0
    if review_ids:
        del_findings = delete(FindingRecord).where(FindingRecord.review_id.in_(review_ids))
        res_findings = await session.execute(del_findings)
        findings_deleted = res_findings.rowcount or 0

    # Delete reviews
    del_reviews = delete(PRReviewRecord).where(
        (PRReviewRecord.repo_full_name.like(tenant_prefix)) | (PRReviewRecord.repo_full_name == tenant_id)
    )
    res_reviews = await session.execute(del_reviews)
    reviews_deleted = res_reviews.rowcount or 0

    # Delete indexed file tracking
    del_index = delete(RepoFileIndexRecord).where(
        (RepoFileIndexRecord.repo_full_name.like(tenant_prefix)) | (RepoFileIndexRecord.repo_full_name == tenant_id)
    )
    res_index = await session.execute(del_index)
    index_deleted = res_index.rowcount or 0

    # Delete HITL reviews & feedback
    del_hitl = delete(HITLReview).where(
        (HITLReview.repo_full_name.like(tenant_prefix)) | (HITLReview.repo_full_name == tenant_id)
    )
    res_hitl = await session.execute(del_hitl)
    hitl_deleted = res_hitl.rowcount or 0

    del_feedback = delete(HITLFeedback).where(
        (HITLFeedback.repo_full_name.like(tenant_prefix)) | (HITLFeedback.repo_full_name == tenant_id)
    )
    res_feedback = await session.execute(del_feedback)
    feedback_deleted = res_feedback.rowcount or 0

    # Delete LLM call logs
    del_llm = delete(LLMCallLog).where(
        (LLMCallLog.tenant_id == tenant_id)
        | (LLMCallLog.workflow_id.like(tenant_prefix))
        | (LLMCallLog.workflow_id.like(f"{tenant_id}:%"))
    )
    res_llm = await session.execute(del_llm)
    llm_deleted = res_llm.rowcount or 0

    await session.commit()

    # 3. Delete from TimescaleDB / pgvector (code_chunks & agent_events)
    chunks_deleted = 0
    events_deleted = 0
    tiger_pool = get_tiger_pool()
    if tiger_pool is not None and hasattr(tiger_pool, "acquire"):
        try:
            async with tiger_pool.acquire() as conn:
                res_chunks = await conn.execute(
                    "DELETE FROM code_chunks WHERE repo_full_name LIKE $1 OR repo_full_name = $2",
                    tenant_prefix,
                    tenant_id,
                )
                if isinstance(res_chunks, str) and "DELETE" in res_chunks:
                    chunks_deleted = int(res_chunks.split()[-1])

                res_events = await conn.execute(
                    "DELETE FROM agent_events WHERE repo_full_name LIKE $1 OR repo_full_name = $2",
                    tenant_prefix,
                    tenant_id,
                )
                if isinstance(res_events, str) and "DELETE" in res_events:
                    events_deleted = int(res_events.split()[-1])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Tiger Cloud tenant deletion non-fatal warning: %s", exc)

    # 4. Clear tenant Redis keys
    redis_cleared = False
    try:
        # Clear tenant active counter
        if redis_client._pool is not None:
            await redis_client._pool.delete(f"tenant_active:{tenant_id}")
            redis_cleared = True
        else:
            redis_client._in_memory_fallback.pop(f"tenant_active:{tenant_id}", None)
            redis_cleared = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis tenant cleanup warning: %s", exc)

    summary = {
        "tenant_id": tenant_id,
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "postgres_deleted": {
            "pr_reviews": reviews_deleted,
            "findings": findings_deleted,
            "indexed_files": index_deleted,
            "hitl_reviews": hitl_deleted,
            "hitl_feedback": feedback_deleted,
            "llm_logs": llm_deleted,
        },
        "tiger_deleted": {
            "code_chunks": chunks_deleted,
            "agent_events": events_deleted,
        },
        "redis_cleared": redis_cleared,
    }

    # 5. Record immutable audit record and erasure tombstone (preserves erasure obligations across restore)
    record_audit_event(
        action="tenant_data_deleted",
        actor=actor,
        resource_id=tenant_id,
        tenant_id=tenant_id,
        details={
            "reviews_deleted": reviews_deleted,
            "findings_deleted": findings_deleted,
            "chunks_deleted": chunks_deleted,
        },
    )
    try:
        from backend.disaster_recovery.tombstones import record_tombstone
        record_tombstone(tenant_id=tenant_id, actor=actor)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to record erasure tombstone: %s", exc)

    logger.info("Tenant data erasure complete | summary=%s", summary)
    return summary
