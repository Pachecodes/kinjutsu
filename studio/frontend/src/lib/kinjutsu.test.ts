import { describe, expect, it } from 'vitest'

import { makeAsset, makePreset, makeVideoAsset } from '../test/factories'
import { curatePresets, presetTier } from './curation'
import { describeModel, missingBytes, modelState } from './models'
import { EMPTY_DRAFT, effectiveSeconds, mapAttachments, suggestedTemplate, templateProblem, toPromptForm } from './promptForm'
import type { ReferenceSlot } from './references'
import type { ManagedModel } from './types'

const slot = (uid: string, role: ReferenceSlot['role'], kind: 'image' | 'video' | 'audio' = 'image'): ReferenceSlot => ({
  uid,
  role,
  include_audio: false,
  asset: kind === 'video' ? makeVideoAsset({ original_name: `${uid}.mp4` }) : makeAsset({ original_name: `${uid}.png`, kind }),
})

describe('prompt form mapping', () => {
  it('maps the approved swap to Picture 1 identity plus a tokenless aligned guide', () => {
    const mapping = mapAttachments('ref2va', [slot('face', 'identity'), slot('guide', 'aligned_guide', 'video')])
    expect(mapping.assets.map(({ kind, role, token }) => ({ kind, role, token }))).toEqual([
      { kind: 'image', role: 'identity', token: '<Picture 1>' },
      { kind: 'aligned_guide', role: 'aligned_guide', token: undefined },
    ])
    expect(templateProblem('character-swap-aligned', mapping)).toBeNull()
    expect(templateProblem('motion-ref2va', mapping)).toMatch(/sin guía alineada/)
  })

  it('numbers frame-mode images itself and refuses roles the form cannot express', () => {
    const frames = mapAttachments('first_last', [slot('a', 'first_frame'), slot('b', 'last_frame')])
    expect(frames.assets.map((asset) => asset.token)).toEqual(['<Picture 1>', '<Picture 2>'])
    expect(templateProblem('fl2va', frames)).toBeNull()

    const odd = mapAttachments('ref2va', [slot('face', 'identity'), slot('hat', 'prop'), slot('mic', 'voice', 'audio')])
    expect(odd.unsupported).toHaveLength(2)
    expect(templateProblem('motion-ref2va', odd)).toMatch(/hat\.png/)
  })

  it('suggests the template from task and recipe', () => {
    expect(suggestedTemplate('ref2va', 'character-swap-hd-turbo8')).toBe('character-swap-aligned')
    expect(suggestedTemplate('ref2va', 'character-swap-playground')).toBe('motion-ref2va')
    expect(suggestedTemplate('first_frame', null)).toBe('i2va')
    expect(suggestedTemplate('text', 'fast-preview-5s')).toBe('t2va')
  })

  it('builds the exact request: real duration to the millisecond, aligned rules enforced', () => {
    expect(effectiveSeconds(124)).toBe(5.167)
    expect(effectiveSeconds(243)).toBe(10.125)
    const mapping = mapAttachments('ref2va', [slot('face', 'identity'), slot('guide', 'aligned_guide', 'video')])
    const form = toPromptForm(
      {
        ...EMPTY_DRAFT,
        identity: ' A performer ',
        descriptions: { face: 'Portrait', guide: 'Existing guide' },
        shots: [{ ...EMPTY_DRAFT.shots[0], scene: 'Room' }, { ...EMPTY_DRAFT.shots[0], start_seconds: 2 }],
        music: 'Piano',
        dialogue: [{ shot: 1, start_seconds: 0.5, end_seconds: 1, speaker: 'A', language: 'Spanish', text: 'Hola', delivery: 'soft', subject: 1 }],
      },
      mapping,
      124,
      'character-swap-aligned',
    )
    expect(form.duration_seconds).toBe(5.167)
    expect(form.identity).toBe('A performer')
    expect(form.assets).toEqual([
      { kind: 'image', role: 'identity', token: '<Picture 1>', description: 'Portrait' },
      { kind: 'aligned_guide', role: 'aligned_guide', description: 'Existing guide' },
    ])
    expect(form.shots).toHaveLength(1)
    expect(form.audio.music).toBe('N/A')
    expect(form.dialogue).toEqual([])
  })

  it('keeps subject binding for Motion only', () => {
    const line = { shot: 1, start_seconds: 0.5, end_seconds: 1, speaker: 'A', language: 'Spanish', text: '¡Hola!', delivery: 'soft', subject: 1 as const }
    const draft = { ...EMPTY_DRAFT, dialogue: [line] }
    expect(toPromptForm(draft, { assets: [], unsupported: [] }, 124, 'motion-ref2va').dialogue[0]).toMatchObject({ subject: 1, text: '¡Hola!' })
    expect(toPromptForm(draft, { assets: [], unsupported: [] }, 124, 't2va').dialogue[0]).not.toHaveProperty('subject')
  })
})

const model = (overrides: Partial<ManagedModel> = {}): ManagedModel => ({
  id: '0',
  target: 'loras/minimax_h3_character_swap_v1.1_ref2va_fro.safetensors',
  size: 80_673_112,
  sha256: 'a'.repeat(64),
  included: true,
  installed: false,
  verified: false,
  reused: false,
  revision: 'b'.repeat(40),
  repo: 'Alissonerdx/Minimax-H3-ComfyUI',
  ...overrides,
})

describe('model catalog presentation', () => {
  it('names known targets and falls back to the file name', () => {
    expect(describeModel(model())).toMatchObject({ label: 'BFS Character Swap v1.1', category: 'loras' })
    expect(describeModel({ target: 'vae/something_new.safetensors' })).toMatchObject({ label: 'something_new.safetensors', category: 'vae' })
  })

  it('merges the slow catalog with live jobs, including a requested cancel', () => {
    expect(modelState(model(), undefined, false)).toBe('missing')
    expect(modelState(model({ verified: true, installed: true, reused: true }), undefined, false)).toBe('reused')
    const job = { id: '0', status: 'downloading' as const, bytes: 10, total: 100, error: null }
    expect(modelState(model(), job, false)).toBe('downloading')
    expect(modelState(model(), job, true)).toBe('cancelling')
    expect(modelState(model(), { ...job, status: 'installed' }, false)).toBe('installed_now')
    expect(modelState(model(), { ...job, status: 'error', error: 'SHA256' }, false)).toBe('error')
    expect(missingBytes([model(), model({ verified: true, size: 5 })])).toBe(80_673_112)
  })
})

describe('backend recipe curation', () => {
  it('honours Kinjutsu groups and puts the single default first', () => {
    const curated = curatePresets([
      makePreset({ id: 'balanced-10s', group: 'recommended' }),
      makePreset({ id: 'fast-final-trt-5s', group: 'experimental' }),
      makePreset({ id: 'character-swap-v11', group: 'control' }),
      makePreset({ id: 'character-swap-hd-turbo8', group: 'recommended', default: true }),
    ])
    expect(curated.recommended.map((preset) => preset.id)).toEqual(['character-swap-hd-turbo8', 'balanced-10s'])
    expect(curated.standard.map((preset) => preset.id)).toEqual(['character-swap-v11'])
    expect(presetTier(makePreset({ id: 'fast-final-trt-5s', group: 'experimental' }))).toBe('experimental')
  })
})
