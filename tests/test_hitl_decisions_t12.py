"""
tests/test_hitl_decisions_t12.py

Acceptance tests for T12:
Make human decisions atomic, attributable, and deliverable.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from starlette.testclient import TestClient

from backend.auth.dependencies import get_current_principal, require_auth
from backend.auth.principal import Principal
from backend.database.models import HITLReview
from backend.hitl.dispute import (
    DisputeAlreadyResolved,
    DisputeRequest,
    _human_verdict_to_github_event,
    resolve_dispute,
)
from backend.integrations.github_models import ReviewEvent
from backend.main import app
from backend.security.rbac import Role


@pytest.fixture
def reviewer_principal():
    return Principal(
        id="reviewer_bob",
        role=Role.REVIEWER,
        account="acme",
        tenant_id="acme",
        auth_method="session",
    )


class TestT12HITLHumanDecisions:
    def test_faithful_verdict_event_mapping(self):
        """Human verdicts faithfully map to APPROVE and REQUEST_CHANGES on GitHub."""
        assert _human_verdict_to_github_event("approve") == "APPROVE"
        assert _human_verdict_to_github_event("request_changes") == "REQUEST_CHANGES"
        assert _human_verdict_to_github_event("dismiss") == "COMMENT"

    @pytest.mark.asyncio
    async def test_atomic_resolution_and_attributable_github_body(self):
        """Resolution and feedback execute atomically; GitHub body includes reviewer attribution."""
        mock_hitl_review = MagicMock(spec=HITLReview)
        mock_hitl_review.id = "hitl-101"
        mock_hitl_review.status = "pending"
        mock_hitl_review.repo_full_name = "acme/service"
        mock_hitl_review.pr_number = 15
        mock_hitl_review.review_id = "acme/service:15:sha777"
        mock_hitl_review.agent_verdict = "needs_human_review"
        mock_hitl_review.findings_snapshot = "[]"
        mock_hitl_review.escalation_reason = "Critical security alert"
        mock_hitl_review.overall_confidence = 0.65

        mock_session = MagicMock()
        mock_nested = AsyncMock()
        mock_nested.__aenter__.return_value = None
        mock_nested.__aexit__.return_value = None
        mock_session.begin_nested.return_value = mock_nested

        mock_execute_res = MagicMock()
        mock_execute_res.scalar_one_or_none.return_value = mock_hitl_review
        mock_session.execute = AsyncMock(return_value=mock_execute_res)
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        mock_github_client = AsyncMock()
        captured_payload = None

        async def capture_post(repo_full_name, pr_number, payload):
            nonlocal captured_payload
            captured_payload = payload

        mock_github_client.post_pr_review.side_effect = capture_post

        request = DisputeRequest(
            hitl_review_id="hitl-101",
            human_verdict="approve",
            reason="Verified manually by senior engineer",
            reviewer_id="engineer_alice",
        )

        with patch("backend.hitl.dispute.record_feedback", new=AsyncMock(return_value="feedback-uuid-123")), \
             patch("backend.database.postgres.get_session_factory") as mock_sf:
            mock_update_session = MagicMock()
            mock_begin = AsyncMock()
            mock_begin.__aenter__.return_value = None
            mock_begin.__aexit__.return_value = None
            mock_update_session.begin.return_value = mock_begin
            mock_update_res = MagicMock()
            mock_update_res.scalar_one_or_none.return_value = mock_hitl_review
            mock_update_session.execute = AsyncMock(return_value=mock_update_res)
            mock_sf.return_value.return_value.__aenter__.return_value = mock_update_session

            result = await resolve_dispute(
                session=mock_session,
                github_client=mock_github_client,
                request=request,
            )

            assert result.new_status == "approved"
            assert result.posted_to_github is True
            assert result.feedback_id == "feedback-uuid-123"

            # Check attribution in review comment body
            assert captured_payload is not None
            assert captured_payload.event == ReviewEvent.APPROVE
            assert "**Reviewer:** engineer_alice" in captured_payload.body
            assert "Verified manually by senior engineer" in captured_payload.body

    @pytest.mark.asyncio
    async def test_concurrent_dispute_already_resolved_conflict(self):
        """Second concurrent reviewer receives DisputeAlreadyResolved (HTTP 409)."""
        mock_hitl_review = MagicMock(spec=HITLReview)
        mock_hitl_review.status = "approved"  # Already resolved

        mock_session = MagicMock()
        mock_nested = AsyncMock()
        mock_nested.__aenter__.return_value = None
        mock_nested.__aexit__.return_value = None
        mock_session.begin_nested.return_value = mock_nested

        mock_execute_res = MagicMock()
        mock_execute_res.scalar_one_or_none.return_value = mock_hitl_review
        mock_session.execute = AsyncMock(return_value=mock_execute_res)

        request = DisputeRequest(
            hitl_review_id="hitl-102",
            human_verdict="request_changes",
            reason="Rejected",
            reviewer_id="reviewer_charlie",
        )

        with pytest.raises(DisputeAlreadyResolved) as exc_info:
            await resolve_dispute(
                session=mock_session,
                github_client=AsyncMock(),
                request=request,
            )
        assert exc_info.value.current_status == "approved"

    def test_truthful_queue_pagination_total(self, reviewer_principal):
        """HITL queue endpoint returns actual total count from database, not page slice length."""
        app.dependency_overrides[get_current_principal] = lambda: reviewer_principal
        app.dependency_overrides[require_auth] = lambda: reviewer_principal

        now = datetime.now(timezone.utc)
        mock_item1 = MagicMock(
            id="h1",
            review_id="acme/service:1:sha1",
            repo_full_name="acme/service",
            pr_number=1,
            agent_verdict="needs_human_review",
            human_verdict=None,
            status="pending",
            escalation_reason="Low confidence",
            overall_confidence=0.5,
            posted_to_github=False,
            created_at=now,
            resolved_at=None,
        )
        mock_item2 = MagicMock(
            id="h2",
            review_id="acme/service:2:sha2",
            repo_full_name="acme/service",
            pr_number=2,
            agent_verdict="needs_human_review",
            human_verdict=None,
            status="pending",
            escalation_reason="Low confidence",
            overall_confidence=0.5,
            posted_to_github=False,
            created_at=now,
            resolved_at=None,
        )

        with patch("backend.api.hitl_router.count_pending_queue", new=AsyncMock(return_value=42)), \
             patch("backend.api.hitl_router.get_pending_queue", new=AsyncMock(return_value=[mock_item1, mock_item2])):
            client = TestClient(app)
            resp = client.get("/api/v1/hitl/queue?limit=2&offset=0")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["items"]) == 2
            # Total must be truthful database total count (42), NOT page slice len (2)
            assert data["total"] == 42
            assert data["limit"] == 2
