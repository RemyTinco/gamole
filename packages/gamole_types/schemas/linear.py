"""Linear schemas - ported from packages/types/src/schemas/linear.ts."""

from typing import Literal

from pydantic import BaseModel, Field


class LinearPushConfig(BaseModel):
    team_id: str | None = Field(default=None, alias="teamId")
    project_id: str | None = Field(default=None, alias="projectId")
    labels: list[str] | None = None
    state_id: str | None = Field(default=None, alias="stateId")
    mode: Literal["create", "update"] = "create"
    existing_issue_id: str | None = Field(default=None, alias="existingIssueId")

    model_config = {"populate_by_name": True}


class CreatedIssueInfo(BaseModel):
    linear_id: str = Field(alias="linearId")
    identifier: str
    title: str

    model_config = {"populate_by_name": True}


class CreatedRelationInfo(BaseModel):
    id: str
    type: str


class LinearPushResult(BaseModel):
    created_issues: list[CreatedIssueInfo] = Field(alias="createdIssues")
    created_relations: list[CreatedRelationInfo] = Field(alias="createdRelations")
    errors: list[str]

    model_config = {"populate_by_name": True}
