import { Check } from 'lucide-react'

import { isSwapPreset } from '../../lib/curation'
import { cn } from '../../lib/cn'
import { swapChecklist } from '../../lib/recipeRoute'
import { useComposer } from '../../state/composer'

function focusTarget(target: string) {
  const node =
    document.querySelector<HTMLElement>(`[data-focus="${target}"]`) ??
    document.querySelector<HTMLElement>(`[data-tour="${target}"]`)
  if (!node) return
  node.scrollIntoView({ block: 'center', behavior: 'smooth' })
  const focusable = node.matches('button, textarea, input, [tabindex]')
    ? node
    : node.querySelector<HTMLElement>('button, textarea, input')
  focusable?.focus({ preventScroll: true })
}

/**
 * The recommended route, made visible: what the recipe still needs, in order,
 * each step one click away from the control that resolves it.
 */
export function RecipeChecklist() {
  const presetId = useComposer((state) => state.presetId)
  const references = useComposer((state) => state.references)
  const prompt = useComposer((state) => state.prompt)
  const width = useComposer((state) => state.width)
  const height = useComposer((state) => state.height)
  const length = useComposer((state) => state.length)
  const mode = useComposer((state) => state.mode)

  if (mode !== 'ref2va' || !isSwapPreset(presetId)) return null
  const steps = swapChecklist({ presetId, references, prompt, width, height, length })
  const remaining = steps.filter((step) => !step.done).length

  return (
    <nav aria-label="Pasos de la receta" className="flex flex-wrap items-center gap-1.5">
      <span className="eyebrow mr-1">{remaining === 0 ? 'Listo para generar' : `Faltan ${remaining}`}</span>
      <ol className="flex flex-wrap items-center gap-1.5">
        {steps.map((step, index) => (
          <li key={step.id}>
            <button
              type="button"
              onClick={() => focusTarget(step.focus)}
              aria-label={`Paso ${index + 1}: ${step.label} — ${step.done ? 'hecho' : 'pendiente'}`}
              className={cn(
                'inline-flex min-h-8 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors',
                step.done
                  ? 'border-accent/30 bg-accent/10 text-accent'
                  : 'border-white/10 bg-white/[0.03] text-muted hover:border-white/25 hover:text-fg',
              )}
            >
              <span
                aria-hidden
                className={cn(
                  'flex size-4 items-center justify-center rounded-full text-[9px] font-black',
                  step.done ? 'bg-accent text-accent-ink' : 'bg-white/10 text-fg',
                )}
              >
                {step.done ? <Check className="size-2.5" strokeWidth={3} /> : index + 1}
              </span>
              {step.label}
            </button>
          </li>
        ))}
      </ol>
    </nav>
  )
}
