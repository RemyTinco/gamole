import { describe, it, expect } from 'bun:test'
import { computeQualityScore } from '../quality'
import type { AgentOutput, SupervisorOutput } from '../agents/types'

describe('Quality scoring', () => {
  it('returns score in 0-10 range', () => {
    const agentOutputs: AgentOutput[] = [
      {
        revisedDoc: 'test revised doc',
        critique: 'Looks good overall',
        riskFlags: [],
        confidence: 0.8,
        ready: true,
      },
    ]
    const supervisorOutput: SupervisorOutput = {
      ready: true,
      reason: 'Quality acceptable',
      forceStop: false,
      qualityScore: 80,
    }

    const score = computeQualityScore(agentOutputs, supervisorOutput)
    expect(score.score).toBeGreaterThanOrEqual(0)
    expect(score.score).toBeLessThanOrEqual(10)
  })

  it('returns flags array', () => {
    const agentOutputs: AgentOutput[] = [
      {
        revisedDoc: 'test revised doc',
        critique: 'ok',
        riskFlags: [],
        confidence: 0.9,
        ready: true,
      },
    ]
    const supervisorOutput: SupervisorOutput = {
      ready: true,
      reason: 'All good',
      forceStop: false,
      qualityScore: 90,
    }

    const result = computeQualityScore(agentOutputs, supervisorOutput)
    expect(Array.isArray(result.flags)).toBe(true)
  })

  it('flags below_quality_threshold when score is low', () => {
    const agentOutputs: AgentOutput[] = [
      {
        revisedDoc: 'test revised doc',
        critique: 'terrible quality, needs complete rework',
        riskFlags: ['TECH_RISK', 'BUSINESS_RISK', 'MISSING_AC'],
        confidence: 0.1,
        ready: false,
      },
    ]
    const supervisorOutput: SupervisorOutput = {
      ready: false,
      reason: 'Very low quality',
      forceStop: true,
      qualityScore: 20,
    }

    const result = computeQualityScore(agentOutputs, supervisorOutput)
    // Score should be low with bad confidence (0.1) and low supervisor score (20)
    // score100 = 20*0.5 + 0.1*100*0.3 + (100-15)*0.2 = 10 + 3 + 17 = 30
    // score = 3.0 → well below 7
    expect(result.score).toBeLessThan(7)
  })

  it('assigns LOW_CONFIDENCE flag when confidence is below 0.6', () => {
    const agentOutputs: AgentOutput[] = [
      {
        revisedDoc: 'test revised doc',
        critique: 'uncertain about requirements',
        riskFlags: [],
        confidence: 0.3,
        ready: false,
      },
    ]
    const supervisorOutput: SupervisorOutput = {
      ready: false,
      reason: 'Low confidence',
      forceStop: false,
      qualityScore: 70,
    }

    const result = computeQualityScore(agentOutputs, supervisorOutput)
    expect(result.flags).toContain('low_grounding_coverage')
  })

  it('returns higher score for high confidence and supervisor score', () => {
    const agentOutputs: AgentOutput[] = [
      {
        revisedDoc: 'test revised doc',
        critique: 'Excellent requirements',
        riskFlags: [],
        confidence: 0.95,
        ready: true,
      },
    ]
    const supervisorOutput: SupervisorOutput = {
      ready: true,
      reason: 'Ready to ship',
      forceStop: false,
      qualityScore: 95,
    }

    const highResult = computeQualityScore(agentOutputs, supervisorOutput)

    const lowAgentOutputs: AgentOutput[] = [
      {
        revisedDoc: 'test revised doc',
        critique: 'Poor requirements',
        riskFlags: ['TECH_RISK'],
        confidence: 0.2,
        ready: false,
      },
    ]
    const lowSupervisorOutput: SupervisorOutput = {
      ready: false,
      reason: 'Needs work',
      forceStop: false,
      qualityScore: 30,
    }

    const lowResult = computeQualityScore(lowAgentOutputs, lowSupervisorOutput)
    expect(highResult.score).toBeGreaterThan(lowResult.score)
  })
})
