# backend/disaster_recovery/restore.py
#
# Isolated database restore engine with SHA-256 validation, foreign key ordering,
# and tombstone replay to preserve GDPR Art. 17 right-to-erasure obligations.

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import (
    FindingRecord,
    HITLFeedback,
    HITLReview,
    LLMCallLog,
    PRReviewRecord,
    RepoFileIndexRecord,
)
from backend.disaster_recovery.crypto import decrypt_payload
from backend.disaster_recovery.tombstones import get_tombstones
from backend.governance.deletion import delete_tenant_data
from backend.governance.models import DataExportRecord, LegalHoldRecord
from backend.observability.audit import record_audit_event

logger = logging.getLogger(__name__)

DEFAULT_BACKUP_KEY = os.getenv("DR_BACKUP_ENCRYPTION_KEY", "hadron-disaster-recovery-master-key-32b")


def _dict_to_model(model_cls: type, data: dict[str, Any]) -> Any:
    """Instantiates a SQLAlchemy model from a dictionary, converting ISO datetimes."""
    clean_kwargs: dict[str, Any] = {}
    for col in model_cls.__table__.columns:
        if col.name in data:
            val = data[col.name]
            # Convert ISO string back to datetime if column is DateTime
            if str(col.type).startswith("DATETIME") or "DateTime" in str(col.type):
                if isinstance(val, str) and val:
                    try:
                        clean_kwargs[col.name] = datetime.fromisoformat(val)
                    except ValueError:
                        clean_kwargs[col.name] = val
                else:
                    clean_kwargs[col.name] = val
            else:
                clean_kwargs[col.name] = val
    return model_cls(**clean_kwargs)


async def restore_backup(
    backup_package: dict[str, Any] | str | Path,
    target_session: AsyncSession,
    encryption_key: str | bytes | None = None,
    apply_tombstones: bool = True,
    tombstone_path: Path | None = None,
    actor: str = "dr_automated_restore",
) -> dict[str, Any]:
    """
    Restores database from an encrypted backup package into target_session.
    Enforces tamper-evident integrity checks, foreign key dependency ordering,
    and post-restore erasure tombstone replay.
    """
    start_time = time.perf_counter()
    key = encryption_key or DEFAULT_BACKUP_KEY

    # 1. Load package if path or JSON string
    if isinstance(backup_package, (str, Path)):
        p = Path(backup_package)
        if p.is_file():
            raw_text = p.read_text(encoding="utf-8")
            package = json.loads(raw_text)
        else:
            package = json.loads(str(backup_package))
    else:
        package = backup_package

    manifest = package["manifest"]
    ciphertext = package["payload"]
    checksum = manifest["sha256_checksum"]
    backup_id = manifest["backup_id"]
    backup_time = datetime.fromisoformat(manifest["created_at"])

    logger.info("Initiating database restore | backup_id=%s created_at=%s", backup_id, manifest["created_at"])

    # 2. Authenticate, verify SHA-256, and decrypt payload
    tables_data = decrypt_payload(ciphertext=ciphertext, checksum=checksum, key=key)

    restored_counts: dict[str, int] = {}

    # 3. Stage 1: Insert parent tables (no inbound FKs)
    # pr_review_records
    for row in tables_data.get("pr_review_records", []):
        target_session.add(_dict_to_model(PRReviewRecord, row))
    restored_counts["pr_review_records"] = len(tables_data.get("pr_review_records", []))

    # repo_file_indices
    for row in tables_data.get("repo_file_indices", []):
        target_session.add(_dict_to_model(RepoFileIndexRecord, row))
    restored_counts["repo_file_indices"] = len(tables_data.get("repo_file_indices", []))

    # hitl_reviews
    for row in tables_data.get("hitl_reviews", []):
        target_session.add(_dict_to_model(HITLReview, row))
    restored_counts["hitl_reviews"] = len(tables_data.get("hitl_reviews", []))

    # legal_holds
    for row in tables_data.get("legal_holds", []):
        target_session.add(_dict_to_model(LegalHoldRecord, row))
    restored_counts["legal_holds"] = len(tables_data.get("legal_holds", []))

    # data_exports
    for row in tables_data.get("data_exports", []):
        target_session.add(_dict_to_model(DataExportRecord, row))
    restored_counts["data_exports"] = len(tables_data.get("data_exports", []))

    await target_session.flush()

    # 4. Stage 2: Insert child tables (FKs to parent tables)
    # finding_records (FK to pr_review_records)
    for row in tables_data.get("finding_records", []):
        target_session.add(_dict_to_model(FindingRecord, row))
    restored_counts["finding_records"] = len(tables_data.get("finding_records", []))

    # hitl_feedback (FK to hitl_reviews)
    for row in tables_data.get("hitl_feedback", []):
        target_session.add(_dict_to_model(HITLFeedback, row))
    restored_counts["hitl_feedback"] = len(tables_data.get("hitl_feedback", []))

    # llm_call_log
    for row in tables_data.get("llm_call_log", []):
        target_session.add(_dict_to_model(LLMCallLog, row))
    restored_counts["llm_call_log"] = len(tables_data.get("llm_call_log", []))

    await target_session.flush()

    # 5. Stage 3: Replay Tombstone Ledger (Preserve Right-to-Erasure obligations)
    tombstones_applied = 0
    erased_tenants: list[str] = []
    if apply_tombstones:
        subsequent_tombstones = get_tombstones(since=backup_time, path=tombstone_path)
        for ts in subsequent_tombstones:
            t_id = ts["tenant_id"]
            logger.warning("Replaying erasure tombstone across restored database | tenant=%s deleted_at=%s",
                           t_id, ts["timestamp"])
            await delete_tenant_data(session=target_session, tenant_id=t_id, actor="dr_tombstone_replayer")
            tombstones_applied += 1
            erased_tenants.append(t_id)

    await target_session.commit()
    elapsed = time.perf_counter() - start_time

    summary = {
        "status": "restored",
        "backup_id": backup_id,
        "restored_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(elapsed, 4),
        "restored_counts": restored_counts,
        "tombstones_applied": tombstones_applied,
        "erased_tenants": erased_tenants,
    }

    record_audit_event(
        action="dr_backup_restored",
        actor=actor,
        resource_id=backup_id,
        details=summary,
    )

    logger.info("Database restore completed successfully | backup_id=%s duration=%.2fs tombstones_applied=%d",
                backup_id, elapsed, tombstones_applied)
    return summary
