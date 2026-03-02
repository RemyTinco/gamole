import { pgTable, uuid, text, timestamp, index } from 'drizzle-orm/pg-core'
import { vector } from 'drizzle-orm/pg-core'

export const codebaseChunks = pgTable('codebase_chunks', {
  id: uuid('id').defaultRandom().primaryKey(),
  repoName: text('repo_name').notNull(),
  filePath: text('file_path').notNull(),
  language: text('language'),
  chunkText: text('chunk_text').notNull(),
  domain: text('domain'),
  artifactType: text('artifact_type'),
  embedding: vector('embedding', { dimensions: 768 }),
  lastIndexedAt: timestamp('last_indexed_at').defaultNow().notNull(),
}, (table) => [
  index('codebase_chunks_embedding_idx').using('hnsw', table.embedding.op('vector_cosine_ops')),
])
