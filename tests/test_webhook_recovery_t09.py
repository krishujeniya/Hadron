"""
tests/test_webhook_recovery_t09.py

Acceptance tests for T09:
Make webhook receipt and enqueue recoverable.
"""

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from starlette.testclient import TestClient

from backend.config.settings import Settings, get_settings
from backend.core.exceptions import DuplicateWebhookError, MemoryStoreError
from backend.job_queue.arq_worker import enqueue_review_job
from backend.main import app
from backend.memory.redis_client import redis_client


WEBHOOK_SECRET = "test-webhook-secret-12345"


def sign_payload(payload_bytes: bytes, secret: str = WEBHOOK_SECRET) -> str:
    mac = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


@pytest.fixture
def test_settings():
    return Settings(
        github_webhook_secret=WEBHOOK_SECRET,
        github_token="ghp_test",
        openai_api_key="sk-test",
        redis_url="redis://localhost:6379/0",
    )


@pytest.fixture
def pr_payload():
    return {
        "action": "opened",
        "number": 42,
        "repository": {
            "full_name": "acme/backend-service",
            "name": "backend-service",
            "clone_url": "https://github.com/acme/backend-service.git",
            "owner": {"login": "acme"},
        },
        "pull_request": {
            "number": 42,
            "title": "Add authentication middleware",
            "body": "Implements JWT checks",
            "diff_url": "https://github.com/acme/backend-service/pull/42.diff",
            "user": {"login": "developer-alice"},
            "head": {
                "sha": "c0ffee1234567890abcdefc0ffee1234567890ab",
                "ref": "feature/auth",
            },
            "base": {"ref": "main"},
        },
    }


class TestT09WebhookRecovery:
    def test_unsupported_content_type_returns_415(self, test_settings):
        """Unsupported content-type is rejected with HTTP 415."""
        app.dependency_overrides[get_settings] = lambda: test_settings
        client = TestClient(app)
        resp = client.post(
            "/webhook/github",
            content=b"hello",
            headers={"Content-Type": "text/xml"},
        )
        assert resp.status_code == 415

    def test_oversized_payload_returns_413(self, test_settings):
        """Payload exceeding 10MB is rejected with HTTP 413."""
        app.dependency_overrides[get_settings] = lambda: test_settings
        client = TestClient(app)
        huge_payload = b" " * (10 * 1024 * 1024 + 1)
        resp = client.post(
            "/webhook/github",
            content=huge_payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=invalid",
            },
        )
        assert resp.status_code == 413

    def test_duplicate_delivery_receipt_replayed_promptly(self, test_settings, pr_payload):
        """Replay of an already accepted delivery returns 200 without duplicate enqueue."""
        app.dependency_overrides[get_settings] = lambda: test_settings
        payload_bytes = json.dumps(pr_payload).encode("utf-8")
        sig = sign_payload(payload_bytes)

        delivery_id = "delivery-guid-1111"
        with patch.object(redis_client, "check_receipt", new=AsyncMock(return_value="acme/backend-service:42:c0ffee1234567890abcdefc0ffee1234567890ab")), \
             patch("backend.webhook_receiver.router.enqueue_review_job", new=AsyncMock()) as mock_enqueue:
            client = TestClient(app)
            resp = client.post(
                "/webhook/github",
                content=payload_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": sig,
                    "X-GitHub-Event": "pull_request",
                    "X-GitHub-Delivery": delivery_id,
                },
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "already_processed"
            assert resp.json()["delivery_id"] == delivery_id
            mock_enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_enqueue_failure_cleans_up_idempotency_key(self, test_settings):
        """If ARQ enqueue throws, the idempotency key is deleted so redelivery is not blocked."""
        workflow_id = "test/repo:10:sha12345"

        with patch.object(redis_client, "check_idempotency_key", new=AsyncMock(return_value=False)), \
             patch.object(redis_client, "set_idempotency_key", new=AsyncMock()) as mock_set, \
             patch.object(redis_client, "delete_idempotency_key", new=AsyncMock()) as mock_del, \
             patch("backend.job_queue.arq_worker.create_pool", new=AsyncMock()) as mock_pool:

            mock_arq = AsyncMock()
            mock_arq.enqueue_job.side_effect = RuntimeError("Redis connection dropped")
            mock_pool.return_value = mock_arq

            with pytest.raises(RuntimeError, match="Redis connection dropped"):
                await enqueue_review_job(
                    workflow_id=workflow_id,
                    input_data={"repo": "test/repo"},
                    delivery_id="delivery-guid-2222",
                )

            # mock_del was called to ensure no orphaned idempotency key blocks retry
            mock_del.assert_called_once_with(workflow_id)
            mock_set.assert_not_called()

    @pytest.mark.asyncio
    async def test_successful_enqueue_records_both_idempotency_and_receipt(self, test_settings):
        """Successful enqueue atomically registers idempotency key and delivery receipt."""
        workflow_id = "test/repo:20:shaabcdef"
        delivery_id = "delivery-guid-3333"

        with patch.object(redis_client, "check_idempotency_key", new=AsyncMock(return_value=False)), \
             patch.object(redis_client, "set_idempotency_key", new=AsyncMock()) as mock_set, \
             patch.object(redis_client, "record_receipt", new=AsyncMock()) as mock_receipt, \
             patch("backend.job_queue.arq_worker.create_pool", new=AsyncMock()) as mock_pool:

            mock_arq = AsyncMock()
            mock_job = MagicMock(job_id=workflow_id)
            mock_arq.enqueue_job.return_value = mock_job
            mock_pool.return_value = mock_arq

            await enqueue_review_job(
                workflow_id=workflow_id,
                input_data={"repo": "test/repo"},
                delivery_id=delivery_id,
            )

            mock_set.assert_called_once_with(workflow_id)
            mock_receipt.assert_called_once_with(delivery_id, workflow_id)

    def test_redis_unavailable_returns_503_for_github_redelivery(self, test_settings, pr_payload):
        """When Redis / Job Queue is unavailable during enqueue, HTTP 503 is returned so GitHub will redeliver."""
        app.dependency_overrides[get_settings] = lambda: test_settings
        payload_bytes = json.dumps(pr_payload).encode("utf-8")
        sig = sign_payload(payload_bytes)

        with patch.object(redis_client, "check_receipt", new=AsyncMock(return_value=None)), \
             patch("backend.webhook_receiver.router.enqueue_review_job", side_effect=MemoryStoreError("Redis connection refused", store="redis")):
            client = TestClient(app)
            resp = client.post(
                "/webhook/github",
                content=payload_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": sig,
                    "X-GitHub-Event": "pull_request",
                    "X-GitHub-Delivery": "delivery-retry-guid",
                },
            )
            assert resp.status_code == 503
            assert "Job queue temporarily unavailable" in resp.json()["detail"]
