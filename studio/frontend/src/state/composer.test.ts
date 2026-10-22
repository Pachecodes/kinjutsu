import { beforeEach, describe, expect, it } from 'vitest'

import { toGenerationRequest, useComposer } from './composer'

describe('automatic continuity', () => {
  beforeEach(() => useComposer.getState().reset())

  it('defaults to safe auto-splitting and sends its window policy on the wire', () => {
    const state = useComposer.getState()
    expect(state.continuity).toEqual({ auto_split: true, window: 'auto', pin_frames: '22' })
    state.setContinuity({ window: '141', pin_frames: '39' })
    const { notice: _notice, auto_ratio: _autoRatio, ...snapshot } = useComposer.getState()
    expect(toGenerationRequest(snapshot).continuity).toEqual({
      auto_split: true,
      window: '141',
      pin_frames: '39',
    })
  })
})

describe('composer LoRA chain', () => {
  beforeEach(() => useComposer.getState().reset())

  it('adds an installed LoRA once and sends its strength on the wire', () => {
    const store = useComposer.getState()
    store.addLora('PinkFluffyBunny-alpha-lora.safetensors', 0.5)
    store.addLora('PinkFluffyBunny-alpha-lora.safetensors', 1)

    const state = useComposer.getState()
    expect(state.lora_chain).toEqual([
      { name: 'PinkFluffyBunny-alpha-lora.safetensors', strength: 0.5 },
    ])
    const { notice: _notice, ...snapshot } = state
    expect(toGenerationRequest(snapshot).lora_chain).toEqual(state.lora_chain)
  })

  it('clears a LoRA when the selected mode changes checkpoint family', () => {
    useComposer.getState().addLora('PinkFluffyBunny-alpha-lora.safetensors', 0.5)
    useComposer.getState().setMode('ref2va')

    const state = useComposer.getState()
    expect(state.lora_chain).toEqual([])
    expect(state.notice).toContain('familia del checkpoint')
  })

  it('updates and removes LoRA strength entries', () => {
    useComposer.getState().addLora('adapter.safetensors', 1)
    useComposer.getState().setLoraStrength(0, 0.65)
    expect(useComposer.getState().lora_chain[0]?.strength).toBe(0.65)
    useComposer.getState().removeLora(0)
    expect(useComposer.getState().lora_chain).toEqual([])
  })

  it('returns to base INT8 when Pink Cherry changes to a reference-only mode', () => {
    useComposer.getState().setWeights('pinkcherry_v03')
    useComposer.getState().setMode('ref2va')

    expect(useComposer.getState().weights).toBe('int8')
  })

  it('keeps hybrid ErosMax Beta 5 across reference and frame modes', () => {
    useComposer.getState().setMode('ref2va')
    useComposer.getState().setWeights('erosmax_beta5')
    useComposer.getState().setMode('performance')
    expect(useComposer.getState().weights).toBe('erosmax_beta5')

    useComposer.getState().setMode('first_frame')
    expect(useComposer.getState().weights).toBe('erosmax_beta5')
  })
})

describe('automatic reference aspect ratio', () => {
  beforeEach(() => useComposer.getState().reset())

  it('matches the first reference image orientation and aspect on the 32px grid', () => {
    useComposer.getState().setMode('first_frame')
    const image = {
      id: 'portrait', kind: 'image' as const, original_name: 'portrait.png', stored_name: 'portrait.png',
      mime: 'image/png', size_bytes: 1, width: 704, height: 1280, duration_seconds: null,
      has_audio: null, created_at: '2026-09-04T00:00:00Z', url: '/portrait.png',
    }

    expect(useComposer.getState().addAsset(image)).toBe(true)
    expect(useComposer.getState().width).toBe(576)
    expect(useComposer.getState().height).toBe(1024)
  })

  it('leaves the frame unchanged when auto ratio is disabled', () => {
    useComposer.getState().setMode('first_frame')
    useComposer.getState().setAutoRatio(false)
    const image = {
      id: 'portrait', kind: 'image' as const, original_name: 'portrait.png', stored_name: 'portrait.png',
      mime: 'image/png', size_bytes: 1, width: 704, height: 1280, duration_seconds: null,
      has_audio: null, created_at: '2026-09-04T00:00:00Z', url: '/portrait.png',
    }

    expect(useComposer.getState().addAsset(image)).toBe(true)
    expect(useComposer.getState().width).toBe(1024)
    expect(useComposer.getState().height).toBe(576)
  })
})

describe('premium method recipe', () => {
  beforeEach(() => useComposer.getState().reset())

  it('selects the verified W4A8 four-step base recipe without changing the requested output size', () => {
    useComposer.getState().setFrameSize(640, 1152)
    useComposer.getState().setLength(175)
    useComposer.getState().setMethod('w4a8_latent2x_refine3')

    const state = useComposer.getState()
    expect(state.method).toBe('w4a8_latent2x_refine3')
    expect(state.width).toBe(640)
    expect(state.height).toBe(1152)
    expect(state.length).toBe(124)
    expect(state.steps).toBe(4)
    expect(state.sampler_name).toBe('er_sde')
    expect(state.scheduler).toBe('simple')
    expect(state.weights).toBe('int8')
  })

  it('returns to Quality when switching from Premium to Ref2VA so custom checkpoints are selectable', () => {
    useComposer.getState().setMethod('w4a8_latent2x_refine3')
    useComposer.getState().setMode('ref2va')

    expect(useComposer.getState().method).toBe('baseline')
  })
})

describe('Ref2VA VSA method recipe', () => {
  beforeEach(() => useComposer.getState().reset())

  it('selects VSA without replacing creator length, encoder, weights, LoRAs, or continuity', () => {
    useComposer.getState().setMode('ref2va')
    useComposer.getState().addLora('MysticXXX_MMH3-V3.safetensors', 0.7)
    useComposer.getState().setLength(175)
    useComposer.getState().setWeights('gguf_q3km')
    useComposer.getState().setEncoder('heretic')
    useComposer.getState().setContinuity({ auto_split: true })
    useComposer.getState().setMethod('ref2va_vsa')

    const state = useComposer.getState()
    expect(state.method).toBe('ref2va_vsa')
    expect(state.length).toBe(175)
    expect(state.steps).toBe(4)
    expect(state.sampler_name).toBe('euler')
    expect(state.scheduler).toBe('simple')
    expect(state.weights).toBe('gguf_q3km')
    expect(state.encoder).toBe('heretic')
    expect(state.lora_chain).toEqual([{ name: 'MysticXXX_MMH3-V3.safetensors', strength: 0.7 }])
    expect(state.continuity.auto_split).toBe(true)
  })

  it('returns to Quality when leaving References mode', () => {
    useComposer.getState().setMode('ref2va')
    useComposer.getState().setMethod('ref2va_vsa')
    useComposer.getState().setMode('first_frame')

    expect(useComposer.getState().method).toBe('baseline')
  })
})

describe('creator preset recipe', () => {
  beforeEach(() => useComposer.getState().reset())

  it('loads the complete LightX2V8 recipe including the ordered LoRA chain', () => {
    useComposer.getState().applyPreset({
      id: 'lightx2v8-creator-5s',
      label: 'LightX2V8 Creator 5s',
      blurb: 'Exact final recipe',
      suggests_mode: 'first_frame',
      patch: {
        width: 1024,
        height: 576,
        length: 124,
        steps: 8,
        method: 'baseline',
        sampler_name: 'er_sde',
        scheduler: 'beta',
        weights: 'int8',
        encoder: 'standard',
        lora_chain: [
          {
            name: 'minimax_h3_fl2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors',
            strength: 1,
          },
        ],
        ref_image_size: 'match',
      },
      recipe: ['recipe'],
      caveats: ['caveat'],
      needs: [],
      recommended_duration_seconds: 5.167,
      estimate_seconds: 1,
      available: true,
      unavailable_reason: null,
    })

    const state = useComposer.getState()
    expect(state.mode).toBe('first_frame')
    expect(state.steps).toBe(8)
    expect(state.sampler_name).toBe('er_sde')
    expect(state.scheduler).toBe('beta')
    expect(state.weights).toBe('int8')
    expect(state.encoder).toBe('standard')
    expect(state.lora_chain).toEqual([
      {
        name: 'minimax_h3_fl2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors',
        strength: 1,
      },
    ])
  })
})
