"use client"

import { useState, useEffect, use } from "react"
import useSWR from "swr"
import { getGeneration, updateDocument, finalizeGeneration, submitDiscoveryAnswers } from "@/lib/api-client"
import { useGenerationStream } from "@/hooks/use-generation-stream"
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Editor } from "@/components/editor"
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert"
import { Skeleton } from "@/components/ui/skeleton"
import { Check, Circle, Loader2, Send, Save, ChevronDown, ChevronRight, AlertCircle, DollarSign } from "lucide-react"
import { toast } from "sonner"
import type { Generation, GeneratedEpic } from "@/lib/types"

const PIPELINE_STEPS = ["Retrieve Context", "Discovery", "Draft", "QA/Dev/PO", "Supervisor", "Structure"]

function stepIndex(node: string | null): number {
  if (!node) return -1
  const lower = node.toLowerCase()
  if (lower.includes("retriev") || lower.includes("context")) return 0
  if (lower.includes("discover") || lower.includes("awaiting")) return 1
  if (lower.includes("draft")) return 2
  if (lower.includes("qa") || lower.includes("dev") || lower.includes("po") || lower.includes("review")) return 3
  if (lower.includes("supervis")) return 4
  if (lower.includes("struct")) return 5
  return -1
}

export default function GenerationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const { data: gen, mutate } = useSWR<Generation>(`gen-${id}`, () => getGeneration(id), { refreshInterval: 5000 })
  const stream = useGenerationStream(id)
  const [editDoc, setEditDoc] = useState("")
  const [saving, setSaving] = useState(false)
  const [finalizing, setFinalizing] = useState(false)
  const [costOpen, setCostOpen] = useState(false)
  const [expandedEpics, setExpandedEpics] = useState<Set<number>>(new Set())
  const [discoveryAnswers, setDiscoveryAnswers] = useState<Record<string, string>>({})
  const [submittingDiscovery, setSubmittingDiscovery] = useState(false)

  const status = stream.status !== "connecting" ? stream.status : gen?.status || "Loading"
  const canEditDocument = status === "USER_EDITING" || status === "READY_TO_PUSH"
  const isComplete = ["COMPLETED", "READY_TO_PUSH", "PUSHED_TO_LINEAR", "STRUCTURED"].includes(status) || stream.isComplete
  const isError = status === "ERROR"
  const currentStepIdx = status === "AWAITING_DISCOVERY" ? 1 : stepIndex(stream.currentNode)

  useEffect(() => {
    if (canEditDocument && gen?.document) {
      setEditDoc(gen.document)
    }
  }, [canEditDocument, gen?.document])

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateDocument(id, editDoc)
      toast.success("Document saved")
      mutate()
    } catch { toast.error("Failed to save") }
    setSaving(false)
  }

  const handleFinalize = async () => {
    setFinalizing(true)
    try {
      if (status === "READY_TO_PUSH") {
        await updateDocument(id, editDoc)
      }
      await finalizeGeneration(id)
      toast.success("Generation finalized!")
      mutate()
    } catch { toast.error("Failed to finalize") }
    setFinalizing(false)
  }

  const handleDiscoverySubmit = async () => {
    if (!gen?.discoveryQuestions) return
    setSubmittingDiscovery(true)
    try {
      const answers = gen.discoveryQuestions.map(q => ({
        question_id: q.id,
        answer: discoveryAnswers[q.id] || "",
      }))
      await submitDiscoveryAnswers(id, answers)
      toast.success("Answers submitted! Generating your tickets...")
      mutate()
    } catch {
      toast.error("Failed to submit answers")
    }
    setSubmittingDiscovery(false)
  }


  const toggleEpic = (i: number) => {
    setExpandedEpics((prev) => {
      const next = new Set(prev)
      next.has(i) ? next.delete(i) : next.add(i)
      return next
    })
  }

  if (!gen) {
    return <div className="space-y-4"><Skeleton className="h-8 w-64" /><Skeleton className="h-64 w-full" /></div>
  }

  const output = gen.structuredOutput
  const cost = gen.costBreakdown

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Generation</h1>
          <p className="text-sm text-muted-foreground">{id}</p>
        </div>
        <Badge variant={isComplete ? "default" : isError ? "destructive" : "secondary"} className="text-sm">
          {status}
        </Badge>
      </div>

      {/* Pipeline tracker */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            {PIPELINE_STEPS.map((step, i) => {
              const done = i < currentStepIdx || isComplete
              const active = i === currentStepIdx && !isComplete && !isError
              return (
                <div key={step} className="flex flex-col items-center flex-1">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center border-2 ${
                    done ? "bg-primary text-primary-foreground border-primary" :
                    active ? "border-primary text-primary animate-pulse" :
                    "border-muted text-muted-foreground"
                  }`}>
                    {done ? <Check className="h-4 w-4" /> : active ? <Loader2 className="h-4 w-4 animate-spin" /> : <Circle className="h-3 w-3" />}
                  </div>
                  <span className={`text-xs mt-1 text-center ${active ? "font-medium" : "text-muted-foreground"}`}>{step}</span>
                </div>
              )
            })}
          </div>
          {stream.round > 0 && (
            <div className="flex items-center gap-4 mt-4 text-sm text-muted-foreground">
              <span>Round {stream.round}/5</span>
              {stream.qualityScore != null && <span>Quality: {stream.qualityScore}%</span>}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Error state */}
      {isError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Generation Failed</AlertTitle>
          <AlertDescription>{stream.error || gen.error || "An unknown error occurred"}</AlertDescription>
        </Alert>
      )}

      {/* Discovery form */}
      {status === "AWAITING_DISCOVERY" && gen?.discoveryQuestions && gen.discoveryQuestions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Discovery Questions</CardTitle>
            <p className="text-sm text-muted-foreground">
              Answer these questions to help us generate better tickets for your feature.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            {gen.discoveryQuestions.map((q) => (
              <div key={q.id} className="space-y-1.5">
                <label htmlFor={`discovery-${q.id}`} className="text-sm font-medium leading-none">
                  {q.text}
                </label>
                <textarea
                  id={`discovery-${q.id}`}
                  className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 resize-none"
                  placeholder={q.placeholder || "Your answer..."}
                  value={discoveryAnswers[q.id] || ""}
                  onChange={(e) => setDiscoveryAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
                  disabled={submittingDiscovery}
                />
              </div>
            ))}
          </CardContent>
          <CardFooter>
            <Button
              onClick={handleDiscoverySubmit}
              disabled={
                submittingDiscovery ||
                !gen.discoveryQuestions.every(q => (discoveryAnswers[q.id] || "").trim())
              }
            >
              {submittingDiscovery ? (
                <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Submitting...</>
              ) : (
                <><Send className="h-4 w-4 mr-2" />Submit Answers</>
              )}
            </Button>
          </CardFooter>
        </Card>
      )}

      {/* Document panel for editing */}
      {canEditDocument && (
        <Card>
          <CardHeader>
            <CardTitle>Edit Document</CardTitle>
            {status === "READY_TO_PUSH" && (
              <p className="text-sm text-muted-foreground">
                Editing here will move this generation back to USER_EDITING. Click Finalize again to
                regenerate structured output from your updated document.
              </p>
            )}
          </CardHeader>
          <CardContent>
            <Editor content={editDoc} onChange={setEditDoc} markdown minHeight="400px" />
          </CardContent>
          <CardFooter className="gap-2">
            <Button onClick={handleSave} disabled={saving} variant="outline">
              {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
              Save Draft
            </Button>
            <Button onClick={handleFinalize} disabled={finalizing}>
              {finalizing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Check className="h-4 w-4 mr-2" />}
              {status === "READY_TO_PUSH" ? "Re-finalize" : "Finalize"}
            </Button>
          </CardFooter>
        </Card>
      )}

      {/* Document view (non-editing) */}
      {!canEditDocument && gen.document && (
        <Card>
          <CardHeader><CardTitle>Document</CardTitle></CardHeader>
          <CardContent>
            <Editor content={gen.document} onChange={() => {}} markdown readOnly minHeight="200px" />
          </CardContent>
        </Card>
      )}

      {/* Structured output */}
      {output && output.epics && output.epics.length > 0 && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>{output.projectName || "Structured Output"}</CardTitle>
              {output.overallNotes && <p className="text-sm text-muted-foreground mt-1">{output.overallNotes}</p>}
            </div>
            <div className="flex gap-2">
              {isComplete && status !== "PUSHED_TO_LINEAR" && (
                <Button onClick={() => window.location.href = `/generation/${id}/push`} size="sm">
                  <Send className="h-4 w-4 mr-2" />Review & Push
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {status === "PUSHED_TO_LINEAR" && (
              <Alert>
                <AlertTitle>Pushed to Linear</AlertTitle>
                <AlertDescription>This generation has been pushed to Linear.</AlertDescription>
              </Alert>
            )}
            {output.epics.map((epic: GeneratedEpic, i: number) => (
              <div key={i} className="border rounded-md">
                <button onClick={() => toggleEpic(i)} className="w-full flex items-center justify-between p-4 text-left hover:bg-accent/50">
                  <div className="flex items-center gap-3">
                    {expandedEpics.has(i) ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                    <span className="font-medium">{epic.epicTitle}</span>
                    {epic.teamName && <Badge variant="secondary">{epic.teamName}</Badge>}
                  </div>
                  <span className="text-xs text-muted-foreground">{epic.stories.length} stories</span>
                </button>
                {expandedEpics.has(i) && (
                  <div className="px-4 pb-4 space-y-3">
                    <p className="text-sm text-muted-foreground">{epic.epicDescription}</p>
                    {epic.stories.map((story, j) => (
                      <div key={j} className="border rounded-md p-3 bg-muted/30">
                        <h4 className="font-medium text-sm">{story.title}</h4>
                        <p className="text-sm text-muted-foreground mt-1">{story.description}</p>
                        {story.acceptanceCriteria.length > 0 && (
                          <div className="mt-2">
                            <span className="text-xs font-medium">Acceptance Criteria:</span>
                            <ul className="list-disc list-inside text-xs text-muted-foreground mt-1">
                              {story.acceptanceCriteria.map((ac, k) => <li key={k}>{ac}</li>)}
                            </ul>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Cost breakdown */}
      {cost && (
        <Card>
          <button onClick={() => setCostOpen(!costOpen)} className="w-full flex items-center justify-between p-6 text-left">
            <div className="flex items-center gap-2">
              <DollarSign className="h-4 w-4" />
              <span className="font-medium">Cost Breakdown</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm text-muted-foreground">${cost.totalCostUsd.toFixed(4)}</span>
              {costOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </div>
          </button>
          {costOpen && (
            <CardContent>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span>Total Input Tokens</span><span>{cost.totalInputTokens.toLocaleString()}</span></div>
                <div className="flex justify-between"><span>Total Output Tokens</span><span>{cost.totalOutputTokens.toLocaleString()}</span></div>
                {Object.entries(cost.perAgent).map(([agent, data]) => (
                  <div key={agent} className="flex justify-between text-muted-foreground">
                    <span>{agent}</span>
                    <span>${data.costUsd.toFixed(4)}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          )}
        </Card>
      )}

    </div>
  )
}
