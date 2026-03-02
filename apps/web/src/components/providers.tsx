"use client"

import { ThemeProvider } from "next-themes"
import { Toaster } from "sonner"
import { AuthProvider } from "@/hooks/use-auth"
import type { ReactNode } from "react"

export function Providers({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
        {children}
        <Toaster position="bottom-right" />
      </ThemeProvider>
    </AuthProvider>
  )
}
