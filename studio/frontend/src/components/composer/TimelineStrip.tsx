import { t, useT } from '../../i18n'
import { cn } from '../../lib/cn'
import {
  FRAME_STEP,
  TRAINED_FRAME_MAX,
  TRAINED_FRAME_MIN,
  lengthToSeconds,
  isNativeLength,
} from '../../lib/frames'
import { findGuide, formatSecondsEs } from '../../lib/guideSync'
import { HELP } from '../../lib/help'
import type { LengthOption } from '../../lib/types'
import { useComposer } from '../../state/composer'
import { InfoTip } from '../ui/info-tip'
import { Slider } from '../ui/slider'

const RULER_MAX = 719

/**
 * The take's duration on a ruler instead of a bare number field: preferred
 * 17k+5 lengths are marked, and H3's trained window is drawn so stepping
 * outside it is a visible, deliberate act.
 */
export function TimelineStrip({ options }: { options: LengthOption[] }) {
  useT()
  const length = useComposer((state) => state.length)
  const method = useComposer((state) => state.method)
  const continuityEnabled = useComposer((state) => state.continuity.auto_split)
  const hasGuide = useComposer((state) => findGuide(state.references) !== null)
  const setLength = useComposer((state) => state.setLength)
  const premiumFixed = method === 'w4a8_latent2x_refine3'

  const seconds = lengthToSeconds(length)
  const native = isNativeLength(length)
  const position = (frames: number) => `${Math.min(100, (frames / RULER_MAX) * 100)}%`

  return (
    <div className="space-y-2" data-tour="duration">
      <div className="flex items-baseline justify-between gap-2">
        <span className="flex items-center gap-1">
          <span className="eyebrow">{t('Duración')}</span>
          <InfoTip help={HELP.duration} label={t('Duración')} />
        </span>
        <span className="tabular text-[11px] text-muted">
          <span className={cn('font-semibold', native ? 'text-fg' : 'text-warn')}>{formatSecondsEs(seconds)}</span>
          <span className="text-faint">{t(' · {length} frames · 24 fps', { length })}</span>
        </span>
      </div>

      <div className="relative h-10 select-none rounded-xl border border-white/[0.07] bg-ink-950/60 px-1">
        {/* Trained window */}
        <div
          className="absolute inset-y-1 rounded-lg bg-accent/10"
          style={{
            left: position(TRAINED_FRAME_MIN),
            width: `calc(${position(TRAINED_FRAME_MAX)} - ${position(TRAINED_FRAME_MIN)})`,
          }}
          aria-hidden
        />
        {options.map((option) => (
          <button
            key={option.frames}
            type="button"
            disabled={premiumFixed}
            onClick={() => setLength(option.frames)}
            aria-label={t('{duration} · {frames} frames', { duration: formatSecondsEs(option.seconds), frames: option.frames })}
            aria-pressed={length === option.frames}
            className={cn(
              'absolute top-1 h-8 -translate-x-1/2 rounded-lg px-1.5 text-[10px] font-bold tabular transition-colors',
              length === option.frames ? 'bg-accent text-accent-ink' : 'text-faint hover:bg-ink-700 hover:text-fg',
              premiumFixed && 'cursor-not-allowed opacity-50',
            )}
            style={{ left: position(option.frames) }}
          >
            {option.label.replace('.00', '')}
          </button>
        ))}
      </div>

      <Slider
        value={[length]}
        min={5}
        max={RULER_MAX}
        step={FRAME_STEP}
        aria-label={t('Duración en frames')}
        aria-valuetext={t('{length} frames, {duration}', { length, duration: formatSecondsEs(seconds) })}
        disabled={premiumFixed}
        onValueChange={([next]) => setLength(next)}
      />
      <p className="text-[11px] leading-snug text-faint">
        {t(
          'La franja verde es la ventana entrenada ({min}–{max} frames · {minDuration}–{maxDuration}). Solo valen longitudes 17k+5: el control salta de 17 en 17 frames.',
          {
            min: TRAINED_FRAME_MIN,
            max: TRAINED_FRAME_MAX,
            minDuration: formatSecondsEs(lengthToSeconds(TRAINED_FRAME_MIN)),
            maxDuration: formatSecondsEs(lengthToSeconds(TRAINED_FRAME_MAX)),
          },
        )}
      </p>

      {premiumFixed ? (
        <p className="text-[11px] leading-snug text-accent">
          {t('Premium 2× Refine3 está verificado a 124 frames / 5,17 s; la duración queda fija por seguridad en la RTX 4090.')}
        </p>
      ) : null}
      {hasGuide ? (
        <p className="text-[11px] leading-snug text-muted">
          {t('Con guía alineada, la guía debe tener exactamente esta duración. Si cambias la duración, prepara la guía de nuevo.')}
        </p>
      ) : null}

      {!native && !continuityEnabled ? (
        <p className="text-[11px] leading-snug text-warn">
          {t('Fuera de la ventana entrenada de H3. La calidad no está probada y el render puede ser muy lento.')}
        </p>
      ) : null}
      {!native && continuityEnabled && !hasGuide ? (
        <p className="text-[11px] leading-snug text-accent">
          {t('Más larga que una ventana entrenada: la continuidad automática la dividirá en ventanas.')}
        </p>
      ) : null}
    </div>
  )
}
