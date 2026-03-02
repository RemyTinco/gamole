import { google } from '@ai-sdk/google'
import { generateObject } from 'ai'

import {
  AgentInput,
  FLASH_MODEL,
  MAX_CRITIQUE_ROUNDS,
  SupervisorOutput,
  SupervisorOutputSchema,
  critiquesToText,
  hasGoogleApiKey,
} from './types'

const SUPERVISOR_AGENT_PROMPT = `You are a requirements quality supervisor. Review the document
and all critiques. Decide if the output is ready for delivery or needs another
revision round. Force stop after 5 rounds regardless of quality.`

function forceStopOutput(round: number): SupervisorOutput {
  return SupervisorOutputSchema.parse({
    ready: true,
    reason: `Force stop at round ${round} (max ${MAX_CRITIQUE_ROUNDS} rounds).`,
    forceStop: true,
    qualityScore: 0,
  })
}

function mockOutput(reason: string): SupervisorOutput {
  return SupervisorOutputSchema.parse({
    ready: false,
    reason,
    forceStop: false,
    qualityScore: 60,
  })
}

export async function run(input: AgentInput): Promise<SupervisorOutput> {
  if (input.round >= MAX_CRITIQUE_ROUNDS) {
    return forceStopOutput(input.round)
  }

  if (!hasGoogleApiKey()) {
    return mockOutput('Mock supervisor review generated because GOOGLE_GENERATIVE_AI_API_KEY is unavailable.')
  }

  const prompt = [
    `Document:\n${input.document}`,
    `Context:\n${input.context}`,
    `Round: ${input.round}`,
    `All critiques:\n${critiquesToText(input.previousCritiques)}`,
  ].join('\n\n')

  try {
    const { object } = await generateObject({
      model: google(FLASH_MODEL),
      output: 'object',
      schema: SupervisorOutputSchema,
      system: SUPERVISOR_AGENT_PROMPT,
      prompt,
    })

    return SupervisorOutputSchema.parse({
      ...object,
      forceStop: false,
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return mockOutput(`Supervisor fallback after model error: ${message}`)
  }
}
