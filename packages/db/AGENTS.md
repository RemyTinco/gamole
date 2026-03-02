# DB — packages/db

Drizzle ORM with PostgreSQL 16 + pgvector. 11 tables across 5 layers.

## STRUCTURE

```
src/
├── index.ts              # Singleton db instance (postgres-js + drizzle), schema re-export
└── schema/
    ├── index.ts          # Barrel export for all tables
    ├── users.ts          # Root entity (id, email)
    ├── workspaces.ts     # User workspace (templateJson, settingsJson JSONB)
    ├── workflows.ts      # Core: 13-state enum, qualityScore, stateJson (XState snapshot)
    ├── documentVersions.ts  # AI_FINAL | USER_EDITED versions
    ├── agentRuns.ts      # Per-agent execution: latency, tokens, critique
    ├── linearConnections.ts # Workspace ↔ Linear org (tokenRef only, never actual token)
    ├── linearPushEvents.ts  # Push history (create/update modes)
    ├── linearIssuesCache.ts # Cached issues + vector(768) + HNSW index
    ├── codebaseChunks.ts    # Code chunks + vector(768) + HNSW index
    └── auditLog.ts       # Append-only event log (NEVER update/delete)
drizzle/                  # Generated migrations + meta
drizzle.config.ts         # PostgreSQL dialect, schema path
```

## DATA MODEL

```
users → workspaces → workflows → documentVersions
                               → agentRuns
                               → linearPushEvents
                   → linearConnections
linearIssuesCache (standalone, pgvector)
codebaseChunks (standalone, pgvector)
auditLog (append-only, optional workflow FK)
```

All FKs cascade on delete. Deleting a user cascades through everything.

## ENUMS

- **workflow_status** (13): INITIALIZED → ... → PUSHED_TO_LINEAR | FAILED
- **document_version_type** (2): AI_FINAL | USER_EDITED
- **push_mode** (2): create | update

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Add table | `schema/*.ts` | Create file, export from `schema/index.ts` |
| Add column | `schema/*.ts` | Edit table, run generate + migrate |
| Vector search | `linearIssuesCache.ts`, `codebaseChunks.ts` | HNSW index, cosine ops |
| Workflow state | `workflows.ts` | `stateJson` stores XState snapshot |
| Audit events | `auditLog.ts` | Append-only — never update/delete |

## CONVENTIONS

- Requires `DATABASE_URL` env var (throws on startup if missing)
- JSONB columns for flexible data: `templateJson`, `settingsJson`, `stateJson`, `resultJson`, `payloadJson`
- Vector columns: 768 dimensions, HNSW index with `vector_cosine_ops`
- `tokenRef` fields store references only — actual tokens never in DB
- Quality score stored as `real` (0-1 range in DB, displayed as 0-10)

## COMMANDS

```bash
pnpm --filter @gamole/db generate    # Generate migration from schema changes
pnpm --filter @gamole/db migrate     # Apply pending migrations
pnpm --filter @gamole/db studio      # Open Drizzle Studio (visual DB browser)
```
