"""
tests/test_preserve_agent_failures_t06.py

Regression test suite for T06:
  - Preserve agent failures and prevent false approval
  - Mandatory security check enforcement (exceptions, timeouts, malformed outputs)
  - Distinguish success vs provider failure vs invalid output vs timeout
  - Incomplete coverage policy
"""

import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")

from backend.agents.contracts import AgentFailureKind, AgentTask, AgentVerdict
from backend.agents.security_agent import SecurityAgent
from backend.models.enums import ReviewVerdict
from backend.orchestrator.nodes import aggregate_results, fan_out_agents
from backend.tools.llm_client import LLMResponse


def _make_agent_result(agent_type: str, success: bool = True, findings=None, confidence=0.9, per_verdict="approve", error_message=""):
    return {
        "agent_type": agent_type,
        "success": success,
        "findings": findings or [],
        "confidence": confidence,
        "per_verdict": per_verdict,
        "error_message": error_message,
        "duration_seconds": 0.5,
    }


def _make_state(results):
    return {
        "workflow_id": "test/repo:42:commit123",
        "agent_results": results,
        "pr_diff": "+def safe(): pass",
        "pr_title": "Safe PR",
        "pr_body": "Nothing dangerous",
        "repo_full_name": "test/repo",
        "pr_number": 42,
        "head_commit_sha": "commit123",
        "confidence_threshold": 0.70,
    }


class TestT06PreserveAgentFailures:
    """Verify that agent failures are strictly preserved and never falsely approved."""

    @pytest.mark.asyncio
    async def test_security_provider_exception_prevents_approval(self):
        """When security agent raises provider exception, overall review cannot approve."""
        agent = SecurityAgent()

        # Mock LLM client raising provider network/auth exception
        with patch.object(agent, "_dispatch_llm_call", side_effect=RuntimeError("Provider timeout / API down")):
            task = AgentTask(
                diff="+x = 1",
                pr_title="Fix bug",
                pr_description="",
                repo_name="test/repo",
                changed_files=("test.py",),
                peer_context=(),
                workflow_id="w-1",
            )
            output = await agent.analyze(task=task)

            # Failure must be explicit
            assert output.succeeded is False
            assert output.failure_kind == AgentFailureKind.PROVIDER_FAILURE
            assert "LLM call failed" in output.error_message
            assert output.per_verdict != AgentVerdict.APPROVE

        # Now test that aggregation rejects approval even if other 3 agents approve with 0.99 confidence
        state = _make_state([
            _make_agent_result("security", success=False, error_message=output.error_message, per_verdict="request_changes", confidence=0.0),
            _make_agent_result("quality", success=True, per_verdict="approve", confidence=0.99),
            _make_agent_result("test", success=True, per_verdict="approve", confidence=0.99),
            _make_agent_result("docs", success=True, per_verdict="approve", confidence=0.99),
        ])

        agg = await aggregate_results(state)
        assert agg["verdict"] != ReviewVerdict.APPROVE
        assert agg["verdict"] == ReviewVerdict.NEEDS_HUMAN_REVIEW
        assert agg["needs_human_review"] is True
        assert "Security agent failed" in agg["human_review_reason"]

    @pytest.mark.asyncio
    async def test_security_invalid_json_prevents_approval(self):
        """When security agent returns non-JSON garbage, it fails output guardrail and cannot approve."""
        agent = SecurityAgent()
        garbage_response = LLMResponse(
            content="I am an AI and here is some unstructured thought without JSON",
            input_tokens=100,
            output_tokens=50,
            estimated_cost_usd=0.001,
            is_valid_json=False,
            model_used="gpt-4o-mini",
            latency_seconds=0.5,
        )

        with patch.object(agent, "_dispatch_llm_call", return_value=garbage_response):
            task = AgentTask(
                diff="+x = 1",
                pr_title="Fix bug",
                pr_description="",
                repo_name="test/repo",
                changed_files=("test.py",),
                peer_context=(),
                workflow_id="w-1",
            )
            output = await agent.analyze(task=task)

            assert output.succeeded is False
            assert output.failure_kind == AgentFailureKind.PARSE_FAILURE
            assert output.per_verdict != AgentVerdict.APPROVE

        # Feeding this into aggregation
        state = _make_state([
            _make_agent_result("security", success=False, error_message=output.error_message, per_verdict="request_changes", confidence=0.0),
            _make_agent_result("quality", success=True, per_verdict="approve", confidence=0.95),
            _make_agent_result("test", success=True, per_verdict="approve", confidence=0.95),
            _make_agent_result("docs", success=True, per_verdict="approve", confidence=0.95),
        ])
        agg = await aggregate_results(state)
        assert agg["verdict"] == ReviewVerdict.NEEDS_HUMAN_REVIEW
        assert agg["needs_human_review"] is True

    @pytest.mark.asyncio
    async def test_security_schema_invalid_prevents_approval(self):
        """When security agent returns valid JSON but with invalid schema (no findings array), cannot approve."""
        agent = SecurityAgent()
        schema_invalid_response = LLMResponse(
            content={"message": "All done", "status": "ok"},  # No findings list
            input_tokens=100,
            output_tokens=50,
            estimated_cost_usd=0.001,
            is_valid_json=True,
            model_used="gpt-4o-mini",
            latency_seconds=0.5,
        )

        with patch.object(agent, "_dispatch_llm_call", return_value=schema_invalid_response):
            task = AgentTask(
                diff="+x = 1",
                pr_title="Fix bug",
                pr_description="",
                repo_name="test/repo",
                changed_files=("test.py",),
                peer_context=(),
                workflow_id="w-1",
            )
            output = await agent.analyze(task=task)

            assert output.succeeded is False
            assert output.failure_kind == AgentFailureKind.INVALID_OUTPUT
            assert output.per_verdict != AgentVerdict.APPROVE

    @pytest.mark.asyncio
    async def test_all_agents_failing_prevents_approval(self):
        """When all agents fail, overall review cannot approve."""
        state = _make_state([
            _make_agent_result("security", success=False, error_message="Crash 1", per_verdict="request_changes", confidence=0.0),
            _make_agent_result("quality", success=False, error_message="Crash 2", per_verdict="request_changes", confidence=0.0),
            _make_agent_result("test", success=False, error_message="Crash 3", per_verdict="request_changes", confidence=0.0),
            _make_agent_result("docs", success=False, error_message="Crash 4", per_verdict="request_changes", confidence=0.0),
        ])
        agg = await aggregate_results(state)
        assert agg["verdict"] == ReviewVerdict.NEEDS_HUMAN_REVIEW
        assert agg["needs_human_review"] is True

    @pytest.mark.asyncio
    async def test_missing_agent_results_prevents_approval(self):
        """When agent_results is empty or missing, cannot approve."""
        state = _make_state([])
        agg = await aggregate_results(state)
        assert agg["verdict"] == ReviewVerdict.NEEDS_HUMAN_REVIEW
        assert agg["needs_human_review"] is True
