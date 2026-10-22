import * as LabelPrimitive from '@radix-ui/react-label'
import { forwardRef, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes } from 'react'

import { cn } from '../../lib/cn'
import type { HelpEntry } from '../../lib/help'
import { InfoTip } from './info-tip'

export const Label = forwardRef<
  React.ComponentRef<typeof LabelPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>
>(function Label({ className, ...props }, ref) {
  return (
    <LabelPrimitive.Root
      ref={ref}
      className={cn('text-xs font-medium text-muted', className)}
      {...props}
    />
  )
})

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...props },
  ref,
) {
  return (
    <input
      ref={ref}
      className={cn(
        'h-9 w-full rounded border border-line bg-ink-850 px-2.5 text-sm text-fg placeholder:text-faint',
        'transition-colors hover:border-line-strong focus:border-accent/60 disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
})

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...props }, ref) {
    return (
      <textarea
        ref={ref}
        className={cn(
          'w-full resize-none rounded border border-line bg-ink-850 px-3 py-2.5 text-sm leading-relaxed',
          'text-fg placeholder:text-faint transition-colors hover:border-line-strong focus:border-accent/60',
          className,
        )}
        {...props}
      />
    )
  },
)

interface FieldProps {
  label: ReactNode
  htmlFor?: string
  hint?: ReactNode
  aside?: ReactNode
  /** Explanation tip, rendered beside (never inside) the label so it cannot activate the control. */
  help?: HelpEntry
  children: ReactNode
  className?: string
}

/** Label + control + optional hint, laid out the same way everywhere. */
export function Field({ label, htmlFor, hint, aside, help, children, className }: FieldProps) {
  return (
    <div className={cn('space-y-1.5', className)}>
      <div className="flex min-h-[18px] items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-1">
          <Label htmlFor={htmlFor}>{label}</Label>
          {help ? <InfoTip help={help} label={typeof label === 'string' ? label : 'este control'} /> : null}
        </span>
        {aside ? <span className="tabular text-[11px] text-faint">{aside}</span> : null}
      </div>
      {children}
      {hint ? <p className="text-[11px] leading-snug text-faint">{hint}</p> : null}
    </div>
  )
}
