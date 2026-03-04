"""Context formatter — converts a ContextBundle into structured markdown for agent prompt injection."""

from gamole_types.schemas.agent import CodeChunk, ContextBundle

_MIN_SIMILARITY = 0.30
_TRUNCATE_LINES = 500
_KEEP_HEAD = 50
_KEEP_TAIL = 10


def _sort_key(chunk: CodeChunk) -> float:
    """Return sort key: score takes priority over similarity."""
    return chunk.score if chunk.score is not None else chunk.similarity


def _format_chunk(chunk: CodeChunk) -> str:
    """Format a single code chunk as a markdown section."""
    if chunk.parent_symbol and chunk.symbol_name:
        symbol_part = f" > {chunk.parent_symbol}.{chunk.symbol_name}"
    elif chunk.symbol_name:
        symbol_part = f" > {chunk.symbol_name}"
    else:
        symbol_part = ""

    header = f"### {chunk.file_path}{symbol_part} (similarity: {chunk.similarity:.2f})"

    lines = chunk.chunk_text.splitlines()
    if len(lines) > _TRUNCATE_LINES:
        kept = lines[:_KEEP_HEAD] + ["... [truncated] ..."] + lines[-_KEEP_TAIL:]
        text = "\n".join(kept)
    else:
        text = chunk.chunk_text

    return f"{header}\n```{chunk.language}\n{text}\n```"


def format_context(bundle: ContextBundle) -> str:
    """Convert a ContextBundle into structured markdown for agent prompt injection.

    Sets bundle.formatted_context and returns the formatted string.
    """
    sections: list[str] = []

    # --- Code chunks ---
    eligible_chunks = [c for c in bundle.code_chunks if c.similarity >= _MIN_SIMILARITY]
    sorted_chunks = sorted(eligible_chunks, key=_sort_key, reverse=True)
    if sorted_chunks:
        chunk_parts = [_format_chunk(c) for c in sorted_chunks]
        sections.append("## Relevant Code Context\n\n" + "\n\n".join(chunk_parts))

    # --- Linear artifacts ---
    eligible_artifacts = [a for a in bundle.linear_artifacts if a.similarity >= _MIN_SIMILARITY]
    if eligible_artifacts:
        lines = [
            f'{i + 1}. **{a.linear_id}**: "{a.title}" (similarity: {a.similarity:.2f})'
            for i, a in enumerate(eligible_artifacts)
        ]
        sections.append("## Similar Existing Tickets\n\n" + "\n".join(lines))

    # --- Repositories ---
    if bundle.repositories:
        repo_lines = [
            f"- **{r.name}**: {r.description} [{', '.join(r.languages)}]"
            for r in bundle.repositories
        ]
        sections.append("## Repository Context\n\n" + "\n".join(repo_lines))

    if not sections:
        result = "No relevant context found."
    else:
        result = "\n\n".join(sections)

    bundle.formatted_context = result
    return result
