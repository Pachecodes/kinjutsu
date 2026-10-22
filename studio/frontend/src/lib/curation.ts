/**
 * Presentation-only curation: which recipes the front page leads with, how
 * tasks and render stages read for a creator, and which recipes are Character
 * Swap. Nothing here changes a recipe's parameters — those stay owned by the
 * backend presets, and every value remains editable in Advanced.
 */

import type { JobOut, MethodId, Mode, Preset } from './types'

export type PresetTier = 'recommended' | 'standard' | 'experimental'

/**
 * Tested recipes, in the order the rail shows them. The approved Character Swap
 * leads. Used only when the backend does not send its own `tier`.
 */
const RECOMMENDED = [
  'character-swap-hd-turbo8',
  'fast-preview-5s',
  'fast-final-trt-5s',
  'lightx2v8-creator-5s',
  'premium-vertical-5s',
]

/** Everyday recipes that are not experiments but have no dedicated benchmark. */
const STANDARD = ['balanced-10s', 'final-15s', 'identity-locked', 'lip-sync', 'performance-transfer']

/** Recipes that render through an aligned full-clip guide (the approved swap route). */
export const GUIDE_SWAP_PRESETS = ['character-swap-hd-turbo8', 'character-swap-v11']
export const SWAP_PRESETS = [...GUIDE_SWAP_PRESETS, 'character-swap-playground']
export const APPROVED_SWAP_PRESET = 'character-swap-hd-turbo8'

export function isSwapPreset(id: string | null | undefined): boolean {
  return Boolean(id && SWAP_PRESETS.includes(id))
}

export function isGuideSwapPreset(id: string | null | undefined): boolean {
  return Boolean(id && GUIDE_SWAP_PRESETS.includes(id))
}

/**
 * Anything the Studio does not explicitly know is treated as experimental: a new
 * backend recipe never lands on the front page until it is curated.
 */
export function presetTier(preset: Preset): PresetTier {
  if (preset.tier === 'recommended' || preset.tier === 'standard' || preset.tier === 'experimental') {
    return preset.tier
  }
  if (preset.tier === 'legacy') return 'experimental'
  // Kinjutsu curation. `recommended` is a front-page choice, not a claim that models are installed.
  if (preset.group === 'recommended') return 'recommended'
  if (preset.group === 'control') return 'standard'
  if (preset.group === 'experimental') return 'experimental'
  if (RECOMMENDED.includes(preset.id)) return 'recommended'
  if (STANDARD.includes(preset.id)) return 'standard'
  return 'experimental'
}

export interface CuratedPresets {
  recommended: Preset[]
  standard: Preset[]
  experimental: Preset[]
}

export function curatePresets(presets: Preset[]): CuratedPresets {
  const order = (preset: Preset) => {
    // The backend's single default (the approved swap) always leads.
    if (preset.default) return -1
    const index = [...RECOMMENDED, ...STANDARD].indexOf(preset.id)
    return index === -1 ? Number.MAX_SAFE_INTEGER : index
  }
  const sorted = [...presets].sort((a, b) => order(a) - order(b))
  return {
    recommended: sorted.filter((preset) => presetTier(preset) === 'recommended'),
    standard: sorted.filter((preset) => presetTier(preset) === 'standard'),
    experimental: sorted.filter((preset) => presetTier(preset) === 'experimental'),
  }
}

/** True when applying `preset` would overwrite a prompt the creator wrote. */
export function presetReplacesPrompt(preset: Preset, currentPrompt: string): boolean {
  const next = preset.patch.prompt
  if (typeof next !== 'string') return false
  const current = currentPrompt.trim()
  return current.length > 0 && current !== next.trim()
}

export interface ModeCopy {
  label: string
  short: string
  blurb: string
}

/** Task names in creator language. Mode ids are the stable API enum. */
export const MODE_COPY: Record<Mode, ModeCopy> = {
  text: { label: 'Texto a vídeo', short: 'Texto', blurb: 'Solo prompt. H3 escribe imagen y sonido.' },
  first_frame: {
    label: 'Animar una imagen',
    short: 'Imagen',
    blurb: 'Parte de una imagen fija y deja que la escena se mueva.',
  },
  first_last: {
    label: 'Inicio + final',
    short: 'Inicio+fin',
    blurb: 'Fija la primera y la última imagen; H3 rellena el medio.',
  },
  ref2va: {
    label: 'Referencias',
    short: 'Refs',
    blurb: 'Hasta 9 imágenes, 3 clips y 3 audios como anclas de identidad y estilo.',
  },
  performance: {
    label: 'Performance',
    short: 'Performance',
    blurb: 'Una identidad, un clip de movimiento y voz opcional.',
  },
}

export type RenderPhase = 'queued' | 'load' | 'refs' | 'prepare' | 'render' | 'decode' | 'save'

export const PHASES: { id: RenderPhase; label: string }[] = [
  { id: 'queued', label: 'En cola' },
  { id: 'load', label: 'Cargando modelos' },
  { id: 'refs', label: 'Leyendo referencias' },
  { id: 'prepare', label: 'Preparando' },
  { id: 'render', label: 'Renderizando' },
  { id: 'decode', label: 'Decodificando' },
  { id: 'save', label: 'Guardando' },
]

/** Backend stage labels (`STAGE_LABELS` in jobs.py) → phase + creator wording. */
const STAGES: Record<string, { phase: RenderPhase; label: string }> = {
  'Loading H3 weights': { phase: 'load', label: 'Cargando pesos de H3' },
  'Loading text encoder': { phase: 'load', label: 'Cargando codificador de texto' },
  'Applying LoRAs': { phase: 'load', label: 'Aplicando LoRAs' },
  'Loading VAE': { phase: 'load', label: 'Cargando VAE' },
  'Reading references': { phase: 'refs', label: 'Leyendo referencias' },
  'Unpacking motion clip': { phase: 'refs', label: 'Desempaquetando el clip' },
  'Understanding the prompt': { phase: 'prepare', label: 'Interpretando el prompt' },
  'Understanding references': { phase: 'prepare', label: 'Preparando referencias' },
  'Preparing fast preview': { phase: 'prepare', label: 'Preparando caché' },
  'Patching attention': { phase: 'prepare', label: 'Ajustando atención' },
  'Building the schedule': { phase: 'prepare', label: 'Preparando el muestreo' },
  Rendering: { phase: 'render', label: 'Renderizando' },
  'Decoding video': { phase: 'decode', label: 'Decodificando vídeo' },
  'Decoding audio': { phase: 'decode', label: 'Decodificando audio' },
  'Muxing video and sound': { phase: 'save', label: 'Uniendo vídeo y sonido' },
  'Saving take': { phase: 'save', label: 'Guardando la toma' },
}

export interface StageInfo {
  phase: RenderPhase
  label: string
  /** The raw backend stage, shown when the Studio does not recognise it. */
  raw: string | null
}

export function describeStage(job: Pick<JobOut, 'status' | 'stage'>): StageInfo {
  if (job.status === 'queued') return { phase: 'queued', label: 'En cola', raw: job.stage }
  const known = job.stage ? STAGES[job.stage] : undefined
  if (known) return { ...known, raw: job.stage }
  return { phase: 'render', label: job.stage ?? 'Renderizando', raw: job.stage }
}

export const STATUS_LABEL: Record<JobOut['status'], string> = {
  queued: 'En cola',
  running: 'Generando',
  completed: 'Lista',
  failed: 'Falló',
  canceled: 'Cancelada',
}

/** What the backend actually did on cancel, read from the take's own events. */
export type CancelOutcome = 'dequeued' | 'interrupt_requested' | 'not_running' | 'before_submit' | 'unknown'

export function cancelOutcome(messages: string[]): CancelOutcome {
  for (const message of [...messages].reverse()) {
    if (message.startsWith('Removed from the ComfyUI queue')) return 'dequeued'
    if (message.startsWith('Interrupted the running render')) return 'interrupt_requested'
    if (message.startsWith('ComfyUI is not running this take')) return 'not_running'
    if (message.startsWith('Canceled before ComfyUI accepted it')) return 'before_submit'
  }
  return 'unknown'
}

export const CANCEL_COPY: Record<CancelOutcome, string> = {
  dequeued: 'Se quitó de la cola de ComfyUI antes de empezar. No se calculó nada.',
  interrupt_requested:
    'Se pidió a ComfyUI que interrumpa el render. Se detiene al terminar el paso en curso; durante la decodificación puede tardar más. La GPU puede seguir ocupada unos segundos.',
  not_running: 'ComfyUI no estaba ejecutando esta toma: se marcó cancelada sin interrumpir nada más.',
  before_submit: 'Se canceló antes de llegar a ComfyUI. No se calculó nada.',
  unknown: 'La toma está marcada como cancelada. El registro de actividad no indica si llegó a calcularse.',
}

const FRAME_ONLY: MethodId[] = ['w4a8_lightx2v', 'w4a8_lightx2v_trt', 'w4a8_latent2x_refine3']

/** Why a method cannot run in this task, or null when it can. */
export function methodModeBlock(id: MethodId, mode: Mode): string | null {
  if (FRAME_ONLY.includes(id) && (mode === 'ref2va' || mode === 'performance')) {
    return 'Solo para Texto, Animar una imagen e Inicio + final.'
  }
  if (id === 'ref2va_vsa' && mode !== 'ref2va') return 'Solo en la tarea Referencias.'
  return null
}
