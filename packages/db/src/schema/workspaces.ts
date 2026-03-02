import { pgTable, uuid, text, jsonb, timestamp } from 'drizzle-orm/pg-core'
import { users } from './users'

export const workspaces = pgTable('workspaces', {
  id: uuid('id').defaultRandom().primaryKey(),
  userId: uuid('user_id').notNull().references(() => users.id, { onDelete: 'cascade' }),
  templateJson: jsonb('template_json'),
  settingsJson: jsonb('settings_json'),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
})
