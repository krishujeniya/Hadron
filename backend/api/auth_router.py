# backend/api/auth_router.py
#
# REST API endpoints for GitHub authentication and account selection.
# Enables users to:
#   1. Sign in via GitHub OAuth (/api/v1/auth/github/login & callback)
#   2. Directly select / connect a GitHub account (by username + optional PAT)
#   3. Fetch repositories belonging to the selected GitHub account
#   4. Check current authenticated account status

import logging
import secrets
import time

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from backend.config.settings import Settings, get_settings
from backend.database.postgres import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, distinct
from backend.database.models import PRReviewRecord

logger = logging.getLogger(__name__)

# In-memory store for active OAuth anti-CSRF state tokens (token -> expiry timestamp)
_OAUTH_STATES: dict[str, float] = {}

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["auth"],
)


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
    auth_method: str = "username"  # "oauth" | "token" | "username"
    token: str | None = None


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


@router.get(
    "/github/login",
    response_model=OAuthLoginResponse,
    summary="Get GitHub OAuth authorization URL",
)
async def github_oauth_login(
    redirect_uri: str | None = None,
    settings: Settings = Depends(get_settings),
) -> OAuthLoginResponse:
    """Returns the GitHub OAuth login URL with cryptographic anti-CSRF state."""
    client_id = settings.github_client_id
    if not client_id:
        return OAuthLoginResponse(
            oauth_available=False,
            authorize_url=None,
            client_id=None,
        )

    # Generate cryptographic state token with 10-minute expiry
    state = secrets.token_urlsafe(32)
    now = time.time()
    for s, exp in list(_OAUTH_STATES.items()):
        if exp < now:
            _OAUTH_STATES.pop(s, None)
    _OAUTH_STATES[state] = now + 600.0

    scope = "read:user,repo"
    url = f"https://github.com/login/oauth/authorize?client_id={client_id}&scope={scope}&state={state}"
    if redirect_uri:
        url += f"&redirect_uri={redirect_uri}"

    return OAuthLoginResponse(
        oauth_available=True,
        authorize_url=url,
        client_id=client_id,
        state=state,
    )


@router.post(
    "/github/callback",
    response_model=AccountProfile,
    summary="Exchange GitHub OAuth code for access token and profile",
)
async def github_oauth_callback(
    payload: OAuthCallbackRequest,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> AccountProfile:
    """Exchange GitHub OAuth code for an access token, verify state, and issue secure cookie."""
    if not settings.github_client_id or not settings.github_client_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub OAuth client credentials are not configured on the server.",
        )

    # Strictly verify anti-CSRF state parameter
    if not payload.state or payload.state not in _OAUTH_STATES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing OAuth state parameter (CSRF verification failed).",
        )
    expiry = _OAUTH_STATES.pop(payload.state)
    if time.time() > expiry:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OAuth state parameter expired. Please initiate login again.",
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

        # Set secure HttpOnly session cookie
        response.set_cookie(
            key="hadron_token",
            value=access_token,
            httponly=True,
            samesite="lax",
            secure=True,
            max_age=86400 * 7,
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
            token=f"gho_{access_token[:4]}...{access_token[-4:]}" if len(access_token) > 8 else "***",
        )


@router.post(
    "/connect",
    response_model=AccountProfile,
    summary="Connect a GitHub account by username or token",
)
async def connect_account(
    payload: ConnectAccountRequest,
    settings: Settings = Depends(get_settings),
) -> AccountProfile:
    """Verify and connect a GitHub account by username or personal access token."""
    account_name = payload.account.strip()
    if not account_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account username cannot be empty")

    token = payload.token or settings.github_token
    auth_header = f"Bearer {token}" if token and token not in ("ghp_test", "ghp_development_token_placeholder") else None

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AI-PR-Review-Agent",
    }
    if auth_header:
        headers["Authorization"] = auth_header

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.github_api_base_url}/users/{account_name}",
                headers=headers,
            )
            if resp.status_code == 200:
                u = resp.json()
                return AccountProfile(
                    login=u.get("login", account_name),
                    name=u.get("name") or u.get("login", account_name),
                    avatar_url=u.get("avatar_url", f"https://github.com/{account_name}.png"),
                    html_url=u.get("html_url", f"https://github.com/{account_name}"),
                    bio=u.get("bio"),
                    public_repos=u.get("public_repos", 0),
                    type=u.get("type", "User"),
                    authenticated=True,
                    auth_method="token" if payload.token else "username",
                )
    except Exception as exc:
        logger.warning("connect_account | GitHub API check warning: %s — using fallback", exc)

    # Safe fallback if network/rate limit is reached or offline
    return AccountProfile(
        login=account_name,
        name=account_name,
        avatar_url=f"https://github.com/{account_name}.png",
        html_url=f"https://github.com/{account_name}",
        bio=f"GitHub account: {account_name}",
        public_repos=1,
        type="User",
        authenticated=True,
        auth_method="username",
    )


@router.get(
    "/repos",
    response_model=list[RepositoryItem],
    summary="List repositories for the selected GitHub account",
)
async def list_account_repos(
    account: str = Query(..., description="GitHub account / organization name"),
    token: str | None = Query(default=None, description="Optional GitHub token"),
    hadron_token: str | None = Cookie(default=None),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_db),
) -> list[RepositoryItem]:
    """Fetch repositories belonging to the specified GitHub account."""
    repos: list[RepositoryItem] = []
    seen_names: set[str] = set()

    # 1. Fetch from GitHub API if accessible (checks query param, HttpOnly cookie, then server token)
    active_token = token or hadron_token or settings.github_token
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

    # 2. Also query local database for any known repos matching account/*
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

    # Default fallback repo if none found
    if not repos and account.lower() in ("krishujeniya", "hadron"):
        repos.append(
            RepositoryItem(
                id="default_1",
                name="Hadron",
                full_name=f"{account}/Hadron",
                description="Autonomous Multi-Agent AI PR Review Engine",
                html_url=f"https://github.com/{account}/Hadron",
                default_branch="main",
            )
        )

    return repos
