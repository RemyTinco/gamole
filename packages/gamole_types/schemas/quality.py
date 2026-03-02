"""Quality schemas - ported from packages/types/src/schemas/quality.ts."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class QualityFlag(StrEnum):
    BELOW_QUALITY_THRESHOLD = "below_quality_threshold"
    MISSING_NFRS = "missing_nfrs"
    AMBIGUOUS_ACCEPTANCE_CRITERIA = "ambiguous_acceptance_criteria"
    LOW_GROUNDING_COVERAGE = "low_grounding_coverage"
    HIGH_OVERLAP_RISK = "high_overlap_risk"


class QualityScore(BaseModel):
    score: float = Field(ge=0, le=10)
    flags: list[QualityFlag]
    details: dict[str, Any]
