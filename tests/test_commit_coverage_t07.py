"""
tests/test_commit_coverage_t07.py

Acceptance tests for T07:
Review an identified commit with complete, honest source coverage.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.models.enums import ReviewStatus, ReviewVerdict
from backend.orchestrator.nodes import (
    _build_review_summary,
    aggregate_results,
    build_context,
    post_review,
)
from backend.orchestrator.state import PRReviewState


def _make_agent_result(
    agent_type: str,
    verdict: str = "approve",
    confidence: float = 0.95,
    findings: list | None = None,
    success: bool = True,
) -> dict:
    return {
        "agent_type": agent_type,
        "success": success,
        "error_message": "" if success else "failed",
        "duration_seconds": 1.0,
        "findings": findings or [],
        "confidence": confidence,
        "per_verdict": verdict,
    }


def _make_clean_results() -> list[dict]:
    return [
        _make_agent_result("security", "approve", 0.95),
        _make_agent_result("quality", "approve", 0.95),
        _make_agent_result("test", "approve", 0.95),
        _make_agent_result("docs", "approve", 0.95),
    ]


@pytest.mark.asyncio
class TestT07CommitCoverage:
    async def test_github_fetch_failure_marks_diff_unavailable_and_escalates(self):
        """When GitHub fetch fails in non-demo mode, aggregate_results MUST NOT approve."""
        state: PRReviewState = {
            "workflow_id": "wf-err-1",
            "repo_full_name": "acme/repo",
            "pr_number": 10,
            "pr_title": "feat: test",
            "pr_body": "test PR",
            "pr_diff": "",
            "author_login": "alice",
            "head_commit_sha": "commit-sha-123",
            "base_branch": "main",
            "changed_files": [],
            "retrieved_context": "",
            "idempotency_key": "k1",
            "agent_results": _make_clean_results(),
            "verdict": None,
            "final_findings": [],
            "overall_confidence": 0.0,
            "needs_human_review": False,
            "human_review_reason": "",
            "status": ReviewStatus.QUEUED,
            "confidence_threshold": 0.7,
            "conflict_detected": False,
            "partial_review": False,
            "review_posted": False,
            "github_review_id": None,
            "threat_detected": False,
            "threat_reason": "",
            "source_coverage": {"complete": False, "truncation_reasons": ["GitHub 404 Not Found"]},
            "diff_unavailable": True,
            "is_empty_pr": False,
        }

        agg = await aggregate_results(state)
        assert agg["verdict"] == ReviewVerdict.NEEDS_HUMAN_REVIEW
        assert agg["needs_human_review"] is True
        assert "diff unavailable" in agg["human_review_reason"].lower()

    async def test_valid_empty_pr_is_distinguished_and_approved(self):
        """Valid empty PR (0 changed files) is distinguished from unavailable diff."""
        state: PRReviewState = {
            "workflow_id": "wf-empty-1",
            "repo_full_name": "acme/repo",
            "pr_number": 11,
            "pr_title": "docs: empty PR",
            "pr_body": "empty",
            "pr_diff": "",
            "author_login": "bob",
            "head_commit_sha": "commit-sha-empty",
            "base_branch": "main",
            "changed_files": [],
            "retrieved_context": "",
            "idempotency_key": "k2",
            "agent_results": _make_clean_results(),
            "verdict": None,
            "final_findings": [],
            "overall_confidence": 0.0,
            "needs_human_review": False,
            "human_review_reason": "",
            "status": ReviewStatus.QUEUED,
            "confidence_threshold": 0.7,
            "conflict_detected": False,
            "partial_review": False,
            "review_posted": False,
            "github_review_id": None,
            "threat_detected": False,
            "threat_reason": "",
            "source_coverage": {
                "complete": True,
                "files_received": [],
                "files_omitted": [],
                "truncation_reasons": [],
            },
            "diff_unavailable": False,
            "is_empty_pr": True,
        }

        agg = await aggregate_results(state)
        assert agg["verdict"] == ReviewVerdict.APPROVE
        assert agg["needs_human_review"] is False

    async def test_source_coverage_identifies_omitted_assets(self):
        """build_context categorizes lockfiles, binaries, and minified bundles in files_omitted."""
        mock_meta = MagicMock()
        mock_meta.title = "Add assets"
        mock_meta.body = "description"
        mock_meta.author_login = "dev"
        mock_meta.head_sha = "sha-999"
        mock_meta.base_branch = "main"
        mock_meta.changed_files_count = 4

        mock_files = [
            {"filename": "src/app.py"},
            {"filename": "package-lock.json"},
            {"filename": "assets/logo.png"},
            {"filename": "dist/bundle.min.js"},
        ]

        with patch("backend.orchestrator.nodes.GitHubClient") as mock_client_cls, \
             patch("backend.orchestrator.nodes.retrieve_context_for_diff", new_callable=AsyncMock) as mock_rag:
            mock_rag.return_value = ""
            client_inst = AsyncMock()
            client_inst.get_pr_metadata.return_value = mock_meta
            client_inst.get_pr_diff.return_value = "+# app code"
            client_inst.get_pr_files.return_value = mock_files
            mock_client_cls.return_value.__aenter__.return_value = client_inst

            initial_state = {
                "workflow_id": "wf-cov-1",
                "repo_full_name": "acme/repo",
                "pr_number": 22,
                "status": ReviewStatus.QUEUED,
            }

            res = await build_context(initial_state)

            assert res["diff_unavailable"] is False
            assert res["is_empty_pr"] is False
            source_cov = res["source_coverage"]
            assert source_cov["complete"] is True
            assert "src/app.py" in source_cov["files_received"]

            omitted_names = [o["filename"] for o in source_cov["files_omitted"]]
            assert "package-lock.json" in omitted_names
            assert "assets/logo.png" in omitted_names
            assert "dist/bundle.min.js" in omitted_names

    async def test_review_summary_identifies_exact_sha_and_coverage(self):
        """_build_review_summary visibly states reviewed SHA and excluded files."""
        state = {
            "verdict": ReviewVerdict.APPROVE,
            "final_findings": [],
            "overall_confidence": 0.95,
            "agent_results": _make_clean_results(),
            "workflow_id": "wf-sha-test",
            "head_commit_sha": "d3adb33f123456",
            "base_branch": "feature-branch",
            "source_coverage": {
                "files_received": ["src/main.py", "package-lock.json"],
                "files_omitted": [{"filename": "package-lock.json", "reason": "lockfile"}],
            },
        }

        summary = _build_review_summary(state)
        assert "Commit Reviewed:** `d3adb33f123456`" in summary
        assert "Base Branch:** `feature-branch`" in summary
        assert "Coverage:** 2 file(s) evaluated" in summary
        assert "Exclusions:** `package-lock.json` (lockfile)" in summary

    async def test_post_review_detects_superseded_head_commit(self):
        """post_review aborts publication if head SHA has changed (force push or new commit)."""
        mock_meta = MagicMock()
        mock_meta.head_sha = "new-head-sha-789"  # Differs from state head_commit_sha

        with patch("backend.orchestrator.nodes.GitHubClient") as mock_client_cls, \
             patch("backend.orchestrator.nodes.get_settings") as mock_settings:
            settings_obj = MagicMock()
            settings_obj.app_env = "production"
            settings_obj.review_body_max_characters = 65536
            mock_settings.return_value = settings_obj

            client_inst = AsyncMock()
            client_inst.get_pr_metadata.return_value = mock_meta
            mock_client_cls.return_value.__aenter__.return_value = client_inst

            state = {
                "workflow_id": "wf-superseded-1",
                "repo_full_name": "acme/repo",
                "pr_number": 33,
                "head_commit_sha": "old-head-sha-123",
                "base_branch": "main",
                "verdict": ReviewVerdict.APPROVE,
                "final_findings": [],
                "needs_human_review": False,
                "human_review_reason": "",
                "status": ReviewStatus.POSTING,
                "pr_diff": "+code",
            }

            res = await post_review(state)
            assert res["review_posted"] is False
            assert res.get("superseded") is True
            # post_pr_review should NOT have been called
            client_inst.post_pr_review.assert_not_called()
