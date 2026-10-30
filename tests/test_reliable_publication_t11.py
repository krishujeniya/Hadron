"""
tests/test_reliable_publication_t11.py

Acceptance tests for T11:
Separate review computation from reliable GitHub publication.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.integrations.github_client import GitHubAPIError, GitHubNotFoundError, GitHubRateLimitError, PostReviewResponse
from backend.integrations.github_models import ReviewEvent
from backend.models.enums import ReviewStatus, ReviewVerdict
from backend.orchestrator.nodes import (
    _findings_to_review_comments,
    _parse_diff_hunk_lines,
    post_review,
)


class TestT11ReliablePublication:
    def test_parse_diff_hunk_lines_handles_complex_diff(self):
        """Unified diff parser tracks additions, context, deletions, and no-newline markers."""
        diff = """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -10,4 +10,5 @@ def run():
     step1()
-    old_step()
+    new_step()
+    step3()
\\ No newline at end of file
"""
        valid_lines = _parse_diff_hunk_lines(diff)
        assert "src/app.py" in valid_lines
        # Right side: line 10 is 'step1()', 11 is 'new_step()', 12 is 'step3()'
        assert 10 in valid_lines["src/app.py"]
        assert 11 in valid_lines["src/app.py"]
        assert 12 in valid_lines["src/app.py"]
        # Line 50 is outside the hunk
        assert 50 not in valid_lines["src/app.py"]

    def test_inline_comments_filter_unsupported_lines_and_deduplicate(self):
        """Comments outside diff hunks are omitted; duplicate agent findings on same line are deduplicated."""
        valid_lines = {"src/app.py": {10, 11}}
        findings = [
            {"file_path": "src/app.py", "line_start": 10, "summary": "Missing type annotation"},
            {"file_path": "src/app.py", "line_start": 10, "summary": "Missing type annotation"},  # duplicate
            {"file_path": "src/app.py", "line_start": 99, "summary": "Line outside diff"},         # outside hunk
        ]

        comments = _findings_to_review_comments(findings, valid_diff_lines=valid_lines)
        assert len(comments) == 1
        assert comments[0].path == "src/app.py"
        assert comments[0].line == 10
        assert "Missing type annotation" in comments[0].body

    @pytest.mark.asyncio
    async def test_reconcile_existing_review_marker_prevents_duplicate_post(self):
        """If a review containing the stable marker already exists, post_review reconciles without duplicating."""
        workflow_id = "acme/repo:42:sha12345"
        state = {
            "workflow_id": workflow_id,
            "repo_full_name": "acme/repo",
            "pr_number": 42,
            "head_commit_sha": "sha12345",
            "needs_human_review": False,
            "final_findings": [],
            "verdict": ReviewVerdict.APPROVE,
            "pr_diff": "",
        }

        mock_existing = [
            {"id": 777, "body": f"<!-- hadron-review:{workflow_id} -->\n## Prior Post"},
        ]

        mock_client = AsyncMock()
        mock_client.list_pr_reviews.return_value = mock_existing

        with patch("backend.orchestrator.nodes.GitHubClient") as mock_gh_cls, \
             patch("backend.orchestrator.nodes._save_review_record", new=AsyncMock()) as mock_save:
            mock_gh_cls.return_value.__aenter__.return_value = mock_client

            result = await post_review(state)

            assert result["review_posted"] is True
            assert result["github_review_id"] == 777
            assert result["publication_status"] == "posted"
            # post_pr_review was NOT called because reconciliation discovered existing review
            mock_client.post_pr_review.assert_not_called()
            mock_save.assert_called_once_with(state, 777)

    @pytest.mark.asyncio
    async def test_fallback_to_body_only_when_inline_rejected(self):
        """When GitHub rejects inline comments with API error, post_review retries with body-only."""
        workflow_id = "acme/repo:42:sha67890"
        diff = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,1 +1,1 @@\n+line1\n"
        state = {
            "workflow_id": workflow_id,
            "repo_full_name": "acme/repo",
            "pr_number": 42,
            "head_commit_sha": "sha67890",
            "needs_human_review": False,
            "final_findings": [
                {"file_path": "a.py", "line_start": 1, "summary": "Issue"}
            ],
            "verdict": ReviewVerdict.APPROVE,
            "pr_diff": diff,
            "allow_stub_diff": True,
        }

        mock_client = AsyncMock()
        mock_client.list_pr_reviews.return_value = []
        
        # First call fails on comments (e.g. 422), second call succeeds without comments
        mock_resp = PostReviewResponse(id=888, state=ReviewEvent.APPROVE, html_url="https://github.com/rev/888")
        mock_client.post_pr_review.side_effect = [
            GitHubAPIError("422 Unprocessable Entity - line outside diff hunk", status_code=422),
            mock_resp,
        ]

        with patch("backend.orchestrator.nodes.GitHubClient") as mock_gh_cls, \
             patch("backend.orchestrator.nodes._save_review_record", new=AsyncMock()):
            mock_gh_cls.return_value.__aenter__.return_value = mock_client

            result = await post_review(state)

            assert result["review_posted"] is True
            assert result["github_review_id"] == 888
            assert result["publication_status"] == "posted"
            assert mock_client.post_pr_review.call_count == 2

    @pytest.mark.asyncio
    async def test_publication_failure_modeling(self):
        """Rate limits model retryable_failure; 404 models permanent_failure."""
        workflow_id = "acme/repo:42:sha99999"
        state = {
            "workflow_id": workflow_id,
            "repo_full_name": "acme/repo",
            "pr_number": 42,
            "head_commit_sha": "sha99999",
            "needs_human_review": False,
            "final_findings": [],
            "verdict": ReviewVerdict.APPROVE,
            "pr_diff": "",
            "allow_stub_diff": True,
        }

        mock_client = AsyncMock()
        mock_client.list_pr_reviews.return_value = []
        mock_client.post_pr_review.side_effect = GitHubRateLimitError("Rate limit exceeded", retry_after_seconds=60)

        with patch("backend.orchestrator.nodes.GitHubClient") as mock_gh_cls, \
             patch("backend.orchestrator.nodes._save_review_record", new=AsyncMock()):
            mock_gh_cls.return_value.__aenter__.return_value = mock_client

            res_rate = await post_review(state)
            assert res_rate["review_posted"] is False
            assert res_rate["publication_status"] == "retryable_failure"
            assert "Rate limited" in res_rate["publication_error"]

        # PR Not Found
        mock_client.post_pr_review.side_effect = GitHubNotFoundError("PR not found", status_code=404)
        with patch("backend.orchestrator.nodes.GitHubClient") as mock_gh_cls, \
             patch("backend.orchestrator.nodes._save_review_record", new=AsyncMock()):
            mock_gh_cls.return_value.__aenter__.return_value = mock_client

            res_404 = await post_review(state)
            assert res_404["review_posted"] is False
            assert res_404["publication_status"] == "permanent_failure"
            assert res_404["publication_error"] == "Pull request not found"
