"""Agent tests (mock mode — no API key)."""

import pytest

from gamole_ai.agents.types import AgentInput


@pytest.fixture
def sample_input():
    return AgentInput(
        document="As a user, I want to login so that I can access my account.",
        context="Auth system context",
        round=1,
        previous_critiques=None,
    )


@pytest.mark.asyncio
async def test_draft_agent_mock(sample_input):
    from gamole_ai.agents.draft import run

    result = await run(sample_input)
    assert result.critique
    assert result.confidence > 0
    assert result.revised_doc is not None


@pytest.mark.asyncio
async def test_qa_agent_mock(sample_input):
    from gamole_ai.agents.qa import run

    result = await run(sample_input)
    assert result.critique
    assert result.confidence > 0


@pytest.mark.asyncio
async def test_dev_agent_mock(sample_input):
    from gamole_ai.agents.dev import run

    result = await run(sample_input)
    assert result.critique
    assert result.confidence > 0


@pytest.mark.asyncio
async def test_po_agent_mock(sample_input):
    from gamole_ai.agents.po import run

    result = await run(sample_input)
    assert result.critique
    assert result.confidence > 0


@pytest.mark.asyncio
async def test_supervisor_agent_mock(sample_input):
    from gamole_ai.agents.supervisor import run

    result = await run(sample_input)
    assert result.reason
    assert isinstance(result.ready, bool)


@pytest.mark.asyncio
async def test_supervisor_force_stop_at_max_rounds(sample_input):
    from gamole_ai.agents.supervisor import run

    sample_input.round = 5
    result = await run(sample_input)
    assert result.ready is True
    assert result.force_stop is True
