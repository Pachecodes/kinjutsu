import { describe, expect, it } from 'vitest'

import {
  DIMENSION_MAX,
  FRAME_BASE,
  FRAME_STEP,
  PREFERRED_LENGTHS,
  isNativeLength,
  isValidLength,
  lengthToSeconds,
  secondsToLength,
  snapDimension,
  snapLength,
} from './frames'

describe('frame grid parity with the backend', () => {
  it('accepts only 17k+5 lengths inside bounds', () => {
    expect(isValidLength(5)).toBe(true)
    expect(isValidLength(124)).toBe(true)
    expect(isValidLength(362)).toBe(true)
    expect(isValidLength(125)).toBe(false)
    expect(isValidLength(4)).toBe(false)
    expect(isValidLength(3601)).toBe(false)
  })

  it('treats every preferred length as valid and native', () => {
    for (const frames of PREFERRED_LENGTHS) {
      expect(isValidLength(frames)).toBe(true)
      expect(isNativeLength(frames)).toBe(true)
    }
  })

  it('snaps arbitrary counts onto the nearest grid value', () => {
    expect(snapLength(130)).toBe(124)
    expect(snapLength(133)).toBe(141)
    expect(snapLength(0)).toBe(FRAME_BASE)
    expect(snapLength(10_000)).toBeLessThanOrEqual(3600)
    expect(isValidLength(snapLength(10_000))).toBe(true)
  })

  it('round-trips seconds through the 24fps grid', () => {
    expect(lengthToSeconds(124)).toBeCloseTo(5.167, 3)
    expect(lengthToSeconds(362)).toBeCloseTo(15.083, 3)
    expect(secondsToLength(10)).toBe(243)
    expect(isValidLength(secondsToLength(7.3))).toBe(true)
  })

  it('flags lengths outside the trained window', () => {
    expect(isNativeLength(123)).toBe(false)
    expect(isNativeLength(363)).toBe(false)
    expect(isNativeLength(124)).toBe(true)
  })

  it('snaps dimensions onto the 32px grid and clamps to the Studio cap', () => {
    expect(snapDimension(1000)).toBe(992)
    expect(snapDimension(17)).toBe(32)
    expect(snapDimension(99_999)).toBe(DIMENSION_MAX)
    expect(snapDimension(1024) % 32).toBe(0)
  })

  it('keeps the grid constants the workflow builder depends on', () => {
    expect(FRAME_STEP).toBe(17)
    expect(FRAME_BASE).toBe(5)
  })
})
