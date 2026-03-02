"use client"

import { useState } from "react"
import useSWR from "swr"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import {
  listRepositories, addRepository, deleteRepository, indexRepository, listGithubRepos,
  listTeams, syncTeams, updateTeam,
  getLinearSyncStatus, linearSync, setLinearSchedule, getLinearSchedule,
  getHealth
} from "@/lib/api-client"
import { useAuth } from "@/hooks/use-auth"
import { useTheme } from "next-themes"
import { toast } from "sonner"
import { Plus, Trash2, RefreshCw, Github, Database, Loader2, Sun, Moon, Copy, Eye, EyeOff, Check } from "lucide-react"
import type { Repository, GitHubRepo, Team } from "@/lib/types"

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Settings</h1>
      <Tabs defaultValue="repositories">
        <TabsList>
          <TabsTrigger value="repositories">Repositories</TabsTrigger>
          <TabsTrigger value="teams">Teams</TabsTrigger>
          <TabsTrigger value="sync">Sync</TabsTrigger>
          <TabsTrigger value="general">General</TabsTrigger>
        </TabsList>
        <TabsContent value="repositories"><RepositoriesTab /></TabsContent>
        <TabsContent value="teams"><TeamsTab /></TabsContent>
        <TabsContent value="sync"><SyncTab /></TabsContent>
        <TabsContent value="general"><GeneralTab /></TabsContent>
      </Tabs>
    </div>
  )
}

function RepositoriesTab() {
  const isAnyIndexing = (repos: Repository[]) => repos.some((r) => r.indexingStatus === "indexing")
  const { data, isLoading, mutate } = useSWR("repos", () => listRepositories(), {
    refreshInterval: (latestData) => {
      const repos = latestData?.repositories || []
      return isAnyIndexing(repos) ? 3000 : 0
    },
  })
  const [addOpen, setAddOpen] = useState(false)
  const [ghOpen, setGhOpen] = useState(false)
  const [form, setForm] = useState({ url: "", description: "", branch: "", languages: "" })
  const [submitting, setSubmitting] = useState(false)
  const [ghRepos, setGhRepos] = useState<GitHubRepo[]>([])
  const [ghLoading, setGhLoading] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)

  const repos = data?.repositories || []

  const handleAdd = async () => {
    setSubmitting(true)
    try {
      await addRepository({
        url: form.url,
        description: form.description,
        branch: form.branch || undefined,
        languages: form.languages ? form.languages.split(",").map((l) => l.trim()) : undefined,
      })
      toast.success("Repository added")
      setAddOpen(false)
      setForm({ url: "", description: "", branch: "", languages: "" })
      mutate()
    } catch { toast.error("Failed to add repository") }
    setSubmitting(false)
  }

  const handleBrowseGh = async () => {
    setGhOpen(true)
    setGhLoading(true)
    try {
      const result = await listGithubRepos()
      setGhRepos(result.repositories || [])
    } catch { toast.error("Failed to fetch GitHub repos") }
    setGhLoading(false)
  }

  const handleAddGh = async (repo: GitHubRepo) => {
    try {
      await addRepository({ url: repo.url, description: repo.description || "", languages: repo.language ? [repo.language] : undefined })
      toast.success(`Added ${repo.fullName}`)
      mutate()
    } catch { toast.error("Failed to add") }
  }

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this repository?")) return
    setDeleting(id)
    try { await deleteRepository(id); toast.success("Deleted"); mutate() }
    catch { toast.error("Failed to delete") }
    setDeleting(null)
  }

  const handleIndex = async (id: string) => {
    try { await indexRepository(id); toast.success("Indexing started"); mutate() }
    catch { toast.error("Failed to start indexing") }
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Button onClick={() => setAddOpen(true)}><Plus className="h-4 w-4 mr-2" />Add Repository</Button>
        <Button variant="outline" onClick={handleBrowseGh}><Github className="h-4 w-4 mr-2" />Browse GitHub</Button>
      </div>

      {isLoading ? (
        <div className="space-y-2">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}</div>
      ) : repos.length === 0 ? (
        <p className="text-muted-foreground text-sm">No repositories registered yet.</p>
      ) : (
        <div className="space-y-2">
          {repos.map((repo: Repository) => (
            <Card key={repo.id}>
              <CardContent className="flex items-center justify-between p-4">
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">{repo.name}</span>
                    {repo.languages?.map((l) => <Badge key={l} variant="secondary" className="text-xs">{l}</Badge>)}
                    {repo.indexingStatus === "indexing" && (
                      <Badge variant="default" className="text-xs animate-pulse">
                        <Loader2 className="h-3 w-3 animate-spin mr-1" />Indexing…
                      </Badge>
                    )}
                    {repo.indexingStatus === "error" && (
                      <Badge variant="destructive" className="text-xs">Error</Badge>
                    )}
                    {repo.indexingStatus === "done" && !repo.indexingError && (
                      <Badge variant="outline" className="text-xs text-green-600 border-green-600">Indexed</Badge>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground truncate">{repo.description || repo.url}</p>
                  <div className="flex items-center gap-3 text-xs text-muted-foreground">
                    <span>{repo.fileCount} files</span>
                    <span>{repo.chunkCount} chunks</span>
                    {repo.indexedAt && <span>Indexed: {new Date(repo.indexedAt).toLocaleDateString()}</span>}
                  </div>
                  {repo.indexingStatus === "error" && repo.indexingError && (
                    <p className="text-xs text-destructive mt-1">{repo.indexingError}</p>
                  )}
                </div>
                <div className="flex gap-2 shrink-0">
                  <Button size="sm" variant="outline" onClick={() => handleIndex(repo.id)} disabled={repo.indexingStatus === "indexing"}>
                    {repo.indexingStatus === "indexing" ? <Loader2 className="h-3 w-3 animate-spin" /> : <Database className="h-3 w-3" />}
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => handleDelete(repo.id)} disabled={deleting === repo.id}>
                    {deleting === repo.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Add Repository</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><label className="text-sm font-medium">URL</label><Input value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="https://github.com/org/repo" /></div>
            <div><label className="text-sm font-medium">Description</label><Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
            <div><label className="text-sm font-medium">Branch (optional)</label><Input value={form.branch} onChange={(e) => setForm({ ...form, branch: e.target.value })} placeholder="main" /></div>
            <div><label className="text-sm font-medium">Languages (comma-separated)</label><Input value={form.languages} onChange={(e) => setForm({ ...form, languages: e.target.value })} placeholder="TypeScript, Python" /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddOpen(false)}>Cancel</Button>
            <Button onClick={handleAdd} disabled={!form.url || submitting}>{submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : "Add"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={ghOpen} onOpenChange={setGhOpen}>
        <DialogContent className="max-h-[80vh] overflow-auto">
          <DialogHeader><DialogTitle>GitHub Repositories</DialogTitle></DialogHeader>
          {ghLoading ? (
            <div className="space-y-2">{[...Array(5)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}</div>
          ) : (
            <div className="space-y-2">
              {ghRepos.map((repo) => (
                <div key={repo.fullName} className="flex items-center justify-between p-3 border rounded-md">
                  <div className="min-w-0">
                    <div className="text-sm font-medium">{repo.fullName}</div>
                    <p className="text-xs text-muted-foreground truncate">{repo.description}</p>
                  </div>
                  <Button size="sm" onClick={() => handleAddGh(repo)}><Plus className="h-3 w-3" /></Button>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

function TeamsTab() {
  const { data, isLoading, mutate } = useSWR("teams", () => listTeams())
  const [syncing, setSyncing] = useState(false)
  const [editTeam, setEditTeam] = useState<Team | null>(null)
  const [editDesc, setEditDesc] = useState("")
  const [saving, setSaving] = useState(false)
  const teams = data?.teams || []

  const handleSync = async () => {
    setSyncing(true)
    try { await syncTeams(); toast.success("Teams synced from Linear"); mutate() }
    catch { toast.error("Failed to sync teams") }
    setSyncing(false)
  }

  const handleSave = async () => {
    if (!editTeam) return
    setSaving(true)
    try { await updateTeam(editTeam.id, { description: editDesc }); toast.success("Team updated"); setEditTeam(null); mutate() }
    catch { toast.error("Failed to update") }
    setSaving(false)
  }

  return (
    <div className="space-y-4">
      <Button onClick={handleSync} disabled={syncing}>
        {syncing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
        Sync from Linear
      </Button>

      {isLoading ? (
        <div className="space-y-2">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}</div>
      ) : teams.length === 0 ? (
        <p className="text-muted-foreground text-sm">No teams. Sync from Linear to get started.</p>
      ) : (
        <div className="space-y-2">
          {teams.map((team: Team) => (
            <Card key={team.id}>
              <CardContent className="flex items-center justify-between p-4">
                <div>
                  <span className="font-medium text-sm">{team.name}</span>
                  <p className="text-xs text-muted-foreground">{team.description || "No description"}</p>
                </div>
                <Button size="sm" variant="outline" onClick={() => { setEditTeam(team); setEditDesc(team.description) }}>Edit</Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={!!editTeam} onOpenChange={(open) => !open && setEditTeam(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Edit {editTeam?.name}</DialogTitle></DialogHeader>
          <Textarea value={editDesc} onChange={(e) => setEditDesc(e.target.value)} rows={4} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditTeam(null)}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving}>{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function SyncTab() {
  const { data: status, mutate } = useSWR("sync-status", () => getLinearSyncStatus().catch(() => null))
  const { data: schedule, mutate: mutateSchedule } = useSWR("sync-schedule", () => getLinearSchedule().catch(() => null))
  const [syncing, setSyncing] = useState(false)
  const [interval, setInterval2] = useState("")

  const handleSync = async (full: boolean) => {
    setSyncing(true)
    try { await linearSync(full); toast.success(full ? "Full sync started" : "Incremental sync started"); mutate() }
    catch { toast.error("Sync failed") }
    setSyncing(false)
  }

  const handleSchedule = async (enabled: boolean) => {
    const mins = parseInt(interval) || schedule?.intervalMinutes || 30
    try { await setLinearSchedule(mins, enabled); toast.success(enabled ? "Periodic sync enabled" : "Periodic sync disabled"); mutateSchedule() }
    catch { toast.error("Failed to update schedule") }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>Linear Sync Status</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex justify-between text-sm">
            <span>Last synced</span>
            <span>{status?.lastSyncedAt ? new Date(status.lastSyncedAt).toLocaleString() : "Never"}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span>Cached issues</span>
            <span>{status?.cachedIssueCount ?? 0}</span>
          </div>
          <div className="flex gap-2">
            <Button onClick={() => handleSync(false)} disabled={syncing}>
              {syncing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
              Sync Now
            </Button>
            <Button variant="outline" onClick={() => handleSync(true)} disabled={syncing}>Force Full Sync</Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Periodic Sync</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-3">
            <label className="text-sm">Interval (minutes):</label>
            <Input
              type="number"
              className="w-24"
              value={interval || schedule?.intervalMinutes || ""}
              onChange={(e) => setInterval2(e.target.value)}
              placeholder="30"
            />
          </div>
          <div className="flex gap-2">
            <Button onClick={() => handleSchedule(true)} size="sm">Enable</Button>
            <Button onClick={() => handleSchedule(false)} variant="outline" size="sm">Disable</Button>
          </div>
          {schedule && <p className="text-xs text-muted-foreground">Currently: {schedule.enabled ? `Enabled, every ${schedule.intervalMinutes}min` : "Disabled"}</p>}
        </CardContent>
      </Card>
    </div>
  )
}

function GeneralTab() {
  const { token, logout } = useAuth()
  const { theme, setTheme } = useTheme()
  const { data: health } = useSWR("health", () => getHealth().catch(() => null))
  const [showToken, setShowToken] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    if (token) { navigator.clipboard.writeText(token); setCopied(true); setTimeout(() => setCopied(false), 2000) }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>Appearance</CardTitle></CardHeader>
        <CardContent>
          <Button variant="outline" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
            {theme === "dark" ? <Sun className="h-4 w-4 mr-2" /> : <Moon className="h-4 w-4 mr-2" />}
            {theme === "dark" ? "Light Mode" : "Dark Mode"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>API Connection</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${health ? "bg-green-500" : "bg-red-500"}`} />
            <span className="text-sm">{health ? "Connected" : "Disconnected"}</span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Token</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2">
            <code className="text-xs bg-muted p-2 rounded flex-1 truncate">
              {showToken ? token : token ? token.slice(0, 10) + "..." : "No token"}
            </code>
            <Button size="icon" variant="outline" onClick={() => setShowToken(!showToken)}>
              {showToken ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
            </Button>
            <Button size="icon" variant="outline" onClick={handleCopy}>
              {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
            </Button>
          </div>
          <Button variant="destructive" size="sm" onClick={logout}>Clear Token</Button>
        </CardContent>
      </Card>
    </div>
  )
}
