import { describe, expect, it } from 'vitest'

import { makeAsset, makeAudioAsset, makeVideoAsset } from '../test/factories'
import type { AssetOut, Mode, RefRole } from './types'
import {
  MAX_REF_IMAGES,
  MAX_REF_TOTAL,
  canAccept,
  durationWarning,
  kindsFor,
  maxReferencesFor,
  migrateReferences,
  missingTags,
  move,
  referenceTags,
  rolesFor,
  toReferenceInputs,
  withTagsAppended,
  type ReferenceSlot,
} from './references'

let uid = 0
function slot(asset: AssetOut, role: RefRole, include_audio = false): ReferenceSlot {
  uid += 1
  return { uid: `u${uid}`, asset, role, include_audio }
}

const images = (count: number) =>
  Array.from({ length: count }, (_, index) => slot(makeAsset({ id: `img-${index}` }), 'subject'))

describe('canAccept — the limits the backend enforces', () => {
  it('refuses every reference in text mode', () => {
    const result = canAccept('text', [], 'image')
    expect(result.ok).toBe(false)
    expect(result.reason).toMatch(/solo el prompt/i)
  })

  it('holds exactly one image in first-frame mode', () => {
    expect(canAccept('first_frame', [], 'image')).toMatchObject({ ok: true, role: 'first_frame' })
    expect(canAccept('first_frame', images(1), 'image').ok).toBe(false)
    expect(canAccept('first_frame', [], 'video').ok).toBe(false)
  })

  it('fills first then last in first+last mode', () => {
    const first = canAccept('first_last', [], 'image')
    expect(first).toMatchObject({ ok: true, role: 'first_frame' })
    const withFirst = [slot(makeAsset(), 'first_frame')]
    expect(canAccept('first_last', withFirst, 'image')).toMatchObject({ ok: true, role: 'last_frame' })
    const withBoth = [...withFirst, slot(makeAsset(), 'last_frame')]
    expect(canAccept('first_last', withBoth, 'image').ok).toBe(false)
  })

  it('caps images at 9 in reference mode', () => {
    expect(canAccept('ref2va', images(MAX_REF_IMAGES - 1), 'image').ok).toBe(true)
    const full = canAccept('ref2va', images(MAX_REF_IMAGES), 'image')
    expect(full.ok).toBe(false)
    expect(full.reason).toContain('9')
  })

  it('caps videos at 3 and audios at 3', () => {
    const videos = [0, 1, 2].map(() => slot(makeVideoAsset(), 'scene_video'))
    expect(canAccept('ref2va', videos, 'video').ok).toBe(false)
    const audios = [0, 1, 2].map(() => slot(makeAudioAsset(), 'voice'))
    expect(canAccept('ref2va', audios, 'audio').ok).toBe(false)
  })

  it('caps the combined total at 12', () => {
    const slots = [
      ...images(8),
      slot(makeVideoAsset(), 'scene_video'),
      slot(makeVideoAsset(), 'scene_video'),
      slot(makeAudioAsset(), 'voice'),
      slot(makeAudioAsset(), 'ambience'),
    ]
    expect(slots).toHaveLength(MAX_REF_TOTAL)
    const result = canAccept('ref2va', slots, 'image')
    expect(result.ok).toBe(false)
    expect(result.reason).toContain('12')
  })

  it('allows only one motion clip in performance transfer', () => {
    expect(canAccept('performance', [], 'video')).toMatchObject({ ok: true, role: 'motion' })
    const withMotion = [slot(makeVideoAsset(), 'motion')]
    expect(canAccept('performance', withMotion, 'video').ok).toBe(false)
  })

  it('anchors the first image as identity and the rest as subjects', () => {
    expect(canAccept('ref2va', [], 'image')).toMatchObject({ role: 'identity' })
    expect(canAccept('ref2va', [slot(makeAsset(), 'identity')], 'image')).toMatchObject({ role: 'subject' })
  })
})

describe('mode shapes', () => {
  it('exposes only the roles a mode accepts', () => {
    expect(rolesFor('text', 'image')).toEqual([])
    expect(rolesFor('first_frame', 'image')).toEqual(['first_frame'])
    expect(rolesFor('first_last', 'image')).toEqual(['first_frame', 'last_frame'])
    expect(rolesFor('ref2va', 'video')).toEqual(['motion', 'scene_video', 'aligned_guide'])
    expect(rolesFor('ref2va', 'audio')).toEqual(['voice', 'ambience'])
    expect(rolesFor('first_frame', 'audio')).toEqual([])
  })

  it('reports the kinds and the slot ceiling for each mode', () => {
    const expectations: [Mode, number][] = [
      ['text', 0],
      ['first_frame', 1],
      ['first_last', 2],
      ['ref2va', 12],
      ['performance', 12],
    ]
    for (const [mode, max] of expectations) expect(maxReferencesFor(mode)).toBe(max)
    expect(kindsFor('text')).toEqual([])
    expect(kindsFor('first_last')).toEqual(['image'])
    expect(kindsFor('ref2va')).toEqual(['image', 'video', 'audio'])
  })
})

describe('migrateReferences', () => {
  it('drops everything when moving to text mode', () => {
    const { slots, dropped } = migrateReferences('text', images(3))
    expect(slots).toHaveLength(0)
    expect(dropped).toHaveLength(3)
  })

  it('keeps one image when moving to first-frame mode and re-roles it', () => {
    const { slots, dropped } = migrateReferences('first_frame', images(3))
    expect(slots).toHaveLength(1)
    expect(slots[0].role).toBe('first_frame')
    expect(dropped).toHaveLength(2)
  })

  it('re-roles frame images into reference roles when entering ref2va', () => {
    const frames = [slot(makeAsset(), 'first_frame'), slot(makeAsset(), 'last_frame')]
    const { slots, dropped } = migrateReferences('ref2va', frames)
    expect(dropped).toHaveLength(0)
    expect(slots.map((entry) => entry.role)).toEqual(['identity', 'subject'])
  })

  it('drops the extra motion clips when entering performance transfer', () => {
    const clips = [slot(makeVideoAsset(), 'motion'), slot(makeVideoAsset(), 'motion')]
    const { slots, dropped } = migrateReferences('performance', clips)
    expect(slots).toHaveLength(1)
    expect(dropped).toHaveLength(1)
  })

  it('preserves a role that is still legal in the new mode', () => {
    const scene = [slot(makeVideoAsset(), 'scene_video')]
    const { slots } = migrateReferences('ref2va', scene)
    expect(slots[0].role).toBe('scene_video')
  })
})

describe('reference tags', () => {
  const mixed = [
    slot(makeAsset({ id: 'a' }), 'identity'),
    slot(makeVideoAsset({ id: 'b' }), 'motion'),
    slot(makeAsset({ id: 'c' }), 'subject'),
    slot(makeAudioAsset({ id: 'd' }), 'voice'),
  ]

  it('numbers per kind in creator order, like the workflow builder', () => {
    expect(referenceTags('ref2va', mixed)).toEqual(['<Picture 1>', '<Video 1>', '<Picture 2>', '<Audio 1>'])
  })

  it('has no tags in the frame-driven modes', () => {
    expect(referenceTags('first_last', [slot(makeAsset(), 'first_frame')])).toEqual([null])
  })

  it('renumbers when the creator reorders', () => {
    const reordered = move(mixed, 2, 0)
    expect(referenceTags('ref2va', reordered)).toEqual([
      '<Picture 1>',
      '<Picture 2>',
      '<Video 1>',
      '<Audio 1>',
    ])
  })

  it('reports the tags the prompt is missing', () => {
    expect(missingTags('ref2va', mixed, 'Only <Picture 1> is named here')).toEqual([
      '<Video 1>',
      '<Picture 2>',
      '<Audio 1>',
    ])
    expect(missingTags('ref2va', mixed, '<Picture 1><Video 1><Picture 2><Audio 1>')).toEqual([])
  })

  it('appends missing tags without destroying the prompt', () => {
    expect(withTagsAppended('A quiet room. ', ['<Picture 1>'])).toBe('A quiet room. <Picture 1>')
    expect(withTagsAppended('', ['<Picture 1>'])).toBe('<Picture 1>')
    expect(withTagsAppended('unchanged', [])).toBe('unchanged')
  })
})

describe('wire projection and warnings', () => {
  it('never sends include_audio for non-video references', () => {
    const inputs = toReferenceInputs([slot(makeAsset(), 'identity', true), slot(makeVideoAsset(), 'motion', true)])
    expect(inputs[0]).toMatchObject({ kind: 'image', include_audio: false })
    expect(inputs[1]).toMatchObject({ kind: 'video', include_audio: true })
  })

  it('warns on clips outside H3s 2-15s reference window', () => {
    expect(durationWarning(slot(makeVideoAsset({ duration_seconds: 20 }), 'motion'))).toMatch(/supera/)
    expect(durationWarning(slot(makeVideoAsset({ duration_seconds: 1 }), 'motion'))).toMatch(/más corto/)
    expect(durationWarning(slot(makeVideoAsset({ duration_seconds: 6 }), 'motion'))).toBeNull()
    expect(durationWarning(slot(makeAudioAsset({ duration_seconds: 16 }), 'voice'))).toMatch(/supera/)
    expect(durationWarning(slot(makeAsset(), 'identity'))).toBeNull()
  })

  it('moves items without mutating the original array', () => {
    const original = images(3)
    const moved = move(original, 0, 2)
    expect(moved.map((entry) => entry.asset.id)).toEqual(['img-1', 'img-2', 'img-0'])
    expect(original.map((entry) => entry.asset.id)).toEqual(['img-0', 'img-1', 'img-2'])
    expect(move(original, 0, 9)).toBe(original)
  })
})
