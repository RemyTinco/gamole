"""Agent schemas - ported from packages/types/src/schemas/agent.ts."""

from pydantic import BaseModel, Field


class LinearArtifact(BaseModel):
    linear_id: str = Field(alias="linearId")
    title: str
    description: str | None = None
    similarity: float
    team_id: str | None = Field(default=None, alias="teamId")

    model_config = {"populate_by_name": True}


class CodeChunk(BaseModel):
    file_path: str = Field(alias="filePath")
    repo_name: str = Field(alias="repoName")
    language: str
    chunk_text: str = Field(alias="chunkText")
    similarity: float
    domain: str | None = None
    artifact_type: str | None = Field(default=None, alias="artifactType")
    symbol_name: str | None = Field(default=None, alias="symbolName")
    parent_symbol: str | None = Field(default=None, alias="parentSymbol")
    score: float | None = Field(default=None)

    model_config = {"populate_by_name": True}


class RepositorySummary(BaseModel):
    name: str
    description: str
    languages: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class ContextBundle(BaseModel):
    linear_artifacts: list[LinearArtifact] = Field(default_factory=list, alias="linearArtifacts")
    code_chunks: list[CodeChunk] = Field(default_factory=list, alias="codeChunks")
    repositories: list[RepositorySummary] = Field(default_factory=list)
    key_facts: list[str] = Field(default_factory=list, alias="keyFacts")
    gaps: list[str] = Field(default_factory=list)
    formatted_context: str | None = Field(default=None, alias="formattedContext")

    model_config = {"populate_by_name": True}


class AgentResult(BaseModel):
    agent_name: str = Field(alias="agentName")
    revised_doc: str = Field(alias="revisedDoc")
    critique: str
    risk_flags: list[str] = Field(alias="riskFlags")
    missing_info_questions: list[str] = Field(alias="missingInfoQuestions")
    confidence: float = Field(ge=0, le=1)
    score: float = Field(ge=0, le=10)

    model_config = {"populate_by_name": True}
