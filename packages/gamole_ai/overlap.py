"""Overlap detection - ported from packages/ai/src/overlap.ts."""

import logging
from dataclasses import dataclass, field

from .embeddings import embed_batch

logger = logging.getLogger(__name__)


@dataclass
class OverlapMatch:
    linear_id: str
    title: str
    similarity: float


@dataclass
class OverlapResult:
    story_index: int
    story_title: str
    overlaps: list[OverlapMatch] = field(default_factory=list)


async def detect_overlaps(
    stories: list[dict],
    threshold: float = 0.85,
    top_k: int = 3,
    team_id: str | None = None,
) -> list[OverlapResult]:
    """Detect overlapping/duplicate Linear issues for generated stories.

    G10: Simple cosine similarity only — no re-ranking.
    """
    if not stories:
        return []

    texts = [f"{s['title']} {s['description']}" for s in stories]
    embeddings = await embed_batch(texts)

    results: list[OverlapResult] = []

    try:
        from sqlalchemy import select, text

        from gamole_db import LinearIssueCache, get_session

        async for session in get_session():
            for i, story in enumerate(stories):
                embedding = embeddings[i] if i < len(embeddings) else None
                if not embedding:
                    continue

                embedding_literal = str(embedding)
                similarity_sql = f"1.0 - (embedding <=> '{embedding_literal}'::vector)"

                stmt = (
                    select(
                        LinearIssueCache.linear_id,
                        LinearIssueCache.title,
                        text(f"{similarity_sql} as similarity"),
                    )
                    .where(text(f"{similarity_sql} >= {threshold}"))
                    .order_by(text(f"embedding <=> '{embedding_literal}'::vector"))
                    .limit(top_k)
                )

                if team_id:
                    stmt = stmt.where(LinearIssueCache.team_id == team_id)

                result = await session.execute(stmt)
                matches = [
                    OverlapMatch(
                        linear_id=row.linear_id,
                        title=row.title,
                        similarity=row.similarity or 0,
                    )
                    for row in result
                ]

                results.append(OverlapResult(
                    story_index=i,
                    story_title=story.get("title", ""),
                    overlaps=matches,
                ))

    except Exception:
        logger.warning("detect_overlaps: DB unavailable, returning empty overlaps")
        return [
            OverlapResult(story_index=i, story_title=s.get("title", ""), overlaps=[])
            for i, s in enumerate(stories)
        ]

    return results
