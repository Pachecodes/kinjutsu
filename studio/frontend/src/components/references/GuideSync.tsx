import { AlertTriangle, CheckCircle2, Film } from 'lucide-react'

import { cn } from '../../lib/cn'
import { TRAINED_FRAME_MAX, TRAINED_FRAME_MIN } from '../../lib/frames'
import { describeMismatch, findGuide, formatSecondsEs, guideStatus, type GuideStatus } from '../../lib/guideSync'
import { HELP } from '../../lib/help'
import { useComposer } from '../../state/composer'
import { Button } from '../ui/button'
import { InfoTip } from '../ui/info-tip'
import { PrepareGuide } from './PrepareGuide'

function Spec({ label, width, height, frames, seconds }: { label: string; width: number; height: number; frames: number | null; seconds: number | null }) {
  return (
    <div className="min-w-0">
      <dt className="eyebrow">{label}</dt>
      <dd className="tabular mt-0.5 text-[12px] font-semibold text-fg">
        {width}×{height}
        <span className="font-normal text-muted">
          {' · '}
          {frames === null ? '¿? frames' : `${frames} frames`} · {formatSecondsEs(seconds)}
        </span>
      </dd>
    </div>
  )
}

function Coverage({ status }: { status: GuideStatus }) {
  if (!status.coverage) {
    return (
      <p className="text-[11px] leading-snug text-faint">
        Sin procedencia guardada: si este vídeo es el original, «Preparar guía» lo convierte. Si es una guía antigua, añade
        su original desde la Biblioteca una vez; no se adivinan enlaces por nombre.
      </p>
    )
  }
  const { coverage } = status
  return (
    <p className="text-[11px] leading-snug text-muted">
      Cobertura real: usa {formatSecondsEs(coverage.start)}–{formatSecondsEs(coverage.end)} de un original de{' '}
      {formatSecondsEs(coverage.sourceSeconds)}
      {coverage.excerpt ? (
        <span className="text-warn"> · es un fragmento: quedan {formatSecondsEs(coverage.tailSeconds)} sin usar.</span>
      ) : (
        <span> · usa el original completo.</span>
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
      aria-label="Guía alineada"
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
              {status.ok ? 'Guía alineada con la salida' : 'La guía no coincide con la salida'}
            </p>
            <InfoTip help={HELP.prepareGuide} label="Preparar guía" />
          </div>

          {!compact ? (
            <dl className="grid grid-cols-1 gap-2 rounded-xl bg-ink-950/50 px-2.5 py-2 sm:grid-cols-2">
              <Spec label="Salida" width={status.output.width} height={status.output.height} frames={status.output.frames} seconds={status.output.seconds} />
              {status.guide ? (
                <Spec label="Guía" width={status.guide.width} height={status.guide.height} frames={status.guide.frames} seconds={status.guide.seconds} />
              ) : (
                <div>
                  <dt className="eyebrow">Guía</dt>
                  <dd className="mt-0.5 text-[12px] text-warn">Tamaño ilegible</dd>
                </div>
              )}
            </dl>
          ) : null}

          {mismatch ? <p className="text-[12px] leading-snug text-fg">{mismatch}</p> : null}
          <Coverage status={status} />
          {status.originalCoversOutput === false && !status.framesMatch ? (
            <p className="text-[11px] leading-snug text-warn">
              El original no alcanza {formatSecondsEs(status.output.seconds)} desde el inicio guardado. Reduce la duración,
              adelanta el inicio o usa un vídeo más largo; no se congela ni se repite el final.
            </p>
          ) : null}
          {outsideTrained ? (
            <p className="text-[11px] leading-snug text-warn">
              {length} frames está fuera de la ventana entrenada ({TRAINED_FRAME_MIN}–{TRAINED_FRAME_MAX}). Se puede preparar,
              pero el render a esa duración es experimental y puede ser muy lento en la 4090.
            </p>
          ) : null}

          <div className="flex flex-wrap items-center gap-2">
            {!status.ok && status.canFollowGuide && status.guide ? (
              <Button variant="primary" size="sm" onClick={followGuide}>
                <Film aria-hidden />
                Ajustar salida a la guía · {status.guide.frames} f · {formatSecondsEs(status.guide.seconds)}
              </Button>
            ) : null}
            <PrepareGuide
              slot={slot}
              triggerLabel={
                status.ok ? 'Cambiar duración o encuadre' : `Preparar guía de ${formatSecondsEs(status.output.seconds)}`
              }
              triggerVariant={status.ok || status.canFollowGuide ? 'outline' : 'primary'}
            />
          </div>
        </div>
      </div>
    </section>
  )
}
