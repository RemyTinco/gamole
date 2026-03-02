import { pgTable, uuid, text, jsonb, timestamp, pgEnum } from 'drizzle-orm/pg-core'
import { workflows } from './workflows'

export const pushModeEnum = pgEnum('push_mode', ['create', 'update'])

export const linearPushEvents = pgTable('linear_push_events', {
  id: uuid('id').defaultRandom().primaryKey(),
  workflowId: uuid('workflow_id').notNull().references(() => workflows.id, { onDelete: 'cascade' }),
  linearIssueId: text('linear_issue_id').notNull(),
  mode: pushModeEnum('mode').notNull(),
  pushedAt: timestamp('pushed_at').defaultNow().notNull(),
  tokenRef: text('token_ref').notNull(),
  resultJson: jsonb('result_json'),
})
