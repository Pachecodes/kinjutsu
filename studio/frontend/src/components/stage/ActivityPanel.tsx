import { ScrollText } from 'lucide-react'

import { useJobEvents } from '../../hooks/queries'
import { cn } from '../../lib/cn'
import { MODE_COPY } from '../../lib/curation'
import { formatTimeOfDay } from '../../lib/format'
import type { JobOut } from '../../lib/types'
import { EmptyState, ErrorState, Skeleton } from '../ui/states'

/** Logs are deliberately secondary: the stage is the product, this explains it. */
export function ActivityPanel({ job }: { job: JobOut | null }) {
  const active = job?.status === 'queued' || job?.status === 'running'
  const events = useJobEvents(job?.id ?? null, Boolean(active))

  if (!job) {
    return <EmptyState compact icon={ScrollText} title="Ninguna toma seleccionada" body="Aquí aparece el registro de la toma." />
  }

  if (events.isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-4 w-2/3" />
      </div>
    )
  }

  if (events.isError) {
    return <ErrorState message="No se pudo cargar la actividad de esta toma." onRetry={() => void events.refetch()} />
  }

  const items = events.data?.events ?? []

  return (
    <div className="space-y-3">
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-[11px]">
        <dt className="text-faint">Tarea</dt>
        <dd className="text-right text-muted">{MODE_COPY[job.mode].label}</dd>
        <dt className="text-faint">Método</dt>
        <dd className="text-right text-muted">{job.method}</dd>
        <dt className="text-faint">Semilla</dt>
        <dd className="tabular truncate text-right text-muted">{job.seed}</dd>
        {job.comfy_prompt_id ? (
          <>
            <dt className="text-faint">Prompt de Comfy</dt>
            <dd className="truncate text-right font-mono text-[10px] text-muted">{job.comfy_prompt_id}</dd>
          </>
        ) : null}
      </dl>

      {job.error ? (
        <p className="rounded-xl border border-danger/40 bg-danger-soft/40 px-2.5 py-1.5 text-[11px] leading-snug text-danger">
          {job.error}
        </p>
      ) : null}

      {items.length === 0 ? (
        <EmptyState compact icon={ScrollText} title="Sin actividad registrada" />
      ) : (
        <ol className="space-y-1">
          {items.map((event) => (
            <li key={event.id} className="flex gap-2 text-[11px] leading-snug">
              <span className="tabular shrink-0 text-faint">{formatTimeOfDay(event.created_at)}</span>
              <span className={cn('min-w-0', event.level === 'error' ? 'text-danger' : 'text-muted')}>
                {event.message}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
