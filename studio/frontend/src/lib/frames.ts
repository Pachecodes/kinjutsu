/**
 * Frame-grid math, mirrored from `backend/app/workflow/frames.py`.
 *
 * The backend is authoritative and re-snaps everything it receives; this module
 * exists so the composer can show the creator the same numbers *before* a round
 * trip. The unit tests assert parity with the Python rules.
 */

export const FPS = 24
export const FRAME_STEP = 17
export const FRAME_BASE = 5
export const FRAME_MIN = FRAME_BASE
export const FRAME_MAX = 3600
export const TRAINED_FRAME_MIN = 124
export const TRAINED_FRAME_MAX = 362
export const PREFERRED_LENGTHS = [124, 175, 192, 243, 362] as const

export const DIMENSION_STEP = 32
export const DIMENSION_MIN = 32
export const DIMENSION_MAX = 1536

export function isValidLength(frames: number): boolean {
  if (frames < FRAME_MIN || frames > FRAME_MAX) return false
  return (frames - FRAME_BASE) % FRAME_STEP === 0
}

/** Snap an arbitrary frame count onto the nearest valid 17k+5 value. */
export function snapLength(frames: number): number {
  const clamped = Math.max(FRAME_MIN, Math.min(FRAME_MAX, Math.trunc(frames)))
  const k = Math.round((clamped - FRAME_BASE) / FRAME_STEP)
  let snapped = FRAME_BASE + FRAME_STEP * k
  if (snapped < FRAME_MIN) snapped = FRAME_MIN
  while (snapped > FRAME_MAX) snapped -= FRAME_STEP
  return snapped
}

export function lengthToSeconds(frames: number): number {
  return Math.round((frames / FPS) * 1000) / 1000
}

export function secondsToLength(seconds: number): number {
  return snapLength(Math.round(seconds * FPS))
}

export function isNativeLength(frames: number): boolean {
  return frames >= TRAINED_FRAME_MIN && frames <= TRAINED_FRAME_MAX
}

export function snapDimension(
  value: number,
  step = DIMENSION_STEP,
  minimum = DIMENSION_MIN,
  maximum = DIMENSION_MAX,
): number {
  const clamped = Math.max(minimum, Math.min(maximum, Math.trunc(value)))
  const snapped = Math.round(clamped / step) * step
  return Math.max(minimum, Math.min(maximum, snapped))
}

export interface AspectPreset {
  id: string
  label: string
  width: number
  height: number
}

/** Frame sizes that stay on the 32px grid and inside the Studio's 1536 cap. */
export const ASPECT_PRESETS: AspectPreset[] = [
  { id: 'wide-1024', label: '16:9 · 1024x576', width: 1024, height: 576 },
  { id: 'wide-832', label: '16:9 · 832x480', width: 832, height: 480 },
  { id: 'wide-608', label: '16:9 · 608x352', width: 608, height: 352 },
  { id: 'vertical-576', label: '9:16 · 576x1024', width: 576, height: 1024 },
  { id: 'vertical-480', label: '9:16 · 480x832', width: 480, height: 832 },
  { id: 'square-704', label: '1:1 · 704x704', width: 704, height: 704 },
  { id: 'portrait-768', label: '4:5 · 768x960', width: 768, height: 960 },
]

export function matchAspectPreset(width: number, height: number): AspectPreset | undefined {
  return ASPECT_PRESETS.find((preset) => preset.width === width && preset.height === height)
}
