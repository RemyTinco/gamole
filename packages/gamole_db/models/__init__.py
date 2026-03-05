"""SQLAlchemy 2.0 models - ported from packages/db/src/schema/*.ts.

All 11 tables: users, workspaces, workflows, document_versions, agent_runs,
audit_log, linear_connections, linear_issues_cache, linear_push_events, codebase_chunks.
"""

import uuid as _uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[_uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    workspaces: Mapped[list["Workspace"]] = relationship(back_populates="user", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# workspaces
# ---------------------------------------------------------------------------
class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[_uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
    user_id: Mapped[_uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    template_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    settings_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="workspaces")
    workflows: Mapped[list["Workflow"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")
    linear_connections: Mapped[list["LinearConnection"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# workflows
# ---------------------------------------------------------------------------
WORKFLOW_STATUS_ENUM = Enum(
    "INITIALIZED", "CONTEXT_RETRIEVED", "DRAFT_GENERATED", "QA_REVIEWED",
    "DEV_REVIEWED", "PO_REVIEWED", "SUPERVISOR_REFINED", "QUALITY_EVALUATED",
    "APPROVED_FINAL_AI", "USER_EDITING", "READY_TO_PUSH", "PUSHED_TO_LINEAR", "FAILED",
    "AWAITING_DISCOVERY",
    name="workflow_status",
)


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[_uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
    workspace_id: Mapped[_uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(WORKFLOW_STATUS_ENUM, nullable=False, default="INITIALIZED")
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    input_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="form")
    target_team_id: Mapped[str] = mapped_column(Text, nullable=False)
    target_project_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_flags_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    retrieval_stats_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cost_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    structured_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    document: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # state_json structure for discovery step:
    # {
    #   "discovery": {
    #     "questions": [{"id": "q1", "text": "...", "placeholder": "..."}],
    #     "answers": [{"question_id": "q1", "answer": "..."}],
    #     "context": {...},  # serialized RAG context bundle
    #     "enriched_document": "..."  # document after enrichment
    #   }
    # }
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    workspace: Mapped["Workspace"] = relationship(back_populates="workflows")
    document_versions: Mapped[list["DocumentVersion"]] = relationship(back_populates="workflow", cascade="all, delete-orphan")
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="workflow", cascade="all, delete-orphan")
    push_events: Mapped[list["LinearPushEvent"]] = relationship(back_populates="workflow", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# document_versions
# ---------------------------------------------------------------------------
DOCUMENT_VERSION_TYPE_ENUM = Enum("AI_FINAL", "USER_EDITED", "FEEDBACK", name="document_version_type")


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[_uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
    workflow_id: Mapped[_uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(DOCUMENT_VERSION_TYPE_ENUM, nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    feedback_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    workflow: Mapped["Workflow"] = relationship(back_populates="document_versions")


# ---------------------------------------------------------------------------
# agent_runs
# ---------------------------------------------------------------------------
class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[_uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
    workflow_id: Mapped[_uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    agent_name: Mapped[str] = mapped_column(Text, nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    critique_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="agent_call")
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    workflow: Mapped["Workflow"] = relationship(back_populates="agent_runs")


# ---------------------------------------------------------------------------
# audit_log
# ---------------------------------------------------------------------------
class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[_uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
    workflow_id: Mapped[_uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


# ---------------------------------------------------------------------------
# linear_connections
# ---------------------------------------------------------------------------
class LinearConnection(Base):
    __tablename__ = "linear_connections"

    id: Mapped[_uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
    workspace_id: Mapped[_uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    token_ref: Mapped[str] = mapped_column(Text, nullable=False)
    linear_org_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    workspace: Mapped["Workspace"] = relationship(back_populates="linear_connections")


# ---------------------------------------------------------------------------
# linear_issues_cache
# ---------------------------------------------------------------------------
class LinearIssueCache(Base):
    __tablename__ = "linear_issues_cache"

    id: Mapped[_uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
    linear_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    team_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding = mapped_column(Vector(768), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("linear_issues_embedding_idx", embedding, postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"}),
    )


# ---------------------------------------------------------------------------
# linear_push_events
# ---------------------------------------------------------------------------
PUSH_MODE_ENUM = Enum("create", "update", name="push_mode")


class LinearPushEvent(Base):
    __tablename__ = "linear_push_events"

    id: Mapped[_uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
    workflow_id: Mapped[_uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    linear_issue_id: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(PUSH_MODE_ENUM, nullable=False)
    pushed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    token_ref: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    workflow: Mapped["Workflow"] = relationship(back_populates="push_events")


# ---------------------------------------------------------------------------
# sync_state (tracks last sync timestamps)
# ---------------------------------------------------------------------------
class SyncState(Base):
    __tablename__ = "sync_state"

    id: Mapped[_uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
    key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ---------------------------------------------------------------------------
# linear_teams
# ---------------------------------------------------------------------------
class LinearTeam(Base):
    __tablename__ = "linear_teams"

    id: Mapped[_uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
    linear_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    default_state_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_labels: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


# ---------------------------------------------------------------------------
# repositories
# ---------------------------------------------------------------------------
class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[_uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    branch: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    languages: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    indexing_status: Mapped[str | None] = mapped_column(Text, nullable=True)  # idle, indexing, done, error
    indexing_error: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------------------------
# codebase_chunks
# ---------------------------------------------------------------------------
class CodebaseChunk(Base):
    __tablename__ = "codebase_chunks"

    id: Mapped[_uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
    repo_name: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding = mapped_column(Vector(768), nullable=True)
    last_indexed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    symbol_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parent_symbol: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_tsv = mapped_column(TSVECTOR, nullable=True)

    __table_args__ = (
        Index("codebase_chunks_embedding_idx", embedding, postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("codebase_chunks_tsv_idx", "content_tsv", postgresql_using="gin"),
    )


# ---------------------------------------------------------------------------
# linear_workspace_cache (users, labels, states, projects for chat entity resolution)
# ---------------------------------------------------------------------------
class LinearWorkspaceCache(Base):
    __tablename__ = "linear_workspace_cache"

    id: Mapped[_uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
    key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)  # "users", "labels", "states", "projects"
    data_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
