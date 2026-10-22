import * as ToastPrimitive from '@radix-ui/react-toast'
import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react'
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

import { cn } from '../../lib/cn'

export type ToastTone = 'info' | 'success' | 'error'

interface ToastRecord {
  id: number
  title: string
  description?: string
  tone: ToastTone
}

interface ToastApi {
  toast: (input: { title: string; description?: string; tone?: ToastTone }) => void
}

const ToastContext = createContext<ToastApi | null>(null)

const TONE_ICON = {
  info: Info,
  success: CheckCircle2,
  error: AlertTriangle,
} as const

const TONE_CLASS = {
  info: 'text-muted',
  success: 'text-accent',
  error: 'text-danger',
} as const

let toastId = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastRecord[]>([])

  const toast = useCallback<ToastApi['toast']>(({ title, description, tone = 'info' }) => {
    toastId += 1
    setItems((current) => [...current.slice(-3), { id: toastId, title, description, tone }])
  }, [])

  const api = useMemo(() => ({ toast }), [toast])

  return (
    <ToastContext.Provider value={api}>
      <ToastPrimitive.Provider swipeDirection="right" duration={6000}>
        {children}
        {items.map((item) => {
          const Icon = TONE_ICON[item.tone]
          return (
            <ToastPrimitive.Root
              key={item.id}
              onOpenChange={(open) => {
                if (!open) setItems((current) => current.filter((entry) => entry.id !== item.id))
              }}
              className={cn(
                'pointer-events-auto flex items-start gap-2.5 rounded-xl border border-white/[0.08] bg-ink-850 p-3',
                'shadow-lift data-[state=open]:animate-slide-up data-[swipe=end]:animate-fade-in',
              )}
            >
              <Icon className={cn('mt-0.5 size-4 shrink-0', TONE_CLASS[item.tone])} aria-hidden />
              <div className="min-w-0 flex-1">
                <ToastPrimitive.Title className="text-xs font-medium text-fg">{item.title}</ToastPrimitive.Title>
                {item.description ? (
                  <ToastPrimitive.Description className="mt-0.5 text-[11px] leading-snug text-muted">
                    {item.description}
                  </ToastPrimitive.Description>
                ) : null}
              </div>
              <ToastPrimitive.Close
                className="rounded p-0.5 text-faint transition-colors hover:text-fg"
                aria-label="Cerrar aviso"
              >
                <X className="size-3.5" aria-hidden />
              </ToastPrimitive.Close>
            </ToastPrimitive.Root>
          )
        })}
        <ToastPrimitive.Viewport
          className={cn(
            'pointer-events-none fixed bottom-16 right-0 z-[60] flex w-[min(22rem,calc(100vw-1.5rem))] lg:bottom-0',
            'flex-col gap-2 p-3 safe-pb',
          )}
        />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastApi {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast must be used inside <ToastProvider>')
  return context
}
