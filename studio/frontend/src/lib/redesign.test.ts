import { describe, expect, it } from 'vitest'

import { makeAsset, makePreset, makeVideoAsset } from '../test/factories'
import {
  cancelOutcome,
  curatePresets,
  describeStage,
  methodModeBlock,
  presetReplacesPrompt,
  presetTier,
} from './curation'
import { describeMismatch, framesFromSeconds, guideStatus } from './guideSync'
import { blockingSentence, issueArea, visibleIssues } from './issues'
import { appendToPrompt, buildPrompt, buildSwapDirection, EMPTY_FIELDS, swapPromptReady } from './promptBuilder'
import { slotsFor, swapChecklist } from './recipeRoute'
import type { ReferenceSlot } from './references'
import type { Issue } from './types'

const guideSlot = (overrides: Parameters<typeof makeVideoAsset>[0] = {}): ReferenceSlot => ({
  uid: 'guide',
  asset: makeVideoAsset({ width: 736, height: 1280, duration_seconds: 124 / 24, has_audio: false, ...overrides }),
  role: 'aligned_guide',
  include_audio: false,
})

const issue = (code: string, field: string | null, severity: Issue['severity'] = 'error'): Issue => ({
  code,
  field,
  severity,
  message: `backend says ${code}`,
})

describe('recipe curation', () => {
  it('leads with the approved swap and keeps unknown recipes off the front page', () => {
    const curated = curatePresets([
      makePreset({ id: 'brand-new-backend-recipe', label: 'New' }),
      makePreset({ id: 'fast-preview-5s' }),
      makePreset({ id: 'character-swap-hd-turbo8' }),
      makePreset({ id: 'balanced-10s' }),
      makePreset({ id: 'character-swap-playground' }),
    ])
    expect(curated.recommended.map((preset) => preset.id)).toEqual(['character-swap-hd-turbo8', 'fast-preview-5s'])
    expect(curated.standard.map((preset) => preset.id)).toEqual(['balanced-10s'])
    expect(curated.experimental.map((preset) => preset.id).sort()).toEqual(
      ['brand-new-backend-recipe', 'character-swap-playground'].sort(),
    )
  })

  it('honours a backend tier when one is sent, and files legacy under experimental', () => {
    expect(presetTier(makePreset({ id: 'brand-new', tier: 'recommended' }))).toBe('recommended')
    expect(presetTier(makePreset({ id: 'fast-preview-5s', tier: 'legacy' }))).toBe('experimental')
  })

  it('only asks before replacing a prompt the creator actually wrote', () => {
    const withPrompt = makePreset({ patch: { ...makePreset().patch, prompt: 'body_swap: recipe text <Picture 1>' } })
    expect(presetReplacesPrompt(withPrompt, '')).toBe(false)
    expect(presetReplacesPrompt(withPrompt, 'body_swap: recipe text <Picture 1>')).toBe(false)
    expect(presetReplacesPrompt(withPrompt, 'my own scene')).toBe(true)
    expect(presetReplacesPrompt(makePreset(), 'my own scene')).toBe(false)
  })

  it('names which tasks a method cannot run in', () => {
    expect(methodModeBlock('w4a8_lightx2v_trt', 'ref2va')).toMatch(/Solo para Texto/)
    expect(methodModeBlock('ref2va_vsa', 'text')).toMatch(/Referencias/)
    expect(methodModeBlock('baseline', 'performance')).toBeNull()
  })
})

describe('render stages', () => {
  it('maps backend stages to creator phases and keeps unknown labels verbatim', () => {
    expect(describeStage({ status: 'queued', stage: null })).toMatchObject({ phase: 'queued' })
    expect(describeStage({ status: 'running', stage: 'Understanding references' })).toMatchObject({
      phase: 'prepare',
      label: 'Preparando referencias',
    })
    expect(describeStage({ status: 'running', stage: 'Decoding video' })).toMatchObject({ phase: 'decode' })
    expect(describeStage({ status: 'running', stage: 'Some new node' })).toMatchObject({
      phase: 'render',
      label: 'Some new node',
    })
  })

  it('distinguishes a requested interrupt from a take that never computed', () => {
    expect(cancelOutcome(['Queued.', 'Interrupted the running render.'])).toBe('interrupt_requested')
    expect(cancelOutcome(['Removed from the ComfyUI queue.'])).toBe('dequeued')
    expect(cancelOutcome(['ComfyUI is not running this take; marked canceled locally without interrupting anything.'])).toBe(
      'not_running',
    )
    expect(cancelOutcome(['Canceled before ComfyUI accepted it.'])).toBe('before_submit')
    expect(cancelOutcome([])).toBe('unknown')
  })
})

describe('aligned guide sync', () => {
  it('spells out the classic 243-frame output against a 124-frame guide', () => {
    const status = guideStatus({ width: 736, height: 1280, length: 243 }, guideSlot())!
    expect(status.ok).toBe(false)
    expect(status.sizeMatch).toBe(true)
    expect(status.framesMatch).toBe(false)
    expect(status.canFollowGuide).toBe(true)
    expect(describeMismatch(status)).toBe(
      'La salida pide 243 frames (10,13 s) pero la guía tiene 124 (5,17 s).',
    )
  })

  it('reports size mismatches and a matching guide', () => {
    const wrongSize = guideStatus({ width: 576, height: 1024, length: 124 }, guideSlot())!
    expect(describeMismatch(wrongSize)).toMatch(/576×1024 y la guía 736×1280/)
    const ok = guideStatus({ width: 736, height: 1280, length: 124 }, guideSlot())!
    expect(ok.ok).toBe(true)
    expect(describeMismatch(ok)).toBeNull()
  })

  it('keeps requested, grid and real coverage apart and flags excerpts', () => {
    const slot = guideSlot({
      guide_provenance: { source_asset_id: 'src', fit: 'pad', start_seconds: 0, source_duration_seconds: 16.667 },
    })
    const status = guideStatus({ width: 736, height: 1280, length: 124 }, slot)!
    expect(status.coverage).toMatchObject({ start: 0, excerpt: true })
    expect(status.coverage!.tailSeconds).toBeCloseTo(16.667 - 124 / 24, 3)
    expect(status.originalCoversOutput).toBe(true)

    const longer = guideStatus({ width: 736, height: 1280, length: 413 }, slot)!
    expect(longer.originalCoversOutput).toBe(false)
  })

  it('never invents a frame count when the duration is unknown', () => {
    expect(framesFromSeconds(null)).toBeNull()
    const status = guideStatus({ width: 736, height: 1280, length: 124 }, guideSlot({ duration_seconds: null }))!
    expect(status.ok).toBe(false)
    expect(status.canFollowGuide).toBe(false)
    expect(describeMismatch(status)).toMatch(/no se pudo leer la duración/)
  })
})

describe('deterministic prompt template', () => {
  it('orders the creator words and skips empty fields', () => {
    expect(
      buildPrompt({
        ...EMPTY_FIELDS,
        subject: '<Picture 1> a tall woman',
        action: 'walks into the bar',
        camera: ['tracking', 'static'],
        sound: 'jazz trio',
      }),
    ).toBe(
      '<Picture 1> a tall woman. walks into the bar. Camera: static locked-off camera, smooth lateral tracking shot. Sound: jazz trio.',
    )
    expect(buildPrompt(EMPTY_FIELDS)).toBe('')
  })

  it('adds swap direction without touching scene or camera, and appends after the recipe text', () => {
    const direction = buildSwapDirection({ subject: 'freckles', light: ['golden'], sound: '' })
    expect(direction).toBe('Character details for <Picture 1>: freckles. Lighting and mood: warm golden-hour sunlight.')
    expect(appendToPrompt('body_swap: recipe <Picture 1>.', direction)).toBe(`body_swap: recipe <Picture 1>. ${direction}`)
    expect(swapPromptReady('body_swap: recipe <Picture 1>.')).toBe(true)
    expect(swapPromptReady('recipe <Picture 1>.')).toBe(false)
  })
})

describe('recipe routes', () => {
  it('shows identity and guide slots for the approved swap', () => {
    expect(slotsFor('ref2va', 'character-swap-hd-turbo8').map((slot) => [slot.key, slot.roles[0]])).toEqual([
      ['identity', 'identity'],
      ['guide', 'aligned_guide'],
    ])
    expect(slotsFor('ref2va', 'character-swap-playground')[1].roles).toEqual(['motion'])
    expect(slotsFor('first_last', null).map((slot) => slot.key)).toEqual(['first', 'last'])
    expect(slotsFor('ref2va', null)).toEqual([])
  })

  it('checks the swap route step by step', () => {
    const base = { presetId: 'character-swap-hd-turbo8', width: 736, height: 1280, length: 124, prompt: '' }
    const empty = swapChecklist({ ...base, references: [] })
    expect(empty.map((step) => step.done)).toEqual([false, false, false, false])

    const identity: ReferenceSlot = { uid: 'id', asset: makeAsset(), role: 'identity', include_audio: false }
    const ready = swapChecklist({
      ...base,
      prompt: 'body_swap: replace with <Picture 1>.',
      references: [identity, guideSlot()],
    })
    expect(ready.every((step) => step.done)).toBe(true)

    const misaligned = swapChecklist({ ...base, length: 243, references: [identity, guideSlot()] })
    expect(misaligned.find((step) => step.id === 'aligned')?.done).toBe(false)
  })
})

describe('issue routing', () => {
  it('places issues beside the control they concern', () => {
    expect(issueArea(issue('guide_alignment', 'references'))).toBe('references')
    expect(issueArea(issue('unknown_asset', 'references[1]'))).toBe('references')
    expect(issueArea(issue('character_swap_trigger', 'prompt'))).toBe('prompt')
    expect(issueArea(issue('lora_unavailable', 'lora_chain[0]'))).toBe('advanced')
    expect(issueArea(issue('easycache_window', 'easycache'))).toBe('method')
    expect(issueArea(issue('x', null))).toBe('general')
  })

  it('does not repeat missing inputs as red errors but still blocks with a plain sentence', () => {
    const missing = issue('character_swap_guide_required', 'references')
    const real = issue('guide_recipe', 'method')
    expect(visibleIssues([missing, real])).toEqual([real])
    expect(blockingSentence(missing)).toMatch(/Falta el vídeo guía/)
    expect(blockingSentence(issue('never_seen_code', null))).toBe('backend says never_seen_code')
  })
})
