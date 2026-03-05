'use client'

import { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { cn } from '@/lib/utils'
import { apiPost } from '@/lib/api-client'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

const WELCOME_MESSAGE: Message = {
  role: 'assistant',
  content: `Hi! I'm here to help you define your requirements. 

Tell me about the feature you want to build. For example:
- "I want users to be able to reset their passwords"
- "We need a dashboard showing sales metrics"
- "Add dark mode support to the app"

Feel free to describe it in your own words, and I'll help you refine it before generating the formal requirements.`,
}

export default function ChatInputPage() {
  const router = useRouter()
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE])
  const [inputValue, setInputValue] = useState('')
  const [teamId, setTeamId] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    // Load saved team ID from localStorage
    const savedTeamId = localStorage.getItem('linear_team_id') || ''
    setTeamId(savedTeamId)
  }, [])

  function handleSendMessage(e: React.FormEvent) {
    e.preventDefault()
    const text = inputValue.trim()
    if (!text) return

    const newMessage: Message = { role: 'user', content: text }
    setMessages(prev => [...prev, newMessage, {
      role: 'assistant',
      content: `Got it! I'll include that in the requirements: "${text}". 
      
Is there anything else you'd like to specify? Or click "Generate Requirements" below when you're ready.`,
    }])
    setInputValue('')
  }

  async function handleGenerate() {
    // Compile all user messages into a single requirement text
    const userMessages = messages
      .filter(m => m.role === 'user')
      .map(m => m.content)
      .join('\n\n')

    if (!userMessages) {
      setError('Please describe your requirement first')
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      const data = await apiPost<{ workflowId: string }>('api/generation', {
        text: userMessages,
        targetTeamId: teamId || 'default',
        mode: 'chat',
      })

      router.push(`/generation/${data.workflowId}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start generation')
    } finally {
      setIsSubmitting(false)
    }
  }

  const hasUserMessages = messages.some(m => m.role === 'user')

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] max-w-2xl">
      <div className="mb-4">
        <h1 className="text-2xl font-bold">Chat Input</h1>
        <p className="text-muted-foreground text-sm">Describe your requirement in your own words</p>
      </div>

      {/* Chat messages */}
      <div className="flex-1 overflow-y-auto rounded-md border p-4 space-y-4 mb-4">
        {messages.map((message, idx) => (
          <div
            key={idx}
            className={cn(
              'flex',
              message.role === 'user' ? 'justify-end' : 'justify-start'
            )}
          >
            <div
              className={cn(
                'max-w-[80%] rounded-lg px-4 py-2 text-sm whitespace-pre-wrap',
                message.role === 'user'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-secondary-foreground'
              )}
            >
              {message.content}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <form onSubmit={handleSendMessage} className="flex gap-2 mb-4">
        <input
          type="text"
          value={inputValue}
          onChange={e => setInputValue(e.target.value)}
          placeholder="Type your requirement..."
          className="flex-1 rounded-md border border-input bg-background text-foreground px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          disabled={isSubmitting}
        />
        <button
          type="submit"
          disabled={!inputValue.trim() || isSubmitting}
          className="rounded-md bg-secondary text-secondary-foreground px-4 py-2 text-sm font-medium hover:bg-secondary/80 disabled:opacity-50"
        >
          Send
        </button>
      </form>

      {/* Team ID + Generate button */}
      <div className="space-y-2">
        <div className="flex gap-2 items-center">
          <label className="text-sm font-medium w-28">Linear Team ID:</label>
          <input
            type="text"
            value={teamId}
            onChange={e => {
              setTeamId(e.target.value)
              localStorage.setItem('linear_team_id', e.target.value)
            }}
            placeholder="team-id"
            className="flex-1 rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        {error && (
          <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
        )}

        <div className="flex gap-2">
          <a
            href="/generate"
            className="rounded-md border px-4 py-2 text-sm hover:bg-accent"
          >
            ← Use Form Instead
          </a>
          <button
            onClick={handleGenerate}
            disabled={!hasUserMessages || isSubmitting}
            className="flex-1 rounded-md bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
          >
            {isSubmitting ? 'Starting generation...' : '🚀 Generate Requirements'}
          </button>
        </div>
      </div>
    </div>
  )
}
