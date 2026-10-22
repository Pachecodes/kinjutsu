import { BadgeCheck, Check, ChevronDown, FlaskConical, Timer } from 'lucide-react'
import { useState } from 'react'

import { APPROVED_SWAP_PRESET, curatePresets, presetReplacesPrompt, presetTier, type PresetTier } from '../../lib/curation'
import { cn } from '../../lib/cn'
import { formatSeconds } from '../../lib/format'
import { HELP } from '../../lib/help'
import type { Preset } from '../../lib/types'
import { useComposer } from '../../state/composer'
import { useUi } from '../../state/ui'
import { ConfirmDialog } from '../ui/alert-dialog'
import { InfoTip } from '../ui/info-tip'
import { Switch } from '../ui/switch'
import { useToast } from '../ui/toast'

interface RecipeCardProps {
  preset: Preset
  tier: PresetTier
  active: boolean
  comfyOnline: boolean
  onApply: (preset: Preset) => void
}

function RecipeCard({ preset, tier, active, comfyOnline, onApply }: RecipeCardProps) {
  const [open, setOpen] = useState(false)
  // Offline, availability is unknown rather than denied: loading a recipe is harmless.
  const blocked = comfyOnline && !preset.available
  const detailsId = `recipe-details-${preset.id}`

  return (
    <li
      className={cn(
        'rounded-2xl border transition-colors',
        active
          ? 'border-accent/45 bg-accent/[0.07]'
          : blocked
            ? 'border-transparent opacity-60'
            : 'border-white/[0.05] bg-white/[0.02] hover:border-white/15 hover:bg-white/[0.04]',
      )}
    >
      <div className="flex items-start gap-1">
        <button
          type="button"
          onClick={() => !blocked && onApply(preset)}
          disabled={blocked}
          aria-pressed={active}
          aria-describedby={open ? detailsId : undefined}
          className="min-w-0 flex-1 rounded-2xl px-3 py-2.5 text-left disabled:cursor-not-allowed"
        >
          <span className="flex flex-wrap items-center gap-1.5">
            {active ? <Check className="size-3.5 shrink-0 text-accent" aria-hidden /> : null}
            <span className={cn('text-[13px] font-semibold leading-tight', active ? 'text-fg' : 'text-muted')}>
              {preset.label}
            </span>
            {preset.default || preset.id === APPROVED_SWAP_PRESET ? (
              <span className="inline-flex items-center gap-0.5 rounded-md bg-accent/15 px-1 py-px text-[9px] font-bold uppercase tracking-caps text-accent">
                <BadgeCheck className="size-2.5" aria-hidden />
                Aprobada
              </span>
            ) : tier === 'recommended' ? (
              <span className="inline-flex items-center rounded-md border border-accent/30 px-1 py-px text-[9px] font-bold uppercase tracking-caps text-accent">
                Recomendada
              </span>
            ) : null}
            {tier === 'experimental' ? (
              <span className="inline-flex items-center gap-0.5 rounded-md border border-warn/40 px-1 text-[9px] font-bold uppercase tracking-caps text-warn">
                <FlaskConical className="size-2.5" aria-hidden />
                Experimental
              </span>
            ) : null}
          </span>
          <span className="mt-1 block text-[11px] leading-snug text-faint">{preset.blurb}</span>
          {blocked ? (
            <span className="mt-1 block text-[10px] leading-snug text-warn">
              No disponible: {preset.unavailable_reason ?? 'falta una capacidad del runtime.'}
            </span>
          ) : null}
          <span className="mt-1.5 flex items-center gap-1 text-[10px] text-faint">
            <Timer className="size-3" aria-hidden />
            <span className="tabular">
              {preset.estimate_seconds === null
                ? 'Sin medir en esta máquina'
                : `≈ ${formatSeconds(preset.estimate_seconds)} estimado`}
            </span>
          </span>
        </button>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={detailsId}
          aria-label={`${open ? 'Ocultar' : 'Ver'} detalles de ${preset.label}`}
          onClick={() => setOpen(!open)}
          className="mr-1.5 mt-2 rounded-lg p-1.5 text-faint transition-colors hover:bg-white/[0.06] hover:text-fg"
        >
          <ChevronDown className={cn('size-3.5 transition-transform', open && 'rotate-180')} aria-hidden />
        </button>
      </div>

      {open ? (
        <div id={detailsId} className="space-y-2 border-t border-white/[0.05] px-3 py-2.5">
          {preset.needs.length > 0 ? (
            <div>
              <p className="eyebrow mb-1">Necesita</p>
              <ul className="flex flex-wrap gap-1">
                {preset.needs.map((need) => (
                  <li key={need} className="rounded-md border border-white/10 px-1.5 py-0.5 text-[10px] text-muted">
                    {need}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {preset.recipe.length > 0 ? (
            <div>
              <p className="eyebrow mb-1">Receta</p>
              <ul className="space-y-0.5">
                {preset.recipe.map((line) => (
                  <li key={line} className="text-[11px] leading-snug text-muted">
                    {line}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {preset.caveats.map((caveat) => (
            <p key={caveat} className="text-[11px] leading-snug text-warn/90">
              {caveat}
            </p>
          ))}
        </div>
      ) : null}
    </li>
  )
}

/**
 * Curated recipes. Tested ones lead; experiments and legacy recipes live behind
 * an explicit, remembered opt-in. Loading a recipe never generates, and if it
 * would replace the creator's prompt, it asks first.
 */
export function RecipeList({ presets, comfyOnline, onApplied }: { presets: Preset[]; comfyOnline: boolean; onApplied?: () => void }) {
  const applyPreset = useComposer((state) => state.applyPreset)
  const presetId = useComposer((state) => state.presetId)
  const showExperimental = useUi((state) => state.showExperimental)
  const setShowExperimental = useUi((state) => state.setShowExperimental)
  const { toast } = useToast()
  const [pending, setPending] = useState<Preset | null>(null)
  const curated = curatePresets(presets)

  const load = (preset: Preset) => {
    applyPreset(preset)
    setPending(null)
    toast({
      title: `Receta cargada: ${preset.label}`,
      description: 'No se ha generado nada. Revisa referencias y prompt; todo sigue editable.',
      tone: 'success',
    })
    onApplied?.()
  }

  const request = (preset: Preset) => {
    if (presetReplacesPrompt(preset, useComposer.getState().prompt)) setPending(preset)
    else load(preset)
  }

  const section = (title: string, items: Preset[]) =>
    items.length > 0 ? (
      <section className="space-y-1.5">
        <h3 className="eyebrow px-1">{title}</h3>
        <ul className="space-y-1.5">
          {items.map((preset) => (
            <RecipeCard
              key={preset.id}
              preset={preset}
              tier={presetTier(preset)}
              active={presetId === preset.id}
              comfyOnline={comfyOnline}
              onApply={request}
            />
          ))}
        </ul>
      </section>
    ) : null

  return (
    <div className="space-y-4" data-tour="recipes">
      <p className="flex items-start gap-1 px-1 text-[11px] leading-snug text-faint">
        Una receta carga ajustes (y a veces un prompt). No genera; todo queda editable.
        <InfoTip help={HELP.recipe} label="Recetas" />
      </p>
      {section('Recomendadas', curated.recommended)}
      {section('Más recetas', curated.standard)}

      {curated.experimental.length > 0 ? (
        <section className="space-y-2 rounded-2xl border border-dashed border-white/10 p-2.5">
          <label className="flex items-center justify-between gap-3">
            <span className="min-w-0">
              <span className="flex items-center gap-1.5 text-[12px] font-semibold text-fg">
                <FlaskConical className="size-3.5 text-warn" aria-hidden />
                Experimentales y legacy
              </span>
              <span className="mt-0.5 block text-[11px] leading-snug text-faint">
                {curated.experimental.length} recetas sin validar en esta 4090 o sustituidas por otra receta.
              </span>
            </span>
            <Switch
              checked={showExperimental}
              onCheckedChange={setShowExperimental}
              aria-label="Mostrar recetas experimentales y legacy"
            />
          </label>
          {showExperimental ? (
            <ul className="space-y-1.5">
              {curated.experimental.map((preset) => (
                <RecipeCard
                  key={preset.id}
                  preset={preset}
                  tier="experimental"
                  active={presetId === preset.id}
                  comfyOnline={comfyOnline}
                  onApply={request}
                />
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}

      <ConfirmDialog
        open={pending !== null}
        onOpenChange={(open) => !open && setPending(null)}
        title="¿Sustituir tu prompt?"
        description={
          <>
            <span className="block">
              «{pending?.label}» trae su propio prompt y sustituirá el que escribiste. También cambian duración, tamaño y
              ajustes de la receta.
            </span>
            <span className="mt-2 block text-xs text-faint">No se genera nada. Copia tu prompt antes si quieres conservarlo.</span>
          </>
        }
        confirmLabel="Cargar receta"
        cancelLabel="Mantener mi prompt"
        destructive={false}
        onConfirm={() => pending && load(pending)}
      />
    </div>
  )
}
