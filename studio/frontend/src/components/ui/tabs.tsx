import * as TabsPrimitive from '@radix-ui/react-tabs'
import { forwardRef } from 'react'

import { cn } from '../../lib/cn'

export const Tabs = TabsPrimitive.Root

export const TabsList = forwardRef<
  React.ComponentRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(function TabsList({ className, ...props }, ref) {
  return (
    <TabsPrimitive.List
      ref={ref}
      className={cn('flex items-center gap-1 border-b border-white/[0.06] px-2', className)}
      {...props}
    />
  )
})

export const TabsTrigger = forwardRef<
  React.ComponentRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(function TabsTrigger({ className, ...props }, ref) {
  return (
    <TabsPrimitive.Trigger
      ref={ref}
      className={cn(
        'relative -mb-px min-h-11 whitespace-nowrap border-b-2 border-transparent px-2.5 py-2.5 text-[11px] font-bold uppercase tracking-caps',
        'text-faint transition-colors hover:text-muted',
        'data-[state=active]:border-accent data-[state=active]:text-fg',
        className,
      )}
      {...props}
    />
  )
})

export const TabsContent = forwardRef<
  React.ComponentRef<typeof TabsPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(function TabsContent({ className, ...props }, ref) {
  return (
    <TabsPrimitive.Content
      ref={ref}
      className={cn('outline-none data-[state=active]:animate-fade-in', className)}
      {...props}
    />
  )
})
