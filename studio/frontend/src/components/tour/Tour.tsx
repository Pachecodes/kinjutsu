import { ArrowLeft, ArrowRight, Compass, X } from 'lucide-react'
import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'

import { useIsDesktop } from '../../hooks/useMediaQuery'
import { cn } from '../../lib/cn'
import { useUi } from '../../state/ui'
import { Button } from '../ui/button'
import { TOUR_STEPS } from './steps'

interface Box {
  top: number
  left: number
  width: number
  height: number
}

const PAD = 6
const CARD_WIDTH = 360

function findTarget(ids: string[]): HTMLElement | null {
  for (const id of ids) {
    for (const node of document.querySelectorAll<HTMLElement>(`[data-tour="${id}"]`)) {
      // Desktop and phone layouts both exist in the DOM; only one is displayed.
      if (node.getClientRects().length > 0) return node
    }
  }
  return null
}

function measure(node: HTMLElement): Box {
  const rect = node.getBoundingClientRect()
  return { top: rect.top - PAD, left: rect.left - PAD, width: rect.width + PAD * 2, height: rect.height + PAD * 2 }
}

/** Where the card sits on desktop: beside the highlight, never off-screen. */
function cardPosition(box: Box | null): React.CSSProperties {
  if (!box) return { top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }
  const viewportW = window.innerWidth
  const viewportH = window.innerHeight
  const left = Math.min(Math.max(16, box.left), viewportW - CARD_WIDTH - 16)
  if (viewportH - (box.top + box.height) > 280) return { top: box.top + box.height + 12, left }
  if (box.top > 280) return { bottom: viewportH - box.top + 12, left }
  // Tall target: dock beside it when there is room, else bottom-right.
  if (viewportW - (box.left + box.width) > CARD_WIDTH + 32) return { top: Math.max(16, box.top), left: box.left + box.width + 12 }
  return { bottom: 16, right: 16 }
}

/**
 * Optional, repeatable guided tour. While it is open the page underneath is
 * inert to the pointer, so walking through it can never start a render or a
 * download. Esc or «Salir» end it on any step; finishing or leaving is
 * remembered so it is never forced again.
 */
export function Tour() {
  const step = useUi((state) => state.tourStep)
  const setTourStep = useUi((state) => state.setTourStep)
  const closeTour = useUi((state) => state.closeTour)
  const setMobileView = useUi((state) => state.setMobileView)
  const isDesktop = useIsDesktop()
  const [box, setBox] = useState<Box | null>(null)
  const cardRef = useRef<HTMLDivElement>(null)
  const titleId = useId()
  const bodyId = useId()

  const current = step === null ? null : (TOUR_STEPS[step] ?? null)

  // Bring the right phone tab forward, then find and follow the target.
  useEffect(() => {
    if (!current) return
    if (!isDesktop && current.mobileView) setMobileView(current.mobileView)
    let node: HTMLElement | null = null
    let frame = 0
    // Targets grow as thumbnails load; follow their size, not just scroll and resize.
    const resize = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(() => update())
    const update = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => setBox(node ? measure(node) : null))
    }
    const locate = window.setTimeout(() => {
      node = findTarget(current.targets)
      node?.scrollIntoView({ block: isDesktop ? 'center' : 'start', behavior: 'auto' })
      if (node) resize?.observe(node)
      update()
    }, 60)
    window.addEventListener('resize', update)
    window.addEventListener('scroll', update, true)
    return () => {
      window.clearTimeout(locate)
      cancelAnimationFrame(frame)
      resize?.disconnect()
      window.removeEventListener('resize', update)
      window.removeEventListener('scroll', update, true)
    }
  }, [current, isDesktop, setMobileView])

  useEffect(() => {
    if (current) cardRef.current?.focus()
  }, [current])

  if (!current || step === null) return null

  const last = step === TOUR_STEPS.length - 1
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.stopPropagation()
      closeTour()
      return
    }
    if (event.key !== 'Tab' || !cardRef.current) return
    // Keep keyboard focus inside the card while the tour is open.
    const focusable = [...cardRef.current.querySelectorAll<HTMLElement>('button:not([disabled])')]
    if (focusable.length === 0) return
    const first = focusable[0]
    const lastItem = focusable[focusable.length - 1]
    if (event.shiftKey && (document.activeElement === first || document.activeElement === cardRef.current)) {
      event.preventDefault()
      lastItem.focus()
    } else if (!event.shiftKey && document.activeElement === lastItem) {
      event.preventDefault()
      first.focus()
    }
  }

  return (
    <div className="fixed inset-0 z-[70]" onKeyDown={onKeyDown}>
      {/* Blocks the pointer so nothing underneath can be pressed mid-tour. */}
      <div aria-hidden className={cn('absolute inset-0', box ? 'bg-transparent' : 'bg-ink-950/70')} />
      {box ? (
        <div
          aria-hidden
          className="pointer-events-none absolute rounded-2xl outline outline-2 outline-accent transition-all duration-200"
          style={{ ...box, boxShadow: '0 0 0 9999px hsl(var(--ink-950) / 0.72)' }}
        />
      ) : null}

      <div
        ref={cardRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={bodyId}
        tabIndex={-1}
        style={isDesktop ? { width: CARD_WIDTH, ...cardPosition(box) } : undefined}
        className={cn(
          'absolute z-10 rounded-[1.5rem] border border-white/10 bg-ink-850 p-4 shadow-lift outline-none animate-slide-up',
          !isDesktop && 'inset-x-2 bottom-2 mb-[var(--safe-bottom)]',
        )}
      >
        <div className="flex items-start gap-2">
          <Compass className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
          <div className="min-w-0 flex-1">
            <p className="eyebrow">
              Guía · paso {step + 1} de {TOUR_STEPS.length}
            </p>
            <h2 id={titleId} className="display-title mt-0.5 text-[15px] text-fg">
              {current.title}
            </h2>
          </div>
          <button
            type="button"
            onClick={closeTour}
            aria-label="Salir del recorrido"
            className="flex size-9 shrink-0 items-center justify-center rounded-xl text-faint hover:bg-white/[0.06] hover:text-fg"
          >
            <X className="size-4" aria-hidden />
          </button>
        </div>
        <div id={bodyId} className="mt-2 space-y-2 text-[13px] leading-relaxed text-muted">
          {current.body.map((paragraph) => (
            <p key={paragraph}>{paragraph}</p>
          ))}
        </div>
        <div className="mt-4 flex items-center gap-2">
          <ol aria-hidden className="mr-auto flex gap-1">
            {TOUR_STEPS.map((entry, index) => (
              <li
                key={entry.id}
                className={cn('h-1.5 rounded-full transition-all', index === step ? 'w-4 bg-accent' : 'w-1.5 bg-white/20')}
              />
            ))}
          </ol>
          {step > 0 ? (
            <Button variant="ghost" size="sm" onClick={() => setTourStep(step - 1)}>
              <ArrowLeft aria-hidden />
              Anterior
            </Button>
          ) : null}
          <Button variant="primary" size="sm" onClick={() => (last ? closeTour() : setTourStep(step + 1))}>
            {last ? 'Terminar' : 'Siguiente'}
            {last ? null : <ArrowRight aria-hidden />}
          </Button>
        </div>
      </div>
    </div>
  )
}

/** First-visit offer: one quiet card, never a blocking modal, remembered once dismissed. */
export function TourOffer({ className }: { className?: string }) {
  const tourDone = useUi((state) => state.tourDone)
  const tourStep = useUi((state) => state.tourStep)
  const openTour = useUi((state) => state.openTour)
  const closeTour = useUi((state) => state.closeTour)
  if (tourDone || tourStep !== null) return null
  return (
    <aside
      aria-label="Recorrido guiado"
      className={cn('rounded-2xl border border-accent/25 bg-accent/[0.06] p-3', className)}
    >
      <p className="flex items-center gap-1.5 text-[12px] font-semibold text-fg">
        <Compass className="size-3.5 text-accent" aria-hidden />
        ¿Primera vez aquí?
      </p>
      <p className="mt-1 text-[11px] leading-snug text-muted">
        Un recorrido corto por la ruta completa, de la receta a la descarga. No genera ni descarga nada.
      </p>
      <div className="mt-2 flex gap-1.5">
        <Button variant="primary" size="sm" onClick={() => openTour(0)}>
          Empezar
        </Button>
        <Button variant="ghost" size="sm" onClick={closeTour}>
          Ahora no
        </Button>
      </div>
    </aside>
  )
}
