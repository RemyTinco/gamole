import { pgTable, uuid, text, integer, real, boolean, timestamp } from 'drizzle-orm/pg-core'
import { workflows } from './workflows'

export const agentRuns = pgTable('agent_runs', {
  id: uuid('id').defaultRandom().primaryKey(),
  workflowId: uuid('workflow_id').notNull().references(() => workflows.id, { onDelete: 'cascade' }),
  agentName: text('agent_name').notNull(),
  roundNumber: integer('round_number').notNull().default(1),
  latencyMs: integer('latency_ms'),
  tokenIn: integer('token_in'),
  tokenOut: integer('token_out'),
  success: boolean('success').notNull().default(true),
  errorType: text('error_type'),
  critiqueMarkdown: text('critique_markdown'), // stored but never shown to user
  createdAt: timestamp('created_at').defaultNow().notNull(),
})
