# backend/economics/__init__.py
#
# Phase 16 / Gate B T18 — Economics, Cost Control & Reliable Ledger.
#

from backend.economics.cost_repository import (
    record_llm_call,
    get_daily_spend,
    get_workflow_cost,
    get_summary,
    get_daily_timeseries,
    query_daily_spend_db,
)
from backend.economics.budget import BudgetGuard, BudgetExceededError
from backend.economics.ledger import (
    CostLedger,
    CostReservation,
    CostLedgerUnavailableError,
    get_cost_ledger,
)
from backend.economics.pricing import (
    get_token_cost,
    estimate_call_cost,
    estimate_embedding_cost,
    UnknownModelPricingError,
    MODEL_TOKEN_PRICES,
)
from backend.economics.routing_advisor import recommend_model, would_have_saved

# Helper for recording non-reserved entries (e.g. embeddings, judges)
async def record_cost_entry(
    *,
    workflow_id: str | None = None,
    tenant_id: str | None = None,
    agent_type: str = "system",
    model: str = "text-embedding-3-large",
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float = 0.0,
    latency_ms: float = 0.0,
    is_valid_json: bool = True,
    idempotency_key: str | None = None,
    call_type: str = "llm",
) -> None:
    await get_cost_ledger().record_direct_entry(
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        agent_type=agent_type,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        is_valid_json=is_valid_json,
        idempotency_key=idempotency_key,
        call_type=call_type,
    )

__all__ = [
    "record_llm_call",
    "record_cost_entry",
    "get_daily_spend",
    "query_daily_spend_db",
    "get_workflow_cost",
    "get_summary",
    "get_daily_timeseries",
    "BudgetGuard",
    "BudgetExceededError",
    "CostLedger",
    "CostReservation",
    "CostLedgerUnavailableError",
    "get_cost_ledger",
    "get_token_cost",
    "estimate_call_cost",
    "estimate_embedding_cost",
    "UnknownModelPricingError",
    "MODEL_TOKEN_PRICES",
    "recommend_model",
    "would_have_saved",
]
