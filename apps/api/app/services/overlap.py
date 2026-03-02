"""Overlap detection service."""

from gamole_ai.overlap import OverlapResult, detect_overlaps


async def check_overlaps(
    stories: list[dict],
    threshold: float = 0.85,
    top_k: int = 3,
    team_id: str | None = None,
) -> list[OverlapResult]:
    """Check for overlapping Linear issues."""
    return await detect_overlaps(stories, threshold=threshold, top_k=top_k, team_id=team_id)
