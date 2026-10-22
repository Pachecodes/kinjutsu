import { LayoutTemplate, RotateCcw } from 'lucide-react'
import { useId, useState } from 'react'

import { useFeatures } from '../../hooks/features'
import { useCachedConfig } from '../../hooks/queries'
import { isGuideSwapPreset } from '../../lib/curation'
import { cn } from '../../lib/cn'
import { HELP } from '../../lib/help'
import {
  CAMERA_OPTIONS,
  EMPTY_FIELDS,
  LIGHT_OPTIONS,
  appendToPrompt,
  buildPrompt,
  buildSwapDirection,
  swapPromptReady,
  type PromptFields,
  type ShotOption,
} from '../../lib/promptBuilder'
import { referenceTags } from '../../lib/references'
import { useComposer } from '../../state/composer'
import { Button } from '../ui/button'
import { Dialog, DialogPanel, DialogTrigger } from '../ui/dialog'
import { Input, Textarea } from '../ui/field'
import { InfoTip } from '../ui/info-tip'
import { PromptFormBuilder } from './PromptFormBuilder'

function ChipGroup({
  label,
  options,
  value,
  onChange,
}: {
  label: string
  options: ShotOption[]
  value: string[]
  onChange: (next: string[]) => void
}) {
  return (
    <fieldset className="space-y-1.5">
      <legend className="eyebrow">{label}</legend>
      <div className="flex flex-wrap gap-1.5">
        {options.map((option) => {
          const pressed = value.includes(option.id)
          return (
            <button
              key={option.id}
              type="button"
              aria-pressed={pressed}
              onClick={() => onChange(pressed ? value.filter((id) => id !== option.id) : [...value, option.id])}
              className={cn(
                'min-h-8 rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors',
                pressed
                  ? 'border-accent/50 bg-accent/15 text-accent'
                  : 'border-white/10 bg-white/[0.03] text-muted hover:border-white/25 hover:text-fg',
              )}
            >
              {option.label}
            </button>
          )
        })}
      </div>
    </fieldset>
  )
}

function TextField({
  label,
  value,
  onChange,
  placeholder,
  multiline = false,
}: {
  label: string
  value: string
  onChange: (next: string) => void
  placeholder: string
  multiline?: boolean
}) {
  const id = useId()
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="eyebrow block">
        {label}
      </label>
      {multiline ? (
        <Textarea id={id} rows={2} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} className="text-[16px] md:text-sm" />
      ) : (
        <Input id={id} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} className="text-[16px] md:text-sm" />
      )}
    </div>
  )
}

/**
 * Deterministic prompt template. It arranges the creator's own words and the
 * shot vocabulary they pick; it never looks at the references and is never
 * presented as AI. Applying it never generates.
 */
export function PromptBuilder() {
  const features = useFeatures()
  // The Kinjutsu backend owns the H3 prompt format when it serves it; otherwise
  // the local arrangement below is the fallback.
  if (!features.ready) return null
  return features.prompting ? <PromptFormBuilder /> : <LocalPromptBuilder />
}

function LocalPromptBuilder() {
  const [open, setOpen] = useState(false)
  const [fields, setFields] = useState<PromptFields>(EMPTY_FIELDS)
  const mode = useComposer((state) => state.mode)
  const prompt = useComposer((state) => state.prompt)
  const presetId = useComposer((state) => state.presetId)
  const references = useComposer((state) => state.references)
  const setPrompt = useComposer((state) => state.setPrompt)
  const cachedConfig = useCachedConfig()

  const swap = mode === 'ref2va' && isGuideSwapPreset(presetId)
  const recipePrompt = cachedConfig()?.presets.find((preset) => preset.id === presetId)?.patch.prompt
  const tags = referenceTags(mode, references).filter((tag): tag is string => tag !== null)
  const result = swap ? buildSwapDirection(fields) : buildPrompt(fields)
  const set = (patch: Partial<PromptFields>) => setFields((current) => ({ ...current, ...patch }))

  const apply = (how: 'replace' | 'append') => {
    if (!result) return
    setPrompt(how === 'replace' ? result : appendToPrompt(prompt, result))
    setOpen(false)
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button type="button" className="chip min-h-9 py-1.5" data-tour="prompt-builder">
          <LayoutTemplate className="size-3.5" aria-hidden />
          Plantilla
        </button>
      </DialogTrigger>
      <DialogPanel
        title="Plantilla de prompt"
        description="Ordena tus palabras en un prompt. Sin IA: no mira tus imágenes ni reescribe nada. No genera."
        className="w-[min(40rem,calc(100vw-1.5rem))]"
      >
        <div className="space-y-4">
          <p className="flex items-center gap-1.5 text-[11px] text-faint">
            <InfoTip help={HELP.promptBuilder} label="Plantilla de prompt" />
            Todo queda editable en el prompt después de aplicarlo.
          </p>

          {swap ? (
            <>
              <p className="rounded-xl border border-white/[0.06] bg-ink-950/60 px-3 py-2 text-[12px] leading-snug text-muted">
                La guía alineada controla escena, pose, ropa y cámara. Aquí solo añades dirección para el personaje de{' '}
                <span className="font-mono text-accent">&lt;Picture 1&gt;</span> después del texto de la receta.
              </p>
              {!swapPromptReady(prompt) ? (
                <div className="rounded-xl border border-warn/35 bg-warn-soft/40 px-3 py-2 text-[12px] text-warn">
                  <p>El prompt debe empezar por body_swap: y nombrar &lt;Picture 1&gt;.</p>
                  {recipePrompt ? (
                    <Button
                      variant="outline"
                      size="sm"
                      className="mt-2"
                      onClick={() => setPrompt(recipePrompt)}
                    >
                      <RotateCcw aria-hidden />
                      Restaurar el texto de la receta
                    </Button>
                  ) : null}
                </div>
              ) : null}
              <TextField
                label="Detalles del personaje"
                value={fields.subject}
                onChange={(subject) => set({ subject })}
                placeholder="p. ej. pelo rizado castaño, pecas, mirada serena"
                multiline
              />
              <ChipGroup label="Luz y ambiente" options={LIGHT_OPTIONS} value={fields.light} onChange={(light) => set({ light })} />
              <TextField label="Sonido" value={fields.sound} onChange={(sound) => set({ sound })} placeholder="p. ej. ambiente de salón, risa suave" />
            </>
          ) : (
            <>
              {tags.length > 0 ? (
                <p className="text-[11px] text-faint">
                  Nombra tus referencias en el sujeto o la acción:{' '}
                  {tags.map((tag) => (
                    <button
                      key={tag}
                      type="button"
                      onClick={() => set({ subject: `${fields.subject}${fields.subject && !fields.subject.endsWith(' ') ? ' ' : ''}${tag}` })}
                      className="mr-1 rounded-md border border-white/10 px-1.5 py-0.5 font-mono text-[10px] text-accent hover:border-accent/50"
                    >
                      {tag}
                    </button>
                  ))}
                </p>
              ) : null}
              <div className="grid gap-3 sm:grid-cols-2">
                <TextField label="Sujeto" value={fields.subject} onChange={(subject) => set({ subject })} placeholder="Quién o qué aparece" />
                <TextField label="Acción" value={fields.action} onChange={(action) => set({ action })} placeholder="Qué hace" />
              </div>
              <TextField label="Escena" value={fields.scene} onChange={(scene) => set({ scene })} placeholder="Dónde ocurre" />
              <ChipGroup label="Cámara" options={CAMERA_OPTIONS} value={fields.camera} onChange={(camera) => set({ camera })} />
              <ChipGroup label="Luz y ambiente" options={LIGHT_OPTIONS} value={fields.light} onChange={(light) => set({ light })} />
              <TextField label="Sonido" value={fields.sound} onChange={(sound) => set({ sound })} placeholder="Lo que se oye: diálogo, ambiente, música" />
            </>
          )}

          <section aria-label="Vista previa" className="space-y-1.5">
            <h3 className="eyebrow">Vista previa</h3>
            <p className="min-h-12 whitespace-pre-wrap rounded-xl border border-white/[0.06] bg-ink-950 px-3 py-2 text-[12px] leading-relaxed text-fg">
              {result || <span className="text-faint">Rellena algún campo para ver el resultado.</span>}
            </p>
          </section>

          <div className="flex flex-wrap items-center justify-end gap-2 border-t border-white/[0.06] pt-3">
            <Button variant="ghost" size="sm" onClick={() => setFields(EMPTY_FIELDS)}>
              Vaciar campos
            </Button>
            {!swap ? (
              <Button variant="outline" size="sm" disabled={!result} onClick={() => apply('replace')}>
                {prompt.trim() ? 'Sustituir mi prompt' : 'Usar como prompt'}
              </Button>
            ) : null}
            <Button variant="primary" size="sm" disabled={!result} onClick={() => apply('append')}>
              Añadir al final del prompt
            </Button>
          </div>
        </div>
      </DialogPanel>
    </Dialog>
  )
}
