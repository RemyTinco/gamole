import { pgTable, uuid, text, timestamp } from 'drizzle-orm/pg-core'
import { workspaces } from './workspaces'

export const linearConnections = pgTable('linear_connections', {
  id: uuid('id').defaultRandom().primaryKey(),
  workspaceId: uuid('workspace_id').notNull().references(() => workspaces.id, { onDelete: 'cascade' }),
  tokenRef: text('token_ref').notNull(), // reference only, not actual token
  linearOrgId: text('linear_org_id').notNull(),
  createdAt: timestamp('created_at').defaultNow().notNull(),
})
