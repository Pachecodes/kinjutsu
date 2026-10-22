import { Check, FlaskConical } from 'lucide-react'
import { useState } from 'react'

import { t, useT } from '../../i18n'
import { BRAND } from '../../lib/brand'
import { cn } from '../../lib/cn'
import { formatSeconds } from '../../lib/format'
import { methodModeBlock } from '../../lib/curation'
import type { MethodInfo } from '../../lib/types'
import { useComposer } from '../../state/composer'
import { OmniSetup } from './OmniSetup'

/**
 * Method profiles with their measured numbers attached. Experimental profiles
 * sit behind an explicit toggle and are never selected automatically.
 * `comfyOnline` false means availability is unconfirmed, not denied.
 */
export function MethodPicker({ methods, comfyOnline = true }: { methods: MethodInfo[]; comfyOnline?: boolean }) {
  useT()
  const method = useComposer((state) => state.method)
  const mode = useComposer((state) => state.mode)
  const setMethod = useComposer((state) => state.setMethod)
  const selected = methods.find((info) => info.id === method)
  const [showExperimental, setShowExperimental] = useState(Boolean(selected?.experimental))

  const visible = methods.filter((info) => !info.experimental || showExperimental || info.id === method)
  const hiddenCount = methods.filter((info) => info.experimental).length

  return (
    <div className="space-y-2">
      <div role="radiogroup" aria-label={t('Método')} className="space-y-1">
        {visible.map((info) => {
          const active = method === info.id
          const blocked = methodModeBlock(info.id, mode)
          const unavailable = (info.id === 'fast_h3_omni_8step' || comfyOnline) && !info.available
          const disabled = Boolean(blocked) || unavailable
          return (
            <button
              key={info.id}
              type="button"
              role="radio"
              aria-checked={active}
              disabled={disabled}
              onClick={() => setMethod(info.id)}
              className={cn(
                'flex w-full items-start gap-2.5 rounded-xl border px-2.5 py-2 text-left transition-colors',
                active ? 'border-accent/50 bg-accent/10' : 'border-transparent hover:border-white/10 hover:bg-white/[0.04]',
                disabled && 'cursor-not-allowed opacity-45 hover:border-transparent hover:bg-transparent',
              )}
            >
              <span
                aria-hidden
                className={cn(
                  'mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full border',
                  active ? 'border-accent bg-accent text-accent-ink' : 'border-white/20',
                )}
              >
                {active ? <Check className="size-2.5" strokeWidth={3} /> : null}
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-1.5">
                  <span className={cn('text-[12px] font-semibold', active ? 'text-fg' : 'text-muted')}>{info.label}</span>
                  {info.experimental ? (
                    <span className="inline-flex items-center gap-0.5 rounded-md border border-warn/40 px-1 text-[9px] font-bold uppercase tracking-caps text-warn">
                      <FlaskConical className="size-2.5" aria-hidden />
                      {t('Experimental')}
                    </span>
                  ) : null}
                  {info.measured_seconds !== null ? (
                    <span className="tabular rounded-md bg-white/[0.06] px-1 text-[10px] text-muted">
                      {t('{time} medido', { time: formatSeconds(info.measured_seconds) })}
                    </span>
                  ) : null}
                  {info.measured_ssim !== null ? (
                    <span className="tabular rounded-md bg-white/[0.06] px-1 text-[10px] text-muted">
                      SSIM {info.measured_ssim.toFixed(3)}
                    </span>
                  ) : null}
                </span>
                <span className="mt-0.5 block text-[11px] leading-snug text-faint">{info.blurb}</span>
                {active || blocked || unavailable ? (
                  <span className={cn('mt-0.5 block text-[11px] leading-snug', blocked || unavailable ? 'text-danger' : 'text-faint')}>
                    {blocked ?? (unavailable ? info.unavailable_reason : info.caveat)}
                  </span>
                ) : null}
              </span>
            </button>
          )
        })}
      </div>
      {methods.some((info) => info.id === 'fast_h3_omni_8step' && !info.available) ? <OmniSetup /> : null}
      {hiddenCount > 0 ? (
        <button
          type="button"
          aria-pressed={showExperimental}
          onClick={() => setShowExperimental(!showExperimental)}
          className="flex min-h-8 w-full items-center gap-1.5 rounded-lg px-2.5 text-[11px] font-semibold text-faint hover:text-fg"
        >
          <FlaskConical className="size-3.5" aria-hidden />
          {showExperimental ? t('Ocultar métodos experimentales') : t('Mostrar {n} métodos experimentales', { n: hiddenCount })}
        </button>
      ) : null}
      <p className="px-2.5 text-[10px] leading-snug text-faint">
        {t(
          'Perfiles clásicos medidos en {machine} (608×352, 5 s). Omni tiene ejemplos independientes de una imagen y 5,17 s: 86–123 s con motor caliente en RTX 4090. No es una garantía de velocidad ni HD.',
          { machine: BRAND.machine },
        )}
      </p>
    </div>
  )
}
