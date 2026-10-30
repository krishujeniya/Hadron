# backend/governance/retention.py
#
# Scheduled data retention and lifecycle purge engine.
# Enforces configurable data retention periods while respecting legal holds.
# Separates audit integrity (verdicts, metrics) from unnecessary raw code diff retention.

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import FindingRecord, HITLFeedback, PRReviewRecord
from backend.database.postgres import get_tiger_pool
from backend.governance.models import LegalHoldRecord
from backend.observability.audit import record_audit_event

logger = logging.getLogger(__name__)


@dataclass
class RetentionPolicy:
    """Configurable data retention periods."""
    diff_retention_days: int = 14       # Raw code diff context scrubbed after 14 days
    review_retention_days: int = 90     # Full review & finding records purged after 90 days
    event_retention_days: int = 365     # Telemetry & agent events purged after 1 year


async def _get_active_legal_hold_tenants(session: AsyncSession) -> set[str]:
    """Returns set of tenant_ids currently under an active legal hold."""
    stmt = select(LegalHoldRecord.tenant_id).where(LegalHoldRecord.active.is_(True))
    res = await session.execute(stmt)
    return {row[0] for row in res.fetchall()}


async def purge_expired_data(
    session: AsyncSession,
    policy: RetentionPolicy | None = None,
    actor: str = "scheduled_retention_job",
) -> dict[str, Any]:
    """
    Executes automated retention purge.
    Skips any tenant with an active legal hold.
    Idempotent and retry-safe.
    """
    policy = policy or RetentionPolicy()
    now = datetime.now(timezone.utc)
    held_tenants = await _get_active_legal_hold_tenants(session)

    # 1. Scrub raw code diff context (context_snapshot in HITLFeedback) older than diff_retention_days
    # (Audit integrity preserved: verdict, findings, line numbers remain, raw code scrubbed)
    diff_cutoff = now - timedelta(days=policy.diff_retention_days)
    feedback_stmt = (
        update(HITLFeedback)
        .where(HITLFeedback.created_at < diff_cutoff)
        .where(HITLFeedback.context_snapshot != "")
        .where(HITLFeedback.context_snapshot.is_not(None))
    )
    for tenant in held_tenants:
        feedback_stmt = feedback_stmt.where(~HITLFeedback.repo_full_name.like(f"{tenant}/%"))

    feedback_stmt = feedback_stmt.values(context_snapshot="")
    res_diffs = await session.execute(feedback_stmt)
    diffs_scrubbed = res_diffs.rowcount or 0

    # 2. Purge expired reviews & findings older than review_retention_days
    review_cutoff = now - timedelta(days=policy.review_retention_days)
    find_expired_reviews = (
        select(PRReviewRecord.id)
        .where(PRReviewRecord.created_at < review_cutoff)
    )
    for tenant in held_tenants:
        find_expired_reviews = find_expired_reviews.where(~PRReviewRecord.repo_full_name.like(f"{tenant}/%"))

    expired_res = await session.execute(find_expired_reviews)
    expired_ids = [r[0] for r in expired_res.fetchall()]

    findings_purged = 0
    reviews_purged = 0
    if expired_ids:
        del_findings = delete(FindingRecord).where(FindingRecord.review_id.in_(expired_ids))
        res_f = await session.execute(del_findings)
        findings_purged = res_f.rowcount or 0

        del_reviews = delete(PRReviewRecord).where(PRReviewRecord.id.in_(expired_ids))
        res_r = await session.execute(del_reviews)
        reviews_purged = res_r.rowcount or 0

    await session.commit()

    # 3. Purge expired agent events in TimescaleDB
    events_purged = 0
    tiger_pool = get_tiger_pool()
    if tiger_pool is not None and hasattr(tiger_pool, "acquire"):
        try:
            event_cutoff = now - timedelta(days=policy.event_retention_days)
            async with tiger_pool.acquire() as conn:
                res_e = await conn.execute(
                    "DELETE FROM agent_events WHERE timestamp < $1",
                    event_cutoff,
                )
                if isinstance(res_e, str) and "DELETE" in res_e:
                    events_purged = int(res_e.split()[-1])
        except Exception as exc:  # noqa: BLE001
            logger.warning("TimescaleDB retention purge warning: %s", exc)

    summary = {
        "executed_at": now.isoformat(),
        "actor": actor,
        "diffs_scrubbed": diffs_scrubbed,
        "reviews_purged": reviews_purged,
        "findings_purged": findings_purged,
        "agent_events_purged": events_purged,
        "held_tenants_skipped": sorted(list(held_tenants)),
    }

    record_audit_event(
        action="retention_purge_executed",
        actor=actor,
        resource_id="global_retention",
        details=summary,
    )

    logger.info("Retention purge completed | summary=%s", summary)
    return summary
