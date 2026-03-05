"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { X } from "lucide-react"

interface SheetContextType {
  open: boolean
  setOpen: (v: boolean) => void
}

const SheetContext = React.createContext<SheetContextType>({ open: false, setOpen: () => {} })

export function Sheet({ open, onOpenChange, children }: {
  open?: boolean
  onOpenChange?: (v: boolean) => void
  children: React.ReactNode
}) {
  const [internal, setInternal] = React.useState(false)
  const isOpen = open ?? internal
  const setIsOpen = onOpenChange ?? setInternal

  return (
    <SheetContext.Provider value={{ open: isOpen, setOpen: setIsOpen }}>
      {children}
    </SheetContext.Provider>
  )
}

export function SheetTrigger({ children, asChild, className }: { children: React.ReactNode; asChild?: boolean; className?: string }) {
  const { setOpen } = React.useContext(SheetContext)
  if (asChild && React.isValidElement(children)) {
    return React.cloneElement(children as React.ReactElement<Record<string, unknown>>, {
      onClick: () => setOpen(true),
    })
  }
  return <button className={className} onClick={() => setOpen(true)}>{children}</button>
}

export function SheetContent({ children, className, side = "right" }: { children: React.ReactNode; className?: string; side?: "top" | "right" | "bottom" | "left" }) {
  const { open, setOpen } = React.useContext(SheetContext)
  if (!open) return null

  const sideClasses = {
    right: "inset-y-0 right-0 h-full w-3/4 border-l sm:max-w-sm",
    left: "inset-y-0 left-0 h-full w-3/4 border-r sm:max-w-sm",
    top: "inset-x-0 top-0 border-b",
    bottom: "inset-x-0 bottom-0 border-t",
  }

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="fixed inset-0 bg-black/50" onClick={() => setOpen(false)} />
      <div className={cn("relative z-50 bg-background p-6 shadow-lg transition ease-in-out", sideClasses[side], className)}>
        <button className="absolute right-4 top-4 rounded-sm opacity-70 hover:opacity-100" onClick={() => setOpen(false)}>
          <X className="h-4 w-4" />
        </button>
        {children}
      </div>
    </div>
  )
}

export function SheetHeader({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("flex flex-col space-y-1.5 text-center sm:text-left", className)}>{children}</div>
}

export function SheetTitle({ children, className }: { children: React.ReactNode; className?: string }) {
  return <h2 className={cn("text-lg font-semibold leading-none tracking-tight", className)}>{children}</h2>
}

export function SheetDescription({ children, className }: { children: React.ReactNode; className?: string }) {
  return <p className={cn("text-sm text-muted-foreground", className)}>{children}</p>
}

export function SheetFooter({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2 mt-4", className)}>{children}</div>
}

export function SheetClose({ children, className }: { children?: React.ReactNode; className?: string }) {
  const { setOpen } = React.useContext(SheetContext)
  return <button className={className} onClick={() => setOpen(false)}>{children}</button>
}

export function SheetPortal({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

export function SheetOverlay({ className }: { className?: string }) {
  const { setOpen } = React.useContext(SheetContext)
  return <div className={cn("fixed inset-0 z-50 bg-black/80", className)} onClick={() => setOpen(false)} />
}
