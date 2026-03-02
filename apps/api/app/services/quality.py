"""Quality service - wraps the quality scoring engine."""

from gamole_ai.agents.types import AgentOutput, SupervisorOutput
from gamole_ai.quality import compute_quality_score
from gamole_types.schemas.quality import QualityScore


async def evaluate_quality(
    agent_outputs: list[AgentOutput],
    supervisor_output: SupervisorOutput,
) -> QualityScore:
    """Compute quality score from agent and supervisor outputs."""
    return compute_quality_score(agent_outputs, supervisor_output)
