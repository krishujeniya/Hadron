# backend/auth/dependencies.py
#
# FastAPI dependencies for server-derived authentication and authorization.
# Enforces deny-by-default access control and prevents role/reviewer forgery.

import hmac
import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status

from backend.auth.principal import Principal
from backend.auth.session_store import session_store
from backend.config.settings import Settings, get_settings
from backend.security.rbac import Role

logger = logging.getLogger(__name__)


async def get_current_principal(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Principal:
    """
    Derive the authenticated Principal from verified server state.

    Checks credentials in the following order:
      1. Session cookie ('hadron_session') or Bearer token (opaque server session)
      2. 'X-API-Key' header (constant-time verified against configured settings.api_key)
      3. 'Authorization: Bearer <token>' matching API key

    Crucial Security Properties:
      - Client-supplied 'X-Role' headers are NEVER trusted for role escalation.
      - Anonymous requests to protected routes receive HTTP 401 Unauthorized.
      - Invalid API keys receive HTTP 403 Forbidden.
      - Unconfigured API keys in production raise HTTP 500 Misconfiguration.
    """
    auth_header = request.headers.get("Authorization")
    api_key_header = request.headers.get("X-API-Key")
    session_cookie = request.cookies.get("hadron_session")

    # 1. Check Bearer token or session cookie against server SessionStore
    token: Optional[str] = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif session_cookie:
        token = session_cookie.strip()

    if token:
        # Check if token is a valid server session
        session = await session_store.get_session(token)
        if session:
            # If request is a mutation (POST, PUT, DELETE, PATCH) using a cookie, verify CSRF if present
            if session_cookie and request.method in ("POST", "PUT", "DELETE", "PATCH"):
                csrf_header = request.headers.get("X-CSRF-Token")
                sec_fetch_site = request.headers.get("Sec-Fetch-Site")
                # Enforce CSRF check or same-origin header if provided
                if sec_fetch_site and sec_fetch_site == "cross-site":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Cross-origin mutation forbidden (anti-CSRF protection).",
                    )
                if csrf_header and not hmac.compare_digest(csrf_header, session.csrf_token):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Invalid CSRF token.",
                    )

            return Principal(
                id=session.user_id,
                role=session.role,
                account=session.account,
                auth_method="session",
                metadata={"session_id": session.session_id},
            )

        # Check if the bearer token directly matches the configured API key
        if settings.api_key and hmac.compare_digest(token.encode("utf-8"), settings.api_key.encode("utf-8")):
            return Principal(
                id="api_key_operator",
                role=Role.ADMIN,
                account=None,
                auth_method="bearer_api_key",
            )

    # 2. Check X-API-Key header
    if api_key_header:
        if not settings.api_key:
            logger.error("require_auth | API_KEY is not configured on server.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="API key not configured. Contact the system administrator.",
            )

        if hmac.compare_digest(api_key_header.encode("utf-8"), settings.api_key.encode("utf-8")):
            return Principal(
                id="api_key_operator",
                role=Role.ADMIN,
                account=None,
                auth_method="api_key",
            )
        else:
            logger.warning(
                "require_auth | Invalid API key provided | path=%s",
                request.url.path,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API key.",
            )

    # 3. No credentials provided
    logger.info("require_auth | Unauthenticated request rejected | path=%s", request.url.path)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Bearer, ApiKey"},
    )


async def require_auth(
    principal: Principal = Depends(get_current_principal),
) -> Principal:
    """
    FastAPI dependency that enforces authentication.
    Returns the validated server Principal.
    """
    return principal
