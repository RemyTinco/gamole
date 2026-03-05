"""Pydantic v2 schemas for generation trace data."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TraceEvent(BaseModel):
    """Full trace event — includes prompt/response text. Returned by REST API."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    workflow_id: str
    agent_name: str
    event_type: str  # e.g. 'agent_complete', 'retrieval_complete', 'round_start', 'supervisor_decision'
    round_number: int
    prompt_text: str | None = None
    response_text: str | None = None
    model_name: str | None = None
    latency_ms: int | None = None
    token_in: int | None = None
    token_out: int | None = None
    cost_usd: float | None = None
    success: bool = True
    error_type: str | None = None
    critique_markdown: str | None = None
    metadata_json: dict | None = None
    created_at: str


class TraceEventSummary(BaseModel):
    """Lightweight trace event for SSE streaming — NO prompt/response text."""

    model_config = ConfigDict(populate_by_name=True)

    agent_name: str
    event_type: str
    round_number: int
    latency_ms: int | None = None
    token_in: int | None = None
    token_out: int | None = None
    success: bool = True
    timestamp: str
