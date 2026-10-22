import { beforeEach, expect, it } from 'vitest'
import { useComposer, toGenerationRequest } from './composer'
import type { Preset } from '../lib/types'
beforeEach(() => useComposer.getState().reset())
it('loads 10Eros manual sigmas and round-trips the checkpoint through history', () => {
  const sigmas = [1, .94, .83, .72, .55, .30, .10, 0]
  useComposer.getState().applyPreset({id: '10eros-custom7', suggests_mode: null, patch: {width: 608, height: 352, length: 124, steps: 7, weights: 'erosmax_beta5', method: 'baseline', sampler_name: 'er_sde', scheduler: 'simple', custom_sigmas: sigmas}} as Preset)
  expect(toGenerationRequest(useComposer.getState())).toHaveProperty('custom_sigmas', sigmas)
  const request = toGenerationRequest(useComposer.getState())
  useComposer.getState().reset()
  useComposer.getState().loadRequest(request, new Map())
  expect(toGenerationRequest(useComposer.getState())).toHaveProperty('custom_sigmas', sigmas)
  expect(useComposer.getState().weights).toBe('erosmax_beta5')
})
