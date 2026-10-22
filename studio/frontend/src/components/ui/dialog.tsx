import * as DialogPrimitive from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '../../lib/cn'
import { t, useT } from '../../i18n'

export const Dialog = DialogPrimitive.Root
export const DialogTrigger = DialogPrimitive.Trigger

interface DialogPanelProps {
  title: string
  description?: string
  children: ReactNode
  className?: string
}

export function DialogPanel({ title, description, children, className }: DialogPanelProps) {
  useT()
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-ink-950/80 backdrop-blur-sm data-[state=open]:animate-fade-in" />
      <DialogPrimitive.Content
        className={cn(
          'fixed left-1/2 top-1/2 z-50 flex max-h-[85vh] w-[min(46rem,calc(100vw-2rem))] -translate-x-1/2',
          '-translate-y-1/2 flex-col rounded-2xl border border-white/[0.08] bg-ink-900 shadow-lift',
          'data-[state=open]:animate-slide-up',
          className,
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-white/[0.06] px-5 py-4">
          <div>
            <DialogPrimitive.Title className="display-title text-base text-fg">{title}</DialogPrimitive.Title>
            {description ? (
              <DialogPrimitive.Description className="mt-1 text-xs text-faint">
                {description}
              </DialogPrimitive.Description>
            ) : (
              <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
            )}
          </div>
          <DialogPrimitive.Close
            className="rounded-lg p-1.5 text-faint transition-colors hover:bg-ink-800 hover:text-fg"
            aria-label={t('Cerrar')}
          >
            <X className="size-4" aria-hidden />
          </DialogPrimitive.Close>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-5">{children}</div>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  )
}
