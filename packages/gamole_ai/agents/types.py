"""Agent types - ported from packages/ai/src/agents/types.ts."""

import os

from pydantic import BaseModel, Field

MAX_CRITIQUE_ROUNDS = 5
FLASH_MODEL = "gemini-2.5-flash"


class AgentInput(BaseModel):
    document: str
    context: str
    round: int = Field(ge=1)
    previous_critiques: list[str] | None = None


class AgentOutput(BaseModel):
    revised_doc: str | None = None
    critique: str
    risk_flags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    ready: bool = False


class SupervisorOutput(BaseModel):
    ready: bool
    reason: str
    force_stop: bool = False
    quality_score: float | None = Field(default=None, ge=0, le=100)


def has_google_api_key() -> bool:
    api_key = os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY", "")
    return api_key.startswith("AIza")


def critiques_to_text(critiques: list[str] | None) -> str:
    if not critiques:
        return "None"
    return "\n".join(f"{i + 1}. {c}" for i, c in enumerate(critiques))
