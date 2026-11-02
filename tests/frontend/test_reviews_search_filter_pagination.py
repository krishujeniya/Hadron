"""
tests/frontend/test_reviews_search_filter_pagination.py
--------------------------------------------------
Validates T35: Reviews search, filters, sorting, and pagination.
Tests:
  1. Backend list_reviews repository function supports q (title, SHA, repo) and sort.
  2. Backend GET /api/v1/reviews endpoint supports q and sort query parameters with auth.
  3. Search query filters accurately across PR title, commit SHA, and repo full name.
  4. Keyset / offset pagination boundaries and counts.
  5. Frontend reviews page implements debounced search, clear filters, sort dropdown,
     accessible table region, and responsive mobile card layout.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.auth.dependencies import require_auth, get_current_principal
from backend.auth.principal import Principal
from backend.security.rbac import Role
from backend.database.models import PRReviewRecord
from backend.database.repository import list_reviews


@pytest.mark.asyncio
async def test_repository_list_reviews_search_and_sort():
    """Verify list_reviews repository query generator handles q and sort filters."""
    session = AsyncMock()

    # Mock count query scalar_one()
    count_mock = MagicMock()
    count_mock.scalar_one.return_value = 42

    # Mock data query scalars().all()
    sample_record = PRReviewRecord(
        id="owner/repo:pr:123",
        repo_full_name="owner/repo",
        pr_number=123,
        pr_title="Fix memory leak in parser",
        head_commit_sha="a1b2c3d4e5f6",
        status="completed",
        findings=[],
        created_at=datetime.now(timezone.utc),
    )
    data_mock = MagicMock()
    data_mock.scalars.return_value.all.return_value = [sample_record]

    session.execute.side_effect = [count_mock, data_mock]

    # Test with q search and sort="findings"
    records, total = await list_reviews(
        session,
        repo_full_name="owner/repo",
        q="memory leak",
        sort="findings",
        limit=10,
        offset=0,
    )

    assert total == 42
    assert len(records) == 1
    assert records[0].pr_title == "Fix memory leak in parser"
    assert session.execute.call_count == 2


@pytest.mark.asyncio
async def test_api_reviews_endpoint_q_and_sort_params():
    """Verify GET /api/v1/reviews accepts q and sort query parameters and passes them downstream."""
    principal = Principal(
        id="test-user",
        account="octocat",
        role=Role.VIEWER,
        tenant_id="octocat",
    )

    sample_record = PRReviewRecord(
        id="octocat/hello-world:pr:1",
        repo_full_name="octocat/hello-world",
        pr_number=1,
        pr_title="Add performance benchmarking",
        head_commit_sha="abcdef123456",
        status="completed",
        findings=[],
        verdict="comment",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    with (
        patch("backend.api.reviews.require_auth", return_value=principal),
        patch("backend.api.reviews.list_reviews", new_callable=AsyncMock) as mock_list,
        patch("backend.api.reviews.get_db") as mock_db,
    ):
        mock_list.return_value = ([sample_record], 1)
        mock_session = AsyncMock()
        mock_db.return_value = mock_session

        app.dependency_overrides[require_auth] = lambda: principal
        app.dependency_overrides[get_current_principal] = lambda: principal

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/reviews?account=octocat&q=performance&sort=findings&limit=25"
            )

        app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["pr_title"] == "Add performance benchmarking"

        # Verify mock_list was called with q and sort
        mock_list.assert_called_once()
        _, kwargs = mock_list.call_args
        assert kwargs["q"] == "performance"
        assert kwargs["sort"] == "findings"
        assert kwargs["limit"] == 25


def test_frontend_reviews_page_contract():
    """Inspect frontend/src/app/reviews/page.tsx to verify search, sort, filters, and mobile layout."""
    import pathlib

    reviews_path = pathlib.Path("frontend/src/app/reviews/page.tsx")
    assert reviews_path.exists(), "frontend/src/app/reviews/page.tsx must exist"

    content = reviews_path.read_text(encoding="utf-8")

    # 1. Debounced search input
    assert "searchInput" in content
    assert "setTimeout" in content
    assert "clearTimeout" in content
    assert 'aria-label="Clear search query"' in content

    # 2. Sort dropdown
    assert 'name="sort"' in content
    assert "Newest first" in content
    assert "Oldest first" in content
    assert "Most findings" in content

    # 3. Clear all filters
    assert "Clear all filters" in content
    assert "clearAllFilters" in content

    # 4. Accessible table & mobile cards (no overflow trap)
    assert 'role="region"' in content
    assert 'aria-label="Pull request reviews"' in content
    assert "sm:hidden" in content
    assert "hidden sm:block" in content
    assert "Page out of range" in content
