# tests/test_observability_and_evidence_t20.py
"""
Acceptance tests for T20: Initialize observability in every process and preserve evidence.

Covers:
1. Shared explicit resource lifecycle (startup_process / shutdown_process) across API and worker.
2. Secret and credential redaction: API keys, tokens, DB connection passwords, and private code
   are masked in structured logs and audit records.
3. Label cardinality and string length bounding to prevent metric/logging explosion.
4. Structured logging automatic context enrichment (workflow_id, agent_type, tenant_id).
5. Background event task tracking and reliable flush on shutdown (flush_agent_events).
6. Identity consistency across event writers and economics readers (UUIDs vs string workflow_ids).
7. Append-only audit logging with durable persistence and secret redaction.
"""

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.lifecycle import (
    flush_telemetry,
    get_process_telemetry_status,
    init_telemetry,
    shutdown_process,
    startup_process,
)
from backend.observability.audit import AuditLogger
from backend.observability.events import (
    AgentEvent,
    dispatch_agent_event,
    emit_agent_event,
    flush_agent_events,
)
from backend.observability.logging import (
    StructuredLogger,
    get_logger,
    redact_sensitive_data,
)
from backend.observability.workflow_context import scoped_workflow_context


@pytest.mark.asyncio
class TestT20ObservabilityAndEvidence:
    """Acceptance test suite for T20."""

    async def test_shared_lifecycle_startup_and_shutdown(self):
        """
        Both API and worker processes must use startup_process and shutdown_process
        to symmetrically initialize and cleanly terminate DB, Tiger Cloud, Redis, and telemetry.
        """
        with patch("backend.lifecycle.redis_client.connect", new_callable=AsyncMock) as mock_r_conn, \
             patch("backend.lifecycle.redis_client.disconnect", new_callable=AsyncMock) as mock_r_disc, \
             patch("backend.lifecycle.init_db", new_callable=AsyncMock) as mock_db_init, \
             patch("backend.lifecycle.close_db", new_callable=AsyncMock) as mock_db_close, \
             patch("backend.lifecycle.init_tiger_schema", new_callable=AsyncMock) as mock_tiger_init, \
             patch("backend.lifecycle.close_tiger_pool", new_callable=AsyncMock) as mock_tiger_close, \
             patch("backend.lifecycle.flush_telemetry", new_callable=AsyncMock) as mock_flush:

            # 1. Startup
            await startup_process(service_name="hadron-worker-test")
            mock_r_conn.assert_awaited_once()
            mock_db_init.assert_awaited_once()
            mock_tiger_init.assert_awaited_once()

            status = get_process_telemetry_status()
            assert status["service_name"] == "hadron-worker-test"
            assert status["redis_active"] is True
            assert status["postgres_active"] is True
            assert status["tiger_active"] is True

            # 2. Shutdown
            await shutdown_process(service_name="hadron-worker-test")
            mock_flush.assert_awaited_once()
            mock_r_disc.assert_awaited_once()
            mock_tiger_close.assert_awaited_once()
            mock_db_close.assert_awaited_once()

    async def test_sensitive_data_redaction_in_logs_and_strings(self):
        """
        API keys, GitHub tokens, DB passwords, and private code bodies
        must be redacted from log strings and tag dictionaries.
        """
        raw_msg = (
            "Connecting with postgresql+asyncpg://hadron_user:super_secret_pw@db.cloud.timescale.com:5432/hadron "
            "using key sk-proj-1234567890abcdef1234567890 and token ghp_ABCDEF1234567890abcdef"
        )
        redacted_msg = redact_sensitive_data(raw_msg)
        assert "super_secret_pw" not in redacted_msg
        assert "sk-proj-1234567890" not in redacted_msg
        assert "ghp_ABCDEF1234567890" not in redacted_msg
        assert "postgresql+asyncpg://hadron_user:[REDACTED]@db.cloud.timescale.com:5432/hadron" in redacted_msg
        assert "sk-...[REDACTED]" in redacted_msg
        assert "gh_...[REDACTED]" in redacted_msg

        # Dictionary tag redaction
        tags = {
            "token": "ghp_1234567890abcdef1234567890",
            "diff": "--- a/secrets.py\n+++ b/secrets.py\n+API_KEY='12345'",
            "code": "def process(): return secret",
            "normal_metric": 42,
            "nested": {
                "redis_url": "rediss://default:redis_pw_123@redis.upstash.io:6379",
            },
        }
        redacted_tags = redact_sensitive_data(tags)
        assert redacted_tags["token"] == "[REDACTED_SECRET]"
        assert redacted_tags["diff"] == "[REDACTED_CODE]"
        assert redacted_tags["code"] == "[REDACTED_CODE]"
        assert redacted_tags["normal_metric"] == 42
        assert "redis_pw_123" not in redacted_tags["nested"]["redis_url"]
        assert "rediss://default:[REDACTED]@redis.upstash.io:6379" in redacted_tags["nested"]["redis_url"]

    async def test_label_cardinality_and_string_length_bounding(self):
        """
        Excessive string lengths (>1024 chars) and dictionary keys (>50 keys)
        must be bounded to protect log storage and aggregation systems.
        """
        giant_string = "A" * 2000
        bounded = redact_sensitive_data(giant_string)
        assert len(bounded) < 1100
        assert bounded.endswith("...[TRUNCATED]")

        wide_dict = {f"key_{i}": i for i in range(100)}
        bounded_dict = redact_sensitive_data(wide_dict)
        assert len(bounded_dict) <= 51
        assert bounded_dict.get("...") == "[CARDINALITY_BOUNDED]"

    async def test_structured_logger_context_enrichment(self):
        """
        StructuredLogger._emit must automatically pull workflow_id, agent_type,
        and tenant_id from the active WorkflowContext.
        """
        logger = get_logger("test.observability.logger")

        with scoped_workflow_context(workflow_id="owner/repo:42:sha123", agent_type="security", tenant_id="tenant-alpha"):
            entry = logger.info("test.event", "Testing context injection")
            assert entry["trace_id"] == "owner/repo:42:sha123"
            assert entry["agent_type"] == "security"
            assert entry["tenant_id"] == "tenant-alpha"
            assert entry["service"] == "ai-pr-review-agent"
            assert entry["event"] == "test.event"

    async def test_event_task_tracking_and_flush(self):
        """
        dispatch_agent_event must register active background event tasks,
        and flush_agent_events must wait for in-flight tasks to finish before shutdown.
        """
        executed = False

        async def slow_insert(pool, event):
            nonlocal executed
            await asyncio.sleep(0.05)
            executed = True

        event = AgentEvent(
            review_id="test-review-1",
            agent="security",
            event_type="span.end",
        )

        with patch("backend.observability.events.emit_agent_event", side_effect=slow_insert):
            dispatch_agent_event(event)
            assert not executed

            # Flush must await completion
            await flush_agent_events(timeout_s=2.0)
            assert executed

    async def test_audit_logger_durable_append_with_redaction(self, tmp_path):
        """
        AuditLogger must write append-only JSONL records and sanitize secrets.
        """
        audit_file = tmp_path / "test_audit.jsonl"
        auditor = AuditLogger(path=audit_file)

        auditor.log_review_started(
            review_id="owner/repo:1:sha",
            repo="owner/repo",
            pr_number=1,
            triggered_by="webhook_token_ghp_1234567890abcdef123456",
        )

        assert audit_file.exists()
        lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

        record = json.loads(lines[0])
        assert record["review_id"] == "owner/repo:1:sha"
        assert record["repo"] == "owner/repo"
        assert record["pr_number"] == 1
        assert "ghp_1234567890" not in record["triggered_by"]
        assert "gh_...[REDACTED]" in record["triggered_by"]

    async def test_identity_consistency_uuid_and_string(self):
        """
        AgentEvent and LLMCallLog must accept and handle both UUIDs and
        'owner/repo:pr:sha' strings without schema corruption or type failures.
        """
        u_id = str(uuid.uuid4())
        str_id = "acme/hadron:101:a1b2c3d"

        # UUID review_id
        ev_uuid = AgentEvent(review_id=u_id, agent="system", event_type="span.start")
        assert ev_uuid.review_id == u_id

        # String review_id
        ev_str = AgentEvent(review_id=str_id, agent="quality", event_type="span.start")
        assert ev_str.review_id == str_id
