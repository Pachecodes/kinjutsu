import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import { Info } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '../../lib/cn'
import type { HelpEntry } from '../../lib/help'

interface InfoTipProps {
  /** A help entry from `lib/help.ts`, or free content. */
  help: HelpEntry | ReactNode
  /** Names the control the tip explains, for screen readers ("Ayuda: Pasos"). */
  label: string
  className?: string
  side?: 'top' | 'right' | 'bottom' | 'left'
}

function isEntry(help: InfoTipProps['help']): help is HelpEntry {
  return typeof help === 'object' && help !== null && 'what' in (help as object)
}

/**
 * A focusable (i) next to a control. The tooltip opens on hover *and* keyboard
 * focus, so the explanation is reachable without a mouse. Tips explain; they are
 * never the only place a blocking fact appears.
 */
export function InfoTip({ help, label, className, side = 'top' }: InfoTipProps) {
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger asChild>
        <button
          type="button"
          aria-label={`Ayuda: ${label}`}
          className={cn(
            'inline-flex size-5 shrink-0 items-center justify-center rounded-full text-faint transition-colors',
            'hover:bg-white/[0.08] hover:text-fg',
            className,
          )}
        >
          <Info className="size-3.5" aria-hidden />
        </button>
      </TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          side={side}
          sideOffset={6}
          collisionPadding={12}
          className="z-50 max-w-[19rem] rounded-xl border border-white/[0.08] bg-ink-800 px-3 py-2.5 text-[11px] leading-snug text-fg shadow-lift animate-fade-in"
        >
          {isEntry(help) ? (
            <span className="block space-y-1.5">
              <span className="block">{help.what}</span>
              {help.when ? (
                <span className="block text-muted">
                  <span className="font-semibold text-fg">Cuándo tocarlo: </span>
                  {help.when}
                </span>
              ) : null}
              {help.cost ? (
                <span className="block text-warn">
                  <span className="font-semibold">Coste / límite: </span>
                  {help.cost}
                </span>
              ) : null}
            </span>
          ) : (
            help
          )}
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  )
}
