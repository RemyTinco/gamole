import { AgentResultSchema } from '@gamole/types'
import { z } from 'zod'

export const MAX_CRITIQUE_ROUNDS = 5
export const FLASH_MODEL = 'gemini-2.0-flash'

export const AgentInputSchema = z.object({
  document: z.string(),
  context: z.string(),
  round: z.number().int().min(1),
  previousCritiques: z.array(z.string()).optional(),
})

export type AgentInput = z.infer<typeof AgentInputSchema>

export const AgentOutputSchema = AgentResultSchema.pick({
  revisedDoc: true,
  critique: true,
  riskFlags: true,
  confidence: true,
})
  .partial({ revisedDoc: true })
  .extend({
    ready: z.boolean(),
  })

export type AgentOutput = z.infer<typeof AgentOutputSchema>

export const SupervisorOutputSchema = z.object({
  ready: z.boolean(),
  reason: z.string(),
  forceStop: z.boolean(),
  qualityScore: z.number().min(0).max(100).optional(),
})

export type SupervisorOutput = z.infer<typeof SupervisorOutputSchema>

export type AgentContext = {
  name: 'draft' | 'qa' | 'dev' | 'po' | 'supervisor'
  model: string
  maxRounds: number
}

export function hasGoogleApiKey(): boolean {
  const apiKey = process.env.GOOGLE_GENERATIVE_AI_API_KEY
  return typeof apiKey === 'string' && apiKey.startsWith('AIza')
}

export function critiquesToText(critiques: string[] | undefined): string {
  if (!critiques || critiques.length === 0) {
    return 'None'
  }

  return critiques.map((critique, index) => `${index + 1}. ${critique}`).join('\n')
}
