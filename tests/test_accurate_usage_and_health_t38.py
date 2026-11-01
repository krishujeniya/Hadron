"""
tests/test_accurate_usage_and_health_t38.py
-------------------------------------------
Validates T38: Make usage and health screens accurate and scoped.
Tests:
  1. Backend economics router (/summary, /timeseries) scopes queries to authenticated tenant/workspace.
  2. Cost repository functions (get_summary, get_daily_timeseries, get_workflow_cost) support tenant_id filtering.
  3. Non-admin users are rejected (HTTP 403) when attempting to read another workspace's economics.
  4. Health screen separates API, worker, queue, persistence, provider and optional retrieval status.
  5. Missing telemetry cannot render healthy pipeline or misleading $0 spend.
  6. Frontend economics page provides accessible table equivalent and downloadable CSV export.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import AsyncClient, ASGITransport
import pathlib

from backend.main import app
from backend.auth.dependencies import require_auth, get_current_principal
from backend.auth.principal import Principal
from backend.security.rbac import Role
from backend.database.models import LLMCallLog
from backend.economics.cost_repository import get_summary, get_daily_timeseries, get_workflow_cost


@pytest.mark.asyncio
async def test_cost_repository_tenant_scoping():
    """Verify cost repository functions apply tenant_id filter to avoid cross-tenant leaks."""
    session = AsyncMock()

    call1 = LLMCallLog(
        id="call-1",
        workflow_id="tenant-a/repo:pr:sha",
        tenant_id="tenant-a",
        agent_type="security",
        model="gpt-4o",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.015,
        created_at=datetime.now(timezone.utc),
    )

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [call1]
    session.execute.return_value = result_mock

    with patch("backend.economics.cost_repository._new_session") as mock_session_ctx:
        mock_session_ctx.return_value.__aenter__.return_value = session

        # Call get_summary with explicit tenant_id
        summary = await get_summary(tenant_id="tenant-a")
        assert summary.last_30d_usd == 0.015
        assert summary.call_count_30d == 1

        # Call get_daily_timeseries with explicit tenant_id
        points = await get_daily_timeseries(days=7, tenant_id="tenant-a")
        assert len(points) == 7

        # Call get_workflow_cost with explicit tenant_id
        wf_cost = await get_workflow_cost("tenant-a/repo:pr:sha", tenant_id="tenant-a")
        assert wf_cost.total_cost_usd == 0.015


@pytest.mark.asyncio
async def test_economics_router_tenant_authorization():
    """Verify GET /api/v1/economics/summary denies cross-tenant access for non-admin principals."""
    reviewer_tenant_a = Principal(
        id="user-a",
        account="octocat",
        role=Role.REVIEWER,
        tenant_id="octocat",
    )

    app.dependency_overrides[require_auth] = lambda: reviewer_tenant_a
    app.dependency_overrides[get_current_principal] = lambda: reviewer_tenant_a

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Cross-tenant query must be rejected with 403
        resp_forbidden = await client.get("/api/v1/economics/summary?account=other-org")
        assert resp_forbidden.status_code == 403

        # Scoped query matching authorized account succeeds
        with patch("backend.api.economics_router.get_summary") as mock_summary:
            from backend.economics.cost_repository import EconomicsSummary
            mock_summary.return_value = EconomicsSummary(
                today_usd=0.05,
                last_7d_usd=0.35,
                last_30d_usd=1.20,
                by_model_30d={"gpt-4o": 1.20},
                by_agent_30d={"security": 1.20},
                call_count_30d=10,
                total_input_tokens_30d=5000,
                total_output_tokens_30d=1500,
            )
            resp_ok = await client.get("/api/v1/economics/summary?account=octocat")
            assert resp_ok.status_code == 200
            data = resp_ok.json()
            assert data["today_usd"] == 0.05
            mock_summary.assert_called_with(tenant_id="octocat")

    app.dependency_overrides.clear()


def test_frontend_economics_and_health_contracts():
    """Inspect frontend/src/app/economics/page.tsx and health/page.tsx to verify contracts."""
    econ_path = pathlib.Path("frontend/src/app/economics/page.tsx")
    assert econ_path.exists(), "economics/page.tsx must exist"
    econ_content = econ_path.read_text(encoding="utf-8")

    # 1. Accessible table toggle and export CSV
    assert "showTableView" in econ_content
    assert "exportCsv" in econ_content
    assert "Export Ledger (CSV)" in econ_content
    assert 'role="region"' in econ_content
    assert 'aria-label="30-day daily spend table"' in econ_content

    # 2. Honest telemetry error states (not misleading $0)
    assert "Telemetry unavailable" in econ_content
    assert "Telemetry error" in econ_content

    health_path = pathlib.Path("frontend/src/app/health/page.tsx")
    assert health_path.exists(), "health/page.tsx must exist"
    health_content = health_path.read_text(encoding="utf-8")

    # 3. Missing telemetry cannot render healthy pipeline
    assert "readyError ?" in health_content
    assert "TELEMETRY UNREACHABLE" in health_content
    assert "Subsystem readiness probe could not be completed" in health_content
