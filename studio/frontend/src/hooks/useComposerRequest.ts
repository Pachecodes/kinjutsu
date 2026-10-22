import { useMemo } from 'react'
import { useShallow } from 'zustand/react/shallow'

import type { GenerationRequest } from '../lib/types'
import { toGenerationRequest, useComposer } from '../state/composer'

/** The composer projected onto the wire contract, recomputed only on change. */
export function useComposerRequest(): GenerationRequest {
  const snapshot = useComposer(
    useShallow((store) => ({
      mode: store.mode,
      prompt: store.prompt,
      title: store.title,
      width: store.width,
      height: store.height,
      length: store.length,
      steps: store.steps,
      seed: store.seed,
      sampler_name: store.sampler_name,
      scheduler: store.scheduler,
      custom_sigmas: store.custom_sigmas,
      method: store.method,
      easycache: store.easycache,
      sol: store.sol,
      continuity: store.continuity,
      weights: store.weights,
      encoder: store.encoder,
      lora_chain: store.lora_chain,
      ref_image_size: store.ref_image_size,
      references: store.references,
      presetId: store.presetId,
    })),
  )
  return useMemo(() => toGenerationRequest(snapshot), [snapshot])
}
