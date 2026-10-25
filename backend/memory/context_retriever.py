# backend/memory/context_retriever.py
#
# The single entry point for RAG context retrieval.
#
# WHAT THIS FILE DOES:
#   1. Takes a PR diff as the "query" — what are we looking for?
#   2. Embeds the first MAX_QUERY_CHARS of the diff (a semantic fingerprint)
#   3. Asks Qdrant: "what code have we seen before that looks like this?"
#   4. Formats the top results as a plain text context string
#   5. Returns that string to be injected into the agent prompts
#
# SINGLE ENTRY POINT PRINCIPLE (from Decoupling-and-Law-of-Demeter.md wiki):
#   "A module should talk to its immediate neighbors, not reach through them."
#   nodes.py calls retrieve_context_for_diff() ONLY.
#   It does not import embedder.py or qdrant_client.py.
#   If we replace Qdrant with Weaviate, only this file and qdrant_client.py change.
#   nodes.py is untouched.
#
# GRACEFUL DEGRADATION — THE CARDINAL RULE:
# (From Production-Hardening.md wiki, "Defense in Depth"):
#   "Each guardrail is independent. Each can block."
#   Applied here as: each failure point is independent. Each returns "".
#   Failure at any step returns "" immediately:
#     - Empty diff         -> return ""
#     - Embed fails        -> return ""  (EmbeddingError caught)
#     - Qdrant unavailable -> return ""  (search returns [] on error)
#     - No results found   -> return ""
#   The review pipeline receives "" and runs with diff-only analysis.
#   This is NOT a degraded experience — it is the DESIGNED fallback.
#   RAG context is enhancement, not foundation.
#
# QUERY CONSTRUCTION:
# (From RAG-Architecture.md wiki):
#   "Dense embeddings capture semantic understanding."
#   We embed the FIRST part of the diff (the changed code) not the entire diff.
#   The first part of a unified diff contains the most semantically dense content:
#   file headers, hunk headers, the actual changed lines.
#   We cap at MAX_QUERY_CHARS to stay within embedding API limits.
#
# CONTEXT FORMAT:
# The output is a plain text block:
#   --- Relevant prior code context ---
#   [File: src/auth.py (from PR #17)]
#   <code chunk text>
#   ---
#   [File: src/utils.py (from PR #15)]
#   <code chunk text>
#   ---
#
# This format was chosen because:
#   1. Agents get a labeled context block they can cite ("see prior context for auth.py")
#   2. File names are explicit — agents can say "auth.py was seen before and had pattern X"
#   3. PR number is included — human reviewers can trace the provenance
#
# (RAG-Architecture.md: "Citation grounding: every retrieved chunk must carry provenance.")

import logging
import re
from typing import Any

from backend.config.settings import Settings, get_settings
from backend.memory.embedder import EmbeddingError, embed_text
# TIGER: was Qdrant search — now pgvectorscale DiskANN hybrid retrieval
from backend.memory.tiger_client import CodeChunk, get_tiger_memory

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# How many chars of the diff to embed as the search query when falling back
MAX_QUERY_CHARS = 2_000

# Minimum score to include a result (RRF scale vs Cosine scale)
MIN_SIMILARITY_SCORE = 0.5


# ---------------------------------------------------------------------------
# Diff Entity Extraction
# ---------------------------------------------------------------------------
def extract_diff_entities(diff: str) -> list[dict[str, str]]:
    """
    Extracts changed functions, classes, and file paths from a unified diff.
    Returns a list of dicts with keys: 'path', 'symbol', 'query_text'.
    """
    entities: list[dict[str, str]] = []
    current_path = ""
    seen_symbols: set[tuple[str, str]] = set()

    for line in diff.splitlines():
        # Match git diff file header
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4 and parts[3].startswith("b/"):
                current_path = parts[3][2:]
        elif line.startswith("+++ b/"):
            current_path = line[6:].strip()

        # Match Python function/class definitions
        m_py = re.search(r"^[+ ]\s*(?:async\s+)?def\s+([A-Za-z0-9_]+)\s*\(|^[+ ]\s*class\s+([A-Za-z0-9_]+)", line)
        if m_py:
            sym = m_py.group(1) or m_py.group(2)
            if sym and not (sym.startswith("__") and sym.endswith("__")) and (current_path, sym) not in seen_symbols:
                seen_symbols.add((current_path, sym))
                entities.append({
                    "path": current_path,
                    "symbol": sym,
                    "query_text": f"File: {current_path}\nSymbol: {sym}\n{line.strip()}",
                })
            continue

        # Match JS/TS function, arrow function, or class definitions
        m_js = re.search(
            r"^[+ ]\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_]+)\s*\("
            r"|^[+ ]\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?\("
            r"|^[+ ]\s*(?:export\s+)?class\s+([A-Za-z0-9_]+)",
            line,
        )
        if m_js:
            sym = m_js.group(1) or m_js.group(2) or m_js.group(3)
            if sym and (current_path, sym) not in seen_symbols:
                seen_symbols.add((current_path, sym))
                entities.append({
                    "path": current_path,
                    "symbol": sym,
                    "query_text": f"File: {current_path}\nSymbol: {sym}\n{line.strip()}",
                })
            continue

        # Match Go / Rust function definitions
        m_other = re.search(r"^[+ ]\s*(?:pub\s+)?fn\s+([A-Za-z0-9_]+)\s*\(|^[+ ]\s*func\s+(?:\([^)]+\)\s+)?([A-Za-z0-9_]+)\s*\(", line)
        if m_other:
            sym = m_other.group(1) or m_other.group(2)
            if sym and (current_path, sym) not in seen_symbols:
                seen_symbols.add((current_path, sym))
                entities.append({
                    "path": current_path,
                    "symbol": sym,
                    "query_text": f"File: {current_path}\nSymbol: {sym}\n{line.strip()}",
                })

    # Return top 5 distinct entities to bound embedding API calls
    return entities[:5]


# ---------------------------------------------------------------------------
# retrieve_context_for_diff()
#
# The public interface. This is the only function nodes.py calls.
# ---------------------------------------------------------------------------
async def retrieve_context_for_diff(
    diff: str,
    repo_full_name: str,
    settings: Settings | None = None,
) -> str:
    """
    Retrieves RAG context for a PR diff using multi-entity semantic queries.

    Extracts changed functions and classes from the PR diff, embeds each
    modified entity, queries Tiger Cloud (pgvectorscale DiskANN + tsvector RRF),
    and aggregates relevant chunks across all modified files.

    GRACEFUL DEGRADATION:
    This function NEVER raises. On any failure, it returns "".
    """
    # --- Guard: empty diff ---
    if not diff or not diff.strip():
        logger.debug(
            "retrieve_context | empty_diff | repo=%s -> returning ''", repo_full_name
        )
        return ""

    # --- Guard: empty repo ---
    if not repo_full_name or not repo_full_name.strip():
        logger.debug("retrieve_context | empty_repo -> returning ''")
        return ""

    cfg = settings or get_settings()

    # Step 1: Extract entities or fallback to diff prefix
    entities = extract_diff_entities(diff)
    if not entities:
        entities = [{"path": "", "symbol": "", "query_text": diff[:MAX_QUERY_CHARS]}]

    try:
        client = get_tiger_memory()
    except Exception as exc:
        logger.warning("retrieve_context | tiger_not_initialized | error=%s -> ''", exc)
        return ""

    combined_results: list[Any] = []
    seen_chunk_keys: set[str] = set()

    # Step 2: Query Tiger Cloud for each extracted entity
    for entity in entities:
        query_text = entity["query_text"]
        try:
            query_vector = await embed_text(query_text)
        except EmbeddingError as e:
            logger.warning(
                "retrieve_context | embed_failed | repo=%s symbol=%s error=%s",
                repo_full_name, entity.get("symbol"), str(e),
            )
            continue
        except Exception as e:
            logger.warning(
                "retrieve_context | embed_unexpected_error | repo=%s error=%s: %s",
                repo_full_name, type(e).__name__, e,
            )
            continue

        try:
            results = await client.search(
                query_vector,
                repo=repo_full_name,
                hybrid=True,
                query_text=entity.get("symbol") or query_text,
                top_k=3,
            )
        except Exception as e:
            logger.warning("retrieve_context | search_failed | repo=%s error=%s", repo_full_name, e)
            results = []

        for r in results:
            score = r.get("score", 0.0) if hasattr(r, "get") else getattr(r, "score", 0.0)
            # Relevancy check: RRF score threshold (0.002) vs pure Cosine (0.35)
            is_relevant = (score >= 0.002 if score <= 0.1 else score >= 0.35)
            if not is_relevant:
                continue

            chunk_id = str(r.get("id") if hasattr(r, "get") else getattr(r, "id", ""))
            chunk_key = chunk_id or f"{r.get('file_path', r.get('path'))}:{r.get('chunk_index', 0)}"
            if chunk_key not in seen_chunk_keys:
                seen_chunk_keys.add(chunk_key)
                combined_results.append(r)

    if not combined_results:
        logger.debug(
            "retrieve_context | no_relevant_results | repo=%s -> ''",
            repo_full_name,
        )
        return ""

    # Step 3: Format the aggregated context string
    context = _format_context(combined_results)

    logger.info(
        "retrieve_context | success | repo=%s entities=%d chunks=%d",
        repo_full_name, len(entities), len(combined_results),
    )

    return context


# ---------------------------------------------------------------------------
# PRIVATE HELPERS
# ---------------------------------------------------------------------------

def _format_context(results: list[dict]) -> str:
    """
    Formats Qdrant search results as a plain text context block.

    Each result becomes a labeled section with file path, PR number, and code.
    The format is designed to be injected directly into an agent's user message.

    WHY PLAIN TEXT AND NOT JSON?
    The context is part of an LLM prompt, not an API response.
    Plain text is more token-efficient and agents reason about it more naturally.
    JSON keys add token overhead without adding semantics.

    CITATION GROUNDING (RAG-Architecture.md):
    Every chunk is labeled with its source: file path AND PR number.
    Agents can include this provenance in their findings:
    "Similar pattern was seen in auth.py (PR #17) — check for same issue."
    """
    lines: list[str] = ["--- Relevant prior code context ---"]

    for result in results:
        file_path = result.get("file_path", "unknown")
        chunk_text = result.get("chunk_text", "")
        pr_number = result.get("pr_number", "?")
        score = result.get("score", 0.0)

        # Skip chunks with empty content (shouldn't happen but defensive)
        if not chunk_text.strip():
            continue

        lines.append(f"\n[File: {file_path} | from PR #{pr_number} | similarity: {score:.2f}]")
        lines.append(chunk_text)
        lines.append("---")

    if len(lines) <= 1:
        # Only the header was added (all chunks had empty text)
        return ""

    return "\n".join(lines)
