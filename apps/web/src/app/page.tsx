"use client"

import useSWR from "swr"
import Link from "next/link"
import { listGenerations, getLinearSyncStatus } from "@/lib/api-client"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Sparkles, RefreshCw, Clock, Layers } from "lucide-react"
import type { Generation } from "@/lib/types"

const statusColor: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  COMPLETED: "default",
  RUNNING: "secondary",
  ERROR: "destructive",
  USER_EDITING: "outline",
}

export default function DashboardPage() {
  const { data: genData, isLoading: genLoading } = useSWR("generations", () => listGenerations())
  const { data: syncData } = useSWR("sync-status", () => getLinearSyncStatus().catch(() => null))

  const generations = (genData?.workflows || []).slice(0, 10) as Generation[]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <div className="flex gap-2">
          <Link href="/generate">
            <Button><Sparkles className="h-4 w-4 mr-2" />New Generation</Button>
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Generations</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold flex items-center gap-2">
              <Layers className="h-5 w-5 text-muted-foreground" />
              {genLoading ? <Skeleton className="h-8 w-16" /> : genData?.workflows?.length ?? 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Last Sync</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm flex items-center gap-2">
              <RefreshCw className="h-4 w-4 text-muted-foreground" />
              {syncData?.lastSyncedAt ? new Date(syncData.lastSyncedAt).toLocaleString() : "Never"}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Cached Issues</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{syncData?.cachedIssueCount ?? 0}</div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Generations</CardTitle>
        </CardHeader>
        <CardContent>
          {genLoading ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
            </div>
          ) : generations.length === 0 ? (
            <p className="text-muted-foreground text-sm">No generations yet. Create your first one!</p>
          ) : (
            <div className="space-y-2">
              {generations.map((gen) => (
                <Link key={gen.id} href={`/generation/${gen.id}`} className="flex items-center justify-between p-3 rounded-md border hover:bg-accent/50 transition-colors">
                  <div className="flex items-center gap-3 min-w-0">
                    <Clock className="h-4 w-4 text-muted-foreground shrink-0" />
                    <span className="text-sm truncate">{gen.id.slice(0, 8)}...</span>
                    <span className="text-xs text-muted-foreground">{new Date(gen.createdAt).toLocaleString()}</span>
                  </div>
                  <Badge variant={statusColor[gen.status] || "outline"}>{gen.status}</Badge>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
