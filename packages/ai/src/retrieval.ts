import { cosineDistance, desc, sql, eq } from 'drizzle-orm'
import { embedText } from './embeddings'
import type { ContextBundle, LinearArtifact, CodeChunk } from '@gamole/types'

const EMPTY_BUNDLE: ContextBundle = {
  linearArtifacts: [],
  codeChunks: [],
  keyFacts: [],
  gaps: [],
}

export interface RetrieveContextOptions {
  topK?: number
  teamId?: string
}

/**
 * Retrieve a ContextBundle from the vector store using cosine similarity search.
 *
 * Embeds `query`, then queries `linear_issues_cache` and `codebase_chunks`
 * for the top-K most similar rows using pgvector cosine distance (G10: no re-ranking).
 *
 * Returns an empty bundle if the DB is unavailable or any query fails.
 */
export async function retrieveContext(
  query: string,
  options: RetrieveContextOptions = {},
): Promise<ContextBundle> {
  const { topK = 5, teamId } = options

  // Embed the query — fall back to empty bundle on embedding failure
  const queryEmbedding = await embedText(query).catch((err: unknown) => {
    console.error('retrieveContext: embedText failed', err)
    return null
  })

  if (queryEmbedding === null) {
    return EMPTY_BUNDLE
  }

  // Dynamic import handles missing DATABASE_URL gracefully — db/index.ts throws
  // synchronously at module evaluation time if DATABASE_URL is unset, so the
  // dynamic import rejects and we catch it here.
  let dbModule: typeof import('@gamole/db')
  try {
    dbModule = await import('@gamole/db')
  } catch (err) {
    console.warn('retrieveContext: DB unavailable, returning empty bundle', err)
    return EMPTY_BUNDLE
  }

  const { db, linearIssuesCache, codebaseChunks } = dbModule

  // --- Linear issues similarity search ---
  let linearArtifacts: LinearArtifact[] = []
  try {
    const issueSimilarity = sql<number>`1 - ${cosineDistance(linearIssuesCache.embedding, queryEmbedding)}`

    const issueRows = await db
      .select({
        linearId: linearIssuesCache.linearId,
        title: linearIssuesCache.title,
        description: linearIssuesCache.description,
        teamId: linearIssuesCache.teamId,
        similarity: issueSimilarity,
      })
      .from(linearIssuesCache)
      .where(teamId ? eq(linearIssuesCache.teamId, teamId) : undefined)
      .orderBy(desc(issueSimilarity))
      .limit(topK)

    linearArtifacts = issueRows.map((row) => ({
      linearId: row.linearId,
      title: row.title,
      description: row.description ?? undefined,
      teamId: row.teamId,
      similarity: row.similarity ?? 0,
    }))
  } catch (err) {
    console.warn('retrieveContext: linear issues query failed', err)
  }

  // --- Codebase chunks similarity search ---
  let codeChunks: CodeChunk[] = []
  try {
    const chunkSimilarity = sql<number>`1 - ${cosineDistance(codebaseChunks.embedding, queryEmbedding)}`

    const chunkRows = await db
      .select({
        filePath: codebaseChunks.filePath,
        repoName: codebaseChunks.repoName,
        language: codebaseChunks.language,
        chunkText: codebaseChunks.chunkText,
        domain: codebaseChunks.domain,
        artifactType: codebaseChunks.artifactType,
        similarity: chunkSimilarity,
      })
      .from(codebaseChunks)
      .orderBy(desc(chunkSimilarity))
      .limit(topK)

    codeChunks = chunkRows.map((row) => ({
      filePath: row.filePath,
      repoName: row.repoName,
      language: row.language ?? '',
      chunkText: row.chunkText,
      domain: row.domain ?? undefined,
      artifactType: row.artifactType ?? undefined,
      similarity: row.similarity ?? 0,
    }))
  } catch (err) {
    console.warn('retrieveContext: codebase chunks query failed', err)
  }

  return {
    linearArtifacts,
    codeChunks,
    keyFacts: [],
    gaps: [],
  }
}
