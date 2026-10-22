/**
 * Aligned-guide bookkeeping, as pure functions.
 *
 * The backend refuses a guide that does not match the output exactly (size,
 * frame count, 24 fps). This module lets the composer show *why* before a round
 * trip, keep three different durations apart — what was requested, what the
 * frame grid rounds it to, and what the file really covers — and offer the two
 * honest ways out: follow the guide, or prepare a new guide from its original.
 */

import { FPS, isValidLength, lengthToSeconds } from './frames'
import type { ReferenceSlot } from './references'

export interface FrameSpec {
  width: number
  height: number
  frames: number
  seconds: number
}

export interface GuideCoverage {
  /** Length of the original the guide was prepared from. */
  sourceSeconds: number
  start: number
  end: number
  /** True when the guide uses only part of its original. */
  excerpt: boolean
  /** Original seconds left after the used stretch. */
  tailSeconds: number
}

export interface GuideStatus {
  output: FrameSpec
  /** Null when the file's duration could not be read. */
  guide: (Omit<FrameSpec, 'frames' | 'seconds'> & { frames: number | null; seconds: number | null }) | null
  sizeMatch: boolean
  framesMatch: boolean
  ok: boolean
  coverage: GuideCoverage | null
  /**
   * Whether the guide's original holds enough footage, from the same start, to
   * prepare a guide as long as the output. Null when there is no provenance.
   */
  originalCoversOutput: boolean | null
  /** The output can simply follow the guide (its size and length are on-grid). */
  canFollowGuide: boolean
}

const EPSILON = 1e-6

export function findGuide(references: ReferenceSlot[]): ReferenceSlot | null {
  return references.find((slot) => slot.role === 'aligned_guide') ?? null
}

/** A 24 fps clip's frame count from its probed duration. */
export function framesFromSeconds(seconds: number | null): number | null {
  if (seconds === null || !Number.isFinite(seconds) || seconds <= 0) return null
  return Math.round(seconds * FPS)
}

export function guideStatus(
  output: { width: number; height: number; length: number },
  slot: ReferenceSlot | null,
): GuideStatus | null {
  if (!slot) return null
  const { asset } = slot
  const spec: FrameSpec = {
    width: output.width,
    height: output.height,
    frames: output.length,
    seconds: lengthToSeconds(output.length),
  }
  const frames = framesFromSeconds(asset.duration_seconds)
  const guide =
    asset.width !== null && asset.height !== null
      ? {
          width: asset.width,
          height: asset.height,
          frames,
          seconds: frames === null ? null : lengthToSeconds(frames),
        }
      : null

  const sizeMatch = guide !== null && guide.width === spec.width && guide.height === spec.height
  const framesMatch = guide !== null && guide.frames === spec.frames

  const provenance = asset.guide_provenance ?? null
  let coverage: GuideCoverage | null = null
  let originalCoversOutput: boolean | null = null
  if (provenance && guide?.seconds != null) {
    const end = provenance.start_seconds + guide.seconds
    const tail = Math.max(0, provenance.source_duration_seconds - end)
    coverage = {
      sourceSeconds: provenance.source_duration_seconds,
      start: provenance.start_seconds,
      end,
      excerpt: provenance.start_seconds > EPSILON || tail > 0.05,
      tailSeconds: tail,
    }
    originalCoversOutput =
      provenance.source_duration_seconds - provenance.start_seconds + EPSILON >= spec.seconds
  }

  const canFollowGuide =
    guide !== null &&
    guide.frames !== null &&
    isValidLength(guide.frames) &&
    guide.width % 32 === 0 &&
    guide.height % 32 === 0

  return {
    output: spec,
    guide,
    sizeMatch,
    framesMatch,
    ok: sizeMatch && framesMatch,
    coverage,
    originalCoversOutput,
    canFollowGuide,
  }
}

function seconds(value: number): string {
  return `${value.toFixed(2).replace('.', ',')} s`
}

/**
 * One plain sentence for the mismatch, naming both sides. The usual trap —
 * output 243 frames against a 124-frame guide — reads as exactly that.
 */
export function describeMismatch(status: GuideStatus): string | null {
  if (status.ok) return null
  if (!status.guide) return 'No se pudo leer el tamaño de la guía. Prepárala de nuevo desde el original.'
  const parts: string[] = []
  if (!status.framesMatch) {
    parts.push(
      status.guide.frames === null
        ? `la salida pide ${status.output.frames} frames (${seconds(status.output.seconds)}) y no se pudo leer la duración de la guía`
        : `la salida pide ${status.output.frames} frames (${seconds(status.output.seconds)}) pero la guía tiene ${status.guide.frames} (${seconds(status.guide.seconds ?? 0)})`,
    )
  }
  if (!status.sizeMatch) {
    parts.push(
      `la salida es ${status.output.width}×${status.output.height} y la guía ${status.guide.width}×${status.guide.height}`,
    )
  }
  const sentence = parts.join('; y ')
  return sentence.charAt(0).toUpperCase() + sentence.slice(1) + '.'
}

export function formatSecondsEs(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return `${value.toFixed(digits).replace('.', ',')} s`
}
