import * as AlertDialogPrimitive from '@radix-ui/react-alert-dialog'
import type { ReactNode } from 'react'

import { cn } from '../../lib/cn'
import { Button } from './button'

interface ConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: ReactNode
  confirmLabel: string
  cancelLabel?: string
  onConfirm: () => void
  destructive?: boolean
  busy?: boolean
}

/**
 * The one confirmation surface in the product. Radix AlertDialog gives us the
 * focus trap, the `alertdialog` role and the Escape/overlay semantics for free,
 * so every destructive action is announced properly instead of silently firing.
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  cancelLabel = 'Volver',
  onConfirm,
  destructive = true,
  busy = false,
}: ConfirmDialogProps) {
  return (
    <AlertDialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <AlertDialogPrimitive.Portal>
        <AlertDialogPrimitive.Overlay
          className="fixed inset-0 z-50 bg-ink-950/80 backdrop-blur-sm data-[state=open]:animate-fade-in"
        />
        <AlertDialogPrimitive.Content
          className={cn(
            'fixed left-1/2 top-1/2 z-50 w-[min(28rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2',
            'rounded-2xl border border-white/[0.08] bg-ink-900 p-5 shadow-lift data-[state=open]:animate-slide-up',
          )}
        >
          <AlertDialogPrimitive.Title className="display-title text-lg text-fg">
            {title}
          </AlertDialogPrimitive.Title>
          <AlertDialogPrimitive.Description asChild>
            <div className="mt-2 text-sm leading-relaxed text-muted">{description}</div>
          </AlertDialogPrimitive.Description>
          <div className="mt-5 flex justify-end gap-2">
            <AlertDialogPrimitive.Cancel asChild>
              <Button variant="ghost">{cancelLabel}</Button>
            </AlertDialogPrimitive.Cancel>
            <AlertDialogPrimitive.Action asChild>
              <Button
                variant={destructive ? 'danger' : 'primary'}
                loading={busy}
                onClick={(event) => {
                  event.preventDefault()
                  onConfirm()
                }}
              >
                {confirmLabel}
              </Button>
            </AlertDialogPrimitive.Action>
          </div>
        </AlertDialogPrimitive.Content>
      </AlertDialogPrimitive.Portal>
    </AlertDialogPrimitive.Root>
  )
}
