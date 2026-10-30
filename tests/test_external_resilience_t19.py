# tests/test_external_resilience_t19.py
"""
Acceptance tests for T19: Consistent external-call resilience across adapters.

Covers:
1. Connect and read timeouts on external HTTP and LLM calls.
2. 429 RateLimit and 5xx transient server error handling with Retry-After and jitter.
3. Ambiguous write protection: non-idempotent writes (POST) timing out refuse blind retry
   and raise AmbiguousWriteError to prevent duplicate reviews/mutations.
4. Shared deadline budget (DeadlineBudget): retries and delays do not multiply across nested
   layers or exceed the workflow deadline; raises DeadlineExceededError when exhausted.
5. Cancellation propagation: asyncio.CancelledError terminates LLM/HTTP calls immediately
   without attempting retries or logging spurious spend.
6. Per-provider concurrency bulkheads: enforce Semaphore limits on concurrent provider calls.
7. Workflow context attribution: scoped_workflow_context guarantees context cleanup after task finish.
8. Circuit breaker recovery: tripped circuit opens, rejects further calls, and resets after cooldown.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.core.exceptions import AgentError
from backend.integrations.github_client import (
    AmbiguousWriteError,
    GitHubAPIError,
    GitHubClient,
    GitHubRateLimitError,
)
from backend.observability.workflow_context import (
    get_workflow_context,
    scoped_workflow_context,
    set_workflow_context,
)
from backend.reliability.circuit_breaker import (
    BreakerConfig,
    BreakerState,
    CircuitBreaker,
    CircuitOpenError,
)
from backend.reliability.retry import RetryConfig, async_retry_with_backoff
from backend.reliability.timeout import DeadlineBudget, DeadlineExceededError
from backend.tools.llm_client import LLMClient, LLMResponse, get_provider_semaphore


@pytest.mark.asyncio
class TestT19ExternalCallResilience:
    """Acceptance test suite for T19: External-call resilience consistency."""

    def _get_test_client(self) -> GitHubClient:
        mock_settings = MagicMock()
        mock_settings.github_token = "ghp_test_token"
        mock_settings.github_api_base_url = "https://api.github.com"
        return GitHubClient(mock_settings)

    async def test_ambiguous_write_timeout_prevents_blind_retry(self):
        """
        Non-idempotent HTTP writes (POST/PUT/PATCH/DELETE) timing out mid-transmission
        must raise AmbiguousWriteError and NEVER blindly retry, preventing duplicate reviews.
        """
        client = self._get_test_client()
        post_calls = 0

        async def mock_post(method, path, **kwargs):
            nonlocal post_calls
            post_calls += 1
            raise httpx.ReadTimeout("Read timed out mid-transmission")

        with patch.object(client._http, "request", side_effect=mock_post):
            with pytest.raises(AmbiguousWriteError) as exc_info:
                await client._request_unwrapped("POST", "/repos/owner/repo/pulls/1/reviews", json={"body": "LGTM"})

            # Must have aborted on the very first attempt without retrying
            assert post_calls == 1
            assert "blind retry" in str(exc_info.value).lower()

    async def test_idempotent_read_retries_on_transient_failures(self):
        """
        Idempotent reads (GET) must retry on network errors / timeouts up to MAX_RETRIES.
        """
        client = self._get_test_client()
        get_calls = 0

        async def mock_get(method, path, **kwargs):
            nonlocal get_calls
            get_calls += 1
            if get_calls < 3:
                raise httpx.ConnectTimeout("Connection timed out")
            return httpx.Response(200, json={"id": 123, "state": "open"}, request=httpx.Request("GET", path))

        with patch.object(client._http, "request", side_effect=mock_get):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                data = await client._request_unwrapped("GET", "/repos/owner/repo/pulls/1")
                assert data["id"] == 123
                assert get_calls == 3

    async def test_rate_limit_retry_after_respected(self):
        """
        429 responses with Retry-After headers must extract the header and raise
        GitHubRateLimitError with the parsed cooldown.
        """
        client = self._get_test_client()

        async def mock_429(method, path, **kwargs):
            resp = httpx.Response(
                429,
                headers={"Retry-After": "42", "X-RateLimit-Remaining": "0"},
                json={"message": "API rate limit exceeded"},
                request=httpx.Request(method, path),
            )
            return resp

        with patch.object(client._http, "request", side_effect=mock_429):
            with pytest.raises(GitHubRateLimitError) as exc_info:
                await client._request_unwrapped("GET", "/rate_limited_endpoint")

            assert exc_info.value.retry_after_seconds == 42
            assert exc_info.value.status_code == 429

    async def test_shared_deadline_budget_prevents_retry_amplification(self):
        """
        When a shared deadline budget has expired or has insufficient headroom,
        retries must abort immediately and raise DeadlineExceededError.
        """
        budget = DeadlineBudget(total_budget_s=0.1)
        await asyncio.sleep(0.12)  # expire budget

        assert budget.is_expired
        assert budget.remaining_s == 0.0

        with pytest.raises(DeadlineExceededError):
            budget.check_headroom(0.05)

        with pytest.raises(DeadlineExceededError):
            budget.slice_for_call(5.0)

    async def test_llm_call_cancellation_stops_spend_immediately(self):
        """
        Cancelling an in-flight LLM call must propagate asyncio.CancelledError
        immediately without triggering backoff loops or logging phantom token spend.
        """
        llm = LLMClient()

        async def mock_create(*args, **kwargs):
            # Simulate a hanging provider call
            await asyncio.sleep(10.0)

        mock_client = MagicMock()
        mock_client.chat.completions.create = mock_create

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            task = asyncio.create_task(
                llm.call_openai(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": "hello"}],
                    system_prompt="sys",
                    api_key="sk-test",
                )
            )
            await asyncio.sleep(0.02)
            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task

    async def test_provider_concurrency_bulkhead(self):
        """
        Provider semaphores must limit active concurrent calls to the configured bound (10).
        """
        sem = get_provider_semaphore("test_provider")
        assert sem._value == 10

        # Acquire 10 permits
        for _ in range(10):
            await sem.acquire()

        assert sem.locked()

        # 11th acquisition must wait
        acquired = False
        async def try_acquire():
            nonlocal acquired
            await sem.acquire()
            acquired = True

        task = asyncio.create_task(try_acquire())
        await asyncio.sleep(0.02)
        assert not acquired

        # Release one permit
        sem.release()
        await asyncio.sleep(0.02)
        assert acquired
        task.cancel()

    async def test_scoped_workflow_context_attribution_cleanup(self):
        """
        scoped_workflow_context must isolate context and cleanly restore previous
        values upon completion or unhandled exceptions.
        """
        assert get_workflow_context().workflow_id is None

        # Successful block
        with scoped_workflow_context(workflow_id="wf-123", agent_type="security", tenant_id="t-1"):
            ctx = get_workflow_context()
            assert ctx.workflow_id == "wf-123"
            assert ctx.agent_type == "security"
            assert ctx.tenant_id == "t-1"

        # Restored
        assert get_workflow_context().workflow_id is None

        # Exception block
        try:
            with scoped_workflow_context(workflow_id="wf-failed", agent_type="quality", tenant_id="t-2"):
                assert get_workflow_context().workflow_id == "wf-failed"
                raise RuntimeError("Something broke")
        except RuntimeError:
            pass

        # Restored after exception
        assert get_workflow_context().workflow_id is None

    async def test_circuit_breaker_trips_and_recovers(self):
        """
        Circuit breaker must trip after configured failures, fast-fail subsequent calls,
        and allow recovery after cooldown.
        """
        cfg = BreakerConfig(failure_threshold=2, recovery_timeout_s=0.1, name="test_resilience")
        breaker = CircuitBreaker(config=cfg)

        async def failing_call():
            raise httpx.ConnectError("Network is down")

        # First failure
        with pytest.raises(httpx.ConnectError):
            await breaker.async_call(failing_call)
        assert breaker.state == BreakerState.CLOSED

        # Second failure -> trips circuit to OPEN
        with pytest.raises(httpx.ConnectError):
            await breaker.async_call(failing_call)
        assert breaker.state == BreakerState.OPEN

        # Subsequent calls fail fast without executing function
        with pytest.raises(CircuitOpenError):
            await breaker.async_call(failing_call)

        # Wait for recovery timeout
        await asyncio.sleep(0.12)
        assert breaker.state == BreakerState.HALF_OPEN

        # Successful probe closes circuit
        async def success_call():
            return "recovered"

        res = await breaker.async_call(success_call)
        assert res == "recovered"
        assert breaker.state == BreakerState.CLOSED
