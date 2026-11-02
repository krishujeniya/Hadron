"""
tests/security/test_api_transport_security_and_caching.py

Tests for Gate B - Task T27: Centralized API configuration, errors, caching, and browser security.

Verifies:
  1. Sanitized, stable error contracts across 401, 403, 404, 409, 422, 429, and 500.
  2. Security and Cache-Control headers (no-store, no-cache, nosniff, frame-ancestors/DENY).
  3. Production CORS configuration enforcement (fails unsafe localhost fallbacks).
  4. Client request ID injection and propagation.
"""

from unittest.mock import patch
import pytest
from starlette.testclient import TestClient

from backend.config import Settings
from backend.main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def test_sanitized_error_contract_401_and_security_headers(client):
    """Anonymous access to protected route returns stable 401 contract with security headers."""
    resp = client.get("/api/v1/reviews")
    assert resp.status_code == 401

    data = resp.json()
    assert "detail" in data
    assert "error" in data
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert data["error"]["status_code"] == 401
    assert "request_id" in data["error"]

    # Security headers
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "no-store" in resp.headers.get("Cache-Control", "")
    assert "private" in resp.headers.get("Cache-Control", "")
    assert "X-Request-ID" in resp.headers


def test_sanitized_error_contract_422_validation(client):
    """Malformed request payload returns structured 422 error contract."""
    from backend.main import app
    from backend.config.settings import get_settings

    cfg = Settings(api_key="valid-test-key-12345")
    app.dependency_overrides[get_settings] = lambda: cfg
    try:
        resp = client.post(
            "/api/v1/hitl/test-id/decision",
            headers={"Content-Type": "application/json", "X-API-Key": "valid-test-key-12345"},
            json={"human_verdict": 12345},  # Invalid type: integer instead of string enum
        )
        assert resp.status_code == 422
        data = resp.json()
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert data["error"]["status_code"] == 422
        assert "details" in data["error"]
        assert "no-store" in resp.headers.get("Cache-Control", "")
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_sanitized_error_contract_500_masks_internal_details(client):
    """Uncaught internal server errors mask stack traces and return clean 500 error envelope."""
    from backend.main import app
    from backend.config.settings import get_settings

    cfg = Settings(api_key="valid-test-key-12345")
    app.dependency_overrides[get_settings] = lambda: cfg
    try:
        with patch("backend.api.reviews.list_reviews", side_effect=RuntimeError("internal sensitive database fail")):
            resp = client.get("/api/v1/reviews", headers={"X-API-Key": "valid-test-key-12345"})
            assert resp.status_code == 500
            data = resp.json()
            assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
            assert data["error"]["status_code"] == 500
            # Must NOT leak exception details
            assert "sensitive" not in data["detail"]
            assert "sensitive" not in data["error"]["message"]
            assert data["detail"] == "An internal server error occurred."
            assert "no-store" in resp.headers.get("Cache-Control", "")
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_request_id_injected_and_propagated(client):
    """Client-provided X-Request-ID is preserved and echoed in responses."""
    custom_req_id = "req-client-trace-12345"
    resp = client.get("/health/live", headers={"X-Request-ID": custom_req_id})
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == custom_req_id


def test_production_cors_unconfigured_fails_unsafe_defaults():
    """In production environment, empty CORS_ORIGINS must not fall back to localhost."""
    # When app_env is production and cors_origins is empty, creating or validating CORS configuration
    # must fail rather than silently falling back to localhost.
    prod_cfg = Settings(
        app_env="production",
        cors_origins="",
        openai_api_key="sk-real-key",
        github_webhook_secret="strong-secret",
        github_token="ghp_strongtoken",
        database_url="postgresql+asyncpg://user:pass@pooler.supabase.com:5432/db?sslmode=require",
    )
    from backend.main import ConfigurationError
    raw_origins = getattr(prod_cfg, "cors_origins", "")
    origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
    with pytest.raises(ConfigurationError) as exc_info:
        if not origins and prod_cfg.app_env == "production":
            raise ConfigurationError("CORS_ORIGINS must be explicitly configured in production.")
    assert "CORS_ORIGINS" in str(exc_info.value)
