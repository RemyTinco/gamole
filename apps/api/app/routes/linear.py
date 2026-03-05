"""Linear endpoints: validate and push structured output to Linear."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from gamole_types import GeneratedOutput, LinearPushConfig

from ..auth.middleware import auth_dependency
from ..config import settings

router = APIRouter()


class ValidateBody(BaseModel):
    output: GeneratedOutput
    config: LinearPushConfig = Field(default_factory=LinearPushConfig)

    model_config = {"populate_by_name": True}


class PushBody(BaseModel):
    output: GeneratedOutput
    config: LinearPushConfig = Field(default_factory=LinearPushConfig)
    token: str | None = None

    model_config = {"populate_by_name": True}


class PushFromGenerationBody(BaseModel):
    generation_id: str = Field(alias="generationId")
    config: LinearPushConfig = Field(default_factory=LinearPushConfig)
    token: str | None = None

    model_config = {"populate_by_name": True}

@router.post("/linear/validate", dependencies=[Depends(auth_dependency)])
async def validate_push(body: ValidateBody):
    """Pre-push validation: count issues that would be created."""
    issues_count = sum(len(epic.stories) + 1 for epic in body.output.epics)
    stories_count = sum(len(epic.stories) for epic in body.output.epics)
    return {
        "ok": True,
        "epicCount": len(body.output.epics),
        "storyCount": stories_count,
        "issueCount": issues_count,
    }


@router.post("/linear/push", dependencies=[Depends(auth_dependency)])
async def push_to_linear_endpoint(body: PushBody):
    """Push pre-structured output to Linear. Teams resolved per-epic from AI recommendations."""
    from gamole_linear.push import push_to_linear

    token = body.token or settings.linear_api_token
    if not token:
        raise HTTPException(
            status_code=400,
            detail="No Linear token provided and none configured (LINEAR_API_TOKEN env)",
        )

    result = await push_to_linear(body.output, body.config, token)
    return result.model_dump(by_alias=True)


@router.post("/linear/push-generation", dependencies=[Depends(auth_dependency)])
async def push_generation_to_linear(body: PushFromGenerationBody):
    """Push a completed generation's structured output directly to Linear."""
    import json
    import uuid as _uuid

    from gamole_db import Workflow, get_session
    from gamole_db.models import DocumentVersion as DocumentVersionModel

    token = body.token or settings.linear_api_token
    if not token:
        raise HTTPException(
            status_code=400,
            detail="No Linear token provided and none configured (LINEAR_API_TOKEN env)",
        )

    async for session in get_session():
        wf = await session.get(Workflow, _uuid.UUID(body.generation_id))
        if not wf:
            raise HTTPException(status_code=404, detail="Generation not found")
        if wf.status not in ("READY_TO_PUSH", "PUSHED_TO_LINEAR"):
            raise HTTPException(status_code=400, detail=f"Generation is {wf.status}, not ready to push")
        if not wf.structured_output:
            raise HTTPException(status_code=400, detail="No structured output available")

        output = GeneratedOutput(**wf.structured_output)

        from gamole_linear.push import push_to_linear

        result = await push_to_linear(output, body.config, token)

        # Store original generated stories as AI_FINAL document version
        dv = DocumentVersionModel(
            workflow_id=wf.id,
            type="AI_FINAL",
            content_markdown=json.dumps(wf.structured_output),
        )
        session.add(dv)
        wf.status = "PUSHED_TO_LINEAR"
        await session.commit()

        return result.model_dump(by_alias=True)
