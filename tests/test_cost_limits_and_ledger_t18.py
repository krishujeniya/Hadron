# tests/test_cost_limits_and_ledger_t18.py
#
# Acceptance test suite for Gate B Task T18:
# "Enforce cost limits with reservations and a reliable ledger"
#

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from backend.config.settings import Settings
from backend.economics import (
    BudgetExceededError,
    BudgetGuard,
    CostLedger,
    CostLedgerUnavailableError,
    CostReservation,
    UnknownModelPricingError,
    estimate_call_cost,
    get_cost_ledger,
    get_token_cost,
    record_cost_entry,
    record_llm_call,
)
from backend.main import app


@pytest.fixture
def custom_settings():
    return Settings(
        app_env="test",
        daily_budget_usd=1.00,
        per_review_budget_usd=0.20,
        enforce_per_review_budget=False,
        budget_fail_closed=False,
        emergency_budget_usd=0.50,
        strict_price_enforcement=False,
    )


@pytest.mark.asyncio
async def test_concurrent_fanout_reservation_blocks_at_daily_cap(custom_settings):
    """
    Concurrent agents requesting reservation at cap cannot breach the cap.
    If spend is $0.90 and cap is $1.00, only two $0.05 reservations succeed.
    """
    ledger = CostLedger(settings=custom_settings)
    guard = BudgetGuard(settings=custom_settings, ledger=ledger)

    # Seed initial spend of $0.90 (leaving $0.10 headroom)
    with patch.object(ledger, "get_daily_spend", AsyncMock(return_value=(0.90, False))):
        results = []
        errors = []

        async def _attempt_reserve(agent_name: str):
            try:
                res = await guard.reserve(
                    amount_usd=0.05,
                    workflow_id="org/repo:1:sha",
                    agent_type=agent_name,
                )
                results.append(res)
            except BudgetExceededError as bx:
                errors.append(bx)

        # 4 concurrent parallel agent reservations
        await asyncio.gather(
            _attempt_reserve("security"),
            _attempt_reserve("quality"),
            _attempt_reserve("test"),
            _attempt_reserve("docs"),
        )

        assert len(results) == 2, f"Expected exactly 2 reservations, got {len(results)}"
        assert len(errors) == 2, f"Expected exactly 2 budget rejections, got {len(errors)}"
        assert all(isinstance(e, BudgetExceededError) for e in errors)

        # Verify active reservations total exactly $0.10
        active_res = await ledger.get_active_reserved_usd()
        assert active_res == 0.10


@pytest.mark.asyncio
async def test_reservation_reconcile_and_release(custom_settings):
    """
    Settle frees reserved amount and restores unused headroom.
    """
    ledger = CostLedger(settings=custom_settings)
    guard = BudgetGuard(settings=custom_settings, ledger=ledger)

    with patch.object(ledger, "get_daily_spend", AsyncMock(return_value=(0.50, False))):
        # Reserve $0.05
        res = await guard.reserve(amount_usd=0.05, workflow_id="wf-1", agent_type="security")
        assert res.is_active
        assert await ledger.get_active_reserved_usd() == 0.05

        # Reconcile with actual cost $0.02
        with patch("backend.economics.cost_repository.record_llm_call", AsyncMock()):
            await guard.reconcile(
                reservation=res,
                actual_cost_usd=0.02,
                model="gpt-4o-mini",
                input_tokens=100,
                output_tokens=20,
            )

        assert not res.is_active
        assert res.status == "settled"
        assert res.settled_amount_usd == 0.02
        assert await ledger.get_active_reserved_usd() == 0.0


@pytest.mark.asyncio
async def test_reservation_release_on_error_or_timeout(custom_settings):
    """
    reserve_context context manager automatically releases reservation if exception occurs.
    """
    ledger = CostLedger(settings=custom_settings)
    guard = BudgetGuard(settings=custom_settings, ledger=ledger)

    with patch.object(ledger, "get_daily_spend", AsyncMock(return_value=(0.10, False))):
        with pytest.raises(RuntimeError):
            async with guard.reserve_context(amount_usd=0.08, workflow_id="wf-err") as res:
                assert res.is_active
                assert await ledger.get_active_reserved_usd() == 0.08
                raise RuntimeError("LLM network timeout!")

        # After exception block: reservation is cleaned up
        assert not res.is_active
        assert res.status == "released"
        assert await ledger.get_active_reserved_usd() == 0.0


@pytest.mark.asyncio
async def test_idempotent_ledger_writes_prevent_replay_double_spend():
    """
    Duplicate ledger writes with the same idempotency key are safely ignored.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from backend.database.models import Base, LLMCallLog
    from sqlalchemy import select

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    with patch("backend.economics.cost_repository._new_session", side_effect=session_factory):
        key = f"idem-test-{datetime.now(timezone.utc).timestamp()}"
        # First write
        await record_llm_call(
            workflow_id="org/repo:10:sha",
            tenant_id="tenant-acme",
            idempotency_key=key,
            agent_type="security",
            call_type="llm",
            model="gpt-4o-mini",
            input_tokens=500,
            output_tokens=100,
            cost_usd=0.0015,
            latency_ms=120.0,
        )

        # Replay second write with same idempotency key
        await record_llm_call(
            workflow_id="org/repo:10:sha",
            tenant_id="tenant-acme",
            idempotency_key=key,
            agent_type="security",
            call_type="llm",
            model="gpt-4o-mini",
            input_tokens=500,
            output_tokens=100,
            cost_usd=0.0015,
            latency_ms=120.0,
        )

        # Verify query
        async with session_factory() as session:
            stmt = select(LLMCallLog).where(LLMCallLog.idempotency_key == key)
            rows = (await session.execute(stmt)).scalars().all()
            assert len(rows) == 1, f"Expected exactly 1 row, got {len(rows)}"

    await test_engine.dispose()


def test_unknown_model_pricing_behavior():
    """
    Unknown models use conservative fallback by default, or raise when strict.
    """
    # Known model
    cost = get_token_cost("gpt-4o-mini", input_tokens=1000, output_tokens=1000)
    assert cost > 0.0

    # Unknown model with strict=False -> conservative fallback, NEVER 0.0
    fallback_cost = get_token_cost("unknown-experimental-model", input_tokens=1000, output_tokens=1000, strict=False)
    assert fallback_cost > 0.0
    # $0.005 input + $0.015 output = $0.020 per 1k tokens
    assert fallback_cost == 0.020

    # Unknown model with strict=True -> raises UnknownModelPricingError
    with pytest.raises(UnknownModelPricingError):
        get_token_cost("unknown-experimental-model", input_tokens=1000, output_tokens=1000, strict=True)


@pytest.mark.asyncio
async def test_ledger_outage_distinguished_from_zero_and_emergency_bounded():
    """
    When DB is down, ledger raises CostLedgerUnavailableError rather than silently returning 0.0.
    Under budget_fail_closed=True, reservation is blocked.
    Under bounded emergency mode (fail_closed=False), spend is bounded by emergency_budget_usd.
    """
    fail_closed_settings = Settings(
        app_env="test",
        daily_budget_usd=50.0,
        budget_fail_closed=True,
    )
    ledger = CostLedger(settings=fail_closed_settings)
    guard = BudgetGuard(settings=fail_closed_settings, ledger=ledger)

    with patch("backend.economics.cost_repository.query_daily_spend_db", AsyncMock(side_effect=ConnectionError("DB Down"))):
        # Must raise CostLedgerUnavailableError from direct query
        with pytest.raises(CostLedgerUnavailableError):
            await ledger.get_daily_spend()

        # Under fail-closed, reservation fails with BudgetExceededError
        with pytest.raises(BudgetExceededError) as exc_info:
            await guard.reserve(amount_usd=0.05, workflow_id="wf-1")
        assert exc_info.value.reason == "cost_ledger_unavailable"

    # Now test bounded emergency mode
    emergency_settings = Settings(
        app_env="test",
        daily_budget_usd=50.0,
        budget_fail_closed=False,
        emergency_budget_usd=0.10,  # only $0.10 emergency headroom
    )
    em_ledger = CostLedger(settings=emergency_settings)
    em_guard = BudgetGuard(settings=emergency_settings, ledger=em_ledger)

    with patch("backend.economics.cost_repository.query_daily_spend_db", AsyncMock(side_effect=ConnectionError("DB Down"))):
        # First $0.06 succeeds
        res1 = await em_guard.reserve(amount_usd=0.06, workflow_id="wf-em-1")
        assert res1.is_active

        # Second $0.06 exceeds emergency bound of $0.10
        with pytest.raises(BudgetExceededError) as exc_info:
            await em_guard.reserve(amount_usd=0.06, workflow_id="wf-em-2")
        assert exc_info.value.reason == "emergency_headroom_exhausted"


@pytest.mark.asyncio
async def test_budget_status_api_reflects_reservations_and_limits(custom_settings):
    """
    /api/v1/economics/budget returns transparent status including active reservations.
    """
    from backend.auth.principal import Principal
    from backend.auth.dependencies import get_current_principal, require_auth
    from backend.security.rbac import Role

    mock_principal = Principal(
        id="test-user",
        account="acme-corp",
        role=Role.ADMIN,
    )
    app.dependency_overrides[get_current_principal] = lambda: mock_principal
    app.dependency_overrides[require_auth] = lambda: mock_principal

    ledger = CostLedger(settings=custom_settings)
    with patch("backend.api.economics_router.BudgetGuard", lambda: BudgetGuard(settings=custom_settings, ledger=ledger)):
        # Make an active reservation
        with patch.object(ledger, "get_daily_spend", AsyncMock(return_value=(0.25, False))):
            await ledger.reserve(amount_usd=0.05, tenant_id="acme-corp", workflow_id="wf-api")

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.get("/api/v1/economics/budget")
                assert resp.status_code == 200
                data = resp.json()

                assert data["daily_cap_usd"] == 1.00
                assert data["daily_spent_usd"] == 0.25
                assert data["daily_reserved_usd"] == 0.05
                assert data["daily_committed_usd"] == 0.30
                assert data["daily_headroom_usd"] == 0.70
                assert data["hard_limit_enforced"] is True
                assert data["is_estimate"] is False
                assert data["ledger_status"] == "settled"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_per_review_budget_enforcement_when_enabled():
    """
    When enforce_per_review_budget=True, reservations exceeding per_review_budget_usd are rejected.
    """
    review_settings = Settings(
        app_env="test",
        daily_budget_usd=50.0,
        per_review_budget_usd=0.10,
        enforce_per_review_budget=True,
    )
    ledger = CostLedger(settings=review_settings)
    guard = BudgetGuard(settings=review_settings, ledger=ledger)

    with patch.object(ledger, "get_daily_spend", AsyncMock(return_value=(1.00, False))):
        # First reservation of $0.06 for wf-pr-1 succeeds
        res1 = await guard.reserve(amount_usd=0.06, workflow_id="wf-pr-1")
        assert res1.is_active

        # Second reservation of $0.05 for same wf-pr-1 exceeds $0.10 review cap
        with pytest.raises(BudgetExceededError) as exc_info:
            await guard.reserve(amount_usd=0.05, workflow_id="wf-pr-1")
        assert exc_info.value.scope == "review"
        assert exc_info.value.reason == "review_cap_reached"

        # But a different workflow can still reserve
        res2 = await guard.reserve(amount_usd=0.05, workflow_id="wf-pr-2")
        assert res2.is_active
