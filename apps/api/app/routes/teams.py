"""Linear team management: track teams with descriptions so AI can auto-route tickets."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from gamole_db.models import LinearTeam
from gamole_db.session import get_session

from ..auth.middleware import auth_dependency

router = APIRouter()


class AddTeamBody(BaseModel):
    linear_id: str = Field(alias="linearId", description="Linear team UUID")
    name: str = Field(min_length=1)
    description: str = Field(min_length=1, description="What this team owns, so agents can route tickets")
    default_state_id: str | None = Field(default=None, alias="defaultStateId")
    default_labels: list[str] | None = Field(default=None, alias="defaultLabels")

    model_config = {"populate_by_name": True}


class UpdateTeamBody(BaseModel):
    description: str | None = None
    default_state_id: str | None = Field(default=None, alias="defaultStateId")
    default_labels: list[str] | None = Field(default=None, alias="defaultLabels")

    model_config = {"populate_by_name": True}


class SyncTeamsBody(BaseModel):
    token: str | None = Field(default=None, description="Linear API token (uses server config if omitted)")
    descriptions: dict[str, str] | None = Field(
        default=None,
        description="Optional map of team name to description. Teams without a description get a placeholder.",
    )


def _to_out(team: LinearTeam) -> dict:
    return {
        "id": str(team.id),
        "linearId": team.linear_id,
        "name": team.name,
        "description": team.description,
        "defaultStateId": team.default_state_id,
        "defaultLabels": team.default_labels,
        "createdAt": team.created_at.isoformat(),
    }


@router.get("/teams", dependencies=[Depends(auth_dependency)])
async def list_teams():
    """List all tracked Linear teams."""
    async for session in get_session():
        result = await session.execute(
            select(LinearTeam).order_by(LinearTeam.name)
        )
        teams = result.scalars().all()
        return {"teams": [_to_out(t) for t in teams]}


@router.post("/teams", dependencies=[Depends(auth_dependency)])
async def add_team(body: AddTeamBody):
    """Register a Linear team with a description."""
    async for session in get_session():
        existing = await session.execute(
            select(LinearTeam).where(LinearTeam.linear_id == body.linear_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"Team with linearId '{body.linear_id}' already exists")

        team = LinearTeam(
            linear_id=body.linear_id,
            name=body.name,
            description=body.description,
            default_state_id=body.default_state_id,
            default_labels=body.default_labels,
        )
        session.add(team)
        await session.commit()
        await session.refresh(team)
        return _to_out(team)


@router.put("/teams/{team_id}", dependencies=[Depends(auth_dependency)])
async def update_team(team_id: str, body: UpdateTeamBody):
    """Update team description or defaults."""
    async for session in get_session():
        team = await session.get(LinearTeam, uuid.UUID(team_id))
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        if body.description is not None:
            team.description = body.description
        if body.default_state_id is not None:
            team.default_state_id = body.default_state_id
        if body.default_labels is not None:
            team.default_labels = body.default_labels
        team.updated_at = datetime.now(timezone.utc)

        await session.commit()
        await session.refresh(team)
        return _to_out(team)


@router.delete("/teams/{team_id}", dependencies=[Depends(auth_dependency)])
async def remove_team(team_id: str):
    """Remove a tracked team."""
    async for session in get_session():
        team = await session.get(LinearTeam, uuid.UUID(team_id))
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        await session.delete(team)
        await session.commit()
        return {"ok": True, "deleted": team.name}


@router.post("/teams/sync", dependencies=[Depends(auth_dependency)])
async def sync_teams_from_linear(body: SyncTeamsBody):
    """Fetch all teams from Linear and upsert them. Preserves existing descriptions."""
    import httpx

    from ..config import settings

    token = body.token or settings.linear_api_token
    if not token:
        raise HTTPException(status_code=400, detail="No Linear token provided and none configured on server")

    query = '{ teams { nodes { id name } } }'
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.linear.app/graphql",
            headers={"Authorization": token, "Content-Type": "application/json"},
            json={"query": query},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

    nodes = data.get("data", {}).get("teams", {}).get("nodes", [])
    if not nodes:
        raise HTTPException(status_code=400, detail="No teams found. Check your Linear API token.")

    created = 0
    updated = 0

    async for session in get_session():
        for node in nodes:
            existing_result = await session.execute(
                select(LinearTeam).where(LinearTeam.linear_id == node["id"])
            )
            existing = existing_result.scalar_one_or_none()

            desc_override = (body.descriptions or {}).get(node["name"])

            if existing:
                if desc_override:
                    existing.description = desc_override
                    existing.updated_at = datetime.now(timezone.utc)
                    updated += 1
            else:
                desc = desc_override or f"Team '{node['name']}' (add a description to help agents route tickets)"
                team = LinearTeam(
                    linear_id=node["id"],
                    name=node["name"],
                    description=desc,
                )
                session.add(team)
                created += 1

        await session.commit()

    return {"ok": True, "total": len(nodes), "created": created, "updated": updated}


@router.get("/teams/context/summary", dependencies=[Depends(auth_dependency)])
async def get_teams_context():
    """Return team summaries for agent context. Agents use this to decide which team to push to."""
    async for session in get_session():
        result = await session.execute(
            select(LinearTeam).order_by(LinearTeam.name)
        )
        teams = result.scalars().all()
        return {
            "teams": [
                {
                    "linearId": t.linear_id,
                    "name": t.name,
                    "description": t.description,
                }
                for t in teams
            ]
        }
