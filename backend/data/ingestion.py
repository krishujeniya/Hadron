# backend/data/ingestion.py
#
# Repository ingestion pipeline.
# Converts a GitHub repo's source files into Tiger Cloud vector embeddings.
#
# DESIGN PHILOSOPHY (Batch-Processing-Patterns.md wiki):
#   "Immutable inputs and explicit outputs: a batch job reads input without
#    modifying it and writes output to a new location. This makes reruns safe."
#
#   GitHub file content is the IMMUTABLE SOURCE. Tiger code_chunks is the DERIVED STORE.
#   This pipeline is safe to re-run at any time — same input produces identical
#   output. If code_chunks is wiped, re-running ingestion restores it fully.
#
# TIGER CHANGE:
#   Previously: upsert_code_chunks() from backend.memory.qdrant_client
#   Now:        TigerMemoryClient.upsert_chunks() via tiger_client.py
#   Same logical interface. Tiger uses DiskANN (pgvectorscale) instead of HNSW (Qdrant).
#   The code_chunks table lives on the Tiger Cloud Postgres instance.
#   Freshness tracking (repo_file_index) is on the same Tiger instance.
#
# COMPOSABLE STAGES (Unix philosophy from Batch wiki):
#   "Each program does one thing well. Programs can be composed via pipes."
#   Each stage below is a pure async function. They compose sequentially:
#     fetch_repo_tree -> filter_code_files -> fetch_file_content
#     -> chunk (split into CodeChunk objects) -> embed -> upsert (Tiger)
#     -> mark_freshness (via freshness.py)
#   Any stage can fail independently without corrupting others.
#
# PER-FILE ERROR ISOLATION:
#   A single file failing to fetch/embed does NOT abort the whole ingestion.
#   The pipeline logs a warning and continues.
#
# FRESHNESS CHECK (Derived-Data-Systems.md wiki):
#   We compare GitHub's current blob SHA against what we last embedded.
#   Same SHA = file unchanged = skip. Different SHA = stale = re-embed.
#   This makes incremental re-indexing cheap: only changed files are re-embedded.
#
# CODE FILE EXTENSIONS:
#   We index source code only — not docs, configs, or binary files.

import ast
import logging
import re
from typing import Any

import httpx

from backend.config.settings import get_settings
from backend.data.freshness import get_stale_files, mark_files_embedded, remove_deleted_files
from backend.database.postgres import get_session_factory
from backend.memory.embedder import EmbeddingError, embed_text
from backend.memory.tiger_client import CodeChunk, get_tiger_memory  # TIGER: was qdrant_client
from backend.reliability.circuit_breaker import GITHUB_BREAKER

logger = logging.getLogger(__name__)


class ChunkBlock:
    """
    Representation of a code chunk with line range and symbol attribution.
    Supports 2-element tuple unpacking `(text, symbol) = block` for backward compatibility
    while providing line_start, line_end, text, and symbol attributes.
    """
    def __init__(self, text: str, symbol: str | None, line_start: int, line_end: int):
        self.text = text
        self.symbol = symbol
        self.line_start = line_start
        self.line_end = line_end

    def __iter__(self):
        yield self.text
        yield self.symbol

    def __getitem__(self, idx: int) -> Any:
        return (self.text, self.symbol, self.line_start, self.line_end)[idx]

    def __len__(self) -> int:
        return 4

    def __repr__(self) -> str:
        return f"ChunkBlock(symbol={self.symbol!r}, lines={self.line_start}..{self.line_end}, len={len(self.text)})"


def split_lines_into_chunks(
    lines: list[str],
    symbol: str | None,
    line_offset: int,
    max_chunk_chars: int = 2500,
    overlap_ratio: float = 0.15,
) -> list[ChunkBlock]:
    """
    Split a list of lines into one or more ChunkBlock instances.
    Guarantees every line and character is covered without silent truncation.
    """
    if not lines:
        return []

    full_text = "".join(lines).strip()
    if len(full_text) <= max_chunk_chars:
        return [ChunkBlock(full_text, symbol, line_offset + 1, line_offset + len(lines))]

    chunks: list[ChunkBlock] = []
    total_lines = len(lines)
    avg_line_len = max(1, len(full_text) // total_lines)
    target_lines = max(5, int(max_chunk_chars / avg_line_len))
    overlap_lines = max(1, int(target_lines * overlap_ratio))
    step = max(1, target_lines - overlap_lines)

    curr_start = 0
    while curr_start < total_lines:
        curr_end = min(curr_start + target_lines, total_lines)
        chunk_lines = lines[curr_start:curr_end]
        chunk_str = "".join(chunk_lines).strip()
        if len(chunk_str) > max_chunk_chars:
            char_step = max(100, int(max_chunk_chars * (1.0 - overlap_ratio)))
            for c_start in range(0, len(chunk_str), char_step):
                c_end = min(c_start + max_chunk_chars, len(chunk_str))
                sub_text = chunk_str[c_start:c_end].strip()
                if sub_text:
                    chunks.append(ChunkBlock(sub_text, symbol, line_offset + curr_start + 1, line_offset + curr_end))
                if c_end >= len(chunk_str):
                    break
        else:
            if chunk_str:
                chunks.append(ChunkBlock(chunk_str, symbol, line_offset + curr_start + 1, line_offset + curr_end))

        if curr_end >= total_lines:
            break
        curr_start += step

    return chunks


async def upsert_code_chunks(chunks: list[CodeChunk]) -> int:
    """Upsert code chunks into the vector store (Tiger Cloud / pgvectorscale)."""
    try:
        tiger = get_tiger_memory()
    except RuntimeError:
        from backend.memory.tiger_client import TigerMemoryClient
        tiger = TigerMemoryClient(in_memory=True)
    return await tiger.upsert_chunks(chunks)


def chunk_code_by_ast(
    content: str,
    file_path: str,
    max_chunk_chars: int = 2500,
    overlap_ratio: float = 0.15,
) -> list[ChunkBlock]:
    """
    Chunks source code using AST/semantic boundary detection with complete line coverage.
    Guarantees that no preambles, definition bodies, or tails are silently dropped.
    """
    if not content or not content.strip():
        return []

    lines = content.splitlines(keepends=True)
    total_lines = len(lines)

    if len(content) <= max_chunk_chars:
        return [ChunkBlock(content.strip(), None, 1, total_lines)]

    chunks: list[ChunkBlock] = []

    # 1. Python AST parsing
    if file_path.endswith(".py"):
        try:
            tree = ast.parse(content)
            definitions: list[tuple[int, int, str]] = []  # (start_line, end_line, symbol)
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    start = node.lineno
                    end = getattr(node, "end_lineno", start + 20)
                    definitions.append((start, end, node.name))

            if definitions:
                # Capture entire preamble without truncation
                first_def_line = definitions[0][0]
                if first_def_line > 1:
                    preamble_lines = lines[:first_def_line - 1]
                    chunks.extend(
                        split_lines_into_chunks(
                            preamble_lines,
                            "module:preamble",
                            line_offset=0,
                            max_chunk_chars=max_chunk_chars,
                            overlap_ratio=overlap_ratio,
                        )
                    )

                # Process each definition completely
                for start, end, symbol in definitions:
                    def_lines = lines[start - 1:end]
                    chunks.extend(
                        split_lines_into_chunks(
                            def_lines,
                            symbol,
                            line_offset=start - 1,
                            max_chunk_chars=max_chunk_chars,
                            overlap_ratio=overlap_ratio,
                        )
                    )

                # Capture any post-definition module tail completely
                last_def_end = definitions[-1][1]
                if last_def_end < total_lines:
                    tail_lines = lines[last_def_end:]
                    chunks.extend(
                        split_lines_into_chunks(
                            tail_lines,
                            "module:tail",
                            line_offset=last_def_end,
                            max_chunk_chars=max_chunk_chars,
                            overlap_ratio=overlap_ratio,
                        )
                    )

                if chunks:
                    return chunks
        except Exception:
            # Fall back to regex/heuristic chunking if syntax error or parse issue
            pass

    # 2. General / Regex boundary chunking (JS/TS, Go, Rust, Java, Python fallback)
    boundary_regex = re.compile(
        r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_]+)|"
        r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?\(|"
        r"^(?:export\s+)?class\s+([A-Za-z0-9_]+)|"
        r"^(?:pub\s+)?fn\s+([A-Za-z0-9_]+)|"
        r"^func\s+(?:\([^)]+\)\s+)?([A-Za-z0-9_]+)"
    )

    boundary_indices: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        m = boundary_regex.search(line)
        if m:
            sym = next((g for g in m.groups() if g), None)
            boundary_indices.append((idx, sym or "boundary"))

    if boundary_indices:
        prev_idx = 0
        prev_sym: str | None = "module:preamble"
        for b_idx, sym in boundary_indices:
            if b_idx > prev_idx:
                block_lines = lines[prev_idx:b_idx]
                chunks.extend(
                    split_lines_into_chunks(
                        block_lines,
                        prev_sym,
                        line_offset=prev_idx,
                        max_chunk_chars=max_chunk_chars,
                        overlap_ratio=overlap_ratio,
                    )
                )
            prev_idx = b_idx
            prev_sym = sym
        # Final tail chunk
        if prev_idx < total_lines:
            tail_lines = lines[prev_idx:]
            chunks.extend(
                split_lines_into_chunks(
                    tail_lines,
                    prev_sym,
                    line_offset=prev_idx,
                    max_chunk_chars=max_chunk_chars,
                    overlap_ratio=overlap_ratio,
                )
            )
        if chunks:
            return chunks

    # 3. Fallback: complete line-based sliding window with overlap
    return split_lines_into_chunks(
        lines,
        None,
        line_offset=0,
        max_chunk_chars=max_chunk_chars,
        overlap_ratio=overlap_ratio,
    )

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# File extensions we consider "source code worth indexing."
# (RAG-Architecture.md: "match retrieval strategy to corpus shape")
# Exclusions: markdown, JSON, YAML, lock files, compiled outputs.
CODE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx",
    ".go", ".java", ".rb", ".rs", ".cpp",
    ".c", ".h", ".cs", ".swift", ".kt",
    ".scala", ".php", ".sh", ".bash",
}

# GitHub REST API base URL.
GITHUB_API_BASE = "https://api.github.com"

# Max file size to embed (bytes). Files larger than this are skipped.
# Rationale: embedder.py caps at 8000 chars anyway, but fetching a 500KB
# binary that happens to have a .py extension wastes network and API quota.
MAX_FILE_BYTES = 100_000  # 100 KB
MAX_INGESTION_FILES = 500  # Bound on stale files per run
MAX_CHUNKS_PER_FILE = 50   # Bound on chunks generated per file

# GitHub API timeout (seconds). Per-request, not total pipeline timeout.
GITHUB_REQUEST_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Stage 1: fetch_repo_tree
#
# Fetches the complete file tree of a repo at its HEAD commit.
# Returns a flat list of file dicts: {path, sha, size, type}.
# Only returns "blob" entries (files, not directories).
#
# WHY recursive=1: GitHub's tree API supports fetching the entire tree in
# one request using ?recursive=1. Without it, we'd have to walk each
# directory with separate requests — O(depth * branching_factor) API calls
# instead of one.
#
# (Batch-Processing-Patterns.md: "Prefer sequential I/O over many round trips.")
# ---------------------------------------------------------------------------
async def fetch_repo_tree(
    repo_full_name: str,
    token: str,
    client: httpx.AsyncClient,
) -> list[dict[str, Any]]:
    """
    Fetch the full file tree of a repo (HEAD commit, recursive).

    Returns list of dicts with keys: path, sha, size, type.
    Returns [] if the repo is unreachable (graceful degradation).
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Step 1: get default branch SHA
    repo_url = f"{GITHUB_API_BASE}/repos/{repo_full_name}"
    try:
        resp = await GITHUB_BREAKER.async_call(
            client.get, repo_url, headers=headers, timeout=GITHUB_REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        repo_data = resp.json()
        default_branch = repo_data.get("default_branch", "main")
    except httpx.HTTPStatusError as e:
        logger.warning(
            "fetch_repo_tree | repo_not_found | repo=%s status=%d",
            repo_full_name, e.response.status_code,
        )
        return []
    except Exception as e:
        logger.warning(
            "fetch_repo_tree | github_error | repo=%s error=%s",
            repo_full_name, e,
        )
        return []

    # Step 2: get HEAD commit SHA for default branch
    branch_url = f"{GITHUB_API_BASE}/repos/{repo_full_name}/branches/{default_branch}"
    try:
        resp = await GITHUB_BREAKER.async_call(
            client.get, branch_url, headers=headers, timeout=GITHUB_REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        branch_data = resp.json()
        tree_sha = branch_data["commit"]["commit"]["tree"]["sha"]
    except Exception as e:
        logger.warning(
            "fetch_repo_tree | branch_error | repo=%s branch=%s error=%s",
            repo_full_name, default_branch, e,
        )
        return []

    # Step 3: fetch full tree recursively (one API call for entire repo)
    tree_url = f"{GITHUB_API_BASE}/repos/{repo_full_name}/git/trees/{tree_sha}?recursive=1"
    try:
        resp = await GITHUB_BREAKER.async_call(
            client.get, tree_url, headers=headers, timeout=GITHUB_REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        tree_data = resp.json()

        # "truncated" means the repo has >100,000 files. Extremely rare.
        # We log a warning but still process what we got.
        if tree_data.get("truncated"):
            logger.warning(
                "fetch_repo_tree | tree_truncated | repo=%s "
                "items_returned=%d (repo has >100k files)",
                repo_full_name, len(tree_data.get("tree", [])),
            )

        # Return only blobs (files, not trees/directories)
        blobs = [
            item for item in tree_data.get("tree", [])
            if item.get("type") == "blob"
        ]

        logger.info(
            "fetch_repo_tree | done | repo=%s total_blobs=%d",
            repo_full_name, len(blobs),
        )
        return blobs

    except Exception as e:
        logger.warning(
            "fetch_repo_tree | tree_error | repo=%s error=%s",
            repo_full_name, e,
        )
        return []


# ---------------------------------------------------------------------------
# Stage 2: filter_code_files
#
# Filters a tree to code files only.
# Applies two filters:
#   1. Extension must be in CODE_EXTENSIONS
#   2. File size must be <= MAX_FILE_BYTES (skip large files)
#
# (RAG-Architecture.md: "Metadata-first filtering reduces search space and
#  improves accuracy." We apply this at ingestion too — index only what
#  an agent can meaningfully reason about.)
# ---------------------------------------------------------------------------
def filter_code_files(tree: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Filter tree entries to indexable source code files.

    Returns subset of tree entries that are small enough and have
    a recognized source code extension.
    """
    result = []
    skipped_ext = 0
    skipped_size = 0

    for item in tree:
        path: str = item.get("path", "")
        size: int = item.get("size", 0)

        # Check extension
        ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
        if ext.lower() not in CODE_EXTENSIONS:
            skipped_ext += 1
            continue

        # Check size
        if size > MAX_FILE_BYTES:
            skipped_size += 1
            logger.debug(
                "filter_code_files | skip_large | path=%s size=%d", path, size
            )
            continue

        result.append(item)

    logger.info(
        "filter_code_files | done | kept=%d skipped_ext=%d skipped_size=%d",
        len(result), skipped_ext, skipped_size,
    )
    return result


# ---------------------------------------------------------------------------
# Stage 3: fetch_file_content
#
# Fetches the raw text content of a single file from GitHub.
# Uses the blob SHA (from the tree) to fetch via the blob API.
# Falls back to the contents API if blob fetch fails.
#
# WHY blob API over contents API:
#   The blob API returns base64-encoded raw bytes. The contents API has a
#   1MB limit and is slower for large files. For code files <= 100KB, both
#   work — we use contents API as it returns utf-8 decoded text directly.
# ---------------------------------------------------------------------------
async def fetch_file_content(
    repo_full_name: str,
    file_path: str,
    token: str,
    client: httpx.AsyncClient,
) -> str | None:
    """
    Fetch the raw text content of a file from GitHub.

    Returns None if the file cannot be fetched (graceful degradation).
    Binary files that cannot be decoded as UTF-8 are also returned as None.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    url = f"{GITHUB_API_BASE}/repos/{repo_full_name}/contents/{file_path}"
    try:
        resp = await GITHUB_BREAKER.async_call(
            client.get, url, headers=headers, timeout=GITHUB_REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()

        # GitHub returns base64-encoded content for file contents
        import base64
        content_b64 = data.get("content", "")
        if not content_b64:
            return None

        # Remove newlines GitHub inserts into base64 output
        content_bytes = base64.b64decode(content_b64.replace("\n", ""))

        # Attempt UTF-8 decode; if invalid, fallback to UTF-16; skip non-text binary
        try:
            return content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return content_bytes.decode("utf-16")
            except UnicodeDecodeError:
                logger.info(
                    "fetch_file_content | unsupported_encoding_or_binary | path=%s", file_path
                )
                return None

    except httpx.HTTPStatusError as e:
        logger.warning(
            "fetch_file_content | http_error | path=%s status=%d",
            file_path, e.response.status_code,
        )
        return None
    except Exception as e:
        logger.warning(
            "fetch_file_content | error | path=%s error=%s", file_path, e
        )
        return None


# ---------------------------------------------------------------------------
# ingest_repository
#
# Main entry point. Orchestrates all stages for a single repository.
#
# FLOW:
#   1. fetch_repo_tree -> full file list with SHAs
#   2. filter_code_files -> code files only
#   3. freshness check -> skip already-embedded files with same SHA
#   4. For each stale file:
#      a. fetch_file_content
#      b. embed_text (embedder.py)
#      c. upsert_code_chunks (qdrant_client.py)
#      d. mark_files_embedded (freshness.py)
#   5. Log summary: total / stale / embedded / skipped
#
# CALLED BY: arq_worker.py after a review completes (background job).
# NOT called from the review pipeline itself — ingestion is async/best-effort.
#
# IDEMPOTENT: Safe to call multiple times for the same repo.
#   Files with unchanged SHAs are skipped. New/changed files are re-embedded.
#   (Batch-Processing-Patterns.md: "Re-runnable batch jobs are a feature.")
# ---------------------------------------------------------------------------
async def ingest_repository(repo_full_name: str) -> dict[str, int]:
    """
    Ingest all code files from a GitHub repository into Qdrant.

    Returns a summary dict:
      total_files    — total code files in repo
      stale_files    — files that needed re-embedding (new or changed)
      embedded       — files successfully embedded
      skipped_fresh  — files skipped because SHA unchanged
      errors         — files that failed to fetch or embed
    """
    cfg = get_settings()

    if not cfg.github_token:
        logger.warning(
            "ingest_repository | no_github_token | repo=%s skipping ingestion",
            repo_full_name,
        )
        return {"total_files": 0, "stale_files": 0, "embedded": 0,
                "skipped_fresh": 0, "errors": 0}

    summary = {
        "total_files": 0,
        "stale_files": 0,
        "embedded": 0,
        "skipped_fresh": 0,
        "errors": 0,
    }

    logger.info("ingest_repository | start | repo=%s", repo_full_name)

    # Use a single httpx.AsyncClient with connection pooling limits for all GitHub requests.
    # (Reuse TCP connections across file fetches — reduces latency.)
    limits = httpx.Limits(max_connections=10, max_keepalive_connections=5, keepalive_expiry=30.0)
    timeout = httpx.Timeout(connect=5.0, read=GITHUB_REQUEST_TIMEOUT, write=5.0, pool=5.0)
    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:

        # Stage 1: fetch the full file tree
        tree = await fetch_repo_tree(repo_full_name, cfg.github_token, client)
        if not tree:
            logger.warning(
                "ingest_repository | empty_tree | repo=%s "
                "(repo may not exist or token has no access)",
                repo_full_name,
            )
            return summary

        # Stage 2: filter to code files only
        code_files = filter_code_files(tree)
        summary["total_files"] = len(code_files)

        if not code_files:
            logger.info(
                "ingest_repository | no_code_files | repo=%s", repo_full_name
            )
            return summary

        # Stage 3: freshness check & removed files cleanup (Gate B - T29)
        # Build {file_path: blob_sha} for all code files
        file_sha_map = {f["path"]: f["sha"] for f in code_files}

        # Get async session factory
        session_factory = get_session_factory()
        try:
            tiger = get_tiger_memory()
        except RuntimeError:
            from backend.memory.tiger_client import TigerMemoryClient
            tiger = TigerMemoryClient(in_memory=True)

        async with session_factory() as session:
            # Clean up files deleted from the repository
            deleted_files = await remove_deleted_files(session, repo_full_name, set(file_sha_map.keys()))
            for del_path in deleted_files:
                await tiger.delete_stale_chunks(repo_full_name, path=del_path)

            stale_files = await get_stale_files(session, repo_full_name, file_sha_map)

        summary["deleted_files"] = len(deleted_files)
        summary["stale_files"] = len(stale_files)
        summary["skipped_fresh"] = len(code_files) - len(stale_files)

        logger.info(
            "ingest_repository | freshness_check | repo=%s "
            "total=%d stale=%d fresh=%d deleted=%d",
            repo_full_name, len(code_files),
            len(stale_files), summary["skipped_fresh"], len(deleted_files),
        )

        if not stale_files:
            logger.info(
                "ingest_repository | all_fresh | repo=%s nothing to embed",
                repo_full_name,
            )
            return summary

        # Stage 4: chunk by AST boundaries, embed and upsert each stale file
        # Bounded processing (Gate B / T17): cap total files and chunks per file
        if len(stale_files) > MAX_INGESTION_FILES:
            logger.warning(
                "ingest_repository | stale_files_capped | total=%d max=%d",
                len(stale_files), MAX_INGESTION_FILES,
            )
            stale_files = dict(list(stale_files.items())[:MAX_INGESTION_FILES])

        for file_path, file_sha in stale_files.items():

            # Stage 4a: fetch raw content
            content = await fetch_file_content(
                repo_full_name, file_path, cfg.github_token, client
            )
            if content is None:
                summary["errors"] += 1
                continue

            # Stage 4b: AST semantic boundary chunking
            chunks_data = chunk_code_by_ast(content, file_path)
            if len(chunks_data) > MAX_CHUNKS_PER_FILE:
                chunks_data = chunks_data[:MAX_CHUNKS_PER_FILE]
            file_chunks: list[CodeChunk] = []
            partial_failure = False

            for idx, item in enumerate(chunks_data):
                chunk_text = getattr(item, "text", item[0])
                symbol = getattr(item, "symbol", item[1])
                line_start = getattr(item, "line_start", item[2] if len(item) > 2 else 1)
                line_end = getattr(item, "line_end", item[3] if len(item) > 3 else len(content.splitlines()))

                try:
                    vector = await embed_text(chunk_text)
                    file_chunks.append(
                        CodeChunk(
                            repo=repo_full_name,
                            path=file_path,
                            content=chunk_text,
                            embedding=vector,
                            chunk_index=idx,
                            symbol=symbol,
                            token_count=len(chunk_text.split()),
                            blob_sha=file_sha,
                            line_start=line_start,
                            line_end=line_end,
                            embedding_version="text-embedding-3-large-256",
                            source_branch="default",
                        )
                    )
                except (EmbeddingError, Exception) as e:
                    logger.warning(
                        "ingest_repository | embed_error | repo=%s path=%s chunk=%d error=%s",
                        repo_full_name, file_path, idx, e,
                    )
                    partial_failure = True
                    break

            # Invariant: Partial embedding failure must never mark a file fresh!
            if partial_failure or not file_chunks or len(file_chunks) < len(chunks_data):
                summary["errors"] += 1
                logger.warning(
                    "ingest_repository | partial_embedding_failure | repo=%s path=%s chunks_succeeded=%d/%d (skipping freshness mark)",
                    repo_full_name, file_path, len(file_chunks), len(chunks_data),
                )
                continue

            # Stage 4c: upsert all chunks into Tiger Cloud (code_chunks table, DiskANN index)
            await upsert_code_chunks(file_chunks)

            # Purge surplus chunks if file shrank (removes old tail chunks)
            try:
                await tiger.delete_surplus_chunks(repo_full_name, file_path, min_index=len(file_chunks))
            except Exception as exc:
                logger.warning(
                    "ingest_repository | delete_surplus_chunks_failed | repo=%s path=%s error=%s",
                    repo_full_name, file_path, exc,
                )

            # Stage 4d: record freshness only after all chunk writes succeed
            async with session_factory() as session:
                await mark_files_embedded(
                    session=session,
                    repo_full_name=repo_full_name,
                    file_path=file_path,
                    file_sha=file_sha,
                    chunk_count=len(file_chunks),
                )

            summary["embedded"] += 1
            logger.debug(
                "ingest_repository | embedded | repo=%s path=%s chunks=%d",
                repo_full_name, file_path, len(file_chunks),
            )

    logger.info(
        "ingest_repository | complete | repo=%s "
        "total=%d stale=%d embedded=%d skipped=%d errors=%d",
        repo_full_name,
        summary["total_files"],
        summary["stale_files"],
        summary["embedded"],
        summary["skipped_fresh"],
        summary["errors"],
    )
    return summary
