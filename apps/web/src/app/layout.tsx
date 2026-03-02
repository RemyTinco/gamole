import type { Metadata } from "next"
import "./globals.css"
import { Providers } from "@/components/providers"
import { Sidebar } from "@/components/sidebar"

export const metadata: Metadata = {
  title: "Gamole",
  description: "AI-powered requirements generation",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Providers>
          <div className="flex h-screen">
            <Sidebar />
            <main className="flex-1 overflow-auto p-6 md:pl-6 pl-6 pt-16 md:pt-6">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  )
}
