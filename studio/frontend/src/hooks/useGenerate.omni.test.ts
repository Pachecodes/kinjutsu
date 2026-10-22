import { expect, it } from 'vitest'
import { generateGate } from './useGenerate'
import { makeCapabilities, makeRequest } from '../test/factories'

it('gates Omni by its own live method rather than the primary engine or OG mode capability', () => {
  const caps = makeCapabilities({ comfy_online: false })
  caps.modes = caps.modes.map((mode) => ({ ...mode, available: false }))
  caps.methods.push({ ...caps.methods[0], id: 'fast_h3_omni_8step', available: true })
  const request = makeRequest({ mode: 'ref2va', method: 'fast_h3_omni_8step' })
  expect(generateGate(request, caps, []).blockedReason).toBeNull()
  caps.methods = caps.methods.filter((method) => method.id !== 'fast_h3_omni_8step')
  expect(generateGate(request, caps, []).blockedReason).toMatch(/Omni/)
})
it('blocks Omni until capabilities are known instead of assuming availability', () => {
  const request = makeRequest({ mode: 'ref2va', method: 'fast_h3_omni_8step' })
  expect(generateGate(request, undefined, []).blockedReason).toMatch(/Omni/)
})
