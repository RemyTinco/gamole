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
    admin,
    chat,
    context,
    feedback,
    generation,
    health,
    linear,
    repositories,
    sync,
    teams,
)

limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.rate_limit_per_minute}/minute"])



logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup if they don't exist."""
    from gamole_db import Base, engine

    async with engine.begin() as conn:
        await conn.execute(sqlalchemy.text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Ensure enum values are up-to-date (safe to run repeatedly)
        await conn.execute(sqlalchemy.text(
            "DO $$ BEGIN"
            " IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'FEEDBACK'"
            " AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'document_version_type'))"
            " THEN ALTER TYPE document_version_type ADD VALUE 'FEEDBACK';"
            " END IF;"
            " END $$"
        ))
        # Add missing columns to existing tables (safe: IF NOT EXISTS)
        migrations = [
            "ALTER TABLE workflows ADD COLUMN IF NOT EXISTS cost_breakdown JSONB",
            "ALTER TABLE workflows ADD COLUMN IF NOT EXISTS structured_output JSONB",
            "ALTER TABLE workflows ADD COLUMN IF NOT EXISTS document TEXT",
            "ALTER TABLE document_versions ADD COLUMN IF NOT EXISTS feedback_json JSONB",
        ]
        for sql in migrations:
            await conn.execute(sqlalchemy.text(sql))
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified/created")
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
app.include_router(context.router, prefix="/api")
app.include_router(linear.router, prefix="/api")
app.include_router(feedback.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(repositories.router, prefix="/api")
app.include_router(teams.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse({"error": "Not found"}, status_code=404)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse({"error": "Internal server error"}, status_code=500)
