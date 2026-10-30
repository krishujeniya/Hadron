# backend/tools/llm_client.py
#
# LLM API client — the ONLY place that calls OpenAI or Anthropic directly.
#
# WHY A WRAPPER?
# The same reason redis_client.py exists. Without this:
#   - SecurityAgent imports openai directly -> tightly coupled to OpenAI
#   - Swapping to Anthropic means touching every agent file
#   - Rate limit handling is duplicated across 4 agents
#   - Token counting happens inconsistently
#
# With this wrapper:
#   - Agents call: await llm_client.call(model="gpt-4o-mini", messages=[...])
#   - They never import openai or anthropic directly
#   - Rate limit + retry logic lives in ONE place
#   - Token counting is automatic and centralized
#
# PROVIDERS SUPPORTED:
#   OpenAI  -> gpt-4o, gpt-4o-mini, gpt-3.5-turbo
#   Anthropic -> claude-3-5-sonnet-20241022, claude-3-haiku-20240307
#
# STRUCTURED OUTPUT:
# Both providers support structured output (JSON mode).
# OpenAI:    response_format={"type": "json_object"} in the API call
# Anthropic: system prompt instruction + xml tags in response
# This client normalizes both into: returns parsed dict | raises LLMOutputError.
#
# RETRY STRATEGY (from Stability Patterns wiki):
# "Every external call is a potential stab-in-the-back."
# We retry on:
#   - 429 RateLimitError  -> wait for retry-after header, then retry (up to 3x)
#   - 500/502/503          -> exponential backoff, up to 3 retries
# We do NOT retry on:
#   - 400 BadRequest (prompt too long) -> caller needs to truncate
#   - 401 Unauthorized (bad key)       -> config error, no point retrying
#   - Content policy violation          -> log and return empty findings
#
# TOKEN COUNTING:
# Every call returns a LLMResponse with input_tokens and output_tokens.
# The model router uses this for cost attribution per agent (Phase 10 full tracing).

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Optional

import anthropic
import openai

from backend.core.exceptions import AgentError
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-provider concurrency bulkheads (prevent overwhelming providers on fan-out)
# ---------------------------------------------------------------------------
_PROVIDER_SEMAPHORES: dict[str, asyncio.Semaphore] = {
    "openai": asyncio.Semaphore(10),
    "anthropic": asyncio.Semaphore(10),
    "nvidia": asyncio.Semaphore(10),
}


def get_provider_semaphore(provider: str) -> asyncio.Semaphore:
    """Returns or creates the concurrency semaphore for a given provider."""
    if provider not in _PROVIDER_SEMAPHORES:
        _PROVIDER_SEMAPHORES[provider] = asyncio.Semaphore(10)
    return _PROVIDER_SEMAPHORES[provider]


def _compute_llm_delay(
    attempt: int,
    base_delay: float = 1.0,
    retry_after: float | None = None,
    deadline: Any | None = None,
) -> float:
    """
    Computes retry backoff delay with uniform jitter and workflow deadline clipping.
    """
    if retry_after is not None and retry_after > 0:
        delay = float(min(retry_after, 60.0))
    else:
        delay = float(base_delay * (2 ** attempt))

    # 25% uniform jitter
    jitter = delay * 0.25 * (2 * random.random() - 1)
    delay = max(0.05, delay + jitter)

    if deadline and hasattr(deadline, "remaining_s"):
        from backend.reliability.timeout import DeadlineExceededError
        rem = deadline.remaining_s
        if delay > rem:
            if rem <= 0.05:
                raise DeadlineExceededError(
                    f"LLM retry delay of {delay:.2f}s exceeds remaining deadline ({rem:.2f}s)"
                )
            delay = rem

    return round(delay, 3)



# ---------------------------------------------------------------------------
# Phase 16 — fire-and-forget cost log writer.
#
# Called after each successful LLM call. Reads the active workflow context
# (set by base_agent.analyze) so we never have to thread a workflow_id arg
# through every retry path. Failures here are swallowed inside
# record_llm_call so a DB hiccup cannot break the review pipeline.
# ---------------------------------------------------------------------------
async def _persist_call_log(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    latency_seconds: float,
    is_valid_json: bool,
    idempotency_key: str | None = None,
) -> None:
    try:
        # Lazy imports to avoid circular import at module load time
        # (economics imports models, models import Base, Base depends on settings).
        import uuid
        from backend.economics import record_llm_call
        from backend.observability.workflow_context import get_workflow_context
        ctx = get_workflow_context()
        tenant_id = getattr(ctx, "tenant_id", None)
        idem_key = idempotency_key or f"{ctx.workflow_id or 'sys'}:{ctx.agent_type or 'gen'}:{model}:{uuid.uuid4()}"

        await record_llm_call(
            workflow_id=ctx.workflow_id,
            tenant_id=tenant_id,
            idempotency_key=idem_key,
            agent_type=ctx.agent_type or "system",
            call_type="judge" if getattr(ctx, "agent_type", None) == "judge" else "llm",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_seconds * 1000.0,
            is_valid_json=is_valid_json,
        )

        # Wire Tiger Cloud agent_events hypertable telemetry
        from backend.observability.events import AgentEvent, dispatch_agent_event
        from backend.database.postgres import get_tiger_pool
        event = AgentEvent(
            review_id=ctx.workflow_id or "system",
            agent=ctx.agent_type or "system",
            event_type="llm.call",
            model=model,
            tokens_in=input_tokens,
            tokens_out=output_tokens,
            cost_usd=cost_usd,
            latency_ms=int(latency_seconds * 1000.0),
            payload={"is_valid_json": is_valid_json},
        )
        dispatch_agent_event(event, pool=get_tiger_pool())
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("llm_call_log_helper_failed | error=%s", exc)


# ---------------------------------------------------------------------------
# Token cost table (USD per 1000 tokens, as of mid-2025)
# Used to compute estimated cost per call for observability.
# Phase 16 (Economics) will move this to a database for runtime updates.
# ---------------------------------------------------------------------------
_TOKEN_COSTS: dict[str, dict[str, float]] = {
    # OpenAI models
    "gpt-4o":            {"input": 0.005,   "output": 0.015},
    "gpt-4o-mini":       {"input": 0.00015, "output": 0.0006},
    "gpt-3.5-turbo":     {"input": 0.0005,  "output": 0.0015},
    # NVIDIA NIM models (including OpenAI open-weight MoE reasoning model)
    "openai/gpt-oss-20b": {"input": 0.00015, "output": 0.0006},
    "openai/gpt-oss-120b": {"input": 0.0005, "output": 0.0015},
    "gpt-oss-22b":        {"input": 0.00015, "output": 0.0006},
    "gpt-oss-20b":        {"input": 0.00015, "output": 0.0006},
    # Anthropic models
    "claude-3-5-sonnet-20241022": {"input": 0.003,  "output": 0.015},
    "claude-3-haiku-20240307":    {"input": 0.00025,"output": 0.00125},
}


@dataclass
class LLMResponse:
    """
    The structured response from one LLM API call.

    WHY A DATACLASS AND NOT PYDANTIC?
    LLMResponse is internal to the tools layer — it never leaves the codebase
    (not stored, not serialized to JSON, not returned via API).
    Dataclass is lighter than Pydantic for pure in-process data.

    FIELDS:
    """
    # The parsed content from the LLM.
    # For JSON mode calls: a parsed dict.
    # For text mode calls: a string.
    content: dict | str

    # How many tokens the prompt used (input side).
    # Billed by the provider. Used for cost tracking.
    input_tokens: int

    # How many tokens the response used (output side).
    # Usually much smaller than input for structured output calls.
    output_tokens: int

    # Which model actually served this request.
    # May differ from requested model if provider falls back.
    model_used: str

    # Wall-clock seconds for this API call.
    # Used by Phase 10 (Observability) to identify slow models.
    latency_seconds: float

    # Estimated cost in USD for this call.
    # Computed from token counts + cost table above.
    estimated_cost_usd: float = 0.0

    # Whether the response content was valid JSON (for JSON mode calls).
    # False means output guardrail caught malformed output.
    is_valid_json: bool = True


def _compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Estimates the cost of one LLM API call in USD using canonical pricing.
    Rejects unknown prices if strict_price_enforcement is enabled, or uses
    an explicit conservative estimate.
    """
    from backend.config import get_settings
    from backend.economics.pricing import get_token_cost
    cfg = get_settings()
    strict = getattr(cfg, "strict_price_enforcement", False)
    return get_token_cost(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        strict=strict,
    )


class LLMClient:
    """
    Async LLM client supporting OpenAI and Anthropic.

    LIFECYCLE:
    This client is stateless — it creates API client objects per call.
    No shared state between calls (thread-safe, safe to use concurrently).
    The API keys are read from Settings at call time.

    USAGE:
    From an agent:
      response = await llm_client.call_openai(
          model="gpt-4o-mini",
          messages=[{"role": "user", "content": "..."}],
          system_prompt="You are a code quality reviewer...",
      )
      findings = response.content  # already parsed dict
    """

    # Maximum number of retries on transient failures (rate limit, 5xx)
    MAX_RETRIES = 3

    # Base delay for exponential backoff in seconds.
    # Retry 1: 1s, Retry 2: 2s, Retry 3: 4s
    BASE_RETRY_DELAY = 1.0

    async def call_openai(
        self,
        model: str,
        messages: list[dict[str, str]],
        system_prompt: str,
        json_mode: bool = True,
        max_tokens: int = 2048,
        api_key: str | None = None,
        deadline: Any | None = None,
    ) -> LLMResponse:
        """
        Makes one call to the OpenAI API with concurrency bulkhead, shared deadline budget,
        jittered backoff, and strict cancellation handling.
        """
        if not model or not str(model).strip():
            raise AgentError("Model name cannot be empty", agent_name="llm_openai")

        from backend.config import get_settings
        from backend.observability.workflow_context import get_workflow_context
        from backend.reliability.circuit_breaker import AGENT_BREAKERS, get_breaker, DEFAULT_LLM_BREAKER_CONFIG

        cfg = get_settings()
        key = api_key or getattr(cfg, "nvidia_api_key", None) or cfg.openai_api_key

        # Resolve base_url and target_model for NVIDIA NIM or custom OpenAI-compatible endpoints
        base_url = None
        if key and key.startswith("nvapi-"):
            base_url = getattr(cfg, "nvidia_base_url", "https://integrate.api.nvidia.com/v1")
        elif getattr(cfg, "openai_api_base_url", None):
            base_url = cfg.openai_api_base_url

        target_model = model
        is_nvidia = bool(base_url and "nvidia" in base_url)
        if is_nvidia:
            if "gpt-oss" in target_model.lower():
                target_model = "openai/gpt-oss-20b"
            elif target_model in ("gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"):
                target_model = "openai/gpt-oss-20b"

        provider_sem = get_provider_semaphore("nvidia" if is_nvidia else "openai")

        # Reasoning models generate chain-of-thought before output, so ensure adequate tokens
        req_max_tokens = max(max_tokens, 4096) if "gpt-oss" in target_model else max_tokens

        client = openai.AsyncOpenAI(api_key=key, base_url=base_url)

        # Build the full messages list: system first, then user messages
        full_messages = [{"role": "system", "content": system_prompt}] + messages

        # OpenAI JSON mode config
        response_format = {"type": "json_object"} if json_mode else {"type": "text"}

        ctx = get_workflow_context()
        agent = getattr(ctx, "agent_type", None) or "llm_openai"
        breaker = AGENT_BREAKERS.get(agent) or get_breaker(f"llm_{agent}", DEFAULT_LLM_BREAKER_CONFIG)

        req_timeout = float(getattr(cfg, "agent_timeout_seconds", 120))
        async def _execute_openai_call() -> LLMResponse:
            async with provider_sem:
                last_error: Exception | None = None
                for attempt in range(self.MAX_RETRIES + 1):
                    if deadline and hasattr(deadline, "check_headroom"):
                        deadline.check_headroom(0.05)

                    call_timeout = req_timeout
                    if deadline and hasattr(deadline, "slice_for_call"):
                        call_timeout = deadline.slice_for_call(req_timeout)

                    start = time.monotonic()
                    try:
                        response = await client.chat.completions.create(
                            model=target_model,
                            messages=full_messages,
                            response_format=response_format,
                            max_tokens=req_max_tokens,
                            temperature=0.1,
                            timeout=call_timeout,
                        )

                        latency = time.monotonic() - start
                        choice = response.choices[0]
                        raw_content = choice.message.content or ""
                        if not raw_content and hasattr(choice.message, "reasoning_content"):
                            raw_content = choice.message.reasoning_content or "{}"
                        if not raw_content:
                            raw_content = "{}"
                        input_tokens  = response.usage.prompt_tokens
                        output_tokens = response.usage.completion_tokens

                        is_valid_json = True
                        try:
                            parsed = json.loads(raw_content)
                        except json.JSONDecodeError:
                            logger.warning(
                                "openai_json_parse_failed | model=%s attempt=%d | "
                                "trying partial extraction",
                                model, attempt,
                            )
                            parsed = _try_extract_json(raw_content)
                            is_valid_json = bool(parsed)

                        cost = _compute_cost(model, input_tokens, output_tokens)
                        logger.info(
                            "openai_call | model=%s input_tokens=%d output_tokens=%d "
                            "latency=%.2fs cost=$%.6f",
                            model, input_tokens, output_tokens, latency, cost,
                        )

                        await _persist_call_log(
                            model=model,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            cost_usd=cost,
                            latency_seconds=latency,
                            is_valid_json=is_valid_json,
                        )

                        return LLMResponse(
                            content=parsed,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            model_used=model,
                            latency_seconds=round(latency, 3),
                            estimated_cost_usd=cost,
                            is_valid_json=is_valid_json,
                        )

                    except asyncio.CancelledError:
                        logger.info("openai_call_cancelled | model=%s attempt=%d", model, attempt)
                        raise

                    except openai.RateLimitError as e:
                        last_error = e
                        retry_after = getattr(e, "retry_after", None)
                        if retry_after is None and hasattr(e, "response") and e.response:
                            ra_hdr = e.response.headers.get("retry-after")
                            if ra_hdr and ra_hdr.isdigit():
                                retry_after = float(ra_hdr)
                        delay = _compute_llm_delay(
                            attempt, self.BASE_RETRY_DELAY, retry_after=retry_after, deadline=deadline
                        )
                        logger.warning(
                            "openai_rate_limit | model=%s attempt=%d/%d | waiting %.2fs",
                            model, attempt + 1, self.MAX_RETRIES, delay,
                        )
                        if attempt < self.MAX_RETRIES:
                            await asyncio.sleep(delay)

                    except openai.APIStatusError as e:
                        last_error = e
                        if e.status_code and 400 <= e.status_code < 500 and e.status_code != 429:
                            logger.error(
                                "openai_client_error | model=%s status=%d | not retrying",
                                model, e.status_code,
                            )
                            raise AgentError(
                                f"OpenAI API client error {e.status_code}: {str(e)}",
                                agent_name=model,
                            ) from e
                        delay = _compute_llm_delay(attempt, self.BASE_RETRY_DELAY, deadline=deadline)
                        logger.warning(
                            "openai_server_error | model=%s attempt=%d/%d | waiting %.2fs",
                            model, attempt + 1, self.MAX_RETRIES, delay,
                        )
                        if attempt < self.MAX_RETRIES:
                            await asyncio.sleep(delay)

                    except Exception as e:
                        last_error = e
                        delay = _compute_llm_delay(attempt, self.BASE_RETRY_DELAY, deadline=deadline)
                        logger.warning(
                            "openai_unexpected_error | model=%s attempt=%d/%d error=%s",
                            model, attempt + 1, self.MAX_RETRIES, str(e),
                        )
                        if attempt < self.MAX_RETRIES:
                            await asyncio.sleep(delay)

                raise AgentError(
                    f"OpenAI call failed after {self.MAX_RETRIES + 1} attempts: {last_error}",
                    agent_name=model,
                ) from last_error

        return await breaker.async_call(_execute_openai_call)

    async def call_anthropic(
        self,
        model: str,
        messages: list[dict[str, str]],
        system_prompt: str,
        max_tokens: int = 2048,
        api_key: str | None = None,
        deadline: Any | None = None,
    ) -> LLMResponse:
        """
        Makes one call to the Anthropic API with concurrency bulkhead, shared deadline budget,
        jittered backoff, and strict cancellation handling.
        """
        if not model or not str(model).strip():
            raise AgentError("Model name cannot be empty", agent_name="llm_anthropic")

        from backend.config import get_settings
        cfg = get_settings()
        key = api_key or cfg.anthropic_api_key

        client = anthropic.AsyncAnthropic(api_key=key)
        provider_sem = get_provider_semaphore("anthropic")

        # Add JSON instruction to system prompt for Anthropic
        # (OpenAI handles this via response_format, Anthropic via prompt)
        json_system = (
            system_prompt
            + "\n\nCRITICAL: You MUST respond with ONLY valid JSON. "
            "No preamble, no explanation, no markdown code blocks. "
            "Start your response with { and end with }."
        )

        # Anthropic "prefill" technique:
        prefill_messages = list(messages) + [{"role": "assistant", "content": "{"}]

        from backend.observability.workflow_context import get_workflow_context
        from backend.reliability.circuit_breaker import AGENT_BREAKERS, get_breaker, DEFAULT_LLM_BREAKER_CONFIG

        ctx = get_workflow_context()
        agent = getattr(ctx, "agent_type", None) or "llm_anthropic"
        breaker = AGENT_BREAKERS.get(agent) or get_breaker(f"llm_{agent}", DEFAULT_LLM_BREAKER_CONFIG)

        req_timeout = float(getattr(cfg, "agent_timeout_seconds", 120))
        async def _execute_anthropic_call() -> LLMResponse:
            async with provider_sem:
                last_error: Exception | None = None
                for attempt in range(self.MAX_RETRIES + 1):
                    if deadline and hasattr(deadline, "check_headroom"):
                        deadline.check_headroom(0.05)

                    call_timeout = req_timeout
                    if deadline and hasattr(deadline, "slice_for_call"):
                        call_timeout = deadline.slice_for_call(req_timeout)

                    start = time.monotonic()
                    try:
                        response = await client.messages.create(
                            model=model,
                            max_tokens=max_tokens,
                            system=json_system,
                            messages=prefill_messages,
                            temperature=0.1,
                            timeout=call_timeout,
                        )

                        latency = time.monotonic() - start

                        # Anthropic response: response.content is a list of ContentBlock.
                        raw_content = ""
                        for block in response.content:
                            if hasattr(block, "text"):
                                raw_content += block.text

                        # Re-attach the prefill "{"
                        full_json = "{" + raw_content

                        input_tokens  = response.usage.input_tokens
                        output_tokens = response.usage.output_tokens

                        is_valid_json = True
                        try:
                            parsed = json.loads(full_json)
                        except json.JSONDecodeError:
                            logger.warning(
                                "anthropic_json_parse_failed | model=%s attempt=%d",
                                model, attempt,
                            )
                            parsed = _try_extract_json(full_json)
                            is_valid_json = bool(parsed)

                        cost = _compute_cost(model, input_tokens, output_tokens)
                        logger.info(
                            "anthropic_call | model=%s input_tokens=%d output_tokens=%d "
                            "latency=%.2fs cost=$%.6f",
                            model, input_tokens, output_tokens, latency, cost,
                        )

                        await _persist_call_log(
                            model=model,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            cost_usd=cost,
                            latency_seconds=latency,
                            is_valid_json=is_valid_json,
                        )

                        return LLMResponse(
                            content=parsed,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            model_used=model,
                            latency_seconds=round(latency, 3),
                            estimated_cost_usd=cost,
                            is_valid_json=is_valid_json,
                        )

                    except asyncio.CancelledError:
                        logger.info("anthropic_call_cancelled | model=%s attempt=%d", model, attempt)
                        raise

                    except anthropic.RateLimitError as e:
                        last_error = e
                        retry_after = getattr(e, "retry_after", None)
                        if retry_after is None and hasattr(e, "response") and e.response:
                            ra_hdr = e.response.headers.get("retry-after")
                            if ra_hdr and ra_hdr.isdigit():
                                retry_after = float(ra_hdr)
                        delay = _compute_llm_delay(
                            attempt, self.BASE_RETRY_DELAY, retry_after=retry_after, deadline=deadline
                        )
                        logger.warning(
                            "anthropic_rate_limit | model=%s attempt=%d/%d | waiting %.2fs",
                            model, attempt + 1, self.MAX_RETRIES, delay,
                        )
                        if attempt < self.MAX_RETRIES:
                            await asyncio.sleep(delay)

                    except anthropic.APIStatusError as e:
                        last_error = e
                        if e.status_code and 400 <= e.status_code < 500 and e.status_code != 429:
                            raise AgentError(
                                f"Anthropic API client error {e.status_code}: {str(e)}",
                                agent_name=model,
                            ) from e
                        delay = _compute_llm_delay(attempt, self.BASE_RETRY_DELAY, deadline=deadline)
                        logger.warning(
                            "anthropic_server_error | model=%s attempt=%d/%d | waiting %.2fs",
                            model, attempt + 1, self.MAX_RETRIES, delay,
                        )
                        if attempt < self.MAX_RETRIES:
                            await asyncio.sleep(delay)

                    except Exception as e:
                        last_error = e
                        delay = _compute_llm_delay(attempt, self.BASE_RETRY_DELAY, deadline=deadline)
                        logger.warning(
                            "anthropic_unexpected | model=%s attempt=%d/%d error=%s",
                            model, attempt + 1, self.MAX_RETRIES, str(e),
                        )
                        if attempt < self.MAX_RETRIES:
                            await asyncio.sleep(delay)

                raise AgentError(
                    f"Anthropic call failed after {self.MAX_RETRIES + 1} attempts: {last_error}",
                    agent_name=model,
                ) from last_error

        return await breaker.async_call(_execute_anthropic_call)

    async def acomplete(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 1024,
        model: str | None = None,
        json_mode: bool = False,
        deadline: Any | None = None,
    ) -> LLMResponse:
        """
        Typed asynchronous completion method for evaluators, judges, and tools.
        """
        from backend.config import get_settings
        cfg = get_settings()
        target_model = model or getattr(cfg, "openai_embedding_model", "gpt-4o-mini")
        if target_model.startswith("text-embedding"):
            target_model = "gpt-4o-mini"
        return await self.call_openai(
            model=target_model,
            messages=[{"role": "user", "content": user_message}],
            system_prompt=system_prompt,
            json_mode=json_mode,
            max_tokens=max_tokens,
            deadline=deadline,
        )

    def complete(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 1024,
        model: str | None = None,
        json_mode: bool = False,
        deadline: Any | None = None,
    ) -> LLMResponse:
        """
        Typed synchronous completion method for evaluator/judge.
        Executes acomplete via event loop or thread runner safely.
        """
        import concurrent.futures
        coro = self.acomplete(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=max_tokens,
            model=model,
            json_mode=json_mode,
            deadline=deadline,
        )
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        else:
            return asyncio.run(coro)


def _try_extract_json(text: str) -> dict | list:
    """
    Output guardrail: tries to extract valid JSON from partially malformed LLM output.

    LLMs sometimes wrap their JSON in markdown code blocks:
      ```json
      { "findings": [...] }
      ```
    Or add a short preamble:
      "Here are the findings:\n{ ... }"

    This function tries three strategies in order:
      1. Strip markdown code fences, parse
      2. Find the first { or [ and parse from there
      3. Give up and return empty dict

    WIKI PRINCIPLE (Production-Hardening.md):
    "Redact before block" — extract partial signal before giving up entirely.
    An empty dict triggers low confidence -> HITL, which is better than crashing.
    """
    if not text:
        return {}

    # Strategy 1: strip markdown code fences
    cleaned = text.strip()
    for fence in ["```json", "```JSON", "```"]:
        if cleaned.startswith(fence):
            cleaned = cleaned[len(fence):]
            break
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strategy 2: find the first { or [ character and parse from there
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = cleaned.find(start_char)
        if start == -1:
            continue
        # Find the last matching closing character
        end = cleaned.rfind(end_char)
        if end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                continue

    # Strategy 3: give up
    logger.error("json_extraction_failed | could not extract JSON from LLM output")
    return {}


# Module-level singleton.
# Stateless — safe to share across all concurrent agent calls.
llm_client = LLMClient()
