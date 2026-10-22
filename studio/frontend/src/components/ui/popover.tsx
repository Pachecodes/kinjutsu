import * as PopoverPrimitive from '@radix-ui/react-popover'
import { forwardRef } from 'react'

import { cn } from '../../lib/cn'

export const Popover = PopoverPrimitive.Root
export const PopoverTrigger = PopoverPrimitive.Trigger
export const PopoverAnchor = PopoverPrimitive.Anchor
export const PopoverClose = PopoverPrimitive.Close

/** One menu surface for every composer chip: Escape closes and focus returns to the chip. */
export const PopoverContent = forwardRef<
  React.ComponentRef<typeof PopoverPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof PopoverPrimitive.Content>
>(function PopoverContent({ className, align = 'start', sideOffset = 8, collisionPadding = 12, ...props }, ref) {
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content
        ref={ref}
        align={align}
        sideOffset={sideOffset}
        collisionPadding={collisionPadding}
        className={cn(
          'z-50 w-[min(22rem,calc(100vw-1.5rem))] rounded-2xl border border-white/[0.08] bg-ink-850 p-3 shadow-lift',
          'outline-none data-[state=open]:animate-fade-in',
          className,
        )}
        {...props}
      />
    </PopoverPrimitive.Portal>
  )
})
