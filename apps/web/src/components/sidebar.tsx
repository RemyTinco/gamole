"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useState } from "react"
import { useTheme } from "next-themes"
import { LayoutDashboard, Sparkles, Settings, MessageSquare, Sun, Moon, Menu, X } from "lucide-react"
import { cn } from "@/lib/utils"

const links = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/generate", label: "Generate", icon: Sparkles },
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/settings", label: "Settings", icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()
  const { theme, setTheme } = useTheme()
  const [open, setOpen] = useState(false)

  const nav = (
    <>
      <div className="font-bold text-lg mb-6 px-3">🧀 Gamole</div>
      <div className="flex flex-col gap-1 flex-1">
        {links.map((link) => {
          const active = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href)
          return (
            <Link
              key={link.href}
              href={link.href}
              onClick={() => setOpen(false)}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
                active ? "bg-accent text-accent-foreground font-medium" : "hover:bg-accent/50 text-muted-foreground"
              )}
            >
              <link.icon className="h-4 w-4" />
              {link.label}
            </Link>
          )
        })}
      </div>
      <button
        onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        className="flex items-center gap-3 px-3 py-2 rounded-md text-sm text-muted-foreground hover:bg-accent/50 mt-auto"
      >
        {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        {theme === "dark" ? "Light mode" : "Dark mode"}
      </button>
    </>
  )

  return (
    <>
      <button className="md:hidden fixed top-4 left-4 z-50 p-2 rounded-md bg-background border" onClick={() => setOpen(!open)}>
        {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </button>
      {open && <div className="fixed inset-0 bg-black/50 z-30 md:hidden" onClick={() => setOpen(false)} />}
      <nav className={cn(
        "w-64 border-r bg-background p-4 flex flex-col fixed md:static h-full z-40 transition-transform",
        open ? "translate-x-0" : "-translate-x-full md:translate-x-0"
      )}>
        {nav}
      </nav>
    </>
  )
}
