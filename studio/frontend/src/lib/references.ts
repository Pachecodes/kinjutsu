/**
 * Reference-slot rules, mirrored from the backend validator and workflow builder.
 *
 * The backend stays authoritative — it revalidates everything — but the composer
 * has to refuse an impossible arrangement *before* the creator wastes a click,
 * and it has to show the same `<Picture i>` numbering the builder will wire up.
 */

import type { AssetOut, Mode, RefKind, RefRole, ReferenceInput } from './types'
import { formatDecimal, localized, t } from '../i18n'

export const MAX_REF_IMAGES = 9
export const MAX_REF_VIDEOS = 3
export const MAX_REF_AUDIOS = 3
export const MAX_REF_TOTAL = 12
export const MAX_REF_VIDEO_SECONDS = 15
export const MIN_REF_VIDEO_SECONDS = 2
export const MAX_REF_AUDIO_SECONDS = 15

/** One reference as the creator arranged it, plus the asset we render from. */
export interface ReferenceSlot {
  /** Stable per-slot key. The same asset may legitimately sit in two slots. */
  uid: string
  asset: AssetOut
  role: RefRole
  include_audio: boolean
}

export interface RoleMeta {
  id: RefRole
  kind: RefKind
  label: string
  hint: string
}

export const ROLE_META: Record<RefRole, RoleMeta> = localized(() => ({
  first_frame: { id: 'first_frame', kind: 'image', label: t('Primer fotograma'), hint: t('La imagen con la que abre la toma.') },
  last_frame: { id: 'last_frame', kind: 'image', label: t('Último fotograma'), hint: t('La imagen con la que cierra la toma.') },
  identity: { id: 'identity', kind: 'image', label: t('Identidad'), hint: t('Retrato canónico: cara, pelo y tono de piel.') },
  subject: { id: 'subject', kind: 'image', label: t('Sujeto'), hint: t('Otra persona, criatura u objeto en cuadro.') },
  scene: { id: 'scene', kind: 'image', label: t('Escena'), hint: t('Lugar, decorado o fondo.') },
  style: { id: 'style', kind: 'image', label: t('Estilo'), hint: t('Paleta, gradación y tratamiento.') },
  prop: { id: 'prop', kind: 'image', label: t('Objeto'), hint: t('Algo que el sujeto usa o lleva.') },
  motion: { id: 'motion', kind: 'video', label: t('Movimiento'), hint: t('Movimiento, ritmo y cámara a transferir (token <Video n>).') },
  aligned_guide: { id: 'aligned_guide', kind: 'video', label: t('Guía alineada'), hint: t('Aligned guide: guía del clip completo desde el frame 0 (sin token <Video n>). Mismo tamaño, frames y 24 FPS que la salida.') },
  scene_video: { id: 'scene_video', kind: 'video', label: t('Clip de escena'), hint: t('Referencia de entorno en movimiento.') },
  voice: { id: 'voice', kind: 'audio', label: t('Voz'), hint: t('Habla que guía la forma de la boca.') },
  ambience: { id: 'ambience', kind: 'audio', label: t('Ambiente'), hint: t('Ambiente, música o efectos.') },
}))

const IMAGE_ROLES: RefRole[] = ['identity', 'subject', 'scene', 'style', 'prop']
const FRAME_ROLES: RefRole[] = ['first_frame', 'last_frame']
const VIDEO_ROLES: RefRole[] = ['motion', 'scene_video']
const AUDIO_ROLES: RefRole[] = ['voice', 'ambience']

export const REFERENCE_MODES: Mode[] = ['ref2va', 'performance']

export function isReferenceMode(mode: Mode): boolean {
  return REFERENCE_MODES.includes(mode)
}

export function isFrameRole(role: RefRole): boolean {
  return FRAME_ROLES.includes(role)
}

/** Roles the creator may pick for `kind` in `mode`. Empty means "not accepted". */
export function rolesFor(mode: Mode, kind: RefKind): RefRole[] {
  if (mode === 'text') return []
  if (mode === 'first_frame') return kind === 'image' ? ['first_frame'] : []
  if (mode === 'first_last') return kind === 'image' ? ['first_frame', 'last_frame'] : []
  if (kind === 'image') return IMAGE_ROLES
  if (kind === 'video') return mode === 'ref2va' ? [...VIDEO_ROLES, 'aligned_guide'] : VIDEO_ROLES
  return AUDIO_ROLES
}

/** Media kinds a mode will take at all. */
export function kindsFor(mode: Mode): RefKind[] {
  if (mode === 'text') return []
  if (mode === 'first_frame' || mode === 'first_last') return ['image']
  return ['image', 'video', 'audio']
}

/** How many slots a mode holds in total — what the `Refs (n/max)` counter shows. */
export function maxReferencesFor(mode: Mode): number {
  if (mode === 'text') return 0
  if (mode === 'first_frame') return 1
  if (mode === 'first_last') return 2
  return MAX_REF_TOTAL
}

export function countByKind(slots: ReferenceSlot[]): Record<RefKind, number> {
  return {
    image: slots.filter((slot) => slot.asset.kind === 'image').length,
    video: slots.filter((slot) => slot.asset.kind === 'video').length,
    audio: slots.filter((slot) => slot.asset.kind === 'audio').length,
  }
}

export interface AcceptResult {
  ok: boolean
  /** Set when `ok` is false: the exact reason, phrased for the creator. */
  reason?: string
  /** The role the new slot should take when accepted. */
  role?: RefRole
}

/**
 * Decide whether one more `kind` reference fits, and which role it lands on.
 * Mirrors `_validate_counts` / `_validate_mode_shape` so the panel never lets
 * the creator build an arrangement the backend will reject outright.
 */
export function canAccept(mode: Mode, slots: ReferenceSlot[], kind: RefKind): AcceptResult {
  if (mode === 'text') {
    return { ok: false, reason: t('Texto a vídeo usa solo el prompt. Cambia de tarea para añadir referencias.') }
  }
  const counts = countByKind(slots)

  if (mode === 'first_frame') {
    if (kind !== 'image') return { ok: false, reason: t('Animar una imagen solo acepta una imagen fija.') }
    if (counts.image >= 1) return { ok: false, reason: t('Animar una imagen lleva exactamente una imagen. Quita la actual para cambiarla.') }
    return { ok: true, role: 'first_frame' }
  }

  if (mode === 'first_last') {
    if (kind !== 'image') return { ok: false, reason: t('Inicio + final solo acepta imágenes fijas.') }
    const hasFirst = slots.some((slot) => slot.role === 'first_frame')
    const hasLast = slots.some((slot) => slot.role === 'last_frame')
    if (hasFirst && hasLast) {
      return { ok: false, reason: t('Inicio + final lleva exactamente dos imágenes.') }
    }
    return { ok: true, role: hasFirst ? 'last_frame' : 'first_frame' }
  }

  if (slots.length >= MAX_REF_TOTAL) {
    return { ok: false, reason: t('H3 acepta como máximo {n} referencias en total.', { n: MAX_REF_TOTAL }) }
  }
  if (kind === 'image') {
    if (counts.image >= MAX_REF_IMAGES) {
      return { ok: false, reason: t('H3 acepta como máximo {n} imágenes de referencia.', { n: MAX_REF_IMAGES }) }
    }
    // The first image anchors identity; everything after it is a plain subject.
    const hasIdentity = slots.some((slot) => slot.role === 'identity')
    return { ok: true, role: hasIdentity ? 'subject' : 'identity' }
  }
  if (kind === 'video') {
    if (counts.video >= MAX_REF_VIDEOS) {
      return { ok: false, reason: t('H3 acepta como máximo {n} vídeos de referencia.', { n: MAX_REF_VIDEOS }) }
    }
    if (mode === 'performance' && slots.some((slot) => slot.role === 'motion')) {
      return { ok: false, reason: t('Performance usa exactamente un clip de movimiento.') }
    }
    return { ok: true, role: 'motion' }
  }
  if (counts.audio >= MAX_REF_AUDIOS) {
    return { ok: false, reason: t('H3 acepta como máximo {n} audios de referencia.', { n: MAX_REF_AUDIOS }) }
  }
  return { ok: true, role: 'voice' }
}

/**
 * Re-home the current references onto a new mode instead of silently dropping
 * everything. Returns the surviving slots and what had to go, so the UI can say
 * so out loud.
 */
export function migrateReferences(
  mode: Mode,
  slots: ReferenceSlot[],
): { slots: ReferenceSlot[]; dropped: ReferenceSlot[] } {
  if (mode === 'text') return { slots: [], dropped: slots }

  const kept: ReferenceSlot[] = []
  const dropped: ReferenceSlot[] = []

  for (const slot of slots) {
    const decision = canAccept(mode, kept, slot.asset.kind)
    if (!decision.ok || !decision.role) {
      dropped.push(slot)
      continue
    }
    const allowed = rolesFor(mode, slot.asset.kind)
    const role = allowed.includes(slot.role) ? slot.role : decision.role
    kept.push({ ...slot, role, include_audio: slot.asset.kind === 'video' ? slot.include_audio : false })
  }

  return { slots: kept, dropped }
}

/**
 * The `<Picture i>` / `<Video k>` / `<Audio j>` tag for each slot, numbered per
 * kind in creator order — exactly how `builder._resolve` wires the graph.
 * Frame-driven modes have no tags; the frames are wired positionally.
 */
export function referenceTags(mode: Mode, slots: ReferenceSlot[]): (string | null)[] {
  if (!isReferenceMode(mode)) return slots.map(() => null)
  const seen: Record<RefKind, number> = { image: 0, video: 0, audio: 0 }
  const word: Record<RefKind, string> = { image: 'Picture', video: 'Video', audio: 'Audio' }
  return slots.map((slot) => {
    if (slot.role === 'aligned_guide') return null
    const kind = slot.asset.kind
    seen[kind] += 1
    return `<${word[kind]} ${seen[kind]}>`
  })
}

/** Tags that belong in the prompt but are not there yet. */
export function missingTags(mode: Mode, slots: ReferenceSlot[], prompt: string): string[] {
  return referenceTags(mode, slots).filter((tag): tag is string => tag !== null && !prompt.includes(tag))
}

/** Append the tags the prompt is missing, keeping what the creator wrote. */
export function withTagsAppended(prompt: string, tags: string[]): string {
  if (tags.length === 0) return prompt
  const base = prompt.trimEnd()
  return base ? `${base} ${tags.join(' ')}` : tags.join(' ')
}

export function toReferenceInputs(slots: ReferenceSlot[]): ReferenceInput[] {
  return slots.map((slot) => ({
    asset_id: slot.asset.id,
    kind: slot.asset.kind,
    role: slot.role,
    include_audio: slot.asset.kind === 'video' ? slot.include_audio : false,
  }))
}

export function move<T>(items: T[], from: number, to: number): T[] {
  if (from === to || from < 0 || to < 0 || from >= items.length || to >= items.length) return items
  const next = items.slice()
  const [item] = next.splice(from, 1)
  next.splice(to, 0, item)
  return next
}

/** Client-side pre-check so an obviously-too-long clip never gets uploaded twice. */
export function durationWarning(slot: ReferenceSlot): string | null {
  const duration = slot.asset.duration_seconds
  if (duration === null) return null
  if (slot.asset.kind === 'video') {
    if (duration > MAX_REF_VIDEO_SECONDS) {
      return t('{d} s supera el límite de {max} s para vídeo de referencia.', { d: formatDecimal(duration, 2), max: MAX_REF_VIDEO_SECONDS })
    }
    if (duration < MIN_REF_VIDEO_SECONDS) {
      return t('{d} s es más corto de lo que H3 espera ({min}–{max} s).', { d: formatDecimal(duration, 2), min: MIN_REF_VIDEO_SECONDS, max: MAX_REF_VIDEO_SECONDS })
    }
  }
  if (slot.asset.kind === 'audio' && duration > MAX_REF_AUDIO_SECONDS) {
    return t('{d} s supera el límite de {max} s para audio de referencia.', { d: formatDecimal(duration, 2), max: MAX_REF_AUDIO_SECONDS })
  }
  return null
}
