import { pgTable, uuid, text, integer, real, jsonb, timestamp, pgEnum } from 'drizzle-orm/pg-core'
import { workspaces } from './workspaces'

export const workflowStatusEnum = pgEnum('workflow_status', [
  'INITIALIZED', 'CONTEXT_RETRIEVED', 'DRAFT_GENERATED', 'QA_REVIEWED',
  'DEV_REVIEWED', 'PO_REVIEWED', 'SUPERVISOR_REFINED', 'QUALITY_EVALUATED',
  'APPROVED_FINAL_AI', 'USER_EDITING', 'READY_TO_PUSH', 'PUSHED_TO_LINEAR', 'FAILED'
])

export const workflows = pgTable('workflows', {
  id: uuid('id').defaultRandom().primaryKey(),
  workspaceId: uuid('workspace_id').notNull().references(() => workspaces.id, { onDelete: 'cascade' }),
  status: workflowStatusEnum('status').notNull().default('INITIALIZED'),
  inputText: text('input_text').notNull(),
  inputMode: text('input_mode', { enum: ['form', 'chat'] }).notNull().default('form'),
  targetTeamId: text('target_team_id').notNull(),
  targetProjectId: text('target_project_id'),
  qualityScore: real('quality_score'),
  qualityFlagsJson: jsonb('quality_flags_json'),
  retrievalStatsJson: jsonb('retrieval_stats_json'),
  agentRounds: integer('agent_rounds').notNull().default(0),
  stateJson: jsonb('state_json'), // XState machine snapshot for checkpoint/resume
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
})
