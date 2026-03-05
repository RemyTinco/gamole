export interface Generation {
  id: string
  status: string
  createdAt: string
  structuredOutput?: GeneratedOutput | null
  document?: string | null
  error?: string | null
  costBreakdown?: CostBreakdown | null
  input?: string | null
  discoveryQuestions?: DiscoveryQuestion[] | null
  qualityScore?: number | null
}

export interface GeneratedOutput {
  epics: GeneratedEpic[]
  projectName?: string | null
  overallNotes?: string | null
}

export interface GeneratedEpic {
  epicTitle: string
  epicDescription: string
  teamName?: string | null
  teamReason?: string | null
  stories: GeneratedStory[]
}

export interface GeneratedStory {
  title: string
  description: string
  acceptanceCriteria: string[]
  assumptions: string[]
  technicalNotes?: string | null
}

export interface CostBreakdown {
  totalInputTokens: number
  totalOutputTokens: number
  totalCostUsd: number
  perAgent: Record<string, { inputTokens: number; outputTokens: number; costUsd: number }>
}

export interface DiscoveryQuestion {
  id: string
  text: string
  placeholder?: string | null
}

export interface DiscoveryAnswer {
  questionId: string
  answer: string
}

export interface GenerationEvent {
  type: "status" | "progress" | "user_edit_required" | "complete" | "error" | "heartbeat" | "discovery_questions" | "trace"
  data: Record<string, unknown>
  timestamp: string
}

export interface TraceEvent {
  id: string
  workflowId: string
  agentName: string
  eventType: string
  roundNumber: number
  promptText?: string | null
  responseText?: string | null
  modelName?: string | null
  latencyMs?: number | null
  tokenIn?: number | null
  tokenOut?: number | null
  costUsd?: number | null
  success: boolean
  errorType?: string | null
  critiqueMarkdown?: string | null
  metadataJson?: Record<string, unknown> | null
  createdAt: string
}

export interface TraceEventSummary {
  id: string
  workflowId: string
  agentName: string
  eventType: string
  roundNumber: number
  modelName?: string | null
  latencyMs?: number | null
  tokenIn?: number | null
  tokenOut?: number | null
  costUsd?: number | null
  success: boolean
  createdAt: string
}

export interface Repository {
  id: string
  name: string
  url: string
  branch?: string | null
  description: string
  languages?: string[] | null
  indexedAt?: string | null
  fileCount: number
  chunkCount: number
  createdAt: string
  indexingStatus?: string | null
  indexingError?: string | null
}

export interface GitHubRepo {
  fullName: string
  url: string
  description: string
  language?: string | null
  defaultBranch: string
  private: boolean
  updatedAt?: string
}

export interface Team {
  id: string
  linearId: string
  name: string
  description: string
  defaultStateId?: string | null
  defaultLabels?: string[] | null
  createdAt: string
}

export interface ChatMessage {
  role: "user" | "assistant"
  content: string
  sources?: Array<{ query: string; result: Record<string, unknown> }>
}

export interface ChatResponse {
  answer: string
  sources: Array<{ query: string; result: Record<string, unknown> }>
  queryType: string
}

export interface SyncStatus {
  lastSyncedAt: string | null
  cachedIssueCount: number
  lastSyncMetadata: Record<string, unknown> | null
}

