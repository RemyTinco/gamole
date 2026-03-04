"""Lightweight score-based reranker with metadata boosting and keyword overlap scoring."""

import re

from gamole_types.schemas.agent import CodeChunk

# Keyword groups that trigger artifact-type boosts
_API_KEYWORDS: frozenset[str] = frozenset({"api", "endpoint", "route", "handler"})
_TEST_KEYWORDS: frozenset[str] = frozenset({"test", "spec", "coverage"})
_MODEL_KEYWORDS: frozenset[str] = frozenset({"model", "schema", "database", "migration"})

# Artifact types that receive a slight penalty unless specifically requested
_PENALIZED_TYPES: frozenset[str] = frozenset({"config", "doc"})


def _tokenize(text: str) -> frozenset[str]:
    """Split text into lowercase tokens, filtering tokens shorter than 3 chars."""
    raw_tokens = re.split(r"[\s\W]+", text.lower())
    return frozenset(t for t in raw_tokens if len(t) >= 3)


def rerank(chunks: list[CodeChunk], query: str, top_k: int | None = None) -> list[CodeChunk]:
    """Rerank code chunks using metadata boosts and keyword overlap.

    Lightweight, deterministic reranker — no LLM calls.
    Starts from the RRF score (chunk.score) or similarity as base.

    Algorithm:
    1. Base score: chunk.score if set, else chunk.similarity.
    2. Multiplicative artifact_type boost based on query keywords.
    3. Additive keyword overlap boost (0.05 per matching query token in chunk_text).
    4. Sort descending by final score.
    5. Optionally trim to top_k.
    6. Return new CodeChunk instances with updated score field.
    """
    query_tokens = _tokenize(query)

    scored: list[tuple[float, CodeChunk]] = []

    for chunk in chunks:
        # 1. Base score
        base = chunk.score if chunk.score is not None else chunk.similarity

        # 2. Artifact-type boost (multiplicative)
        artifact = chunk.artifact_type or ""

        if artifact in _PENALIZED_TYPES:
            multiplier = 0.8
        elif artifact == "api" and (query_tokens & _API_KEYWORDS):
            multiplier = 1.2
        elif artifact == "test" and (query_tokens & _TEST_KEYWORDS):
            multiplier = 1.2
        elif artifact == "model" and (query_tokens & _MODEL_KEYWORDS):
            multiplier = 1.2
        else:
            multiplier = 1.0

        boosted = base * multiplier

        # 3. Keyword overlap boost (additive)
        chunk_text_lower = chunk.chunk_text.lower()
        overlap_count = sum(1 for t in query_tokens if t in chunk_text_lower)
        final_score = boosted + 0.05 * overlap_count

        scored.append((final_score, chunk))

    # 4. Sort by final score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # 5 & 6. Build result with updated score field, apply top_k
    result = [chunk.model_copy(update={"score": score}) for score, chunk in scored]

    if top_k is not None:
        result = result[:top_k]

    return result
