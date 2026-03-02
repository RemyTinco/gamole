"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { X } from "lucide-react"

interface DialogContextType {
  open: boolean
  setOpen: (v: boolean) => void
}

const DialogContext = React.createContext<DialogContextType>({ open: false, setOpen: () => {} })

export function Dialog({ open, onOpenChange, children }: {
  open?: boolean
  onOpenChange?: (v: boolean) => void
  children: React.ReactNode
}) {
  const [internal, setInternal] = React.useState(false)
  const isOpen = open ?? internal
  const setIsOpen = onOpenChange ?? setInternal

  return (
    <DialogContext.Provider value={{ open: isOpen, setOpen: setIsOpen }}>
      {children}
    </DialogContext.Provider>
  )
}

export function DialogTrigger({ children, asChild, className }: { children: React.ReactNode; asChild?: boolean; className?: string }) {
  const { setOpen } = React.useContext(DialogContext)
  if (asChild && React.isValidElement(children)) {
    return React.cloneElement(children as React.ReactElement<Record<string, unknown>>, {
      onClick: () => setOpen(true),
    })
  }
  return <button className={className} onClick={() => setOpen(true)}>{children}</button>
}

export function DialogContent({ children, className }: { children: React.ReactNode; className?: string }) {
  const { open, setOpen } = React.useContext(DialogContext)
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/50" onClick={() => setOpen(false)} />
      <div className={cn("relative z-50 w-full max-w-lg rounded-lg border bg-background p-6 shadow-lg", className)}>
        <button className="absolute right-4 top-4 rounded-sm opacity-70 hover:opacity-100" onClick={() => setOpen(false)}>
          <X className="h-4 w-4" />
        </button>
        {children}
      </div>
    </div>
  )
}

export function DialogHeader({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("flex flex-col space-y-1.5 text-center sm:text-left", className)}>{children}</div>
}

export function DialogTitle({ children, className }: { children: React.ReactNode; className?: string }) {
  return <h2 className={cn("text-lg font-semibold leading-none tracking-tight", className)}>{children}</h2>
}

export function DialogDescription({ children, className }: { children: React.ReactNode; className?: string }) {
  return <p className={cn("text-sm text-muted-foreground", className)}>{children}</p>
}

export function DialogFooter({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2 mt-4", className)}>{children}</div>
}
