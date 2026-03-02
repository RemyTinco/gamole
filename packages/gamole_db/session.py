"""Async engine + session factory for SQLAlchemy 2.0."""

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/gamole")

# Convert postgres:// to postgresql+asyncpg:// if needed
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False, pool_size=5, max_overflow=10)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI route injection."""
    async with async_session() as session:
        yield session
