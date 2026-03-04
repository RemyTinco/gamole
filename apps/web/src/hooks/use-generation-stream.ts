"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import type { GenerationEvent, DiscoveryQuestion } from "@/lib/types"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3001"

interface StreamState {
  status: string
  currentNode: string | null
  round: number
  qualityScore: number | null
  isComplete: boolean
  events: GenerationEvent[]
  error: string | null
  discoveryQuestions: DiscoveryQuestion[] | null
}

export function useGenerationStream(id: string | null) {
  const [state, setState] = useState<StreamState>({
    status: "connecting",
    currentNode: null,
    round: 0,
    qualityScore: null,
    isComplete: false,
    events: [],
    error: null,
    discoveryQuestions: null,
  })
  const esRef = useRef<EventSource | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    if (!id) return
    const url = `${API_BASE}/api/generation/${id}/stream`
    const es = new EventSource(url)
    esRef.current = es

    es.onmessage = (event) => {
      try {
        const parsed: GenerationEvent = JSON.parse(event.data)
        setState((prev) => {
          const newEvents = [...prev.events, parsed]
          const update: Partial<StreamState> = { events: newEvents }

          if (parsed.type === "status") {
            update.status = (parsed.data.status as string) || prev.status
          }
          if (parsed.type === "progress") {
            if (parsed.data.currentNode) update.currentNode = parsed.data.currentNode as string
            if (parsed.data.round) update.round = parsed.data.round as number
            if (parsed.data.qualityScore != null) update.qualityScore = parsed.data.qualityScore as number
          }
          if (parsed.type === "user_edit_required") {
            update.status = "USER_EDITING"
          }
          if (parsed.type === "complete") {
            update.isComplete = true
            update.status = "COMPLETED"
          }
          if (parsed.type === "error") {
            update.error = (parsed.data.error as string) || "Unknown error"
            update.status = "ERROR"
          }
          if (parsed.type === "discovery_questions") {
            update.discoveryQuestions = parsed.data.questions as DiscoveryQuestion[]
            update.status = "AWAITING_DISCOVERY"
          }

          return { ...prev, ...update }
        })

        if (parsed.type === "complete" || parsed.type === "error") {
          es.close()
        }
      } catch {
        // ignore parse errors
      }
    }

    es.onerror = () => {
      es.close()
      // Reconnect after 3s unless complete
      setState((prev) => {
        if (prev.isComplete || prev.status === "ERROR") return prev
        reconnectTimer.current = setTimeout(connect, 3000)
        return prev
      })
    }
  }, [id])

  useEffect(() => {
    connect()
    return () => {
      esRef.current?.close()
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    }
  }, [connect])

  return state
}
