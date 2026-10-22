/**
 * How the pinned model catalog reads for a creator. The backend sends only
 * manifest targets; names and purposes here are presentation, keyed by the
 * exact target. An unknown target still shows, by its file name.
 */

import type { DownloadStatus, ManagedModel, ModelDownload } from './types'
import { formatDecimal, localized, t } from '../i18n'

export type ModelCategory = 'diffusion_models' | 'text_encoders' | 'vae' | 'loras' | 'other'

export const CATEGORY_LABEL: Record<ModelCategory, string> = localized(() => ({
  diffusion_models: t('Modelo base'),
  text_encoders: t('Codificador de prompt'),
  vae: 'VAE',
  loras: 'LoRA',
  other: t('Otro'),
}))

interface KnownModel {
  label: string
  purpose: string
}

const KNOWN: Record<string, KnownModel> = localized(() => ({
  'diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors': {
    label: 'H3 Ref2VA INT8',
    purpose: t('El generador de vídeo para referencias y Character Swap.'),
  },
  'text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors': {
    label: 'Qwen3-VL Standard',
    purpose: t('Convierte el prompt en condicionamiento. No genera vídeo.'),
  },
  'vae/minimax_h3_video_vae_fp16.safetensors': {
    label: t('VAE de vídeo'),
    purpose: t('Decodifica los latentes en fotogramas.'),
  },
  'vae/minimax_h3_audio_vae_fp32.safetensors': {
    label: t('VAE de audio'),
    purpose: t('Decodifica el sonido que escribe H3.'),
  },
  'loras/latest_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors': {
    label: 'Turbo8 Ref2VA',
    purpose: t('LoRA de 8 pasos de la receta Character Swap aprobada.'),
  },
  'loras/minimax_h3_character_swap_v1.1_ref2va_fro.safetensors': {
    label: 'BFS Character Swap v1.1',
    purpose: t('LoRA que cambia la identidad con la guía alineada.'),
  },
}))

export function modelCategory(target: string): ModelCategory {
  const head = target.split('/')[0]
  return head === 'diffusion_models' || head === 'text_encoders' || head === 'vae' || head === 'loras' ? head : 'other'
}

export function modelFileName(target: string): string {
  return target.split('/').pop() ?? target
}

export function describeModel(
  model: Pick<ManagedModel, 'target'> & Partial<Pick<ManagedModel, 'label'>>,
): KnownModel & { category: ModelCategory; file: string } {
  const known = KNOWN[model.target]
  return {
    // The backend's own label wins when it sends one.
    label: model.label || known?.label || modelFileName(model.target),
    purpose: known?.purpose ?? t('Archivo fijado en el manifiesto del paquete.'),
    category: modelCategory(model.target),
    file: modelFileName(model.target),
  }
}

/** What the card should say, merging the (slow) catalog with the (live) job list. */
export type ModelState =
  | 'verified'
  | 'reused'
  | 'missing'
  | 'queued'
  | 'downloading'
  | 'verifying'
  | 'cancelling'
  | 'cancelled'
  | 'error'
  | 'installed_now'

const ACTIVE: DownloadStatus[] = ['queued', 'downloading', 'verifying']

export function isActiveDownload(job: ModelDownload | undefined): boolean {
  return Boolean(job && ACTIVE.includes(job.status))
}

export function modelState(model: ManagedModel, job: ModelDownload | undefined, cancelRequested: boolean): ModelState {
  if (job) {
    if (job.status === 'queued' || job.status === 'downloading' || job.status === 'verifying') {
      return cancelRequested ? 'cancelling' : job.status
    }
    if (job.status === 'installed') return job.reused ? 'reused' : 'installed_now'
    if (job.status === 'cancelled') return 'cancelled'
    if (job.status === 'error') return 'error'
  }
  if (model.verified) return model.reused ? 'reused' : 'verified'
  return 'missing'
}

export const STATE_LABEL: Record<ModelState, string> = localized(() => ({
  verified: t('Instalado y verificado'),
  reused: t('Reutilizado (verificado)'),
  missing: t('Falta'),
  queued: t('En cola'),
  downloading: t('Descargando'),
  verifying: t('Verificando SHA256'),
  cancelling: t('Cancelación solicitada'),
  cancelled: t('Cancelado · parcial conservado'),
  error: 'Error',
  installed_now: t('Instalado · reinicia Comfy'),
}))

export function formatGiB(bytes: number): string {
  const gib = bytes / 1024 ** 3
  if (gib >= 1) return `${formatDecimal(gib, gib >= 10 ? 1 : 2)} GB`
  return `${Math.round(bytes / 1024 ** 2)} MB`
}

/** Bytes still to fetch for the models that are missing. */
export function missingBytes(models: ManagedModel[]): number {
  return models.filter((model) => !model.verified).reduce((sum, model) => sum + model.size, 0)
}

const GIB = 1024 ** 3

/**
 * Whether the disk can take the rest of this file plus the backend's 1 GiB
 * margin. Null when the backend did not report free space.
 */
export function fitsOnDisk(model: ManagedModel, freeBytes: number | undefined): boolean | null {
  if (freeBytes === undefined) return null
  const remaining = Math.max(0, model.size - (model.partial_valid_size === false ? 0 : (model.partial_bytes ?? 0)))
  return freeBytes >= remaining + GIB
}

/** A resumable partial left on disk, or a bad one that must be inspected. */
export function partialInfo(model: ManagedModel): { bytes: number; valid: boolean } | null {
  const bytes = model.partial_bytes ?? 0
  if (model.verified || bytes <= 0) return null
  return { bytes, valid: model.partial_valid_size !== false }
}

export function licenseName(path: string): string {
  return path.split('/').pop() ?? path
}
