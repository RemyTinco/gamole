"""Workflow schemas - ported from packages/types/src/schemas/workflow.ts."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class WorkflowStatus(StrEnum):
    INITIALIZED = "INITIALIZED"
    CONTEXT_RETRIEVED = "CONTEXT_RETRIEVED"
    DRAFT_GENERATED = "DRAFT_GENERATED"
    QA_REVIEWED = "QA_REVIEWED"
    DEV_REVIEWED = "DEV_REVIEWED"
    PO_REVIEWED = "PO_REVIEWED"
    SUPERVISOR_REFINED = "SUPERVISOR_REFINED"
    QUALITY_EVALUATED = "QUALITY_EVALUATED"
    APPROVED_FINAL_AI = "APPROVED_FINAL_AI"
    USER_EDITING = "USER_EDITING"
    READY_TO_PUSH = "READY_TO_PUSH"
    PUSHED_TO_LINEAR = "PUSHED_TO_LINEAR"
    FAILED = "FAILED"


class WorkflowInput(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    mode: Literal["form", "chat"]
    target_team_id: str = Field(alias="targetTeamId")
    target_project_id: str | None = Field(default=None, alias="targetProjectId")
    labels: list[str] | None = None
    priority: int | None = Field(default=None, ge=0, le=4)

    model_config = {"populate_by_name": True}


class DocumentVersionType(StrEnum):
    AI_FINAL = "AI_FINAL"
    USER_EDITED = "USER_EDITED"


class DocumentVersion(BaseModel):
    id: str | None = None
    workflow_id: str | None = Field(default=None, alias="workflowId")
    type: DocumentVersionType
    content_markdown: str = Field(alias="contentMarkdown")
    created_at: datetime | None = Field(default=None, alias="createdAt")

    model_config = {"populate_by_name": True}
