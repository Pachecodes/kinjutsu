import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import { forwardRef, type ReactNode } from 'react'

import { cn } from '../../lib/cn'

export const TooltipProvider = TooltipPrimitive.Provider

const TooltipContent = forwardRef<
  React.ComponentRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(function TooltipContent({ className, sideOffset = 6, ...props }, ref) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        ref={ref}
        sideOffset={sideOffset}
        className={cn(
          'z-50 max-w-[18rem] rounded-xl border border-white/[0.08] bg-ink-800 px-2.5 py-2 text-[11px] leading-snug',
          'text-fg shadow-lift animate-fade-in',
          className,
        )}
        {...props}
      />
    </TooltipPrimitive.Portal>
  )
})

interface TooltipProps {
  content: ReactNode
  children: ReactNode
  side?: 'top' | 'right' | 'bottom' | 'left'
  align?: 'start' | 'center' | 'end'
}

/** Tooltips are supplementary only — nothing here is the sole source of a fact. */
export function Tooltip({ content, children, side = 'top', align = 'center' }: TooltipProps) {
  if (!content) return <>{children}</>
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipContent side={side} align={align}>
        {content}
      </TooltipContent>
    </TooltipPrimitive.Root>
  )
}
