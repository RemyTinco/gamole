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

const DRAFT_AGENT_PROMPT = `You are a senior product manager specializing in agile requirements.
Given a feature request and context, generate clear, delivery-ready user stories
in the format: As a [user], I want [action] so that [benefit]. Include acceptance
criteria, technical notes, and out-of-scope items.`

function buildFallback(input: AgentInput, critique: string): AgentOutput {
  return AgentOutputSchema.parse({
    revisedDoc: input.document || 'Mock draft user story output',
    critique,
    riskFlags: [],
    confidence: 0.8,
    ready: false,
  })
}

export async function run(input: AgentInput): Promise<AgentOutput> {
  if (!hasGoogleApiKey()) {
    return buildFallback(input, 'Mock draft generated because GOOGLE_GENERATIVE_AI_API_KEY is unavailable.')
  }

  const prompt = [
    `Feature request:\n${input.document}`,
    `Context:\n${input.context}`,
    `Round: ${input.round}`,
    `Previous critiques:\n${critiquesToText(input.previousCritiques)}`,
  ].join('\n\n')

  try {
    const { object } = await generateObject({
      model: google(FLASH_MODEL),
      output: 'object',
      schema: AgentOutputSchema,
      system: DRAFT_AGENT_PROMPT,
      prompt,
    })

    const parsed = AgentOutputSchema.parse(object)
    return {
      ...parsed,
      revisedDoc: parsed.revisedDoc ?? input.document,
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return buildFallback(input, `Draft agent fallback after model error: ${message}`)
  }
}
