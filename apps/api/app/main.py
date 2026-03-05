"""FastAPI application - ported from apps/api/src/index.ts."""

import logging
from contextlib import asynccontextmanager

import sqlalchemy
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import settings
from .routes import (
    chat,
    generation,
    health,
    linear,
    repositories,
    sync,
    teams,
)

limiter = Limiter(
    key_func=get_remote_address, default_limits=[f"{settings.rate_limit_per_minute}/minute"]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup if they don't exist."""
    from gamole_db import Base, engine

    async with engine.begin() as conn:
        await conn.execute(sqlalchemy.text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Create tables/enums first so ALTER TYPE can find them
        await conn.run_sync(Base.metadata.create_all)
        # Ensure enum values are up-to-date (safe to run repeatedly)
        await conn.execute(
            sqlalchemy.text(
                "DO $$ BEGIN"
                " IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'FEEDBACK'"
                " AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'document_version_type'))"
                " THEN ALTER TYPE document_version_type ADD VALUE 'FEEDBACK';"
                " END IF;"
                " END $$"
            )
        )
        # Ensure workflow_status enum has AWAITING_DISCOVERY value
        await conn.execute(
            sqlalchemy.text(
                "DO $$ BEGIN"
                " IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'AWAITING_DISCOVERY'"
                " AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'workflow_status'))"
                " THEN ALTER TYPE workflow_status ADD VALUE 'AWAITING_DISCOVERY';"
                " END IF;"
                " END $$"
            )
        )
        # Add missing columns to existing tables (safe: IF NOT EXISTS)
        migrations = [
            "ALTER TABLE workflows ADD COLUMN IF NOT EXISTS cost_breakdown JSONB",
            "ALTER TABLE workflows ADD COLUMN IF NOT EXISTS structured_output JSONB",
            "ALTER TABLE workflows ADD COLUMN IF NOT EXISTS document TEXT",
            "ALTER TABLE codebase_chunks ADD COLUMN IF NOT EXISTS symbol_name TEXT",
            "ALTER TABLE codebase_chunks ADD COLUMN IF NOT EXISTS content_hash TEXT",
            "ALTER TABLE codebase_chunks ADD COLUMN IF NOT EXISTS chunk_index INTEGER",
            "ALTER TABLE codebase_chunks ADD COLUMN IF NOT EXISTS parent_symbol TEXT",
            "ALTER TABLE codebase_chunks ADD COLUMN IF NOT EXISTS content_tsv tsvector",
            "UPDATE codebase_chunks SET content_tsv = to_tsvector('simple', chunk_text) WHERE content_tsv IS NULL",
            "CREATE INDEX IF NOT EXISTS codebase_chunks_tsv_idx ON codebase_chunks USING GIN(content_tsv)",
            "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS event_type TEXT DEFAULT 'agent_call'",
            "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS prompt_text TEXT",
            "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS response_text TEXT",
            "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS model_name TEXT",
            "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS metadata_json JSONB",
            "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS cost_usd REAL",
            "CREATE INDEX IF NOT EXISTS idx_agent_runs_workflow_id ON agent_runs(workflow_id)",
        ]
        for sql in migrations:
            await conn.execute(sqlalchemy.text(sql))
    logger.info("Database tables verified/created")

    # Auto re-index all repositories after schema migration
    # This runs in the background so it doesn't block startup
    async def _auto_reindex():
        """Re-index all repositories to populate new columns (symbol_name, content_hash, etc.)."""
        import asyncio
        await asyncio.sleep(5)  # Wait for DB to be fully ready
        try:
            from sqlalchemy import select

            from app.config import settings
            from gamole_ai.codebase.indexer import index_repository
            from gamole_db import get_session
            from gamole_db.models import Repository

            async for session in get_session():
                result = await session.execute(select(Repository))
                repos = list(result.scalars())

            if not repos:
                return

            logger.info(f"[startup] Auto re-indexing {len(repos)} repositories...")

            for repo in repos:
                try:
                    stats = await index_repository(repo.url, repo.branch, settings.github_token or None)
                    logger.info(f"[startup] Re-indexed {repo.name}: {stats.chunks_created} chunks, {stats.files_skipped} skipped, {stats.orphans_deleted} orphans deleted")
                except Exception as e:
                    logger.warning(f"[startup] Re-index failed for {repo.name}: {e}")
        except Exception as e:
            logger.warning(f"[startup] Auto re-index failed: {e}")

    import asyncio
    asyncio.create_task(_auto_reindex())
    yield


app = FastAPI(title="Gamole API", version="0.1.0", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Rate limiting
app.state.limiter = limiter

# Public routes
app.include_router(health.router)

# Protected routes
app.include_router(generation.router, prefix="/api")
app.include_router(sync.router, prefix="/api")
app.include_router(linear.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(repositories.router, prefix="/api")
app.include_router(teams.router, prefix="/api")


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse({"error": "Not found"}, status_code=404)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse({"error": "Internal server error"}, status_code=500)
