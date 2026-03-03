"""Discovery step schemas — question generation and document enrichment."""

from pydantic import BaseModel


class DiscoveryQuestion(BaseModel):
    """A question to ask the user during discovery."""

    id: str
    text: str
    placeholder: str | None = None


class DiscoveryAnswer(BaseModel):
    """User's answer to a discovery question."""

    question_id: str
    answer: str


class DiscoveryAnswers(BaseModel):
    """Request body for submitting discovery answers."""

    answers: list[DiscoveryAnswer]


class DiscoveryQuestionsOutput(BaseModel):
    """Output from the discovery question generation agent."""

    questions: list[DiscoveryQuestion]


class DiscoveryEnrichmentInput(BaseModel):
    """Input to the discovery enrichment agent."""

    original_input: str
    context: str
    questions: list[DiscoveryQuestion]
    answers: list[DiscoveryAnswer]


class DiscoveryEnrichmentOutput(BaseModel):
    """Output from the discovery enrichment agent."""

    enriched_document: str
