# backend/economics/ledger.py
#
# Reliable Cost Ledger and Atomic Reservation Engine (Phase 16 / Gate B T18).
#
# CONTRACT:
#   - Atomically reserve conservative cost before parallel or sequential LLM/embedding/judge dispatch.
#   - Reconcile actual token cost and release unused reservation on task completion.
#   - On error, timeout, or cancellation: release the entire reservation immediately.
#   - Idempotent and durable ledger writes: prevent duplicate charges on retry/replay.
#   - Distinguish unavailable usage from zero: never treat a DB outage as $0.00 spent.
#   - Bounded emergency behavior: enforce strict emergency spend ceiling during ledger outages.
#

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Optional
import uuid

from backend.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

# TTL for active in-flight reservations before automatic expiration (in seconds)
RESERVATION_TTL_SECONDS = 600  # 10 minutes


class CostLedgerUnavailableError(Exception):
    """Raised when the cost ledger (Postgres & Redis) is unreachable and cannot verify spend."""

    def __init__(self, message: str, last_cached_spend: float = 0.0) -> None:
        self.last_cached_spend = last_cached_spend
        super().__init__(f"{message} (last cached spend: ${last_cached_spend:.4f})")


@dataclass
class CostReservation:
    """Represents an atomic cost reservation for in-flight work."""

    reservation_id: str
    tenant_id: str
    workflow_id: Optional[str]
    agent_type: str
    amount_usd: float
    created_at: datetime
    status: str = "active"  # "active", "settled", "released", "expired"
    settled_amount_usd: Optional[float] = None
    settled_at: Optional[datetime] = None

    @property
    def is_active(self) -> bool:
        if self.status != "active":
            return False
        # Check TTL expiration
        age = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return age < RESERVATION_TTL_SECONDS


class CostLedger:
    """
    Manages atomic reservations, reconciliation, and durable ledger writes.
    Thread-safe and coroutine-safe with asyncio.Lock.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()
        self._lock = asyncio.Lock()
        self._active_reservations: dict[str, CostReservation] = {}
        # In-memory cached daily spend (updated on every settle and successful DB read)
        self._cached_daily_spend: dict[str, float] = {}  # "tenant_id:YYYY-MM-DD" -> spend_usd
        # Emergency spend counter used during DB outages
        self._emergency_spend_usd: float = 0.0

    def _today_key(self, tenant_id: str = "default", at: Optional[datetime] = None) -> str:
        target = at or datetime.now(timezone.utc)
        return f"{tenant_id}:{target.strftime('%Y-%m-%d')}"

    async def _prune_expired_locked(self) -> None:
        """Prunes reservations older than RESERVATION_TTL_SECONDS."""
        now = datetime.now(timezone.utc)
        expired_ids = []
        for res_id, res in self._active_reservations.items():
            if res.status == "active" and (now - res.created_at).total_seconds() >= RESERVATION_TTL_SECONDS:
                res.status = "expired"
                expired_ids.append(res_id)
        for res_id in expired_ids:
            logger.warning("cost_reservation_expired | res_id=%s amount=%.6f", res_id, self._active_reservations[res_id].amount_usd)
            del self._active_reservations[res_id]

    async def get_active_reserved_usd(
        self,
        tenant_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
    ) -> float:
        """Returns the sum of all currently active unexpired reservations."""
        async with self._lock:
            await self._prune_expired_locked()
            total = 0.0
            for res in self._active_reservations.values():
                if res.status != "active":
                    continue
                if tenant_id and res.tenant_id != tenant_id:
                    continue
                if workflow_id and res.workflow_id != workflow_id:
                    continue
                total += res.amount_usd
            return round(total, 6)

    async def get_daily_spend(
        self,
        tenant_id: Optional[str] = None,
        at: Optional[datetime] = None,
    ) -> tuple[float, bool]:
        """
        Returns (spend_usd, is_degraded).
        Distinguishes unavailable usage from zero!
        If DB query fails, falls back to cached spend and returns (cached_spend, True).
        If both fail, raises CostLedgerUnavailableError.
        """
        from backend.economics.cost_repository import query_daily_spend_db

        t_id = tenant_id or "default"
        day_key = self._today_key(t_id, at)

        try:
            db_spend = await query_daily_spend_db(tenant_id=tenant_id, at=at)
            # Update cache on successful DB read
            async with self._lock:
                self._cached_daily_spend[day_key] = db_spend
            return db_spend, False
        except Exception as exc:
            logger.warning("cost_ledger_db_query_failed | tenant=%s error=%s", t_id, exc)
            # Check cached value
            async with self._lock:
                if day_key in self._cached_daily_spend:
                    cached = self._cached_daily_spend[day_key] + self._emergency_spend_usd
                    logger.info("cost_ledger_using_cached_spend | key=%s spend=%.4f", day_key, cached)
                    return round(cached, 6), True

            # If no cached spend is known and DB failed:
            raise CostLedgerUnavailableError(
                f"Cannot determine spend for tenant '{t_id}' — database unreachable",
                last_cached_spend=0.0,
            ) from exc

    async def reserve(
        self,
        amount_usd: float,
        tenant_id: str = "default",
        workflow_id: Optional[str] = None,
        agent_type: str = "agent",
        daily_cap_usd: float = 50.0,
        per_review_cap_usd: float = 0.50,
        enforce_review_cap: bool = False,
    ) -> CostReservation:
        """
        Atomically reserves conservative cost against daily and per-review budgets.
        Raises BudgetExceededError if headroom is insufficient.
        """
        from backend.economics.budget import BudgetExceededError

        req_amount = max(0.0001, float(amount_usd))
        t_id = tenant_id or "default"
        day_key = self._today_key(t_id)

        # 1. Query current settled spend outside the lock to prevent deadlock and avoid holding lock during I/O
        is_emergency = False
        try:
            settled_spend, is_degraded = await self.get_daily_spend(tenant_id=t_id)
        except CostLedgerUnavailableError as err:
            if self._settings.budget_fail_closed:
                raise BudgetExceededError(
                    current_spend_usd=0.0,
                    cap_usd=daily_cap_usd,
                    headroom_usd=0.0,
                    active_reservations_usd=0.0,
                    scope="daily",
                    reason="cost_ledger_unavailable",
                ) from err
            is_emergency = True
            is_degraded = True

        async with self._lock:
            await self._prune_expired_locked()

            if is_emergency:
                # Bounded emergency mode: check emergency headroom cap
                em_cap = float(self._settings.emergency_budget_usd)
                if self._emergency_spend_usd + req_amount > em_cap:
                    raise BudgetExceededError(
                        current_spend_usd=self._emergency_spend_usd,
                        cap_usd=em_cap,
                        headroom_usd=max(0.0, em_cap - self._emergency_spend_usd),
                        active_reservations_usd=0.0,
                        scope="emergency",
                        reason="emergency_headroom_exhausted",
                    )
                settled_spend = self._emergency_spend_usd
                self._emergency_spend_usd += req_amount

            # Calculate active reservations for this tenant
            active_res_usd = 0.0
            workflow_res_usd = 0.0
            for r in self._active_reservations.values():
                if r.status == "active":
                    if r.tenant_id == t_id:
                        active_res_usd += r.amount_usd
                    if workflow_id and r.workflow_id == workflow_id:
                        workflow_res_usd += r.amount_usd

            # Daily cap verification
            if daily_cap_usd > 0:
                committed_daily = settled_spend + active_res_usd + req_amount
                if committed_daily > daily_cap_usd:
                    headroom = max(0.0, daily_cap_usd - (settled_spend + active_res_usd))
                    logger.warning(
                        "budget_reservation_rejected_daily | tenant=%s req=$%.4f committed=$%.4f cap=$%.2f headroom=$%.4f",
                        t_id, req_amount, committed_daily, daily_cap_usd, headroom,
                    )
                    raise BudgetExceededError(
                        current_spend_usd=settled_spend,
                        cap_usd=daily_cap_usd,
                        headroom_usd=headroom,
                        active_reservations_usd=active_res_usd,
                        scope="daily",
                        reason="daily_cap_reached",
                    )

            # Optional per-review cap verification
            if enforce_review_cap and per_review_cap_usd > 0 and workflow_id:
                # Calculate review committed
                # (review settled spend will be tracked if needed, + workflow_res_usd + req_amount)
                if (workflow_res_usd + req_amount) > per_review_cap_usd:
                    headroom_wf = max(0.0, per_review_cap_usd - workflow_res_usd)
                    logger.warning(
                        "budget_reservation_rejected_review | wf=%s req=$%.4f cap=$%.2f headroom=$%.4f",
                        workflow_id, req_amount, per_review_cap_usd, headroom_wf,
                    )
                    raise BudgetExceededError(
                        current_spend_usd=workflow_res_usd,
                        cap_usd=per_review_cap_usd,
                        headroom_usd=headroom_wf,
                        active_reservations_usd=workflow_res_usd,
                        scope="review",
                        reason="review_cap_reached",
                    )

            # Atomically register reservation
            res_id = str(uuid.uuid4())
            reservation = CostReservation(
                reservation_id=res_id,
                tenant_id=t_id,
                workflow_id=workflow_id,
                agent_type=agent_type,
                amount_usd=req_amount,
                created_at=datetime.now(timezone.utc),
                status="active",
            )
            self._active_reservations[res_id] = reservation
            logger.info(
                "budget_reservation_granted | id=%s tenant=%s wf=%s agent=%s amount=$%.6f",
                res_id, t_id, workflow_id, agent_type, req_amount,
            )
            return reservation

    async def settle(
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
        """
        Releases the reservation and persists the settled cost idempotently into the ledger.
        """
        from backend.economics.cost_repository import record_llm_call

        async with self._lock:
            if reservation.reservation_id in self._active_reservations:
                del self._active_reservations[reservation.reservation_id]
            reservation.status = "settled"
            reservation.settled_amount_usd = actual_cost_usd
            reservation.settled_at = datetime.now(timezone.utc)

            # Update cached daily spend
            day_key = self._today_key(reservation.tenant_id)
            self._cached_daily_spend[day_key] = self._cached_daily_spend.get(day_key, 0.0) + actual_cost_usd

        # Durable, idempotent ledger write to Postgres
        idem_key = idempotency_key or f"res:{reservation.reservation_id}"
        await record_llm_call(
            workflow_id=reservation.workflow_id,
            tenant_id=reservation.tenant_id,
            idempotency_key=idem_key,
            agent_type=reservation.agent_type,
            call_type=call_type,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=actual_cost_usd,
            latency_ms=latency_ms,
            is_valid_json=is_valid_json,
            status="settled",
        )
        logger.info(
            "budget_reservation_settled | res_id=%s reserved=$%.6f settled=$%.6f model=%s",
            reservation.reservation_id, reservation.amount_usd, actual_cost_usd, model,
        )

    async def release(self, reservation: CostReservation) -> None:
        """Releases the reservation without incurring cost (e.g. on error or cancellation)."""
        async with self._lock:
            if reservation.reservation_id in self._active_reservations:
                del self._active_reservations[reservation.reservation_id]
            reservation.status = "released"
        logger.info(
            "budget_reservation_released | res_id=%s amount=$%.6f",
            reservation.reservation_id, reservation.amount_usd,
        )

    async def record_direct_entry(
        self,
        *,
        workflow_id: Optional[str],
        tenant_id: Optional[str] = None,
        agent_type: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        latency_ms: float = 0.0,
        is_valid_json: bool = True,
        idempotency_key: Optional[str] = None,
        call_type: str = "llm",
    ) -> None:
        """Records an unreserved direct entry (e.g., embeddings, judges) idempotently."""
        from backend.economics.cost_repository import record_llm_call

        t_id = tenant_id or "default"
        async with self._lock:
            day_key = self._today_key(t_id)
            self._cached_daily_spend[day_key] = self._cached_daily_spend.get(day_key, 0.0) + cost_usd

        await record_llm_call(
            workflow_id=workflow_id,
            tenant_id=t_id,
            idempotency_key=idempotency_key,
            agent_type=agent_type,
            call_type=call_type,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            is_valid_json=is_valid_json,
            status="settled",
        )

    async def status(self, tenant_id: str = "default") -> dict[str, Any]:
        """Provides full ledger transparency for UI and status endpoints."""
        t_id = tenant_id or "default"
        cap = float(self._settings.daily_budget_usd)
        per_review_cap = float(self._settings.per_review_budget_usd)

        try:
            spent, is_degraded = await self.get_daily_spend(tenant_id=t_id)
            ledger_status = "degraded" if is_degraded else "settled"
        except CostLedgerUnavailableError:
            spent = self._emergency_spend_usd
            is_degraded = True
            ledger_status = "unavailable"

        active_res = await self.get_active_reserved_usd(tenant_id=t_id)
        committed = spent + active_res
        headroom = max(0.0, cap - committed) if cap > 0 else 0.0
        utilization = (committed / cap) if cap > 0 else 0.0

        return {
            "daily_cap_usd": round(cap, 4),
            "daily_spent_usd": round(spent, 6),
            "daily_reserved_usd": round(active_res, 6),
            "daily_committed_usd": round(committed, 6),
            "daily_headroom_usd": round(headroom, 6),
            "daily_utilization": round(utilization, 4),
            "per_review_cap_usd": round(per_review_cap, 4),
            "hard_limit_enforced": True,
            "per_review_cap_enforced": bool(self._settings.enforce_per_review_budget),
            "is_estimate": is_degraded,
            "ledger_status": ledger_status,
            "exceeded": committed >= cap and cap > 0,
        }


# Global ledger singleton
cost_ledger = CostLedger()


def get_cost_ledger() -> CostLedger:
    """Return the global CostLedger instance."""
    return cost_ledger
