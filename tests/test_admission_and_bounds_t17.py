# tests/test_admission_and_bounds_t17.py
#
# Verification tests for Task T17:
# Bound ingress, work, and provider consumption.

import gzip
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

from backend.config.settings import Settings, get_settings
from backend.core.exceptions import (
    QueueOverloadedError,
    TenantConcurrencyLimitError,
)
from backend.job_queue.arq_worker import enqueue_review_job
from backend.main import app
from backend.memory.redis_client import redis_client
from backend.orchestrator.nodes import build_context
from backend.security.admission import (
    apply_rate_limit,
    check_webhook_rate_limit,
    get_trusted_client_ip,
)


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def reset_in_memory_redis():
    redis_client._in_memory_fallback.clear()
    yield
    redis_client._in_memory_fallback.clear()


def test_oversized_headers_rejected_with_431(client):
    """Requests with headers exceeding 64KB fail immediately with HTTP 431."""
    large_header_val = "x" * 70_000
    resp = client.get("/health/live", headers={"X-Large-Header": large_header_val})
    assert resp.status_code == 431
    assert "Request header fields exceed maximum limit" in resp.json()["detail"]


def test_oversized_api_body_rejected_with_413(client):
    """REST API endpoints reject payloads exceeding 2MB limit with HTTP 413."""
    oversized_body = "a" * (3 * 1024 * 1024)  # 3 MB
    resp = client.post(
        "/api/v1/hitl/123e4567-e89b-12d3-a456-426614174000/decision",
        content=oversized_body,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 413
    assert "exceeds limit" in resp.json()["detail"].lower()


def test_decompression_bomb_guard_rejects_with_413(client):
    """Gzip-compressed payloads exceeding decompressed size bounds are rejected with HTTP 413."""
    # Compress 5MB of repeated zeros into a small gzip blob (< 10KB)
    raw_zeros = b"0" * (5 * 1024 * 1024)
    compressed_body = gzip.compress(raw_zeros)

    # Sending compressed payload to REST API endpoint (2MB max)
    resp = client.post(
        "/api/v1/hitl/123/decision",
        content=compressed_body,
        headers={
            "Content-Type": "application/json",
            "Content-Encoding": "gzip",
        },
    )
    assert resp.status_code == 413
    assert "decompression bomb" in resp.json()["detail"].lower()


def test_trusted_client_ip_extraction():
    """Client IP extraction does not trust X-Forwarded-For unless proxy is allowlisted."""
    headers = Headers({"x-forwarded-for": "203.0.113.195, 198.51.100.1"})

    # 1. Untrusted proxy: ignores X-Forwarded-For, returns direct client host
    ip_untrusted = get_trusted_client_ip(headers, "192.0.2.1", trusted_proxies="127.0.0.1")
    assert ip_untrusted == "192.0.2.1"

    # 2. Trusted proxy: resolves rightmost untrusted client IP
    ip_trusted = get_trusted_client_ip(headers, "127.0.0.1", trusted_proxies="127.0.0.1")
    assert ip_trusted == "198.51.100.1"


@pytest.mark.asyncio
async def test_rate_limiter_blocks_and_provides_retry_after():
    """Rate limiter enforces quotas and provides actionable Retry-After."""
    from fastapi import HTTPException

    # Consume quota
    for _ in range(5):
        await apply_rate_limit(key="tenant-alpha", max_per_minute=5, category="test")

    # 6th request triggers 429
    with pytest.raises(HTTPException) as exc_info:
        await apply_rate_limit(key="tenant-alpha", max_per_minute=5, category="test")
    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers
    assert int(exc_info.value.headers["Retry-After"]) > 0


@pytest.mark.asyncio
async def test_authenticated_webhook_policy_throttles_by_repo_not_ip():
    """Authenticated webhooks are throttled per repository rather than by GitHub shared IP."""
    from fastapi import HTTPException

    repo = "octocat/hello-world"
    for _ in range(3):
        await check_webhook_rate_limit(repo)

    with patch.object(redis_client, "check_rate_limit", new=AsyncMock(return_value=(False, 45, 61))):
        with pytest.raises(HTTPException) as exc_info:
            await check_webhook_rate_limit(repo)
        assert exc_info.value.status_code == 429
        assert exc_info.value.headers["Retry-After"] == "45"


@pytest.mark.asyncio
async def test_queue_depth_backpressure_enforced():
    """ARQ queue backpressure raises QueueOverloadedError and returns HTTP 503."""
    with patch.object(redis_client, "check_idempotency_key", new=AsyncMock(return_value=False)), \
         patch.object(redis_client, "get_queue_depth", new=AsyncMock(return_value=150)), \
         patch.object(redis_client, "get_tenant_active", new=AsyncMock(return_value=0)):

        with pytest.raises(QueueOverloadedError) as exc_info:
            await enqueue_review_job(
                workflow_id="wf-overloaded",
                input_data={"repo_full_name": "org/repo"},
            )
        assert exc_info.value.queue_depth == 150
        assert exc_info.value.retry_after == 30


@pytest.mark.asyncio
async def test_tenant_concurrency_limit_prevents_starvation():
    """Noisy tenant exceeding max concurrent reviews is throttled to prevent starving others."""
    with patch.object(redis_client, "check_idempotency_key", new=AsyncMock(return_value=False)), \
         patch.object(redis_client, "get_queue_depth", new=AsyncMock(return_value=10)), \
         patch.object(redis_client, "get_tenant_active", new=AsyncMock(return_value=4)):

        with pytest.raises(TenantConcurrencyLimitError) as exc_info:
            await enqueue_review_job(
                workflow_id="wf-noisy",
                input_data={"repo_full_name": "noisy-tenant/repo"},
            )
        assert exc_info.value.tenant_id == "noisy-tenant"
        assert exc_info.value.retry_after == 30


@pytest.mark.asyncio
async def test_webhook_router_handles_backpressure_and_cleans_idempotency(client):
    """
    When webhook receiver hits queue backpressure, it returns HTTP 503 with Retry-After
    and ensures the idempotency key is deleted so GitHub retry succeeds.
    """
    secret = "test-webhook-secret"
    import hashlib
    import hmac
    import json

    payload = {
        "action": "opened",
        "number": 1,
        "repository": {
            "full_name": "owner/repo",
            "name": "repo",
            "clone_url": "https://github.com/owner/repo.git",
            "owner": {"login": "owner"},
        },
        "pull_request": {
            "number": 1,
            "title": "Fix bug",
            "body": "Fixes issue",
            "user": {"login": "dev"},
            "head": {"sha": "0123456789abcdef0123456789abcdef01234567", "ref": "feat"},
            "base": {"ref": "main"},
            "diff_url": "https://api.github.com/diff",
        },
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()

    cfg = Settings(github_webhook_secret=secret)
    app.dependency_overrides[get_settings] = lambda: cfg

    mock_del_key = AsyncMock()
    try:
        with patch("backend.webhook_receiver.router.enqueue_review_job", side_effect=QueueOverloadedError("Overloaded", queue_depth=120, retry_after=45)), \
             patch.object(redis_client, "delete_idempotency_key", new=mock_del_key):

            resp = client.post(
                "/webhook/github",
                content=raw_body,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": sig,
                    "X-GitHub-Event": "pull_request",
                    "X-GitHub-Delivery": "del-12345",
                },
            )
            assert resp.status_code == 503
            assert resp.headers.get("Retry-After") == "45"
            assert "Queue capacity exceeded" in resp.json()["detail"]
            mock_del_key.assert_awaited_once()
    finally:
        app.dependency_overrides.pop(get_settings, None)


@pytest.mark.asyncio
async def test_build_context_bounds_diff_and_file_counts():
    """build_context truncates oversized diffs (>500KB) and caps file count to 100."""
    state = {
        "workflow_id": "wf-bounds-test",
        "repo_full_name": "owner/repo",
        "pr_number": 42,
        "is_demo": True,
        "pr_diff": "diff --git a/file.py\n+content\n" * 40_000,  # ~1.2 MB
        "pr_files": [{"filename": f"src/file_{i}.py"} for i in range(150)],  # 150 files
        "pr_title": "Huge PR",
        "author_login": "alice",
    }

    res = await build_context(state)
    coverage = res["source_coverage"]

    # File count is bounded to 100
    assert len(coverage["files_received"]) == 100
    assert len(coverage["files_omitted"]) == 50
    assert any("file_limit_exceeded" in f["reason"] for f in coverage["files_omitted"])

    # Diff is bounded
    assert len(res["pr_diff"]) <= 500_500
    assert "... [DIFF TRUNCATED" in res["pr_diff"]

    # Coverage complete is False due to bounds
    assert coverage["complete"] is False
    assert any("truncated" in r.lower() for r in coverage["truncation_reasons"])
