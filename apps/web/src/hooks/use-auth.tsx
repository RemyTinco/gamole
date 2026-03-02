"use client"

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react"

interface AuthContextType {
  token: string | null
  isAuthenticated: boolean
  login: (token: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextType>({
  token: null,
  isAuthenticated: false,
  login: () => {},
  logout: () => {},
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setToken(localStorage.getItem("gamole_token"))
    setMounted(true)
  }, [])

  const login = useCallback((newToken: string) => {
    localStorage.setItem("gamole_token", newToken)
    setToken(newToken)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem("gamole_token")
    setToken(null)
  }, [])

  if (!mounted) return null

  return (
    <AuthContext.Provider value={{ token, isAuthenticated: !!token, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
