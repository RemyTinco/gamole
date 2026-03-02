"""Repository management: add, list, remove, re-index codebases."""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select

from gamole_db.models import CodebaseChunk, Repository
from gamole_db.session import get_session

from ..auth.middleware import auth_dependency

router = APIRouter()

logger = logging.getLogger(__name__)
MAX_REPOSITORIES = 10


class AddRepoBody(BaseModel):
    url: str = Field(min_length=1, description="Git clone URL (HTTPS or SSH)")
    description: str = Field(default="", description="Short description so agents know what this repo contains")
    branch: str | None = Field(default=None, description="Branch to index (default: main/master)")
    name: str | None = Field(default=None, description="Short name override (auto-derived from URL if omitted)")
    languages: list[str] | None = Field(default=None, description="Primary languages (e.g. ['python', 'typescript'])")


class UpdateRepoBody(BaseModel):
    description: str | None = None
    branch: str | None = None
    languages: list[str] | None = None


class RepoOut(BaseModel):
    id: str
    name: str
    url: str
    branch: str | None
    description: str
    languages: list[str] | None
    indexed_at: str | None
    file_count: int
    chunk_count: int
    created_at: str


def _repo_name_from_url(url: str) -> str:
    """Derive a short name from a git URL."""
    import re
    clean = url.removesuffix(".git")
    parts = [p for p in clean.replace(":", "/").split("/") if p]
    relevant = "-".join(parts[-2:]) if len(parts) >= 2 else parts[-1] if parts else "unknown"
    return re.sub(r"[^a-zA-Z0-9_-]", "_", relevant).lower()


def _to_out(repo: Repository) -> dict:
    return {
        "id": str(repo.id),
        "name": repo.name,
        "url": repo.url,
        "branch": repo.branch,
        "description": repo.description,
        "languages": repo.languages,
        "indexedAt": repo.indexed_at.isoformat() if repo.indexed_at else None,
        "fileCount": repo.file_count,
        "chunkCount": repo.chunk_count,
        "createdAt": repo.created_at.isoformat(),
        "indexingStatus": repo.indexing_status,
        "indexingError": repo.indexing_error,
    }


@router.get("/repositories", dependencies=[Depends(auth_dependency)])
async def list_repositories():
    """List all registered repositories."""
    async for session in get_session():
        result = await session.execute(
            select(Repository).order_by(Repository.created_at)
        )
        repos = result.scalars().all()
        return {"repositories": [_to_out(r) for r in repos]}


@router.post("/repositories", dependencies=[Depends(auth_dependency)])
async def add_repository(body: AddRepoBody):
    """Register a new repository for codebase indexing."""
    name = body.name or _repo_name_from_url(body.url)
    description = body.description or name

    async for session in get_session():
        # Check limit
        count_result = await session.execute(select(func.count(Repository.id)))
        count = count_result.scalar() or 0
        if count >= MAX_REPOSITORIES:
            raise HTTPException(
                status_code=422,
                detail=f"Repository limit reached (max {MAX_REPOSITORIES}). Remove one first.",
            )

        # Check duplicate
        existing = await session.execute(
            select(Repository).where(Repository.name == name)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"Repository '{name}' already exists")

        repo = Repository(
            name=name,
            url=body.url,
            branch=body.branch,
            description=description,
            languages=body.languages,
        )
        session.add(repo)
        await session.commit()
        await session.refresh(repo)

        return _to_out(repo)


@router.get("/repositories/github/available", dependencies=[Depends(auth_dependency)])
async def list_github_repos():
    """Fetch repos accessible with the configured GitHub token, for frontend selection."""
    from ..config import settings

    if not settings.github_token:
        raise HTTPException(status_code=400, detail="No GitHub token configured on server (GITHUB_TOKEN env)")

    import httpx

    repos_out = []
    page = 1
    async with httpx.AsyncClient() as client:
        while page <= 5:  # cap at 500 repos
            resp = await client.get(
                "https://api.github.com/user/repos",
                params={"per_page": 100, "page": page, "sort": "updated"},
                headers={"Authorization": f"token {settings.github_token}", "Accept": "application/vnd.github.v3+json"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            for r in data:
                repos_out.append({
                    "fullName": r["full_name"],
                    "url": r["clone_url"],
                    "description": r.get("description") or "",
                    "language": r.get("language"),
                    "defaultBranch": r.get("default_branch", "main"),
                    "private": r["private"],
                    "updatedAt": r.get("updated_at"),
                })
            page += 1

    return {"repositories": repos_out}


@router.get("/repositories/context/summary", dependencies=[Depends(auth_dependency)])
async def get_repositories_context():
    """Return a summary of all repos for agent context injection.

    Agents use this to understand which codebases are available and what they contain,
    so they can make informed decisions about which code to investigate.
    """
    async for session in get_session():
        result = await session.execute(
            select(Repository).order_by(Repository.created_at)
        )
        repos = result.scalars().all()
        summaries = []
        for r in repos:
            summaries.append({
                "name": r.name,
                "description": r.description,
                "languages": r.languages or [],
                "branch": r.branch,
                "fileCount": r.file_count,
                "chunkCount": r.chunk_count,
                "indexed": r.indexed_at is not None,
            })
        return {"repositories": summaries}


@router.get("/repositories/{repo_id}", dependencies=[Depends(auth_dependency)])
async def get_repository(repo_id: str):
    """Get a single repository by ID."""
    async for session in get_session():
        repo = await session.get(Repository, uuid.UUID(repo_id))
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        return _to_out(repo)


@router.put("/repositories/{repo_id}", dependencies=[Depends(auth_dependency)])
async def update_repository(repo_id: str, body: UpdateRepoBody):
    """Update repository description, branch, or languages."""
    async for session in get_session():
        repo = await session.get(Repository, uuid.UUID(repo_id))
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")

        if body.description is not None:
            repo.description = body.description
        if body.branch is not None:
            repo.branch = body.branch
        if body.languages is not None:
            repo.languages = body.languages
        repo.updated_at = datetime.utcnow()

        await session.commit()
        await session.refresh(repo)
        return _to_out(repo)


@router.delete("/repositories/{repo_id}", dependencies=[Depends(auth_dependency)])
async def remove_repository(repo_id: str):
    """Remove a repository and all its indexed chunks."""
    async for session in get_session():
        repo = await session.get(Repository, uuid.UUID(repo_id))
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")

        # Delete all chunks for this repo
        await session.execute(
            delete(CodebaseChunk).where(CodebaseChunk.repo_name == repo.name)
        )
        await session.delete(repo)
        await session.commit()

        return {"ok": True, "deleted": repo.name}


@router.post("/repositories/{repo_id}/index", dependencies=[Depends(auth_dependency)])
async def index_repository_endpoint(repo_id: str):
    """Trigger indexing (clone/pull + embed) for a repository. Returns immediately; runs in background."""
    async for session in get_session():
        repo = await session.get(Repository, uuid.UUID(repo_id))
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")

        if repo.indexing_status == "indexing":
            return {"ok": True, "status": "already_indexing"}

        # Mark as indexing
        repo.indexing_status = "indexing"
        repo.indexing_error = None
        repo.updated_at = datetime.utcnow()
        await session.commit()

        # Fire background task
        asyncio.create_task(_run_indexing(str(repo.id), repo.url, repo.branch))

        return {"ok": True, "status": "indexing"}


async def _run_indexing(repo_id: str, repo_url: str, branch: str | None) -> None:
    """Background indexing task. Updates repo status on completion or error."""
    try:
        from gamole_ai.codebase.indexer import index_repository

        from ..config import settings

        stats = await index_repository(repo_url, branch, settings.github_token or None)

        # Update repo with results
        async for session in get_session():
            repo = await session.get(Repository, uuid.UUID(repo_id))
            if repo:
                repo.indexed_at = datetime.utcnow()
                repo.file_count = stats.files_indexed
                repo.chunk_count = stats.chunks_created
                repo.indexing_status = "done"
                repo.indexing_error = None
                repo.updated_at = datetime.utcnow()
                await session.commit()
        logger.info(f"Indexing complete for {repo_url}: {stats.files_indexed} files, {stats.chunks_created} chunks")
    except Exception as e:
        logger.error(f"Indexing failed for {repo_url}: {e}", exc_info=True)
        try:
            async for session in get_session():
                repo = await session.get(Repository, uuid.UUID(repo_id))
                if repo:
                    repo.indexing_status = "error"
                    repo.indexing_error = str(e)[:500]
                    repo.updated_at = datetime.utcnow()
                    await session.commit()
        except Exception:
            logger.error("Failed to update repo status after indexing error", exc_info=True)
