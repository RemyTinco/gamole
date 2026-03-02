"use client"

import { useState, useRef, useEffect } from "react"
import { chatLinear } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import { Send, Loader2, ChevronDown, ChevronRight } from "lucide-react"
import type { ChatMessage } from "@/lib/types"

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || loading) return
    const question = input.trim()
    setInput("")
    const userMsg: ChatMessage = { role: "user", content: question }
    setMessages((prev) => [...prev, userMsg])
    setLoading(true)

    try {
      const history = messages.map((m) => ({ role: m.role, content: m.content }))
      const response = await chatLinear(question, history)
      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: response.answer,
        sources: response.sources,
      }
      setMessages((prev) => [...prev, assistantMsg])
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "Sorry, something went wrong. Please try again." }])
    }
    setLoading(false)
  }

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)] max-w-3xl">
      <h1 className="text-2xl font-bold mb-4">Chat</h1>

      <div className="flex-1 overflow-auto space-y-4 mb-4">
        {messages.length === 0 && (
          <div className="text-center text-muted-foreground mt-20">
            <p className="text-lg">Ask questions about your Linear data</p>
            <p className="text-sm mt-1">Try: "What are the open bugs?" or "Summarize recent sprint progress"</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-muted rounded-lg px-4 py-3">
              <Loader2 className="h-4 w-4 animate-spin" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="flex gap-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
          placeholder="Ask a question..."
          disabled={loading}
        />
        <Button onClick={handleSend} disabled={!input.trim() || loading}>
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const [sourcesOpen, setSourcesOpen] = useState(false)
  const isUser = message.role === "user"

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[80%] rounded-lg px-4 py-3 ${isUser ? "bg-primary text-primary-foreground" : "bg-muted"}`}>
        <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-2 border-t border-border/50 pt-2">
            <button onClick={() => setSourcesOpen(!sourcesOpen)} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
              {sourcesOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              {message.sources.length} sources
            </button>
            {sourcesOpen && (
              <div className="mt-2 space-y-2">
                {message.sources.map((source, i) => (
                  <Card key={i} className="bg-background">
                    <CardContent className="p-2">
                      <p className="text-xs font-mono">{source.query}</p>
                      <pre className="text-xs text-muted-foreground mt-1 overflow-auto max-h-32">{JSON.stringify(source.result, null, 2)}</pre>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
