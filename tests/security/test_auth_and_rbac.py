"""
tests/security/test_auth_and_rbac.py

Comprehensive regression test suite for T02 and T03:
  - Route inventory verification (deny-by-default on all protected endpoints)
  - Anonymous request rejection (HTTP 401)
  - Anti-forgery (untrusted X-Role headers and spoofed reviewer IDs rejected)
  - Role hierarchy checks (VIEWER vs REVIEWER vs ADMIN)
  - OAuth state verification, anti-CSRF, and session lifecycle (/me, /logout)
"""

import sys
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")
os.environ.setdefault("API_KEY", "valid-test-key-12345")

from backend.config.settings import get_settings
get_settings.cache_clear()

import backend.main as _main_module
from backend.auth.session_store import session_store
from backend.security.rbac import Role


@pytest.fixture
def client():
    """TestClient with mocked background infrastructure services."""
    from contextlib import ExitStack
    with ExitStack() as stack:
        stack.enter_context(patch.object(_main_module.redis_client, "connect", new=AsyncMock()))
        stack.enter_context(patch.object(_main_module.redis_client, "disconnect", new=AsyncMock()))
        stack.enter_context(patch.object(_main_module, "init_db", new=AsyncMock()))
        stack.enter_context(patch.object(_main_module, "ensure_collection", new=AsyncMock(return_value=True)))
        stack.enter_context(patch.object(_main_module, "init_tiger_schema", new=AsyncMock(return_value=True)))
        stack.enter_context(patch.object(session_store, "_get_redis_pool", new=AsyncMock(return_value=None)))
        with TestClient(_main_module.app, raise_server_exceptions=False) as c:
            yield c


class TestT02RouteInventoryAndAuthentication:
    """Verify deny-by-default and strict authentication on all protected routes."""

    PUBLIC_PATHS = {
        "/",
        "/health",
        "/health/live",
        "/health/ready",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/webhook/github",
        "/api/v1/auth/github/login",
        "/api/v1/auth/github/callback",
        "/api/v1/auth/connect",
    }

    def test_route_inventory_coverage(self):
        """Audit every registered route in FastAPI app to confirm deny-by-default protection."""
        from fastapi.routing import APIRoute
        app_routes = [r for r in _main_module.app.routes if isinstance(r, APIRoute)]
        assert len(app_routes) > 0, "No API routes found"

        unprotected = []
        for route in app_routes:
            if route.path in self.PUBLIC_PATHS:
                continue

            # Check if route or router has require_auth, require_permission, or get_current_principal in dependencies
            dep_names = [d.call.__name__ for d in route.dependant.dependencies if hasattr(d, "call") and hasattr(d.call, "__name__")]
            all_subdeps = []
            for d in route.dependant.dependencies:
                for sub in getattr(d, "dependencies", []):
                    if hasattr(sub, "call") and hasattr(sub.call, "__name__"):
                        all_subdeps.append(sub.call.__name__)

            combined = set(dep_names + all_subdeps)
            has_auth = any(
                name in combined
                for name in ("require_auth", "require_permission", "get_current_principal", "_enforce_permission")
            )
            if not has_auth:
                unprotected.append(f"{route.methods} {route.path}")

        assert not unprotected, f"Unprotected routes detected without authentication dependency: {unprotected}"

    def test_anonymous_requests_rejected_with_401(self, client):
        """Anonymous access to protected endpoints must return 401 Unauthorized."""
        protected_urls = [
            "/api/v1/reviews",
            "/api/v1/reviews/test%2Frepo%3A1%3Asha",
            "/api/v1/queue",
            "/api/v1/hitl/queue",
            "/api/v1/hitl/test-id",
            "/api/v1/economics/summary",
            "/api/v1/economics/budget",
            "/api/v1/economics/timeseries",
            "/api/v1/economics/agent-health",
            "/api/v1/economics/daily-summary",
            "/api/v1/auth/repos?account=test",
        ]
        for url in protected_urls:
            resp = client.get(url)
            assert resp.status_code == 401, f"Expected 401 for anonymous GET {url}, got {resp.status_code}"

    def test_forged_x_role_header_rejected(self, client):
        """Client supplying X-Role: admin anonymously must still receive 401 Unauthorized."""
        resp = client.get("/api/v1/economics/summary", headers={"X-Role": "admin"})
        assert resp.status_code == 401

        resp = client.post("/api/v1/hitl/queue/rebuild", headers={"X-Role": "admin"})
        assert resp.status_code == 401

    def test_invalid_api_key_rejected_with_403(self, client):
        """Client supplying incorrect X-API-Key must receive 403 Forbidden."""
        resp = client.get("/api/v1/reviews", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 403

    def test_valid_api_key_accepted(self, client):
        """Valid X-API-Key grants access."""
        with patch("backend.api.reviews.list_reviews", new=AsyncMock(return_value=([], 0))):
            resp = client.get("/api/v1/reviews", headers={"X-API-Key": "valid-test-key-12345"})
            assert resp.status_code == 200


class TestT02RoleAuthorizationAndIdentityDerivation:
    """Verify role enforcement and server-derived reviewer identity."""

    @pytest.mark.asyncio
    async def test_viewer_cannot_mutate_or_escalate(self, client):
        """A user with Role.VIEWER cannot submit reviews or escalate using X-Role header."""
        session = await session_store.create_session(
            user_id="viewer_bob",
            role=Role.VIEWER,
            account="bob",
        )

        cookies = {"hadron_session": session.session_id}

        # Attempt to submit decision with viewer role
        resp = client.post(
            "/api/v1/hitl/hitl-123/decision",
            json={"human_verdict": "APPROVE", "reason": "Looks good", "reviewer_id": "bob"},
            cookies=cookies,
            headers={"X-CSRF-Token": session.csrf_token},
        )
        assert resp.status_code == 403, f"Expected 403 for viewer submitting review, got {resp.status_code}"

        # Attempt to forge role escalation via header
        resp = client.post(
            "/api/v1/hitl/hitl-123/decision",
            json={"human_verdict": "APPROVE", "reason": "Looks good", "reviewer_id": "bob"},
            cookies=cookies,
            headers={"X-Role": "admin", "X-CSRF-Token": session.csrf_token},
        )
        assert resp.status_code == 403, "Untrusted X-Role header must not grant escalation"

    @pytest.mark.asyncio
    async def test_server_derived_reviewer_identity(self, client):
        """Reviewer identity is strictly derived from the verified session, ignoring spoofed body."""
        session = await session_store.create_session(
            user_id="alice_verified",
            role=Role.REVIEWER,
            account="alice",
        )

        mock_dispute_result = MagicMock(
            hitl_review_id="hitl-999",
            previous_status="pending",
            new_status="resolved",
            human_verdict="APPROVE",
            posted_to_github=False,
            feedback_id="fb-1",
        )

        captured_request = None
        async def mock_resolve(session, github_client, request):
            nonlocal captured_request
            captured_request = request
            return mock_dispute_result

        mock_hitl_row = MagicMock(repo_full_name="alice/repo")
        with patch("backend.api.hitl_router.get_hitl_review", new=AsyncMock(return_value=mock_hitl_row)), \
             patch("backend.api.hitl_router.resolve_dispute", side_effect=mock_resolve), \
             patch("backend.integrations.github_client.GitHubClient.__aenter__", return_value=AsyncMock()):
            resp = client.post(
                "/api/v1/hitl/hitl-999/decision",
                json={
                    "human_verdict": "APPROVE",
                    "reason": "Verified safe",
                    "reviewer_id": "malicious_spoofed_eve",  # Attacker tries to impersonate Eve
                },
                cookies={"hadron_session": session.session_id},
                headers={"X-CSRF-Token": session.csrf_token},
            )
            assert resp.status_code == 200
            assert captured_request is not None
            # Must be alice_verified, NOT malicious_spoofed_eve
            assert captured_request.reviewer_id == "alice_verified"


class TestT03SessionManagementAndOAuthFlow:
    """Verify session creation, CSRF protection, /me, /logout, and OAuth lifecycle."""

    @pytest.mark.asyncio
    async def test_session_lifecycle_me_and_logout(self, client):
        """Test full login session, profile introspection via /me, and logout revocation."""
        session = await session_store.create_session(
            user_id="developer_carol",
            role=Role.REVIEWER,
            account="carol",
        )

        cookies = {"hadron_session": session.session_id}

        # 1. /me introspection
        resp = client.get("/api/v1/auth/me", cookies=cookies)
        assert resp.status_code == 200
        profile = resp.json()
        assert profile["login"] == "developer_carol"
        assert profile["authenticated"] is True
        assert profile["token"] is None  # Never leak token

        # 2. Cross-origin mutation blocked by CSRF
        resp = client.post(
            "/api/v1/auth/logout",
            cookies=cookies,
            headers={"Sec-Fetch-Site": "cross-site"},
        )
        assert resp.status_code == 403

        # 3. Legitimate logout
        resp = client.post(
            "/api/v1/auth/logout",
            cookies=cookies,
            headers={"X-CSRF-Token": session.csrf_token},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "logged_out"

        # 4. Subsequent access with revoked session is rejected (401)
        resp = client.get("/api/v1/auth/me", cookies=cookies)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_oauth_state_is_single_use(self, client):
        """Test OAuth state expiration, mismatch, and StrictMode duplicate consumption."""
        # 1. Unknown state or unconfigured client fails closed
        resp = client.post("/api/v1/auth/github/callback", json={"code": "123", "state": "unknown-state"})
        assert resp.status_code in (400, 403)

        # 2. Valid state consumed
        state = "test-strict-mode-state"
        await session_store.save_oauth_state(state, data={"redirect_uri": "/reviews"}, ttl_seconds=60)

        # First consumption succeeds
        res1 = await session_store.verify_and_consume_oauth_state(state)
        assert res1 == {"redirect_uri": "/reviews"}

        # The UI deduplicates exchanges; server state must reject replay.
        res2 = await session_store.verify_and_consume_oauth_state(state)
        assert res2 is None

    @pytest.mark.asyncio
    async def test_oauth_state_is_bound_to_initiating_browser(self, client):
        from backend.config.settings import Settings
        configured = Settings(_env_file=None, github_client_id="test-client", github_client_secret="test-secret")
        _main_module.app.dependency_overrides[get_settings] = lambda: configured
        try:
            await session_store.save_oauth_state("browser-bound-state", data={})
            with patch("backend.api.auth_router.httpx.AsyncClient") as http:
                response = client.post("/api/v1/auth/github/callback", json={"code": "code", "state": "browser-bound-state"})
            assert response.status_code == 403
            http.assert_not_called()
            assert await session_store.verify_and_consume_oauth_state("browser-bound-state") == {}
        finally:
            _main_module.app.dependency_overrides.pop(get_settings, None)

    def test_username_alone_cannot_grant_workspace_access(self, client):
        """Knowing a handle must not grant access to that user's private reviews."""
        with patch.object(session_store, "create_session", new_callable=AsyncMock) as create:
            resp = client.post("/api/v1/auth/connect", json={"account": "victim"})
        assert resp.status_code == 401
        assert "hadron_session" not in resp.cookies
        create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cookie_mutation_requires_csrf_token(self, client):
        session = await session_store.create_session(user_id="alice", role=Role.REVIEWER)
        cookies = {"hadron_session": session.session_id}
        resp = client.post("/api/v1/auth/logout", cookies=cookies)
        assert resp.status_code == 403
        assert await session_store.get_session(session.session_id) is not None

    @pytest.mark.asyncio
    async def test_repos_cannot_use_service_token_for_another_workspace(self, client):
        session = await session_store.create_session(user_id="alice", role=Role.REVIEWER)
        with patch("backend.api.auth_router.httpx.AsyncClient") as http:
            resp = client.get("/api/v1/auth/repos?account=victim", cookies={"hadron_session": session.session_id})
        assert resp.status_code == 403
        http.assert_not_called()

    def test_invalid_pat_never_falls_back_to_viewer(self, client):
        response = MagicMock(status_code=401)
        http = AsyncMock()
        http.get.return_value = response
        context = AsyncMock()
        context.__aenter__.return_value = http
        with patch("backend.api.auth_router.httpx.AsyncClient", return_value=context), patch.object(session_store, "create_session", new_callable=AsyncMock) as create:
            resp = client.post("/api/v1/auth/connect", json={"account": "victim", "token": "invalid-pat"})
        assert resp.status_code == 401
        create.assert_not_awaited()


@pytest.mark.asyncio
async def test_shared_revocation_overrides_local_session_cache():
    from backend.auth.session_store import SessionStore
    store = SessionStore()
    pool = AsyncMock()
    with patch.object(store, "_get_redis_pool", new=AsyncMock(return_value=pool)):
        session = await store.create_session(user_id="alice")
        # A different application instance revoked the Redis key.
        pool.get.return_value = None
        assert await store.get_session(session.session_id) is None
        assert session.session_id not in store._sessions


@pytest.mark.asyncio
async def test_shared_oauth_state_uses_atomic_consumption():
    import json
    import time
    from backend.auth.session_store import SessionStore
    store = SessionStore()
    pool = AsyncMock()
    pool.getdel.side_effect = [json.dumps({"expires_at": time.time() + 60, "data": {"redirect_uri": "https://hadron.vercel.app/auth/callback"}}), None]
    with patch.object(store, "_get_redis_pool", new=AsyncMock(return_value=pool)):
        assert await store.verify_and_consume_oauth_state("state") is not None
        assert await store.verify_and_consume_oauth_state("state") is None
    assert pool.getdel.await_count == 2


def test_redirect_rejects_arbitrary_hosting_tenants():
    from backend.api.auth_router import _validate_redirect_uri
    from backend.config.settings import Settings
    from fastapi import HTTPException
    settings = Settings(_env_file=None, cors_origins="https://hadron.vercel.app")
    with pytest.raises(HTTPException):
        _validate_redirect_uri("https://attacker.vercel.app/auth/callback", settings)
    assert _validate_redirect_uri("https://hadron.vercel.app/auth/callback", settings)
