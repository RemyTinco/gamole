"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useAuth } from "@/hooks/use-auth"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { KeyRound } from "lucide-react"

export default function LoginPage() {
  const [token, setToken] = useState("")
  const { login } = useAuth()
  const router = useRouter()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!token.trim()) return
    login(token.trim())
    router.push("/")
  }

  return (
    <div className="flex items-center justify-center min-h-[80vh]">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="text-4xl mb-2">🧀</div>
          <CardTitle>Connect to Gamole</CardTitle>
          <CardDescription>Paste your API token to get started</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">API Token</label>
              <div className="relative">
                <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  type="password"
                  placeholder="Paste your JWT token here"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  className="pl-10"
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Get your token from the Gamole API or your administrator.
              </p>
            </div>
            <Button type="submit" className="w-full" disabled={!token.trim()}>
              Connect
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
