import { AlertTriangle, ChevronDown, ChevronUp, GripVertical, Music, Video, X } from 'lucide-react'

import { cn } from '../../lib/cn'
import { formatBytes } from '../../lib/format'
import { ROLE_HELP } from '../../lib/help'
import { durationWarning, ROLE_META, rolesFor, type ReferenceSlot } from '../../lib/references'
import type { Mode, RefRole } from '../../lib/types'
import { useComposer } from '../../state/composer'
import { Button } from '../ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select'
import { Switch } from '../ui/switch'
import { PrepareGuide } from './PrepareGuide'
import { InfoTip } from '../ui/info-tip'
import { Tooltip } from '../ui/tooltip'

interface ReferenceCardProps {
  alignedGuides?: boolean
  slot: ReferenceSlot
  index: number
  total: number
  mode: Mode
  tag: string | null
  dragging: boolean
  onDragStart: () => void
  onDragEnd: () => void
  onDragOver: () => void
}

function Thumbnail({ slot }: { slot: ReferenceSlot }) {
  const { asset } = slot
  if (asset.kind === 'image') {
    return (
      <img
        src={asset.url}
        alt={asset.original_name}
        loading="lazy"
        className="size-full object-cover"
        draggable={false}
      />
    )
  }
  if (asset.kind === 'video') {
    return (
      <video
        src={asset.url}
        muted
        playsInline
        preload="metadata"
        className="size-full object-cover"
        aria-label={asset.original_name}
      />
    )
  }
  return (
    <div className="flex size-full items-center justify-center bg-ink-800">
      <Music className="size-5 text-faint" aria-hidden />
    </div>
  )
}

export function ReferenceCard({
  alignedGuides = false,
  slot,
  index,
  total,
  mode,
  tag,
  dragging,
  onDragStart,
  onDragEnd,
  onDragOver,
}: ReferenceCardProps) {
  const setRole = useComposer((state) => state.setRole)
  const setIncludeAudio = useComposer((state) => state.setIncludeAudio)
  const removeReference = useComposer((state) => state.removeReference)
  const reorderReference = useComposer((state) => state.reorderReference)

  const roles = rolesFor(mode, slot.asset.kind)
  const warning = durationWarning(slot)
  const duration = slot.asset.duration_seconds

  return (
    <li
      draggable
      onDragStart={(event) => {
        event.dataTransfer.effectAllowed = 'move'
        // Firefox refuses to start a drag without payload.
        event.dataTransfer.setData('text/plain', slot.uid)
        onDragStart()
      }}
      onDragEnd={onDragEnd}
      onDragOver={(event) => {
        event.preventDefault()
        onDragOver()
      }}
      className={cn(
        'group flex gap-2.5 rounded-2xl border border-white/[0.06] bg-ink-850 p-2 transition-colors',
        dragging && 'border-accent/50 opacity-60',
      )}
      aria-label={`Referencia ${index + 1}: ${slot.asset.original_name}`}
    >
      <div className="flex flex-col items-center gap-0.5 pt-0.5">
        <GripVertical className="size-3.5 cursor-grab text-ink-600 group-hover:text-faint" aria-hidden />
        <Button
          variant="ghost"
          size="icon-sm"
          className="size-5"
          aria-label={`Subir ${slot.asset.original_name} en el orden`}
          disabled={index === 0}
          onClick={() => reorderReference(index, index - 1)}
        >
          <ChevronUp aria-hidden />
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          className="size-5"
          aria-label={`Bajar ${slot.asset.original_name} en el orden`}
          disabled={index === total - 1}
          onClick={() => reorderReference(index, index + 1)}
        >
          <ChevronDown aria-hidden />
        </Button>
      </div>

      <div className="relative size-14 shrink-0 overflow-hidden rounded-xl border border-white/[0.08] bg-ink-900">
        <Thumbnail slot={slot} />
        {tag ? (
          <span className="absolute bottom-0 left-0 right-0 bg-ink-950/85 px-1 py-0.5 text-center font-mono text-[9px] text-accent">
            {tag}
          </span>
        ) : null}
      </div>

      <div className="min-w-0 flex-1 space-y-1.5">
        <div className="flex items-start justify-between gap-1">
          <div className="min-w-0">
            <p className="truncate text-xs font-medium text-fg" title={slot.asset.original_name}>
              {slot.asset.original_name}
            </p>
            <p className="tabular text-[10px] text-faint">
              {formatBytes(slot.asset.size_bytes)}
              {slot.asset.width && slot.asset.height ? ` · ${slot.asset.width}×${slot.asset.height}` : ''}
              {duration !== null ? ` · ${duration.toFixed(2).replace('.', ',')} s` : ''}
              {slot.asset.guide_provenance ? ' · guía preparada' : ''}
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Quitar ${slot.asset.original_name} de la toma`}
            onClick={() => removeReference(slot.uid)}
          >
            <X aria-hidden />
          </Button>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <Select value={slot.role} onValueChange={(role) => setRole(slot.uid, role as RefRole)}>
            <SelectTrigger
              aria-label={`Rol de ${slot.asset.original_name}`}
              className="h-7 w-[8.5rem] text-[11px]"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {roles.map((role) => (
                <SelectItem key={role} value={role} disabled={role === 'aligned_guide' && !alignedGuides} description={ROLE_META[role].hint}>
                  {ROLE_META[role].label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <InfoTip help={ROLE_HELP[slot.role]} label={`Rol ${ROLE_META[slot.role].label}`} />
          {slot.role === 'aligned_guide' ? <p className="text-[10px] leading-snug text-accent">Guía desde el frame 0 · sin token de vídeo · sin sonido. Debe coincidir con tamaño, frames y 24 FPS de la salida.</p> : null}
          {slot.asset.kind === 'video' && slot.role !== 'aligned_guide' ? (
            <Tooltip
              content={
                slot.asset.has_audio === false
                  ? 'Este clip no tiene pista de sonido.'
                  : 'Pasa el sonido del clip a H3 para guiar el ritmo. No copia la voz tal cual.'
              }
            >
              <label className="flex items-center gap-1.5 text-[11px] text-muted">
                <Switch
                  checked={slot.include_audio}
                  disabled={slot.asset.has_audio === false}
                  onCheckedChange={(next) => setIncludeAudio(slot.uid, next)}
                  aria-label={`Usar el sonido de ${slot.asset.original_name}`}
                />
                <Video className="size-3" aria-hidden />
                Sonido
              </label>
            </Tooltip>
          ) : null}
        </div>

        {slot.asset.kind === 'video' && mode === 'ref2va' && alignedGuides ? <PrepareGuide slot={slot} /> : null}

        {warning ? (
          <p className="flex items-start gap-1 text-[10px] leading-snug text-warn">
            <AlertTriangle className="mt-px size-3 shrink-0" aria-hidden />
            {warning}
          </p>
        ) : null}
      </div>
    </li>
  )
}
