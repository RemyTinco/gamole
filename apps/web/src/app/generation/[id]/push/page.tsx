'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { getGeneration, updateStructuredOutput, pushGeneration, listTeams } from '@/lib/api-client'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import { Select } from '@/components/ui/select'
import {
  Save,
  Send,
  Trash2,
  ChevronDown,
  ChevronRight,
  Loader2,
  Check,
  Plus,
  X,
} from 'lucide-react'
import { toast } from 'sonner'
import type { GeneratedOutput, GeneratedEpic, GeneratedStory, Team } from '@/lib/types'
import type { PushResult } from '@/lib/api-client'

export default function ReviewAndPushPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()

  const [output, setOutput] = useState<GeneratedOutput | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [saving, setSaving] = useState(false)
  const [pushing, setPushing] = useState(false)
  const [pushed, setPushed] = useState(false)
  const [pushResult, setPushResult] = useState<PushResult | null>(null)
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
  const [lastSaved, setLastSaved] = useState(false)

  const [teams, setTeams] = useState<Team[]>([])
  const [selectedTeamId, setSelectedTeamId] = useState<string>('')

  const [expandedEpics, setExpandedEpics] = useState<Set<number>>(new Set())
  const [deleteTarget, setDeleteTarget] = useState<{
    type: 'epic' | 'story'
    epicIndex: number
    storyIndex?: number
    label: string
  } | null>(null)

  const [pushDialog, setPushDialog] = useState(false)
  // Load generation on mount
  useEffect(() => {
    async function load() {
      try {
        const gen = await getGeneration(id)
        if (gen.structuredOutput) {
          setOutput(gen.structuredOutput)
          setExpandedEpics(new Set(gen.structuredOutput.epics.map((_, i) => i)))
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load generation')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [id])

  // Load teams on mount
  useEffect(() => {
    async function loadTeams() {
      try {
        const data = await listTeams()
        setTeams(data.teams)
        const firstTeam = data.teams[0]
        if (data.teams.length === 1 && firstTeam) {
          setSelectedTeamId(firstTeam.id)
        }
      } catch {
        // Teams fetch is best-effort; push will fail later with a clear error
      }
    }
    loadTeams()
  }, [])

  // Warn before leaving with unsaved changes
  useEffect(() => {
    function handleBeforeUnload(e: BeforeUnloadEvent) {
      if (hasUnsavedChanges) {
        e.preventDefault()
      }
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [hasUnsavedChanges])

  const toggleEpic = useCallback((index: number) => {
    setExpandedEpics((prev) => {
      const next = new Set(prev)
      next.has(index) ? next.delete(index) : next.add(index)
      return next
    })
  }, [])

  // --- Mutation helpers ---

  function updateEpic(epicIndex: number, updates: Partial<GeneratedEpic>) {
    if (!output) return
    const newEpics = [...output.epics]
    const existing = newEpics[epicIndex]
    if (!existing) return
    newEpics[epicIndex] = { ...existing, ...updates }
    setOutput({ ...output, epics: newEpics })
    setHasUnsavedChanges(true)
    setLastSaved(false)
  }

  function updateStory(epicIndex: number, storyIndex: number, updates: Partial<GeneratedStory>) {
    if (!output) return
    const newEpics = [...output.epics]
    const epic = newEpics[epicIndex]
    if (!epic) return
    const newStories = [...epic.stories]
    const existing = newStories[storyIndex]
    if (!existing) return
    newStories[storyIndex] = { ...existing, ...updates }
    newEpics[epicIndex] = { ...epic, stories: newStories }
    setOutput({ ...output, epics: newEpics })
    setHasUnsavedChanges(true)
    setLastSaved(false)
  }

  function deleteEpic(epicIndex: number) {
    if (!output) return
    const newEpics = output.epics.filter((_, i) => i !== epicIndex)
    setOutput({ ...output, epics: newEpics })
    setExpandedEpics((prev) => {
      const next = new Set<number>()
      prev.forEach((idx) => {
        if (idx < epicIndex) next.add(idx)
        else if (idx > epicIndex) next.add(idx - 1)
      })
      return next
    })
    setHasUnsavedChanges(true)
    setLastSaved(false)
    setDeleteTarget(null)
  }

  function deleteStory(epicIndex: number, storyIndex: number) {
    if (!output) return
    const newEpics = [...output.epics]
    const epic = newEpics[epicIndex]
    if (!epic) return
    const newStories = epic.stories.filter((_, i) => i !== storyIndex)
    newEpics[epicIndex] = { ...epic, stories: newStories }
    setOutput({ ...output, epics: newEpics })
    setHasUnsavedChanges(true)
    setLastSaved(false)
    setDeleteTarget(null)
  }

  function updateAcceptanceCriterion(epicIndex: number, storyIndex: number, acIndex: number, value: string) {
    if (!output) return
    const epic = output.epics[epicIndex]
    if (!epic) return
    const story = epic.stories[storyIndex]
    if (!story) return
    const newAc = [...story.acceptanceCriteria]
    newAc[acIndex] = value
    updateStory(epicIndex, storyIndex, { acceptanceCriteria: newAc })
  }

  function addAcceptanceCriterion(epicIndex: number, storyIndex: number) {
    if (!output) return
    const epic = output.epics[epicIndex]
    if (!epic) return
    const story = epic.stories[storyIndex]
    if (!story) return
    updateStory(epicIndex, storyIndex, {
      acceptanceCriteria: [...story.acceptanceCriteria, ''],
    })
  }

  function removeAcceptanceCriterion(epicIndex: number, storyIndex: number, acIndex: number) {
    if (!output) return
    const epic = output.epics[epicIndex]
    if (!epic) return
    const story = epic.stories[storyIndex]
    if (!story) return
    updateStory(epicIndex, storyIndex, {
      acceptanceCriteria: story.acceptanceCriteria.filter((_, i) => i !== acIndex),
    })
  }

  function updateAssumption(epicIndex: number, storyIndex: number, aIndex: number, value: string) {
    if (!output) return
    const epic = output.epics[epicIndex]
    if (!epic) return
    const story = epic.stories[storyIndex]
    if (!story) return
    const newAssumptions = [...story.assumptions]
    newAssumptions[aIndex] = value
    updateStory(epicIndex, storyIndex, { assumptions: newAssumptions })
  }

  function addAssumption(epicIndex: number, storyIndex: number) {
    if (!output) return
    const epic = output.epics[epicIndex]
    if (!epic) return
    const story = epic.stories[storyIndex]
    if (!story) return
    updateStory(epicIndex, storyIndex, {
      assumptions: [...story.assumptions, ''],
    })
  }

  function removeAssumption(epicIndex: number, storyIndex: number, aIndex: number) {
    if (!output) return
    const epic = output.epics[epicIndex]
    if (!epic) return
    const story = epic.stories[storyIndex]
    if (!story) return
    updateStory(epicIndex, storyIndex, {
      assumptions: story.assumptions.filter((_, i) => i !== aIndex),
    })
  }

  // --- Actions ---

  async function handleSave() {
    if (!output) return
    setSaving(true)
    try {
      await updateStructuredOutput(id, output)
      setHasUnsavedChanges(false)
      setLastSaved(true)
      toast.success('Changes saved')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save changes')
    } finally {
      setSaving(false)
    }
  }

  async function handlePush() {
    if (!selectedTeamId) {
      toast.error('Please select a team before pushing')
      return
    }
    setPushing(true)
    try {
      const result = await pushGeneration(id, { teamId: selectedTeamId })
      setPushResult(result)
      if (result.errors.length > 0 && result.createdIssues.length === 0) {
        toast.error('Push failed — see errors below')
      } else if (result.errors.length > 0) {
        toast.warning('Pushed with some errors — see details below')
      } else {
        toast.success('Pushed to Linear!')
      }
      setPushed(true)
      setPushDialog(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to push to Linear')
      setPushDialog(false)
    } finally {
      setPushing(false)
    }
  }

  // --- Render ---

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground py-12 justify-center">
        <Loader2 className="h-5 w-5 animate-spin" />
        <span>Loading structured output...</span>
      </div>
    )
  }

  if (error && !output) {
    return (
      <div className="space-y-4 max-w-4xl">
        <h1 className="text-2xl font-bold">Error</h1>
        <Alert variant="destructive">
          <AlertTitle>Failed to load</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <Button variant="outline" onClick={() => router.push(`/generation/${id}`)}>
          Back to Generation
        </Button>
      </div>
    )
  }

  if (!output || output.epics.length === 0) {
    return (
      <div className="space-y-4 max-w-4xl">
        <h1 className="text-2xl font-bold">No Structured Output</h1>
        <p className="text-muted-foreground">
          This generation doesn&apos;t have structured output yet. Finalize the document first.
        </p>
        <Button variant="outline" onClick={() => router.push(`/generation/${id}`)}>
          Back to Generation
        </Button>
      </div>
    )
  }

  if (pushed && pushResult) {
    const hasErrors = pushResult.errors.length > 0
    const hasIssues = pushResult.createdIssues.length > 0
    return (
      <div className="space-y-4 max-w-4xl">
        <div className="flex items-center gap-3">
          <div className={`h-10 w-10 rounded-full flex items-center justify-center ${hasErrors && !hasIssues ? 'bg-red-100' : 'bg-green-100'}`}>
            {hasErrors && !hasIssues ? (
              <X className="h-5 w-5 text-red-700" />
            ) : (
              <Check className="h-5 w-5 text-green-700" />
            )}
          </div>
          <h1 className={`text-2xl font-bold ${hasErrors && !hasIssues ? 'text-red-700' : 'text-green-700'}`}>
            {hasErrors && !hasIssues ? 'Push Failed' : 'Pushed to Linear!'}
          </h1>
        </div>
        {hasIssues && (
          <Alert>
            <AlertTitle>Created Issues ({pushResult.createdIssues.length})</AlertTitle>
            <AlertDescription>
              {pushResult.createdIssues.map((issue) => issue.identifier).join(', ')}
            </AlertDescription>
          </Alert>
        )}
        {hasErrors && (
          <Alert variant="destructive">
            <AlertTitle>Errors</AlertTitle>
            <AlertDescription>
              <ul className="list-disc pl-4 space-y-1">
                {pushResult.errors.map((err, i) => (
                  <li key={i}>{err}</li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        )}
        <Button onClick={() => router.push(`/generation/${id}`)}>Back to Generation</Button>
      </div>
    )
  }

  const totalStories = output.epics.reduce((sum, e) => sum + e.stories.length, 0)

  return (
    <div className="space-y-6 max-w-4xl pb-24">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">Review & Push</h1>
          <p className="text-muted-foreground">
            {output.epics.length} epic{output.epics.length !== 1 ? 's' : ''}, {totalStories} stor{totalStories !== 1 ? 'ies' : 'y'}
            {output.projectName && <span> · {output.projectName}</span>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {hasUnsavedChanges && (
            <Badge variant="secondary" className="text-amber-600 border-amber-300">
              Unsaved changes
            </Badge>
          )}
          {lastSaved && !hasUnsavedChanges && (
            <Badge variant="secondary" className="text-green-600 border-green-300">
              <Check className="h-3 w-3 mr-1" />
              Saved
            </Badge>
          )}
        </div>
      </div>

      {/* Overall notes */}
      {output.overallNotes && (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">{output.overallNotes}</p>
          </CardContent>
        </Card>
      )}

      {/* Epics */}
      {output.epics.map((epic, epicIndex) => (
        <Card key={epicIndex} className="overflow-hidden">
          {/* Epic header */}
          <CardHeader className="pb-0">
            <div className="flex items-center justify-between">
              <button
                onClick={() => toggleEpic(epicIndex)}
                className="flex items-center gap-2 text-left hover:text-primary transition-colors"
              >
                {expandedEpics.has(epicIndex) ? (
                  <ChevronDown className="h-4 w-4 shrink-0" />
                ) : (
                  <ChevronRight className="h-4 w-4 shrink-0" />
                )}
                <CardTitle className="text-lg">{epic.epicTitle || 'Untitled Epic'}</CardTitle>
              </button>
              <div className="flex items-center gap-2">
                {epic.teamName && (
                  <Badge variant="secondary">{epic.teamName}</Badge>
                )}
                <Badge variant="outline">{epic.stories.length} stories</Badge>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-destructive hover:text-destructive"
                  onClick={() =>
                    setDeleteTarget({
                      type: 'epic',
                      epicIndex,
                      label: epic.epicTitle || `Epic ${epicIndex + 1}`,
                    })
                  }
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </CardHeader>

          {expandedEpics.has(epicIndex) && (
            <CardContent className="pt-4 space-y-4">
              {/* Epic fields */}
              <div className="grid gap-3">
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1 block">Epic Title</label>
                  <Input
                    value={epic.epicTitle}
                    onChange={(e) => updateEpic(epicIndex, { epicTitle: e.target.value })}
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1 block">Epic Description</label>
                  <Textarea
                    value={epic.epicDescription}
                    onChange={(e) => updateEpic(epicIndex, { epicDescription: e.target.value })}
                    rows={3}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-muted-foreground mb-1 block">Team</label>
                    <Select
                      value={epic.teamName || ''}
                      onChange={(e) => updateEpic(epicIndex, { teamName: e.target.value || null })}
                      options={[
                        { value: '', label: 'Select a team...' },
                        ...teams.map((t) => ({ value: t.name, label: t.name })),
                      ]}
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-muted-foreground mb-1 block">Team Reason</label>
                    <Input
                      value={epic.teamReason || ''}
                      onChange={(e) => updateEpic(epicIndex, { teamReason: e.target.value || null })}
                      placeholder="Why this team?"
                    />
                  </div>
                </div>
              </div>

              {/* Stories */}
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-muted-foreground">Stories</h3>
                {epic.stories.map((story, storyIndex) => (
                  <div
                    key={storyIndex}
                    className="border rounded-lg p-4 space-y-3 bg-muted/20"
                  >
                    {/* Story header with delete */}
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-muted-foreground">
                        Story {storyIndex + 1}
                      </span>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-destructive hover:text-destructive"
                        onClick={() =>
                          setDeleteTarget({
                            type: 'story',
                            epicIndex,
                            storyIndex,
                            label: story.title || `Story ${storyIndex + 1}`,
                          })
                        }
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>

                    {/* Story fields */}
                    <div>
                      <label className="text-xs font-medium text-muted-foreground mb-1 block">Title</label>
                      <Input
                        value={story.title}
                        onChange={(e) => updateStory(epicIndex, storyIndex, { title: e.target.value })}
                      />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-muted-foreground mb-1 block">Description</label>
                      <Textarea
                        value={story.description}
                        onChange={(e) =>
                          updateStory(epicIndex, storyIndex, { description: e.target.value })
                        }
                        rows={3}
                      />
                    </div>

                    {/* Acceptance criteria */}
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="text-xs font-medium text-muted-foreground">
                          Acceptance Criteria
                        </label>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 text-xs"
                          onClick={() => addAcceptanceCriterion(epicIndex, storyIndex)}
                        >
                          <Plus className="h-3 w-3 mr-1" />
                          Add
                        </Button>
                      </div>
                      <div className="space-y-1">
                        {story.acceptanceCriteria.map((ac, acIndex) => (
                          <div key={acIndex} className="flex items-center gap-1">
                            <Input
                              value={ac}
                              onChange={(e) =>
                                updateAcceptanceCriterion(epicIndex, storyIndex, acIndex, e.target.value)
                              }
                              className="text-sm"
                              placeholder="Acceptance criterion..."
                            />
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 shrink-0 text-muted-foreground hover:text-destructive"
                              onClick={() =>
                                removeAcceptanceCriterion(epicIndex, storyIndex, acIndex)
                              }
                            >
                              <X className="h-3 w-3" />
                            </Button>
                          </div>
                        ))}
                        {story.acceptanceCriteria.length === 0 && (
                          <p className="text-xs text-muted-foreground italic">No acceptance criteria</p>
                        )}
                      </div>
                    </div>

                    {/* Assumptions */}
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="text-xs font-medium text-muted-foreground">
                          Assumptions
                        </label>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 text-xs"
                          onClick={() => addAssumption(epicIndex, storyIndex)}
                        >
                          <Plus className="h-3 w-3 mr-1" />
                          Add
                        </Button>
                      </div>
                      <div className="space-y-1">
                        {story.assumptions.map((assumption, aIndex) => (
                          <div key={aIndex} className="flex items-center gap-1">
                            <Input
                              value={assumption}
                              onChange={(e) =>
                                updateAssumption(epicIndex, storyIndex, aIndex, e.target.value)
                              }
                              className="text-sm"
                              placeholder="Assumption..."
                            />
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 shrink-0 text-muted-foreground hover:text-destructive"
                              onClick={() =>
                                removeAssumption(epicIndex, storyIndex, aIndex)
                              }
                            >
                              <X className="h-3 w-3" />
                            </Button>
                          </div>
                        ))}
                        {story.assumptions.length === 0 && (
                          <p className="text-xs text-muted-foreground italic">No assumptions</p>
                        )}
                      </div>
                    </div>

                    {/* Technical notes */}
                    <div>
                      <label className="text-xs font-medium text-muted-foreground mb-1 block">
                        Technical Notes
                      </label>
                      <Textarea
                        value={story.technicalNotes || ''}
                        onChange={(e) =>
                          updateStory(epicIndex, storyIndex, {
                            technicalNotes: e.target.value || null,
                          })
                        }
                        rows={2}
                        placeholder="Optional technical notes..."
                      />
                    </div>
                  </div>
                ))}

                {epic.stories.length === 0 && (
                  <p className="text-sm text-muted-foreground italic py-2">
                    No stories in this epic
                  </p>
                )}
              </div>
            </CardContent>
          )}
        </Card>
      ))}

      {/* Sticky action bar */}
      <div className="fixed bottom-0 left-0 right-0 bg-background border-t p-4 flex items-center justify-between z-50">
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => router.push(`/generation/${id}`)}>
            ← Back
          </Button>
        </div>
        <div className="flex items-center gap-3">
          <Button
            onClick={handleSave}
            disabled={saving || !hasUnsavedChanges}
            variant="outline"
          >
            {saving ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Save className="h-4 w-4 mr-2" />
            )}
            {saving ? 'Saving...' : 'Save Changes'}
          </Button>
          <Button
            onClick={() => setPushDialog(true)}
            disabled={hasUnsavedChanges || output.epics.length === 0 || !selectedTeamId}
          >
            <Send className="h-4 w-4 mr-2" />
            {selectedTeamId ? 'Push to Linear' : 'Select a team to push'}
          </Button>
        </div>
      </div>

      {/* Delete confirmation dialog */}
      <Dialog open={deleteTarget !== null} onOpenChange={() => setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete {deleteTarget?.type === 'epic' ? 'Epic' : 'Story'}</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete &ldquo;{deleteTarget?.label}&rdquo;?
              {deleteTarget?.type === 'epic' && ' This will also delete all its stories.'}
              {' '}This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (!deleteTarget) return
                if (deleteTarget.type === 'epic') {
                  deleteEpic(deleteTarget.epicIndex)
                } else if (deleteTarget.storyIndex !== undefined) {
                  deleteStory(deleteTarget.epicIndex, deleteTarget.storyIndex)
                }
              }}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Push confirmation dialog */}
      <Dialog open={pushDialog} onOpenChange={setPushDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Push to Linear</DialogTitle>
            <DialogDescription>
              This will create {output.epics.length} epic{output.epics.length !== 1 ? 's' : ''} and{' '}
              {totalStories} stor{totalStories !== 1 ? 'ies' : 'y'} in Linear.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div>
              <label className="text-sm font-medium mb-1.5 block">Target Team</label>
              {teams.length === 0 ? (
                <Alert>
                  <AlertDescription>
                    No teams synced yet. Go to{' '}
                    <button
                      className="underline font-medium"
                      onClick={() => router.push('/settings')}
                    >
                      Settings
                    </button>{' '}
                    and sync your Linear teams first.
                  </AlertDescription>
                </Alert>
              ) : (
                <Select
                  value={selectedTeamId}
                  onChange={(e) => setSelectedTeamId(e.target.value)}
                  options={[
                    { value: '', label: 'Select a team...' },
                    ...teams.map((t) => ({ value: t.id, label: t.name })),
                  ]}
                />
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPushDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handlePush} disabled={pushing || !selectedTeamId}>
              {pushing ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Send className="h-4 w-4 mr-2" />
              )}
              Push
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
