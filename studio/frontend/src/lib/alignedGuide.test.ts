import { describe, expect, it } from 'vitest'
import { referenceTags, rolesFor, type ReferenceSlot } from './references'
import { makeAsset as asset } from '../test/factories'

describe('aligned guide role', () => {
  it('is selectable only in References and never consumes a Video token', () => {
    expect(rolesFor('ref2va','video')).toContain('aligned_guide')
    expect(rolesFor('performance','video')).not.toContain('aligned_guide')
    const slots = [
      {uid:'guide',asset:asset({kind:'video'}),role:'aligned_guide',include_audio:false},
      {uid:'motion',asset:asset({kind:'video'}),role:'motion',include_audio:false},
    ] as ReferenceSlot[]
    expect(referenceTags('ref2va',slots)).toEqual([null,'<Video 1>'])
  })
})
