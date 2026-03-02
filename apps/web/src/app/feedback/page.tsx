"use client"

import useSWR from "swr"
import { getFeedbackStats, listGenerations } from "@/lib/api-client"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { BarChart3, MessageSquare, FileText } from "lucide-react"
import type { FeedbackStats, Generation } from "@/lib/types"

export default function FeedbackPage() {
  const { data: stats, isLoading: statsLoading } = useSWR<FeedbackStats>("feedback-stats", () => getFeedbackStats())
  const { data: genData, isLoading: genLoading } = useSWR("generations", () => listGenerations())
  const generations = (genData?.workflows || []) as Generation[]

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Feedback</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <FileText className="h-4 w-4" />Total Generations
            </CardTitle>
          </CardHeader>
          <CardContent>
            {statsLoading ? <Skeleton className="h-8 w-16" /> : <div className="text-2xl font-bold">{stats?.totalGenerations ?? 0}</div>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <MessageSquare className="h-4 w-4" />Total Feedback
            </CardTitle>
          </CardHeader>
          <CardContent>
            {statsLoading ? <Skeleton className="h-8 w-16" /> : <div className="text-2xl font-bold">{stats?.totalFeedback ?? 0}</div>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <BarChart3 className="h-4 w-4" />Feedback Rate
            </CardTitle>
          </CardHeader>
          <CardContent>
            {statsLoading ? <Skeleton className="h-8 w-16" /> : (
              <div className="text-2xl font-bold">
                {stats && stats.totalGenerations > 0 ? Math.round((stats.totalFeedback / stats.totalGenerations) * 100) : 0}%
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {stats?.mostEditedFields && Object.keys(stats.mostEditedFields).length > 0 && (
        <Card>
          <CardHeader><CardTitle>Most Edited Fields</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-2">
              {Object.entries(stats.mostEditedFields)
                .sort(([, a], [, b]) => b - a)
                .map(([field, count]) => (
                  <div key={field} className="flex items-center justify-between text-sm">
                    <span>{field}</span>
                    <span className="text-muted-foreground">{count} edits</span>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle>Generations</CardTitle></CardHeader>
        <CardContent>
          {genLoading ? (
            <div className="space-y-2">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}</div>
          ) : generations.length === 0 ? (
            <p className="text-muted-foreground text-sm">No generations yet.</p>
          ) : (
            <div className="space-y-2">
              {generations.map((gen) => (
                <div key={gen.id} className="flex items-center justify-between p-3 border rounded-md text-sm">
                  <span className="font-mono">{gen.id.slice(0, 8)}...</span>
                  <span className="text-muted-foreground">{gen.status}</span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
