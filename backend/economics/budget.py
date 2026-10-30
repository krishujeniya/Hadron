# backend/economics/budget.py
#
# Phase 16 / Gate B T18 — BudgetGuard: atomic budget reservation and cap enforcement.
#
# CONTRACT:
#   - Atomic reservation before dispatching LLM, embedding, or judge calls.
#   - Reconciles actual token usage and releases unused reservation upon completion.
#   - Full release on error, timeout, or cancellation.
#   - Honest status reporting distinguishing settled spend, active reservations,
#     hard vs advisory caps, and ledger health.
#

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
from typing import AsyncIterator, Optional

from backend.config.settings import Settings, get_settings
from backend.economics.ledger import (
    CostLedger,
    CostLedgerUnavailableError,
    CostReservation,
    get_cost_ledger,
)

logger = logging.getLogger(__name__)


class BudgetExceededError(Exception):
    """Raised when the daily or review LLM-spend cap would be breached by in-flight work."""

    def __init__(
        self,
        current_spend_usd: float,
        cap_usd: float,
        headroom_usd: float,
        active_reservations_usd: float = 0.0,
        scope: str = "daily",
        reason: str = "cap_reached",
    ) -> None:
        self.current_spend_usd = current_spend_usd
        self.cap_usd = cap_usd
        self.headroom_usd = headroom_usd
        self.active_reservations_usd = active_reservations_usd
        self.scope = scope
        self.reason = reason
        super().__init__(
            f"{scope.capitalize()} LLM budget cap of ${cap_usd:.2f} reached ({reason}). "
            f"Settled spend: ${current_spend_usd:.4f}. "
            f"Active in-flight reservations: ${active_reservations_usd:.4f}. "
            f"Headroom: ${headroom_usd:.4f}. "
            f"Review will be routed to HITL."
        )


class BudgetGuard:
    """
    Enforces daily and per-review spend caps via atomic reservations.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        ledger: Optional[CostLedger] = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._ledger = ledger or get_cost_ledger()

    @property
    def daily_cap_usd(self) -> float:
        return float(self._settings.daily_budget_usd)

    @property
    def per_review_cap_usd(self) -> float:
        return float(self._settings.per_review_budget_usd)

    async def current_daily_spend_usd(self, tenant_id: str = "default") -> float:
        """Return cumulative USD spent in the current UTC day."""
        try:
            spent, _ = await self._ledger.get_daily_spend(tenant_id=tenant_id)
            return spent
        except CostLedgerUnavailableError:
            return 0.0

    async def check_daily_budget(
        self,
        tenant_id: str = "default",
        required_usd: float = 0.0,
    ) -> None:
        """
        Pre-flight check: raises BudgetExceededError if daily cap + active reservations
        leave no room for `required_usd`.
        """
        cap = self.daily_cap_usd
        if cap <= 0:
            return  # disabled

        try:
            spent, is_degraded = await self._ledger.get_daily_spend(tenant_id=tenant_id)
        except CostLedgerUnavailableError as err:
            if self._settings.budget_fail_closed:
                raise BudgetExceededError(
                    current_spend_usd=0.0,
                    cap_usd=cap,
                    headroom_usd=0.0,
                    active_reservations_usd=0.0,
                    scope="daily",
                    reason="cost_ledger_unavailable",
                ) from err
            spent = 0.0

        active_res = await self._ledger.get_active_reserved_usd(tenant_id=tenant_id)
        committed = spent + active_res + required_usd
        if committed >= cap:
            headroom = max(0.0, cap - (spent + active_res))
            raise BudgetExceededError(
                current_spend_usd=spent,
                cap_usd=cap,
                headroom_usd=headroom,
                active_reservations_usd=active_res,
                scope="daily",
                reason="cap_reached",
            )

    async def reserve(
        self,
        amount_usd: float,
        workflow_id: Optional[str] = None,
        agent_type: str = "agent",
        tenant_id: str = "default",
    ) -> CostReservation:
        """Atomically reserves budget headroom before task execution."""
        return await self._ledger.reserve(
            amount_usd=amount_usd,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            agent_type=agent_type,
            daily_cap_usd=self.daily_cap_usd,
            per_review_cap_usd=self.per_review_cap_usd,
            enforce_review_cap=bool(self._settings.enforce_per_review_budget),
        )

    async def reconcile(
        self,
        reservation: CostReservation,
        actual_cost_usd: float,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float = 0.0,
        is_valid_json: bool = True,
        idempotency_key: Optional[str] = None,
        call_type: str = "llm",
    ) -> None:
        """Reconciles actual token usage and settles reservation."""
        await self._ledger.settle(
            reservation=reservation,
            actual_cost_usd=actual_cost_usd,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            is_valid_json=is_valid_json,
            idempotency_key=idempotency_key,
            call_type=call_type,
        )

    async def release(self, reservation: CostReservation) -> None:
        """Releases the reservation without charging (on error, cancel, or timeout)."""
        await self._ledger.release(reservation)

    @asynccontextmanager
    async def reserve_context(
        self,
        amount_usd: float,
        workflow_id: Optional[str] = None,
        agent_type: str = "agent",
        tenant_id: str = "default",
    ) -> AsyncIterator[CostReservation]:
        """
        Async context manager ensuring atomic reservation and guaranteed cleanup
        on error, timeout, or cancellation.
        """
        res = await self.reserve(
            amount_usd=amount_usd,
            workflow_id=workflow_id,
            agent_type=agent_type,
            tenant_id=tenant_id,
        )
        try:
            yield res
        except Exception:
            if res.is_active:
                await self.release(res)
            raise
        finally:
            if res.is_active:
                await self.release(res)

    async def status(self, tenant_id: str = "default") -> dict:
        """Return structured status for the /budget endpoint."""
        return await self._ledger.status(tenant_id=tenant_id)
