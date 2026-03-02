/**
 * @gamole/linear — Linear Issues Sync
 *
 * Fetches all issues from Linear, embeds them via Google text-embedding-004,
 * and upserts into the linear_issues_cache table for semantic search.
 *
 * RULES:
 * - G9: One-way pull only — NO webhooks, NO push-back
 * - G17: NO bidirectional sync
 * - Tokens used in-memory only, never stored in DB
 */

import { LinearClient } from './client'
import { embedBatch } from '@gamole/ai'

// Type-only imports from @gamole/db — erased at runtime, safe even if DB unavailable
import type { db as DbType } from '@gamole/db'
import type { linearIssuesCache as LinearIssuesCacheType } from '@gamole/db'

export interface SyncStats {
  total: number
  synced: number
  errors: number
}

/**
 * Fetch all Linear issues for the given token, embed them, and upsert into
 * the linear_issues_cache table.
 *
 * @param token        Linear personal API key or OAuth token (never stored)
 * @param workspaceId  Internal workspace ID — reserved for future filtering
 * @returns Sync statistics: total processed, successfully synced, and errors
 */
export async function syncLinearIssues(
  token: string,
  workspaceId: string,
): Promise<SyncStats> {
  // Dynamic import so the API server starts even without DATABASE_URL.
  // If the DB is unavailable the error propagates to the route handler.
  let db: typeof DbType
  let linearIssuesCache: typeof LinearIssuesCacheType

  try {
    const dbModule = await import('@gamole/db')
    db = dbModule.db
    linearIssuesCache = dbModule.linearIssuesCache
  } catch (err) {
    throw new Error(
      `Database not available: ${err instanceof Error ? err.message : String(err)}`,
    )
  }

  const client = new LinearClient(token)
  let cursor: string | undefined
  let total = 0
  let synced = 0
  let errors = 0

  do {
    const page = await client.getIssues({ cursor })
    if (!page.issues.length) break

    // Batch-embed: title + description for richer semantic matching
    const texts = page.issues.map(
      (issue) => `${issue.title} ${issue.description ?? ''}`,
    )
    const embeddings = await embedBatch(texts)

    // Upsert each issue (conflict on linear_id → update)
    for (let i = 0; i < page.issues.length; i++) {
      total++

      const issue = page.issues[i]
      const embedding = embeddings[i]

      // Both are guaranteed by length invariant, but satisfy noUncheckedIndexedAccess
      if (issue === undefined || embedding === undefined) {
        errors++
        continue
      }

      try {
        await db
          .insert(linearIssuesCache)
          .values({
            linearId: issue.id,
            // IssueSummary does not expose team info; stored as empty string
            // workspaceId is not part of the linearIssuesCache schema
            teamId: workspaceId || '',
            title: issue.title,
            description: issue.description ?? null,
            embedding,
            syncedAt: new Date(),
          })
          .onConflictDoUpdate({
            target: linearIssuesCache.linearId,
            set: {
              title: issue.title,
              description: issue.description ?? null,
              embedding,
              syncedAt: new Date(),
            },
          })
        synced++
      } catch {
        errors++
      }
    }

    cursor = page.cursor
  } while (cursor)

  return { total, synced, errors }
}
