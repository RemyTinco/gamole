'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { Editor } from '@/components/editor'
import { apiFetch, apiPut } from '@/lib/api-client'

interface Workflow {
  id: string
  status: string
  inputText: string
  inputMode: 'form' | 'chat'
  targetTeamId: string
  targetProjectId: string | null
  qualityScore: number | null
  createdAt: string
  updatedAt: string
}

interface DocumentVersion {
  id: string
  type: 'AI_FINAL' | 'USER_EDITED'
  contentMarkdown: string
  createdAt: string
}

interface Generation {
  workflow: Workflow
  documents: {
    aiFinal: DocumentVersion | null
    userEdited: DocumentVersion | null
  }
}

export default function EditGenerationPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const [generation, setGeneration] = useState<Generation | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editorHtml, setEditorHtml] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    async function loadGeneration() {
      try {
        const data = await apiFetch<Generation>(`api/generation/${id}`)
        setGeneration(data)
        setEditorHtml(data.documents?.userEdited?.contentMarkdown ?? data.documents?.aiFinal?.contentMarkdown ?? '')
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load generation')
      } finally {
        setLoading(false)
      }
    }

    loadGeneration()
  }, [id])

  async function handleSave() {
    setSaving(true)
    setSaved(false)
    try {
      await apiPut(`api/generation/${id}`, { content_markdown: editorHtml })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        <span>Loading generation...</span>
      </div>
    )
  }

  if (error && !generation) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Error</h1>
        <div className="rounded-md bg-destructive/10 p-4 text-destructive">{error}</div>
        <button
          onClick={() => router.back()}
          className="rounded-md border px-4 py-2 hover:bg-accent"
        >
          Go Back
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">Edit Requirements</h1>
          <p className="text-muted-foreground">
            Generation ID: <span className="font-mono text-xs">{id}</span>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="rounded-md bg-primary text-primary-foreground px-4 py-2 hover:bg-primary/90 disabled:opacity-50 font-medium"
          >
            {saving ? 'Saving...' : saved ? 'Saved ✓' : 'Save'}
          </button>
          <button
            onClick={() => router.push(`/generation/${id}/push`)}
            className="rounded-md border px-4 py-2 hover:bg-accent font-medium"
          >
            Push to Linear →
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
      )}

      <Editor
        content={editorHtml}
        onChange={(html) => {
          setEditorHtml(html)
          setSaved(false)
        }}
      />
    </div>
  )
}
