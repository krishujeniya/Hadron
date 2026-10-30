# tests/test_disaster_recovery_and_backups_t24.py
#
# Contract and acceptance tests for Gate B - Task T24:
# Prove backups and disaster recovery.
#
# Invariants verified:
#   1. Backups produce authenticated AES-256 ciphertext with tamper-evident SHA-256 digests.
#   2. Tampered or corrupted backup payloads are detected and strictly rejected.
#   3. Isolated database restore reconstitutes data with foreign key referential integrity.
#   4. Lost Redis failure recovery reconciles queues from Postgres durable receipts without duplicate GitHub reviews.
#   5. GDPR Art. 17 Right-to-Erasure obligations are preserved across database restores via tombstone replay.
#   6. CLI disaster recovery drill script executes end-to-end backup and isolated restore verification.

import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend.database.models import FindingRecord, HITLReview, PRReviewRecord
from backend.database.postgres import Base
from backend.disaster_recovery.backup import create_backup
from backend.disaster_recovery.crypto import (
    BackupCorruptedError,
    DecryptionError,
    generate_backup_key,
)
from backend.disaster_recovery.reconciliation import (
    reconcile_after_redis_loss,
    verify_isolated_restore,
)
from backend.disaster_recovery.restore import restore_backup
from backend.disaster_recovery.tombstones import record_tombstone
from backend.governance.deletion import delete_tenant_data
from backend.governance.models import LegalHoldRecord
from backend.memory.redis_client import redis_client


@pytest.fixture
async def src_db_session():
    """Isolated in-memory SQLite database representing primary source of record."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def target_db_session():
    """Isolated target database for restore drills."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_encrypted_backup_creation_and_tamper_detection(src_db_session: AsyncSession):
    """
    Backup must encrypt all source tables and verify tamper-evident SHA-256 digest.
    Corrupted payloads must be rejected immediately.
    """
    key = generate_backup_key()

    # Seed data
    rev = PRReviewRecord(
        id="corp/repo:pr:1:sha1",
        repo_full_name="corp/repo",
        pr_number=1,
        head_commit_sha="sha1",
        verdict="approve",
        status="completed",
    )
    f = FindingRecord(
        id=str(uuid.uuid4()),
        review_id=rev.id,
        repo_full_name="corp/repo",
        agent_type="security",
        severity="high",
        category="auth",
        summary="Missing auth check",
        confidence=0.9,
    )
    hold = LegalHoldRecord(
        id=str(uuid.uuid4()),
        tenant_id="corp",
        reason="Compliance audit",
        placed_by="legal_officer",
    )
    src_db_session.add_all([rev, f, hold])
    await src_db_session.commit()

    # Create backup
    backup = await create_backup(session=src_db_session, encryption_key=key)

    manifest = backup["manifest"]
    assert manifest["schema_version"] == "v1.0"
    assert manifest["record_counts"]["pr_review_records"] == 1
    assert manifest["record_counts"]["finding_records"] == 1
    assert manifest["record_counts"]["legal_holds"] == 1
    assert manifest["tenants_included"] == ["corp"]
    assert len(manifest["sha256_checksum"]) == 64

    # 1. Tamper detection: flip characters in ciphertext
    corrupted_backup = {
        "manifest": dict(manifest),
        "payload": backup["payload"][:-4] + "XXXX",
    }
    with pytest.raises(BackupCorruptedError):
        from backend.disaster_recovery.crypto import decrypt_payload
        decrypt_payload(
            ciphertext=corrupted_backup["payload"],
            checksum=corrupted_backup["manifest"]["sha256_checksum"],
            key=key,
        )

    # 2. Decryption failure: wrong key
    wrong_key = generate_backup_key()
    with pytest.raises(DecryptionError):
        from backend.disaster_recovery.crypto import decrypt_payload
        decrypt_payload(
            ciphertext=backup["payload"],
            checksum=manifest["sha256_checksum"],
            key=wrong_key,
        )


@pytest.mark.asyncio
async def test_isolated_database_restore_and_referential_integrity(
    src_db_session: AsyncSession,
    target_db_session: AsyncSession,
):
    """
    Restore into an isolated target database must reconstruct all rows and preserve
    foreign key referential integrity.
    """
    key = generate_backup_key()

    # Seed source DB
    rev = PRReviewRecord(
        id="acme/web:pr:42:sha99",
        repo_full_name="acme/web",
        pr_number=42,
        head_commit_sha="sha99",
        verdict="request_changes",
        status="completed",
    )
    f1 = FindingRecord(
        id=str(uuid.uuid4()),
        review_id=rev.id,
        repo_full_name="acme/web",
        agent_type="quality",
        severity="medium",
        category="style",
        summary="Issue 1",
        confidence=0.8,
    )
    f2 = FindingRecord(
        id=str(uuid.uuid4()),
        review_id=rev.id,
        repo_full_name="acme/web",
        agent_type="security",
        severity="critical",
        category="injection",
        summary="Issue 2",
        confidence=0.95,
    )
    hitl = HITLReview(
        id="acme/web:pr:42:sha99:hitl",
        review_id=rev.id,
        repo_full_name="acme/web",
        pr_number=42,
        agent_verdict="request_changes",
        status="pending",
    )
    src_db_session.add_all([rev, f1, f2, hitl])
    await src_db_session.commit()

    # 1. Create backup
    backup = await create_backup(session=src_db_session, encryption_key=key)

    # 2. Restore to empty target DB
    restore_res = await restore_backup(
        backup_package=backup,
        target_session=target_db_session,
        encryption_key=key,
        apply_tombstones=False,
    )

    assert restore_res["status"] == "restored"
    assert restore_res["restored_counts"]["pr_review_records"] == 1
    assert restore_res["restored_counts"]["finding_records"] == 2
    assert restore_res["restored_counts"]["hitl_reviews"] == 1

    # 3. Verify referential integrity and isolation
    report = await verify_isolated_restore(
        source_session=src_db_session,
        restored_session=target_db_session,
    )
    assert report["is_valid"] is True
    assert report["checks"]["foreign_keys_intact"] is True
    assert report["checks"]["counts_match"] is True


@pytest.mark.asyncio
async def test_lost_redis_reconstruction_without_duplicate_reviews(src_db_session: AsyncSession):
    """
    When Redis is completely wiped, the reconciler must inspect Postgres durable receipts.
    Reviews already delivered to GitHub (github_review_id != None) must be finalized.
    Only unfulfilled reviews without receipts should be re-enqueued.
    """
    # 1. PR review that was delivered to GitHub before Redis crashed
    rev_delivered = PRReviewRecord(
        id="org/app:pr:1:sha1",
        repo_full_name="org/app",
        pr_number=1,
        head_commit_sha="sha1",
        status="in_progress",
        github_review_id=987654321,  # Receipt exists on GitHub!
    )

    # 2. PR review that was pending and never delivered
    rev_pending = PRReviewRecord(
        id="org/app:pr:2:sha2",
        repo_full_name="org/app",
        pr_number=2,
        head_commit_sha="sha2",
        status="pending",
        github_review_id=None,
    )

    # 3. Completed PR review
    rev_completed = PRReviewRecord(
        id="org/app:pr:3:sha3",
        repo_full_name="org/app",
        pr_number=3,
        head_commit_sha="sha3",
        status="completed",
        github_review_id=112233,
    )

    src_db_session.add_all([rev_delivered, rev_pending, rev_completed])
    await src_db_session.commit()

    # Reconcile after Redis failure
    summary = await reconcile_after_redis_loss(db_session=src_db_session, redis_client=redis_client)

    assert summary["total_unfulfilled_found"] == 2
    assert summary["already_delivered_marked_completed"] == 1
    assert summary["requeued_count"] == 1
    assert summary["requeued_ids"] == ["org/app:pr:2:sha2"]

    # Verify database state
    await src_db_session.refresh(rev_delivered)
    assert rev_delivered.status == "completed"  # Marked completed, never re-reviewed!

    await src_db_session.refresh(rev_pending)
    assert rev_pending.status == "pending"


@pytest.mark.asyncio
async def test_preservation_of_erasure_obligations_across_restore(
    src_db_session: AsyncSession,
    target_db_session: AsyncSession,
):
    """
    GDPR Art. 17 Invariant: Restoring an older snapshot taken BEFORE a tenant deletion
    must replay the tombstone ledger and re-purge the erased tenant before serving traffic.
    """
    key = generate_backup_key()
    with tempfile.TemporaryDirectory() as tmp_dir:
        tombstone_file = Path(tmp_dir) / "test_tombstones.jsonl"

        # T0: Seed tenant 'alpha' and tenant 'doomed'
        rev_alpha = PRReviewRecord(
            id="alpha/repo:pr:1:sha1",
            repo_full_name="alpha/repo",
            pr_number=1,
            head_commit_sha="sha1",
            status="completed",
        )
        rev_doomed = PRReviewRecord(
            id="doomed/repo:pr:2:sha2",
            repo_full_name="doomed/repo",
            pr_number=2,
            head_commit_sha="sha2",
            status="completed",
        )
        src_db_session.add_all([rev_alpha, rev_doomed])
        await src_db_session.commit()

        # T0 snapshot: contains BOTH alpha and doomed
        backup = await create_backup(session=src_db_session, encryption_key=key)

        # T1: Tenant 'doomed' exercises Right to Erasure
        erasure_time = datetime.now(timezone.utc) + timedelta(seconds=1)
        record_tombstone(
            tenant_id="doomed",
            actor="gdpr_compliance_officer",
            timestamp=erasure_time,
            path=tombstone_file,
        )

        # T2: Disaster strikes! Restore T0 backup with tombstone replay
        summary = await restore_backup(
            backup_package=backup,
            target_session=target_db_session,
            encryption_key=key,
            apply_tombstones=True,
            tombstone_path=tombstone_file,
        )

        assert summary["tombstones_applied"] == 1
        assert "doomed" in summary["erased_tenants"]

        # Verify target database: alpha is present, doomed is ABSENT!
        alpha_check = await target_db_session.execute(
            select(PRReviewRecord).where(PRReviewRecord.repo_full_name.like("alpha/%"))
        )
        assert len(alpha_check.scalars().all()) == 1

        doomed_check = await target_db_session.execute(
            select(PRReviewRecord).where(PRReviewRecord.repo_full_name.like("doomed/%"))
        )
        assert len(doomed_check.scalars().all()) == 0

        # Run verification helper
        report = await verify_isolated_restore(
            source_session=src_db_session,
            restored_session=target_db_session,
            expected_erased_tenants=["doomed"],
        )
        assert report["is_valid"] is True
        assert report["checks"]["tenant_isolation_preserved"] is True


@pytest.mark.asyncio
async def test_cli_dr_drill_execution(src_db_session: AsyncSession):
    """
    Verifies that the CLI disaster recovery drill (scripts/dr_drill.py) executes
    properly and can restore a snapshot into an isolated testing environment.
    """
    from scripts.dr_drill import run_restore_drill

    with tempfile.TemporaryDirectory() as tmp_dir:
        snap_path = Path(tmp_dir) / "test_snapshot.json"

        # Create snapshot to disk
        backup = await create_backup(session=src_db_session, target_path=snap_path)
        assert snap_path.exists()

        # Run CLI restore drill
        await run_restore_drill(str(snap_path))
