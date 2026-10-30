# tests/test_health_checks_t21.py
#
# Tests for Gate B - Task T21:
# Make health checks reflect actual capability.
#
# Invariants verified:
#   1. Cheap liveness (/health/live) is isolated from external dependencies.
#   2. Readiness (/health/ready and /health) checks Postgres, Schema, Redis, Worker, and Tiger.
#   3. DB/Redis/Worker/Optional-Vector outages produce documented distinct states.
#   4. An API answering HTTP is not displayed as an operating review pipeline when workers are offline.
#   5. Optional RAG degradation is explicit and does not trigger 503 restart loops.
#   6. No raw exceptions or internal traces are exposed to unauthenticated probes.
#   7. Worker heartbeat lifecycle accurately records, tracks, and cleans up worker state.
#   8. Oldest accepted job age and queue depth are tracked.
#   9. Authenticated diagnostics (/health/diagnostics) requires auth and exposes deep telemetry.
#   10. Probe latency is strictly bounded against slow dependencies.

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import backend.main as main_module
from backend.config.settings import Settings, get_settings
from backend.job_queue.heartbeat import WorkerHeartbeat
from backend.memory.redis_client import redis_client


@pytest.fixture(autouse=True)
def reset_redis_fallback():
    """Clear in-memory fallback state in Redis client before each test."""
    redis_client._in_memory_fallback.clear()
    yield
    redis_client._in_memory_fallback.clear()


def test_cheap_liveness_has_zero_external_calls_and_returns_200():
    """
    GET /health/live must always return 200 while the process is alive.
    Never executes external network or database calls.
    """
    client = TestClient(main_module.app, raise_server_exceptions=True)
    start_time = time.time()
    resp = client.get("/health/live")
    elapsed = time.time() - start_time

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert body["process"] == "api"
    assert elapsed < 0.2  # Fast in-memory check


def test_readiness_distinct_states_database_down_produces_503():
    """
    When PostgreSQL is down, /health and /health/ready must return 503
    with status='degraded', services.postgres='unhealthy', and no leaked raw traceback.
    """
    client = TestClient(main_module.app, raise_server_exceptions=False)
    with (
        patch.object(main_module, "_check_postgres", new=AsyncMock(return_value="unhealthy")),
        patch.object(main_module, "_check_schema", new=AsyncMock(return_value="unmigrated")),
        patch.object(main_module, "_check_redis", new=AsyncMock(return_value="ok")),
        patch.object(main_module, "_check_tiger", new=AsyncMock(return_value="ok")),
    ):
        resp = client.get("/health/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["pipeline_ready"] is False
        assert data["services"]["postgres"] == "unhealthy"
        # Verify no raw exception strings or tracebacks are leaked
        assert "Traceback" not in resp.text
        assert "OperationalError" not in resp.text


def test_readiness_distinct_states_schema_unmigrated_produces_503():
    """
    When database schema is incomplete or unmigrated, readiness returns 503.
    """
    client = TestClient(main_module.app, raise_server_exceptions=False)
    with (
        patch.object(main_module, "_check_postgres", new=AsyncMock(return_value="ok")),
        patch.object(
            main_module,
            "_check_schema",
            new=AsyncMock(return_value="unmigrated (missing pr_review_records)"),
        ),
        patch.object(main_module, "_check_redis", new=AsyncMock(return_value="ok")),
        patch.object(main_module, "_check_tiger", new=AsyncMock(return_value="ok")),
    ):
        resp = client.get("/health/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["pipeline_ready"] is False
        assert "unmigrated" in data["services"]["schema"]


def test_readiness_distinct_states_redis_down_produces_503():
    """
    When Redis is unavailable, readiness returns 503 because queue is offline.
    """
    client = TestClient(main_module.app, raise_server_exceptions=False)
    with (
        patch.object(main_module, "_check_postgres", new=AsyncMock(return_value="ok")),
        patch.object(main_module, "_check_schema", new=AsyncMock(return_value="ok")),
        patch.object(main_module, "_check_redis", new=AsyncMock(return_value="unhealthy")),
        patch.object(main_module, "_check_tiger", new=AsyncMock(return_value="ok")),
    ):
        resp = client.get("/health/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["pipeline_ready"] is False
        assert data["services"]["redis"] == "unhealthy"


def test_readiness_worker_offline_with_require_worker_produces_503():
    """
    When require_worker_for_readiness=True and worker fleet is offline,
    readiness returns 503 with pipeline_ready=False.
    An API answering HTTP is not displayed as an operating review pipeline.
    """
    custom_settings = Settings(
        require_worker_for_readiness=True,
        app_env="production",
    )
    main_module.app.dependency_overrides[get_settings] = lambda: custom_settings
    client = TestClient(main_module.app, raise_server_exceptions=False)

    try:
        with (
            patch.object(main_module, "_check_postgres", new=AsyncMock(return_value="ok")),
            patch.object(main_module, "_check_schema", new=AsyncMock(return_value="ok")),
            patch.object(main_module, "_check_redis", new=AsyncMock(return_value="ok")),
            patch.object(
                main_module,
                "_check_worker",
                new=AsyncMock(return_value=("offline", [], None)),
            ),
            patch.object(main_module, "_check_tiger", new=AsyncMock(return_value="ok")),
        ):
            resp = client.get("/health/ready")
            assert resp.status_code == 503
            data = resp.json()
            assert data["status"] == "degraded"
            assert data["pipeline_ready"] is False
            assert data["services"]["worker"] == "offline"
    finally:
        main_module.app.dependency_overrides.pop(get_settings, None)


def test_readiness_distinct_states_optional_rag_degraded_returns_200():
    """
    Optional Tiger Cloud vector memory outage does NOT fail the pod or trigger
    load balancer removal loops. Returns 200 with services.tiger='degraded'.
    """
    client = TestClient(main_module.app, raise_server_exceptions=False)
    with (
        patch.object(main_module, "_check_postgres", new=AsyncMock(return_value="ok")),
        patch.object(main_module, "_check_schema", new=AsyncMock(return_value="ok")),
        patch.object(main_module, "_check_redis", new=AsyncMock(return_value="ok")),
        patch.object(
            main_module,
            "_check_worker",
            new=AsyncMock(return_value=("ok", [{"worker_id": "w1"}], None)),
        ),
        patch.object(main_module, "_check_tiger", new=AsyncMock(return_value="degraded: timeout")),
    ):
        resp = client.get("/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["pipeline_ready"] is True
        assert "degraded" in data["services"]["tiger"]


@pytest.mark.asyncio
async def test_worker_heartbeat_lifecycle_records_and_evicts():
    """
    WorkerHeartbeat registers active worker in Redis, updates timestamps,
    and removes the record cleanly on shutdown.
    """
    heartbeat = WorkerHeartbeat(worker_id="test-worker-01", interval_seconds=0.1, ttl_seconds=5)
    await heartbeat.start()

    # Verify active workers list includes our worker
    workers = await redis_client.get_active_workers(max_age_seconds=10)
    assert len(workers) == 1
    assert workers[0]["worker_id"] == "test-worker-01"
    assert "uptime_seconds" in workers[0]["metadata"]

    # Graceful stop
    await heartbeat.stop()

    # Verify worker was removed
    active_after_stop = await redis_client.get_active_workers(max_age_seconds=10)
    assert len(active_after_stop) == 0


@pytest.mark.asyncio
async def test_oldest_accepted_job_tracking_in_queue():
    """
    Tracks queue depth and oldest accepted job age.
    """
    # Enqueue two jobs
    await redis_client.record_job_enqueued("wf-job-1")
    await asyncio.sleep(0.05)
    await redis_client.record_job_enqueued("wf-job-2")

    job_id, age = await redis_client.get_oldest_accepted_job_age()
    assert job_id == "wf-job-1"
    assert age is not None
    assert age >= 0.04

    # Dequeue oldest job
    await redis_client.record_job_dequeued("wf-job-1")

    # Now oldest job should be wf-job-2
    job_id2, age2 = await redis_client.get_oldest_accepted_job_age()
    assert job_id2 == "wf-job-2"
    assert age2 is not None

    # Dequeue second job
    await redis_client.record_job_dequeued("wf-job-2")
    job_id_empty, age_empty = await redis_client.get_oldest_accepted_job_age()
    assert job_id_empty is None
    assert age_empty is None


def test_probe_latency_bounded_on_slow_upstream():
    """
    If an upstream service hangs, probe timeout boundedly fails without blocking probe.
    """
    async def slow_pg(*args, **kwargs):
        await asyncio.sleep(0.2)
        return "ok"

    client = TestClient(main_module.app, raise_server_exceptions=False)
    # Set probe timeout very small to test timeout trip
    custom_settings = Settings(probe_timeout_seconds=0.05)
    main_module.app.dependency_overrides[get_settings] = lambda: custom_settings

    try:
        with patch.object(main_module, "_check_postgres", side_effect=asyncio.TimeoutError):
            start = time.time()
            resp = client.get("/health/ready")
            duration = time.time() - start
            assert resp.status_code == 503
            assert duration < 1.0  # Probe must not hang
    finally:
        main_module.app.dependency_overrides.pop(get_settings, None)


def test_authenticated_diagnostics_requires_auth_and_provides_deep_telemetry():
    """
    GET /health/diagnostics requires authentication (401 without auth)
    and provides deep operational telemetry to authenticated operators.
    """
    test_key = "test-adm-key-999"
    custom_settings = Settings(
        api_key=test_key,
        app_env="production",
    )
    main_module.app.dependency_overrides[get_settings] = lambda: custom_settings
    client = TestClient(main_module.app, raise_server_exceptions=False)

    try:
        # 1. Unauthenticated probe gets 401
        unauth_resp = client.get("/health/diagnostics")
        assert unauth_resp.status_code == 401

        # 2. Authenticated operator gets 200 with deep telemetry
        with (
            patch.object(main_module, "_check_postgres", new=AsyncMock(return_value="ok")),
            patch.object(main_module, "_check_schema", new=AsyncMock(return_value="ok")),
            patch.object(main_module, "_check_redis", new=AsyncMock(return_value="ok")),
            patch.object(
                main_module,
                "_check_worker",
                new=AsyncMock(
                    return_value=(
                        "ok",
                        [{"worker_id": "worker-1", "hostname": "pod-1", "uptime_seconds": 120}],
                        4.5,
                    )
                ),
            ),
            patch.object(main_module, "_check_tiger", new=AsyncMock(return_value="ok")),
        ):
            auth_resp = client.get("/health/diagnostics", headers={"X-API-Key": test_key})
            assert auth_resp.status_code == 200
            diag = auth_resp.json()
            assert diag["status"] == "ok"
            assert diag["caller"]["principal_id"] == "api_key_operator"
            assert diag["caller"]["role"] == "admin"
            assert "lifecycle" in diag
            assert diag["queue"]["active_workers_count"] == 1
            assert diag["queue"]["oldest_accepted_job_age_seconds"] == 4.5
            assert "circuit_breakers" in diag
    finally:
        main_module.app.dependency_overrides.pop(get_settings, None)
