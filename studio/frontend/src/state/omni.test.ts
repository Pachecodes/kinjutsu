import { beforeEach, expect, it } from 'vitest'
import { useComposer, toGenerationRequest } from './composer'
import { makeAsset, makePreset, makeRequest, makeVideoAsset } from '../test/factories'
import { methodModeBlock, presetTier, isSwapPreset } from '../lib/curation'

const omni = 'fast_h3_omni_8step' as const
const preset = () => makePreset({ id: 'fasth3-omni-scenes', label: 'FastH3 Omni · Escenas', suggests_mode: 'ref2va', patch: { width: 512, height: 640, length: 124, steps: 8, method: omni } })
beforeEach(() => useComposer.getState().reset())
it('selects the Omni scene lane atomically from a swap draft without carrying adapters or aligned guides', () => {
  useComposer.setState({ mode: 'ref2va', presetId: 'character-swap-hd-turbo8', prompt: 'body_swap: stale direction', auto_ratio: false, seed: 42, weights: 'erosmax_beta5', encoder: 'heretic', lora_chain: [{ name: 'swap', strength: 1 }], references: [{ uid: 'guide', asset: makeVideoAsset(), role: 'aligned_guide', include_audio: true }] })
  useComposer.getState().setMethod(omni)
  expect(useComposer.getState()).toMatchObject({ mode: 'ref2va', method: omni, presetId: null, prompt: '', width: 512, height: 640, length: 124, seed: 0, steps: 8, sampler_name: 'euler', scheduler: 'simple', custom_sigmas: null, weights: 'int8', encoder: 'standard', lora_chain: [], auto_ratio: true, ref_image_size: 'max', continuity: { auto_split: false }, references: [] })
})
it('applies the creative scene preset with seed zero, image aspect matching, and no swap contract', () => {
  useComposer.getState().setMode('first_frame')
  useComposer.getState().addAsset(makeAsset({ width: 900, height: 900 }))
  useComposer.getState().setSeed(99)
  useComposer.getState().applyPreset(preset())
  const s = useComposer.getState()
  expect(s.width).toBe(s.height)
  expect(s.references[0].role).toBe('identity')
  expect(s).toMatchObject({ presetId: 'fasth3-omni-scenes', method: omni, seed: 0, steps: 8, ref_image_size: 'max', auto_ratio: true, continuity: { auto_split: false } })
  expect(isSwapPreset(s.presetId)).toBe(false)
  expect(presetTier(preset())).toBe('recommended')
})
it.each([
  [512, 640, 900, 900],
  [832, 480, 900, 900],
  [832, 480, 1600, 900],
  [832, 480, 900, 1600],
  [832, 480, 1200, 900],
  [832, 480, 900, 1200],
  [832, 480, 100000, 1],
  [832, 480, 1, 100000],
])('keeps Omni auto aspect from %ix%i for a %ix%i image inside the pixel ceiling', (width, height, imageWidth, imageHeight) => {
  useComposer.getState().setMethod(omni)
  useComposer.getState().setFrameSize(width, height)
  const image = makeAsset({ width: imageWidth, height: imageHeight })
  expect(useComposer.getState().addAsset(image)).toBe(true)
  const state = useComposer.getState()
  expect(state.width * state.height).toBeLessThanOrEqual(832 * 480)
  for (const dimension of [state.width, state.height]) {
    expect(dimension % 32).toBe(0)
    expect(dimension).toBeGreaterThanOrEqual(32)
    expect(dimension).toBeLessThanOrEqual(1536)
  }
  if (imageWidth === imageHeight) {
    expect(state.width).toBe(width === 512 ? 576 : 608)
    expect(state.width).toBe(state.height)
  }
  expect(state.references[0].asset).toEqual(image)
})
it('caps preset auto aspect with an existing square reference without changing its pixels', () => {
  const image = makeAsset({ width: 900, height: 900 })
  useComposer.getState().setMode('ref2va')
  useComposer.getState().addAsset(image)
  const recipe = preset()
  recipe.patch.width = 832
  recipe.patch.height = 480
  useComposer.getState().applyPreset(recipe)
  const state = useComposer.getState()
  expect(state.width).toBe(state.height)
  expect(state.width * state.height).toBeLessThanOrEqual(832 * 480)
  expect(state.references[0].asset).toEqual(image)
})
it('never silently caps an explicit manual Omni canvas or its serialized request', () => {
  useComposer.getState().setMethod(omni)
  useComposer.getState().setAutoRatio(false)
  useComposer.getState().setFrameSize(1024, 1024)
  useComposer.getState().addAsset(makeAsset({ width: 900, height: 900 }))
  expect(toGenerationRequest(useComposer.getState())).toMatchObject({ width: 1024, height: 1024 })
})
it('preserves the legacy non-Omni CharacterSwap automatic ratio rounding exactly', () => {
  useComposer.setState({ mode: 'ref2va', presetId: 'character-swap-playground', auto_ratio: true, width: 832, height: 480 })
  useComposer.getState().addAsset(makeAsset({ width: 900, height: 900 }))
  expect(useComposer.getState()).toMatchObject({ width: 640, height: 640 })
})
it('locks unsupported Omni options while permitting ordinary reference roles', () => {
  const s = useComposer.getState()
  s.setMethod(omni)
  s.setSteps(20); s.setSampler('res_multistep'); s.setScheduler('beta'); s.setWeights('gguf_q3km'); s.setEncoder('heretic'); s.addLora('swap', 1); s.setContinuity({ auto_split: true })
  s.addAsset(makeVideoAsset())
  const uid = useComposer.getState().references[0].uid
  s.setRole(uid, 'aligned_guide')
  expect(toGenerationRequest(useComposer.getState())).toMatchObject({ steps: 8, sampler_name: 'euler', scheduler: 'simple', weights: 'int8', encoder: 'standard', lora_chain: [], continuity: { auto_split: false }, references: [{ role: 'motion' }] })
  expect(useComposer.getState().references[0].role).toBe('motion')
})
it('leaves the scene lane atomically when changing task or applying a non-Omni recipe', () => {
  useComposer.getState().applyPreset(preset())
  useComposer.getState().setMode('performance')
  expect(useComposer.getState()).toMatchObject({ method: 'baseline', presetId: null, mode: 'performance' })
  useComposer.getState().applyPreset(preset())
  useComposer.getState().applyPreset(makePreset({ patch: { width: 832, height: 480, length: 124, steps: 16 } }))
  expect(useComposer.getState().method).toBe('baseline')
})
it('restores Omni reuse without inheriting swap auto-ratio and preserves reused seed and canvas', () => {
  useComposer.setState({ auto_ratio: false })
  const request = makeRequest({ method: omni, mode: 'ref2va', seed: 123, width: 832, height: 480, preset_id: 'fasth3-omni-scenes', steps: 8, sampler_name: 'euler', scheduler: 'simple', ref_image_size: 'max', continuity: { auto_split: false, window: 'auto', pin_frames: '22' } })
  useComposer.getState().loadRequest(request, new Map())
  expect(useComposer.getState()).toMatchObject({ auto_ratio: true, seed: 123, width: 832, height: 480, method: omni })
  expect(toGenerationRequest(useComposer.getState()).method).toBe(omni)
})
it('preserves a newly attached motion video after reusing Omni history with an incompatible swap preset', () => {
  const video = makeVideoAsset()
  useComposer.getState().loadRequest(makeRequest({ method: omni, mode: 'ref2va', preset_id: 'character-swap-hd-turbo8' }), new Map())
  expect(useComposer.getState().addAsset(video)).toBe(true)
  const state = useComposer.getState()
  expect(state.references).toEqual([{ uid: expect.any(String), asset: video, role: 'motion', include_audio: false }])
  expect(state.presetId).toBeNull()
  expect(toGenerationRequest(state)).toMatchObject({ preset_id: null, references: [{ asset_id: video.id, role: 'motion', include_audio: false }] })
})
it.each(['character-swap-v11', 'character-swap-hd-turbo8'])('never assigns aligned guides to Omni video attachments even with stale preset %s', (presetId) => {
  useComposer.setState({ mode: 'ref2va', method: omni, presetId })
  const video = makeVideoAsset()
  expect(useComposer.getState().addAsset(video)).toBe(true)
  const state = useComposer.getState()
  expect(state.references[0].role).toBe('motion')
  expect(toGenerationRequest(state).references).toEqual([{ asset_id: video.id, kind: 'video', role: 'motion', include_audio: false }])
})
it('allows Omni only for Ref2VA, never conflating it with FastH3 V2', () => {
  expect(methodModeBlock(omni, 'ref2va')).toBeNull()
  expect(methodModeBlock(omni, 'performance')).toBeTruthy()
  expect(methodModeBlock(omni, 'text')).toBeTruthy()
})
