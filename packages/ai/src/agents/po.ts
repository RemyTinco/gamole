import { google } from '@ai-sdk/google'
import { generateObject } from 'ai'

import {
  AgentInput,
  AgentOutput,
  AgentOutputSchema,
  FLASH_MODEL,
  critiquesToText,
  hasGoogleApiKey,
} from './types'

const PO_AGENT_PROMPT = `You are a product owner reviewing user stories for business value.
Check: Does this align with business goals? Is the priority justified?
Are there simpler alternatives? Provide critique and business risk flags.`

function buildFallback(critique: string): AgentOutput {
  return AgentOutputSchema.parse({
    critique,
    riskFlags: [],
    confidence: 0.75,
    ready: false,
  })
}

export async function run(input: AgentInput): Promise<AgentOutput> {
  if (!hasGoogleApiKey()) {
    return buildFallback('Mock PO critique generated because GOOGLE_GENERATIVE_AI_API_KEY is unavailable.')
  }

  const prompt = [
    `Document:\n${input.document}`,
    `Context:\n${input.context}`,
    `Round: ${input.round}`,
    `Previous critiques:\n${critiquesToText(input.previousCritiques)}`,
  ].join('\n\n')

  try {
    const { object } = await generateObject({
      model: google(FLASH_MODEL),
      output: 'object',
      schema: AgentOutputSchema,
      system: PO_AGENT_PROMPT,
      prompt,
    })

    return AgentOutputSchema.parse(object)
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return buildFallback(`PO agent fallback after model error: ${message}`)
  }
}
