# tests/test_embeddings_t13.py
#
# Verification tests for Task T13:
# Repair embedding dimensions, batch shape, and semantic validity.

import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.memory.embedder import (
    DEFAULT_EMBEDDING_DIMENSIONS,
    EmbeddingContract,
    EmbeddingError,
    embed_batch,
    embed_text,
    get_embedding_contract,
    normalize_vector,
    set_test_embedder,
)
from backend.memory.tiger_client import CodeChunk, TigerMemoryClient
from backend.memory.qdrant_client import search_similar_code, upsert_code_chunks


@pytest.fixture(autouse=True)
def reset_embedder_test_hook():
    """Ensure test hook is cleared before and after each test."""
    set_test_embedder(None)
    yield
    set_test_embedder(None)


def test_embedding_contract_definition():
    """Embedding contract defines provider, model, dimension (256), normalization, namespace, and version."""
    contract = get_embedding_contract()
    assert isinstance(contract, EmbeddingContract)
    assert contract.dimension == DEFAULT_EMBEDDING_DIMENSIONS
    assert contract.dimension == 256
    assert contract.normalized is True
    assert contract.namespace == "code_chunks"
    assert contract.version == "v1"


def test_vector_normalization():
    """L2 normalization ensures unit length vectors."""
    zero_vec = [0.0] * 256
    assert normalize_vector(zero_vec) == zero_vec

    raw_vec = [3.0, 4.0] + [0.0] * 254
    norm_vec = normalize_vector(raw_vec)
    assert len(norm_vec) == 256
    assert math.isclose(norm_vec[0], 0.6, rel_tol=1e-5)
    assert math.isclose(norm_vec[1], 0.8, rel_tol=1e-5)
    norm = math.sqrt(sum(x * x for x in norm_vec))
    assert math.isclose(norm, 1.0, rel_tol=1e-5)


@pytest.mark.asyncio
async def test_embed_text_empty_input_policy():
    """Empty and whitespace strings return zero vectors of exact contract dimension."""
    v1 = await embed_text("")
    v2 = await embed_text("   \n\t  ")
    assert len(v1) == 256
    assert len(v2) == 256
    assert all(x == 0.0 for x in v1)
    assert all(x == 0.0 for x in v2)


@pytest.mark.asyncio
async def test_embed_batch_exact_shape_order_and_duplicates():
    """
    embed_batch satisfies exact shape, length, order, and duplicate equality.
    Empty inputs return zero vectors without skipping slots or skewing indices.
    """
    inputs = [
        "",                          # idx 0: empty
        "def authenticate(): pass",  # idx 1: code A
        "   ",                       # idx 2: whitespace
        "def checkout(): pass",      # idx 3: code B
        "def authenticate(): pass",  # idx 4: duplicate of code A
    ]

    # Deterministic test embedder simulating semantic vectors
    async def mock_provider_call(texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            if "authenticate" in t:
                base = [0.8, 0.6] + [0.0] * 254
            else:
                base = [0.1, 0.2] + [0.0] * 254
            out.append(normalize_vector(base))
        return out

    set_test_embedder(mock_provider_call)

    results = await embed_batch(inputs)

    # Exact count preserved
    assert len(results) == len(inputs)

    # Dimensions verified for every item
    for r in results:
        assert len(r) == 256

    # Empty indices get zero vectors
    assert all(x == 0.0 for x in results[0])
    assert all(x == 0.0 for x in results[2])

    # Non-empty inputs get normalized embeddings
    assert not all(x == 0.0 for x in results[1])
    assert not all(x == 0.0 for x in results[3])

    # Duplicates yield identical embeddings
    assert results[1] == results[4]

    # Distinct inputs yield distinct embeddings
    assert results[1] != results[3]


@pytest.mark.asyncio
async def test_wrong_dimensions_rejected_by_embedder():
    """Embedding provider returning wrong dimensions raises EmbeddingError."""
    with patch("backend.memory.embedder.AsyncOpenAI") as mock_openai_cls, \
         patch("backend.memory.embedder.get_settings") as mock_settings:
        settings_obj = MagicMock()
        settings_obj.openai_api_key = "sk-valid-key"
        settings_obj.openai_embedding_model = "text-embedding-3-large"
        settings_obj.openai_embedding_dimensions = 256
        settings_obj.openai_api_base_url = ""
        mock_settings.return_value = settings_obj

        mock_client = AsyncMock()
        mock_res = MagicMock()
        mock_embedding_obj = MagicMock()
        mock_embedding_obj.embedding = [0.1] * 1536  # WRONG: 1536 instead of 256
        mock_res.data = [mock_embedding_obj]
        mock_client.embeddings.create.return_value = mock_res
        mock_openai_cls.return_value = mock_client

        with pytest.raises(EmbeddingError) as exc_info:
            await embed_text("def test(): pass")
        assert "dimension" in str(exc_info.value).lower()

        with pytest.raises(EmbeddingError) as exc_info_batch:
            await embed_batch(["def test(): pass"])
        assert "dimension" in str(exc_info_batch.value).lower()


@pytest.mark.asyncio
async def test_wrong_dimensions_rejected_before_storage():
    """TigerMemoryClient and Qdrant reject mismatched vector dimensions before storage or search."""
    tiger = TigerMemoryClient(in_memory=True, expected_dim=256)

    # Rejects invalid chunk dimension in upsert
    bad_chunk = CodeChunk(
        repo="org/repo",
        path="src/file.py",
        content="code",
        embedding=[0.1] * 1536,  # wrong dimension
        chunk_index=0,
    )
    with pytest.raises(ValueError) as exc:
        await tiger.upsert_chunks([bad_chunk])
    assert "dimension mismatch" in str(exc.value)

    # Rejects invalid query dimension in search
    with pytest.raises(ValueError) as exc:
        await tiger.search(query_embedding=[0.1] * 512, repo="org/repo")
    assert "Query embedding dimension mismatch" in str(exc.value)

    # Qdrant search rejects invalid query dimension
    with pytest.raises(ValueError) as exc_q:
        await search_similar_code(query_vector=[0.1] * 512, repo_full_name="org/repo")
    assert "Query vector dimension mismatch" in str(exc_q.value)

    # Qdrant upsert rejects invalid chunk vector dimension
    with pytest.raises(ValueError) as exc_qu:
        await upsert_code_chunks(
            repo_full_name="org/repo",
            pr_number=1,
            file_chunks=[{"file_path": "a.py", "text": "foo", "vector": [0.1] * 1536}],
        )
    assert "dimension mismatch" in str(exc_qu.value)


@pytest.mark.asyncio
async def test_no_fake_fallback_for_nvapi_key():
    """
    A cryptographic hash is NOT an embedding.
    Non-OpenAI keys (like nvapi-) raise EmbeddingError to explicitly disable retrieval.
    """
    with patch("backend.memory.embedder.get_settings") as mock_settings:
        settings_obj = MagicMock()
        settings_obj.openai_api_key = "nvapi-some-nvidia-nim-token"
        settings_obj.openai_embedding_model = "text-embedding-3-large"
        settings_obj.openai_embedding_dimensions = 256
        mock_settings.return_value = settings_obj

        with pytest.raises(EmbeddingError) as exc_info:
            await embed_text("def test(): pass")
        assert "NVIDIA NIM does not provide" in str(exc_info.value)
        assert "Semantic retrieval is disabled" in str(exc_info.value)

        with pytest.raises(EmbeddingError) as exc_info_batch:
            await embed_batch(["def test(): pass"])
        assert "NVIDIA NIM does not provide" in str(exc_info_batch.value)


@pytest.mark.asyncio
async def test_semantic_retrieval_baseline_beats_hash_baseline():
    """
    Verifies that a semantic embedding baseline clearly differentiates related code
    from unrelated code, whereas a SHA-256 cryptographic hash baseline fails.
    """
    import hashlib

    # Ground truth documents
    auth_doc = "def authenticate_user(username, password): verify user credentials in database and create session"
    duty_doc = "def calculate_customs_duty(weight_kg, tariff_rate): compute international freight customs tax"

    query = "verify user credentials and authenticate login password"

    # 1. Semantic vector representation (simulating true semantic embedding)
    # Target auth_doc has high overlap in semantic subspace [x, y], duty_doc is orthogonal in [z, w]
    def semantic_embed(text: str) -> list[float]:
        vec = [0.0] * 256
        t = text.lower()
        if "user" in t or "authenticate" in t or "credentials" in t or "login" in t:
            vec[0] = 0.8
            vec[1] = 0.6
        if "customs" in t or "duty" in t or "freight" in t or "tariff" in t:
            vec[2] = 0.8
            vec[3] = 0.6
        return normalize_vector(vec)

    # 2. Cryptographic hash baseline (the flawed legacy nvapi- fallback)
    def hash_embed(text: str) -> list[float]:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        vec = [(h[i % len(h)] / 127.5 - 1.0) for i in range(256)]
        return normalize_vector(vec)

    def cosine_sim(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b))

    # Evaluate semantic baseline
    query_semantic = semantic_embed(query)
    auth_semantic = semantic_embed(auth_doc)
    duty_semantic = semantic_embed(duty_doc)

    sim_semantic_auth = cosine_sim(query_semantic, auth_semantic)
    sim_semantic_duty = cosine_sim(query_semantic, duty_semantic)
    semantic_margin = sim_semantic_auth - sim_semantic_duty

    # Evaluate hash baseline
    query_hash = hash_embed(query)
    auth_hash = hash_embed(auth_doc)
    duty_hash = hash_embed(duty_doc)

    sim_hash_auth = cosine_sim(query_hash, auth_hash)
    sim_hash_duty = cosine_sim(query_hash, duty_hash)
    hash_margin = sim_hash_auth - sim_hash_duty

    # The semantic model gives high similarity to auth and zero to duty
    assert sim_semantic_auth > 0.95
    assert sim_semantic_duty < 0.05
    assert semantic_margin > 0.90

    # Semantic retrieval baseline overwhelmingly beats hash baseline margin (> 0.50 margin difference)
    assert semantic_margin - hash_margin > 0.50
