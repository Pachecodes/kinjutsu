import * as ProgressPrimitive from '@radix-ui/react-progress'

import { cn } from '../../lib/cn'

interface ProgressBarProps {
  /** 0..1. Pass `null` for work with no reported fraction yet. */
  value: number | null
  className?: string
  label?: string
}

export function ProgressBar({ value, className, label }: ProgressBarProps) {
  const percent = value === null ? null : Math.round(Math.max(0, Math.min(1, value)) * 100)
  return (
    <ProgressPrimitive.Root
      value={percent ?? undefined}
      aria-label={label}
      className={cn('relative h-1 w-full overflow-hidden rounded-full bg-ink-700', className)}
    >
      {percent === null ? (
        <div className="absolute inset-y-0 w-1/4 animate-sweep rounded-full bg-accent/70" />
      ) : (
        <ProgressPrimitive.Indicator
          className="h-full rounded-full bg-accent transition-[width] duration-500 ease-out"
          style={{ width: `${percent}%` }}
        />
      )}
    </ProgressPrimitive.Root>
  )
}
