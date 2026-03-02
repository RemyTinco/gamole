"""Context endpoint - ported from apps/api/src/routes/context.ts."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from gamole_ai.retrieval import RetrieveContextOptions, retrieve_context

from ..auth.middleware import auth_dependency

router = APIRouter()


class ContextBody(BaseModel):
    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, alias="topK")
    team_id: str | None = Field(default=None, alias="teamId")

    model_config = {"populate_by_name": True}


@router.post("/context", dependencies=[Depends(auth_dependency)])
async def get_context(body: ContextBody):
    options = RetrieveContextOptions(
        top_k=body.top_k or 5,
        team_id=body.team_id,
    )
    bundle = await retrieve_context(body.query, options)
    return bundle.model_dump(by_alias=True)
