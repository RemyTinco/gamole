'use client'

import { useEffect } from 'react'

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error('Global error:', error)
  }, [error])

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="space-y-4 text-center max-w-md">
        <h1 className="text-2xl font-bold">Something went wrong</h1>
        <p className="text-muted-foreground">{error.message || 'An unexpected error occurred'}</p>
        <button
          onClick={reset}
          className="rounded-md bg-primary text-primary-foreground px-4 py-2 hover:bg-primary/90"
        >
          Try again
        </button>
      </div>
    </div>
  )
}
