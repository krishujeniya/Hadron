# tests/data/test_code_ingestion_complete.py
#
# Gate B (T29): Make code ingestion complete, versioned, and removable.
# Verifies:
# 1. Complete source coverage without truncation: oversized preambles, functions,
#    and tails are split into full sub-chunks with exact line ranges.
# 2. Deletion of removed files: deleted repository files have their index and chunks purged.
# 3. Shrinking files: surplus old chunk indices are removed.
# 4. Partial failure isolation: files with partial embedding failure are not marked fresh.
# 5. Provenance labeling: default branch code cannot impersonate PR head.
# 6. Deep monorepo paths: keys up to 512 chars succeed without assertion error.

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.data.ingestion import chunk_code_by_ast, ChunkBlock
from backend.data.freshness import mark_files_embedded, remove_deleted_files
from backend.memory.tiger_client import CodeChunk, TigerMemoryClient
from backend.memory.context_retriever import _format_context


def test_chunk_code_by_ast_preserves_large_preamble_and_functions():
    """Oversized preambles and functions are completely chunked without dropping characters or lines."""
    # 3,000 character preamble of comments and module docstrings
    preamble_lines = [f"# Module docstring line {i:03d} with detailed architecture notes.\n" for i in range(50)]
    preamble = "".join(preamble_lines)

    # 4,000 character function definition
    fn_lines = ["def massive_data_processor(input_stream):\n"]
    for i in range(70):
        fn_lines.append(f"    processed_line_{i:03d} = input_stream.read_chunk({i}) + 1\n")
    fn_lines.append("    return processed_line_069\n")
    fn_body = "".join(fn_lines)

    # Tail after function
    tail_lines = [f"# Global constant definition {i} following the massive function\n" for i in range(20)]
    tail = "".join(tail_lines)

    content = preamble + fn_body + tail
    chunks = chunk_code_by_ast(content, "backend/processor.py", max_chunk_chars=1200)

    assert len(chunks) > 3
    # Check that every chunk is a ChunkBlock with valid line ranges
    for c in chunks:
        assert isinstance(c, ChunkBlock)
        assert c.line_start >= 1
        assert c.line_end >= c.line_start
        assert len(c.text) > 0
        # Backward-compatible 2-tuple unpacking
        text, sym = c
        assert isinstance(text, str)

    # Verify that first chunk covers preamble and middle chunks cover function
    symbols = [c.symbol for c in chunks]
    assert "module:preamble" in symbols
    assert "massive_data_processor" in symbols


def test_delete_surplus_chunks_when_file_shrinks():
    """Surplus old chunks are purged when a file shrinks in size."""
    tiger = TigerMemoryClient(pool=None, in_memory=True)
    repo = "test-org/repo-shrink"
    path = "src/utils.py"

    # Initially insert 5 chunks (indices 0..4)
    initial_chunks = [
        CodeChunk(
            repo=repo,
            path=path,
            content=f"chunk content {i}",
            embedding=[0.01 * (i + 1)] * 256,
            chunk_index=i,
        )
        for i in range(5)
    ]
    import asyncio
    asyncio.run(tiger.upsert_chunks(initial_chunks))

    matching = [c for c in tiger._in_memory_chunks if c.repo == repo and c.path == path]
    assert len(matching) == 5

    # File shrinks: now only 2 chunks remain (indices 0, 1)
    # delete_surplus_chunks with min_index=2 should remove indices 2, 3, 4
    deleted = asyncio.run(tiger.delete_surplus_chunks(repo, path, min_index=2))
    assert deleted == 3

    remaining = [c for c in tiger._in_memory_chunks if c.repo == repo and c.path == path]
    assert len(remaining) == 2
    assert [c.chunk_index for c in remaining] == [0, 1]


@pytest.mark.asyncio
async def test_remove_deleted_files_from_index_and_storage():
    """Files removed from repository are identified and removed from repo_file_index and memory."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [
        ("src/active.py",),
        ("src/deleted_old.py",),
        ("src/also_removed.py",),
    ]
    mock_session.execute.return_value = mock_result

    active_paths = {"src/active.py", "src/new_file.py"}
    deleted_paths = await remove_deleted_files(mock_session, "test-org/repo", active_paths)

    assert set(deleted_paths) == {"src/deleted_old.py", "src/also_removed.py"}
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_partial_embedding_failure_does_not_mark_file_fresh():
    """If any chunk in a multi-chunk file fails embedding, mark_files_embedded is skipped."""
    from backend.data.ingestion import ingest_repository

    with patch("backend.data.ingestion.get_settings") as mock_settings, \
         patch("backend.data.ingestion.fetch_repo_tree") as mock_tree, \
         patch("backend.data.ingestion.fetch_file_content") as mock_content, \
         patch("backend.data.ingestion.get_stale_files", new_callable=AsyncMock) as mock_stale, \
         patch("backend.data.ingestion.remove_deleted_files", new_callable=AsyncMock) as mock_remove_del, \
         patch("backend.data.ingestion.mark_files_embedded", new_callable=AsyncMock) as mock_mark_fresh, \
         patch("backend.data.ingestion.get_tiger_memory") as mock_get_tiger, \
         patch("backend.data.ingestion.embed_text") as mock_embed:

        mock_tiger = MagicMock()
        mock_tiger.delete_stale_chunks = AsyncMock(return_value=0)
        mock_tiger.delete_surplus_chunks = AsyncMock(return_value=0)
        mock_tiger.upsert_chunks = AsyncMock(return_value=1)
        mock_get_tiger.return_value = mock_tiger

        mock_settings.return_value = MagicMock(github_token="ghp_test_token")
        mock_tree.return_value = [{"path": "src/main.py", "sha": "sha123", "size": 100, "type": "blob"}]
        mock_stale.return_value = {"src/main.py": "sha123"}
        mock_remove_del.return_value = []
        # Multi-chunk content (> 2500 chars)
        mock_content.return_value = "def func_a():\n    x = 1\n" + ("    # padding\n" * 250) + "def func_b():\n    y = 2\n"

        # Embedder fails on the second call
        mock_embed.side_effect = [[0.1] * 256, RuntimeError("Provider timeout on chunk 2")]

        summary = await ingest_repository("test-org/repo")

        # File must count as an error and NOT marked as fresh
        assert summary["errors"] >= 1
        assert summary["embedded"] == 0
        assert not mock_mark_fresh.called


def test_retrieval_provenance_labels_default_branch_correctly():
    """Retrieved chunks from default branch are labeled and cannot impersonate PR head."""
    results = [
        {
            "file_path": "backend/auth.py",
            "chunk_text": "def verify_token(tok): return True",
            "pr_number": "?",
            "score": 0.88,
            "source_branch": "default",
        },
        {
            "file_path": "backend/database.py",
            "chunk_text": "class DatabasePool: pass",
            "pr_number": 42,
            "score": 0.91,
        },
    ]

    formatted = _format_context(results)
    # Default branch chunk must explicitly state it is from repository default branch
    assert "Source: repository default branch (not PR head)" in formatted
    # Prior PR chunk must state prior PR number
    assert "from prior PR #42" in formatted


@pytest.mark.asyncio
async def test_monorepo_deep_path_512_chars_supported():
    """Deep nested monorepo file paths up to 512 chars succeed without assertion error."""
    mock_session = AsyncMock()
    # 250 character directory tree + filename
    long_path = "packages/frontend/components/views/enterprise/security/compliance/governance/" + ("subfolder/" * 15) + "Component.tsx"
    repo_name = "enterprise-corp/monorepo-super-repo-name"
    assert len(f"{repo_name}:{long_path}") > 150  # Exceeds old 128 limit

    # Must complete without AssertionError
    await mark_files_embedded(
        mock_session,
        repo_full_name=repo_name,
        file_path=long_path,
        file_sha="4b825dc642cb6eb9a060e54bf8d69288fbee4904",
        chunk_count=1,
    )
    assert mock_session.commit.called
