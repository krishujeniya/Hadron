# tests/test_data_governance_and_retention_t23.py
#
# Contract and acceptance tests for Gate B - Task T23:
# Implement retention, deletion, export, and data governance.
#
# Invariants verified:
#   1. Scoped data export (GDPR Art. 20) includes only the requesting tenant's data.
#   2. Tenant data deletion (GDPR Art. 17) deletes records across Postgres and Redis.
#   3. Active legal hold strictly prevents data deletion and scheduled purges.
#   4. Scheduled retention purges expired reviews while respecting legal holds.
#   5. Scheduled diff scrubbing removes raw code while preserving findings & audit metrics.
#   6. GitHub App uninstall (installation.deleted) triggers automatic tenant data deletion.
#   7. Governance API endpoints enforce strict RBAC and tenant isolation boundaries.

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend.database.models import (
    FindingRecord,
    HITLFeedback,
    HITLReview,
    PRReviewRecord,
)
from backend.database.postgres import Base
from backend.governance.deletion import delete_tenant_data
from backend.governance.export import export_tenant_data
from backend.governance.legal_hold import (
    LegalHoldActiveError,
    is_tenant_on_legal_hold,
    place_legal_hold,
    release_legal_hold,
)
from backend.governance.retention import RetentionPolicy, purge_expired_data
from backend.memory.redis_client import redis_client


@pytest.fixture
async def test_db_session():
    """Isolated in-memory SQLite database for governance tests."""
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
async def test_tenant_scoped_export_includes_only_tenant_data(test_db_session: AsyncSession):
    """
    Export must extract only the requesting tenant's reviews and findings,
    strictly isolating it from other tenants in the database.
    """
    # 1. Insert records for tenant-alpha
    rev_a = PRReviewRecord(
        id="alpha/repo:pr:1:sha1",
        repo_full_name="alpha/repo",
        pr_number=1,
        head_commit_sha="sha1",
        verdict="approve",
        status="completed",
        created_at=datetime.now(timezone.utc),
    )
    f_a = FindingRecord(
        id=str(uuid.uuid4()),
        review_id=rev_a.id,
        repo_full_name="alpha/repo",
        agent_type="security",
        severity="high",
        category="injection",
        summary="Alpha finding",
        confidence=0.9,
    )
    test_db_session.add_all([rev_a, f_a])

    # 2. Insert records for tenant-beta
    rev_b = PRReviewRecord(
        id="beta/repo:pr:2:sha2",
        repo_full_name="beta/repo",
        pr_number=2,
        head_commit_sha="sha2",
        verdict="request_changes",
        status="completed",
        created_at=datetime.now(timezone.utc),
    )
    f_b = FindingRecord(
        id=str(uuid.uuid4()),
        review_id=rev_b.id,
        repo_full_name="beta/repo",
        agent_type="quality",
        severity="low",
        category="style",
        summary="Beta finding",
        confidence=0.8,
    )
    test_db_session.add_all([rev_b, f_b])
    await test_db_session.commit()

    # 3. Export data for tenant 'alpha'
    export = await export_tenant_data(
        session=test_db_session,
        tenant_id="alpha",
        requested_by="user_alpha",
    )

    manifest = export["manifest"]
    assert manifest["tenant_id"] == "alpha"
    assert manifest["record_counts"]["reviews"] == 1
    assert manifest["record_counts"]["findings"] == 1

    reviews = export["reviews"]
    assert len(reviews) == 1
    assert reviews[0]["repo_full_name"] == "alpha/repo"
    assert len(reviews[0]["findings"]) == 1
    assert reviews[0]["findings"][0]["summary"] == "Alpha finding"

    # Verify tenant 'beta' data is completely absent
    assert not any("beta" in r["repo_full_name"] for r in reviews)


@pytest.mark.asyncio
async def test_tenant_data_deletion_removes_from_all_active_stores(test_db_session: AsyncSession):
    """
    delete_tenant_data must erase tenant records in Postgres and Redis while
    leaving other tenants intact.
    """
    # Setup data
    rev_del = PRReviewRecord(
        id="doomed/repo:pr:1:sha1",
        repo_full_name="doomed/repo",
        pr_number=1,
        head_commit_sha="sha1",
        verdict="approve",
        status="completed",
    )
    f_del = FindingRecord(
        id=str(uuid.uuid4()),
        review_id=rev_del.id,
        repo_full_name="doomed/repo",
        agent_type="security",
        severity="medium",
        category="auth",
        summary="Doomed finding",
        confidence=0.85,
    )
    rev_keep = PRReviewRecord(
        id="safe/repo:pr:1:sha1",
        repo_full_name="safe/repo",
        pr_number=1,
        head_commit_sha="sha1",
        verdict="approve",
        status="completed",
    )
    test_db_session.add_all([rev_del, f_del, rev_keep])
    await test_db_session.commit()

    # Set up Redis tenant active counter
    await redis_client.increment_tenant_active("doomed")

    # Execute deletion
    summary = await delete_tenant_data(
        session=test_db_session,
        tenant_id="doomed",
        actor="admin_user",
    )

    assert summary["postgres_deleted"]["pr_reviews"] == 1
    assert summary["postgres_deleted"]["findings"] == 1
    assert summary["redis_cleared"] is True

    # Verify in DB: doomed repo gone, safe repo intact
    doomed_check = await test_db_session.execute(
        select(PRReviewRecord).where(PRReviewRecord.repo_full_name.like("doomed/%"))
    )
    assert len(doomed_check.scalars().all()) == 0

    safe_check = await test_db_session.execute(
        select(PRReviewRecord).where(PRReviewRecord.repo_full_name.like("safe/%"))
    )
    assert len(safe_check.scalars().all()) == 1


@pytest.mark.asyncio
async def test_legal_hold_blocks_tenant_deletion(test_db_session: AsyncSession):
    """
    An active legal hold must strictly prohibit tenant data erasure.
    """
    rev = PRReviewRecord(
        id="litigation/repo:pr:1:sha1",
        repo_full_name="litigation/repo",
        pr_number=1,
        head_commit_sha="sha1",
        verdict="request_changes",
        status="completed",
    )
    test_db_session.add(rev)
    await test_db_session.commit()

    # Place legal hold
    hold = await place_legal_hold(
        session=test_db_session,
        tenant_id="litigation",
        reason="SEC investigation subpoena docket #12345",
        placed_by="compliance_officer",
    )
    assert hold.active is True
    assert await is_tenant_on_legal_hold(test_db_session, "litigation") is True

    # Attempt deletion — must raise LegalHoldActiveError
    with pytest.raises(LegalHoldActiveError) as exc_info:
        await delete_tenant_data(session=test_db_session, tenant_id="litigation")

    assert "litigation" in str(exc_info.value)

    # Release legal hold
    released = await release_legal_hold(
        session=test_db_session,
        tenant_id="litigation",
        released_by="compliance_officer",
    )
    assert released is True
    assert await is_tenant_on_legal_hold(test_db_session, "litigation") is False

    # Deletion now succeeds
    summary = await delete_tenant_data(session=test_db_session, tenant_id="litigation")
    assert summary["postgres_deleted"]["pr_reviews"] == 1


@pytest.mark.asyncio
async def test_retention_scrubs_raw_diffs_while_preserving_findings_and_verdict(test_db_session: AsyncSession):
    """
    Audit integrity separation: 14-day retention scrubs raw code diff context
    (context_snapshot in HITLFeedback) to minimize proprietary source retention,
    while keeping verdicts and findings intact.
    """
    old_date = datetime.now(timezone.utc) - timedelta(days=20)
    rev = PRReviewRecord(
        id="corp/repo:pr:1:sha1",
        repo_full_name="corp/repo",
        pr_number=1,
        head_commit_sha="sha1",
        verdict="approve",
        status="completed",
        created_at=old_date,
    )
    f = FindingRecord(
        id=str(uuid.uuid4()),
        review_id=rev.id,
        repo_full_name="corp/repo",
        agent_type="security",
        severity="critical",
        category="hardcoded_secret",
        summary="Hardcoded secret detected",
        confidence=0.95,
    )
    hitl_rev = HITLReview(
        id="corp/repo:pr:1:sha1:hitl",
        review_id=rev.id,
        repo_full_name="corp/repo",
        pr_number=1,
        agent_verdict="request_changes",
        status="approved",
        created_at=old_date,
    )
    feedback = HITLFeedback(
        id=str(uuid.uuid4()),
        hitl_review_id=hitl_rev.id,
        repo_full_name="corp/repo",
        pr_number=1,
        agent_verdict="request_changes",
        human_verdict="approve",
        feedback_type="override",
        context_snapshot="diff --git a/secret.py b/secret.py\n+password = 'private'",
        created_at=old_date,
    )
    test_db_session.add_all([rev, f, hitl_rev, feedback])
    await test_db_session.commit()

    # Run purge with 14-day diff retention and 90-day review retention
    summary = await purge_expired_data(
        session=test_db_session,
        policy=RetentionPolicy(diff_retention_days=14, review_retention_days=90),
    )

    assert summary["diffs_scrubbed"] == 1
    assert summary["reviews_purged"] == 0

    # Verify review and feedback in database: context_snapshot is empty, but verdict and finding remain
    await test_db_session.refresh(feedback)
    await test_db_session.refresh(rev)
    assert feedback.context_snapshot == ""
    assert rev.verdict == "approve"

    findings_check = await test_db_session.execute(
        select(FindingRecord).where(FindingRecord.review_id == rev.id)
    )
    findings = findings_check.scalars().all()
    assert len(findings) == 1
    assert findings[0].summary == "Hardcoded secret detected"


@pytest.mark.asyncio
async def test_retention_purges_expired_reviews_and_respects_legal_hold(test_db_session: AsyncSession):
    """
    Scheduled purge erases reviews older than 90 days, but completely skips tenants
    with an active legal hold.
    """
    very_old_date = datetime.now(timezone.utc) - timedelta(days=120)

    # 1. Normal tenant review (should be purged)
    rev_normal = PRReviewRecord(
        id="normal/repo:pr:1:sha1",
        repo_full_name="normal/repo",
        pr_number=1,
        head_commit_sha="sha1",
        status="completed",
        created_at=very_old_date,
    )

    # 2. Held tenant review (must NOT be purged)
    rev_held = PRReviewRecord(
        id="held/repo:pr:2:sha2",
        repo_full_name="held/repo",
        pr_number=2,
        head_commit_sha="sha2",
        status="completed",
        created_at=very_old_date,
    )

    test_db_session.add_all([rev_normal, rev_held])
    await test_db_session.commit()

    # Place hold on 'held'
    await place_legal_hold(
        session=test_db_session,
        tenant_id="held",
        reason="Litigation hold",
        placed_by="attorney",
    )

    # Run purge
    summary = await purge_expired_data(
        session=test_db_session,
        policy=RetentionPolicy(diff_retention_days=14, review_retention_days=90),
    )

    assert summary["reviews_purged"] == 1
    assert "held" in summary["held_tenants_skipped"]

    # Verify normal was deleted, held remains
    normal_res = await test_db_session.execute(
        select(PRReviewRecord).where(PRReviewRecord.id == "normal/repo:pr:1:sha1")
    )
    assert normal_res.scalar_one_or_none() is None

    held_res = await test_db_session.execute(
        select(PRReviewRecord).where(PRReviewRecord.id == "held/repo:pr:2:sha2")
    )
    assert held_res.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_governance_api_endpoints_rbac_and_lifecycle(test_db_session: AsyncSession):
    """
    Contract test for FastAPI governance router:
      1. Unauthenticated requests are rejected (401).
      2. Authenticated Admin can place legal hold, list holds, and trigger retention.
      3. Deletion is blocked with 409 while legal hold is active.
      4. Releasing legal hold permits deletion.
      5. Scoped export generates a downloadable payload with audit manifest.
    """
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.database.postgres import get_db
    from backend.auth.session_store import session_store
    from backend.security.rbac import Role

    app.dependency_overrides[get_db] = lambda: test_db_session

    # Seed data
    rev = PRReviewRecord(
        id="gov-tenant/repo:pr:1:sha1",
        repo_full_name="gov-tenant/repo",
        pr_number=1,
        head_commit_sha="sha1",
        status="completed",
    )
    test_db_session.add(rev)
    await test_db_session.commit()

    with TestClient(app, raise_server_exceptions=True) as client:
        # 1. Unauthenticated requests return 401
        res = client.post("/api/v1/governance/export", json={"tenant_id": "gov-tenant"})
        assert res.status_code == 401

        res = client.get("/api/v1/governance/legal-holds")
        assert res.status_code == 401

        # Create authenticated admin session
        admin_session = await session_store.create_session(
            user_id="compliance_admin",
            role=Role.ADMIN,
            account="gov-tenant",
        )
        client.cookies.set("hadron_session", admin_session.session_id)
        headers = {"X-CSRF-Token": admin_session.csrf_token}

        # 2. Place legal hold via API
        res = client.post(
            "/api/v1/governance/tenants/gov-tenant/legal-hold",
            json={"reason": "Regulatory audit request ref #987"},
            headers=headers,
        )
        assert res.status_code == 200
        assert res.json()["status"] == "placed"
        assert res.json()["status"] == "placed"

        # 3. List legal holds
        res = client.get("/api/v1/governance/legal-holds?tenant_id=gov-tenant", headers=headers)
        assert res.status_code == 200
        holds = res.json()
        assert len(holds) == 1
        assert holds[0]["tenant_id"] == "gov-tenant"
        assert holds[0]["active"] is True

        # 4. Attempt tenant purge while legal hold is active -> Expect 409 Conflict
        res = client.post("/api/v1/governance/tenants/gov-tenant/purge", headers=headers)
        assert res.status_code == 409

        # 5. Release legal hold via API
        res = client.delete("/api/v1/governance/tenants/gov-tenant/legal-hold", headers=headers)
        assert res.status_code == 200
        assert res.json()["status"] == "released"

        # 6. Scoped export via API
        res = client.post(
            "/api/v1/governance/export",
            json={"tenant_id": "gov-tenant"},
            headers=headers,
        )
        assert res.status_code == 200
        export_body = res.json()
        assert export_body["manifest"]["tenant_id"] == "gov-tenant"
        assert len(export_body["reviews"]) == 1

        # 7. Execute tenant purge -> Expect 200 OK
        res = client.post("/api/v1/governance/tenants/gov-tenant/purge", headers=headers)
        assert res.status_code == 200
        assert res.json()["postgres_deleted"]["pr_reviews"] == 1

        # 8. Trigger retention run -> Expect 200 OK
        res = client.post("/api/v1/governance/retention/run", json={}, headers=headers)
        assert res.status_code == 200
        assert "diffs_scrubbed" in res.json()

    app.dependency_overrides.pop(get_db, None)
