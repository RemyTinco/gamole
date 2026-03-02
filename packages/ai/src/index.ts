export {
  EMBEDDING_DIMENSIONS,
  embedText,
  embedBatch,
  chunkText,
} from './embeddings'

export { indexRepository, REPO_LIMIT_ERROR_PREFIX } from './codebase/index'
export type { IndexStats } from './codebase/index'
export { classifyFile, isSecretFile, ALLOWED_EXTENSIONS } from './codebase/classifier'
export type { FileClassification } from './codebase/classifier'

export {
  runDraftAgent,
  runQAAgent,
  runDevAgent,
  runPOAgent,
  runSupervisorAgent,
  AgentInputSchema,
  AgentOutputSchema,
  SupervisorOutputSchema,
  MAX_CRITIQUE_ROUNDS,
} from './agents'

export type {
  AgentContext,
  AgentInput,
  AgentOutput,
  SupervisorOutput,
} from './agents'

export { retrieveContext } from './retrieval'
export type { RetrieveContextOptions } from './retrieval'

export { detectOverlaps } from './overlap'
export type { OverlapResult } from './overlap'

export { computeQualityScore, QualityFlags } from './quality'
