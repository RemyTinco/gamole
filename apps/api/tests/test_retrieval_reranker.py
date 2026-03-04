"""Tests for retrieval module (RetrieveContextOptions) and reranker (rerank())."""

from gamole_ai.reranker import rerank
from gamole_ai.retrieval import RetrieveContextOptions
from gamole_types.schemas.agent import CodeChunk

# ---------------------------------------------------------------------------
# RetrieveContextOptions
# ---------------------------------------------------------------------------


def test_retrieve_context_options_defaults():
    opts = RetrieveContextOptions()
    assert opts.top_k == 5
    assert opts.min_similarity == 0.30
    assert opts.use_hybrid is True
    assert opts.team_id is None
    assert opts.repo_names is None


def test_retrieve_context_options_custom():
    opts = RetrieveContextOptions(top_k=10, min_similarity=0.5, use_hybrid=False)
    assert opts.top_k == 10
    assert opts.min_similarity == 0.5
    assert opts.use_hybrid is False


# ---------------------------------------------------------------------------
# rerank()
# ---------------------------------------------------------------------------


def test_rerank_api_boost():
    api_chunk = CodeChunk(
        filePath="routes.py",
        repoName="r",
        language="python",
        chunkText="@router.post /api/endpoint",
        similarity=0.7,
        artifactType="api",
        score=0.5,
    )
    src_chunk = CodeChunk(
        filePath="utils.py",
        repoName="r",
        language="python",
        chunkText="def helper function",
        similarity=0.7,
        artifactType="source",
        score=0.5,
    )
    result = rerank([src_chunk, api_chunk], "add new API endpoint")
    assert result[0].file_path == "routes.py"


def test_rerank_config_penalty():
    config_chunk = CodeChunk(
        filePath="config.yaml",
        repoName="r",
        language="yaml",
        chunkText="database: postgres",
        similarity=0.8,
        artifactType="config",
        score=0.8,
    )
    src_chunk = CodeChunk(
        filePath="service.py",
        repoName="r",
        language="python",
        chunkText="def process_data",
        similarity=0.8,
        artifactType="source",
        score=0.8,
    )
    result = rerank([config_chunk, src_chunk], "implement data processing")
    # Source chunk should rank higher than config chunk
    assert result[0].file_path == "service.py"


def test_rerank_keyword_overlap():
    chunk_with_keywords = CodeChunk(
        filePath="payment.py",
        repoName="r",
        language="python",
        chunkText="def process_payment(amount): return charge(amount)",
        similarity=0.6,
        score=0.6,
    )
    chunk_without = CodeChunk(
        filePath="utils.py",
        repoName="r",
        language="python",
        chunkText="def helper(): pass",
        similarity=0.6,
        score=0.6,
    )
    result = rerank([chunk_without, chunk_with_keywords], "process payment amount")
    assert result[0].file_path == "payment.py"


def test_rerank_top_k():
    chunks = [
        CodeChunk(
            filePath=f"file{i}.py",
            repoName="r",
            language="python",
            chunkText=f"def func{i}(): pass",
            similarity=0.5,
            score=0.5,
        )
        for i in range(10)
    ]
    result = rerank(chunks, "some query", top_k=3)
    assert len(result) == 3


def test_rerank_empty():
    result = rerank([], "some query")
    assert result == []


def test_rerank_score_updated():
    chunk = CodeChunk(
        filePath="test.py",
        repoName="r",
        language="python",
        chunkText="def test_api_endpoint(): pass",
        similarity=0.7,
        artifactType="api",
        score=0.5,
    )
    result = rerank([chunk], "add API endpoint")
    # Score should be updated (boosted from 0.5)
    assert result[0].score is not None
    assert result[0].score > 0.5  # boosted


def test_rerank_uses_similarity_when_no_score():
    chunk = CodeChunk(
        filePath="test.py",
        repoName="r",
        language="python",
        chunkText="def foo(): pass",
        similarity=0.8,
    )
    # score is None by default
    result = rerank([chunk], "some query")
    assert result[0].score is not None
    assert result[0].score >= 0.8  # at least similarity value
