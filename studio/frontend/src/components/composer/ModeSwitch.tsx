import { Clapperboard, Film, Image as ImageIcon, Layers, Type } from 'lucide-react'
import { useRef, type ComponentType, type KeyboardEvent } from 'react'

import { t, useT } from '../../i18n'
import { MODE_COPY } from '../../lib/curation'
import { cn } from '../../lib/cn'
import type { Mode, ModeInfo } from '../../lib/types'
import { useComposer } from '../../state/composer'
import { Tooltip } from '../ui/tooltip'

const MODE_ICON: Record<Mode, ComponentType<{ className?: string }>> = {
  text: Type,
  first_frame: ImageIcon,
  first_last: Film,
  ref2va: Layers,
  performance: Clapperboard,
}

/**
 * The task switch, floating above the composer like an output-type toggle.
 * A radio group with roving focus: arrows move, Home/End jump. When the lab is
 * offline availability is unknown, so tasks stay selectable for composing.
 */
export function ModeSwitch({ modes, comfyOnline, className }: { modes: ModeInfo[]; comfyOnline: boolean; className?: string }) {
  useT()
  const mode = useComposer((state) => state.mode)
  const setMode = useComposer((state) => state.setMode)
  const refs = useRef<(HTMLButtonElement | null)[]>([])

  const enabled = modes.map((info) => !comfyOnline || info.available)
  const activeIndex = modes.findIndex((info) => info.id === mode)
  // Roving focus must land on an enabled radio, even if the current task went unavailable.
  const focusIndex = activeIndex >= 0 && enabled[activeIndex] ? activeIndex : enabled.indexOf(true)

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const keys = ['ArrowRight', 'ArrowLeft', 'ArrowDown', 'ArrowUp', 'Home', 'End']
    if (!keys.includes(event.key)) return
    event.preventDefault()
    const current = modes.findIndex((info) => info.id === mode)
    const order = modes.map((_, index) => index).filter((index) => enabled[index])
    if (order.length === 0) return
    const at = Math.max(0, order.indexOf(current))
    const nextIndex =
      event.key === 'Home'
        ? order[0]
        : event.key === 'End'
          ? order[order.length - 1]
          : order[(at + (event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : -1) + order.length) % order.length]
    setMode(modes[nextIndex].id)
    refs.current[nextIndex]?.focus()
  }

  return (
    <div
      role="radiogroup"
      aria-label={t('Tarea')}
      data-tour="mode-switch"
      onKeyDown={onKeyDown}
      className={cn(
        'flex max-w-full flex-wrap gap-1 rounded-2xl border border-white/[0.05] bg-ink-900 p-1 shadow-panel',
        className,
      )}
    >
      {modes.map((info, index) => {
        const Icon = MODE_ICON[info.id]
        const copy = MODE_COPY[info.id]
        const active = mode === info.id
        return (
          <Tooltip
            key={info.id}
            content={
              <span className="block space-y-1">
                <span className="block font-semibold">{copy.label}</span>
                <span className="block text-muted">{copy.blurb}</span>
                {!info.available ? (
                  <span className="block text-warn">
                    {comfyOnline ? info.unavailable_reason : t('Disponibilidad sin confirmar: H3 Lab está desconectado.')}
                  </span>
                ) : null}
              </span>
            }
          >
            <button
              ref={(node) => {
                refs.current[index] = node
              }}
              type="button"
              role="radio"
              aria-checked={active}
              aria-label={copy.label}
              tabIndex={index === focusIndex ? 0 : -1}
              disabled={!enabled[index]}
              onClick={() => setMode(info.id)}
              className={cn(
                'flex min-h-10 items-center gap-1.5 rounded-xl px-2.5 py-1.5 transition-colors sm:px-3',
                'disabled:cursor-not-allowed disabled:opacity-40',
                active ? 'bg-white/[0.09] text-fg' : 'text-faint hover:bg-white/[0.04] hover:text-muted',
              )}
            >
              <Icon className={cn('size-4', active ? 'text-accent' : 'text-current')} aria-hidden />
              <span className="text-[10px] font-black uppercase tracking-wider">{copy.short}</span>
            </button>
          </Tooltip>
        )
      })}
    </div>
  )
}
