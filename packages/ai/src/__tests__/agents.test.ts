import { describe, it, expect } from 'bun:test'
import { AgentOutputSchema, SupervisorOutputSchema } from '../agents/types'

describe('Agent output schemas', () => {
  describe('AgentOutputSchema', () => {
    it('validates valid output', () => {
      const validOutput = {
        revisedDoc: '# User Story\n\nAs a user...',
        critique: 'Looks good',
        riskFlags: [],
        confidence: 0.8,
        ready: false,
      }
      const result = AgentOutputSchema.safeParse(validOutput)
      expect(result.success).toBe(true)
    })

    it('validates output with revisedDoc required', () => {
      const validOutput = {
        revisedDoc: 'Revised document content',
        critique: 'Needs improvement',
        riskFlags: ['missing_nfrs'],
        confidence: 0.5,
        ready: false,
      }
      const result = AgentOutputSchema.safeParse(validOutput)
      expect(result.success).toBe(true)
    })

    it('rejects missing required fields', () => {
      const invalidOutput = { critique: 'Missing fields' }
      const result = AgentOutputSchema.safeParse(invalidOutput)
      expect(result.success).toBe(false)
    })

    it('rejects confidence out of range', () => {
      const invalidOutput = {
        critique: 'Bad confidence',
        riskFlags: [],
        confidence: 1.5, // max is 1.0
        ready: true,
      }
      const result = AgentOutputSchema.safeParse(invalidOutput)
      expect(result.success).toBe(false)
    })
  })

  describe('SupervisorOutputSchema', () => {
    it('validates valid output', () => {
      const validOutput = {
        ready: true,
        reason: 'Resolved all issues',
        forceStop: false,
        qualityScore: 85,
      }
      const result = SupervisorOutputSchema.safeParse(validOutput)
      expect(result.success).toBe(true)
    })

    it('validates output without optional qualityScore', () => {
      const validOutput = {
        ready: false,
        reason: 'More iterations needed',
        forceStop: false,
      }
      const result = SupervisorOutputSchema.safeParse(validOutput)
      expect(result.success).toBe(true)
    })

    it('rejects missing reason', () => {
      const invalidOutput = {
        ready: true,
        forceStop: false,
      }
      const result = SupervisorOutputSchema.safeParse(invalidOutput)
      expect(result.success).toBe(false)
    })

    it('rejects qualityScore out of range', () => {
      const invalidOutput = {
        ready: true,
        reason: 'Done',
        forceStop: false,
        qualityScore: 150, // max is 100
      }
      const result = SupervisorOutputSchema.safeParse(invalidOutput)
      expect(result.success).toBe(false)
    })
  })
})
