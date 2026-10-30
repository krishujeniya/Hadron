# backend/security/admission.py
#
# Gate B (T17): Admission Control, Rate Limiting, and Ingress Protection.
#
# Enforces:
# 1. Header size limits (max 64KB) -> HTTP 431 Request Header Fields Too Large.
# 2. Path-aware body size limits (10MB webhook, 2MB REST API) -> HTTP 413 Content Too Large.
# 3. Decompression bomb (zip bomb) protection for gzip / deflate payloads.
# 4. Proxy-aware client IP extraction (avoids blind trust in X-Forwarded-For).
# 5. Distinct rate-limiting policies:
#    - Authenticated API routes: per-principal / per-tenant quotas.
#    - Authenticated Webhooks: per-repository rate limiting (does not throttle shared GitHub IPs).
#    - Public endpoints: per-trusted-IP rate limiting.

import gzip
import logging
import zlib
from typing import Callable

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.config.settings import get_settings
from backend.core.exceptions import RateLimitExceededError
from backend.memory.redis_client import redis_client

logger = logging.getLogger(__name__)


def get_trusted_client_ip(headers: Headers, client_host: str | None, trusted_proxies: str | list[str]) -> str:
    """
    Extracts client IP safely without blind trust in X-Forwarded-For.
    Only trusts X-Forwarded-For if client_host is in trusted_proxies.
    """
    if isinstance(trusted_proxies, str):
        trusted_set = {p.strip() for p in trusted_proxies.split(",") if p.strip()}
    else:
        trusted_set = set(trusted_proxies)

    host = client_host or "127.0.0.1"
    if host in trusted_set:
        xff = headers.get("x-forwarded-for")
        if xff:
            # Parse rightmost untrusted hop
            ips = [ip.strip() for ip in xff.split(",") if ip.strip()]
            for ip in reversed(ips):
                if ip not in trusted_set:
                    return ip
            if ips:
                return ips[0]
    return host


class AdmissionControlMiddleware:
    """
    ASGI middleware enforcing header limits, streaming body size bounds,
    and safe decompression before expensive application parsing.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        cfg = get_settings()
        raw_headers = scope.get("headers", [])
        path = scope.get("path", "")

        # ------------------------------------------------------------------
        # 1. Header Size Limit (Max 64KB)
        # ------------------------------------------------------------------
        total_header_bytes = sum(len(k) + len(v) for k, v in raw_headers)
        max_headers = getattr(cfg, "max_headers_bytes", 65536)
        if total_header_bytes > max_headers:
            logger.warning("admission | headers_too_large | bytes=%d max=%d", total_header_bytes, max_headers)
            response = JSONResponse(
                {"detail": f"Request header fields exceed maximum limit of {max_headers} bytes."},
                status_code=status.HTTP_431_REQUEST_HEADER_FIELDS_TOO_LARGE,
            )
            await response(scope, receive, send)
            return

        # ------------------------------------------------------------------
        # 2. Determine Body Size Bound
        # ------------------------------------------------------------------
        is_webhook = path.startswith("/webhook")
        max_body_bytes = (
            getattr(cfg, "max_webhook_body_bytes", 10 * 1024 * 1024)
            if is_webhook
            else getattr(cfg, "max_api_body_bytes", 2 * 1024 * 1024)
        )

        headers = Headers(raw=raw_headers)
        content_length = headers.get("content-length")
        http_413 = getattr(status, "HTTP_413_CONTENT_TOO_LARGE", status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

        if content_length:
            try:
                cl_val = int(content_length)
                if cl_val > max_body_bytes:
                    logger.warning(
                        "admission | content_length_exceeded | path=%s length=%d max=%d",
                        path, cl_val, max_body_bytes,
                    )
                    response = JSONResponse(
                        {"detail": f"Request payload ({cl_val} bytes) exceeds limit ({max_body_bytes} bytes)."},
                        status_code=http_413,
                    )
                    await response(scope, receive, send)
                    return
            except ValueError:
                pass

        # ------------------------------------------------------------------
        # 3. Intercept streaming receive to guard chunked payloads & zip bombs
        # ------------------------------------------------------------------
        encoding = headers.get("content-encoding", "").lower()
        has_compression = encoding in ("gzip", "deflate")
        received_bytes = 0
        decompressed_bytes = 0
        decompressor = None

        if has_compression:
            if encoding == "gzip":
                decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
            else:
                decompressor = zlib.decompressobj()

        async def bounded_receive():
            nonlocal received_bytes, decompressed_bytes
            message = await receive()
            if message["type"] == "http.request":
                chunk = message.get("body", b"")
                received_bytes += len(chunk)
                if received_bytes > max_body_bytes:
                    raise HTTPException(
                        status_code=http_413,
                        detail=f"Request body exceeded maximum limit ({max_body_bytes} bytes).",
                    )

                if has_compression and decompressor and chunk:
                    try:
                        decomp = decompressor.decompress(chunk)
                        decompressed_bytes += len(decomp)
                        if decompressed_bytes > max_body_bytes:
                            raise HTTPException(
                                status_code=http_413,
                                detail="Decompressed payload exceeds maximum size limit (decompression bomb guard).",
                            )
                    except zlib.error as e:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Malformed compressed payload: {e}",
                        ) from e

            return message

        try:
            await self.app(scope, bounded_receive, send)
        except HTTPException as exc:
            response = JSONResponse(
                {"detail": exc.detail},
                status_code=exc.status_code,
                headers=exc.headers or {},
            )
            await response(scope, receive, send)


# -----------------------------------------------------------------------------
# Rate Limiting & Quota Guards
# -----------------------------------------------------------------------------

async def apply_rate_limit(
    key: str,
    max_per_minute: int,
    category: str = "general",
) -> None:
    """
    Enforces rate limit quotas using the shared Redis sliding/fixed window.
    Raises HTTPException(429) with Retry-After header on violation.
    """
    allowed, retry_after, current = await redis_client.check_rate_limit(
        key=f"{category}:{key}",
        max_requests=max_per_minute,
        window_seconds=60,
    )
    if not allowed:
        logger.warning(
            "rate_limit_exceeded | category=%s key=%s current=%d max=%d retry_after=%ds",
            category, key, current, max_per_minute, retry_after,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded for {category}. Please retry in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )


async def check_authenticated_rate_limit(request: Request) -> None:
    """
    Rate limits authenticated API traffic per workspace / tenant / principal.
    Reads principal from request state (populated by auth dependency) or header token.
    """
    cfg = get_settings()
    principal = getattr(request.state, "principal", None)
    identifier = "anonymous"
    if principal:
        identifier = principal.account or principal.tenant_id or principal.reviewer_id
    else:
        # Check API key or session cookie as identity token
        api_key = request.headers.get("x-api-key")
        session_id = request.cookies.get("hadron_session")
        if api_key:
            identifier = f"key_{hash(api_key)}"
        elif session_id:
            identifier = f"session_{session_id}"
        else:
            client_host = request.client.host if request.client else "unknown"
            identifier = get_trusted_client_ip(request.headers, client_host, cfg.trusted_proxies)

    await apply_rate_limit(
        key=identifier,
        max_per_minute=cfg.rate_limit_api_per_minute,
        category="api_tenant",
    )


async def check_webhook_rate_limit(repo_full_name: str) -> None:
    """
    Authenticated Webhook Rate Limiter:
    Throttles by target repository name rather than shared GitHub source IPs.
    """
    cfg = get_settings()
    await apply_rate_limit(
        key=repo_full_name,
        max_per_minute=cfg.rate_limit_webhook_per_minute,
        category="webhook_repo",
    )


async def check_public_auth_rate_limit(request: Request) -> None:
    """
    Rate limits unauthenticated public endpoints (e.g. /auth/login) per trusted client IP.
    """
    cfg = get_settings()
    client_host = request.client.host if request.client else "127.0.0.1"
    ip = get_trusted_client_ip(request.headers, client_host, cfg.trusted_proxies)
    await apply_rate_limit(
        key=ip,
        max_per_minute=cfg.rate_limit_auth_per_minute,
        category="public_ip",
    )
