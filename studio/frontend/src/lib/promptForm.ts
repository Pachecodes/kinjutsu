/**
 * Bridge between the composer and the Kinjutsu deterministic prompt form
 * (`POST /api/prompting/build`). Pure; no React, no network.
 *
 * Roles and tokens always come from the attachments the creator actually has,
 * in their real order, numbered the way the workflow builder numbers them. The
 * form never infers anything from file names and never touches the recipe.
 */

import { isGuideSwapPreset, isSwapPreset } from './curation'
import { FPS } from './frames'
import { referenceTags, type ReferenceSlot } from './references'
import type { FormAsset, FormAssetRole, FormDialogue, FormShot, Mode, PromptForm, PromptTemplateId } from './types'
import { localized, t } from '../i18n'

export const TEMPLATE_LABEL: Record<PromptTemplateId, string> = localized(() => ({
  'character-swap-aligned': t('Character Swap · guía alineada'),
  'motion-ref2va': t('Referencias · Motion (experimental)'),
  t2va: t('Texto a vídeo'),
  i2va: t('Animar una imagen'),
  fl2va: 'Inicio + final',
  l2va: t('Solo imagen final'),
}))

/** Effective duration of the output, rounded to milliseconds for the prompt text. */
export function effectiveSeconds(length: number): number {
  return Math.round((length / FPS) * 1000) / 1000
}

/** The template the current task/recipe naturally maps to. */
export function suggestedTemplate(mode: Mode, presetId: string | null): PromptTemplateId {
  if (mode === 'ref2va' && isGuideSwapPreset(presetId)) return 'character-swap-aligned'
  if (mode === 'ref2va' && isSwapPreset(presetId)) return 'motion-ref2va'
  if (mode === 'first_frame') return 'i2va'
  if (mode === 'first_last') return 'fl2va'
  if (mode === 'ref2va' || mode === 'performance') return 'motion-ref2va'
  return 't2va'
}

const IMAGE_ROLE: Partial<Record<ReferenceSlot['role'], FormAssetRole>> = {
  identity: 'identity',
  scene: 'scene',
  style: 'style',
  first_frame: 'first_frame',
  last_frame: 'last_frame',
}

export interface MappedAsset {
  uid: string
  kind: FormAsset['kind']
  role: FormAssetRole
  token?: string
  /** What the creator sees next to the description field. */
  label: string
}

export interface AssetMapping {
  assets: MappedAsset[]
  /** Attachments the form cannot express, with the reason. Never silently dropped. */
  unsupported: string[]
}

/** Current attachments → form assets, in attachment order. */
export function mapAttachments(mode: Mode, slots: ReferenceSlot[]): AssetMapping {
  const tags = referenceTags(mode, slots)
  const assets: MappedAsset[] = []
  const unsupported: string[] = []
  // Frame-driven modes have no tags in the composer; the form numbers images itself.
  let pictures = 0
  slots.forEach((slot, index) => {
    const name = slot.asset.original_name
    if (slot.role === 'aligned_guide') {
      assets.push({ uid: slot.uid, kind: 'aligned_guide', role: 'aligned_guide', label: t('Guía alineada (sin token)') })
      return
    }
    if (slot.asset.kind === 'image') {
      pictures += 1
      const role = IMAGE_ROLE[slot.role]
      if (!role) {
        unsupported.push(t('{name}: el rol «{role}» no existe en el formulario (usa identidad, escena o estilo).', { name, role: slot.role }))
        return
      }
      const token = tags[index] ?? `<Picture ${pictures}>`
      assets.push({ uid: slot.uid, kind: 'image', role, token, label: `${token} · ${role}` })
      return
    }
    if (slot.asset.kind === 'video' && slot.role === 'motion') {
      const token = tags[index] ?? '<Video 1>'
      assets.push({ uid: slot.uid, kind: 'video', role: 'motion', token, label: `${token} · motion` })
      return
    }
    unsupported.push(
      slot.asset.kind === 'audio'
        ? `${name}: el formulario v1 no admite audio de referencia.`
        : t('{name}: solo se admite vídeo de movimiento (motion) o guía alineada.', { name }),
    )
  })
  return { assets, unsupported }
}

/** Mirrors the renderer's per-template role rules so the UI can explain before a round trip. */
export function templateProblem(template: PromptTemplateId, mapping: AssetMapping): string | null {
  if (mapping.unsupported.length > 0) return mapping.unsupported[0]
  const pairs = mapping.assets.map((asset) => `${asset.kind}:${asset.role}`)
  const same = (expected: string[]) => pairs.length === expected.length && pairs.every((pair, i) => pair === expected[i])
  switch (template) {
    case 'character-swap-aligned':
      return same(['image:identity', 'aligned_guide:aligned_guide'])
        ? null
        : t('Necesita exactamente el retrato de identidad (<Picture 1>) seguido de una guía alineada.')
    case 'motion-ref2va': {
      const videos = mapping.assets.filter((asset) => asset.kind === 'video')
      const identities = mapping.assets.filter((asset) => asset.role === 'identity')
      const guide = mapping.assets.some((asset) => asset.kind === 'aligned_guide')
      const badImage = mapping.assets.some(
        (asset) => asset.kind === 'image' && !['identity', 'scene', 'costume', 'style'].includes(asset.role),
      )
      return videos.length === 1 && identities.length === 1 && !guide && !badImage
        ? null
        : t('Necesita una imagen de identidad y exactamente un vídeo de movimiento; sin guía alineada ni audio.')
    }
    case 't2va':
      return pairs.length === 0 ? null : t('Texto a vídeo no lleva referencias.')
    case 'i2va':
      return same(['image:first_frame']) ? null : t('Necesita solo una imagen inicial.')
    case 'fl2va':
      return same(['image:first_frame', 'image:last_frame']) ? null : t('Necesita imagen inicial y final, en ese orden.')
    case 'l2va':
      return same(['image:last_frame']) ? null : t('Necesita solo una imagen final.')
  }
}

export interface FormDraft {
  identity: string
  style: string
  /** Per attachment uid. */
  descriptions: Record<string, string>
  shots: FormShot[]
  soundscape: string
  music: string
  silent: boolean
  dialogue: FormDialogue[]
}

export const EMPTY_SHOT: FormShot = { start_seconds: 0, scene: '', performance: '', camera: '', lighting: '', sound: '' }

export const EMPTY_DRAFT: FormDraft = {
  identity: '',
  style: '',
  descriptions: {},
  shots: [{ ...EMPTY_SHOT }],
  soundscape: '',
  music: 'N/A',
  silent: false,
  dialogue: [],
}

/** The exact request body for `POST /api/prompting/build`. */
export function toPromptForm(
  draft: FormDraft,
  mapping: AssetMapping,
  length: number,
  template: PromptTemplateId,
): PromptForm {
  const silent = draft.silent
  // The approved aligned swap keeps the guide's timing: one shot, no music or speech.
  const aligned = template === 'character-swap-aligned'
  const shots = aligned ? draft.shots.slice(0, 1) : draft.shots
  const dialogue = silent || aligned ? [] : draft.dialogue.map((line) => {
    // Binding speech to <Subject 1> exists only in Motion.
    if (template === 'motion-ref2va' || line.subject === undefined) return line
    const { subject: _subject, ...rest } = line
    return rest
  })
  return {
    duration_seconds: effectiveSeconds(length),
    identity: draft.identity.trim(),
    style: draft.style.trim(),
    assets: mapping.assets.map((asset) => ({
      kind: asset.kind,
      role: asset.role,
      ...(asset.token && asset.kind !== 'aligned_guide' ? { token: asset.token } : {}),
      description: (draft.descriptions[asset.uid] ?? '').trim(),
    })),
    shots: shots.map((shot) => ({
      start_seconds: shot.start_seconds,
      scene: shot.scene.trim(),
      performance: shot.performance.trim(),
      camera: shot.camera.trim(),
      lighting: shot.lighting.trim(),
      sound: silent ? 'N/A' : shot.sound.trim(),
    })),
    audio: {
      soundscape: silent ? 'N/A' : draft.soundscape.trim(),
      music: silent || aligned ? 'N/A' : draft.music.trim() || 'N/A',
      silent,
    },
    dialogue,
  }
}

/** A stable fingerprint of what a preview was built from, so Apply can refuse a stale one. */
export function previewKey(template: PromptTemplateId, form: PromptForm): string {
  return JSON.stringify([template, form])
}
