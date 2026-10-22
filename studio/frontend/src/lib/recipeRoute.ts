/**
 * The recommended routes as data: which named slots a task shows, and which
 * steps the approved Character Swap still needs. Pure; no React.
 */

import { isGuideSwapPreset, isSwapPreset } from './curation'
import { findGuide, guideStatus } from './guideSync'
import { swapPromptReady } from './promptBuilder'
import type { ReferenceSlot } from './references'
import type { Mode, RefKind, RefRole } from './types'

/** A named place the current task expects something in. */
export interface SlotSpec {
  key: string
  kind: RefKind
  roles: RefRole[]
  label: string
  hint: string
  required: boolean
}

/** The slots a creator should see for this task and recipe, in wiring order. */
export function slotsFor(mode: Mode, presetId: string | null): SlotSpec[] {
  if (mode === 'ref2va' && isGuideSwapPreset(presetId)) {
    return [
      { key: 'identity', kind: 'image', roles: ['identity', 'subject'], label: 'Identidad', hint: 'Retrato del personaje · <Picture 1>', required: true },
      { key: 'guide', kind: 'video', roles: ['aligned_guide'], label: 'Vídeo guía', hint: 'Pose, gestos, ropa, escena y cámara', required: true },
    ]
  }
  if (mode === 'ref2va' && isSwapPreset(presetId)) {
    return [
      { key: 'identity', kind: 'image', roles: ['identity', 'subject'], label: 'Identidad', hint: 'Retrato del personaje · <Picture 1>', required: true },
      { key: 'motion', kind: 'video', roles: ['motion'], label: 'Vídeo de movimiento', hint: 'Referencia normal · <Video 1>', required: true },
    ]
  }
  if (mode === 'performance') {
    return [
      { key: 'identity', kind: 'image', roles: ['identity'], label: 'Identidad', hint: 'Retrato canónico', required: true },
      { key: 'motion', kind: 'video', roles: ['motion'], label: 'Movimiento', hint: 'Clip de 2–15 s', required: true },
      { key: 'voice', kind: 'audio', roles: ['voice', 'ambience'], label: 'Voz', hint: 'Opcional · máx. 15 s', required: false },
    ]
  }
  if (mode === 'first_frame') {
    return [{ key: 'first', kind: 'image', roles: ['first_frame'], label: 'Imagen inicial', hint: 'La toma abre aquí', required: true }]
  }
  if (mode === 'first_last') {
    return [
      { key: 'first', kind: 'image', roles: ['first_frame'], label: 'Inicio', hint: 'Primer fotograma', required: true },
      { key: 'last', kind: 'image', roles: ['last_frame'], label: 'Final', hint: 'Último fotograma', required: true },
    ]
  }
  return []
}

export interface ChecklistStep {
  id: 'identity' | 'video' | 'aligned' | 'prompt'
  label: string
  done: boolean
  /** `data-focus` target that resolves the step. */
  focus: string
}

/** Pure: the approved swap route as four checkable steps. */
export function swapChecklist(input: {
  presetId: string | null
  references: ReferenceSlot[]
  prompt: string
  width: number
  height: number
  length: number
}): ChecklistStep[] {
  const guided = isGuideSwapPreset(input.presetId)
  const images = input.references.filter((slot) => slot.asset.kind === 'image')
  const identity = images.length > 0 && (images[0].role === 'identity' || images[0].role === 'subject')
  const video = guided
    ? findGuide(input.references) !== null
    : input.references.some((slot) => slot.asset.kind === 'video' && slot.role === 'motion')
  const steps: ChecklistStep[] = [
    { id: 'identity', label: 'Retrato de identidad', done: identity, focus: 'slot-identity' },
    { id: 'video', label: guided ? 'Vídeo guía' : 'Vídeo de movimiento', done: video, focus: guided ? 'slot-guide' : 'slot-motion' },
  ]
  if (guided) {
    const status = guideStatus(input, findGuide(input.references))
    steps.push({ id: 'aligned', label: 'Guía alineada a la salida', done: Boolean(status?.ok), focus: 'guide-sync' })
  }
  steps.push({ id: 'prompt', label: 'Prompt body_swap con <Picture 1>', done: swapPromptReady(input.prompt), focus: 'prompt' })
  return steps
}

