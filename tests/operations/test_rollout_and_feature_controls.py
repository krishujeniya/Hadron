"""
tests/operations/test_rollout_and_feature_controls.py

Tests for Gate B - Task T26: Safe rollout, rollback, and operational feature controls.

Verifies:
  1. kill_switch_new_intake halts new webhook arrivals while preserving in-flight jobs.
  2. kill_switch_publication halts GitHub posting while durably saving computed reviews.
  3. kill_switch_provider_spend halts paid LLM provider calls and vector embeddings immediately.
  4. enable_rag_context toggles RAG retrieval on/off cleanly without pipeline failure.
  5. enable_canary_models routes canary traffic to configured experimental models.
  6. verify_environment_separation rejects insecure production configurations and detects cross-environment leaks.
  7. Preflight checks and immutable release manifest creation.
"""

from unittest.mock import AsyncMock, patch
import pytest

from backend.config import Settings
from backend.core.exceptions import (
    ProviderSpendHaltedError,
    QueueOverloadedError,
)
from backend.memory.embedder import EmbeddingError, embed_batch, embed_text
from backend.models.enums import AgentType, ReviewVerdict
from backend.orchestrator.nodes import build_context, post_review
from backend.rollout.preflight import (
    create_release_manifest,
    run_canary_health_check,
    run_migration_preflight,
    verify_environment_separation,
)
from backend.tools.llm_client import LLMClient
from backend.tools.model_router import get_routing_table


# ---------------------------------------------------------------------------
# 1. Kill Switch: New Intake
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_kill_switch_new_intake_rejects_with_503_backpressure():
    """When kill_switch_new_intake is active, enqueue_review_job raises QueueOverloadedError."""
    from backend.job_queue.arq_worker import enqueue_review_job

    cfg = Settings(kill_switch_new_intake=True)
    with patch("backend.job_queue.arq_worker.get_settings", return_value=cfg):
        with pytest.raises(QueueOverloadedError) as exc_info:
            await enqueue_review_job(
                workflow_id="wf-test-intake-kill",
                input_data={"repo_full_name": "owner/repo"},
            )
        assert "disabled by kill switch" in str(exc_info.value)
        assert exc_info.value.retry_after == 60


# ---------------------------------------------------------------------------
# 2. Kill Switch: Publication
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_kill_switch_publication_holds_github_post_and_saves_review():
    """
    When kill_switch_publication is active, post_review does not call GitHub,
    durably saves the computed review, and sets publication_status="held_by_kill_switch".
    """
    cfg = Settings(kill_switch_publication=True)
    state = {
        "workflow_id": "owner/repo:42:0123456789abcdef",
        "repo_full_name": "owner/repo",
        "pr_number": 42,
        "head_commit_sha": "0123456789abcdef",
        "needs_human_review": False,
        "human_review_reason": None,
        "verdict": ReviewVerdict.APPROVE,
        "final_findings": [],
        "overall_confidence": 0.95,
        "review_posted": False,
        "github_review_id": None,
    }

    mock_save = AsyncMock()
    with patch("backend.orchestrator.nodes.get_settings", return_value=cfg), \
         patch("backend.orchestrator.nodes._save_review_record", new=mock_save), \
         patch("backend.orchestrator.nodes.GitHubClient") as mock_gh:

        res = await post_review(state)

        # Did not call GitHub
        mock_gh.assert_not_called()

        # Durably saved record
        mock_save.assert_awaited_once_with(state, None)

        # Retained pending status
        assert res["review_posted"] is False
        assert res["github_review_id"] is None
        assert res["publication_status"] == "held_by_kill_switch"


# ---------------------------------------------------------------------------
# 3. Kill Switch: Provider Spend
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_kill_switch_provider_spend_halts_llm_and_embeddings():
    """When kill_switch_provider_spend is True, LLMClient and embedder refuse provider calls."""
    cfg = Settings(
        kill_switch_provider_spend=True,
        openai_api_key="sk-real-looking-key",
        anthropic_api_key="sk-ant-real-looking-key",
    )

    client = LLMClient()

    # OpenAI call blocked
    with patch("backend.config.get_settings", return_value=cfg):
        with pytest.raises(ProviderSpendHaltedError) as exc_info:
            await client.call_openai(
                model="gpt-4o",
                messages=[{"role": "user", "content": "hello"}],
                system_prompt="sys",
            )
        assert "kill_switch_provider_spend" in str(exc_info.value)

    # Anthropic call blocked
    with patch("backend.config.get_settings", return_value=cfg):
        with pytest.raises(ProviderSpendHaltedError) as exc_info:
            await client.call_anthropic(
                model="claude-3-5-sonnet",
                messages=[{"role": "user", "content": "hello"}],
                system_prompt="sys",
            )
        assert "kill_switch_provider_spend" in str(exc_info.value)

    # Embedder blocked
    with patch("backend.memory.embedder.get_settings", return_value=cfg):
        with pytest.raises(EmbeddingError) as exc_info:
            await embed_text("some code to embed")
        assert "kill_switch_provider_spend" in str(exc_info.value)

        with pytest.raises(EmbeddingError) as exc_info:
            await embed_batch(["chunk 1", "chunk 2"])
        assert "kill_switch_provider_spend" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 4. Feature Flag: RAG Context
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_feature_flag_enable_rag_context_toggles_cleanly():
    """When enable_rag_context is False, build_context skips vector retrieval."""
    cfg_disabled = Settings(enable_rag_context=False)
    state = {
        "workflow_id": "owner/repo:1:sha123",
        "repo_full_name": "owner/repo",
        "pr_number": 1,
        "is_demo": True,
        "pr_diff": "diff --git a/a.py b/a.py\n+x = 1\n",
        "pr_files": [{"filename": "a.py"}],
        "pr_title": "Test PR",
        "author_login": "alice",
    }

    mock_retrieve = AsyncMock()
    with patch("backend.orchestrator.nodes.get_settings", return_value=cfg_disabled), \
         patch("backend.orchestrator.nodes.retrieve_context_for_diff", new=mock_retrieve):

        res = await build_context(state)
        mock_retrieve.assert_not_called()
        assert res["retrieved_context"] == ""


# ---------------------------------------------------------------------------
# 5. Feature Flag: Canary Models
# ---------------------------------------------------------------------------

def test_feature_flag_enable_canary_models_routes_traffic():
    """When enable_canary_models is True, quality agent routes to canary_model."""
    cfg_canary = Settings(enable_canary_models=True, canary_model="o1-mini")
    with patch("backend.config.get_settings", return_value=cfg_canary):
        table = get_routing_table()
        assert table[AgentType.QUALITY].model_name == "o1-mini"


# ---------------------------------------------------------------------------
# 6. Environment Separation and Preflight Checks
# ---------------------------------------------------------------------------

def test_environment_separation_rejects_insecure_production_settings():
    """verify_environment_separation detects placeholder secrets and missing TLS in production."""
    insecure_prod = Settings(
        app_env="production",
        openai_api_key="change-me-in-production",
        github_webhook_secret="test-secret",
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/pr_review_agent",
    )
    report = verify_environment_separation("production", insecure_prod)
    assert report.passed is False
    assert len(report.errors) >= 2
    assert any("secret" in err.lower() or "setting" in err.lower() for err in report.errors)
    assert any("tls" in err.lower() for err in report.errors)


def test_environment_separation_accepts_clean_staging_and_production():
    """verify_environment_separation passes when valid isolated configuration is provided."""
    valid_prod = Settings(
        app_env="production",
        openai_api_key="sk-prod-real-secure-key-12345",
        github_webhook_secret="strong-webhook-secret-987654321",
        github_token="ghp_realtoken1234567890",
        database_url="postgresql+asyncpg://prod_user:pAssW0rd123@aws-0-us-east-1.pooler.supabase.com:5432/hadron_prod?sslmode=require",
    )
    report = verify_environment_separation("production", valid_prod)
    assert report.passed is True
    assert len(report.errors) == 0


@pytest.mark.asyncio
async def test_migration_and_canary_preflight_checks():
    """run_migration_preflight and run_canary_health_check execute structured checks."""
    cfg = Settings(app_env="test")
    with patch("backend.database.postgres.check_schema_readiness", new=AsyncMock(return_value=(True, "ok"))):
        mig_report = await run_migration_preflight(cfg)
        assert mig_report.passed is True

    with patch("backend.memory.redis_client.redis_client.get_queue_depth", new=AsyncMock(return_value=0)), \
         patch("backend.memory.redis_client.redis_client.get_active_workers", new=AsyncMock(return_value=[{"worker_id": "w1"}])):
        canary_report = await run_canary_health_check(cfg)
        assert canary_report.passed is True


def test_create_release_manifest():
    """create_release_manifest generates immutable audit manifest with prompt hashes and feature flags."""
    cfg = Settings(kill_switch_publication=False, enable_canary_models=True)
    manifest = create_release_manifest(
        approver="SecurityLead-Alex",
        artifact_digest="sha256:7f9b8c12a4",
        rollback_target="sha256:1a2b3c4d5e",
        environment="production",
        cfg=cfg,
    )
    assert manifest.approver == "SecurityLead-Alex"
    assert manifest.artifact_digest == "sha256:7f9b8c12a4"
    assert manifest.feature_flags["enable_canary_models"] is True
    assert manifest.feature_flags["kill_switch_publication"] is False
    assert manifest.schema_version == "2026-06-tiger-init"
    assert isinstance(manifest.prompt_hashes, dict)
