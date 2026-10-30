# backend/api/auth_router.py
#
# REST API endpoints for GitHub authentication, session management, and account connection.
# Implements:
#   1. Secure OAuth flow with anti-CSRF state tokens persisted in SessionStore
#   2. Opaque application sessions with server-side provider token storage
#   3. Session verification (/api/v1/auth/me) and revocation (/api/v1/auth/logout)
#   4. Strict input and redirect allowlisting

from __future__ import annotations

import logging
import secrets
import urllib.parse
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_principal, require_auth
from backend.auth.principal import Principal
from backend.auth.session_store import session_store
from backend.config.settings import Settings, get_settings
from backend.database.models import PRReviewRecord
from backend.database.postgres import get_db
from backend.security.rbac import Role

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["auth"],
)

ALLOWED_REDIRECT_HOSTS = {"localhost", "127.0.0.1", "hadron.dev", "localhost:3000"}


class ConnectAccountRequest(BaseModel):
    account: str = Field(..., description="GitHub username or organization name")
    token: str | None = Field(default=None, description="Optional GitHub Personal Access Token")


class AccountProfile(BaseModel):
    login: str
    name: str | None = None
    avatar_url: str | None = None
    html_url: str | None = None
    bio: str | None = None
    public_repos: int = 0
    type: str = "User"
    authenticated: bool = True
    auth_method: str = "oauth"  # "oauth" | "token" | "session" | "preview"
    token: str | None = None  # Always None in responses to prevent credential leaks


class OAuthLoginResponse(BaseModel):
    oauth_available: bool
    authorize_url: str | None = None
    client_id: str | None = None
    state: str | None = None


class OAuthCallbackRequest(BaseModel):
    code: str
    state: str | None = None


class RepositoryItem(BaseModel):
    id: int | str
    name: str
    full_name: str
    description: str | None = None
    html_url: str
    default_branch: str = "main"
    open_issues_count: int = 0
    stargazers_count: int = 0
    private: bool = False
    updated_at: str | None = None


def _validate_redirect_uri(redirect_uri: str | None) -> str | None:
    """Ensure redirect URI targets an allowlisted host."""
    if not redirect_uri:
        return None
    parsed = urllib.parse.urlparse(redirect_uri)
    if parsed.netloc and parsed.netloc not in ALLOWED_REDIRECT_HOSTS:
        logger.warning("auth | rejected untrusted redirect_uri: %s", redirect_uri)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Disallowed redirect_uri host.",
        )
    return redirect_uri


@router.get(
    "/github/login",
    response_model=OAuthLoginResponse,
    summary="Get GitHub OAuth authorization URL",
)
async def github_oauth_login(
    redirect_uri: str | None = None,
    settings: Settings = Depends(get_settings),
) -> OAuthLoginResponse:
    """Returns the GitHub OAuth login URL with cryptographic anti-CSRF state stored in SessionStore."""
    client_id = settings.github_client_id
    if not client_id:
        return OAuthLoginResponse(
            oauth_available=False,
            authorize_url=None,
            client_id=None,
        )

    validated_redirect = _validate_redirect_uri(redirect_uri)
    state = secrets.token_urlsafe(32)

    await session_store.save_oauth_state(
        state=state,
        data={"redirect_uri": validated_redirect},
        ttl_seconds=600,
    )

    scope = "read:user,repo"
    url = f"https://github.com/login/oauth/authorize?client_id={client_id}&scope={scope}&state={state}"
    if validated_redirect:
        url += f"&redirect_uri={urllib.parse.quote(validated_redirect, safe='')}"

    return OAuthLoginResponse(
        oauth_available=True,
        authorize_url=url,
        client_id=client_id,
        state=state,
    )


@router.post(
    "/github/callback",
    response_model=AccountProfile,
    summary="Exchange GitHub OAuth code for session and profile",
)
async def github_oauth_callback(
    payload: OAuthCallbackRequest,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> AccountProfile:
    """Exchange GitHub OAuth code for an access token, verify state, and issue secure opaque session cookie."""
    if not settings.github_client_id or not settings.github_client_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub OAuth client credentials are not configured on the server.",
        )

    if not payload.state:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing OAuth state parameter (CSRF verification failed).",
        )

    # Verify and consume state (supports 15s grace for StrictMode duplicate mounts)
    state_data = await session_store.verify_and_consume_oauth_state(payload.state)
    if state_data is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired OAuth state parameter (CSRF verification failed).",
        )

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Step 1: Exchange code for token
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": payload.code,
            },
            headers={"Accept": "application/json"},
        )
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            error_desc = token_data.get("error_description", "Failed to retrieve access token from GitHub")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error_desc)

        # Step 2: Fetch user profile
        user_resp = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "AI-PR-Review-Agent",
            },
        )
        if user_resp.status_code != 200:
            raise HTTPException(status_code=user_resp.status_code, detail="Failed to fetch user profile from GitHub")

        u = user_resp.json()

        # Step 3: Create opaque server session
        session = await session_store.create_session(
            user_id=u["login"],
            role=Role.REVIEWER,
            account=u["login"],
            provider_token=access_token,
            ttl_seconds=86400 * 7,
        )

        # Set secure HttpOnly session cookie
        is_secure = not settings.is_development
        response.set_cookie(
            key="hadron_session",
            value=session.session_id,
            httponly=True,
            samesite="lax",
            secure=is_secure,
            max_age=86400 * 7,
            path="/",
        )
        response.set_cookie(
            key="hadron_csrf",
            value=session.csrf_token,
            httponly=False,
            samesite="lax",
            secure=is_secure,
            max_age=86400 * 7,
            path="/",
        )

        return AccountProfile(
            login=u["login"],
            name=u.get("name") or u["login"],
            avatar_url=u.get("avatar_url"),
            html_url=u.get("html_url"),
            bio=u.get("bio"),
            public_repos=u.get("public_repos", 0),
            type=u.get("type", "User"),
            authenticated=True,
            auth_method="oauth",
            token=None,  # Never leak raw token
        )


@router.get(
    "/me",
    response_model=AccountProfile,
    summary="Get authenticated caller profile",
)
async def get_current_user_profile(
    principal: Principal = Depends(get_current_principal),
) -> AccountProfile:
    """Return verified profile of current authenticated principal."""
    return AccountProfile(
        login=principal.id,
        name=principal.metadata.get("name") or principal.id,
        avatar_url=principal.metadata.get("avatar_url", f"https://github.com/{principal.id}.png"),
        html_url=f"https://github.com/{principal.id}",
        bio=f"Authenticated via {principal.auth_method} as {principal.role.value}",
        public_repos=0,
        type="User",
        authenticated=True,
        auth_method=principal.auth_method,
        token=None,
    )


@router.post(
    "/logout",
    summary="Revoke session and clear cookies",
)
async def logout(
    response: Response,
    principal: Principal = Depends(get_current_principal),
) -> dict[str, str]:
    """Invalidate server session and delete client cookies."""
    session_id = principal.metadata.get("session_id")
    if session_id:
        await session_store.invalidate_session(session_id)

    response.delete_cookie(key="hadron_session", path="/")
    response.delete_cookie(key="hadron_csrf", path="/")
    response.delete_cookie(key="hadron_token", path="/")
    return {"status": "logged_out", "message": "Session invalidated successfully."}


@router.post(
    "/connect",
    response_model=AccountProfile,
    summary="Connect a GitHub account by verified token or query public profile",
)
async def connect_account(
    payload: ConnectAccountRequest,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> AccountProfile:
    """
    Connect an account. If a valid personal token is supplied, creates an authenticated session.
    If no token is supplied, returns a preview of public profile without granting access to private resources.
    """
    account_name = payload.account.strip()
    if not account_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account username cannot be empty")

    token = payload.token
    if token and token not in ("ghp_test", "ghp_development_token_placeholder"):
        # Verify PAT against GitHub API
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "AI-PR-Review-Agent",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{settings.github_api_base_url}/user", headers=headers)
                if resp.status_code == 200:
                    u = resp.json()
                    user_login = u.get("login", account_name)
                    # Create authenticated session
                    session = await session_store.create_session(
                        user_id=user_login,
                        role=Role.REVIEWER,
                        account=user_login,
                        provider_token=token,
                        ttl_seconds=86400 * 7,
                    )
                    is_secure = not settings.is_development
                    response.set_cookie(
                        key="hadron_session",
                        value=session.session_id,
                        httponly=True,
                        samesite="lax",
                        secure=is_secure,
                        max_age=86400 * 7,
                        path="/",
                    )
                    return AccountProfile(
                        login=user_login,
                        name=u.get("name") or user_login,
                        avatar_url=u.get("avatar_url", f"https://github.com/{user_login}.png"),
                        html_url=u.get("html_url", f"https://github.com/{user_login}"),
                        bio=u.get("bio"),
                        public_repos=u.get("public_repos", 0),
                        type=u.get("type", "User"),
                        authenticated=True,
                        auth_method="token",
                        token=None,
                    )
        except Exception as exc:
            logger.warning("connect_account | GitHub token verification error: %s", exc)

    # Fallback / Preview: unauthenticated profile info
    return AccountProfile(
        login=account_name,
        name=account_name,
        avatar_url=f"https://github.com/{account_name}.png",
        html_url=f"https://github.com/{account_name}",
        bio=f"GitHub preview: {account_name}",
        public_repos=0,
        type="User",
        authenticated=False,
        auth_method="preview",
        token=None,
    )


@router.get(
    "/repos",
    response_model=list[RepositoryItem],
    summary="List repositories for the selected GitHub account",
)
async def list_account_repos(
    account: str = Query(..., description="GitHub account / organization name"),
    principal: Principal = Depends(require_auth),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_db),
) -> list[RepositoryItem]:
    """Fetch repositories belonging to the specified GitHub account for an authenticated user."""
    repos: list[RepositoryItem] = []
    seen_names: set[str] = set()

    # Retrieve provider token from session if available
    session_id = principal.metadata.get("session_id")
    sess_obj = await session_store.get_session(session_id) if session_id else None
    active_token = (sess_obj.provider_token if sess_obj else None) or settings.github_token

    auth_header = (
        f"Bearer {active_token}"
        if active_token and active_token not in ("ghp_test", "ghp_development_token_placeholder")
        else None
    )

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AI-PR-Review-Agent",
    }
    if auth_header:
        headers["Authorization"] = auth_header

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.github_api_base_url}/users/{account}/repos?per_page=100&sort=updated",
                headers=headers,
            )
            if resp.status_code == 200:
                for r in resp.json():
                    full_name = r.get("full_name", f"{account}/{r.get('name')}")
                    seen_names.add(full_name.lower())
                    repos.append(
                        RepositoryItem(
                            id=r.get("id", len(repos) + 1),
                            name=r.get("name", ""),
                            full_name=full_name,
                            description=r.get("description"),
                            html_url=r.get("html_url", f"https://github.com/{full_name}"),
                            default_branch=r.get("default_branch", "main"),
                            open_issues_count=r.get("open_issues_count", 0),
                            stargazers_count=r.get("stargazers_count", 0),
                            private=r.get("private", False),
                            updated_at=r.get("updated_at"),
                        )
                    )
    except Exception as exc:
        logger.warning("list_account_repos | GitHub API error: %s", exc)

    # Query local database for known repos matching account/* ONLY if caller is authorized for this workspace or admin
    authorized_account = principal.account or principal.tenant_id
    is_authorized_workspace = principal.is_admin or (
        authorized_account is not None and account.lower() == authorized_account.lower()
    )

    if is_authorized_workspace:
        try:
            db_result = await session.execute(
                select(distinct(PRReviewRecord.repo_full_name)).where(
                    PRReviewRecord.repo_full_name.like(f"{account}/%")
                )
            )
            db_repos = db_result.scalars().all()
            for full_name in db_repos:
                if full_name.lower() not in seen_names:
                    repo_name = full_name.split("/")[-1] if "/" in full_name else full_name
                    seen_names.add(full_name.lower())
                    repos.append(
                        RepositoryItem(
                            id=f"db_{len(repos) + 1}",
                            name=repo_name,
                            full_name=full_name,
                            description="Tracked in review database",
                            html_url=f"https://github.com/{full_name}",
                            default_branch="main",
                            open_issues_count=0,
                            stargazers_count=0,
                            private=False,
                        )
                    )
        except Exception as exc:
            logger.debug("list_account_repos | local DB check: %s", exc)

    return repos
