"""
backend/security/rbac.py

Phase 11: Role-Based Access Control
=====================================
Our system has two API actor types:

  1. GitHub webhook service account — authenticated by HMAC-SHA256 signature
     (handled in Phase 3 webhook_receiver/validator.py). This actor triggers
     reviews automatically and needs no RBAC — it only calls the webhook.

  2. Human operators — authenticated by X-API-Key (Phase 3 auth layer).
     Different operators have different capabilities:
       VIEWER   — read-only access (dashboards, audit logs)
       REVIEWER — can read and submit manual review decisions
       ADMIN    — full access including eval triggers and key management

Design decisions:

1. ADDITIVE ROLE MODEL — Each role inherits all permissions of roles below it.
   ADMIN ⊇ REVIEWER ⊇ VIEWER. This simplifies reasoning: to add a capability,
   just add a Permission to the appropriate level.

2. PERMISSIONS ARE FINE-GRAINED STRINGS — Not coarse "can_write" booleans.
   This lets us evolve the permission set without changing role definitions.
   Example: TRIGGER_EVAL can be granted to REVIEWER without granting
   MANAGE_API_KEYS.

3. FASTAPI INTEGRATION — require_permission() returns a FastAPI Depends()
   callable that can be used in route signatures directly. It reads the
   role from the X-Role header (set by the API gateway or test client).
   In production, the gateway validates the key and injects the role.

4. PermissionDeniedError subclasses HTTPException(403) — so FastAPI's
   default exception handler returns a well-formed 403 JSON response without
   any extra error-handling wiring.

5. NO GLOBAL STATE — RBACPolicy is a pure value object with no singletons.
   The DEFAULT_RBAC_POLICY constant is a convenience; callers can construct
   their own policy for tests.

Wiki ref: Client Isolation Layer — "Per-client policy objects enforce tool
allowlists, data residency, concurrent workflow limits, and audit levels
BEFORE any request reaches execution infrastructure." and "Security
boundaries are hard to retrofit. Design them in from the beginning."
(llmops-ai-agents/concepts/_pre-consolidation/Client-Isolation-Layer...)
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable

# Python 3.10 StrEnum shim (StrEnum added in 3.11)
try:
    from enum import StrEnum
except ImportError:
    class StrEnum(str, Enum):  # type: ignore[no-redef]
        pass


# ---------------------------------------------------------------------------
# Role & Permission enumerations
# ---------------------------------------------------------------------------

class Role(StrEnum):
    """
    Operator roles — ordered from least to most privileged.
    The integer ordering is used by requires_at_least().
    """
    VIEWER = "viewer"
    REVIEWER = "reviewer"
    ADMIN = "admin"


class Permission(StrEnum):
    """
    Fine-grained capabilities. Each permission maps to exactly one API
    operation or resource class.

    READ_REVIEWS       -- GET /api/v1/reviews, GET /api/v1/reviews/{id}
    READ_AUDIT_LOG     -- GET /api/v1/audit
    READ_QUEUE         -- GET /api/v1/queue
    SUBMIT_REVIEW      -- POST /api/v1/reviews/{id}/decision (HITL override)
    TRIGGER_EVAL       -- POST /api/v1/eval/run (Phase 9 regression gate)
    MANAGE_API_KEYS    -- POST/DELETE /api/v1/admin/keys
    OVERRIDE_VERDICT   -- POST /api/v1/reviews/{id}/override
    VIEW_COST_REPORT   -- GET /api/v1/admin/costs (Phase 16)
    """
    READ_REVIEWS = "read_reviews"
    READ_AUDIT_LOG = "read_audit_log"
    READ_QUEUE = "read_queue"
    SUBMIT_REVIEW = "submit_review"
    TRIGGER_EVAL = "trigger_eval"
    MANAGE_API_KEYS = "manage_api_keys"
    OVERRIDE_VERDICT = "override_verdict"
    VIEW_COST_REPORT = "view_cost_report"


# ---------------------------------------------------------------------------
# Role → Permission mapping
# ---------------------------------------------------------------------------
# ADDITIVE: each level includes all permissions from levels below it.

_VIEWER_PERMISSIONS: frozenset[Permission] = frozenset({
    Permission.READ_REVIEWS,
    Permission.READ_AUDIT_LOG,
    Permission.READ_QUEUE,
})

_REVIEWER_PERMISSIONS: frozenset[Permission] = _VIEWER_PERMISSIONS | frozenset({
    Permission.SUBMIT_REVIEW,
    Permission.TRIGGER_EVAL,
    Permission.VIEW_COST_REPORT,
})

_ADMIN_PERMISSIONS: frozenset[Permission] = _REVIEWER_PERMISSIONS | frozenset({
    Permission.MANAGE_API_KEYS,
    Permission.OVERRIDE_VERDICT,
})

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.VIEWER: _VIEWER_PERMISSIONS,
    Role.REVIEWER: _REVIEWER_PERMISSIONS,
    Role.ADMIN: _ADMIN_PERMISSIONS,
}

# Role ordering for "requires at least" checks
_ROLE_ORDER: dict[Role, int] = {
    Role.VIEWER: 0,
    Role.REVIEWER: 1,
    Role.ADMIN: 2,
}


try:
    from fastapi import HTTPException
except ImportError:
    class HTTPException(Exception):  # type: ignore[no-redef]
        def __init__(self, status_code: int, detail: str) -> None:
            self.status_code = status_code
            self.detail = detail
            super().__init__(detail)


# ---------------------------------------------------------------------------
# PermissionDeniedError
# ---------------------------------------------------------------------------

class PermissionDeniedError(HTTPException):
    """
    Raised when a role lacks a required permission.

    Inherits from HTTPException(403) so FastAPI's default exception handler
    returns a proper HTTP 403 response without extra error-handling wiring.
    """

    def __init__(
        self,
        role: Role | str,
        permission: Permission | str,
        message: str | None = None,
    ) -> None:
        self.role = role
        self.permission = permission
        self.status_code = 403
        _msg = message or (
            f"Role '{role}' does not have permission '{permission}'"
        )
        self.detail = _msg
        super().__init__(status_code=403, detail=_msg)

    def to_dict(self) -> dict[str, str]:
        """Serialisable form for JSON error responses."""
        return {
            "error": "permission_denied",
            "role": str(self.role),
            "required_permission": str(self.permission),
            "detail": self.detail,
        }


# ---------------------------------------------------------------------------
# RBACPolicy
# ---------------------------------------------------------------------------

class RBACPolicy:
    """
    Pure value object: checks whether a role has a permission.

    Stateless and immutable. Safe to share across requests.

    Usage:
        policy = RBACPolicy()
        policy.assert_allowed(Role.VIEWER, Permission.TRIGGER_EVAL)
        # raises PermissionDeniedError("viewer does not have trigger_eval")
    """

    def __init__(
        self,
        role_permissions: dict[Role, frozenset[Permission]] | None = None,
    ) -> None:
        """
        Args:
            role_permissions -- Override the default ROLE_PERMISSIONS map.
                                Useful for tests that need a custom policy.
        """
        self._policy = role_permissions or ROLE_PERMISSIONS

    def check(self, role: Role | str, permission: Permission | str) -> bool:
        """Return True if role has permission, False otherwise."""
        _role = Role(role) if isinstance(role, str) else role
        _perm = Permission(permission) if isinstance(permission, str) else permission
        return _perm in self._policy.get(_role, frozenset())

    def assert_allowed(
        self,
        role: Role | str,
        permission: Permission | str,
    ) -> None:
        """
        Raise PermissionDeniedError if role lacks permission.

        This is the primary call site for route-level permission checks.
        """
        if not self.check(role, permission):
            raise PermissionDeniedError(role, permission)

    def requires_at_least(self, role: Role | str, minimum: Role) -> bool:
        """
        Return True if role is at least as privileged as minimum.

        Example:
            policy.requires_at_least(Role.ADMIN, Role.REVIEWER)  # True
            policy.requires_at_least(Role.VIEWER, Role.REVIEWER)  # False
        """
        _role = Role(role) if isinstance(role, str) else role
        return _ROLE_ORDER.get(_role, -1) >= _ROLE_ORDER[minimum]

    def get_permissions(self, role: Role | str) -> frozenset[Permission]:
        """Return the full set of permissions for a role."""
        _role = Role(role) if isinstance(role, str) else role
        return self._policy.get(_role, frozenset())


# ---------------------------------------------------------------------------
# Singleton policy (used by FastAPI dependency)
# ---------------------------------------------------------------------------

DEFAULT_RBAC_POLICY = RBACPolicy()


# ---------------------------------------------------------------------------
# FastAPI dependency factory
# ---------------------------------------------------------------------------

def require_permission(permission: Permission) -> Callable[..., Any]:
    """
    FastAPI Depends() factory. Enforces server-derived authorization.
    Verifies that the server-authenticated Principal holds the required Permission.
    Untrusted caller-supplied X-Role headers are ignored.
    """
    try:
        from fastapi import Depends
        from backend.auth.dependencies import get_current_principal
        from backend.auth.principal import Principal

        async def _enforce_permission(
            principal: Principal = Depends(get_current_principal),
        ) -> Role:
            DEFAULT_RBAC_POLICY.assert_allowed(principal.role, permission)
            return principal.role

        return _enforce_permission
    except ImportError:
        def _fallback(role: Role | str = Role.VIEWER) -> Role:
            _role = Role(role) if isinstance(role, str) else role
            DEFAULT_RBAC_POLICY.assert_allowed(_role, permission)
            return _role

        return _fallback
