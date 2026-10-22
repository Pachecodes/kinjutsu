import { Clapperboard } from 'lucide-react'
import { useState } from 'react'

import { useJobs } from '../../hooks/queries'
import type { JobOut, JobStatus } from '../../lib/types'
import { useUi } from '../../state/ui'
import { Segmented } from '../ui/segmented'
import { EmptyState, ErrorState, Skeleton } from '../ui/states'
import { Switch } from '../ui/switch'
import { TakeCard } from './TakeCard'
import { t, useT } from '../../i18n'

type Filter = 'all' | 'completed' | 'active' | 'failed'

const FILTER_STATUSES: Record<Filter, JobStatus[]> = {
  all: [],
  completed: ['completed'],
  active: ['queued', 'running'],
  failed: ['failed', 'canceled'],
}

export function Gallery({ className }: { className?: string }) {
  useT()
  const showHidden = useUi((state) => state.showHidden)
  const setShowHidden = useUi((state) => state.setShowHidden)
  const selectedJobId = useUi((state) => state.selectedJobId)
  const selectJob = useUi((state) => state.selectJob)
  const [filter, setFilter] = useState<Filter>('all')

  const jobs = useJobs({ includeHidden: showHidden, statuses: FILTER_STATUSES[filter] })
  const items: JobOut[] = jobs.data?.jobs ?? []

  return (
    <section aria-label={t('Galería')} className={className} data-tour="gallery">
      <div className="mb-2.5 flex flex-wrap items-center gap-2">
        <h2 className="eyebrow mr-auto">
          {t('Tomas')}{jobs.data ? ` (${jobs.data.total})` : ''}
        </h2>
        <Segmented
          size="sm"
          label={t('Filtrar tomas')}
          className="w-auto"
          value={filter}
          onValueChange={setFilter}
          options={[
            { value: 'all', label: t('Todas') },
            { value: 'completed', label: t('Listas') },
            { value: 'active', label: t('En curso') },
            { value: 'failed', label: t('Fallidas') },
          ]}
        />
        <label className="flex items-center gap-1.5 text-[11px] text-muted">
          <Switch checked={showHidden} onCheckedChange={setShowHidden} aria-label={t('Mostrar tomas ocultas')} />
          {t('Ocultas')}
        </label>
      </div>

      {jobs.isLoading ? (
        <ul className="grid grid-cols-2 gap-2 lg:grid-cols-3 xl:grid-cols-4">
          {[0, 1, 2, 3].map((key) => (
            <li key={key}>
              <Skeleton className="aspect-video w-full" />
            </li>
          ))}
        </ul>
      ) : jobs.isError ? (
        <ErrorState
          title={t('Historial no disponible')}
          message={t('El backend del Studio no devolvió el historial de tomas.')}
          onRetry={() => void jobs.refetch()}
        />
      ) : items.length === 0 ? (
        <EmptyState
          compact
          icon={Clapperboard}
          title={filter === 'all' ? t('Todavía no hay tomas') : t('Nada coincide con este filtro')}
          body={
            filter === 'all'
              ? t('Cada render llega aquí con su receta, listo para reutilizar.')
              : t('Prueba otro filtro o muestra las tomas ocultas.')
          }
        />
      ) : (
        <ul className="grid grid-cols-2 gap-2 lg:grid-cols-3 xl:grid-cols-4">
          {items.map((job) => (
            <TakeCard
              key={job.id}
              job={job}
              selected={selectedJobId === job.id}
              onSelect={() => selectJob(job.id)}
            />
          ))}
        </ul>
      )}
    </section>
  )
}
