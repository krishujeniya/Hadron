# backend/disaster_recovery/backup.py
#
# Automated encrypted backup generator for PostgreSQL source-of-record tables.
# Enforces authenticated encryption (AES-256 via Fernet) and SHA-256 tamper-evident integrity.

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import (
    FindingRecord,
    HITLFeedback,
    HITLReview,
    LLMCallLog,
    PRReviewRecord,
    RepoFileIndexRecord,
)
from backend.disaster_recovery.crypto import encrypt_payload
from backend.governance.models import DataExportRecord, LegalHoldRecord
from backend.observability.audit import record_audit_event

logger = logging.getLogger(__name__)

DEFAULT_BACKUP_KEY = os.getenv("DR_BACKUP_ENCRYPTION_KEY", "hadron-disaster-recovery-master-key-32b")


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Serializes a SQLAlchemy model row to a plain JSON-compatible dictionary."""
    d: dict[str, Any] = {}
    for column in row.__table__.columns:
        val = getattr(row, column.name)
        if isinstance(val, datetime):
            d[column.name] = val.isoformat()
        else:
            d[column.name] = val
    return d


async def create_backup(
    session: AsyncSession,
    encryption_key: str | bytes | None = None,
    target_path: Path | str | None = None,
    actor: str = "dr_automated_backup",
) -> dict[str, Any]:
    """
    Extracts all source-of-record PostgreSQL tables, serializes them, encrypts with AES-256,
    computes SHA-256 tamper-evident digests, and builds a self-describing backup package.
    """
    key = encryption_key or DEFAULT_BACKUP_KEY
    now = datetime.now(timezone.utc)
    backup_id = f"dr-snap-{now.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"

    logger.info("Starting encrypted database backup | backup_id=%s actor=%s", backup_id, actor)

    # 1. Extract records from all persistent tables
    tables_data: dict[str, list[dict[str, Any]]] = {}
    tenants: set[str] = set()

    # pr_review_records
    reviews_res = await session.execute(select(PRReviewRecord))
    reviews = reviews_res.scalars().all()
    tables_data["pr_review_records"] = [_row_to_dict(r) for r in reviews]
    for r in reviews:
        if r.repo_full_name:
            tenants.add(r.repo_full_name.split("/")[0])

    # finding_records
    findings_res = await session.execute(select(FindingRecord))
    findings = findings_res.scalars().all()
    tables_data["finding_records"] = [_row_to_dict(f) for f in findings]

    # repo_file_indices
    indices_res = await session.execute(select(RepoFileIndexRecord))
    indices = indices_res.scalars().all()
    tables_data["repo_file_indices"] = [_row_to_dict(i) for i in indices]

    # hitl_reviews
    hitl_res = await session.execute(select(HITLReview))
    hitls = hitl_res.scalars().all()
    tables_data["hitl_reviews"] = [_row_to_dict(h) for h in hitls]

    # hitl_feedback
    feedback_res = await session.execute(select(HITLFeedback))
    feedbacks = feedback_res.scalars().all()
    tables_data["hitl_feedback"] = [_row_to_dict(fb) for fb in feedbacks]

    # legal_holds
    holds_res = await session.execute(select(LegalHoldRecord))
    holds = holds_res.scalars().all()
    tables_data["legal_holds"] = [_row_to_dict(lh) for lh in holds]

    # data_exports
    exports_res = await session.execute(select(DataExportRecord))
    exports = exports_res.scalars().all()
    tables_data["data_exports"] = [_row_to_dict(de) for de in exports]

    # llm_call_log
    llm_res = await session.execute(select(LLMCallLog))
    llm_logs = llm_res.scalars().all()
    tables_data["llm_call_log"] = [_row_to_dict(l) for l in llm_logs]

    record_counts = {table: len(rows) for table, rows in tables_data.items()}

    # 2. Encrypt payload and compute SHA-256 checksum
    ciphertext, checksum = encrypt_payload(tables_data, key)

    manifest = {
        "backup_id": backup_id,
        "created_at": now.isoformat(),
        "schema_version": "v1.0",
        "encryption_algorithm": "AES-256-Fernet",
        "sha256_checksum": checksum,
        "tenants_included": sorted(list(tenants)),
        "record_counts": record_counts,
        "total_records": sum(record_counts.values()),
    }

    backup_package = {
        "manifest": manifest,
        "payload": ciphertext,
    }

    # 3. Optional write to target path
    if target_path:
        out_p = Path(target_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(backup_package, indent=2), encoding="utf-8")
        logger.info("Backup package written to file | path=%s", out_p)

    # 4. Record audit event
    record_audit_event(
        action="dr_backup_created",
        actor=actor,
        resource_id=backup_id,
        details={
            "backup_id": backup_id,
            "record_counts": record_counts,
            "sha256_checksum": checksum,
        },
    )

    logger.info("Encrypted backup created successfully | backup_id=%s total_records=%d checksum=%s",
                backup_id, manifest["total_records"], checksum)
    return backup_package
