"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import useSWR from "swr"
import Link from "next/link"
import { startGeneration, listGenerations } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Sparkles, Loader2, Clock } from "lucide-react"
import { toast } from "sonner"
import type { Generation } from "@/lib/types"

export default function GeneratePage() {
  const [input, setInput] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const router = useRouter()
  const { data } = useSWR("generations", () => listGenerations())
  const generations = (data?.workflows || []) as Generation[]

  const handleSubmit = async () => {
    if (!input.trim() || submitting) return
    setSubmitting(true)
    try {
      const result = await startGeneration(input.trim())
      toast.success("Generation started!")
      router.push(`/generation/${result.id}`)
    } catch (err) {
      toast.error("Failed to start generation: " + (err instanceof Error ? err.message : "Unknown error"))
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-2xl font-bold">Generate Requirements</h1>

      <Card>
        <CardContent className="pt-6">
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium mb-2 block">Feature Description</label>
              <Textarea
                placeholder="Describe the feature you want to generate requirements for..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                rows={8}
                className="resize-y"
              />
              <p className="text-xs text-muted-foreground mt-1 text-right">{input.length} characters</p>
            </div>
            <Button onClick={handleSubmit} disabled={!input.trim() || submitting} className="w-full">
              {submitting ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Sparkles className="h-4 w-4 mr-2" />}
              {submitting ? "Starting..." : "Generate"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {generations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Previous Generations</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {generations.map((gen) => (
                <Link key={gen.id} href={`/generation/${gen.id}`} className="flex items-center justify-between p-3 rounded-md border hover:bg-accent/50 transition-colors">
                  <div className="flex items-center gap-3">
                    <Clock className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm">{gen.id.slice(0, 8)}...</span>
                    <span className="text-xs text-muted-foreground">{new Date(gen.createdAt).toLocaleString()}</span>
                  </div>
                  <Badge variant={gen.status === "COMPLETED" ? "default" : gen.status === "ERROR" ? "destructive" : "outline"}>
                    {gen.status}
                  </Badge>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
