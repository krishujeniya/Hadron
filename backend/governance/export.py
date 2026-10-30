# backend/governance/export.py
#
# Tenant-scoped data export engine (GDPR Article 20 / CCPA Portability).
# Compiles machine-readable JSON exports bounded strictly by tenant identity.

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database.models import (
    HITLFeedback,
    HITLReview,
    PRReviewRecord,
)
from backend.governance.models import DataExportRecord
from backend.observability.audit import record_audit_event

logger = logging.getLogger(__name__)


async def export_tenant_data(
    session: AsyncSession,
    tenant_id: str,
    requested_by: str,
    expiration_hours: int = 24,
) -> dict[str, Any]:
    """
    Exports all operational records, reviews, findings, and HITL decisions
    belonging strictly to the specified tenant.
    Excludes credentials, secrets, and other tenants' data.
    """
    if not tenant_id or not tenant_id.strip():
        raise ValueError("tenant_id must be provided")

    tenant_id = tenant_id.strip()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=expiration_hours)
    export_id = str(uuid.uuid4())
    tenant_prefix = f"{tenant_id}/%"

    # 1. Fetch PR reviews and eager-load findings
    reviews_stmt = (
        select(PRReviewRecord)
        .where(
            (PRReviewRecord.repo_full_name.like(tenant_prefix)) | (PRReviewRecord.repo_full_name == tenant_id)
        )
        .options(selectinload(PRReviewRecord.findings))
        .order_by(PRReviewRecord.created_at.desc())
    )
    reviews_res = await session.execute(reviews_stmt)
    reviews = reviews_res.scalars().all()

    # 2. Fetch HITL decisions & feedback
    hitl_stmt = select(HITLReview).where(
        (HITLReview.repo_full_name.like(tenant_prefix)) | (HITLReview.repo_full_name == tenant_id)
    )
    hitl_res = await session.execute(hitl_stmt)
    hitl_items = hitl_res.scalars().all()

    feedback_stmt = select(HITLFeedback).where(
        (HITLFeedback.repo_full_name.like(tenant_prefix)) | (HITLFeedback.repo_full_name == tenant_id)
    )
    feedback_res = await session.execute(feedback_stmt)
    feedback_items = feedback_res.scalars().all()

    # 3. Format structured export
    reviews_export = []
    total_findings = 0
    for r in reviews:
        findings_data = [
            {
                "id": f.id,
                "agent_type": f.agent_type,
                "severity": f.severity,
                "category": f.category,
                "summary": f.summary,
                "file_path": f.file_path,
                "line_start": f.line_start,
                "line_end": f.line_end,
                "confidence": f.confidence,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in getattr(r, "findings", [])
        ]
        total_findings += len(findings_data)

        reviews_export.append({
            "id": r.id,
            "repo_full_name": r.repo_full_name,
            "pr_number": r.pr_number,
            "commit_sha": getattr(r, "head_commit_sha", getattr(r, "commit_sha", "")),
            "verdict": r.verdict,
            "confidence_score": getattr(r, "overall_confidence", getattr(r, "confidence_score", 0.0)),
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "finding_count": len(findings_data),
            "findings": findings_data,
        })

    hitl_export = [
        {
            "id": h.id,
            "repo_full_name": h.repo_full_name,
            "pr_number": h.pr_number,
            "status": h.status,
            "human_verdict": h.human_verdict,
            "reviewed_by": getattr(h, "reviewer_id", getattr(h, "reviewed_by", None)),
            "reviewed_at": h.resolved_at.isoformat() if getattr(h, "resolved_at", None) else (h.reviewed_at.isoformat() if getattr(h, "reviewed_at", None) else None),
        }
        for h in hitl_items
    ]

    manifest = {
        "export_id": export_id,
        "tenant_id": tenant_id,
        "requested_by": requested_by,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "record_counts": {
            "reviews": len(reviews_export),
            "findings": total_findings,
            "hitl_reviews": len(hitl_export),
            "hitl_feedbacks": len(feedback_items),
        },
    }

    payload = {
        "manifest": manifest,
        "reviews": reviews_export,
        "hitl_records": hitl_export,
    }

    # 4. Save export log in database
    export_record = DataExportRecord(
        id=export_id,
        tenant_id=tenant_id,
        requested_by=requested_by,
        created_at=now,
        expires_at=expires_at,
        status="ready",
        manifest_summary=json.dumps(manifest["record_counts"]),
    )
    session.add(export_record)
    await session.commit()

    # 5. Record audit event
    record_audit_event(
        action="tenant_data_exported",
        actor=requested_by,
        resource_id=export_id,
        tenant_id=tenant_id,
        details=manifest["record_counts"],
    )

    logger.info("Tenant export generated | export_id=%s tenant=%s counts=%s",
                export_id, tenant_id, manifest["record_counts"])
    return payload
