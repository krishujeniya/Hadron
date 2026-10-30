"""JSON-structured logging for the PR Review Agent.

DESIGN OVERVIEW
  Every log entry is a JSON object written to Python's stdlib logging.
  This fixes the UnstructuredFreeTextLogs anti-pattern -- human-readable
  strings are not queryable or alertable.

  Wiki: "Every log entry should be a JSON object with a consistent schema
  including trace_id, span_id, level, and typed tag fields."

  opensre StructuredLogger pattern (observability chapter) extended with:
    - agent_type tag for per-agent cost/latency attribution
    - named helper functions (log_llm_call, log_tool_call, log_agent_verdict)
      so callsites never forget required fields

SCHEMA (all log entries share this base)
  {
    "timestamp": "2026-05-12T10:00:00.000Z",   # ISO-8601 UTC
    "service":   "ai-pr-review-agent",
    "logger":    "backend.agents.security_agent",
    "level":     "INFO",
    "event":     "llm.called",                  # ReviewEvent value
    "message":   "LLM call completed",
    "trace_id":  "review_abc123",               # correlates to TraceContext
    "span_id":   "a1b2c3d4e5f6a7b8",
    ...typed tags...
  }

NO SIDE EFFECTS AT IMPORT TIME
  StructuredLogger is instantiated per module (get_logger(name)).
  No settings() call at module level -- consistent with our architectural rule.
"""

from __future__ import annotations

import json
import logging
import re
import traceback as tb_module
from datetime import datetime, timezone
from typing import Any, Optional


_SERVICE_NAME = "ai-pr-review-agent"

# Redaction patterns for secrets, credentials, tokens, and database passwords
_REDACT_PATTERNS = [
    # OpenAI and Anthropic keys
    (re.compile(r"sk-[a-zA-Z0-9_\-]{15,}"), "sk-...[REDACTED]"),
    # GitHub tokens
    (re.compile(r"gh[posr]_[a-zA-Z0-9]{15,}"), "gh_...[REDACTED]"),
    # NVIDIA API keys
    (re.compile(r"nvapi-[a-zA-Z0-9_\-]{15,}"), "nvapi-...[REDACTED]"),
    # Bearer tokens
    (re.compile(r"(Bearer\s+)[a-zA-Z0-9_\-\.]{15,}", re.IGNORECASE), r"\1[REDACTED]"),
    # Database connection passwords
    (re.compile(r"(postgres(?:ql)?(?:\+asyncpg)?://[^:]+:)[^@]+(@.+)", re.IGNORECASE), r"\1[REDACTED]\2"),
    # Redis connection passwords
    (re.compile(r"(redis[s]?://[^:]+:)[^@]+(@.+)", re.IGNORECASE), r"\1[REDACTED]\2"),
]

_SENSITIVE_KEYS = {
    "token", "password", "secret", "api_key", "authorization",
    "private_key", "code", "diff", "patch", "prompt", "raw_content"
}


def redact_sensitive_data(val: Any, max_string_len: int = 1024, depth: int = 0) -> Any:
    """
    Recursively redacts secrets, tokens, connection strings, and private code
    while bounding string length and label cardinality.
    """
    if depth > 10:
        return "[DEPTH_EXCEEDED]"

    if isinstance(val, str):
        # Bound string length
        if len(val) > max_string_len:
            val = val[:max_string_len] + "...[TRUNCATED]"
        for pattern, repl in _REDACT_PATTERNS:
            val = pattern.sub(repl, val)
        return val

    if isinstance(val, dict):
        redacted = {}
        # Bound cardinality (up to 50 keys)
        for i, (k, v) in enumerate(val.items()):
            if i >= 50:
                redacted["..."] = "[CARDINALITY_BOUNDED]"
                break
            k_lower = str(k).lower()
            # Token metrics (input_tokens, total_tokens) are numeric counters, not secrets
            is_token_count = k_lower.endswith("tokens") or k_lower.endswith("_token_count")
            if is_token_count:
                redacted[k] = v
            elif k_lower in ("code", "diff", "patch", "prompt", "raw_content"):
                redacted[k] = "[REDACTED_CODE]"
            elif (
                k_lower in ("token", "auth_token", "access_token", "refresh_token", "github_token", "api_token", "bearer_token")
                or any(s in k_lower for s in ("password", "secret", "api_key", "authorization", "private_key"))
            ):
                redacted[k] = "[REDACTED_SECRET]"
            else:
                redacted[k] = redact_sensitive_data(v, max_string_len, depth + 1)
        return redacted

    if isinstance(val, (list, tuple, set)):
        items = [redact_sensitive_data(item, max_string_len, depth + 1) for item in list(val)[:50]]
        if len(val) > 50:
            items.append("[CARDINALITY_BOUNDED]")
        return items

    return val


class StructuredLogger:
    """JSON-structured logger.  One instance per module, via get_logger().

    Usage:
        logger = get_logger(__name__)
        logger.info("review.completed", message="Review finished",
                    trace_id="review_123", verdict="APPROVE")

    All keyword arguments beyond the required ones become additional JSON tags.
    This is intentional: the caller decides what context is relevant.
    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._stdlib = logging.getLogger(name)

    # ── Core log method ───────────────────────────────────────────────────────

    def _emit(
        self,
        level: int,
        event: str,
        message: str,
        *,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        **tags: Any,
    ) -> dict[str, Any]:
        """Build the JSON entry and write it to stdlib logging with automated
        redaction and workflow context enrichment.

        Returns the entry dict so callers can inspect it in tests.
        """
        # Enrich with active workflow context if available
        try:
            from backend.observability.workflow_context import get_workflow_context
            wf_ctx = get_workflow_context()
        except Exception:
            wf_ctx = None

        effective_trace_id = trace_id or (wf_ctx.workflow_id if wf_ctx else None)

        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": _SERVICE_NAME,
            "logger": self._name,
            "level": logging.getLevelName(level),
            "event": event,
            "message": redact_sensitive_data(message),
        }
        if effective_trace_id is not None:
            entry["trace_id"] = effective_trace_id
        if span_id is not None:
            entry["span_id"] = span_id
        if wf_ctx and wf_ctx.tenant_id:
            entry["tenant_id"] = wf_ctx.tenant_id
        if wf_ctx and wf_ctx.agent_type and wf_ctx.agent_type != "system":
            entry["agent_type"] = wf_ctx.agent_type

        # Redact remaining typed tags
        redacted_tags = redact_sensitive_data(tags)
        if isinstance(redacted_tags, dict):
            entry.update(redacted_tags)

        self._stdlib.log(level, json.dumps(entry))
        return entry

    # ── Convenience level shortcuts ──────────────────────────────────────────

    def info(
        self,
        event: str,
        message: str,
        *,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        **tags: Any,
    ) -> dict[str, Any]:
        return self._emit(
            logging.INFO, event, message,
            trace_id=trace_id, span_id=span_id, **tags
        )

    def warning(
        self,
        event: str,
        message: str,
        *,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        **tags: Any,
    ) -> dict[str, Any]:
        return self._emit(
            logging.WARNING, event, message,
            trace_id=trace_id, span_id=span_id, **tags
        )

    def error(
        self,
        event: str,
        message: str,
        *,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        exc: Optional[Exception] = None,
        **tags: Any,
    ) -> dict[str, Any]:
        """Log an error, optionally attaching exception info as a JSON field.

        We deliberately DO NOT call logging.exception() here because that
        writes a multi-line traceback as a free-text string, which defeats
        structured logging.  Instead we serialize it as a JSON field.
        """
        if exc is not None:
            tags["exception"] = {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": tb_module.format_exc(),
            }
        return self._emit(
            logging.ERROR, event, message,
            trace_id=trace_id, span_id=span_id, **tags
        )

    def debug(
        self,
        event: str,
        message: str,
        *,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        **tags: Any,
    ) -> dict[str, Any]:
        return self._emit(
            logging.DEBUG, event, message,
            trace_id=trace_id, span_id=span_id, **tags
        )


# ── Module-level factory ──────────────────────────────────────────────────────


def get_logger(name: str) -> StructuredLogger:
    """Return a StructuredLogger for the given module name.

    Convention: call this at module level like stdlib logging:
        logger = get_logger(__name__)

    This mirrors opensre's StructuredLogger(name=..., service=...) pattern
    but hides the service name so callers only pass __name__.
    """
    return StructuredLogger(name)


# ── Named helper functions ────────────────────────────────────────────────────
# These exist so call sites in agents, nodes, and llm_client never forget
# which tags are required for alerting and cost attribution to work.
#
# Wiki: "Focus on metrics that answer business questions."
#   - log_llm_call  -> answers "how much did this PR review cost?"
#   - log_tool_call -> answers "which tool is slowest / most error-prone?"
#   - log_agent_verdict -> answers "how often does security block vs quality?"


def log_llm_call(
    logger: StructuredLogger,
    *,
    trace_id: str,
    span_id: Optional[str] = None,
    agent_type: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    latency_ms: float,
    is_valid_json: bool = True,
) -> dict[str, Any]:
    """Log one LLM API call with full token and cost attribution.

    Called from LLMClient.call() wrapper or directly by agent analyze() after
    receiving an LLMResponse.

    Wiki: "Attach cost_usd and token counts as span tags on every LLM call to
    fix the FlatCostVisibility anti-pattern -- aggregate by model and agent."
    """
    return logger.info(
        "llm.called",
        "LLM call completed",
        trace_id=trace_id,
        span_id=span_id,
        agent_type=agent_type,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        cost_usd=cost_usd,
        latency_ms=round(latency_ms, 2),
        is_valid_json=is_valid_json,
    )


def log_tool_call(
    logger: StructuredLogger,
    *,
    trace_id: str,
    span_id: Optional[str] = None,
    agent_type: str,
    tool_name: str,
    success: bool,
    latency_ms: float,
    result_length: int = 0,
    error_message: Optional[str] = None,
) -> dict[str, Any]:
    """Log one tool execution through the ToolRegistry.

    opensre pattern: log tool_name, input_keys, output_length, latency, success.
    We simplify: result_length is enough for monitoring (not raw output content).
    """
    level_fn = logger.info if success else logger.warning
    return level_fn(
        "tool.called" if success else "tool.failed",
        f"Tool {'succeeded' if success else 'failed'}: {tool_name}",
        trace_id=trace_id,
        span_id=span_id,
        agent_type=agent_type,
        tool_name=tool_name,
        success=success,
        latency_ms=round(latency_ms, 2),
        result_length=result_length,
        **({"error_message": error_message} if error_message else {}),
    )


def log_agent_verdict(
    logger: StructuredLogger,
    *,
    trace_id: str,
    span_id: Optional[str] = None,
    agent_type: str,
    verdict: str,
    finding_count: int,
    critical_count: int,
    latency_ms: float,
) -> dict[str, Any]:
    """Log the per-agent verdict emitted by _derive_per_agent_verdict().

    Feeds the dashboard widget: "verdict distribution by agent_type".
    Useful to see if security_agent is over-blocking vs. quality_agent under-blocking.
    """
    return logger.info(
        "agent.completed",
        f"Agent {agent_type} verdict: {verdict}",
        trace_id=trace_id,
        span_id=span_id,
        agent_type=agent_type,
        verdict=verdict,
        finding_count=finding_count,
        critical_count=critical_count,
        latency_ms=round(latency_ms, 2),
    )


def log_review_verdict(
    logger: StructuredLogger,
    *,
    trace_id: str,
    span_id: Optional[str] = None,
    final_verdict: str,
    hitl_triggered: bool,
    agent_count: int,
    total_cost_usd: float,
    total_tokens: int,
    total_latency_ms: float,
) -> dict[str, Any]:
    """Log the final aggregate verdict for a complete PR review.

    This is the top-level business metric: how did this PR end up?
    All four agent verdicts + cost roll up into this single entry.

    Wiki: "Not all metrics are equal. Focus on metrics that answer business questions."
    """
    return logger.info(
        "verdict.emitted",
        f"Review completed: {final_verdict}",
        trace_id=trace_id,
        span_id=span_id,
        final_verdict=final_verdict,
        hitl_triggered=hitl_triggered,
        agent_count=agent_count,
        total_cost_usd=round(total_cost_usd, 6),
        total_tokens=total_tokens,
        total_latency_ms=round(total_latency_ms, 2),
    )
