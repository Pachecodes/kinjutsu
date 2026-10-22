import { cva, type VariantProps } from 'class-variance-authority'
import type { HTMLAttributes } from 'react'

import { cn } from '../../lib/cn'

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-caps',
  {
    variants: {
      tone: {
        neutral: 'border-line bg-ink-800 text-muted',
        accent: 'border-accent/40 bg-accent/10 text-accent',
        warn: 'border-warn/40 bg-warn-soft/60 text-warn',
        danger: 'border-danger/40 bg-danger-soft/60 text-danger',
        outline: 'border-line-strong bg-transparent text-faint',
      },
    },
    defaultVariants: { tone: 'neutral' },
  },
)

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />
}
