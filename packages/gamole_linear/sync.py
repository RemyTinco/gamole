"""Linear issues sync: full and incremental.

G9: One-way pull only, no webhooks, no push-back.
G17: NO bidirectional sync.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from gamole_ai.embeddings import embed_batch

from .client import LinearClient

logger = logging.getLogger(__name__)

SYNC_STATE_KEY = "linear_issues"


@dataclass
class SyncStats:
    total: int = 0
    synced: int = 0
    skipped: int = 0
    deleted: int = 0
    errors: int = 0
    mode: str = "full"
    duration_seconds: float = 0
    teams_synced: list[str] = field(default_factory=list)


async def _get_last_sync_time() -> datetime | None:
    """Get the last successful sync timestamp from DB."""
    try:
        from sqlalchemy import select

        from gamole_db.models import SyncState
        from gamole_db.session import get_session

        async for session in get_session():
            result = await session.execute(
                select(SyncState).where(SyncState.key == SYNC_STATE_KEY)
            )
            state = result.scalar_one_or_none()
            if state:
                return state.last_synced_at
    except Exception:
        logger.warning("Could not read sync state", exc_info=True)
    return None


async def _update_sync_time(sync_time: datetime, metadata: dict | None = None) -> None:
    """Update the last sync timestamp in DB."""
    try:
        from sqlalchemy.dialects.postgresql import insert

        from gamole_db.models import SyncState
        from gamole_db.session import get_session

        async for session in get_session():
            stmt = insert(SyncState).values(
                key=SYNC_STATE_KEY,
                last_synced_at=sync_time,
                metadata_json=metadata,
                updated_at=sync_time,
            ).on_conflict_do_update(
                index_elements=["key"],
                set_={
                    "last_synced_at": sync_time,
                    "metadata_json": metadata,
                    "updated_at": sync_time,
                },
            )
            await session.execute(stmt)
            await session.commit()
    except Exception:
        logger.error("Could not update sync state", exc_info=True)


async def _sync_deleted_issues(client: LinearClient, session, known_ids: set[str]) -> int:
    """Remove cached issues that no longer exist in Linear. Returns count of deleted."""
    from sqlalchemy import delete, select

    from gamole_db import LinearIssueCache

    # Get all cached linear_ids
    result = await session.execute(select(LinearIssueCache.linear_id))
    cached_ids = {row[0] for row in result}

    stale_ids = cached_ids - known_ids
    if not stale_ids:
        return 0

    # Delete in batches
    deleted = 0
    batch_size = 100
    stale_list = list(stale_ids)
    for i in range(0, len(stale_list), batch_size):
        batch = stale_list[i:i + batch_size]
        await session.execute(
            delete(LinearIssueCache).where(LinearIssueCache.linear_id.in_(batch))
        )
        deleted += len(batch)

    return deleted


async def sync_linear_issues(
    token: str,
    workspace_id: str = "",
    force_full: bool = False,
) -> SyncStats:
    """Sync Linear issues to pgvector cache.

    Incremental by default: only fetches issues updated since last sync.
    Set force_full=True to re-sync everything.
    """
    import time

    start = time.monotonic()

    from sqlalchemy.dialects.postgresql import insert

    from gamole_db import LinearIssueCache, get_session

    client = LinearClient(token)
    stats = SyncStats()

    # Determine sync mode
    last_sync = None if force_full else await _get_last_sync_time()
    sync_start_time = datetime.now(timezone.utc)

    if last_sync and not force_full:
        stats.mode = "incremental"
        updated_after = last_sync.isoformat()
        logger.info(f"Incremental sync: fetching issues updated after {updated_after}")
    else:
        stats.mode = "full"
        updated_after = None
        logger.info("Full sync: fetching all issues")

    cursor: str | None = None
    all_synced_ids: set[str] = set()

    async for session in get_session():
        while True:
            page = await client.get_issues(
                cursor=cursor,
                updated_after=updated_after,
            )
            if not page.issues:
                break

            texts = [f"{issue.title} {issue.description or ''}" for issue in page.issues]
            try:
                embeddings = await embed_batch(texts)
            except Exception as embed_err:
                logger.error(f"Embedding batch failed: {embed_err}")
                stats.errors += len(page.issues)
                stats.total += len(page.issues)
                cursor = page.cursor
                if not page.has_next_page:
                    break
                continue

            for i, issue in enumerate(page.issues):
                stats.total += 1
                all_synced_ids.add(issue.id)
                embedding = embeddings[i] if i < len(embeddings) else None

                if embedding is None:
                    stats.errors += 1
                    continue

                try:
                    stmt = insert(LinearIssueCache).values(
                        linear_id=issue.id,
                        team_id=workspace_id or "",
                        title=issue.title,
                        description=issue.description,
                        embedding=embedding,
                    ).on_conflict_do_update(
                        index_elements=["linear_id"],
                        set_={
                            "title": issue.title,
                            "description": issue.description,
                            "embedding": embedding,
                            "synced_at": sync_start_time,
                        },
                    )
                    await session.execute(stmt)
                    stats.synced += 1
                except Exception as e:
                    logger.error(f"Insert failed for {issue.id}: {e}")
                    stats.errors += 1

            cursor = page.cursor
            if not page.has_next_page:
                break

        # On full sync, also clean up deleted issues
        if stats.mode == "full" and all_synced_ids:
            try:
                stats.deleted = await _sync_deleted_issues(client, session, all_synced_ids)
            except Exception:
                logger.error("Failed to clean deleted issues", exc_info=True)

        await session.commit()

    await client.close()

    # Update sync state
    stats.duration_seconds = round(time.monotonic() - start, 2)
    await _update_sync_time(
        sync_start_time,
        metadata={
            "mode": stats.mode,
            "total": stats.total,
            "synced": stats.synced,
            "deleted": stats.deleted,
            "errors": stats.errors,
            "duration_seconds": stats.duration_seconds,
        },
    )

    logger.info(
        f"Sync complete ({stats.mode}): {stats.synced} synced, "
        f"{stats.deleted} deleted, {stats.errors} errors in {stats.duration_seconds}s"
    )

    return stats


async def get_sync_status() -> dict:
    """Return current sync state info."""
    last_sync = await _get_last_sync_time()

    try:
        from sqlalchemy import func, select

        from gamole_db import LinearIssueCache
        from gamole_db.models import SyncState
        from gamole_db.session import get_session

        async for session in get_session():
            count_result = await session.execute(
                select(func.count(LinearIssueCache.id))
            )
            issue_count = count_result.scalar() or 0

            state_result = await session.execute(
                select(SyncState).where(SyncState.key == SYNC_STATE_KEY)
            )
            state = state_result.scalar_one_or_none()

            return {
                "lastSyncedAt": last_sync.isoformat() if last_sync else None,
                "cachedIssueCount": issue_count,
                "lastSyncMetadata": state.metadata_json if state else None,
            }
    except Exception:
        return {
            "lastSyncedAt": last_sync.isoformat() if last_sync else None,
            "cachedIssueCount": 0,
            "lastSyncMetadata": None,
        }


# ---------------------------------------------------------------------------
# Workspace entity sync (users, labels, states, projects for chat resolution)
# ---------------------------------------------------------------------------

ENTITY_SYNC_QUERY = """
{
    users { nodes { id name email } }
    teams { nodes { id name
        labels { nodes { id name } }
        states { nodes { id name type } }
    }}
    projects { nodes { id name state } }
}
"""


@dataclass
class EntitySyncStats:
    users: int = 0
    labels: int = 0
    states: int = 0
    projects: int = 0


async def sync_workspace_entities(token: str) -> EntitySyncStats:
    """Fetch users, labels, states, projects from Linear and cache in DB.

    Single GraphQL call fetches all entity types. Stored as JSONB in
    linear_workspace_cache table, keyed by entity type.
    Graceful: returns empty stats on any failure.
    """
    client = LinearClient(token)
    stats = EntitySyncStats()

    try:
        data = await client.raw_query(ENTITY_SYNC_QUERY)
    except Exception:
        logger.error("Failed to fetch workspace entities from Linear", exc_info=True)
        await client.close()
        return stats

    # Parse entities from response
    users = data.get("data", data).get("users", {}).get("nodes", [])
    stats.users = len(users)

    labels: list[dict] = []
    states: list[dict] = []
    for team in data.get("data", data).get("teams", {}).get("nodes", []):
        team_name = team.get("name", "")
        for label in team.get("labels", {}).get("nodes", []):
            labels.append({**label, "teamName": team_name})
        for state in team.get("states", {}).get("nodes", []):
            states.append({**state, "teamName": team_name})
    stats.labels = len(labels)
    stats.states = len(states)

    projects = data.get("data", data).get("projects", {}).get("nodes", [])
    stats.projects = len(projects)

    # Upsert into DB
    try:
        from sqlalchemy.dialects.postgresql import insert

        from gamole_db.models import LinearWorkspaceCache
        from gamole_db.session import get_session

        async for session in get_session():
            for key, value in [("users", users), ("labels", labels),
                               ("states", states), ("projects", projects)]:
                stmt = insert(LinearWorkspaceCache).values(
                    key=key,
                    data_json=value,
                    synced_at=datetime.now(timezone.utc),
                ).on_conflict_do_update(
                    index_elements=["key"],
                    set_={
                        "data_json": value,
                        "synced_at": datetime.now(timezone.utc),
                    },
                )
                await session.execute(stmt)
            await session.commit()
    except Exception:
        logger.error("Failed to persist workspace entities", exc_info=True)

    await client.close()

    logger.info(
        f"Entity sync complete: {stats.users} users, {stats.labels} labels, "
        f"{stats.states} states, {stats.projects} projects"
    )
    return stats


async def get_workspace_entities() -> dict:
    """Load cached workspace entities from DB. Returns empty dicts on failure."""
    result: dict[str, list] = {"users": [], "labels": [], "states": [], "projects": []}
    try:
        from sqlalchemy import select

        from gamole_db.models import LinearWorkspaceCache
        from gamole_db.session import get_session

        async for session in get_session():
            for key in result:
                row = await session.execute(
                    select(LinearWorkspaceCache).where(LinearWorkspaceCache.key == key)
                )
                cache = row.scalar_one_or_none()
                if cache:
                    result[key] = cache.data_json
    except Exception:
        logger.warning("Could not load workspace entity cache", exc_info=True)
    return result
