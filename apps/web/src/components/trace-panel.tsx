"use client"

import * as React from "react"
import {
  Play,
  CheckCircle,
  Search,
  Brain,
  AlertCircle,
  Circle,
  ChevronDown,
  ChevronRight,
  Bug,
} from "lucide-react"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { getGenerationTraces } from "@/lib/api-client"
import type { TraceEvent, TraceEventSummary } from "@/lib/types"

// ─── Props ────────────────────────────────────────────────────────────────────

interface TracePanelProps {
  generationId: string
  isOpen: boolean
  onClose: () => void
  liveTraceEvents: TraceEventSummary[]
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function EventIcon({ eventType }: { eventType: string }) {
  if (eventType === "supervisor_decision") {
    return <Brain className="h-4 w-4 text-purple-500 shrink-0" />
  }
  if (eventType === "error") {
    return <AlertCircle className="h-4 w-4 text-red-500 shrink-0" />
  }
  if (eventType.startsWith("retrieval_")) {
    return <Search className="h-4 w-4 text-amber-500 shrink-0" />
  }
  if (eventType.endsWith("_complete")) {
    return <CheckCircle className="h-4 w-4 text-green-500 shrink-0" />
  }
  if (eventType.endsWith("_start")) {
    return <Play className="h-4 w-4 text-blue-500 shrink-0" />
  }
  return <Circle className="h-4 w-4 text-gray-400 shrink-0" />
}

function eventBadgeClass(eventType: string): string {
  if (eventType === "supervisor_decision") {
    return "border-transparent bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300 hover:bg-purple-100"
  }
  if (eventType === "error") {
    return "border-transparent bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300 hover:bg-red-100"
  }
  if (eventType.startsWith("retrieval_")) {
    return "border-transparent bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300 hover:bg-amber-100"
  }
  if (eventType.endsWith("_complete")) {
    return "border-transparent bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300 hover:bg-green-100"
  }
  if (eventType.endsWith("_start")) {
    return "border-transparent bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 hover:bg-blue-100"
  }
  return ""
}

function formatLatency(ms: number | null | undefined): string {
  if (ms == null) return "—"
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`
  return `${ms}ms`
}

// ─── Timeline Tab ─────────────────────────────────────────────────────────────

function TimelineTab({ events }: { events: Array<TraceEvent | TraceEventSummary> }) {
  if (events.length === 0) {
    return (
      <p className="text-muted-foreground text-sm mt-4">No trace events yet.</p>
    )
  }

  return (
    <div className="space-y-0.5 mt-2">
      {events.map((event) => (
        <div
          key={event.id}
          className="flex items-center gap-2 text-xs py-1.5 px-2 rounded hover:bg-muted/50"
        >
          <EventIcon eventType={event.eventType} />
          <span className="font-medium text-foreground truncate max-w-[90px]">
            {event.agentName}
          </span>
          <Badge
            className={cn(
              "text-[10px] px-1.5 py-0 max-w-[140px] truncate",
              eventBadgeClass(event.eventType)
            )}
          >
            {event.eventType}
          </Badge>
          <span className="ml-auto text-muted-foreground shrink-0">
            {new Date(event.createdAt).toLocaleTimeString()}
          </span>
          <span className="text-muted-foreground shrink-0 w-14 text-right">
            {formatLatency(event.latencyMs)}
          </span>
        </div>
      ))}
    </div>
  )
}

// ─── Agents Tab ───────────────────────────────────────────────────────────────

function AgentsTab({ fullEvents }: { fullEvents: TraceEvent[] }) {
  const [expandedAgents, setExpandedAgents] = React.useState<Set<string>>(new Set())
  const [expandedEvents, setExpandedEvents] = React.useState<Set<string>>(new Set())

  const byAgent = React.useMemo(() => {
    const map = new Map<string, TraceEvent[]>()
    for (const ev of fullEvents) {
      if (!map.has(ev.agentName)) map.set(ev.agentName, [])
      map.get(ev.agentName)!.push(ev)
    }
    return map
  }, [fullEvents])

  if (byAgent.size === 0) {
    return (
      <p className="text-muted-foreground text-sm mt-4">No agent data available.</p>
    )
  }

  const toggleAgent = (name: string) => {
    setExpandedAgents((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  const toggleEvent = (id: string) => {
    setExpandedEvents((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div className="space-y-2 mt-2">
      {Array.from(byAgent.entries()).map(([agentName, events]) => {
        const totalLatency = events.reduce((s, e) => s + (e.latencyMs ?? 0), 0)
        const totalTokens = events.reduce(
          (s, e) => s + (e.tokenIn ?? 0) + (e.tokenOut ?? 0),
          0
        )
        const totalCost = events.reduce((s, e) => s + (e.costUsd ?? 0), 0)
        const isExpanded = expandedAgents.has(agentName)

        return (
          <Card key={agentName} className="overflow-hidden">
            <button
              className="w-full flex items-center gap-2 p-3 hover:bg-muted/50 text-left"
              onClick={() => toggleAgent(agentName)}
            >
              {isExpanded ? (
                <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
              )}
              <span className="font-medium text-sm">{agentName}</span>
              <div className="ml-auto flex items-center gap-3 text-xs text-muted-foreground">
                <span>{events.length} events</span>
                <span>{formatLatency(totalLatency)}</span>
                {totalTokens > 0 && (
                  <span>{totalTokens.toLocaleString()} tok</span>
                )}
                {totalCost > 0 && <span>${totalCost.toFixed(4)}</span>}
              </div>
            </button>

            {isExpanded && (
              <div className="border-t divide-y">
                {events.map((ev) => {
                  const hasContent = ev.promptText || ev.responseText
                  const isEvExpanded = expandedEvents.has(ev.id)

                  return (
                    <div key={ev.id} className="px-3 py-2">
                      <div className="flex items-center gap-2 text-xs">
                        <EventIcon eventType={ev.eventType} />
                        <Badge
                          className={cn(
                            "text-[10px] px-1.5 py-0",
                            eventBadgeClass(ev.eventType)
                          )}
                        >
                          {ev.eventType}
                        </Badge>
                        <span className="text-muted-foreground">
                          {new Date(ev.createdAt).toLocaleTimeString()}
                        </span>
                        <span className="ml-auto text-muted-foreground">
                          {formatLatency(ev.latencyMs)}
                        </span>
                        {hasContent && (
                          <button
                            className="text-muted-foreground hover:text-foreground ml-1"
                            onClick={() => toggleEvent(ev.id)}
                          >
                            {isEvExpanded ? (
                              <ChevronDown className="h-3 w-3" />
                            ) : (
                              <ChevronRight className="h-3 w-3" />
                            )}
                          </button>
                        )}
                      </div>

                      {isEvExpanded && hasContent && (
                        <div className="mt-2 space-y-2">
                          {ev.promptText && (
                            <div>
                              <p className="text-xs font-medium text-muted-foreground mb-1">
                                Prompt
                              </p>
                              <pre className="text-xs whitespace-pre-wrap bg-muted p-2 rounded max-h-48 overflow-y-auto">
                                {ev.promptText}
                              </pre>
                            </div>
                          )}
                          {ev.responseText && (
                            <div>
                              <p className="text-xs font-medium text-muted-foreground mb-1">
                                Response
                              </p>
                              <pre className="text-xs whitespace-pre-wrap bg-muted p-2 rounded max-h-48 overflow-y-auto">
                                {ev.responseText}
                              </pre>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </Card>
        )
      })}
    </div>
  )
}

// ─── Context Tab ──────────────────────────────────────────────────────────────

interface RetrievalMetadata {
  linear_count?: number
  code_count?: number
  linear_artifacts?: Array<{ id: string; title: string; score?: number }>
  code_chunks?: Array<{
    file_path: string
    repository: string
    language: string
    score?: number
  }>
}

function ContextTab({ fullEvents }: { fullEvents: TraceEvent[] }) {
  const retrievalEvents = fullEvents.filter(
    (e) => e.eventType === "retrieval_complete"
  )

  if (retrievalEvents.length === 0) {
    return (
      <p className="text-muted-foreground text-sm mt-4">
        No context data available.
      </p>
    )
  }

  const allLinear: Array<{ id: string; title: string; score?: number }> = []
  const allCode: Array<{
    file_path: string
    repository: string
    language: string
    score?: number
  }> = []

  for (const ev of retrievalEvents) {
    const meta = ev.metadataJson as RetrievalMetadata | null
    if (!meta) continue
    if (meta.linear_artifacts) allLinear.push(...meta.linear_artifacts)
    if (meta.code_chunks) allCode.push(...meta.code_chunks)
  }

  return (
    <div className="space-y-4 mt-2">
      <Card>
        <CardHeader className="p-3 pb-2">
          <CardTitle className="text-sm">
            Linear Issues ({allLinear.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-3 pt-0">
          {allLinear.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              No linear issues retrieved.
            </p>
          ) : (
            <div className="space-y-1">
              {allLinear.map((issue, i) => (
                <div
                  key={`${issue.id}-${i}`}
                  className="flex items-start justify-between gap-2 text-xs py-1"
                >
                  <div className="min-w-0">
                    <span className="font-mono text-muted-foreground mr-1">
                      {issue.id}
                    </span>
                    <span className="break-words">{issue.title}</span>
                  </div>
                  {issue.score != null && (
                    <span className="text-muted-foreground shrink-0">
                      {(issue.score * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="p-3 pb-2">
          <CardTitle className="text-sm">
            Code Chunks ({allCode.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-3 pt-0">
          {allCode.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              No code chunks retrieved.
            </p>
          ) : (
            <div className="space-y-1">
              {allCode.map((chunk, i) => (
                <div
                  key={`${chunk.file_path}-${i}`}
                  className="flex items-start justify-between gap-2 text-xs py-1"
                >
                  <div className="min-w-0">
                    <span className="font-mono text-muted-foreground">
                      {chunk.repository}/
                    </span>
                    <span className="font-mono">{chunk.file_path}</span>
                    {chunk.language && (
                      <Badge className="ml-1 text-[10px] px-1 py-0">
                        {chunk.language}
                      </Badge>
                    )}
                  </div>
                  {chunk.score != null && (
                    <span className="text-muted-foreground shrink-0">
                      {(chunk.score * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

// ─── Cost Tab ─────────────────────────────────────────────────────────────────

function CostTab({ events }: { events: Array<TraceEvent | TraceEventSummary> }) {
  const hasCostData = events.some(
    (e) => e.costUsd != null || e.tokenIn != null || e.tokenOut != null
  )

  if (!hasCostData) {
    return (
      <p className="text-muted-foreground text-sm mt-4">
        No cost data available.
      </p>
    )
  }

  const totalCost = events.reduce((s, e) => s + (e.costUsd ?? 0), 0)
  const totalIn = events.reduce((s, e) => s + (e.tokenIn ?? 0), 0)
  const totalOut = events.reduce((s, e) => s + (e.tokenOut ?? 0), 0)

  const byAgent = new Map<
    string,
    { tokenIn: number; tokenOut: number; costUsd: number }
  >()
  for (const ev of events) {
    const existing = byAgent.get(ev.agentName) ?? {
      tokenIn: 0,
      tokenOut: 0,
      costUsd: 0,
    }
    byAgent.set(ev.agentName, {
      tokenIn: existing.tokenIn + (ev.tokenIn ?? 0),
      tokenOut: existing.tokenOut + (ev.tokenOut ?? 0),
      costUsd: existing.costUsd + (ev.costUsd ?? 0),
    })
  }

  return (
    <div className="space-y-4 mt-2">
      <div className="grid grid-cols-3 gap-3">
        <Card>
          <CardContent className="p-3">
            <p className="text-xs text-muted-foreground">Total Cost</p>
            <p className="text-lg font-semibold">${totalCost.toFixed(4)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3">
            <p className="text-xs text-muted-foreground">Tokens In</p>
            <p className="text-lg font-semibold">{totalIn.toLocaleString()}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3">
            <p className="text-xs text-muted-foreground">Tokens Out</p>
            <p className="text-lg font-semibold">{totalOut.toLocaleString()}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="p-3 pb-2">
          <CardTitle className="text-sm">Per-Agent Breakdown</CardTitle>
        </CardHeader>
        <CardContent className="p-3 pt-0">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-muted-foreground border-b">
                <th className="text-left pb-2 font-medium">Agent</th>
                <th className="text-right pb-2 font-medium">Tokens In</th>
                <th className="text-right pb-2 font-medium">Tokens Out</th>
                <th className="text-right pb-2 font-medium">Cost</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {Array.from(byAgent.entries()).map(([agentName, data]) => (
                <tr key={agentName}>
                  <td className="py-1.5 font-medium">{agentName}</td>
                  <td className="py-1.5 text-right">
                    {data.tokenIn.toLocaleString()}
                  </td>
                  <td className="py-1.5 text-right">
                    {data.tokenOut.toLocaleString()}
                  </td>
                  <td className="py-1.5 text-right">
                    ${data.costUsd.toFixed(4)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function TracePanel({
  generationId,
  isOpen,
  onClose,
  liveTraceEvents,
}: TracePanelProps) {
  const [fullTraces, setFullTraces] = React.useState<TraceEvent[]>([])
  const [loading, setLoading] = React.useState(false)

  React.useEffect(() => {
    if (!isOpen) return
    setLoading(true)
    getGenerationTraces(generationId)
      .then(({ traces }) => setFullTraces(traces))
      .catch(() => setFullTraces([]))
      .finally(() => setLoading(false))
  }, [isOpen, generationId])

  // Merge fetched + live events, deduplicate by id, sort chronologically
  const allEvents: Array<TraceEvent | TraceEventSummary> = React.useMemo(
    () =>
      [
        ...fullTraces,
        ...liveTraceEvents.filter(
          (live) => !fullTraces.some((f) => f.id === live.id)
        ),
      ].sort(
        (a, b) =>
          new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
      ),
    [fullTraces, liveTraceEvents]
  )

  return (
    <Sheet open={isOpen} onOpenChange={onClose}>
      <SheetContent
        side="right"
        className="w-[560px] sm:w-[640px] overflow-y-auto"
      >
        <SheetHeader className="mb-4">
          <SheetTitle className="flex items-center gap-2">
            <Bug className="h-4 w-4" />
            Generation Debug
          </SheetTitle>
        </SheetHeader>

        {loading ? (
          <div className="flex items-center justify-center py-12 text-muted-foreground text-sm">
            Loading trace data…
          </div>
        ) : (
          <Tabs defaultValue="timeline">
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="timeline">Timeline</TabsTrigger>
              <TabsTrigger value="agents">Agents</TabsTrigger>
              <TabsTrigger value="context">Context</TabsTrigger>
              <TabsTrigger value="cost">Cost</TabsTrigger>
            </TabsList>

            <TabsContent value="timeline">
              <TimelineTab events={allEvents} />
            </TabsContent>

            <TabsContent value="agents">
              <AgentsTab fullEvents={fullTraces} />
            </TabsContent>

            <TabsContent value="context">
              <ContextTab fullEvents={fullTraces} />
            </TabsContent>

            <TabsContent value="cost">
              <CostTab events={allEvents} />
            </TabsContent>
          </Tabs>
        )}
      </SheetContent>
    </Sheet>
  )
}
