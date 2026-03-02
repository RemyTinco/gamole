"""Quality scoring tests."""


from gamole_ai.agents.types import AgentOutput, SupervisorOutput
from gamole_ai.quality import compute_quality_score


def test_quality_score_basic():
    agent_outputs = [
        AgentOutput(critique="Good", risk_flags=[], confidence=0.8, ready=False),
        AgentOutput(critique="Fine", risk_flags=[], confidence=0.9, ready=False),
        AgentOutput(critique="OK", risk_flags=[], confidence=0.7, ready=False),
    ]
    supervisor = SupervisorOutput(ready=True, reason="Ready", force_stop=False, quality_score=80)

    result = compute_quality_score(agent_outputs, supervisor)
    assert 0 <= result.score <= 10
    assert isinstance(result.flags, list)
    assert "avgConfidence" in result.details


def test_quality_score_low_confidence():
    agent_outputs = [
        AgentOutput(critique="Weak", risk_flags=["unclear scope"], confidence=0.3, ready=False),
    ]
    supervisor = SupervisorOutput(ready=False, reason="Needs work", force_stop=False, quality_score=30)

    result = compute_quality_score(agent_outputs, supervisor)
    assert result.score < 5
    assert any("low_grounding_coverage" in str(f) for f in result.flags)


def test_quality_score_many_flags():
    agent_outputs = [
        AgentOutput(critique="Bad", risk_flags=["a", "b", "c"], confidence=0.5, ready=False),
    ]
    supervisor = SupervisorOutput(ready=False, reason="Bad", force_stop=False, quality_score=40)

    result = compute_quality_score(agent_outputs, supervisor)
    assert any("high_overlap_risk" in str(f) for f in result.flags)


def test_quality_score_defaults_supervisor():
    """Supervisor score defaults to 70 if not provided."""
    agent_outputs = [
        AgentOutput(critique="OK", risk_flags=[], confidence=0.8, ready=False),
    ]
    supervisor = SupervisorOutput(ready=True, reason="OK", force_stop=False)

    result = compute_quality_score(agent_outputs, supervisor)
    assert result.score > 0
