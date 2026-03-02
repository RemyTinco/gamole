import { pgTable, uuid, text, timestamp, index } from 'drizzle-orm/pg-core'
import { vector } from 'drizzle-orm/pg-core'

export const linearIssuesCache = pgTable('linear_issues_cache', {
  id: uuid('id').defaultRandom().primaryKey(),
  linearId: text('linear_id').notNull().unique(),
  teamId: text('team_id').notNull(),
  title: text('title').notNull(),
  description: text('description'),
  embedding: vector('embedding', { dimensions: 768 }),
  syncedAt: timestamp('synced_at').defaultNow().notNull(),
}, (table) => [
  index('linear_issues_embedding_idx').using('hnsw', table.embedding.op('vector_cosine_ops')),
])
