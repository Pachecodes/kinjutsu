import { FolderOpen, ImagePlus, Loader2, Music, Plus, Video, X } from 'lucide-react'
import { useRef, useState, type DragEvent } from 'react'

import { ACCEPT_ALL, ACCEPT_BY_KIND, useReferenceIngest } from '../../hooks/useReferenceIngest'
import { isSwapPreset } from '../../lib/curation'
import { cn } from '../../lib/cn'
import { ROLE_HELP } from '../../lib/help'
import {
  ROLE_META,
  countByKind,
  isReferenceMode,
  kindsFor,
  maxReferencesFor,
  referenceTags,
  type ReferenceSlot,
} from '../../lib/references'
import { slotsFor, type SlotSpec } from '../../lib/recipeRoute'
import type { RefKind } from '../../lib/types'
import { useComposer } from '../../state/composer'
import { useUi } from '../../state/ui'
import { LibraryDialog } from '../references/LibraryDialog'
import { InfoTip } from '../ui/info-tip'

function Thumb({ slot }: { slot: ReferenceSlot }) {
  const { asset } = slot
  if (asset.kind === 'image') return <img src={asset.url} alt="" draggable={false} className="size-full object-cover" />
  if (asset.kind === 'video') {
    return <video src={asset.url} muted playsInline preload="metadata" className="size-full object-cover" aria-hidden />
  }
  return (
    <span className="flex size-full items-center justify-center bg-ink-800">
      <Music className="size-5 text-faint" aria-hidden />
    </span>
  )
}

function FilledTile({ slot, tag, label }: { slot: ReferenceSlot; tag: string | null; label?: string }) {
  const removeReference = useComposer((state) => state.removeReference)
  const setInspectorTab = useUi((state) => state.setInspectorTab)
  const setMobileView = useUi((state) => state.setMobileView)
  const roleLabel = label ?? ROLE_META[slot.role].label

  return (
    <li className="group relative w-[6.5rem] shrink-0">
      <button
        type="button"
        onClick={() => {
          setInspectorTab('references')
          setMobileView('refs')
        }}
        aria-label={`${roleLabel}: ${slot.asset.original_name}. Ver detalles`}
        className="block w-full overflow-hidden rounded-xl border border-white/[0.08] bg-ink-950 text-left transition-colors hover:border-accent/50"
      >
        <span className="relative block aspect-square">
          <Thumb slot={slot} />
          {tag ? (
            <span className="absolute left-1 top-1 rounded-md bg-ink-950/85 px-1 py-0.5 font-mono text-[9px] text-accent">
              {tag}
            </span>
          ) : null}
          {slot.role === 'aligned_guide' ? (
            <span className="absolute left-1 top-1 rounded-md bg-ink-950/85 px-1 py-0.5 text-[9px] font-semibold text-accent">
              guía
            </span>
          ) : null}
        </span>
        <span className="block truncate px-1.5 pb-1 pt-1 text-[10px] font-bold uppercase tracking-caps text-muted">
          {roleLabel}
        </span>
      </button>
      <button
        type="button"
        onClick={() => removeReference(slot.uid)}
        aria-label={`Quitar ${slot.asset.original_name}`}
        className="absolute -right-1.5 -top-1.5 flex size-6 items-center justify-center rounded-full border border-white/10 bg-ink-800 text-muted shadow-lift transition-colors hover:bg-danger hover:text-fg"
      >
        <X className="size-3" aria-hidden />
      </button>
    </li>
  )
}

function EmptyTile({
  spec,
  onPick,
  disabled,
}: {
  spec: Pick<SlotSpec, 'key' | 'kind' | 'label' | 'hint' | 'required'>
  onPick: (kind: RefKind) => void
  disabled: boolean
}) {
  const Icon = spec.kind === 'video' ? Video : spec.kind === 'audio' ? Music : ImagePlus
  return (
    <li className="w-[6.5rem] shrink-0">
      <button
        type="button"
        data-focus={`slot-${spec.key}`}
        disabled={disabled}
        onClick={() => onPick(spec.kind)}
        aria-label={`Subir ${spec.label.toLowerCase()}${spec.required ? ' (obligatorio)' : ' (opcional)'}`}
        className={cn(
          'flex aspect-square w-full flex-col items-center justify-center gap-1 rounded-xl border border-dashed px-1.5 text-center transition-colors',
          spec.required
            ? 'border-accent/35 bg-accent/[0.04] text-accent hover:border-accent hover:bg-accent/[0.08]'
            : 'border-white/15 text-faint hover:border-white/30 hover:text-fg',
          'disabled:cursor-not-allowed disabled:opacity-50',
        )}
      >
        <Icon className="size-5" aria-hidden />
        <span className="text-[10px] font-bold uppercase tracking-caps">{spec.label}</span>
        <span className="text-[9px] leading-tight text-faint">{spec.hint}</span>
      </button>
    </li>
  )
}

/**
 * The ordered references inside the composer. Slot-aware tasks show their named
 * places (Identity, Guide…), so the creator sees what is missing before writing
 * a word; free References mode shows the `<Picture i>` numbering the builder uses.
 */
export function ReferenceTray() {
  const mode = useComposer((state) => state.mode)
  const presetId = useComposer((state) => state.presetId)
  const references = useComposer((state) => state.references)
  const { ingest, progress, uploading } = useReferenceIngest()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dropActive, setDropActive] = useState(false)

  const kinds = kindsFor(mode)
  if (kinds.length === 0) return null

  const tags = referenceTags(mode, references)
  const specs = slotsFor(mode, presetId)
  const counts = countByKind(references)
  const max = maxReferencesFor(mode)

  // Pair each named slot with the first reference that fills it; the rest are extras.
  const used = new Set<string>()
  const placed = specs.map((spec) => {
    const slot = references.find(
      (candidate) => !used.has(candidate.uid) && candidate.asset.kind === spec.kind && spec.roles.includes(candidate.role),
    )
    if (slot) used.add(slot.uid)
    return { spec, slot }
  })
  const extras = references.filter((slot) => !used.has(slot.uid))
  const full = references.length >= max

  const pick = (kind?: RefKind) => {
    const input = inputRef.current
    if (!input) return
    // Narrow the picker to what the slot takes, synchronously, inside the click.
    input.accept = kind ? ACCEPT_BY_KIND[kind] : kinds.map((entry) => ACCEPT_BY_KIND[entry]).join(',')
    input.click()
  }

  const onDrop = (event: DragEvent<HTMLElement>) => {
    event.preventDefault()
    setDropActive(false)
    if (event.dataTransfer.files.length > 0) void ingest(event.dataTransfer.files)
  }

  return (
    <section
      aria-label="Referencias de la toma"
      data-tour="reference-tray"
      onDragOver={(event) => {
        if (!event.dataTransfer.types.includes('Files')) return
        event.preventDefault()
        setDropActive(true)
      }}
      onDragLeave={() => setDropActive(false)}
      onDrop={onDrop}
      className={cn(
        'relative rounded-2xl border px-2.5 pb-2.5 pt-2 transition-colors',
        dropActive ? 'border-accent bg-accent/[0.05]' : 'border-white/[0.05] bg-black/20',
      )}
    >
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPT_ALL}
        className="sr-only"
        tabIndex={-1}
        aria-label="Subir archivos de referencia"
        onChange={(event) => {
          if (event.target.files?.length) void ingest(event.target.files)
          event.target.value = ''
        }}
      />
      <div className="mb-2 flex flex-wrap items-center gap-1.5">
        <span className="eyebrow mr-1">
          Refs ({references.length}/{max})
        </span>
        {isReferenceMode(mode) ? (
          <span className="tabular text-[10px] text-faint">
            Img {counts.image}/9 · Vid {counts.video}/3 · Aud {counts.audio}/3
          </span>
        ) : null}
        <span className="ml-auto flex items-center gap-1">
          <LibraryDialog
            kinds={kinds}
            trigger={
              <button type="button" className="chip min-h-8 px-2.5 py-1 text-[10px]">
                <FolderOpen className="size-3.5" aria-hidden />
                Biblioteca
              </button>
            }
          />
        </span>
      </div>

      {progress ? (
        <div role="status" className="mb-2 space-y-1">
          <p className="flex items-center gap-2 text-[11px] text-muted">
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
            <span className="truncate">Subiendo {progress.name}…</span>
            <span className="tabular ml-auto">{Math.round(progress.fraction * 100)}%</span>
          </p>
          <div className="h-1 overflow-hidden rounded-full bg-ink-700">
            <div className="h-full rounded-full bg-accent transition-[width]" style={{ width: `${Math.round(progress.fraction * 100)}%` }} />
          </div>
        </div>
      ) : null}

      <ul className="flex flex-wrap gap-2.5 pr-1.5 pt-1.5">
        {placed.map(({ spec, slot }) =>
          slot ? (
            <FilledTile
              key={spec.key}
              slot={slot}
              tag={tags[references.indexOf(slot)] ?? null}
              label={spec.label}
            />
          ) : (
            <EmptyTile key={spec.key} spec={spec} onPick={pick} disabled={uploading} />
          ),
        )}
        {extras.map((slot) => (
          <FilledTile key={slot.uid} slot={slot} tag={tags[references.indexOf(slot)] ?? null} />
        ))}
        {!full && (specs.length === 0 || (isReferenceMode(mode) && !isSwapPreset(presetId))) ? (
          <EmptyTile
            spec={{
              key: 'add',
              kind: kinds[0],
              label: specs.length === 0 ? 'Añadir' : 'Otra ref.',
              hint: kinds.length > 1 ? 'Imagen, vídeo o audio' : 'Imagen',
              required: false,
            }}
            onPick={() => pick()}
            disabled={uploading}
          />
        ) : null}
      </ul>

      {specs.length > 0 && placed.some(({ slot }) => !slot) ? (
        <p className="mt-2 flex items-center gap-1 text-[11px] text-faint">
          Arrastra archivos aquí o pulsa un hueco.
          {placed.find(({ slot }) => !slot)?.spec.roles[0] ? (
            <InfoTip
              help={ROLE_HELP[placed.find(({ slot }) => !slot)!.spec.roles[0]]}
              label={placed.find(({ slot }) => !slot)!.spec.label}
            />
          ) : null}
        </p>
      ) : null}
      {dropActive ? (
        <div aria-hidden className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-2xl">
          <span className="flex items-center gap-2 rounded-full border border-accent/30 bg-ink-950/90 px-3 py-1.5 text-[11px] font-bold text-accent">
            <Plus className="size-3.5" />
            Suelta para añadir
          </span>
        </div>
      ) : null}
    </section>
  )
}
