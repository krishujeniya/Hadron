"""
tests/test_tenant_isolation_t04.py

Acceptance tests for T04:
Enforce workspace, repository, and installation isolation.
"""

from unittest.mock import AsyncMock, MagicMock
import pytest
from starlette.testclient import TestClient

from backend.auth.dependencies import get_current_principal, require_auth
from backend.auth.principal import Principal
from backend.main import app
from backend.security.rbac import Role


@pytest.fixture
def alice_principal():
    return Principal(
        id="alice",
        role=Role.REVIEWER,
        account="alice",
        tenant_id="alice",
        auth_method="session",
    )


@pytest.fixture
def admin_principal():
    return Principal(
        id="admin_user",
        role=Role.ADMIN,
        account="hadron-admin",
        tenant_id="hadron-admin",
        auth_method="api_key",
    )


@pytest.fixture(autouse=True)
def clean_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


class TestT04TenantIsolation:
    def test_tenant_cannot_list_another_account_reviews(self, alice_principal):
        """Alice cannot query reviews for account 'bob'."""
        app.dependency_overrides[get_current_principal] = lambda: alice_principal
        app.dependency_overrides[require_auth] = lambda: alice_principal

        client = TestClient(app)
        resp = client.get("/api/v1/reviews?account=bob")
        assert resp.status_code == 403
        assert "cannot access reviews for account 'bob'" in resp.json()["detail"]

    def test_tenant_cannot_list_another_repo_reviews(self, alice_principal):
        """Alice cannot query reviews for repo 'bob/secret'."""
        app.dependency_overrides[get_current_principal] = lambda: alice_principal
        app.dependency_overrides[require_auth] = lambda: alice_principal

        client = TestClient(app)
        resp = client.get("/api/v1/reviews?repo=bob/secret")
        assert resp.status_code == 403
        assert "outside your authorized workspace" in resp.json()["detail"]

    def test_tenant_cannot_view_another_workspace_review_detail(self, alice_principal, monkeypatch):
        """Alice cannot fetch review detail for bob/project."""
        app.dependency_overrides[get_current_principal] = lambda: alice_principal
        app.dependency_overrides[require_auth] = lambda: alice_principal

        mock_record = MagicMock()
        mock_record.repo_full_name = "bob/project"

        from unittest.mock import patch
        with patch("backend.api.reviews.get_review", new_callable=AsyncMock) as mock_get_review:
            mock_get_review.return_value = mock_record
            client = TestClient(app)
            resp = client.get("/api/v1/reviews/bob-review-123")
            assert resp.status_code == 403
            assert "belongs to another workspace" in resp.json()["detail"]

    def test_tenant_cannot_access_another_account_queue(self, alice_principal):
        """Alice cannot query the queue for account 'bob'."""
        app.dependency_overrides[get_current_principal] = lambda: alice_principal
        app.dependency_overrides[require_auth] = lambda: alice_principal

        client = TestClient(app)
        resp = client.get("/api/v1/queue?account=bob")
        assert resp.status_code == 403
        assert "cannot access queue for account 'bob'" in resp.json()["detail"]

    def test_tenant_cannot_access_another_account_hitl_queue(self, alice_principal):
        """Alice cannot query HITL queue for account 'bob'."""
        app.dependency_overrides[get_current_principal] = lambda: alice_principal
        app.dependency_overrides[require_auth] = lambda: alice_principal

        client = TestClient(app)
        resp = client.get("/api/v1/hitl/queue?account=bob")
        assert resp.status_code == 403
        assert "cannot access HITL queue for account 'bob'" in resp.json()["detail"]

    def test_tenant_cannot_view_another_workspace_hitl_item(self, alice_principal):
        """Alice cannot fetch HITL item belonging to bob/service."""
        app.dependency_overrides[get_current_principal] = lambda: alice_principal
        app.dependency_overrides[require_auth] = lambda: alice_principal

        mock_hitl_row = MagicMock()
        mock_hitl_row.repo_full_name = "bob/service"

        from unittest.mock import patch
        with patch("backend.api.hitl_router.get_hitl_review", new_callable=AsyncMock) as mock_get_hitl:
            mock_get_hitl.return_value = mock_hitl_row
            client = TestClient(app)
            resp = client.get("/api/v1/hitl/hitl-bob-456")
            assert resp.status_code == 403
            assert "belongs to another workspace" in resp.json()["detail"]

    def test_tenant_cannot_view_another_workspace_economics(self, alice_principal):
        """Alice cannot view cost breakdown for workflow on bob/repo."""
        app.dependency_overrides[get_current_principal] = lambda: alice_principal
        app.dependency_overrides[require_auth] = lambda: alice_principal

        client = TestClient(app)
        resp = client.get("/api/v1/economics/workflow/bob/repo:10:sha123")
        assert resp.status_code == 403
        assert "cannot view economics for another workspace" in resp.json()["detail"]

    def test_admin_can_access_across_workspaces(self, admin_principal):
        """Admin principal is not restricted by workspace filters."""
        app.dependency_overrides[get_current_principal] = lambda: admin_principal
        app.dependency_overrides[require_auth] = lambda: admin_principal

        from unittest.mock import patch
        with patch("backend.api.reviews.list_reviews", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = ([], 0)
            client = TestClient(app)
            resp = client.get("/api/v1/reviews?account=bob")
            assert resp.status_code == 200
