"""
backend/auth/principal.py

Unified Authenticated Principal model for Hadron.
Represents the verified server-side identity and authorization context of the caller.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from backend.security.rbac import Role


class Principal(BaseModel):
    """
    Verified server-derived principal.
    Never trusts client-supplied headers for role or identity escalation.
    """
    id: str = Field(..., description="Unique caller identifier (user login, API key identifier, or system id)")
    role: Role = Field(default=Role.VIEWER, description="Verified server-derived role")
    account: str | None = Field(default=None, description="GitHub account or organization scope")
    auth_method: str = Field(default="api_key", description="Authentication mechanism: api_key, session, oauth, or bearer")
    tenant_id: str | None = Field(default=None, description="Workspace or tenant identifier for data isolation")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional verified session claims")

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN

    @property
    def is_reviewer(self) -> bool:
        return self.role in (Role.REVIEWER, Role.ADMIN)
