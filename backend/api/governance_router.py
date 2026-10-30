# backend/api/governance_router.py
#
# REST API endpoints for Data Governance, Retention, Erasure, and Legal Holds.

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import require_auth
from backend.auth.principal import Principal
from backend.database.postgres import get_db
from backend.governance.deletion import delete_tenant_data
from backend.governance.export import export_tenant_data
from backend.governance.legal_hold import (
    LegalHoldActiveError,
    list_legal_holds,
    place_legal_hold,
    release_legal_hold,
)
from backend.governance.retention import RetentionPolicy, purge_expired_data
from backend.security.rbac import Permission, Role, require_permission

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/governance",
    tags=["governance"],
)


class ExportRequest(BaseModel):
    tenant_id: str = Field(..., description="Tenant organization or account identifier to export")
    expiration_hours: int = Field(default=24, ge=1, le=168, description="Export lifetime in hours")


class LegalHoldRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="Legal justification or docket reference")


class PurgeRequest(BaseModel):
    diff_retention_days: int = Field(default=14, ge=1)
    review_retention_days: int = Field(default=90, ge=1)
    event_retention_days: int = Field(default=365, ge=1)


@router.post(
    "/export",
    summary="Export tenant data archive",
    description="Generates machine-readable JSON archive of all tenant data (GDPR Art. 20).",
)
async def request_data_export(
    body: ExportRequest,
    principal: Principal = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    # Scoping check: non-admin can only export their own account/tenant
    if principal.role != Role.ADMIN and principal.account != body.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Principal '{principal.id}' cannot export data for tenant '{body.tenant_id}'.",
        )

    try:
        return await export_tenant_data(
            session=db,
            tenant_id=body.tenant_id,
            requested_by=principal.id,
            expiration_hours=body.expiration_hours,
        )
    except Exception as exc:
        logger.error("Export request failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(exc)}",
        ) from exc


@router.post(
    "/tenants/{tenant_id}/purge",
    summary="Offboard tenant and erase data",
    description="Permanently erases all tenant reviews, findings, embeddings, and context (GDPR Art. 17).",
)
async def purge_tenant_endpoint(
    tenant_id: str,
    principal: Principal = Depends(require_auth),
    _role: Role = Depends(require_permission(Permission.DATA_GOVERNANCE_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    try:
        return await delete_tenant_data(
            session=db,
            tenant_id=tenant_id,
            actor=principal.id,
        )
    except LegalHoldActiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("Tenant purge failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tenant erasure failed: {str(exc)}",
        ) from exc


@router.post(
    "/tenants/{tenant_id}/legal-hold",
    summary="Place legal hold on tenant",
    description="Freezes automated data purges and erasure operations for legal compliance.",
)
async def place_legal_hold_endpoint(
    tenant_id: str,
    body: LegalHoldRequest,
    principal: Principal = Depends(require_auth),
    _role: Role = Depends(require_permission(Permission.DATA_GOVERNANCE_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    record = await place_legal_hold(
        session=db,
        tenant_id=tenant_id,
        reason=body.reason,
        placed_by=principal.id,
    )
    return {
        "status": "placed",
        "id": record.id,
        "tenant_id": record.tenant_id,
        "reason": record.reason,
        "placed_at": record.placed_at.isoformat(),
        "active": record.active,
    }


@router.delete(
    "/tenants/{tenant_id}/legal-hold",
    summary="Release legal hold on tenant",
    description="Removes active legal hold and permits normal retention lifecycle.",
)
async def release_legal_hold_endpoint(
    tenant_id: str,
    principal: Principal = Depends(require_auth),
    _role: Role = Depends(require_permission(Permission.DATA_GOVERNANCE_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    released = await release_legal_hold(
        session=db,
        tenant_id=tenant_id,
        released_by=principal.id,
    )
    if not released:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active legal hold found for tenant '{tenant_id}'.",
        )
    return {"status": "released", "tenant_id": tenant_id}


@router.get(
    "/legal-holds",
    summary="List active legal holds",
)
async def list_legal_holds_endpoint(
    tenant_id: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    _role: Role = Depends(require_permission(Permission.DATA_GOVERNANCE_READ)),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    records = await list_legal_holds(session=db, tenant_id=tenant_id, active_only=active_only)
    return [
        {
            "id": r.id,
            "tenant_id": r.tenant_id,
            "reason": r.reason,
            "placed_by": r.placed_by,
            "placed_at": r.placed_at.isoformat() if r.placed_at else None,
            "active": r.active,
            "released_at": r.released_at.isoformat() if r.released_at else None,
            "released_by": r.released_by,
        }
        for r in records
    ]


@router.post(
    "/retention/run",
    summary="Trigger scheduled retention purge",
    description="Executes automated data retention lifecycle purge.",
)
async def run_retention_purge(
    body: PurgeRequest = PurgeRequest(),
    principal: Principal = Depends(require_auth),
    _role: Role = Depends(require_permission(Permission.DATA_GOVERNANCE_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    policy = RetentionPolicy(
        diff_retention_days=body.diff_retention_days,
        review_retention_days=body.review_retention_days,
        event_retention_days=body.event_retention_days,
    )
    return await purge_expired_data(session=db, policy=policy, actor=principal.id)
