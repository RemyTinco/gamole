"""Sync endpoints: Linear issues (incremental/full), sync status and scheduling."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth.middleware import auth_dependency

router = APIRouter()
logger = logging.getLogger(__name__)

# Background sync state
_sync_task: asyncio.Task | None = None


class LinearSyncBody(BaseModel):
    token: str | None = Field(default=None, description="Linear API token (uses server config if omitted)")
    workspace_id: str = Field(default="", alias="workspaceId")
    force_full: bool = Field(default=False, alias="forceFull", description="Force full re-sync instead of incremental")

    model_config = {"populate_by_name": True}


class SyncScheduleBody(BaseModel):
    enabled: bool = True
    interval_hours: int = Field(default=6, alias="intervalHours", ge=1, le=168)

    model_config = {"populate_by_name": True}


async def _run_background_sync(token: str, workspace_id: str = "") -> None:
    """Background task for periodic sync."""
    try:
        from gamole_linear.sync import sync_linear_issues, sync_workspace_entities

        stats = await sync_linear_issues(token, workspace_id)
        logger.info(
            f"Background sync complete: {stats.synced} synced, "
            f"{stats.deleted} deleted in {stats.duration_seconds}s"
        )

        # Also sync workspace entities (users, labels, states, projects)
        entity_stats = await sync_workspace_entities(token)
        logger.info(
            f"Entity sync complete: {entity_stats.users} users, "
            f"{entity_stats.labels} labels, {entity_stats.states} states, "
            f"{entity_stats.projects} projects"
        )
    except Exception:
        logger.error("Background sync failed", exc_info=True)

@router.post("/sync/linear", dependencies=[Depends(auth_dependency)])
async def sync_linear(body: LinearSyncBody):
    """Sync Linear issues to pgvector cache. Incremental by default."""
    from ..config import settings

    token = body.token or settings.linear_api_token
    if not token:
        raise HTTPException(status_code=400, detail="No Linear token provided and none configured (LINEAR_API_TOKEN)")

    try:
        from gamole_linear.sync import sync_linear_issues, sync_workspace_entities

        stats = await sync_linear_issues(token, body.workspace_id, force_full=body.force_full)

        # Also sync workspace entities for chat entity resolution
        entity_stats = await sync_workspace_entities(token)

        return {
            "ok": True,
            "mode": stats.mode,
            "total": stats.total,
            "synced": stats.synced,
            "deleted": stats.deleted,
            "errors": stats.errors,
            "durationSeconds": stats.duration_seconds,
            "entities": {
                "users": entity_stats.users,
                "labels": entity_stats.labels,
                "states": entity_stats.states,
                "projects": entity_stats.projects,
            },
        }
    except Exception as e:
        message = str(e)
        if "database" in message.lower():
            raise HTTPException(status_code=503, detail=message)


@router.get("/sync/linear/status", dependencies=[Depends(auth_dependency)])
async def sync_linear_status():
    """Get current sync status: last sync time, cached issue count, last sync details."""
    try:
        from gamole_linear.sync import get_sync_status

        return await get_sync_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/linear/schedule", dependencies=[Depends(auth_dependency)])
async def schedule_sync(body: SyncScheduleBody):
    """Start or stop periodic background sync."""
    global _sync_task

    from ..config import settings

    token = settings.linear_api_token
    if not token:
        raise HTTPException(status_code=400, detail="LINEAR_API_TOKEN not configured. Periodic sync requires a server-side token.")

    if _sync_task and not _sync_task.done():
        _sync_task.cancel()
        _sync_task = None

    if not body.enabled:
        return {"ok": True, "status": "disabled", "message": "Periodic sync stopped"}

    interval_seconds = body.interval_hours * 3600

    async def _periodic_sync():
        while True:
            await _run_background_sync(token)
            await asyncio.sleep(interval_seconds)

    _sync_task = asyncio.create_task(_periodic_sync())
    return {
        "ok": True,
        "status": "enabled",
        "intervalHours": body.interval_hours,
        "message": f"Periodic incremental sync every {body.interval_hours}h",
    }


@router.get("/sync/linear/schedule", dependencies=[Depends(auth_dependency)])
async def get_sync_schedule():
    """Check if periodic sync is running."""
    running = _sync_task is not None and not _sync_task.done()
    return {"running": running}


