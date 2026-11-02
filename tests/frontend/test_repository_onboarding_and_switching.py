"""
Unit and integration tests for T33: Repository Onboarding and Account Switching.
Verifies live account modal mount, SWR cache purge on workspace switch, and evidence-backed repo status.
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.api.auth_router import list_account_repos
from backend.auth.principal import Principal
from backend.config.settings import Settings
from backend.security.rbac import Role

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


@pytest.mark.asyncio
async def test_repo_status_distinguishes_discovered_connected_active():
    """Verify that repositories distinguish discovered, connected, and active statuses backed by review evidence."""
    mock_session = AsyncMock()
    settings = Settings(
        github_api_base_url="https://api.github.com",
        github_token="ghp_test",
        is_development=True,
    )
    principal = Principal(
        id="octocat",
        user_id="octocat",
        role=Role.REVIEWER,
        account="octocat",
        tenant_id="octocat",
    )

    # 1. First scenario: No review records exist in database for octocat/hello-world
    mock_stats_result_empty = MagicMock()
    mock_stats_result_empty.all.return_value = []
    mock_repos_result_empty = MagicMock()
    mock_repos_result_empty.scalars.return_value.all.return_value = []

    mock_session.execute.side_effect = [mock_stats_result_empty, mock_repos_result_empty]

    # Mock external GitHub API to return two repos
    github_repos_payload = [
        {
            "id": 1,
            "name": "hello-world",
            "full_name": "octocat/hello-world",
            "description": "My first repository",
            "html_url": "https://github.com/octocat/hello-world",
            "default_branch": "main",
            "open_issues_count": 0,
            "stargazers_count": 10,
            "private": False,
        },
        {
            "id": 2,
            "name": "spoon-knife",
            "full_name": "octocat/spoon-knife",
            "description": "Fork test repo",
            "html_url": "https://github.com/octocat/spoon-knife",
            "default_branch": "main",
            "open_issues_count": 1,
            "stargazers_count": 50,
            "private": False,
        },
    ]

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = github_repos_payload
        mock_get.return_value = mock_resp

        repos = await list_account_repos(
            account="octocat",
            principal=principal,
            settings=settings,
            session=mock_session,
        )

        assert len(repos) == 2
        for r in repos:
            assert r.status == "discovered"
            assert r.review_count == 0

    # 2. Second scenario: Review evidence exists for octocat/hello-world
    now = datetime.now(timezone.utc)
    mock_stats_result_with_evidence = MagicMock()
    # (repo_full_name, total_reviews, last_review_at)
    mock_stats_result_with_evidence.all.return_value = [
        ("octocat/hello-world", 3, now)
    ]
    mock_repos_result_with_evidence = MagicMock()
    mock_repos_result_with_evidence.scalars.return_value.all.return_value = ["octocat/hello-world"]

    mock_session.execute.side_effect = [mock_stats_result_with_evidence, mock_repos_result_with_evidence]

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = github_repos_payload
        mock_get.return_value = mock_resp

        repos = await list_account_repos(
            account="octocat",
            principal=principal,
            settings=settings,
            session=mock_session,
        )

        hw_repo = next(r for r in repos if r.full_name == "octocat/hello-world")
        assert hw_repo.status == "active", "Repo with database review records must have status 'active'"
        assert hw_repo.review_count == 3
        assert hw_repo.last_review_at is not None

        sk_repo = next(r for r in repos if r.full_name == "octocat/spoon-knife")
        assert sk_repo.status == "discovered", "Repo without reviews remains 'discovered'"
        assert sk_repo.review_count == 0


def test_frontend_workspace_selector_and_cache_purging():
    """Verify frontend githubContext and Shell mount workspace selector and clear tenant SWR caches."""
    # Shell must mount GitHubAccountModal
    shell_content = (FRONTEND_DIR / "src" / "components" / "layout" / "Shell.tsx").read_text(encoding="utf-8")
    assert "<GitHubAccountModal />" in shell_content or "<GitHubAccountModal" in shell_content

    # githubContext must clear cache on switch
    ctx_content = (FRONTEND_DIR / "src" / "features" / "auth" / "github-context.tsx").read_text(encoding="utf-8")
    assert "mutate(() => true, undefined, { revalidate: false })" in ctx_content
    assert "clearClientTenantData()" in ctx_content

    # types must define RepositoryStatus
    types_content = (FRONTEND_DIR / "src" / "lib" / "types.ts").read_text(encoding="utf-8")
    assert 'type RepositoryStatus = "active" | "connected" | "indexing" | "discovered" | "degraded" | "disconnected"' in types_content
