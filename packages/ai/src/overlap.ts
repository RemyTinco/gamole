import { cosineDistance, desc, sql, eq, and } from 'drizzle-orm'
import { embedBatch } from './embeddings'

export interface OverlapResult {
  storyIndex: number
  storyTitle: string
  overlaps: Array<{ linearId: string; title: string; similarity: number }>
}

/**
 * Detect overlapping/duplicate Linear issues for a set of generated stories.
 *
 * For each story, embeds `title + " " + description` and queries the
 * `linear_issues_cache` for the top-K most similar existing issues using
 * cosine similarity. Results above `threshold` are considered potential
 * duplicates.
 *
 * Returns an empty overlaps array for each story if the DB is unavailable.
 * G10: Simple cosine similarity only — no re-ranking.
 *
 * @param stories - Array of stories with title and description
 * @param options - Optional configuration
 * @param options.threshold - Similarity threshold (default: 0.85)
 * @param options.topK - Max similar issues per story (default: 3)
 * @param options.teamId - Filter by Linear team ID
 */
export async function detectOverlaps(
  stories: Array<{ title: string; description: string }>,
  options: { threshold?: number; topK?: number; teamId?: string } = {},
): Promise<OverlapResult[]> {
  const { threshold = 0.85, topK = 3, teamId } = options

  if (!stories.length) return []

  // Embed all stories in batch
  const texts = stories.map((s) => `${s.title} ${s.description}`)
  const embeddings = await embedBatch(texts)

  const results: OverlapResult[] = []

  try {
    const { db, linearIssuesCache } = await import('@gamole/db')

    for (let i = 0; i < stories.length; i++) {
      const embedding = embeddings[i]
      if (!embedding) continue

      const similarity = sql<number>`1 - ${cosineDistance(linearIssuesCache.embedding, embedding)}`

      const conditions = teamId
        ? and(eq(linearIssuesCache.teamId, teamId), sql`${similarity} >= ${threshold}`)
        : sql`${similarity} >= ${threshold}`

      const matches = await db
        .select({
          linearId: linearIssuesCache.linearId,
          title: linearIssuesCache.title,
          similarity,
        })
        .from(linearIssuesCache)
        .where(conditions)
        .orderBy(desc(similarity))
        .limit(topK)

      results.push({
        storyIndex: i,
        storyTitle: stories[i]?.title ?? '',
        overlaps: matches.map((m) => ({
          linearId: m.linearId,
          title: m.title,
          similarity: m.similarity ?? 0,
        })),
      })
    }
  } catch {
    // DB unavailable — return empty overlaps for all stories
    return stories.map((s, i) => ({ storyIndex: i, storyTitle: s.title, overlaps: [] }))
  }

  return results
}
