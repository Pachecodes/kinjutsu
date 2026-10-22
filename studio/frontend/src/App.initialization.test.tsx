import { waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import App from './App'
import { useComposer } from './state/composer'
import { makeAsset, makeConfig, makePreset } from './test/factories'
import { renderWithProviders, resetStores, stubFetch } from './test/utils'

const hd = makePreset({ id: 'character-swap-hd-turbo8', suggests_mode: 'ref2va', patch: { prompt: 'body_swap: Replace the performer with <Picture 1>.', width: 736, height: 1280, length: 124, steps: 8 } })

beforeEach(() => {
  resetStores()
  window.localStorage.clear()
})
afterEach(() => vi.unstubAllGlobals())

function mount(available = true) {
  stubFetch([
    { match: '/api/config', body: makeConfig({ presets: [{ ...hd, available }] }) },
    { match: '/api/jobs', body: { jobs: [], total: 0 } },
    { match: '/api/health', body: { status: 'ok', version: '1', comfy_online: false, comfy_url: 'http://127.0.0.1:1', active_jobs: 0, data_dir: 'scratch' } },
    { match: '/api/assets', body: [] },
    { match: '/api/openapi.json', body: { paths: {} } },
    { match: '/api/validate', body: { ok: false, issues: [], normalized: null, estimate_seconds: null, estimate_basis: null, continuity_plan: null } },
  ])
  return renderWithProviders(<App />)
}

it('auto-applies available HD Turbo8 once to an empty composer, not after a later reset', async () => {
  const view = mount()
  await waitFor(() => expect(useComposer.getState().presetId).toBe(hd.id))
  expect(useComposer.getState()).toMatchObject({ prompt: hd.patch.prompt, width: 736, height: 1280 })
  useComposer.getState().reset()
  view.rerender(<App />)
  await waitFor(() => expect(useComposer.getState().presetId).toBeNull())
})

it.each(['prompt', 'references', 'presetId', 'title'] as const)('does not overwrite a draft containing %s', async (field) => {
  if (field === 'prompt') useComposer.getState().setPrompt('My draft')
  if (field === 'references') {
    useComposer.getState().setMode('ref2va')
    useComposer.getState().addAsset(makeAsset())
    expect(useComposer.getState().references).toHaveLength(1)
  }
  if (field === 'presetId') useComposer.setState({ presetId: 'another-recipe' })
  if (field === 'title') useComposer.getState().setTitle('My draft title')
  const before = useComposer.getState()
  const view = mount()
  await waitFor(() => expect(view.container.querySelector('header')).not.toBeNull())
  expect(useComposer.getState().presetId).toBe(before.presetId)
  expect(useComposer.getState().prompt).toBe(before.prompt)
  expect(useComposer.getState().title).toBe(before.title)
  expect(useComposer.getState().references).toEqual(before.references)
})

it('does not select an unavailable HD recipe', async () => {
  const view = mount(false)
  await waitFor(() => expect(view.container.querySelector('header')).not.toBeNull())
  expect(useComposer.getState().presetId).toBeNull()
})
