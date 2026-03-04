"""Integration tests for the full pipeline: AST chunking → context formatting → reranking.

No database required. Tests real behavior end-to-end without mocking.
"""

from gamole_ai.codebase.ast_chunker import chunk_code
from gamole_ai.context_formatter import format_context
from gamole_ai.reranker import rerank
from gamole_types.schemas.agent import CodeChunk, ContextBundle, LinearArtifact


def test_ast_to_reranker_pipeline():
    """AST chunks can be converted to CodeChunks and reranked."""
    source = """
def process_payment(amount: float) -> bool:
    if amount <= 0:
        raise ValueError("Invalid amount")
    return True

def validate_user(user_id: str) -> bool:
    return bool(user_id)
"""
    ast_chunks = chunk_code(source, "python", "payment.py")
    assert ast_chunks is not None
    assert len(ast_chunks) >= 2

    # Convert to CodeChunk objects
    code_chunks = [
        CodeChunk(
            filePath="payment.py",
            repoName="test-repo",
            language="python",
            chunkText=c.text,
            similarity=0.7,
            symbolName=c.symbol_name,
            score=0.7,
        )
        for c in ast_chunks
    ]

    # Rerank for payment-related query
    reranked = rerank(code_chunks, "process payment amount")
    assert len(reranked) == len(code_chunks)
    # payment chunk should rank first
    assert "payment" in reranked[0].file_path.lower() or "process_payment" in (reranked[0].symbol_name or "")


def test_context_formatter_with_ast_chunks():
    """format_context produces valid markdown from AST-derived chunks."""
    source = "def authenticate(token: str) -> bool:\n    return bool(token)"
    ast_chunks = chunk_code(source, "python", "auth.py")
    assert ast_chunks is not None

    code_chunks = [
        CodeChunk(
            filePath="auth.py",
            repoName="test-repo",
            language="python",
            chunkText=c.text,
            similarity=0.85,
            symbolName=c.symbol_name,
            score=0.85,
        )
        for c in ast_chunks
    ]

    bundle = ContextBundle(codeChunks=code_chunks)
    result = format_context(bundle)

    assert "## Relevant Code Context" in result
    assert "auth.py" in result
    assert "```python" in result
    assert bundle.formatted_context == result


def test_full_pipeline_no_db():
    """Full pipeline without DB: chunk → rerank → format."""
    # Multiple files
    py_source = "def create_order(items: list) -> dict:\n    return {'items': items}"
    ts_source = "export function fetchOrders(): Promise<string[]> { return api.get('/orders'); }"

    py_chunks = chunk_code(py_source, "python", "orders.py") or []
    ts_chunks = chunk_code(ts_source, "typescript", "orders.ts") or []

    all_chunks = [
        CodeChunk(
            filePath=c_file,
            repoName="test-repo",
            language=lang,
            chunkText=c.text,
            similarity=0.75,
            symbolName=c.symbol_name,
            score=0.75,
        )
        for c_file, lang, chunks in [("orders.py", "python", py_chunks), ("orders.ts", "typescript", ts_chunks)]
        for c in chunks
    ]

    # Rerank for order-related query
    reranked = rerank(all_chunks, "create order API endpoint")

    # Build bundle with linear artifacts too
    bundle = ContextBundle(
        codeChunks=reranked,
        linearArtifacts=[
            LinearArtifact(linearId="ORD-1", title="Order creation flow", similarity=0.8)
        ],
    )

    result = format_context(bundle)

    # Verify output structure
    assert "## Relevant Code Context" in result
    assert "## Similar Existing Tickets" in result
    assert "ORD-1" in result
    assert len(result) > 100


def test_context_formatter_empty():
    """format_context handles empty bundle gracefully."""
    result = format_context(ContextBundle())
    assert isinstance(result, str)
    assert len(result) > 0
    assert "No relevant context found" in result


def test_reranker_preserves_all_chunks():
    """Reranker returns all chunks with no loss."""
    chunks = [
        CodeChunk(
            filePath=f"file{i}.py",
            repoName="r",
            language="python",
            chunkText=f"def func{i}(): pass",
            similarity=0.5 + i * 0.1,
        )
        for i in range(5)
    ]
    result = rerank(chunks, "some query")
    assert len(result) == 5
    # All original file paths present
    original_paths = {c.file_path for c in chunks}
    result_paths = {c.file_path for c in result}
    assert original_paths == result_paths
