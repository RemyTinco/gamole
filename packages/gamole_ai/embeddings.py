"""Embeddings module - ported from packages/ai/src/embeddings.ts."""

import asyncio
import os

EMBEDDING_DIMENSIONS = 768


def _mock_embedding() -> list[float]:
    return [0.0] * EMBEDDING_DIMENSIONS


async def _with_retry(fn, max_attempts: int = 3, base_delay_ms: int = 2000):
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await fn()
        except Exception as e:
            last_error = e
            if attempt < max_attempts:
                delay = base_delay_ms * (2 ** (attempt - 1)) / 1000.0
                await asyncio.sleep(delay)
    raise last_error


async def embed_text(text: str) -> list[float]:
    """Embed a single text string. Returns a 768-dim vector."""
    if not os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY"):
        return _mock_embedding()

    async def _do():
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            task_type="retrieval_document",
        )
        result = await embeddings.aembed_query(text)
        return result[:EMBEDDING_DIMENSIONS]

    return await _with_retry(_do)


async def embed_query(text: str) -> list[float]:
    """Embed a query string for similarity search. Uses retrieval_query task type.

    Use this at search time (NOT for indexing documents).
    Documents should use embed_text() with retrieval_document task type.
    """
    if not os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY"):
        return _mock_embedding()

    async def _do():
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            task_type="retrieval_query",
        )
        result = await embeddings.aembed_query(text)
        return result[:EMBEDDING_DIMENSIONS]

    return await _with_retry(_do)


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed multiple texts. Returns list of 768-dim vectors."""
    if not os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY"):
        return [_mock_embedding() for _ in texts]

    async def _do():
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            task_type="retrieval_document",
        )
        results = await embeddings.aembed_documents(texts)
        return [r[:EMBEDDING_DIMENSIONS] for r in results]

    return await _with_retry(_do)


def chunk_text(text: str, max_tokens: int = 2048, overlap_tokens: int = 200) -> list[str]:
    """Split text into chunks. 1 token ≈ 4 characters. Splits on paragraph boundaries."""
    approx_chars_per_token = 4
    max_chars = max_tokens * approx_chars_per_token
    overlap_chars = overlap_tokens * approx_chars_per_token

    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    paragraphs = text.split("\n\n")
    current = ""

    for para in paragraphs:
        if len(current + para) > max_chars and current:
            chunks.append(current.strip())
            current = current[-overlap_chars:] + "\n\n" + para
        else:
            current = current + "\n\n" + para if current else para

    if current.strip():
        chunks.append(current.strip())

    return chunks
