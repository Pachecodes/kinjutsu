import { Clipboard, Eye, LayoutTemplate, Plus, Trash2 } from 'lucide-react'
import { useId, useState, type ReactNode } from 'react'

import { usePromptCatalog } from '../../hooks/features'
import { copyText } from '../../hooks/useCopy'
import { ApiError, api } from '../../lib/api'
import { cn } from '../../lib/cn'
import { formatSecondsEs } from '../../lib/guideSync'
import { CAMERA_OPTIONS, LIGHT_OPTIONS } from '../../lib/promptBuilder'
import {
  EMPTY_DRAFT,
  EMPTY_SHOT,
  TEMPLATE_LABEL,
  effectiveSeconds,
  mapAttachments,
  previewKey,
  suggestedTemplate,
  templateProblem,
  toPromptForm,
  type FormDraft,
} from '../../lib/promptForm'
import type { FormDialogue, FormShot, PromptTemplateId } from '../../lib/types'
import { useComposer } from '../../state/composer'
import { Button } from '../ui/button'
import { Dialog, DialogPanel, DialogTrigger } from '../ui/dialog'
import { Input, Textarea } from '../ui/field'

function Text({
  label,
  value,
  onChange,
  placeholder,
  multiline = false,
  hint,
}: {
  label: string
  value: string
  onChange: (next: string) => void
  placeholder?: string
  multiline?: boolean
  hint?: ReactNode
}) {
  const id = useId()
  return (
    <div className="min-w-0 space-y-1">
      <label htmlFor={id} className="eyebrow block">
        {label}
      </label>
      {multiline ? (
        <Textarea id={id} rows={2} value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value.replace(/\n/g, ' '))} className="text-[16px] md:text-sm" />
      ) : (
        <Input id={id} value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} className="text-[16px] md:text-sm" />
      )}
      {hint ? <p className="text-[10px] text-faint">{hint}</p> : null}
    </div>
  )
}

function Seconds({ label, value, onChange, disabled }: { label: string; value: number; onChange: (next: number) => void; disabled?: boolean }) {
  const id = useId()
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="eyebrow block">
        {label}
      </label>
      <Input
        id={id}
        type="number"
        min={0}
        step={0.001}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(Math.round(Number(event.target.value) * 1000) / 1000)}
        className="tabular text-[16px] md:text-sm"
      />
    </div>
  )
}

function QuickFill({ options, onPick, label }: { options: { id: string; label: string; text: string }[]; onPick: (text: string) => void; label: string }) {
  return (
    <div className="flex flex-wrap gap-1" aria-label={label}>
      {options.slice(0, 6).map((option) => (
        <button
          key={option.id}
          type="button"
          onClick={() => onPick(option.text)}
          className="min-h-7 rounded-full border border-white/10 px-2 text-[10px] text-muted hover:border-white/25 hover:text-fg"
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

/**
 * Kinjutsu's deterministic prompt form. Attachments, roles and tokens come
 * from the take as it is; duration is the output's real duration. Preview is
 * a text-only request; Apply is a separate, explicit step that only replaces
 * the prompt — never the recipe, never a render.
 */
export function PromptFormBuilder() {
  const [open, setOpen] = useState(false)
  const mode = useComposer((state) => state.mode)
  const presetId = useComposer((state) => state.presetId)
  const references = useComposer((state) => state.references)
  const length = useComposer((state) => state.length)
  const setPrompt = useComposer((state) => state.setPrompt)
  const catalog = usePromptCatalog(open)

  const [template, setTemplate] = useState<PromptTemplateId | null>(null)
  const [draft, setDraft] = useState<FormDraft>(EMPTY_DRAFT)
  const [preview, setPreview] = useState<{ key: string; prompt: string } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const active = template ?? suggestedTemplate(mode, presetId)
  const mapping = mapAttachments(mode, references)
  const problem = templateProblem(active, mapping)
  const aligned = active === 'character-swap-aligned'
  const motion = active === 'motion-ref2va'
  const form = toPromptForm(draft, mapping, length, active)
  const key = previewKey(active, form)
  const stale = preview !== null && preview.key !== key
  const info = catalog.data?.templates.find((entry) => entry.id === active)

  const set = (patch: Partial<FormDraft>) => setDraft((current) => ({ ...current, ...patch }))
  const setShot = (index: number, patch: Partial<FormShot>) =>
    set({ shots: draft.shots.map((shot, i) => (i === index ? { ...shot, ...patch } : shot)) })
  const setLine = (index: number, patch: Partial<FormDialogue>) =>
    set({ dialogue: draft.dialogue.map((line, i) => (i === index ? { ...line, ...patch } : line)) })

  const build = async () => {
    setError(null)
    setBusy(true)
    try {
      const result = await api.buildPrompt(active, form)
      if (result.submits_render !== false || result.requires_agent !== false) {
        throw new Error('Respuesta inesperada del generador de prompts; no se aplica.')
      }
      setPreview({ key, prompt: result.prompt })
    } catch (cause) {
      // The editor prompt is never touched on error.
      setError(cause instanceof ApiError || cause instanceof Error ? cause.message : 'No se pudo construir el prompt.')
    } finally {
      setBusy(false)
    }
  }

  const apply = () => {
    if (!preview || stale) return
    setPrompt(preview.prompt)
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
        title="Plantilla H3 sin agente"
        description="Rellena el formulario; el backend lo ordena en el formato de H3. Sin IA ni tokens: no mira tus archivos, no traduce y no genera."
        className="w-[min(52rem,calc(100vw-1.5rem))]"
      >
        <div className="space-y-5">
          <fieldset className="space-y-1.5">
            <legend className="eyebrow mb-1">Plantilla</legend>
            <div role="radiogroup" aria-label="Plantilla" className="grid gap-1.5 sm:grid-cols-2">
              {(catalog.data?.templates ?? []).map((entry) => {
                const issue = templateProblem(entry.id, mapping)
                const selected = entry.id === active
                return (
                  <button
                    key={entry.id}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => {
                      setTemplate(entry.id)
                      setPreview(null)
                      setError(null)
                    }}
                    className={cn(
                      'rounded-xl border px-2.5 py-2 text-left transition-colors',
                      selected ? 'border-accent/50 bg-accent/10' : 'border-white/[0.07] hover:bg-white/[0.04]',
                    )}
                  >
                    <span className="block text-[12px] font-semibold text-fg">{TEMPLATE_LABEL[entry.id]}</span>
                    <span className={cn('block text-[10px] leading-snug', issue ? 'text-warn' : 'text-faint')}>
                      {issue ?? entry.mode}
                    </span>
                  </button>
                )
              })}
            </div>
            {catalog.isLoading ? <p className="text-[11px] text-faint">Cargando plantillas…</p> : null}
            {catalog.isError ? <p role="alert" className="text-[11px] text-danger">No se pudo cargar el catálogo de plantillas.</p> : null}
            {info ? <p className="text-[10px] text-faint">Estado: {info.status}</p> : null}
          </fieldset>

          {problem ? (
            <p role="alert" className="rounded-xl border border-warn/35 bg-warn-soft/40 px-3 py-2 text-[12px] text-warn">
              {problem} Ajusta las referencias de la toma o elige otra plantilla; el formulario no inventa adjuntos.
            </p>
          ) : null}

          <section className="space-y-2 rounded-xl border border-white/[0.06] bg-ink-950/40 p-3">
            <p className="text-[12px] text-fg">
              Duración efectiva: <span className="tabular font-semibold">{formatSecondsEs(effectiveSeconds(length), 3)}</span>
              <span className="text-faint"> · {length} frames de la salida (no se edita aquí)</span>
            </p>
            <p className="text-[11px] text-faint">
              Describe en <strong className="text-muted">inglés</strong> lo visual y el sonido: no se traduce nada. Los diálogos se
              conservan tal cual en su idioma. Un párrafo por campo, sin saltos de línea.
            </p>
          </section>

          {mapping.assets.length > 0 ? (
            <section className="space-y-2">
              <h3 className="eyebrow">Adjuntos de la toma</h3>
              {mapping.assets.map((asset) => (
                <Text
                  key={asset.uid}
                  label={asset.label}
                  value={draft.descriptions[asset.uid] ?? ''}
                  onChange={(value) => set({ descriptions: { ...draft.descriptions, [asset.uid]: value } })}
                  placeholder={asset.kind === 'aligned_guide' ? 'Describe the existing guide: clothing, scene, motion' : 'Describe what this attachment shows'}
                  hint={asset.kind === 'aligned_guide' ? 'Describe la guía que ya existe, no una escena nueva.' : undefined}
                />
              ))}
            </section>
          ) : null}

          <section className="grid gap-3 sm:grid-cols-2">
            <Text label="Identidad" value={draft.identity} onChange={(identity) => set({ identity })} placeholder="A single adult performer with…" multiline />
            <Text label="Estilo" value={draft.style} onChange={(style) => set({ style })} placeholder="Live-action, natural colors" multiline />
          </section>

          <section className="space-y-3">
            <h3 className="eyebrow">{aligned ? 'Plano continuo de la guía' : 'Planos'}</h3>
            {draft.shots.map((shot, index) => (
              <div key={index} className="space-y-2 rounded-xl border border-white/[0.06] p-3">
                <div className="flex items-end gap-2">
                  <p className="text-[12px] font-semibold text-fg">Plano {index + 1}</p>
                  {index > 0 ? (
                    <div className="w-32">
                      <Seconds label="Empieza en (s)" value={shot.start_seconds} onChange={(start_seconds) => setShot(index, { start_seconds })} />
                    </div>
                  ) : (
                    <span className="text-[10px] text-faint">empieza en 0 s</span>
                  )}
                  {index > 0 ? (
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      className="ml-auto"
                      aria-label={`Quitar plano ${index + 1}`}
                      onClick={() => set({ shots: draft.shots.filter((_, i) => i !== index) })}
                    >
                      <Trash2 aria-hidden />
                    </Button>
                  ) : null}
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <Text label="Escena" value={shot.scene} onChange={(scene) => setShot(index, { scene })} />
                  <Text label="Acción / actuación" value={shot.performance} onChange={(performance) => setShot(index, { performance })} />
                  <div className="space-y-1">
                    <Text label="Cámara" value={shot.camera} onChange={(camera) => setShot(index, { camera })} />
                    <QuickFill label={`Cámara rápida plano ${index + 1}`} options={CAMERA_OPTIONS} onPick={(text) => setShot(index, { camera: `The camera uses a ${text}` })} />
                  </div>
                  <div className="space-y-1">
                    <Text label="Luz" value={shot.lighting} onChange={(lighting) => setShot(index, { lighting })} />
                    <QuickFill label={`Luz rápida plano ${index + 1}`} options={LIGHT_OPTIONS} onPick={(text) => setShot(index, { lighting: text.charAt(0).toUpperCase() + text.slice(1) })} />
                  </div>
                  <Text label="Sonido del plano" value={draft.silent ? 'N/A' : shot.sound} onChange={(sound) => setShot(index, { sound })} />
                </div>
              </div>
            ))}
            {!aligned ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  set({
                    shots: [
                      ...draft.shots,
                      { ...EMPTY_SHOT, start_seconds: Math.min(effectiveSeconds(length) - 0.5, (draft.shots.at(-1)?.start_seconds ?? 0) + 2) },
                    ],
                  })
                }
              >
                <Plus aria-hidden />
                Añadir corte
              </Button>
            ) : (
              <p className="text-[11px] text-faint">La receta aprobada conserva el tiempo de la guía: un solo plano, sin cortes, diálogo ni música.</p>
            )}
          </section>

          <section className="space-y-2">
            <h3 className="eyebrow">Sonido</h3>
            <label className="flex items-center gap-2 text-[12px] text-fg">
              <input type="checkbox" checked={draft.silent} onChange={(event) => set({ silent: event.target.checked })} className="size-4 accent-[hsl(var(--accent))]" />
              Silencio completo (sin ambiente, música ni diálogo)
            </label>
            {!draft.silent ? (
              <div className="grid gap-2 sm:grid-cols-2">
                <Text label="Ambiente general" value={draft.soundscape} onChange={(soundscape) => set({ soundscape })} placeholder="Quiet room tone continues throughout." />
                <Text label="Música" value={aligned ? 'N/A' : draft.music} onChange={(music) => set({ music })} hint={aligned ? 'Sin música en la receta aprobada.' : 'N/A si no hay música.'} />
              </div>
            ) : null}
          </section>

          {!aligned && !draft.silent ? (
            <section className="space-y-2">
              <h3 className="eyebrow">Diálogo (opcional)</h3>
              {draft.dialogue.map((line, index) => (
                <div key={index} className="space-y-2 rounded-xl border border-white/[0.06] p-3">
                  <div className="grid grid-cols-3 gap-2">
                    <div className="space-y-1">
                      <label className="eyebrow block" htmlFor={`line-shot-${index}`}>Plano</label>
                      <Input id={`line-shot-${index}`} type="number" min={1} max={draft.shots.length} value={line.shot} onChange={(event) => setLine(index, { shot: Number(event.target.value) })} className="text-[16px] md:text-sm" />
                    </div>
                    <Seconds label="Desde (s)" value={line.start_seconds} onChange={(start_seconds) => setLine(index, { start_seconds })} />
                    <Seconds label="Hasta (s)" value={line.end_seconds} onChange={(end_seconds) => setLine(index, { end_seconds })} />
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <Text label="Quién habla" value={line.speaker} onChange={(speaker) => setLine(index, { speaker })} placeholder="The adult performer with a low voice" />
                    <Text label="Idioma" value={line.language} onChange={(language) => setLine(index, { language })} placeholder="Spanish" />
                    <Text label="Texto exacto" value={line.text} onChange={(text) => setLine(index, { text })} />
                    <Text label="Cómo lo dice" value={line.delivery} onChange={(delivery) => setLine(index, { delivery })} placeholder="quietly" />
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-[12px] text-fg">
                    <label className="flex items-center gap-1.5">
                      <input type="checkbox" checked={Boolean(line.voiceover)} onChange={(event) => setLine(index, { voiceover: event.target.checked || undefined })} className="size-4 accent-[hsl(var(--accent))]" />
                      Voz en off
                    </label>
                    {motion ? (
                      <label className="flex items-center gap-1.5">
                        <input type="checkbox" checked={line.subject === 1} onChange={(event) => setLine(index, { subject: event.target.checked ? 1 : undefined })} className="size-4 accent-[hsl(var(--accent))]" />
                        La dice la identidad (&lt;Subject 1&gt;)
                      </label>
                    ) : null}
                    <Button variant="ghost" size="sm" className="ml-auto" onClick={() => set({ dialogue: draft.dialogue.filter((_, i) => i !== index) })}>
                      <Trash2 aria-hidden />
                      Quitar línea
                    </Button>
                  </div>
                </div>
              ))}
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  set({
                    dialogue: [
                      ...draft.dialogue,
                      { shot: 1, start_seconds: 0.5, end_seconds: 2, speaker: '', language: 'Spanish', text: '', delivery: '' },
                    ],
                  })
                }
              >
                <Plus aria-hidden />
                Añadir línea de diálogo
              </Button>
            </section>
          ) : null}

          <section aria-label="Vista previa del prompt" className="space-y-2 border-t border-white/[0.06] pt-4">
            {error ? (
              <p role="alert" className="rounded-xl border border-danger/35 bg-danger-soft/30 px-3 py-2 text-[12px] text-danger">
                {error} Tu prompt actual no ha cambiado.
              </p>
            ) : null}
            {preview ? (
              <>
                <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-xl border border-white/[0.06] bg-ink-950 p-3 text-[12px] leading-relaxed text-fg">
                  {preview.prompt}
                </pre>
                {stale ? (
                  <p role="status" className="text-[11px] text-warn">
                    El formulario o los adjuntos cambiaron desde esta vista previa. Vuelve a generarla antes de aplicar.
                  </p>
                ) : null}
              </>
            ) : null}
            <div className="flex flex-wrap items-center justify-end gap-2">
              <Button variant="outline" size="sm" loading={busy} disabled={problem !== null} onClick={() => void build()}>
                <Eye aria-hidden />
                Vista previa
              </Button>
              <Button variant="ghost" size="sm" disabled={!preview || stale} onClick={() => preview && void copyText(preview.prompt)}>
                <Clipboard aria-hidden />
                Copiar
              </Button>
              <Button variant="primary" size="sm" disabled={!preview || stale} onClick={apply}>
                Usar como prompt
              </Button>
            </div>
            <p className="text-right text-[10px] text-faint">Sustituye el prompt del compositor. No cambia la receta ni genera.</p>
          </section>
        </div>
      </DialogPanel>
    </Dialog>
  )
}
