# backend/webhook_receiver/router.py
#
# FastAPI router for the GitHub webhook endpoint.
#
# THIS IS THE ENTRY POINT FOR ALL GITHUB EVENTS.
#
# The flow inside this endpoint (6 steps):
#
#   Step 1: Read raw body (before any parsing — needed for HMAC)
#   Step 2: Validate HMAC-SHA256 signature  -> 401 if invalid
#   Step 3: Parse payload into WebhookEvent -> 400 if malformed
#   Step 4: Check idempotency (already processed this?) -> 200 if duplicate
#   Step 5: Enqueue job in Redis queue
#   Step 6: Return 200 immediately (do not make GitHub wait)
#
# IMPORTANT: GitHub expects a response within 10 seconds.
# If we take longer, GitHub marks the delivery as failed and retries.
# This is why we enqueue and return immediately — actual review runs async.
#
# Steps 4 and 5 involve Redis. They are stubbed (Phase 3 scope).
# Real Redis integration comes in Phase 4.
#
# FIX (Orthogonality / GlobalDataCoupling):
#   Previously this file did:
#     from backend.config.settings import settings   <- global singleton at import time
#   That coupled this module to the settings global, making it impossible to test
#   this router without a full .env file present.
#
#   Now: settings is injected as a FastAPI Depends() parameter.
#   The route function RECEIVES settings as an argument — it does not reach out
#   and grab it from a global. This is "explicitly pass any required context."
#
#   To test this router, you override the dependency:
#     app.dependency_overrides[get_settings] = lambda: Settings(
#         github_webhook_secret="test-secret", ...
#     )
#   No .env file needed. No environment variables needed. Truly isolated.

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from backend.config.settings import Settings, get_settings
from backend.core.exceptions import (
    DuplicateWebhookError,
    MemoryStoreError,
    QueueOverloadedError,
    TenantConcurrencyLimitError,
    WebhookParseError,
    WebhookValidationError,
)
from backend.job_queue.arq_worker import enqueue_review_job
from backend.security.admission import check_webhook_rate_limit
from backend.webhook_receiver.parser import parse_webhook_payload
from backend.webhook_receiver.validator import validate_github_signature

logger = logging.getLogger(__name__)

# APIRouter groups related endpoints under a shared prefix.
# Mounted in main.py — the full path becomes POST /webhook/github
router = APIRouter(
    prefix="/webhook",
    tags=["webhook"],
)


@router.post(
    "/github",
    status_code=status.HTTP_200_OK,
    summary="GitHub webhook receiver",
    description=(
        "Receives GitHub pull_request webhook events. "
        "Validates HMAC signature, parses payload, deduplicates, and enqueues review job."
    ),
)
async def receive_github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
    x_github_delivery: str | None = Header(default=None),
    cfg: Settings = Depends(get_settings),
) -> JSONResponse:
    """
    Receives and processes a GitHub webhook event.

    GitHub sends this when a pull request is opened, updated, or reopened.
    We validate the signature, parse the payload, deduplicate, and enqueue.
    The actual review runs asynchronously — we return 200 immediately.
    """
    # ------------------------------------------------------------------
    # Step 0: Validate Content-Type and enforce payload size limits
    # ------------------------------------------------------------------
    content_type = request.headers.get("content-type", "")
    if content_type and not ("application/json" in content_type or "application/x-www-form-urlencoded" in content_type):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported Content-Type header. Expected application/json.",
        )

    # ------------------------------------------------------------------
    # Step 1: Read raw body with 10MB safety bound
    # ------------------------------------------------------------------
    raw_body = await request.body()
    MAX_PAYLOAD_BYTES = 10 * 1024 * 1024  # 10 MB limit
    if len(raw_body) > MAX_PAYLOAD_BYTES:
        http_413 = getattr(status, "HTTP_413_CONTENT_TOO_LARGE", status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        raise HTTPException(
            status_code=http_413,
            detail="Webhook payload exceeds 10MB limit.",
        )

    # ------------------------------------------------------------------
    # Step 1b: Check delivery receipt deduplication
    # ------------------------------------------------------------------
    from backend.memory.redis_client import redis_client
    if x_github_delivery:
        try:
            existing_workflow = await redis_client.check_receipt(x_github_delivery)
            if existing_workflow:
                logger.info(
                    "Duplicate delivery receipt | delivery_id=%s workflow_id=%s",
                    x_github_delivery,
                    existing_workflow,
                )
                return JSONResponse(
                    content={
                        "status": "already_processed",
                        "delivery_id": x_github_delivery,
                        "workflow_id": existing_workflow,
                    },
                    status_code=status.HTTP_200_OK,
                )
        except MemoryStoreError as e:
            logger.warning("Redis unavailable during delivery receipt check: %s", e)

    # ------------------------------------------------------------------
    # Step 2: Validate HMAC-SHA256 signature
    # ------------------------------------------------------------------
    try:
        validate_github_signature(
            payload_bytes=raw_body,
            signature_header=x_hub_signature_256,
            secret=cfg.github_webhook_secret,   # pass the value, not the settings object
        )
    except WebhookValidationError as e:
        logger.warning("Webhook signature validation failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature.",
        ) from e

    # ------------------------------------------------------------------
    # Step 3: Parse the payload into a typed WebhookEvent model
    #
    # Returns None for event types we ignore (push, star, fork, etc.)
    # Raises WebhookParseError if the payload is malformed.
    # ------------------------------------------------------------------
    try:
        event = parse_webhook_payload(
            raw_body=raw_body,
            event_type_header=x_github_event,
        )
    except WebhookParseError as e:
        logger.error("Webhook payload parse error: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse webhook payload: {str(e)}",
        ) from e

    # None means "valid signature, but an event type we don't handle" — not an error.
    if event is None:
        # Handle GitHub App offboarding / uninstall lifecycle (installation.deleted)
        if x_github_event == "installation":
            try:
                import json
                payload = json.loads(raw_body)
                inst_action = payload.get("action")
                if inst_action in ("deleted", "suspend"):
                    account = payload.get("installation", {}).get("account", {}).get("login")
                    if account:
                        from backend.database.postgres import get_session_factory
                        from backend.governance.deletion import delete_tenant_data
                        factory = get_session_factory()
                        async with factory() as db_session:
                            try:
                                await delete_tenant_data(
                                    session=db_session,
                                    tenant_id=account,
                                    actor=f"github_app_{inst_action}",
                                )
                                logger.info("Automatic tenant data deletion executed on GitHub app %s | tenant=%s", inst_action, account)
                            except Exception as del_exc:  # noqa: BLE001
                                logger.warning("Automatic tenant deletion deferred: %s", del_exc)
                    return JSONResponse(
                        content={"status": "handled", "event": "installation", "action": inst_action},
                        status_code=status.HTTP_200_OK,
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed parsing installation event: %s", exc)

        logger.debug(
            "Ignoring webhook event type '%s' — not a pull_request event.",
            x_github_event,
        )
        return JSONResponse(
            content={"status": "ignored", "reason": "event type not handled"},
            status_code=status.HTTP_200_OK,
        )

    logger.info(
        "Received pull_request webhook | repo=%s pr=%d action=%s commit=%s",
        event.repo_full_name,
        event.pr_number,
        event.action,
        event.head_commit_sha[:8],   # log only first 8 chars of the SHA
    )

    # Authenticated Webhook Rate Limit Policy:
    # Throttle by target repository rather than shared GitHub source IPs.
    await check_webhook_rate_limit(event.repo_full_name)

    # ------------------------------------------------------------------
    # Steps 4 + 5: Idempotency check AND enqueue (combined)
    #
    # enqueue_review_job() does both atomically:
    #   1. Checks idempotency key in Redis -> raises DuplicateWebhookError if found
    #   2. Sets idempotency key in Redis (expires in 24h)
    #   3. Pushes the job to the ARQ queue
    #
    # DuplicateWebhookError -> return 200 silently (not an error, expected behavior)
    # MemoryStoreError -> Redis is down, log and return 503 (caller should retry)
    # QueueOverloadedError -> Backpressure 503 with Retry-After header
    # TenantConcurrencyLimitError -> Throttled 429 with Retry-After header
    # ------------------------------------------------------------------
    try:
        await enqueue_review_job(
            workflow_id=event.idempotency_key,
            delivery_id=x_github_delivery,
            input_data={
                "repo_full_name": event.repo_full_name,
                "pr_number": event.pr_number,
                "pr_title": event.pr_title,
                "pr_body": event.pr_body,
                "author_login": event.author_login,
                "head_commit_sha": event.head_commit_sha,
                "base_branch": event.base_branch,
                # Pass diff inline if the webhook payload contains it.
                # Used as fallback when GitHub API is unavailable (local demo).
                "pr_diff": event.pull_request.diff if hasattr(event.pull_request, "diff") else "",
            },
        )
    except DuplicateWebhookError:
        logger.info(
            "Duplicate webhook ignored | idempotency_key=%s",
            event.idempotency_key,
        )
        return JSONResponse(
            content={"status": "already_queued", "idempotency_key": event.idempotency_key},
            status_code=status.HTTP_200_OK,
        )
    except QueueOverloadedError as e:
        logger.warning("Webhook rejected due to queue backpressure | queue_depth=%d", e.queue_depth)
        await redis_client.delete_idempotency_key(event.idempotency_key)
        return JSONResponse(
            content={"detail": "Queue capacity exceeded. Backpressure active.", "retry_after": e.retry_after},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            headers={"Retry-After": str(e.retry_after)},
        )
    except TenantConcurrencyLimitError as e:
        logger.warning("Webhook throttled due to tenant concurrency | tenant=%s", e.tenant_id)
        await redis_client.delete_idempotency_key(event.idempotency_key)
        return JSONResponse(
            content={"detail": f"Tenant '{e.tenant_id}' active review limit reached.", "retry_after": e.retry_after},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(e.retry_after)},
        )
    except MemoryStoreError as e:
        logger.error("Redis unavailable during enqueue: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Job queue temporarily unavailable. Please retry.",
        ) from e

    # ------------------------------------------------------------------
    # Step 6: Return 200 immediately
    #
    # GitHub marks this delivery as successful when it receives this response.
    # The review continues running asynchronously in the background.
    # We include enough info for GitHub to log which PR triggered this.
    # ------------------------------------------------------------------
    return JSONResponse(
        content={
            "status": "queued",
            "repo": event.repo_full_name,
            "pr_number": event.pr_number,
            "commit_sha": event.head_commit_sha,
        },
        status_code=status.HTTP_200_OK,
    )
