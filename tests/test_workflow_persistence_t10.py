"""
tests/test_workflow_persistence_t10.py

Acceptance tests for T10:
Persist workflow state and make retries real.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from arq.worker import Retry
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

from backend.core.exceptions import RetryableWorkflowError
from backend.core.workflow_engine import WorkflowResult
from backend.job_queue.arq_worker import run_pr_review, MAX_WORKER_RETRIES
from backend.models.enums import ReviewStatus, ReviewVerdict
from backend.orchestrator.checkpointer import DurableCheckpointSaver
from backend.orchestrator.nodes import post_review


class SampleState(TypedDict):
    step: int
    data: str


class TestT10WorkflowPersistenceAndRetries:
    @pytest.mark.asyncio
    async def test_durable_checkpoint_cross_process_resumption(self):
        """Killing a worker and resuming in a new instance completes without re-executing completed nodes."""
        step1_calls = 0
        step2_calls = 0

        def node_step1(state):
            nonlocal step1_calls
            step1_calls += 1
            return {"step": 1, "data": "computed_in_worker_1"}

        def node_step2(state):
            nonlocal step2_calls
            step2_calls += 1
            return {"step": 2, "data": state["data"] + "_completed_in_worker_2"}

        builder = StateGraph(SampleState)
        builder.add_node("step1", node_step1)
        builder.add_node("step2", node_step2)
        builder.add_edge(START, "step1")
        builder.add_edge("step1", "step2")
        builder.add_edge("step2", END)

        # Worker 1 runs and is interrupted before step2
        saver_worker1 = DurableCheckpointSaver()
        graph1 = builder.compile(checkpointer=saver_worker1, interrupt_before=["step2"])
        thread_id = "test-repo:100:sha-resumption"

        await graph1.ainvoke({"step": 0, "data": "initial"}, config={"configurable": {"thread_id": thread_id}})
        assert step1_calls == 1
        assert step2_calls == 0

        # Snapshot portable checkpoint bytes (simulating Redis/DB storage across process crash)
        persisted_bytes = saver_worker1.save_to_bytes(thread_id)

        # Worker 2 starts in a new process, restores from persisted bytes
        saver_worker2 = DurableCheckpointSaver()
        saver_worker2.load_from_bytes(thread_id, persisted_bytes)
        graph2 = builder.compile(checkpointer=saver_worker2)

        # Resume execution
        final_state = await graph2.ainvoke(None, config={"configurable": {"thread_id": thread_id}})

        # step1 was NOT re-run; step2 ran to completion
        assert step1_calls == 1
        assert step2_calls == 1
        assert final_state["step"] == 2
        assert final_state["data"] == "computed_in_worker_1_completed_in_worker_2"

    @pytest.mark.asyncio
    async def test_transient_error_triggers_bounded_retry(self):
        """Transient errors trigger an ARQ Retry with exponential backoff when below max retries."""
        workflow_id = "acme/repo:55:sha1"
        ctx = {"job_id": "job-1", "job_try": 1}

        with patch("backend.job_queue.arq_worker._engine.run", side_effect=RetryableWorkflowError("API timeout")):
            with patch("backend.memory.redis_client.redis_client.set_workflow_status", new=AsyncMock()) as mock_status:
                with pytest.raises(Retry) as exc_info:
                    await run_pr_review(ctx, workflow_id, {})

                # Exponential backoff deferral: 2 ** 1 = 2 seconds (defer_score in ARQ is 2000ms)
                assert exc_info.value.defer_score in (2, 2000)
                mock_status.assert_any_call(workflow_id, "retrying")

    @pytest.mark.asyncio
    async def test_max_retries_exceeded_routes_to_dead_letter_queue(self):
        """Exceeding max retries records actionable DLQ record and terminates as failed."""
        workflow_id = "acme/repo:55:sha2"
        ctx = {"job_id": "job-2", "job_try": MAX_WORKER_RETRIES}  # Already at retry limit

        with patch("backend.job_queue.arq_worker._engine.run", side_effect=RetryableWorkflowError("API timeout")), \
             patch("backend.memory.redis_client.redis_client.set_workflow_status", new=AsyncMock()) as mock_status, \
             patch("backend.memory.redis_client.redis_client.record_dead_letter", new=AsyncMock()) as mock_dlq:

            res = await run_pr_review(ctx, workflow_id, {})

            assert res["status"] == "failed"
            mock_dlq.assert_called_once()
            args, kwargs = mock_dlq.call_args
            called_workflow_id = kwargs.get("workflow_id") or (args[0] if args else None)
            called_reason = kwargs.get("reason") or (args[1] if len(args) > 1 else None)
            assert called_workflow_id == workflow_id
            assert called_reason == "max_retries_exceeded"
            mock_status.assert_called_with(workflow_id, "failed")

    @pytest.mark.asyncio
    async def test_poison_job_routes_immediately_to_dead_letter_queue(self):
        """Poison jobs route directly to DLQ on first attempt without wasteful retries."""
        workflow_id = "acme/repo:55:sha3"
        ctx = {"job_id": "job-3", "job_try": 0}

        fake_failed_result = WorkflowResult(
            workflow_id=workflow_id,
            status=ReviewStatus.FAILED,
            verdict=None,
            findings=[],
            error_message="Corrupted AST schema: poison payload",
        )

        with patch("backend.job_queue.arq_worker._engine.run", return_value=fake_failed_result), \
             patch("backend.memory.redis_client.redis_client.set_workflow_status", new=AsyncMock()) as mock_status, \
             patch("backend.memory.redis_client.redis_client.record_dead_letter", new=AsyncMock()) as mock_dlq:

            res = await run_pr_review(ctx, workflow_id, {})

            assert res["status"] == "failed"
            mock_dlq.assert_called_once()
            args, kwargs = mock_dlq.call_args
            called_workflow_id = kwargs.get("workflow_id") or (args[0] if args else None)
            called_reason = kwargs.get("reason") or (args[1] if len(args) > 1 else None)
            assert called_workflow_id == workflow_id
            assert called_reason == "workflow_execution_failed"
            mock_status.assert_called_with(workflow_id, "failed")

    @pytest.mark.asyncio
    async def test_post_review_idempotency_prevents_duplicate_github_publication(self):
        """If review was already posted, post_review safely skips re-posting on replay."""
        state = {
            "workflow_id": "acme/repo:1:sha99",
            "repo_full_name": "acme/repo",
            "pr_number": 1,
            "head_commit_sha": "sha99",
            "needs_human_review": False,
            "review_posted": True,
            "github_review_id": 98765,
            "final_findings": [],
            "verdict": ReviewVerdict.APPROVE,
        }

        with patch("backend.integrations.github_client.GitHubClient") as mock_gh:
            result = await post_review(state)
            assert result["review_posted"] is True
            assert result["github_review_id"] == 98765
            mock_gh.assert_not_called()
