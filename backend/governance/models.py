# backend/governance/models.py
#
# SQLAlchemy ORM models for data governance, legal holds, and scoped exports.

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.postgres import Base


class LegalHoldRecord(Base):
    """
    Tracks active and historical legal holds on tenant repositories.
    While active=True, all automated data purges and tenant deletions
    are strictly rejected.
    """

    __tablename__ = "legal_holds"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique identifier for this legal hold record",
    )

    tenant_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Tenant organization or account identifier subject to hold",
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Justification, docket reference, or legal authority for the hold",
    )

    placed_by: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Principal ID of compliance officer who placed the hold",
    )

    placed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    released_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_legal_holds_tenant_active", "tenant_id", "active"),
    )


class DataExportRecord(Base):
    """
    Tracks tenant data export requests and expiration lifetimes.
    """

    __tablename__ = "data_exports"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    tenant_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    requested_by: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        default="ready",
        nullable=False,
    )

    manifest_summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="{}",
        comment="JSON summary of exported record counts and metadata",
    )
