"""Generated output schemas - ported from packages/types/src/schemas/generated.ts."""

from pydantic import BaseModel, Field


class GeneratedStory(BaseModel):
    title: str
    description: str
    acceptance_criteria: list[str] = Field(alias="acceptanceCriteria")
    assumptions: list[str]
    technical_notes: str | None = Field(default=None, alias="technicalNotes")

    model_config = {"populate_by_name": True}


class GeneratedEpic(BaseModel):
    epic_title: str = Field(alias="epicTitle")
    epic_description: str = Field(alias="epicDescription")
    team_name: str | None = Field(default=None, alias="teamName")
    team_reason: str | None = Field(default=None, alias="teamReason")
    stories: list[GeneratedStory]

    model_config = {"populate_by_name": True}


class GeneratedOutput(BaseModel):
    epics: list[GeneratedEpic]
    project_name: str | None = Field(default=None, alias="projectName")
    overall_notes: str | None = Field(default=None, alias="overallNotes")

    model_config = {"populate_by_name": True}
