import { useQuery } from '@tanstack/react-query'
import { AlertOctagon, Ban, Check, Clapperboard, Film, Loader2, X } from 'lucide-react'
import { useEffect, useState } from 'react'

import { useJobEvents } from '../../hooks/queries'
import { useTakeActions } from '../../hooks/useTakeActions'
import { api } from '../../lib/api'
import { cn } from '../../lib/cn'
import { CANCEL_COPY, PHASES, STATUS_LABEL, cancelOutcome, describeStage } from '../../lib/curation'
import { elapsedSeconds, formatClock, formatRelative, formatSeconds } from '../../lib/format'
import type { JobOut } from '../../lib/types'
import { ConfirmDialog } from '../ui/alert-dialog'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { ProgressBar } from '../ui/progress'
import { EmptyState, Skeleton } from '../ui/states'
import { TakeActions } from './TakeActions'

const STATUS_TONE = {
  queued: 'neutral',
  running: 'accent',
  completed: 'neutral',
  failed: 'danger',
  canceled: 'outline',
} as const

function useTicker(active: boolean): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [active])
  return now
}

/** Phases as a stepper. Phases a recipe skips simply stay unlit. */
function PhaseSteps({ job }: { job: JobOut }) {
  const stage = describeStage(job)
  const current = PHASES.findIndex((phase) => phase.id === stage.phase)
  return (
    <ol aria-label="Etapas del render" className="flex flex-wrap items-center justify-center gap-x-1 gap-y-1">
      {PHASES.map((phase, index) => {
        const done = index < current
        const active = index === current
        return (
          <li key={phase.id} className="flex items-center gap-1" aria-current={active ? 'step' : undefined}>
            <span
              className={cn(
                'flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold',
                active ? 'bg-accent text-accent-ink' : done ? 'text-accent' : 'text-faint',
              )}
            >
              {done ? <Check className="size-3" aria-hidden /> : null}
              {phase.label}
              <span className="sr-only">{active ? ' (en curso)' : done ? ' (hecha)' : ''}</span>
            </span>
            {index < PHASES.length - 1 ? <span aria-hidden className="h-px w-2 bg-white/15" /> : null}
          </li>
        )
      })}
    </ol>
  )
}

function RenderProgress({ job }: { job: JobOut }) {
  const { cancelTake, pending } = useTakeActions()
  const [confirming, setConfirming] = useState(false)
  const preview = useQuery({
    queryKey: ['live-preview', job.id],
    queryFn: api.latestPreview,
    refetchInterval: 1000,
    staleTime: 0,
  })
  const now = useTicker(true)
  const elapsed = elapsedSeconds(job.started_at, now)
  const queued = job.status === 'queued'
  const stage = describeStage(job)
  const live = preview.data

  return (
    <div className="relative flex size-full flex-col items-center justify-center overflow-hidden bg-ink-950 text-center">
      {live ? (
        live.data_url.startsWith('data:video/') ? (
          <video src={live.data_url} autoPlay loop muted playsInline aria-label="Vista previa en vivo" className="absolute inset-0 size-full object-contain" />
        ) : (
          <img src={live.data_url} alt="Vista previa en vivo" className="absolute inset-0 size-full object-contain" />
        )
      ) : null}
      <div
        className={cn(
          'relative z-10 mx-3 flex max-w-[34rem] flex-col items-center gap-3 rounded-2xl px-4 py-4',
          live ? 'bg-ink-950/80 backdrop-blur-sm' : '',
        )}
      >
        <Loader2 className="size-5 animate-spin text-accent" aria-hidden />
        <div className="space-y-1" role="status" aria-live="polite">
          <p className="display-title text-base text-fg">
            {queued
              ? job.queue_position && job.queue_position > 0
                ? `En cola · posición ${job.queue_position}`
                : 'En cola en H3 Lab'
              : stage.label}
          </p>
          <p className="tabular text-[11px] text-muted">
            {live ? `Paso ${live.step} / ${live.total} · ` : ''}
            {!queued && job.progress > 0 ? `${Math.round(job.progress * 100)}% de esta etapa` : 'Esta etapa no informa porcentaje'}
          </p>
        </div>
        <div className="w-60 max-w-full">
          <ProgressBar value={!queued && job.progress > 0 ? job.progress : null} label={`Progreso de la etapa: ${stage.label}`} />
        </div>
        <PhaseSteps job={job} />
        <p className="tabular text-[11px] text-faint">
          {elapsed !== null ? `Tiempo total ${formatClock(elapsed)}` : 'Esperando a que ComfyUI empiece'}
          {job.estimate_seconds ? ` · referencia ≈ ${formatSeconds(job.estimate_seconds)}, no es un compromiso` : ''}
        </p>
        <Button variant="outline" size="sm" loading={pending.cancel} onClick={() => setConfirming(true)}>
          <X aria-hidden />
          Cancelar toma
        </Button>
      </div>
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title="¿Cancelar esta toma?"
        description={
          <>
            <span className="block">
              {queued
                ? 'Se quitará de la cola antes de empezar.'
                : 'Se pedirá a ComfyUI que interrumpa el render. Se detiene al terminar el paso en curso y el trabajo hecho se pierde.'}
            </span>
            <span className="mt-2 block text-xs text-faint">
              Solo se interrumpe un render de este Studio; nunca otro trabajo de la GPU.
            </span>
          </>
        }
        confirmLabel="Cancelar toma"
        cancelLabel="Seguir generando"
        busy={pending.cancel}
        onConfirm={() => {
          void cancelTake(job).then(() => setConfirming(false))
        }}
      />
    </div>
  )
}

function CanceledState({ job }: { job: JobOut }) {
  const events = useJobEvents(job.id, false)
  const outcome = cancelOutcome((events.data?.events ?? []).map((event) => event.message))
  return (
    <EmptyState
      icon={Ban}
      title="Toma cancelada"
      body={
        <span className="block space-y-1">
          <span className="block">{events.isLoading ? 'Comprobando qué llegó a calcularse…' : CANCEL_COPY[outcome]}</span>
          <span className="block text-faint">No se guardó ningún archivo de esta toma.</span>
        </span>
      }
    />
  )
}

function Viewer({ job }: { job: JobOut }) {
  const video = job.outputs.find((output) => output.kind === 'video')
  const audio = job.outputs.find((output) => output.kind === 'audio')
  const image = job.outputs.find((output) => output.kind === 'image')
  if (video) {
    return (
      <video
        key={video.id}
        src={api.outputUrl(video.id)}
        controls
        autoPlay
        loop
        playsInline
        preload="metadata"
        className="size-full bg-ink-950 object-contain"
        aria-label={job.title ?? 'Toma renderizada'}
      />
    )
  }
  if (image) {
    return <img src={api.outputUrl(image.id)} alt={job.title ?? 'Toma renderizada'} className="size-full object-contain" />
  }
  if (audio) {
    return (
      <div className="flex size-full items-center justify-center p-8">
        <audio src={api.outputUrl(audio.id)} controls className="w-full max-w-md" aria-label="Audio renderizado" />
      </div>
    )
  }
  return <EmptyState icon={Film} title="Esta toma no produjo un archivo reproducible" />
}

interface OutputStageProps {
  job: JobOut | null
  loading: boolean
  hasAnyTake: boolean
}

export function OutputStage({ job, loading, hasAnyTake }: OutputStageProps) {
  const active = job !== null && (job.status === 'queued' || job.status === 'running')
  return (
    <section aria-label="Escenario" className="flex min-h-0 flex-col gap-2.5" data-tour="stage">
      <div
        className={cn(
          'relative flex h-[clamp(15rem,44dvh,34rem)] flex-none items-center justify-center overflow-hidden rounded-[1.5rem] border border-white/[0.06]',
          job?.status === 'completed' ? 'bg-ink-950' : 'stage-surface',
        )}
      >
        {loading ? (
          <Skeleton className="size-full rounded-none" />
        ) : !job ? (
          <EmptyState
            icon={Clapperboard}
            title={hasAnyTake ? 'Elige una toma de la galería' : 'Todavía no hay tomas'}
            body={
              hasAnyTake
                ? 'Tus últimos renders están abajo. Selecciona uno para verlo aquí.'
                : 'Elige una receta, sube tus referencias, escribe el prompt y pulsa Generar. El render aparece aquí mientras ocurre.'
            }
          />
        ) : active ? (
          <RenderProgress job={job} />
        ) : job.status === 'failed' ? (
          <EmptyState
            icon={AlertOctagon}
            title="Esta toma falló"
            body={
              <span className="block space-y-1">
                <span className="block text-danger">{job.error ?? 'ComfyUI informó un error de ejecución.'}</span>
                <span className="block text-faint">Pulsa Reutilizar para cargar la receta y corregirla; el detalle está en Actividad.</span>
              </span>
            }
          />
        ) : job.status === 'canceled' ? (
          <CanceledState job={job} />
        ) : (
          <Viewer job={job} />
        )}
      </div>
      {job ? (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-1">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <p className="display-title truncate text-[15px] text-fg">{job.title ?? 'Toma sin título'}</p>
              <Badge tone={STATUS_TONE[job.status]}>{STATUS_LABEL[job.status]}</Badge>
              {job.hidden ? <Badge tone="outline">oculta</Badge> : null}
            </div>
            <p className="tabular mt-0.5 text-[11px] text-faint">
              {job.width}×{job.height} · {job.length} f · {job.steps} pasos · semilla {job.seed}
              {job.duration_seconds !== null ? ` · render en ${formatSeconds(job.duration_seconds)}` : ''}
              {` · ${formatRelative(job.created_at)}`}
            </p>
          </div>
          <TakeActions job={job} />
        </div>
      ) : null}
    </section>
  )
}
