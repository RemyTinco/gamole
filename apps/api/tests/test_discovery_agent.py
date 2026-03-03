"""Discovery agent tests (mock mode — no API key)."""

import pytest


@pytest.mark.asyncio
async def test_generate_questions_returns_3_to_7():
    """Mock mode returns between 3 and 7 questions."""
    from gamole_ai.agents.discovery import generate_questions

    result = await generate_questions("Add dark mode to settings", "{}")
    assert 3 <= len(result.questions) <= 7


@pytest.mark.asyncio
async def test_generate_questions_each_has_id_and_text():
    """Each returned question must have a non-empty id and text."""
    from gamole_ai.agents.discovery import generate_questions

    result = await generate_questions("Add dark mode", "{}")
    for q in result.questions:
        assert q.id
        assert q.text


@pytest.mark.asyncio
async def test_enrich_document_returns_longer_text():
    """Enriched document must be longer than the original input."""
    from gamole_ai.agents.discovery import enrich_document, generate_questions
    from gamole_types.schemas.discovery import DiscoveryAnswer, DiscoveryEnrichmentInput

    questions_result = await generate_questions("Add dark mode", "{}")
    inp = DiscoveryEnrichmentInput(
        original_input="Add dark mode",
        context="{}",
        questions=questions_result.questions,
        answers=[
            DiscoveryAnswer(question_id=q.id, answer="test answer")
            for q in questions_result.questions
        ],
    )
    result = await enrich_document(inp)
    assert len(result.enriched_document) > len("Add dark mode")


@pytest.mark.asyncio
async def test_generate_questions_with_empty_context():
    """generate_questions should work even when context is an empty string."""
    from gamole_ai.agents.discovery import generate_questions

    result = await generate_questions("Add feature X", "")
    assert len(result.questions) >= 3
