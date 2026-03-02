"""Tests for the structurer agent."""

import pytest

from gamole_ai.agents.structurer import run as run_structurer
from gamole_types.schemas.generated import GeneratedOutput


@pytest.mark.asyncio
async def test_structurer_mock_output():
    """Without API key, returns mock structured output."""
    import os

    old = os.environ.pop("GOOGLE_GENERATIVE_AI_API_KEY", None)
    try:
        result = await run_structurer("Some refined document about password reset")
        assert isinstance(result, GeneratedOutput)
        assert len(result.epics) >= 1
        assert len(result.epics[0].stories) >= 1
        assert result.epics[0].stories[0].title
    finally:
        if old:
            os.environ["GOOGLE_GENERATIVE_AI_API_KEY"] = old


@pytest.mark.asyncio
async def test_structurer_output_has_acceptance_criteria():
    """Structured output stories include acceptance criteria."""
    import os

    old = os.environ.pop("GOOGLE_GENERATIVE_AI_API_KEY", None)
    try:
        result = await run_structurer("Build a login page with OAuth support")
        story = result.epics[0].stories[0]
        assert isinstance(story.acceptance_criteria, list)
        assert len(story.acceptance_criteria) >= 1
    finally:
        if old:
            os.environ["GOOGLE_GENERATIVE_AI_API_KEY"] = old
