# backend/economics/pricing.py
#
# Model token pricing and conservative cost estimation.
# Enforces:
#   - Honest model pricing per 1,000 tokens (USD)
#   - Explicit conservative estimate for unknown models OR strict rejection
#   - Pre-call cost estimation for atomic budget reservations
#

from __future__ import annotations

import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)


class UnknownModelPricingError(Exception):
    """Raised when strict pricing is enabled and a model is missing from the price table."""
    def __init__(self, model: str) -> None:
        self.model = model
        super().__init__(
            f"Unknown pricing for model '{model}'. "
            f"Configure pricing in MODEL_TOKEN_PRICES or disable strict_price_enforcement."
        )


# ---------------------------------------------------------------------------
# Token cost table (USD per 1,000 tokens)
# ---------------------------------------------------------------------------
MODEL_TOKEN_PRICES: dict[str, dict[str, float]] = {
    # OpenAI Frontier & Standard
    "gpt-4o":                     {"input": 0.005,    "output": 0.015},
    "gpt-4o-2024-05-13":          {"input": 0.005,    "output": 0.015},
    "gpt-4o-2024-08-06":          {"input": 0.0025,   "output": 0.010},
    "gpt-4o-mini":                {"input": 0.00015,  "output": 0.0006},
    "gpt-4o-mini-2024-07-18":     {"input": 0.00015,  "output": 0.0006},
    "gpt-3.5-turbo":              {"input": 0.0005,   "output": 0.0015},
    "gpt-3.5-turbo-0125":         {"input": 0.0005,   "output": 0.0015},

    # OpenAI Embeddings
    "text-embedding-3-large":     {"input": 0.00013,  "output": 0.0},
    "text-embedding-3-small":     {"input": 0.00002,  "output": 0.0},
    "text-embedding-ada-002":     {"input": 0.00010,  "output": 0.0},

    # Anthropic Claude
    "claude-3-5-sonnet":          {"input": 0.003,    "output": 0.015},
    "claude-3-5-sonnet-20241022": {"input": 0.003,    "output": 0.015},
    "claude-3-5-sonnet-20240620": {"input": 0.003,    "output": 0.015},
    "claude-3-haiku":             {"input": 0.00025,  "output": 0.00125},
    "claude-3-haiku-20240307":    {"input": 0.00025,  "output": 0.00125},
    "claude-3-opus":              {"input": 0.015,    "output": 0.075},
    "claude-3-opus-20240229":     {"input": 0.015,    "output": 0.075},

    # NVIDIA NIM & Open-Weights / Reasoning Models
    "openai/gpt-oss-120b":        {"input": 0.0005,   "output": 0.0015},
    "openai/gpt-oss-20b":         {"input": 0.00015,  "output": 0.0006},
    "gpt-oss-120b":               {"input": 0.0005,   "output": 0.0015},
    "gpt-oss-22b":                {"input": 0.00015,  "output": 0.0006},
    "gpt-oss-20b":                {"input": 0.00015,  "output": 0.0006},
    "meta/llama-3.3-70b-instruct":{"input": 0.00035,  "output": 0.0004},
    "meta/llama-3.1-70b-instruct":{"input": 0.00035,  "output": 0.0004},

    # Google Gemini Models
    "gemini-1.5-pro":             {"input": 0.00125,  "output": 0.005},
    "gemini-1.5-flash":           {"input": 0.000075, "output": 0.0003},
    "gemini-2.0-flash":           {"input": 0.0001,   "output": 0.0004},
    "gemini-2.0-flash-exp":       {"input": 0.0001,   "output": 0.0004},
}

# Conservative default fallback pricing (frontier rates: $0.005 in / $0.015 out per 1k tokens)
CONSERVATIVE_FALLBACK_PRICE: dict[str, float] = {
    "input": 0.005,
    "output": 0.015,
}


def normalize_model_name(model: str) -> str:
    """Normalize model string to match pricing keys."""
    cleaned = (model or "").strip().lower()
    if cleaned in MODEL_TOKEN_PRICES:
        return cleaned

    # Try removing vendor prefix (e.g., "openai/gpt-4o" -> "gpt-4o")
    if "/" in cleaned:
        unprefixed = cleaned.split("/", 1)[1]
        if unprefixed in MODEL_TOKEN_PRICES:
            return unprefixed

    # Try matching without version dates
    for key in MODEL_TOKEN_PRICES:
        if cleaned.startswith(key):
            return key

    return cleaned


def get_token_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    strict: bool = False,
) -> float:
    """
    Computes cost of tokens for an LLM/embedding call in USD.

    If model is unknown:
      - If strict is True: raises UnknownModelPricingError
      - If strict is False: uses CONSERVATIVE_FALLBACK_PRICE and logs warning.
    """
    norm_key = normalize_model_name(model)
    rates = MODEL_TOKEN_PRICES.get(norm_key)

    if rates is None:
        if strict:
            raise UnknownModelPricingError(model)
        logger.warning(
            "unknown_model_pricing | using_conservative_default | model=%s rates=%s",
            model, CONSERVATIVE_FALLBACK_PRICE,
        )
        rates = CONSERVATIVE_FALLBACK_PRICE

    in_cost = (max(0, input_tokens) / 1000.0) * rates.get("input", 0.0)
    out_cost = (max(0, output_tokens) / 1000.0) * rates.get("output", 0.0)
    return round(in_cost + out_cost, 8)


def estimate_call_cost(
    model: str,
    input_chars: int = 4000,
    max_tokens: int = 2048,
    strict: bool = False,
) -> float:
    """
    Calculates a conservative pre-call estimate for atomic reservation.
    Assumes 3.5 chars per token for inputs and 75% max_tokens generation.
    """
    est_input_tokens = max(100, math.ceil(max(0, input_chars) / 3.5))
    est_output_tokens = min(max_tokens, max(256, int(max_tokens * 0.75)))
    return get_token_cost(
        model=model,
        input_tokens=est_input_tokens,
        output_tokens=est_output_tokens,
        strict=strict,
    )


def estimate_embedding_cost(
    text_chars: int,
    model: str = "text-embedding-3-large",
) -> float:
    """Calculates embedding cost estimate based on text character count."""
    tokens = max(1, math.ceil(max(0, text_chars) / 3.5))
    return get_token_cost(model=model, input_tokens=tokens, output_tokens=0, strict=False)
