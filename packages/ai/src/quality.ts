/**
 * Quality scoring engine — INTERNAL USE ONLY.
 * Quality scores are NEVER pushed to Linear.
 */

import type { QualityFlag, QualityScore } from '@gamole/types'

import type { AgentOutput, SupervisorOutput } from './agents/types'

/**
 * Quality flag constants mapped to QualityFlag enum values.
 * Internal use only — never exposed to external systems (e.g. Linear).
 */
export const QualityFlags = {
  MISSING_AC: 'missing_nfrs' as QualityFlag,
  AMBIGUOUS_SCOPE: 'ambiguous_acceptance_criteria' as QualityFlag,
  TECH_RISK: 'high_overlap_risk' as QualityFlag,
  BUSINESS_RISK: 'below_quality_threshold' as QualityFlag,
  LOW_CONFIDENCE: 'low_grounding_coverage' as QualityFlag,
} as const

/**
 * Compute an internal quality score from agent outputs and supervisor output.
 *
 * Score breakdown (resulting in 0-10 range per QualityScore schema):
 * - Supervisor qualityScore (0-100): 50% weight
 * - Average agent confidence (0-1 → 0-100): 30% weight
 * - Flag count penalty (0-20): 20% weight
 *
 * INTERNAL ONLY — quality scores are never pushed to Linear.
 */
export function computeQualityScore(
  agentOutputs: AgentOutput[],
  supervisorOutput: SupervisorOutput,
): QualityScore {
  const avgConfidence =
    agentOutputs.reduce((sum, a) => sum + a.confidence, 0) / (agentOutputs.length || 1)

  const allRawFlags = agentOutputs.flatMap((a) => a.riskFlags)
  const uniqueRawFlags = [...new Set(allRawFlags)]

  // Penalty: 5 points per unique raw flag, capped at 20
  const flagPenalty = Math.min(uniqueRawFlags.length * 5, 20)

  // Supervisor qualityScore defaults to 70 if not provided
  const supervisorScore = supervisorOutput.qualityScore ?? 70

  // Compute composite score in 0-100 range
  const score100 = Math.round(
    supervisorScore * 0.5 + avgConfidence * 100 * 0.3 + (100 - flagPenalty) * 0.2,
  )

  // Generate typed quality flags based on analysis heuristics
  const typedFlags = new Set<QualityFlag>()

  if (avgConfidence < 0.6) {
    typedFlags.add(QualityFlags.LOW_CONFIDENCE)
  }

  if (score100 < 50) {
    typedFlags.add(QualityFlags.BUSINESS_RISK)
  }

  if (uniqueRawFlags.length > 2) {
    typedFlags.add(QualityFlags.TECH_RISK)
  }

  // Scale composite score from 0-100 to 0-10 (schema constraint)
  const score = Math.max(0, Math.min(10, score100 / 10))

  return {
    score,
    flags: [...typedFlags],
    details: {
      avgConfidence,
      supervisorScore,
      flagCount: uniqueRawFlags.length,
      agentCount: agentOutputs.length,
      rawFlags: uniqueRawFlags,
    },
  }
}
