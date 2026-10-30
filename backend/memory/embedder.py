# backend/memory/embedder.py
#
# OpenAI embedding client — the bridge between raw text and vector space.
#
# MODEL CHOICE: text-embedding-3-large
# (From RAG-Architecture.md wiki, "Dense Embeddings" and ADR-003):
#   "Dense (embeddings) captures semantic understanding:
#    'maximum thrust at depth' even if phrased differently."
#   text-embedding-3-large: 256 dimensions via Matryoshka dimensionality reduction,
#   matching VECTOR(256) in code_chunks (ADR-003).
#   Provides 6x less storage with the same recall curve on code.
#
# CHUNKING STRATEGY: chunk by FILE / AST, not by arbitrary token count
# (From RAG-Architecture.md wiki, "Token-Limit Chunking" Anti-Pattern):
#   "Splitting documents purely on character/token count destroys section
#    hierarchy, making it impossible to trace answers to their source location."
#   For code: AST boundaries and semantic file units preserve structure.
#
# INPUT LENGTH GUARD: 8000 chars
# OpenAI's text-embedding-3 supports 8191 tokens (~32k chars) input.
# We cap at 8000 chars (conservative approximation) to ensure safety.
#
# ASYNC CLIENT:
# AsyncOpenAI is used throughout. All calls are async coroutines.
#
# GRACEFUL DEGRADATION:
# (From Production-Hardening.md wiki, "Circuit Breaker" + "Graceful Degradation"):
#   Every public method catches ALL exceptions and re-raises them as a simple
#   EmbeddingError. The caller (context_retriever.py) catches EmbeddingError
#   and returns "" — the pipeline continues without RAG context.
#   The embedder NEVER crashes the review pipeline.
#
# STRICT CONTRACT & SEMANTIC VALIDITY (Gate B — T13):
#   - Explicit EmbeddingContract: provider, model, dimension, normalization, and namespace.
#   - Strict shape guarantees: embed_batch(N texts) returns exactly N vectors of dimension D.
#   - Empty input policy: zero vector of exact dimension D.
#   - No fake fallback: cryptographic hash is NOT an embedding. Non-OpenAI keys (like nvapi-)
#     raise EmbeddingError to explicitly disable retrieval rather than polluting vector space.
#   - Synthetic test vectors are confined strictly to test environments via set_test_embedder.

import logging
import math
from dataclasses import dataclass
from typing import Any, Callable

from openai import AsyncOpenAI

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum input length for embedding.
MAX_EMBED_CHARS = 8_000

# Default embedding dimensionality (reads from settings if available).
# text-embedding-3-large truncated to 256 dimensions matches code_chunks VECTOR(256) (ADR-003).
DEFAULT_EMBEDDING_DIMENSIONS = 256
EMBEDDING_DIMENSIONS = DEFAULT_EMBEDDING_DIMENSIONS


@dataclass(frozen=True)
class EmbeddingContract:
    """
    Formal embedding contract across storage, models, and retrieval.
    Enforces unified dimensions, normalization, namespace, and versioning.
    """
    provider: str = "openai"
    model: str = "text-embedding-3-large"
    dimension: int = 256
    normalized: bool = True
    namespace: str = "code_chunks"
    version: str = "v1"


def get_embedding_contract() -> EmbeddingContract:
    """Returns the active embedding contract derived from configuration."""
    cfg = get_settings()
    model = getattr(cfg, "openai_embedding_model", "text-embedding-3-large")
    dims = getattr(cfg, "openai_embedding_dimensions", DEFAULT_EMBEDDING_DIMENSIONS)
    return EmbeddingContract(
        provider="openai",
        model=model,
        dimension=dims,
        normalized=True,
        namespace="code_chunks",
        version="v1",
    )


def normalize_vector(vec: list[float]) -> list[float]:
    """Applies L2 normalization so cosine distance equals dot product."""
    if not vec:
        return vec
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0 or math.isclose(norm, 1.0, rel_tol=1e-5):
        return vec
    return [x / norm for x in vec]


# Optional test hook to confine synthetic vectors exclusively to tests
_test_embedder_override: Callable[[list[str]], Any] | None = None


def set_test_embedder(fn: Callable[[list[str]], Any] | None) -> None:
    """Confines synthetic vectors exclusively to test environments."""
    global _test_embedder_override
    _test_embedder_override = fn


class EmbeddingError(Exception):
    """
    Raised when an embedding API call fails or when semantic embeddings are unavailable.

    Callers (specifically context_retriever.py) catch this and return ""
    (graceful degradation: no RAG context, review still runs).
    Never propagates to the user or crashes the review.
    """
    pass


# ---------------------------------------------------------------------------
# Core embedding functions
# ---------------------------------------------------------------------------

async def embed_text(text: str) -> list[float]:
    """
    Embeds a single text string into a contract-dimensional vector (default 256).

    Designed for: embedding a PR diff summary or a code search query.
    One API call per call to this function.

    INPUT LENGTH GUARD:
    If text > MAX_EMBED_CHARS, truncates to MAX_EMBED_CHARS.
    We truncate from the end (preserve the beginning — imports and
    class signatures are at the top and are semantically richest).

    Args:
        text: The text to embed. Will be truncated if over 8000 chars.

    Returns:
        List of contract-dimensional floats (the normalized embedding vector).

    Raises:
        EmbeddingError: on any API failure or unavailable provider. Caller handles gracefully.
    """
    contract = get_embedding_contract()
    dims = contract.dimension

    if not text or not text.strip():
        # Empty text: explicit zero vector policy of exact contract dimensions
        logger.debug("embed_text | empty_text | returning zero vector of dimension %d", dims)
        return [0.0] * dims

    # Confine synthetic vectors to tests if test hook is active
    if _test_embedder_override is not None:
        raw_res = await _test_embedder_override([text])
        vec = raw_res[0]
        if len(vec) != dims:
            raise EmbeddingError(f"Test embedder returned dimension {len(vec)}, expected {dims}")
        return normalize_vector(vec)

    # Phase 11 & Gate A (T08): Redact secrets / PII before dispatching to embedding provider
    from backend.security.masking import redact_text
    text, _ = redact_text(text)

    # Truncate to MAX_EMBED_CHARS if needed
    original_len = len(text)
    if original_len > MAX_EMBED_CHARS:
        text = text[:MAX_EMBED_CHARS]
        logger.debug(
            "embed_text | truncated | original_chars=%d truncated_to=%d",
            original_len, MAX_EMBED_CHARS,
        )

    cfg = get_settings()

    # Reject non-OpenAI keys (e.g. nvapi-) masquerading as OpenAI embedding provider.
    # A cryptographic hash is not a semantic embedding; disable retrieval cleanly.
    if cfg.openai_api_key.startswith("nvapi-"):
        raise EmbeddingError(
            "NVIDIA NIM does not provide text-embedding-3 embeddings. "
            "Semantic retrieval is disabled. Configure a supported OpenAI embedding key or disable RAG."
        )

    if not cfg.openai_api_key or cfg.openai_api_key == "change-me-in-production":
        raise EmbeddingError("OpenAI API key is missing or unconfigured. Cannot generate embeddings.")

    client = AsyncOpenAI(api_key=cfg.openai_api_key, base_url=cfg.openai_api_base_url or None)

    try:
        kwargs = {"model": contract.model, "input": text}
        if "text-embedding-3" in contract.model:
            kwargs["dimensions"] = dims
        response = await client.embeddings.create(**kwargs)
        vector = response.data[0].embedding

        # Gate B T18: Record embedding cost in budget scope
        try:
            from backend.economics import record_cost_entry
            from backend.observability.workflow_context import get_workflow_context
            ctx = get_workflow_context()
            tok_count = getattr(response.usage, "total_tokens", len(text) // 4)
            emb_cost = round((tok_count / 1000.0) * 0.00013, 8)
            asyncio.create_task(
                record_cost_entry(
                    workflow_id=getattr(ctx, "workflow_id", None),
                    tenant_id=getattr(ctx, "tenant_id", None),
                    agent_type="embedder",
                    model=contract.model,
                    input_tokens=tok_count,
                    cost_usd=emb_cost,
                    call_type="embedding",
                )
            )
        except Exception:
            pass

        if len(vector) != dims:
            raise EmbeddingError(
                f"Embedding provider returned vector of dimension {len(vector)}, expected {dims}"
            )

        logger.debug(
            "embed_text | success | model=%s dims=%d input_chars=%d",
            contract.model, len(vector), len(text),
        )

        return normalize_vector(vector)

    except EmbeddingError:
        raise
    except Exception as e:
        raise EmbeddingError(
            f"OpenAI embedding call failed: {type(e).__name__}: {e}"
        ) from e


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """
    Embeds a list of texts in a single API call (batch mode).

    Designed for: embedding multiple code chunks at index time.
    One API call for all texts (much more efficient than N separate calls).
    OpenAI's embedding API accepts up to ~2048 inputs per request.

    BATCH TRUNCATION & SHAPE GUARANTEES:
    - Result length strictly equals input length (result[i] corresponds to texts[i]).
    - Each vector strictly matches contract.dimension (256 dims).
    - Empty or whitespace inputs yield a zero vector of exact contract dimension.
    - Duplicate inputs receive identical embeddings in their respective slots.

    Args:
        texts: List of strings to embed. Empty list returns [].

    Returns:
        List of contract-dimensional vectors, one per input text in original order.

    Raises:
        EmbeddingError: on any API failure or unavailable provider.
    """
    if not texts:
        return []

    contract = get_embedding_contract()
    dims = contract.dimension

    # Phase 11 & Gate A (T08): Redact secrets / PII from all texts before batch embedding
    from backend.security.masking import redact_text
    redacted_texts = [redact_text(t)[0] if t else "" for t in texts]

    # Truncate each text individually (preserve structural unit per chunk)
    truncated_texts: list[str] = []
    empty_indices: set[int] = set()

    for i, text in enumerate(redacted_texts):
        if not text or not text.strip():
            truncated_texts.append("")   # placeholder
            empty_indices.add(i)
        elif len(text) > MAX_EMBED_CHARS:
            truncated_texts.append(text[:MAX_EMBED_CHARS])
        else:
            truncated_texts.append(text)

    # Initialize results with exact length, order, and dimensions (empty indices get zero vectors)
    results: list[list[float]] = [[0.0] * dims for _ in texts]

    # Separate non-empty texts for the API call
    non_empty = [(i, t) for i, t in enumerate(truncated_texts) if i not in empty_indices]

    if not non_empty:
        # All texts were empty
        return results

    # Confine synthetic vectors to tests if test hook is active
    if _test_embedder_override is not None:
        indices, batch_texts = zip(*non_empty)
        raw_res = await _test_embedder_override(list(batch_texts))
        if len(raw_res) != len(batch_texts):
            raise EmbeddingError(f"Test embedder returned {len(raw_res)} vectors, expected {len(batch_texts)}")
        for position, v in zip(indices, raw_res):
            if len(v) != dims:
                raise EmbeddingError(f"Test embedder returned dimension {len(v)}, expected {dims}")
            results[position] = normalize_vector(v)
        return results

    cfg = get_settings()

    # Reject non-OpenAI keys (e.g. nvapi-) masquerading as OpenAI embedding provider
    if cfg.openai_api_key.startswith("nvapi-"):
        raise EmbeddingError(
            "NVIDIA NIM does not provide text-embedding-3 embeddings. "
            "Semantic retrieval is disabled. Configure a supported OpenAI embedding key or disable RAG."
        )

    if not cfg.openai_api_key or cfg.openai_api_key == "change-me-in-production":
        raise EmbeddingError("OpenAI API key is missing or unconfigured. Cannot generate embeddings.")

    client = AsyncOpenAI(api_key=cfg.openai_api_key, base_url=cfg.openai_api_base_url or None)

    try:
        indices, batch_texts = zip(*non_empty)
        kwargs = {"model": contract.model, "input": list(batch_texts)}
        if "text-embedding-3" in contract.model:
            kwargs["dimensions"] = dims
        response = await client.embeddings.create(**kwargs)

        # Gate B T18: Record batch embedding cost in budget scope
        try:
            from backend.economics import record_cost_entry
            from backend.observability.workflow_context import get_workflow_context
            ctx = get_workflow_context()
            tok_count = getattr(response.usage, "total_tokens", sum(len(t) for t in batch_texts) // 4)
            emb_cost = round((tok_count / 1000.0) * 0.00013, 8)
            asyncio.create_task(
                record_cost_entry(
                    workflow_id=getattr(ctx, "workflow_id", None),
                    tenant_id=getattr(ctx, "tenant_id", None),
                    agent_type="embedder",
                    model=contract.model,
                    input_tokens=tok_count,
                    cost_usd=emb_cost,
                    call_type="embedding",
                )
            )
        except Exception:
            pass

        if len(response.data) != len(batch_texts):
            raise EmbeddingError(
                f"OpenAI returned {len(response.data)} embeddings, expected {len(batch_texts)}"
            )

        logger.debug(
            "embed_batch | success | model=%s batch_size=%d dims=%d",
            contract.model, len(batch_texts), dims,
        )

        # Reconstruct the full results list with dimension and normalization guarantees
        for position, embedding_obj in zip(indices, response.data):
            vec = embedding_obj.embedding
            if len(vec) != dims:
                raise EmbeddingError(
                    f"Embedding provider returned vector of dimension {len(vec)}, expected {dims}"
                )
            results[position] = normalize_vector(vec)

        return results

    except EmbeddingError:
        raise
    except Exception as e:
        raise EmbeddingError(
            f"OpenAI batch embedding call failed: {type(e).__name__}: {e}"
        ) from e
