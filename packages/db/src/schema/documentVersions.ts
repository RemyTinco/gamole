import { pgTable, uuid, text, timestamp, pgEnum } from 'drizzle-orm/pg-core'
import { workflows } from './workflows'

export const documentVersionTypeEnum = pgEnum('document_version_type', ['AI_FINAL', 'USER_EDITED'])

export const documentVersions = pgTable('document_versions', {
  id: uuid('id').defaultRandom().primaryKey(),
  workflowId: uuid('workflow_id').notNull().references(() => workflows.id, { onDelete: 'cascade' }),
  type: documentVersionTypeEnum('type').notNull(),
  contentMarkdown: text('content_markdown').notNull(),
  createdAt: timestamp('created_at').defaultNow().notNull(),
})
