import * as ToggleGroupPrimitive from '@radix-ui/react-toggle-group'
import { Check } from 'lucide-react'

import { cn } from '../../lib/cn'
import { Tooltip } from './tooltip'

export interface SegmentedOption<T extends string> {
  value: T
  label: string
  disabled?: boolean
  /** Shown on hover/focus when the option is unavailable or needs a caveat. */
  tooltip?: string
}

interface SegmentedProps<T extends string> {
  value: T
  onValueChange: (value: T) => void
  options: SegmentedOption<T>[]
  label: string
  className?: string
  size?: 'sm' | 'md'
}

/** A single-select segmented control. Never lets the value become empty. */
export function Segmented<T extends string>({
  value,
  onValueChange,
  options,
  label,
  className,
  size = 'md',
}: SegmentedProps<T>) {
  return (
    <ToggleGroupPrimitive.Root
      type="single"
      value={value}
      aria-label={label}
      onValueChange={(next) => {
        if (next) onValueChange(next as T)
      }}
      className={cn('flex w-full rounded-xl border border-white/[0.07] bg-ink-850 p-0.5', className)}
    >
      {options.map((option) => {
        const selected = option.value === value
        return (
        <Tooltip key={option.value} content={option.tooltip}>
          <ToggleGroupPrimitive.Item
            value={option.value}
            disabled={option.disabled}
            data-selected={selected}
            className={cn(
              'inline-flex min-w-0 flex-1 items-center justify-center gap-1.5 rounded-lg text-center font-semibold leading-tight transition-colors active:scale-[0.98]',
              size === 'sm' ? 'whitespace-nowrap px-2 py-1 text-[11px]' : 'px-2.5 py-1.5 text-xs',
              selected
                ? 'bg-accent font-semibold text-accent-ink shadow-sm'
                : 'text-muted hover:bg-ink-700 hover:text-fg',
              'disabled:pointer-events-none disabled:opacity-35',
            )}
          >
            {selected ? <Check data-selection-check="true" className="size-3.5 shrink-0" aria-hidden /> : null}
            {option.label}
          </ToggleGroupPrimitive.Item>
        </Tooltip>
        )
      })}
    </ToggleGroupPrimitive.Root>
  )
}
