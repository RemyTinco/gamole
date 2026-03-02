"""Quality scoring engine - ported from packages/ai/src/quality.ts.

Quality scores are NEVER pushed to Linear. INTERNAL USE ONLY.
"""

from gamole_types.schemas.quality import QualityFlag, QualityScore

from .agents.types import AgentOutput, SupervisorOutput


class QualityFlags:
    MISSING_AC = QualityFlag.MISSING_NFRS
    AMBIGUOUS_SCOPE = QualityFlag.AMBIGUOUS_ACCEPTANCE_CRITERIA
    TECH_RISK = QualityFlag.HIGH_OVERLAP_RISK
    BUSINESS_RISK = QualityFlag.BELOW_QUALITY_THRESHOLD
    LOW_CONFIDENCE = QualityFlag.LOW_GROUNDING_COVERAGE


def compute_quality_score(
    agent_outputs: list[AgentOutput],
    supervisor_output: SupervisorOutput,
) -> QualityScore:
    """Compute an internal quality score from agent outputs and supervisor output.

    Score breakdown (resulting in 0-10 range):
    - Supervisor qualityScore (0-100): 50% weight
    - Average agent confidence (0-1 → 0-100): 30% weight
    - Flag count penalty (0-20): 20% weight
    """
    avg_confidence = (
        sum(a.confidence for a in agent_outputs) / len(agent_outputs)
        if agent_outputs
        else 0
    )

    all_raw_flags = [flag for a in agent_outputs for flag in a.risk_flags]
    unique_raw_flags = list(set(all_raw_flags))

    # Penalty: 5 points per unique raw flag, capped at 20
    flag_penalty = min(len(unique_raw_flags) * 5, 20)

    # Supervisor qualityScore defaults to 70 if not provided
    supervisor_score = supervisor_output.quality_score if supervisor_output.quality_score is not None else 70

    # Compute composite score in 0-100 range
    score100 = round(
        supervisor_score * 0.5 + avg_confidence * 100 * 0.3 + (100 - flag_penalty) * 0.2
    )

    # Generate typed quality flags based on analysis heuristics
    typed_flags: set[QualityFlag] = set()

    if avg_confidence < 0.6:
        typed_flags.add(QualityFlags.LOW_CONFIDENCE)

    if score100 < 50:
        typed_flags.add(QualityFlags.BUSINESS_RISK)

    if len(unique_raw_flags) > 2:
        typed_flags.add(QualityFlags.TECH_RISK)

    # Scale composite score from 0-100 to 0-10
    score = max(0, min(10, score100 / 10))

    return QualityScore(
        score=score,
        flags=list(typed_flags),
        details={
            "avgConfidence": avg_confidence,
            "supervisorScore": supervisor_score,
            "flagCount": len(unique_raw_flags),
            "agentCount": len(agent_outputs),
            "rawFlags": unique_raw_flags,
        },
    )
