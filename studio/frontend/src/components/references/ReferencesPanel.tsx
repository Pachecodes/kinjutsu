import { ImagePlus, Layers, Loader2, Upload } from 'lucide-react'
import { useRef, useState } from 'react'

import { ACCEPT_BY_KIND, useReferenceIngest } from '../../hooks/useReferenceIngest'
import { MODE_COPY } from '../../lib/curation'
import { cn } from '../../lib/cn'
import {
  MAX_REF_AUDIOS,
  MAX_REF_IMAGES,
  MAX_REF_VIDEOS,
  countByKind,
  isReferenceMode,
  kindsFor,
  maxReferencesFor,
  referenceTags,
} from '../../lib/references'
import type { RefKind, StudioConfig } from '../../lib/types'
import { useComposer } from '../../state/composer'
import { Button } from '../ui/button'
import { EmptyState } from '../ui/states'
import { GuideSync } from './GuideSync'
import { LibraryDialog } from './LibraryDialog'
import { ReferenceCard } from './ReferenceCard'
import { localized, t, useT } from '../../i18n'

const KIND_WORD: Record<RefKind, string> = localized(() => ({ image: t('imágenes'), video: t('vídeos'), audio: t('audios') }))

function CountPill({ label, used, max }: { label: string; used: number; max: number }) {
  return (
    <span
      className={cn(
        'rounded-md border px-1.5 py-0.5 tabular text-[10px]',
        used >= max ? 'border-warn/40 bg-warn-soft/40 text-warn' : 'border-white/10 text-faint',
      )}
    >
      {label} {used}/{max}
    </span>
  )
}

/**
 * Every reference in detail: role, order (the `<Picture i>` numbering), clip
 * sound and guide preparation. The composer tray is the quick view; this is
 * where a creator fine-tunes what each file contributes.
 */
export function ReferencesPanel({ config }: { config: StudioConfig }) {
  useT()
  const mode = useComposer((state) => state.mode)
  const references = useComposer((state) => state.references)
  const clearReferences = useComposer((state) => state.clearReferences)
  const reorderReference = useComposer((state) => state.reorderReference)
  const { ingest, progress } = useReferenceIngest()

  const inputRef = useRef<HTMLInputElement>(null)
  const [dropActive, setDropActive] = useState(false)
  const [dragIndex, setDragIndex] = useState<number | null>(null)

  const kinds = kindsFor(mode)
  const counts = countByKind(references)
  const tags = referenceTags(mode, references)

  if (kinds.length === 0) {
    return (
      <EmptyState
        icon={Layers}
        title={t('Esta tarea no usa referencias')}
        body={t('{mode} genera solo desde el prompt. Cambia a Animar una imagen, Referencias o Performance para añadir archivos.', { mode: MODE_COPY[mode].label })}
      />
    )
  }

  return (
    <div className="flex h-full flex-col gap-3">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="eyebrow mr-auto">
          Refs ({references.length}/{maxReferencesFor(mode)})
        </span>
        {isReferenceMode(mode) ? (
          <>
            <CountPill label="Img" used={counts.image} max={MAX_REF_IMAGES} />
            <CountPill label="Vid" used={counts.video} max={MAX_REF_VIDEOS} />
            <CountPill label="Aud" used={counts.audio} max={MAX_REF_AUDIOS} />
          </>
        ) : null}
      </div>

      <div
        onDragOver={(event) => {
          event.preventDefault()
          if (dragIndex === null) setDropActive(true)
        }}
        onDragLeave={() => setDropActive(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDropActive(false)
          if (event.dataTransfer.files.length > 0) void ingest(event.dataTransfer.files)
        }}
        className={cn(
          'rounded-2xl border border-dashed p-3 text-center transition-colors',
          dropActive ? 'border-accent bg-accent/5' : 'border-white/15 bg-black/20',
        )}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={kinds.map((kind) => ACCEPT_BY_KIND[kind]).join(',')}
          className="sr-only"
          aria-label={t('Añadir archivos de referencia')}
          onChange={(event) => {
            if (event.target.files?.length) void ingest(event.target.files)
            event.target.value = ''
          }}
        />
        {progress ? (
          <div className="space-y-1.5" role="status">
            <p className="flex items-center justify-center gap-2 text-[11px] text-muted">
              <Loader2 className="size-3.5 animate-spin" aria-hidden />
              <span className="truncate">{t('Subiendo {name}', { name: progress.name })}</span>
            </p>
            <div className="h-1 overflow-hidden rounded-full bg-ink-700">
              <div
                className="h-full rounded-full bg-accent transition-[width]"
                style={{ width: `${Math.round(progress.fraction * 100)}%` }}
              />
            </div>
          </div>
        ) : (
          <>
            <Upload className="mx-auto size-4 text-faint" aria-hidden />
            <p className="mt-1 text-[11px] text-muted">
              {t('Suelta {kinds} aquí o', { kinds: kinds.map((kind) => KIND_WORD[kind]).join(', ') })}{' '}
              <button
                type="button"
                className="font-semibold text-accent underline underline-offset-2"
                onClick={() => inputRef.current?.click()}
              >
                {t('elige archivos')}
              </button>
            </p>
            <p className="mt-0.5 text-[10px] text-faint">
              {t('Hasta {image} MB imagen · {video} MB vídeo · {audio} MB audio. Los originales nunca se modifican.', {
                image: config.upload_limits.image_mb,
                video: config.upload_limits.video_mb,
                audio: config.upload_limits.audio_mb,
              })}
            </p>
          </>
        )}
      </div>

      <div className="flex items-center gap-1.5">
        <LibraryDialog kinds={kinds} />
        {references.length > 0 ? (
          <Button variant="ghost" size="sm" onClick={clearReferences} className="ml-auto">
            {t('Quitar todas de la toma')}
          </Button>
        ) : null}
      </div>

      <GuideSync compact />

      {references.length === 0 ? (
        <EmptyState
          compact
          icon={ImagePlus}
          title={t('Aún no hay referencias')}
          body={
            mode === 'performance'
              ? t('Performance necesita un retrato de identidad y un clip de movimiento.')
              : mode === 'first_last'
                ? t('Añade la imagen inicial y después la final.')
                : mode === 'first_frame'
                  ? t('Añade la imagen con la que abre la toma.')
                  : t('Hasta 9 imágenes, 3 clips y 3 audios. El orden define la numeración <Picture i>.')
          }
        />
      ) : (
        <ul className="min-h-0 flex-1 space-y-1.5 overflow-y-auto pr-0.5">
          {references.map((slot, index) => (
            <ReferenceCard
              alignedGuides={config.capabilities.aligned_guides ?? false}
              key={slot.uid}
              slot={slot}
              index={index}
              total={references.length}
              mode={mode}
              tag={tags[index]}
              dragging={dragIndex === index}
              onDragStart={() => setDragIndex(index)}
              onDragEnd={() => setDragIndex(null)}
              onDragOver={() => {
                if (dragIndex !== null && dragIndex !== index) {
                  reorderReference(dragIndex, index)
                  setDragIndex(index)
                }
              }}
            />
          ))}
        </ul>
      )}
    </div>
  )
}
