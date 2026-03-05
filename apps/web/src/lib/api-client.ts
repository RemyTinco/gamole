import ky from "ky"
import type {
  Generation,
  GeneratedOutput,
  Repository,
  GitHubRepo,
  Team,
  ChatResponse,
  SyncStatus,
  TraceEvent,
} from "./types"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3001"

export const api = ky.create({
  prefixUrl: API_BASE,
  timeout: 30000,
  hooks: {
    beforeRequest: [
      (request) => {
        const token =
          typeof window !== "undefined"
            ? localStorage.getItem("gamole_token")
            : null
        if (token) {
          request.headers.set("Authorization", `Bearer ${token}`)
        }
      },
    ],
    afterResponse: [
      (_request, _options, response) => {
        if (response.status === 401 && typeof window !== "undefined") {
          window.location.href = "/login"
        }
      },
    ],
  },
})

// Health
export async function getHealth() {
  return api.get("health").json<{ status: string; timestamp: string; service: string }>()
}

// Generation
export async function startGeneration(input: string) {
  return api.post("api/generation", { json: { input } }).json<{ id: string; status: string }>()
}

export async function listGenerations() {
  return api.get("api/generation").json<{ workflows: Generation[] }>()
}

export async function getGeneration(id: string) {
  return api.get(`api/generation/${id}`).json<Generation>()
}

export async function getGenerationOutput(id: string) {
  return api.get(`api/generation/${id}/output`).json<GeneratedOutput>()
}

export async function getGenerationTraces(id: string) {
  return api.get(`api/generation/${id}/traces`).json<{ traces: TraceEvent[] }>()
}

export async function updateDocument(id: string, document: string) {
  return api.put(`api/generation/${id}/document`, { json: { document } }).json()
}

export async function updateStructuredOutput(id: string, structuredOutput: GeneratedOutput) {
  return api.put(`api/generation/${id}/structured-output`, {
    json: { structured_output: structuredOutput },
  }).json<{ id: string; status: string; structuredOutput: GeneratedOutput }>()
}

export async function finalizeGeneration(id: string) {
  return api.post(`api/generation/${id}/finalize`).json()
}

export async function submitDiscoveryAnswers(id: string, answers: Array<{ question_id: string; answer: string }>) {
  return api.post(`api/generation/${id}/discovery-answers`, { json: { answers } }).json<{ status: string }>()
}

export function streamGeneration(id: string): EventSource {
  const token = typeof window !== "undefined" ? localStorage.getItem("gamole_token") : null
  const url = `${API_BASE}/api/generation/${id}/stream${token ? `?token=${token}` : ""}`
  return new EventSource(url)
}

// Linear

export async function pushToLinear(issues: Record<string, unknown>[]) {
  return api.post("api/linear/push", { json: { issues } }).json()
}

export interface PushConfig {
  teamId?: string
  projectId?: string
  labels?: string[]
  stateId?: string
}

export interface PushResult {
  createdIssues: Array<{ linearId: string; identifier: string; title: string }>
  createdRelations: Array<{ id: string; type: string }>
  errors: string[]
}

export async function pushGeneration(generationId: string, config?: PushConfig) {
  return api.post("api/linear/push-generation", {
    json: { generationId, config: config ?? {} },
  }).json<PushResult>()
}

// Chat
export async function chatLinear(question: string, history?: Array<{ role: string; content: string }>) {
  return api.post("api/chat/linear", { json: { message: question, history } }).json<ChatResponse>()
}

export async function chatSearch(query: string) {
  return api.post("api/chat/search", { json: { message: query } }).json<ChatResponse>()
}

// Repositories
export async function listRepositories() {
  return api.get("api/repositories").json<{ repositories: Repository[] }>()
}

export async function addRepository(data: { url: string; description: string; branch?: string; languages?: string[] }) {
  return api.post("api/repositories", { json: data }).json<Repository>()
}

export async function getRepository(id: string) {
  return api.get(`api/repositories/${id}`).json<Repository>()
}

export async function updateRepository(id: string, data: Partial<Repository>) {
  return api.put(`api/repositories/${id}`, { json: data }).json<Repository>()
}

export async function deleteRepository(id: string) {
  return api.delete(`api/repositories/${id}`).json()
}

export async function indexRepository(id: string) {
  return api.post(`api/repositories/${id}/index`).json()
}

export async function listGithubRepos() {
  return api.get("api/repositories/github/available").json<{ repositories: GitHubRepo[] }>()
}

export async function getContextSummary() {
  return api.get("api/repositories/context/summary").json()
}

// Teams
export async function listTeams() {
  return api.get("api/teams").json<{ teams: Team[] }>()
}

export async function addTeam(data: { linearId: string; name: string; description: string }) {
  return api.post("api/teams", { json: data }).json<Team>()
}

export async function updateTeam(id: string, data: Partial<Team>) {
  return api.put(`api/teams/${id}`, { json: data }).json<Team>()
}

export async function deleteTeam(id: string) {
  return api.delete(`api/teams/${id}`).json()
}

export async function syncTeams() {
  return api.post("api/teams/sync").json<{ teams: Team[] }>()
}

export async function getTeamsContextSummary() {
  return api.get("api/teams/context/summary").json()
}

// Sync
export async function linearSync(full?: boolean) {
  return api.post("api/sync/linear", { json: { forceFull: full ?? false } }).json()
}

export async function getLinearSyncStatus() {
  return api.get("api/sync/linear/status").json<SyncStatus>()
}

export async function setLinearSchedule(intervalHours: number, enabled: boolean) {
  return api.post("api/sync/linear/schedule", { json: { intervalHours, enabled } }).json()
}

export async function getLinearSchedule() {
  return api.get("api/sync/linear/schedule").json<{ intervalHours: number; enabled: boolean }>()
}



// Generic helpers
export async function apiFetch<T = unknown>(path: string): Promise<T> {
  return api.get(path).json<T>()
}

export async function apiPost<T = unknown>(path: string, data?: unknown): Promise<T> {
  return api.post(path, data ? { json: data } : undefined).json<T>()
}

export async function apiPut<T = unknown>(path: string, data?: unknown): Promise<T> {
  return api.put(path, data ? { json: data } : undefined).json<T>()
}
