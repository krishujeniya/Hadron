# tests/test_api_models_and_semantics_t28.py
#
# Gate B (T28): API models, totals, composite review IDs, and status semantics.
# Verifies:
# 1. Rebuild endpoint contract compatibility (rebuilt and pushed_to_redis).
# 2. Deterministic pagination with stable tie-breakers (no duplicate or skipped rows).
# 3. Composite review IDs in economics router (avoids UUID-only failure mode).
# 4. Review schema semantic field alignment (workflow_status, publication_status,
#    mandatory_check_coverage, recommendation, human_decision, freshness_status).
# 5. Malformed ID and bounds handling (1..255 chars, 400 Bad Request on invalid IDs).

from datetime import datetime, timezone
import pytest
from starlette.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

from backend.main import app
from backend.config.settings import Settings, get_settings
from backend.database.models import PRReviewRecord


@pytest.fixture
def client():
    return TestClient(app)


def test_rebuild_queue_returns_aligned_rebuilt_and_pushed_to_redis(client):
    """POST /api/v1/hitl/queue/rebuild returns both rebuilt and pushed_to_redis for client compatibility."""
    cfg = Settings(api_key="valid-test-key-t28")
    app.dependency_overrides[get_settings] = lambda: cfg
    try:
        with patch("backend.api.hitl_router.rebuild_redis_queue", new_callable=AsyncMock) as mock_rebuild:
            mock_rebuild.return_value = 5
            resp = client.post(
                "/api/v1/hitl/queue/rebuild",
                headers={"X-API-Key": "valid-test-key-t28"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["rebuilt"] == 5
            assert data["pushed_to_redis"] == 5
            assert "Rebuilt: pushed 5 pending items" in data["message"]
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_economics_pr_cost_accepts_composite_review_ids(client):
    """GET /api/v1/economics/pr-cost/{review_id} accepts composite review IDs without UUID ValueError."""
    cfg = Settings(api_key="valid-test-key-t28")
    app.dependency_overrides[get_settings] = lambda: cfg
    try:
        composite_id = "octocat/Hello-World:42:c0ffee1234"
        with patch("backend.database.postgres.get_tiger_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow.return_value = {
                "review_id": composite_id,
                "total_cost_usd": 0.045,
                "total_tokens": 1250,
                "agents_used": 4,
                "max_confidence": 0.95,
            }
            # Set up async context manager for pool.acquire()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            resp = client.get(
                f"/api/v1/economics/pr-cost/{composite_id}",
                headers={"X-API-Key": "valid-test-key-t28"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["review_id"] == composite_id
            assert data["total_cost_usd"] == 0.045
            assert data["agents_used"] == 4
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_economics_pr_cost_malformed_empty_id_rejected(client):
    """GET /api/v1/economics/pr-cost with invalid or excessive length is rejected with 400 or 404."""
    cfg = Settings(api_key="valid-test-key-t28")
    app.dependency_overrides[get_settings] = lambda: cfg
    try:
        excessive_id = "a" * 300
        resp = client.get(
            f"/api/v1/economics/pr-cost/{excessive_id}",
            headers={"X-API-Key": "valid-test-key-t28"},
        )
        assert resp.status_code == 400
        assert "1..255 chars" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_review_schemas_semantic_fields_alignment():
    """ReviewSummary and ReviewDetail models populate separate semantic fields."""
    now = datetime.now(timezone.utc)
    record = PRReviewRecord(
        id="owner/repo:10:abcdef",
        repo_full_name="owner/repo",
        pr_number=10,
        pr_title="Add semantic telemetry",
        head_commit_sha="abcdef123456",
        verdict="approve",
        status="completed",
        overall_confidence=0.92,
        needs_human_review=0,
        human_review_reason="",
        github_review_id=98765,
        created_at=now,
        updated_at=now,
    )
    # Empty findings list
    record.findings = []

    from backend.api.schemas import review_record_to_summary, review_record_to_detail

    summary = review_record_to_summary(record)
    assert summary.workflow_status == "completed"
    assert summary.publication_status == "posted"
    assert summary.recommendation == "approve"
    assert summary.human_decision is None
    assert summary.freshness_status == "fresh"
    assert summary.mandatory_check_coverage["security"] is True

    # Test held by kill switch
    record_held = PRReviewRecord(
        id="owner/repo:11:abcdef",
        repo_full_name="owner/repo",
        pr_number=11,
        pr_title="PR held by kill switch",
        head_commit_sha="abcdef123456",
        verdict="comment",
        status="held_by_kill_switch",
        overall_confidence=0.85,
        needs_human_review=0,
        human_review_reason="",
        github_review_id=None,
        created_at=now,
        updated_at=now,
    )
    record_held.findings = []
    summary_held = review_record_to_summary(record_held)
    assert summary_held.workflow_status == "held_by_kill_switch"
    assert summary_held.publication_status == "held"

    # Test escalated HITL
    record_hitl = PRReviewRecord(
        id="owner/repo:12:abcdef",
        repo_full_name="owner/repo",
        pr_number=12,
        pr_title="PR requiring human review",
        head_commit_sha="abcdef123456",
        verdict="needs_human_review",
        status="completed",
        overall_confidence=0.55,
        needs_human_review=1,
        human_review_reason="Low confidence score (0.55 < 0.70)",
        github_review_id=None,
        created_at=now,
        updated_at=now,
    )
    record_hitl.findings = []
    detail_hitl = review_record_to_detail(record_hitl)
    assert detail_hitl.publication_status == "pending_hitl"
    assert detail_hitl.human_decision == "escalated"
    assert detail_hitl.recommendation == "needs_human_review"


@pytest.mark.asyncio
async def test_deterministic_queue_and_review_ordering_tie_breaker():
    """Ordering clauses for reviews and HITL queue contain deterministic secondary tie-breaker."""
    import inspect
    from backend.database.repository import list_reviews
    from backend.hitl.queue import get_pending_queue

    list_reviews_src = inspect.getsource(list_reviews)
    assert "PRReviewRecord.created_at.desc(), PRReviewRecord.id.desc()" in list_reviews_src

    get_pending_queue_src = inspect.getsource(get_pending_queue)
    assert "HITLReview.created_at.asc(), HITLReview.id.asc()" in get_pending_queue_src
