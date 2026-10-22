import { EyeOff, Film, Loader2, Music } from 'lucide-react'

import { api } from '../../lib/api'
import { cn } from '../../lib/cn'
import { STATUS_LABEL } from '../../lib/curation'
import { formatRelative, formatSeconds } from '../../lib/format'
import type { JobOut } from '../../lib/types'
import { Badge } from '../ui/badge'
import { LazyVideo } from '../ui/lazy-video'
import { ProgressBar } from '../ui/progress'
import { TakeActions } from '../stage/TakeActions'
import { t, useT } from '../../i18n'

interface TakeCardProps {
  job: JobOut
  selected: boolean
  onSelect: () => void
}

export function TakeCard({ job, selected, onSelect }: TakeCardProps) {
  useT()
  const video = job.outputs.find((output) => output.kind === 'video')
  const image = job.outputs.find((output) => output.kind === 'image')
  const audio = job.outputs.find((output) => output.kind === 'audio')
  const active = job.status === 'queued' || job.status === 'running'

  return (
    <li
      className={cn(
        'group overflow-hidden rounded-2xl border bg-ink-900 transition-colors',
        selected ? 'border-accent/60' : 'border-white/[0.06] hover:border-white/20',
      )}
    >
      <button
        type="button"
        onClick={onSelect}
        aria-current={selected}
        className="block w-full text-left"
        aria-label={t('Ver {title} en el escenario', { title: job.title ?? t('toma sin título') })}
      >
        <span className="relative block aspect-video overflow-hidden bg-ink-950">
          {video ? (
            <LazyVideo
              src={api.outputUrl(video.id)}
              loop
              className="size-full object-cover transition-opacity group-hover:opacity-90"
              onMouseEnter={(event) => void event.currentTarget.play().catch(() => undefined)}
              onMouseLeave={(event) => {
                event.currentTarget.pause()
                event.currentTarget.currentTime = 0
              }}
            />
          ) : image ? (
            <img src={api.outputUrl(image.id)} alt="" loading="lazy" className="size-full object-cover" />
          ) : (
            <span className="flex size-full items-center justify-center">
              {active ? (
                <Loader2 className="size-5 animate-spin text-accent" aria-hidden />
              ) : audio ? (
                <Music className="size-5 text-ink-600" aria-hidden />
              ) : (
                <Film className="size-5 text-ink-600" aria-hidden />
              )}
            </span>
          )}

          {job.hidden ? (
            <span className="absolute left-1.5 top-1.5 rounded-sm bg-ink-950/80 p-1">
              <EyeOff className="size-3 text-faint" aria-label={t('Oculta')} />
            </span>
          ) : null}

          <span className="absolute bottom-1.5 right-1.5 flex gap-1">
            {job.status !== 'completed' ? (
              <Badge
                tone={job.status === 'failed' ? 'danger' : job.status === 'running' ? 'accent' : 'neutral'}
                className="bg-ink-950/85"
              >
                {STATUS_LABEL[job.status]}
              </Badge>
            ) : null}
          </span>

          {active ? (
            <span className="absolute inset-x-0 bottom-0 block">
              <ProgressBar value={job.progress > 0 ? job.progress : null} className="h-0.5 rounded-none" />
            </span>
          ) : null}
        </span>

        <span className="block px-2.5 pb-1.5 pt-2">
          <span className="block truncate text-xs font-semibold text-fg">{job.title ?? t('Toma sin título')}</span>
          <span className="mt-0.5 block truncate text-[11px] text-faint">{job.prompt}</span>
          <span className="tabular mt-1 block text-[10px] text-faint">
            {job.width}×{job.height} · {job.length} f · {job.method}
            {job.duration_seconds !== null ? ` · ${formatSeconds(job.duration_seconds)}` : ''} ·{' '}
            {formatRelative(job.created_at)}
          </span>
        </span>
      </button>

      <div className="border-t border-white/[0.05] px-1.5 py-1">
        <TakeActions job={job} iconOnly size="sm" />
      </div>
    </li>
  )
}
