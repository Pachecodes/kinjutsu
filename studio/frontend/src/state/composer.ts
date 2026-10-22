/**
 * The composer store.
 *
 * One take-in-progress, held in memory. It enforces the reference limits and
 * mode shapes locally so the UI can explain itself instantly, and produces the
 * exact `GenerationRequest` the backend validates and builds from.
 */

import { create } from 'zustand'

import {
  canAccept,
  migrateReferences,
  move,
  type ReferenceSlot,
  rolesFor,
  toReferenceInputs,
} from '../lib/references'
import { snapDimension, snapLength } from '../lib/frames'
import type {
  AssetOut,
  ContinuityOptions,
  EasyCacheOptions,
  EncoderVariant,
  GenerationRequest,
  LoraInput,
  MethodId,
  Mode,
  Preset,
  RefImageSize,
  RefRole,
  SolOptions,
  WeightVariant,
} from '../lib/types'
import { t } from '../i18n'

export const EASYCACHE_DEFAULTS: EasyCacheOptions = {
  reuse_threshold: 0.3,
  start_percent: 0.2,
  end_percent: 0.9,
  verbose: false,
}

export const SOL_DEFAULTS: SolOptions = {
  tau: 1.3,
  start_percent: 0.2,
  end_percent: 0.9,
  min_tokens: 4096,
  int8_qk: true,
  sink_conditioning: 'exact_kv_and_rows',
  morton: false,
  morton_curve: '2d_frame',
  verbose: false,
  use_tma: false,
}

export interface ComposerState {
  mode: Mode
  prompt: string
  title: string
  width: number
  height: number
  length: number
  steps: number
  seed: number | null
  sampler_name: string
  scheduler: string
  custom_sigmas: number[] | null
  method: MethodId
  easycache: EasyCacheOptions
  sol: SolOptions
  continuity: ContinuityOptions
  weights: WeightVariant
  encoder: EncoderVariant
  lora_chain: LoraInput[]
  ref_image_size: RefImageSize
  auto_ratio: boolean
  references: ReferenceSlot[]
  presetId: string | null
  /** Last thing the composer refused to do, surfaced once then cleared. */
  notice: string | null
}

export interface ComposerActions {
  setMode: (mode: Mode) => void
  setPrompt: (prompt: string) => void
  setTitle: (title: string) => void
  setFrameSize: (width: number, height: number) => void
  setLength: (length: number) => void
  setSteps: (steps: number) => void
  setSeed: (seed: number | null) => void
  randomizeSeed: () => void
  setSampler: (sampler: string) => void
  setScheduler: (scheduler: string) => void
  setMethod: (method: MethodId) => void
  setEasyCache: (patch: Partial<EasyCacheOptions>) => void
  setSol: (patch: Partial<SolOptions>) => void
  setContinuity: (patch: Partial<ContinuityOptions>) => void
  setWeights: (weights: WeightVariant) => void
  setEncoder: (encoder: EncoderVariant) => void
  addLora: (name: string, strength: number) => void
  setLoraStrength: (index: number, strength: number) => void
  removeLora: (index: number) => void
  moveLora: (from: number, to: number) => void
  setRefImageSize: (size: RefImageSize) => void
  setAutoRatio: (enabled: boolean) => void
  addAsset: (asset: AssetOut) => boolean
  removeReference: (uid: string) => void
  setRole: (uid: string, role: RefRole) => void
  setIncludeAudio: (uid: string, include: boolean) => void
  reorderReference: (from: number, to: number) => void
  clearReferences: () => void
  applyPreset: (preset: Preset) => void
  clearPreset: () => void
  loadRequest: (request: GenerationRequest, assets: Map<string, AssetOut>) => { missing: number }
  setNotice: (notice: string | null) => void
  reset: () => void
}

export type ComposerStore = ComposerState & ComposerActions

export const INITIAL_COMPOSER: ComposerState = {
  mode: 'text',
  prompt: '',
  title: '',
  width: 1024,
  height: 576,
  length: 124,
  steps: 20,
  seed: null,
  sampler_name: 'res_multistep',
  scheduler: 'beta',
  custom_sigmas: null,
  method: 'baseline',
  easycache: { ...EASYCACHE_DEFAULTS },
  sol: { ...SOL_DEFAULTS },
  continuity: { auto_split: true, window: 'auto', pin_frames: '22' },
  weights: 'int8',
  encoder: 'standard',
  lora_chain: [],
  ref_image_size: 'match',
  auto_ratio: true,
  references: [],
  presetId: null,
  notice: null,
}

let slotCounter = 0
function nextUid(): string {
  slotCounter += 1
  return `slot-${slotCounter}-${Math.random().toString(36).slice(2, 8)}`
}

/** JS bit ops are 32-bit; build a 53-bit seed the backend's u64 range accepts. */
export function randomSeed(): number {
  return Math.floor(Math.random() * Number.MAX_SAFE_INTEGER)
}

export const createComposerState = (): ComposerState => ({
  ...INITIAL_COMPOSER,
  easycache: { ...EASYCACHE_DEFAULTS },
  sol: { ...SOL_DEFAULTS },
  continuity: { auto_split: true, window: 'auto', pin_frames: '22' },
  lora_chain: [],
  references: [],
})

const OMNI = 'fast_h3_omni_8step'
const OMNI_PRESET = 'fasth3-omni-scenes'

/** Shared core for selection, preset application, reuse and serialization. */
function omniCore() {
  return {
    mode: 'ref2va' as const, steps: 8, sampler_name: 'euler', scheduler: 'simple', custom_sigmas: null,
    weights: 'int8' as const, encoder: 'standard' as const, lora_chain: [],
    continuity: { auto_split: false, window: 'auto' as const, pin_frames: '22' as const },
  }
}

function omniReferences(references: ReferenceSlot[]): ReferenceSlot[] {
  return migrateReferences('ref2va', references.filter((slot) => slot.role !== 'aligned_guide')).slots
}

/** Only automatic Omni sizing is capped; manual canvases stay explicit. */
function omniAspectCanvas(width: number, height: number, ratio: number) {
  const idealWidth = Math.sqrt(width * height * ratio)
  const idealHeight = Math.sqrt(width * height / ratio)
  const atScale = (scale: number) => ({
    width: snapDimension(idealWidth * scale),
    height: snapDimension(idealHeight * scale),
  })
  let canvas = atScale(1)
  if (canvas.width * canvas.height <= 832 * 480) return canvas

  // Uniformly shrink before rounding: retain the reference aspect rather than
  // shaving only one axis. Snapping remains monotonic, including min/max caps.
  let low = 0
  let high = 1
  canvas = atScale(low)
  for (let i = 0; i < 32; i += 1) {
    const scale = (low + high) / 2
    const candidate = atScale(scale)
    if (candidate.width * candidate.height <= 832 * 480) {
      low = scale
      canvas = candidate
    } else {
      high = scale
    }
  }
  return canvas
}

function sceneCanvas(width: number, height: number, references: ReferenceSlot[]) {
  const image = references.find((slot) => slot.asset.kind === 'image')?.asset
  if (!image?.width || !image?.height) return { width, height }
  return omniAspectCanvas(width, height, image.width / image.height)
}

export const useComposer = create<ComposerStore>((set, get) => ({
  // Omni always remains a separate scene lane, never a swap adapter.
  ...createComposerState(),

  setMode: (mode) =>
    set((state) => {
      if (state.mode === mode) return state
      const { slots, dropped } = migrateReferences(mode, state.references)
      const changesCheckpointFamily =
        (state.mode === 'ref2va' || state.mode === 'performance') !==
        (mode === 'ref2va' || mode === 'performance')
      const removedLoras = changesCheckpointFamily ? state.lora_chain.length : 0
      return {
        mode,
        ...(state.method === OMNI && mode !== 'ref2va' ? { presetId: null } : {}),
        references: slots,
        method:
          state.method === OMNI && mode !== 'ref2va' ? 'baseline' :
          (mode === 'ref2va' || mode === 'performance') &&
          (state.method === 'w4a8_lightx2v' ||
            state.method === 'w4a8_lightx2v_trt' ||
            state.method === 'w4a8_latent2x_refine3')
            ? 'baseline'
            : mode !== 'ref2va' && state.method === 'ref2va_vsa'
              ? 'baseline'
            : state.method,
        lora_chain: changesCheckpointFamily ? [] : state.lora_chain,
        // GGUF and ErosMax are Ref2VA-only; Pink Cherry v0.3 is FL2VA-only.
        weights:
          mode === 'ref2va' || mode === 'performance'
            ? state.weights === 'pinkcherry_v03' ? 'int8' : state.weights
            : state.weights === 'gguf_q3km' || state.weights === 'erosmax_beta4' ? 'int8' : state.weights,
        notice: [
          dropped.length > 0
            ? (dropped.length === 1 ? t('Se quitó 1 referencia: esta tarea no la admite.') : t('Se quitaron {n} referencias: esta tarea no las admite.', { n: dropped.length }))
            : null,
          removedLoras > 0
            ? (removedLoras === 1 ? t('Se quitó 1 LoRA: cambió la familia del checkpoint.') : t('Se quitaron {n} LoRAs: cambió la familia del checkpoint.', { n: removedLoras }))
            : null,
        ].filter(Boolean).join(' ') || null,
      }
    }),

  setPrompt: (prompt) => set({ prompt }),
  setTitle: (title) => set({ title }),

  setFrameSize: (width, height) => set({ width: snapDimension(width), height: snapDimension(height) }),
  setLength: (length) => set({ length: snapLength(length) }),
  setSteps: (steps) => set({ steps: get().method === OMNI ? 8 : Math.max(1, Math.min(100, Math.round(steps))) }),

  setSeed: (seed) => set({ seed }),
  randomizeSeed: () => set({ seed: randomSeed() }),

  setSampler: (sampler_name) => set({ sampler_name: get().method === OMNI ? 'euler' : sampler_name }),
  setScheduler: (scheduler) => set({ scheduler: get().method === OMNI ? 'simple' : scheduler }),
  setMethod: (method) =>
    set((state) => ({
      ...(state.method === OMNI || method === OMNI ? { presetId: null } : {}),
      ...(method === OMNI
        ? {
            ...omniCore(), method, seed: 0, length: 124, ref_image_size: 'max' as const, auto_ratio: true,
            ...sceneCanvas(512, 640, state.references),
            references: omniReferences(state.references),
            prompt: state.prompt.trimStart().startsWith('body_swap:') ? '' : state.prompt,
            notice: t('Escenas Omni: sin LoRAs ni guía alineada. Se retiraron ajustes incompatibles; revisa referencias y prompt.'),
          }
        : method === 'ref2va_vsa'
        ? {
            method,
            steps: 4,
            sampler_name: 'euler',
            scheduler: 'simple',
          }
        : method === 'w4a8_lightx2v' || method === 'w4a8_lightx2v_trt' || method === 'w4a8_latent2x_refine3'
        ? {
            method,
            steps: 4,
            sampler_name: method === 'w4a8_lightx2v_trt' ? 'res_multistep' : 'er_sde',
            scheduler: 'simple',
            weights: 'int8',
            ...(method === 'w4a8_latent2x_refine3' ? { length: 124 } : {}),
          }
        : { method }),
    })),

  setEasyCache: (patch) => set((state) => ({ easycache: { ...state.easycache, ...patch } })),
  setSol: (patch) => set((state) => ({ sol: { ...state.sol, ...patch } })),
  setContinuity: (patch) => set((state) => ({ continuity: { ...state.continuity, ...patch, ...(state.method === OMNI ? { auto_split: false } : {}) } })),

  setWeights: (weights) => set({ weights: get().method === OMNI ? 'int8' : weights }),
  setEncoder: (encoder) => set({ encoder: get().method === OMNI ? 'standard' : encoder }),
  addLora: (name, strength) =>
    set((state) =>
      state.method === OMNI || state.lora_chain.length >= 8 || state.lora_chain.some((lora) => lora.name === name)
        ? state
        : { lora_chain: [...state.lora_chain, { name, strength }] },
    ),
  setLoraStrength: (index, strength) =>
    set((state) => ({
      lora_chain: state.lora_chain.map((lora, current) =>
        current === index ? { ...lora, strength: Math.max(-10, Math.min(10, strength)) } : lora,
      ),
    })),
  removeLora: (index) =>
    set((state) => ({ lora_chain: state.lora_chain.filter((_, current) => current !== index) })),
  // LoRAs apply in chain order, so the order is a real creative control.
  moveLora: (from, to) => set((state) => ({ lora_chain: move(state.lora_chain, from, to) })),
  setRefImageSize: (ref_image_size) => set({ ref_image_size }),
  setAutoRatio: (auto_ratio) => set({ auto_ratio }),

  addAsset: (asset) => {
    const state = get()
    const decision = canAccept(state.mode, state.references, asset.kind)
    if (!decision.ok || !decision.role) {
      set({ notice: decision.reason ?? t('Esa referencia no encaja en esta tarea.') })
      return false
    }
    const shouldMatchRatio =
      state.auto_ratio &&
      asset.kind === 'image' &&
      asset.width !== null &&
      asset.height !== null &&
      asset.width > 0 &&
      asset.height > 0 &&
      !state.references.some((slot) => slot.asset.kind === 'image')
    const targetArea = state.width * state.height
    const ratio = shouldMatchRatio ? asset.width! / asset.height! : 0
    const canvas = shouldMatchRatio && state.method === OMNI
      ? omniAspectCanvas(state.width, state.height, ratio)
      : {
          width: shouldMatchRatio ? snapDimension(Math.sqrt(targetArea * ratio)) : state.width,
          height: shouldMatchRatio ? snapDimension(Math.sqrt(targetArea / ratio)) : state.height,
        }
    set({
      ...canvas,
      references: [
        ...state.references,
        { uid: nextUid(), asset, role: state.method !== OMNI && ['character-swap-v11', 'character-swap-hd-turbo8'].includes(state.presetId ?? '') && asset.kind === 'video' && !state.references.some((slot) => slot.role === 'aligned_guide') ? 'aligned_guide' : decision.role, include_audio: false },
      ],
      notice: null,
    })
    return true
  },

  removeReference: (uid) =>
    set((state) => ({ references: state.references.filter((slot) => slot.uid !== uid) })),

  setRole: (uid, role) =>
    set((state) => ({
      references: state.references.map((slot) => {
        if (slot.uid !== uid) return slot
        if (state.method === OMNI && role === 'aligned_guide') return slot
        if (!rolesFor(state.mode, slot.asset.kind).includes(role)) return slot
        // First/last frame are positional: only one slot may hold each.
        return { ...slot, role, include_audio: role === 'aligned_guide' ? false : slot.include_audio }
      }),
    })),

  setIncludeAudio: (uid, include) =>
    set((state) => ({
      references: state.references.map((slot) =>
        slot.uid === uid && slot.asset.kind === 'video' ? { ...slot, include_audio: include } : slot,
      ),
    })),

  reorderReference: (from, to) => set((state) => ({ references: move(state.references, from, to) })),

  clearReferences: () => set({ references: [] }),

  applyPreset: (preset) =>
    set((state) => {
      const patch = preset.patch
      const method = preset.patch.method ?? (state.method === OMNI ? 'baseline' : state.method)
      const omni = method === OMNI
      const mode = omni ? 'ref2va' : preset.suggests_mode ?? state.mode
      const { slots, dropped } = migrateReferences(mode, state.references)
      return {
        mode,
        // A recipe is a fresh start: never carry the previous take's name into it.
        title: patch.title ?? '',
        references: preset.id === 'character-swap-playground'
          ? slots.map((slot) => slot.asset.kind === 'video'
            ? { ...slot, role: 'motion' as const, include_audio: false }
            : slot.asset.kind === 'image' ? { ...slot, role: 'identity' as const } : slot)
          : ['character-swap-v11', 'character-swap-hd-turbo8'].includes(preset.id)
          ? slots.map((slot) => slot.asset.kind === 'video'
            ? { ...slot, role: 'aligned_guide' as const, include_audio: false }
            : preset.id === 'character-swap-hd-turbo8' && slot.asset.kind === 'image'
              ? { ...slot, role: 'identity' as const }
              : slot)
          : slots,
        prompt: patch.prompt ?? (preset.id === 'character-swap-v11' && !state.prompt.trimStart().startsWith('body_swap:')
          ? `body_swap: ${state.prompt || 'Replace the main guide subject with the character in <Picture 1>. Preserve guide scene, framing, pose and motion.'}`
          : state.prompt),
        auto_ratio: preset.id === 'character-swap-playground' ? true
          : ['character-swap-v11', 'character-swap-hd-turbo8'].includes(preset.id) ? false : state.auto_ratio,
        width: patch.width,
        height: patch.height,
        length: patch.length,
        steps: patch.steps,
        method,
        sampler_name: patch.sampler_name ?? state.sampler_name,
        scheduler: patch.scheduler ?? state.scheduler,
        custom_sigmas: patch.custom_sigmas ?? null,
        continuity: patch.continuity ?? state.continuity,
        easycache: patch.easycache ? { ...EASYCACHE_DEFAULTS, ...patch.easycache } : state.easycache,
        sol: patch.sol ? { ...SOL_DEFAULTS, ...patch.sol } : state.sol,
        ref_image_size: patch.ref_image_size ?? state.ref_image_size,
        weights: patch.weights ?? (
          mode === 'ref2va' || mode === 'performance'
            ? state.weights === 'pinkcherry_v03' ? 'int8' : state.weights
            : state.weights === 'gguf_q3km' || state.weights === 'erosmax_beta4' ? 'int8' : state.weights
        ),
        encoder: patch.encoder ?? state.encoder,
        lora_chain: patch.lora_chain ? patch.lora_chain.map((lora) => ({ ...lora })) : state.lora_chain,
        presetId: preset.id,
        ...(patch.seed !== undefined ? { seed: patch.seed } : {}),
        ...(omni ? {
          ...omniCore(), seed: patch.seed ?? 0, ref_image_size: patch.ref_image_size ?? 'max', auto_ratio: true,
          references: omniReferences(slots),
          ...sceneCanvas(patch.width, patch.height, slots),
          prompt: patch.prompt ?? (state.prompt.trimStart().startsWith('body_swap:') ? '' : state.prompt),
        } : {}),
        notice:
          omni && state.references.some((slot) => slot.role === 'aligned_guide')
            ? t('Se quitó la guía alineada: Escenas Omni no usa el contrato Character Swap.')
            : dropped.length > 0
            ? (dropped.length === 1 ? t('Se quitó 1 referencia: esta tarea no la admite.') : t('Se quitaron {n} referencias: esta tarea no las admite.', { n: dropped.length }))
            : null,
      }
    }),

  clearPreset: () => set({ presetId: null }),

  loadRequest: (request, assets) => {
    const references: ReferenceSlot[] = []
    let missing = 0
    for (const ref of request.references) {
      const asset = assets.get(ref.asset_id)
      if (!asset) {
        missing += 1
        continue
      }
      references.push({
        uid: nextUid(),
        asset,
        role: ref.role,
        include_audio: ref.include_audio,
      })
    }
    set({
      mode: request.mode,
      prompt: request.prompt,
      title: request.title ?? '',
      width: request.width,
      height: request.height,
      length: request.length,
      steps: request.steps,
      seed: request.seed,
      sampler_name: request.sampler_name,
      scheduler: request.scheduler,
      custom_sigmas: request.custom_sigmas ?? null,
      method: request.method,
      easycache: { ...EASYCACHE_DEFAULTS, ...request.easycache },
      sol: { ...SOL_DEFAULTS, ...request.sol },
      continuity: request.continuity ?? { auto_split: false, window: 'auto', pin_frames: '22' },
      weights: request.weights,
      encoder: request.encoder,
      lora_chain: request.lora_chain ?? [],
      ref_image_size: request.ref_image_size,
      references,
      presetId: request.preset_id,
      ...(request.method === OMNI ? { ...omniCore(), auto_ratio: true, references: omniReferences(references), presetId: request.preset_id === OMNI_PRESET ? OMNI_PRESET : null } : {}),
      notice:
        missing > 0
          ? (missing === 1 ? t('1 referencia ya no está en la biblioteca y no se pudo restaurar.') : t('{n} referencias ya no están en la biblioteca y no se pudieron restaurar.', { n: missing }))
          : null,
    })
    return { missing }
  },

  setNotice: (notice) => set({ notice }),

  reset: () => set(createComposerState()),
}))

/** Everything `toGenerationRequest` needs: the composer minus its transient UI bits. */
export type ComposerSnapshot = Omit<ComposerState, 'notice' | 'auto_ratio'>

/** Project the composer onto the wire contract the backend validates. */
export function toGenerationRequest(state: ComposerSnapshot): GenerationRequest {
  const omni = state.method === OMNI
  return {
    mode: state.mode,
    prompt: state.prompt,
    width: state.width,
    height: state.height,
    length: state.length,
    seed: state.seed,
    steps: state.steps,
    sampler_name: state.sampler_name,
    scheduler: state.scheduler,
    custom_sigmas: state.custom_sigmas,
    method: state.method,
    easycache: state.easycache,
    sol: state.sol,
    continuity: state.continuity,
    weights: state.weights,
    encoder: state.encoder,
    lora_chain: state.lora_chain,
    ref_image_size: state.ref_image_size,
    references: toReferenceInputs(state.references),
    title: state.title.trim() ? state.title.trim() : null,
    preset_id: state.presetId,
    ...(omni ? { ...omniCore(), references: toReferenceInputs(omniReferences(state.references)), preset_id: state.presetId === OMNI_PRESET ? OMNI_PRESET : null } : {}),
  }
}
