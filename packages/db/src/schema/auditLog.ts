import { pgTable, uuid, text, jsonb, timestamp } from 'drizzle-orm/pg-core'

export const auditLog = pgTable('audit_log', {
  id: uuid('id').defaultRandom().primaryKey(),
  workflowId: uuid('workflow_id'), // nullable — some events are workspace-level
  eventType: text('event_type').notNull(),
  payloadJson: jsonb('payload_json'),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  // NOTE: append-only — never UPDATE or DELETE from this table
})
