import { AlertTriangle, CheckCircle2, Film } from 'lucide-react'

import { cn } from '../../lib/cn'
import { TRAINED_FRAME_MAX, TRAINED_FRAME_MIN } from '../../lib/frames'
import { describeMismatch, findGuide, formatSecondsEs, guideStatus, type GuideStatus } from '../../lib/guideSync'
import { HELP } from '../../lib/help'
import { useComposer } from '../../state/composer'
import { Button } from '../ui/button'
import { InfoTip } from '../ui/info-tip'
import { PrepareGuide } from './PrepareGuide'
import { t, useT } from '../../i18n'

function Spec({ label, width, height, frames, seconds }: { label: string; width: number; height: number; frames: number | null; seconds: number | null }) {
  useT()
  return (
    <div className="min-w-0">
      <dt className="eyebrow">{label}</dt>
      <dd className="tabular mt-0.5 text-[12px] font-semibold text-fg">
        {width}×{height}
        <span className="font-normal text-muted">
          {' · '}
          {frames === null ? t('¿? frames') : t('{n} frames', { n: frames })} · {formatSecondsEs(seconds)}
        </span>
      </dd>
    </div>
  )
}

function Coverage({ status }: { status: GuideStatus }) {
  useT()
  if (!status.coverage) {
    return (
      <p className="text-[11px] leading-snug text-faint">
        {t('Sin procedencia guardada: si este vídeo es el original, «Preparar guía» lo convierte. Si es una guía antigua, añade su original desde la Biblioteca una vez; no se adivinan enlaces por nombre.')}
      </p>
    )
  }
  const { coverage } = status
  return (
    <p className="text-[11px] leading-snug text-muted">
      {t('Cobertura real: usa {start}–{end} de un original de {source}', {
        start: formatSecondsEs(coverage.start),
        end: formatSecondsEs(coverage.end),
        source: formatSecondsEs(coverage.sourceSeconds),
      })}
      {coverage.excerpt ? (
        <span className="text-warn">{t(' · es un fragmento: quedan {seconds} sin usar.', { seconds: formatSecondsEs(coverage.tailSeconds) })}</span>
      ) : (
        <span>{t(' · usa el original completo.')}</span>
      )}
    </p>
  )
}

/**
 * The aligned guide next to the output it has to match. Requested duration,
 * grid-rounded duration and real file coverage are shown together, and a
 * mismatch always comes with the two ways out instead of a backend error later.
 */
export function GuideSync({ compact = false }: { compact?: boolean }) {
  useT()
  const width = useComposer((state) => state.width)
  const height = useComposer((state) => state.height)
  const length = useComposer((state) => state.length)
  const references = useComposer((state) => state.references)
  const setLength = useComposer((state) => state.setLength)
  const setFrameSize = useComposer((state) => state.setFrameSize)

  const slot = findGuide(references)
  const status = guideStatus({ width, height, length }, slot)
  if (!slot || !status) return null

  const mismatch = describeMismatch(status)
  const outsideTrained = length < TRAINED_FRAME_MIN || length > TRAINED_FRAME_MAX
  const followGuide = () => {
    if (!status.guide || status.guide.frames === null) return
    setFrameSize(status.guide.width, status.guide.height)
    setLength(status.guide.frames)
  }

  return (
    <section
      aria-label={t('Guía alineada')}
      data-tour="guide-sync"
      className={cn(
        'rounded-2xl border px-3 py-2.5',
        status.ok ? 'border-accent/25 bg-accent/[0.05]' : 'border-warn/35 bg-warn-soft/40',
      )}
    >
      <div className="flex items-start gap-2">
        {status.ok ? (
          <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
        ) : (
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warn" aria-hidden />
        )}
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex items-center gap-1.5">
            <p className="text-[12px] font-semibold text-fg">
              {status.ok ? t('Guía alineada con la salida') : t('La guía no coincide con la salida')}
            </p>
            <InfoTip help={HELP.prepareGuide} label={t('Preparar guía')} />
          </div>

          {!compact ? (
            <dl className="grid grid-cols-1 gap-2 rounded-xl bg-ink-950/50 px-2.5 py-2 sm:grid-cols-2">
              <Spec label={t('Salida')} width={status.output.width} height={status.output.height} frames={status.output.frames} seconds={status.output.seconds} />
              {status.guide ? (
                <Spec label={t('Guía')} width={status.guide.width} height={status.guide.height} frames={status.guide.frames} seconds={status.guide.seconds} />
              ) : (
                <div>
                  <dt className="eyebrow">{t('Guía')}</dt>
                  <dd className="mt-0.5 text-[12px] text-warn">{t('Tamaño ilegible')}</dd>
                </div>
              )}
            </dl>
          ) : null}

          {mismatch ? <p className="text-[12px] leading-snug text-fg">{mismatch}</p> : null}
          <Coverage status={status} />
          {status.originalCoversOutput === false && !status.framesMatch ? (
            <p className="text-[11px] leading-snug text-warn">
              {t('El original no alcanza {seconds} desde el inicio guardado. Reduce la duración, adelanta el inicio o usa un vídeo más largo; no se congela ni se repite el final.', { seconds: formatSecondsEs(status.output.seconds) })}
            </p>
          ) : null}
          {outsideTrained ? (
            <p className="text-[11px] leading-snug text-warn">
              {t('{n} frames está fuera de la ventana entrenada ({min}–{max}). Se puede preparar, pero el render a esa duración es experimental y puede ser muy lento en la 4090.', { n: length, min: TRAINED_FRAME_MIN, max: TRAINED_FRAME_MAX })}
            </p>
          ) : null}

          <div className="flex flex-wrap items-center gap-2">
            {!status.ok && status.canFollowGuide && status.guide ? (
              <Button variant="primary" size="sm" onClick={followGuide}>
                <Film aria-hidden />
                {t('Ajustar salida a la guía · {frames} f · {seconds}', { frames: status.guide.frames ?? '', seconds: formatSecondsEs(status.guide.seconds) })}
              </Button>
            ) : null}
            <PrepareGuide
              slot={slot}
              triggerLabel={
                status.ok ? t('Cambiar duración o encuadre') : t('Preparar guía de {seconds}', { seconds: formatSecondsEs(status.output.seconds) })
              }
              triggerVariant={status.ok || status.canFollowGuide ? 'outline' : 'primary'}
            />
          </div>
        </div>
      </div>
    </section>
  )
}
