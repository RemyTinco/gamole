"""Retrieval module - ported from packages/ai/src/retrieval.ts.

Simple top-K cosine similarity search (G10: no re-ranking).
"""

import logging
from dataclasses import dataclass

from gamole_types.schemas.agent import CodeChunk, ContextBundle, LinearArtifact, RepositorySummary

from .embeddings import embed_text

logger = logging.getLogger(__name__)

EMPTY_BUNDLE = ContextBundle(
    linear_artifacts=[],
    code_chunks=[],
    key_facts=[],
    gaps=[],
)


@dataclass
class RepoSummary:
    name: str
    description: str
    languages: list[str]


@dataclass
class RetrieveContextOptions:
    top_k: int = 5
    team_id: str | None = None
    repo_names: list[str] | None = None


async def retrieve_context(
    query: str,
    options: RetrieveContextOptions | None = None,
) -> ContextBundle:
    """Retrieve a ContextBundle from the vector store using cosine similarity search."""
    if options is None:
        options = RetrieveContextOptions()

    try:
        query_embedding = await embed_text(query)
    except Exception:
        logger.warning("retrieveContext: embedText failed", exc_info=True)
        return EMPTY_BUNDLE

    try:
        from sqlalchemy import literal_column, select, text

        from gamole_db import CodebaseChunk, LinearIssueCache, get_session
        from gamole_db.models import Repository

        async for session in get_session():
            # --- Linear issues similarity search ---
            linear_artifacts: list[LinearArtifact] = []
            try:
                embedding_literal = str(query_embedding)
                similarity_expr = literal_column(
                    f"1.0 - (embedding <=> '{embedding_literal}'::vector)"
                ).label("similarity")
                stmt = (
                    select(
                        LinearIssueCache.linear_id,
                        LinearIssueCache.title,
                        LinearIssueCache.description,
                        LinearIssueCache.team_id,
                        similarity_expr,
                    )
                    .order_by(text(f"embedding <=> '{embedding_literal}'::vector"))
                    .limit(options.top_k)
                )
                if options.team_id:
                    stmt = stmt.where(LinearIssueCache.team_id == options.team_id)

                result = await session.execute(stmt)
                for row in result:
                    linear_artifacts.append(
                        LinearArtifact(
                            linearId=row.linear_id,
                            title=row.title,
                            description=row.description,
                            teamId=row.team_id,
                            similarity=row.similarity or 0,
                        )
                    )
            except Exception:
                logger.warning("retrieveContext: linear issues query failed", exc_info=True)

            # --- Repository summaries ---
            repo_summaries: list[RepositorySummary] = []
            try:
                repo_result = await session.execute(select(Repository))
                for repo in repo_result.scalars():
                    repo_summaries.append(
                        RepositorySummary(
                            name=repo.name,
                            description=repo.description,
                            languages=repo.languages or [],
                        )
                    )
            except Exception:
                logger.warning("retrieveContext: repository query failed", exc_info=True)

            # --- Codebase chunks similarity search ---
            code_chunks: list[CodeChunk] = []
            try:
                stmt2 = (
                    select(
                        CodebaseChunk.file_path,
                        CodebaseChunk.repo_name,
                        CodebaseChunk.language,
                        CodebaseChunk.chunk_text,
                        CodebaseChunk.domain,
                        CodebaseChunk.artifact_type,
                        similarity_expr,
                    )
                    .order_by(text(f"embedding <=> '{embedding_literal}'::vector"))
                    .limit(options.top_k)
                )
                if options.repo_names:
                    stmt2 = stmt2.where(CodebaseChunk.repo_name.in_(options.repo_names))
                result2 = await session.execute(stmt2)
                for row in result2:
                    code_chunks.append(
                        CodeChunk(
                            filePath=row.file_path,
                            repoName=row.repo_name,
                            language=row.language or "",
                            chunkText=row.chunk_text,
                            domain=row.domain,
                            artifactType=row.artifact_type,
                            similarity=row.similarity or 0,
                        )
                    )
            except Exception:
                logger.warning("retrieveContext: codebase chunks query failed", exc_info=True)

            return ContextBundle(
                linear_artifacts=linear_artifacts,
                code_chunks=code_chunks,
                repositories=repo_summaries,
                key_facts=[],
                gaps=[],
            )
    except Exception:
        logger.warning("retrieveContext: DB unavailable, returning empty bundle", exc_info=True)
        return EMPTY_BUNDLE

    return EMPTY_BUNDLE
