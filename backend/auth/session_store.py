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
            from backend.memory.redis_client import redis_client
            if redis_client._pool:
                key = f"hadron:session:{session_id}"
                data = session.model_dump_json()
                await redis_client._pool.setex(key, ttl_seconds, data)
        except Exception as e:
            logger.debug("Redis session save skipped: %s", e)

        return session

    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Retrieve active session by opaque id."""
        if not session_id:
            return None
        self._cleanup_expired()

        session = self._sessions.get(session_id)
        if session and not session.is_expired:
            return session

        # Fallback to Redis if present
        try:
            from backend.memory.redis_client import redis_client
            if redis_client._pool:
                key = f"hadron:session:{session_id}"
                raw = await redis_client._pool.get(key)
                if raw:
                    data = json.loads(raw)
                    sess = SessionData(**data)
                    if not sess.is_expired:
                        self._sessions[session_id] = sess
                        return sess
        except Exception as e:
            logger.debug("Redis session get skipped: %s", e)

        return None

    async def invalidate_session(self, session_id: str) -> bool:
        """Revoke a session completely."""
        existed = bool(self._sessions.pop(session_id, None))
        try:
            from backend.memory.redis_client import redis_client
            if redis_client._pool:
                await redis_client._pool.delete(f"hadron:session:{session_id}")
                existed = True
        except Exception:
            pass
        return existed

    async def save_oauth_state(
        self,
        state: str,
        data: dict[str, Any] | None = None,
        ttl_seconds: int = 600,
    ) -> None:
        """Store OAuth CSRF state with TTL."""
        self._cleanup_expired()
        self._oauth_states[state] = {
            "expires_at": time.time() + ttl_seconds,
            "data": data or {},
            "consumed_at": None,
        }

    async def verify_and_consume_oauth_state(
        self,
        state: str,
        allow_recent_grace: float = 15.0,
    ) -> Optional[dict[str, Any]]:
        """
        Verify state token and consume it.
        Supports a short grace window (15s) for React 18 StrictMode duplicate callback mounts.
        """
        self._cleanup_expired()
        item = self._oauth_states.get(state)
        if not item:
            return None

        now = time.time()
        if now > item["expires_at"]:
            self._oauth_states.pop(state, None)
            return None

        # Check if already consumed
        consumed_at = item.get("consumed_at")
        if consumed_at is not None:
            if now - consumed_at <= allow_recent_grace:
                # Return the cached data during duplicate call grace period
                return item.get("data")
            # Beyond grace window: reject replay
            self._oauth_states.pop(state, None)
            return None

        # Mark consumed
        item["consumed_at"] = now
        return item.get("data")


# Global singleton instance
session_store = SessionStore()
