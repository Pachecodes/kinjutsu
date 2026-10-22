import { BookOpen, ChevronDown, Clock, Dices, Gauge, Lock, RectangleHorizontal, SlidersHorizontal, Unlock } from 'lucide-react'

import { t, useT } from '../../i18n'
import { cn } from '../../lib/cn'
import {
  ASPECT_PRESETS,
  DIMENSION_MAX,
  DIMENSION_MIN,
  DIMENSION_STEP,
  lengthToSeconds,
  matchAspectPreset,
} from '../../lib/frames'
import { findGuide, formatSecondsEs, guideStatus } from '../../lib/guideSync'
import { HELP } from '../../lib/help'
import type { CapabilityResponse, Preset } from '../../lib/types'
import { useComposer } from '../../state/composer'
import { useUi } from '../../state/ui'
import { RecipeList } from '../rail/RecipeRail'
import { Input } from '../ui/field'
import { InfoTip } from '../ui/info-tip'
import { Popover, PopoverContent, PopoverTrigger } from '../ui/popover'
import { Switch } from '../ui/switch'
import { MethodPicker } from './MethodPicker'
import { TimelineStrip } from './TimelineStrip'

function ChipLabel({ children }: { children: React.ReactNode }) {
  return <span className="max-w-[11rem] truncate">{children}</span>
}

export function RecipeChip({ presets, comfyOnline, wide = false }: { presets: Preset[]; comfyOnline: boolean; wide?: boolean }) {
  useT()
  const presetId = useComposer((state) => state.presetId)
  const label = presets.find((preset) => preset.id === presetId)?.label ?? t('Sin receta')
  return (
    <Popover>
      <PopoverTrigger asChild>
        {wide ? (
          <button
            type="button"
            data-tour="recipes"
            aria-label={t('Receta: {label}. Cambiar receta', { label })}
            className="flex min-h-12 w-full items-center gap-2.5 rounded-2xl border border-white/[0.07] bg-ink-900 px-3 py-2 text-left transition-colors hover:border-white/20"
          >
            <BookOpen className="size-4 shrink-0 text-accent" aria-hidden />
            <span className="min-w-0 flex-1">
              <span className="eyebrow block">{t('Receta')}</span>
              <span className="block truncate text-[13px] font-semibold text-fg">{label}</span>
            </span>
            <ChevronDown className="size-4 shrink-0 opacity-60" aria-hidden />
          </button>
        ) : (
          <button type="button" className={cn('chip', presetId && 'text-fg')} aria-label={t('Receta: {label}', { label })}>
            <BookOpen className="size-3.5 text-accent" aria-hidden />
            <ChipLabel>{label}</ChipLabel>
            <ChevronDown className="size-3 opacity-60" aria-hidden />
          </button>
        )}
      </PopoverTrigger>
      <PopoverContent className="max-h-[min(36rem,70dvh)] w-[min(24rem,calc(100vw-1.5rem))] overflow-y-auto">
        <RecipeList presets={presets} comfyOnline={comfyOnline} />
      </PopoverContent>
    </Popover>
  )
}

export function DurationChip({ capabilities }: { capabilities: CapabilityResponse }) {
  useT()
  const length = useComposer((state) => state.length)
  const width = useComposer((state) => state.width)
  const height = useComposer((state) => state.height)
  const references = useComposer((state) => state.references)
  const status = guideStatus({ width, height, length }, findGuide(references))
  const mismatch = status !== null && !status.framesMatch
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn('chip', mismatch && 'border-warn/40 text-warn')}
          aria-label={
            mismatch
              ? t('Duración: {duration}, {length} frames. No coincide con la guía', {
                  duration: formatSecondsEs(lengthToSeconds(length)),
                  length,
                })
              : t('Duración: {duration}, {length} frames', { duration: formatSecondsEs(lengthToSeconds(length)), length })
          }
        >
          <Clock className="size-3.5" aria-hidden />
          <span className="tabular">
            {formatSecondsEs(lengthToSeconds(length))} · {length} f
          </span>
          <ChevronDown className="size-3 opacity-60" aria-hidden />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-[min(28rem,calc(100vw-1.5rem))]">
        <TimelineStrip options={capabilities.preferred_lengths} />
      </PopoverContent>
    </Popover>
  )
}

export function FrameChip() {
  useT()
  const width = useComposer((state) => state.width)
  const height = useComposer((state) => state.height)
  const autoRatio = useComposer((state) => state.auto_ratio)
  const setFrameSize = useComposer((state) => state.setFrameSize)
  const setAutoRatio = useComposer((state) => state.setAutoRatio)
  const aspect = matchAspectPreset(width, height)

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button type="button" className="chip" aria-label={t('Formato: {width} por {height}', { width, height })}>
          <RectangleHorizontal className={cn('size-3.5', height > width && 'rotate-90')} aria-hidden />
          <span className="tabular">
            {width}×{height}
          </span>
          <ChevronDown className="size-3 opacity-60" aria-hidden />
        </button>
      </PopoverTrigger>
      <PopoverContent className="space-y-3">
        <div className="flex items-center gap-1">
          <span className="eyebrow">{t('Formato')}</span>
          <InfoTip help={HELP.frame} label={t('Formato')} />
        </div>
        <div role="radiogroup" aria-label={t('Formato')} className="grid grid-cols-2 gap-1.5">
          {ASPECT_PRESETS.map((preset) => {
            const active = aspect?.id === preset.id
            return (
              <button
                key={preset.id}
                type="button"
                role="radio"
                aria-checked={active}
                onClick={() => setFrameSize(preset.width, preset.height)}
                className={cn(
                  'min-h-9 rounded-xl border px-2 py-1.5 text-left text-[11px] font-semibold tabular transition-colors',
                  active ? 'border-accent/50 bg-accent/10 text-fg' : 'border-white/[0.07] text-muted hover:bg-white/[0.05]',
                )}
              >
                {preset.label}
              </button>
            )
          })}
        </div>
        <div className="grid grid-cols-2 gap-2">
          <label className="space-y-1">
            <span className="eyebrow block">{t('Ancho')}</span>
            <Input
              type="number"
              inputMode="numeric"
              min={DIMENSION_MIN}
              max={DIMENSION_MAX}
              step={DIMENSION_STEP}
              value={width}
              aria-label={t('Ancho en píxeles')}
              onChange={(event) => setFrameSize(Number(event.target.value) || DIMENSION_MIN, height)}
              className="text-[16px] md:text-sm"
            />
          </label>
          <label className="space-y-1">
            <span className="eyebrow block">{t('Alto')}</span>
            <Input
              type="number"
              inputMode="numeric"
              min={DIMENSION_MIN}
              max={DIMENSION_MAX}
              step={DIMENSION_STEP}
              value={height}
              aria-label={t('Alto en píxeles')}
              onChange={(event) => setFrameSize(width, Number(event.target.value) || DIMENSION_MIN)}
              className="text-[16px] md:text-sm"
            />
          </label>
        </div>
        <p className="text-[10px] text-faint">
          {t('Múltiplos de {step} px, máximo {max}.', { step: DIMENSION_STEP, max: DIMENSION_MAX })}
        </p>
        <div className="flex items-center justify-between gap-3 text-xs">
          <span className="flex items-center gap-1 text-fg">
            {t('Ajustar a la primera imagen')}
            <InfoTip help={HELP.autoRatio} label={t('Ajustar a la primera imagen')} />
          </span>
          <Switch checked={autoRatio} onCheckedChange={setAutoRatio} aria-label={t('Ajustar proporción a la primera imagen')} />
        </div>
      </PopoverContent>
    </Popover>
  )
}

export function MethodChip({ capabilities }: { capabilities: CapabilityResponse }) {
  useT()
  const method = useComposer((state) => state.method)
  const info = capabilities.methods.find((entry) => entry.id === method)
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button type="button" className={cn('chip', info?.experimental && 'text-warn')} aria-label={t('Método: {method}', { method: info?.label ?? method })}>
          <Gauge className="size-3.5" aria-hidden />
          <ChipLabel>{info?.label ?? method}</ChipLabel>
          <ChevronDown className="size-3 opacity-60" aria-hidden />
        </button>
      </PopoverTrigger>
      <PopoverContent className="max-h-[min(34rem,70dvh)] w-[min(26rem,calc(100vw-1.5rem))] overflow-y-auto">
        <div className="mb-2 flex items-center gap-1 px-2.5">
          <span className="eyebrow">{t('Método / acelerador')}</span>
          <InfoTip help={HELP.method} label={t('Método')} />
        </div>
        <MethodPicker methods={capabilities.methods} comfyOnline={capabilities.comfy_online} />
      </PopoverContent>
    </Popover>
  )
}

export function SeedChip() {
  useT()
  const seed = useComposer((state) => state.seed)
  const setSeed = useComposer((state) => state.setSeed)
  const randomizeSeed = useComposer((state) => state.randomizeSeed)
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button type="button" className={cn('chip', seed !== null && 'text-fg')} aria-label={seed === null ? t('Semilla aleatoria') : t('Semilla fija {seed}', { seed })}>
          {seed === null ? <Unlock className="size-3.5" aria-hidden /> : <Lock className="size-3.5 text-accent" aria-hidden />}
          <span className="tabular">{seed === null ? t('Semilla') : String(seed).slice(0, 8)}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent className="space-y-3">
        <div className="flex items-center gap-1">
          <span className="eyebrow">{t('Semilla')}</span>
          <InfoTip help={HELP.seed} label={t('Semilla')} />
        </div>
        <label className="flex items-center justify-between gap-3 text-xs text-fg">
          {t('Fijar semilla')}
          <Switch
            checked={seed !== null}
            onCheckedChange={(locked) => (locked ? randomizeSeed() : setSeed(null))}
            aria-label={t('Fijar semilla')}
          />
        </label>
        {seed !== null ? (
          <div className="flex items-center gap-1.5">
            <Input
              type="number"
              min={0}
              value={seed}
              aria-label={t('Semilla')}
              onChange={(event) => {
                const next = Number(event.target.value)
                setSeed(Number.isFinite(next) && next >= 0 ? Math.floor(next) : 0)
              }}
              className="tabular text-[16px] md:text-sm"
            />
            <button
              type="button"
              onClick={randomizeSeed}
              aria-label={t('Tirar una semilla nueva')}
              className="flex size-10 shrink-0 items-center justify-center rounded-xl border border-white/10 text-muted hover:bg-white/[0.06] hover:text-fg"
            >
              <Dices className="size-4" aria-hidden />
            </button>
          </div>
        ) : (
          <p className="text-[11px] text-faint">{t('Cada toma usa una semilla nueva.')}</p>
        )}
      </PopoverContent>
    </Popover>
  )
}

export function AdvancedChip() {
  useT()
  const setInspectorTab = useUi((state) => state.setInspectorTab)
  return (
    <button
      type="button"
      className="chip"
      data-tour="advanced"
      onClick={() => {
        setInspectorTab('settings')
        document.getElementById('advanced-settings')?.scrollIntoView({ block: 'start', behavior: 'smooth' })
      }}
    >
      <SlidersHorizontal className="size-3.5" aria-hidden />
      {t('Avanzado')}
    </button>
  )
}
