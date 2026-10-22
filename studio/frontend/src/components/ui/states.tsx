import { AlertTriangle, RefreshCw } from 'lucide-react'
import type { ComponentType, ReactNode } from 'react'

import { cn } from '../../lib/cn'
import { Button } from './button'

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded bg-ink-800', className)} aria-hidden />
}

interface EmptyStateProps {
  icon?: ComponentType<{ className?: string }>
  title: string
  body?: ReactNode
  action?: ReactNode
  className?: string
  compact?: boolean
}

export function EmptyState({ icon: Icon, title, body, action, className, compact }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center text-center',
        compact ? 'gap-1.5 px-4 py-8' : 'gap-2 px-6 py-12',
        className,
      )}
    >
      {Icon ? <Icon className={cn('text-ink-600', compact ? 'size-5' : 'size-7')} /> : null}
      <p className={cn('display-title text-fg', compact ? 'text-sm' : 'text-base')}>{title}</p>
      {body ? <div className="max-w-sm text-xs leading-relaxed text-faint">{body}</div> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  )
}

interface ErrorStateProps {
  title?: string
  message: string
  onRetry?: () => void
  retrying?: boolean
  className?: string
}

export function ErrorState({ title = 'Algo salió mal', message, onRetry, retrying, className }: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn('flex flex-col items-start gap-2 rounded-xl border border-danger/40 bg-danger-soft/40 p-3', className)}
    >
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-danger" aria-hidden />
        <div>
          <p className="text-xs font-medium text-fg">{title}</p>
          <p className="mt-0.5 text-[11px] leading-snug text-muted">{message}</p>
        </div>
      </div>
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry} loading={retrying}>
          <RefreshCw aria-hidden />
          Reintentar
        </Button>
      ) : null}
    </div>
  )
}
