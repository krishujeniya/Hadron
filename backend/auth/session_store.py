"""
backend/auth/session_store.py

Server-side application session and OAuth state management.
Provides opaque, revocable session identifiers and keeps provider tokens (GitHub PAT / OAuth tokens)
securely on the server, never exposed in client cookies or browser code.
"""

from __future__ import annotations

import json
import logging
import secrets
import time
from typing import Any, Optional
from pydantic import BaseModel, Field
from fastapi import HTTPException
from backend.config.settings import get_settings

from backend.security.rbac import Role

logger = logging.getLogger(__name__)


class SessionData(BaseModel):
    """Server-side session record."""
    session_id: str
    user_id: str
    role: Role = Role.REVIEWER
    account: str | None = None
    provider_token: str | None = None
    csrf_token: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    created_at: float = Field(default_factory=time.time)
    expires_at: float

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class SessionStore:
    """
    Manages opaque server sessions and OAuth state tokens.
    Uses in-memory storage with optional Redis backing when connected.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, SessionData] = {}
        # state -> {"expires_at": float, "data": dict, "consumed_at": float | None}
        self._oauth_states: dict[str, dict[str, Any]] = {}

    def _cleanup_expired(self) -> None:
        now = time.time()
        expired_sessions = [sid for sid, s in self._sessions.items() if s.expires_at < now]
        for sid in expired_sessions:
            self._sessions.pop(sid, None)

        expired_states = [
            st for st, item in self._oauth_states.items()
            if item.get("expires_at", 0) < now
        ]
        for st in expired_states:
            self._oauth_states.pop(st, None)

    async def _get_redis_pool(self) -> Any:
        """Retrieve Redis pool, lazily connecting if not already connected."""
        try:
            from backend.memory.redis_client import redis_client
            if redis_client._pool is None:
                await redis_client.connect()
            return redis_client._pool
        except Exception as e:
            if get_settings().is_production:
                raise HTTPException(status_code=503, detail="Session service unavailable. Please retry.") from e
            logger.debug("Redis lazy pool connection skipped: %s", type(e).__name__)
            return None

    async def create_session(
        self,
        user_id: str,
        role: Role = Role.REVIEWER,
        account: str | None = None,
        provider_token: str | None = None,
        ttl_seconds: int = 86400 * 7,
    ) -> SessionData:
        """Create a new opaque server session."""
        self._cleanup_expired()
        session_id = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        expires_at = time.time() + ttl_seconds

        session = SessionData(
            session_id=session_id,
            user_id=user_id,
            role=role,
            account=account or user_id,
            provider_token=provider_token,
            csrf_token=csrf_token,
            created_at=time.time(),
            expires_at=expires_at,
        )
        self._sessions[session_id] = session

        # Try to cache in Redis if available
        try:
            pool = await self._get_redis_pool()
            if pool:
                key = f"hadron:session:{session_id}"
                data = session.model_dump_json()
                await pool.setex(key, ttl_seconds, data)
        except Exception as e:
            self._sessions.pop(session_id, None)
            if get_settings().is_production:
                raise HTTPException(status_code=503, detail="Session service unavailable. Please retry.") from e
            self._sessions[session_id] = session
            logger.debug("Redis session save skipped: %s", type(e).__name__)

        return session

    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Redis is authoritative: local caches must not resurrect a revoked session."""
        if not session_id:
            return None
        self._cleanup_expired()
        pool = await self._get_redis_pool()
        if pool:
            try:
                raw = await pool.get(f"hadron:session:{session_id}")
                if not raw:
                    self._sessions.pop(session_id, None)
                    return None
                session = SessionData(**json.loads(raw))
                return session if not session.is_expired else None
            except Exception as exc:
                logger.warning("Shared session verification unavailable: %s", type(exc).__name__)
                return None
        session = self._sessions.get(session_id)
        return session if session and not session.is_expired else None

    async def invalidate_session(self, session_id: str) -> bool:
        """Revoke a session completely."""
        existed = bool(self._sessions.pop(session_id, None))
        try:
            pool = await self._get_redis_pool()
            if pool:
                deleted = await pool.delete(f"hadron:session:{session_id}")
                if deleted:
                    existed = True
        except Exception as exc:
            if get_settings().is_production:
                raise HTTPException(status_code=503, detail="Session revocation unavailable. Please retry.") from exc
        return existed

    async def save_oauth_state(
        self,
        state: str,
        data: dict[str, Any] | None = None,
        ttl_seconds: int = 600,
    ) -> None:
        """Store OAuth CSRF state with TTL."""
        self._cleanup_expired()
        state_data = {
            "expires_at": time.time() + ttl_seconds,
            "data": data or {},
            "consumed_at": None,
        }
        self._oauth_states[state] = state_data
        try:
            pool = await self._get_redis_pool()
            if pool:
                key = f"hadron:oauth_state:{state}"
                await pool.setex(key, ttl_seconds, json.dumps(state_data))
        except Exception as e:
            if get_settings().is_production:
                self._oauth_states.pop(state, None)
                raise HTTPException(status_code=503, detail="Sign-in service unavailable. Please retry.") from e
            logger.debug("Redis oauth state save skipped: %s", type(e).__name__)

    async def verify_and_consume_oauth_state(self, state: str) -> Optional[dict[str, Any]]:
        """Atomically consume once across instances; duplicate code exchanges are rejected."""
        self._cleanup_expired()
        pool = await self._get_redis_pool()
        if pool:
            try:
                raw = await pool.getdel(f"hadron:oauth_state:{state}")
                self._oauth_states.pop(state, None)
                item = json.loads(raw) if raw else None
            except Exception:
                # Never accept a process-local copy when shared consumption failed.
                return None
        else:
            item = self._oauth_states.pop(state, None)
        if not item or time.time() > item["expires_at"]:
            return None
        return item.get("data")


# Global singleton instance
session_store = SessionStore()
