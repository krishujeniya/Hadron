# backend/governance/legal_hold.py
#
# Legal-hold management: freezes purges and deletions for designated tenants.

import logging
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.governance.models import LegalHoldRecord

logger = logging.getLogger(__name__)


class LegalHoldActiveError(Exception):
    """Raised when an operation (purge, deletion) is blocked by an active legal hold."""

    def __init__(self, tenant_id: str, reason: str = ""):
        self.tenant_id = tenant_id
        self.reason = reason
        super().__init__(
            f"Tenant '{tenant_id}' is subject to an active legal hold: {reason}. "
            f"Data deletion or purge operations are prohibited."
        )


async def is_tenant_on_legal_hold(session: AsyncSession, tenant_id: str) -> bool:
    """
    Returns True if the tenant has an active legal hold.
    """
    stmt = (
        select(LegalHoldRecord)
        .where(LegalHoldRecord.tenant_id == tenant_id)
        .where(LegalHoldRecord.active.is_(True))
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def place_legal_hold(
    session: AsyncSession,
    tenant_id: str,
    reason: str,
    placed_by: str,
) -> LegalHoldRecord:
    """
    Places an active legal hold on a tenant.
    """
    record = LegalHoldRecord(
        tenant_id=tenant_id,
        reason=reason,
        placed_by=placed_by,
        placed_at=datetime.now(timezone.utc),
        active=True,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    logger.warning("Legal hold placed | tenant=%s placed_by=%s reason=%s", tenant_id, placed_by, reason)
    return record


async def release_legal_hold(
    session: AsyncSession,
    tenant_id: str,
    released_by: str,
) -> bool:
    """
    Releases any active legal hold on a tenant.
    Returns True if a hold was released, False if no active hold was found.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        update(LegalHoldRecord)
        .where(LegalHoldRecord.tenant_id == tenant_id)
        .where(LegalHoldRecord.active.is_(True))
        .values(
            active=False,
            released_at=now,
            released_by=released_by,
        )
    )
    res = await session.execute(stmt)
    await session.commit()
    released = (res.rowcount or 0) > 0
    if released:
        logger.info("Legal hold released | tenant=%s released_by=%s", tenant_id, released_by)
    return released


async def list_legal_holds(
    session: AsyncSession,
    tenant_id: str | None = None,
    active_only: bool = True,
) -> Sequence[LegalHoldRecord]:
    """
    Lists legal hold records.
    """
    stmt = select(LegalHoldRecord)
    if tenant_id:
        stmt = stmt.where(LegalHoldRecord.tenant_id == tenant_id)
    if active_only:
        stmt = stmt.where(LegalHoldRecord.active.is_(True))
    stmt = stmt.order_by(LegalHoldRecord.placed_at.desc())
    result = await session.execute(stmt)
    return result.scalars().all()
