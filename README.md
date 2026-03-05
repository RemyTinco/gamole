# 🧀 Gamole

AI-powered ticket refinement engine. Takes rough feature requests, runs them through multiple AI agents for review, and outputs structured Linear issues ready for sprint planning.

## What it does

1. **You describe a feature** in plain text
2. **5 AI agents** (Draft, QA, Dev, PO, Supervisor) iteratively refine it
3. **You review and edit** the refined document (human-in-the-loop)
4. **Structured output**: epics and stories with acceptance criteria, technical notes, and team assignments
5. **Push to Linear**: each epic routed to the right team, cross-team projects created automatically
6. **Chat with Linear**: ask questions about your workspace in natural language

## Architecture

```mermaid
graph LR
    UI["Next.js UI<br/>(port 3000)"] --> Backend

    subgraph Backend ["FastAPI Backend"]
        LG["LangGraph<br/>Workflow"]
        LC["LangChain<br/>+ LiteLLM"]
        PG["pgvector<br/>RAG"]
        Linear["Linear<br/>GraphQL"]
        GH["GitHub<br/>Codebase"]
    end
```

### Workflow (LangGraph)

```mermaid
graph LR
    Input --> Retrieve[Retrieve Context] --> Draft
    Draft --> QA & Dev & PO
    QA & Dev & PO --> Merge --> Supervisor
    Supervisor -->|quality < threshold| Draft
    Supervisor -->|approved| UE[USER_EDITING<br/>pause]
    UE --> Finalize --> Structure --> Push[Push to Linear]
```

- Max 5 iteration rounds
- QA, Dev, and PO agents run in parallel (fan-out/fan-in)
- Supervisor decides: loop for another round or approve
- Human-in-the-loop: edit the refined document before structuring
- Structurer assigns each epic to the right Linear team based on descriptions

### RAG Context

Agents receive context from two sources:

- **Linear issues**: similar existing tickets via pgvector cosine similarity
- **Codebase chunks**: relevant code from indexed repositories

This grounds the output in your actual codebase and existing ticket patterns.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, React, Tailwind, ky |
| Backend | FastAPI, uvicorn, SSE streaming |
| AI | LangChain, LangGraph, Gemini (via langchain-google-genai) |
| Database | PostgreSQL 16, SQLAlchemy 2.0 async, pgvector, Alembic |
| Integrations | Linear GraphQL API, GitHub API |
| Testing | pytest, ruff |
| Package manager | uv |

## Setup

### Prerequisites

- Python 3.12+
- Node.js 18+ and pnpm
- Docker (for PostgreSQL + pgvector)
- Gemini API key
- Linear API token (optional, for push/chat features)
- GitHub token (optional, for private repo indexing)

### Environment

```bash
cp .env.example .env
```

```env
# Required
GOOGLE_GENERATIVE_AI_API_KEY=AIza...
GEMINI_API_KEY=AIza...
DATABASE_URL=postgresql+asyncpg://postgres:gamole_dev@localhost:5432/gamole
SESSION_SECRET=your-secret-minimum-32-characters-long

# Optional
LINEAR_API_TOKEN=lin_api_...
GITHUB_TOKEN=ghp_...
CORS_ORIGINS=http://localhost:3000
```

### Database

```bash
docker compose up -d postgres
```

Ports bind to `127.0.0.1` only (not exposed to internet).

### Backend

```bash
uv sync
cd apps/api
PYTHONPATH=.:../../ uv run uvicorn app.main:app --port 3001
```

### Frontend

```bash
pnpm install
cd apps/web
NEXT_PUBLIC_API_URL=http://localhost:3001 pnpm dev
```

### Tests

```bash
uv run pytest apps/api/tests/ -v       # unit tests (no DB needed)
uv run ruff check packages/ apps/api/   # linting
```

DB-dependent tests skip automatically when PostgreSQL isn't running.

### Authentication

The API uses JWT bearer tokens for authentication. All `/api/*` routes (except `/health`) require a valid token in the `Authorization` header.

**How it works:**

1. A JWT is created with `create_session(user_id, workspace_id)` from `apps/api/app/auth/jwt.py`
2. The token is signed with `SESSION_SECRET` (HS256) and expires after 7 days
3. Clients send it as `Authorization: Bearer <token>`
4. The `auth_dependency` middleware decodes and validates the token on every protected request

**Generate a dev token:**

```bash
# From the project root (requires the API container running)
docker compose exec api python -c "
from app.auth.jwt import create_session
print(create_session(user_id='dev-user'))"
```

Or without Docker:

```bash
cd apps/api
PYTHONPATH=.:../../ python -c "
from app.auth.jwt import create_session
print(create_session(user_id='dev-user'))"
```

**Use the token:**

```bash
TOKEN="<paste token here>"
curl http://localhost:3001/api/generation -H "Authorization: Bearer $TOKEN"
```

The token payload contains `userId`, `iat`, and `exp`. Optionally includes `workspaceId` if provided at creation.

## API Endpoints

### Generation (ticket refinement)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/generation` | Start a new generation workflow |
| GET | `/api/generation` | List all generations |
| GET | `/api/generation/{id}` | Get generation status and output |
| GET | `/api/generation/{id}/output` | Get structured epics/stories |
| GET | `/api/generation/{id}/stream` | SSE stream for real-time progress |
| PUT | `/api/generation/{id}/document` | Edit refined document (human-in-the-loop) |
| POST | `/api/generation/{id}/finalize` | Trigger structuring after editing |

### Linear

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/linear/validate` | Pre-push validation (count issues) |
| POST | `/api/linear/push` | Push structured output to Linear |
| POST | `/api/linear/push-generation` | Push a generation directly |
| POST | `/api/chat/linear` | Chat with Linear in natural language |
| POST | `/api/chat/search` | Semantic search over cached issues |

### Configuration

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/api/repositories` | Manage codebase repositories |
| GET | `/api/repositories/github/available` | Browse GitHub repos for selection |
| POST | `/api/repositories/{id}/index` | Trigger codebase indexing |
| GET/POST | `/api/teams` | Manage Linear teams with descriptions |
| POST | `/api/teams/sync` | Import teams from Linear API |
| POST | `/api/sync/linear` | Sync Linear issues to pgvector cache |

## Key Features

### Per-epic team routing

Each epic is assigned to the most appropriate Linear team by the AI, based on team descriptions you provide. A feature spanning payments and origination will split into epics for each team, linked under a shared Linear project.

### Cost tracking

Every generation tracks token usage per agent with estimated costs (Gemini Flash pricing). Stored as JSONB on the workflow record and returned in API responses.

### Human-in-the-loop

After AI approval, the workflow pauses in `USER_EDITING` state. Edit the document, then finalize to trigger structuring. The SSE stream emits `user_edit_required` so the frontend knows to show an editor.

### Chat with Linear

Ask questions like "How many tickets did Nelly create last 3 weeks?" or "What's blocked in origination?" The LLM converts to GraphQL, executes against Linear's API, self-corrects on errors, and returns a natural language answer with sources.

## Project Structure

```mermaid
graph TD
    subgraph apps ["apps/"]
        api["api/ — FastAPI backend"]
        api --> routes["routes/ — API endpoints"]
        api --> orch["orchestrator/ — LangGraph workflow"]
        api --> auth["auth/ — JWT auth"]
        api --> cfg["config.py — pydantic-settings"]
        web["web/ — Next.js frontend"]
    end

    subgraph packages ["packages/"]
        gai["gamole_ai/ — LangChain agents, embeddings, retrieval, codebase indexer"]
        gdb["gamole_db/ — SQLAlchemy models, session management"]
        glin["gamole_linear/ — Linear GraphQL client, batch push, sync"]
        gtyp["gamole_types/ — Pydantic schemas (shared types)"]
    end
```

## Later Improvements

Features planned but not yet implemented:

- **Feedback loop**: Track which stories get edited after Linear push. Submit feedback via the API to identify which AI output fields need improvement. Show statistics on what changes most to inform prompt tuning. (Backend scaffolding exists in DB schema — `DocumentVersion.feedback_json` column and `FEEDBACK` type enum are ready.)
- **Codebase sync scheduling**: Automatic periodic re-indexing of repositories (currently manual only)
- **Codebase orphan cleanup**: Detect and remove chunks for deleted/renamed files during re-indexing
- **Diff-based indexing**: Only re-index changed files instead of full repository walks
- **Push response codes**: Return 207 Multi-Status or `ok: false` when some issues fail to push


## License

Private.
