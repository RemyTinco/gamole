import logging
from typing import Any

from pydantic import BaseModel
from sqlalchemy import text

from gamole_types.schemas.agent import CodeChunk, ContextBundle, LinearArtifact, RepositorySummary

from .embeddings import embed_query

logger = logging.getLogger(__name__)

EMPTY_BUNDLE = ContextBundle(
    linearArtifacts=[],
    codeChunks=[],
    keyFacts=[],
    gaps=[],
)


class RetrieveContextOptions(BaseModel):
    top_k: int = 5
    min_similarity: float = 0.30
    use_hybrid: bool = True
    team_id: str | None = None
    repo_names: list[str] | None = None


async def retrieve_context(
    query: str,
    options: RetrieveContextOptions | None = None,
) -> ContextBundle:
    if options is None:
        options = RetrieveContextOptions()
    top_k = max(options.top_k, 1)
    top_k_2x = max(top_k * 2, 1)

    try:
        query_embedding = await embed_query(query)
    except Exception:
        logger.warning("retrieveContext: embedQuery failed", exc_info=True)
        return EMPTY_BUNDLE

    query_vec = str(query_embedding)

    try:
        from sqlalchemy import select

        from gamole_db import get_session
        from gamole_db.models import Repository

        async for session in get_session():
            linear_artifacts: list[LinearArtifact] = []
            try:
                linear_sql = text(
                    """
                    SELECT
                        linear_id,
                        title,
                        description,
                        team_id,
                        1.0 - (embedding <=> (:query_vec)::vector) AS similarity
                    FROM linear_issue_cache
                    WHERE (:team_id IS NULL OR team_id = :team_id)
                    ORDER BY embedding <=> (:query_vec)::vector
                    LIMIT :top_k
                    """
                )
                linear_result = await session.execute(
                    linear_sql,
                    {
                        "query_vec": query_vec,
                        "team_id": options.team_id,
                        "top_k": top_k,
                    },
                )
                for row in linear_result:
                    linear_artifacts.append(
                        LinearArtifact(
                            linearId=row.linear_id,
                            title=row.title,
                            description=row.description,
                            teamId=row.team_id,
                            similarity=float(row.similarity or 0),
                        )
                    )
            except Exception:
                logger.warning("retrieveContext: linear issues query failed", exc_info=True)

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

            code_chunks: list[CodeChunk] = []
            try:
                vector_sql = text(
                    """
                    SELECT
                        id,
                        repo_name,
                        file_path,
                        language,
                        chunk_text,
                        domain,
                        artifact_type,
                        symbol_name,
                        parent_symbol,
                        1.0 - (embedding <=> (:query_vec)::vector) AS similarity
                    FROM codebase_chunks
                    WHERE (:repo_names IS NULL OR repo_name = ANY(:repo_names))
                    ORDER BY embedding <=> (:query_vec)::vector
                    LIMIT :top_k_2x
                    """
                )

                vector_result = await session.execute(
                    vector_sql,
                    {
                        "query_vec": query_vec,
                        "repo_names": options.repo_names,
                        "top_k_2x": top_k_2x,
                    },
                )
                vector_rows = list(vector_result)
                vector_rank = {row.id: idx + 1 for idx, row in enumerate(vector_rows)}
                vector_by_id = {row.id: row for row in vector_rows}

                keyword_rank: dict[str, int] = {}
                if options.use_hybrid:
                    keyword_sql = text(
                        """
                        SELECT
                            id,
                            repo_name,
                            file_path,
                            language,
                            chunk_text,
                            domain,
                            artifact_type,
                            symbol_name,
                            parent_symbol,
                            ts_rank(content_tsv, plainto_tsquery('simple', :query)) AS ts_score
                        FROM codebase_chunks
                        WHERE content_tsv @@ plainto_tsquery('simple', :query)
                          AND (:repo_names IS NULL OR repo_name = ANY(:repo_names))
                        ORDER BY ts_rank(content_tsv, plainto_tsquery('simple', :query)) DESC
                        LIMIT :top_k_2x
                        """
                    )
                    keyword_result = await session.execute(
                        keyword_sql,
                        {
                            "query": query,
                            "repo_names": options.repo_names,
                            "top_k_2x": top_k_2x,
                        },
                    )
                    keyword_rows = list(keyword_result)
                    keyword_rank = {row.id: idx + 1 for idx, row in enumerate(keyword_rows)}

                rrf_k = 60
                fused: list[tuple[float, int, Any]] = []
                for chunk_id, vec_row in vector_by_id.items():
                    similarity = float(vec_row.similarity or 0)
                    if similarity < options.min_similarity:
                        continue

                    rrf_score = 1.0 / (vector_rank[chunk_id] + rrf_k)
                    if chunk_id in keyword_rank:
                        rrf_score += 1.0 / (keyword_rank[chunk_id] + rrf_k)

                    fused.append((rrf_score, vector_rank[chunk_id], vec_row))

                fused.sort(key=lambda item: (-item[0], item[1]))

                for rrf_score, _, row in fused[:top_k]:
                    code_chunks.append(
                        CodeChunk(
                            filePath=row.file_path,
                            repoName=row.repo_name,
                            language=row.language or "unknown",
                            chunkText=row.chunk_text,
                            domain=row.domain,
                            artifactType=row.artifact_type,
                            similarity=float(row.similarity or 0),
                            symbolName=row.symbol_name,
                            parentSymbol=row.parent_symbol,
                            score=rrf_score,
                        )
                    )
            except Exception:
                logger.warning("retrieveContext: codebase chunks query failed", exc_info=True)

            return ContextBundle(
                linearArtifacts=linear_artifacts,
                codeChunks=code_chunks,
                repositories=repo_summaries,
                keyFacts=[],
                gaps=[],
            )
    except Exception:
        logger.warning("retrieveContext: DB unavailable, returning empty bundle", exc_info=True)
        return EMPTY_BUNDLE

    return EMPTY_BUNDLE
