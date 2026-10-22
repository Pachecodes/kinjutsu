import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import App from './App'
import { useComposer } from './state/composer'
import { makeConfig, makeJob, makePreset, makeRequest } from './test/factories'
import { renderWithProviders, resetStores, stubFetch } from './test/utils'

const take = makeJob({ id: 'job-faro', title: 'Faro', prompt: 'A lighthouse at dusk.', status: 'completed' })

beforeEach(() => {
  resetStores()
  window.localStorage.clear()
})
afterEach(() => vi.unstubAllGlobals())

// jsdom reports no matching media query, so App renders its phone layout.
it('works as a phone: tabs, recipes up top, history and Reuse back into Create', async () => {
  const user = userEvent.setup()
  const { calls } = stubFetch([
    { match: '/api/config', body: makeConfig({ presets: [makePreset(), makePreset({ id: 'character-swap-hd-turbo8', label: 'Character Swap · HD Turbo8 ✓' })] }) },
    { match: '/api/jobs/job-faro/reuse', method: 'POST', body: makeRequest({ prompt: 'A lighthouse at dusk.', title: 'Faro', seed: 42 }) },
    { match: '/api/jobs/job-faro/events', body: { events: [] } },
    { match: '/api/jobs', body: { jobs: [take], total: 1 } },
    { match: '/api/health', body: { status: 'ok', version: '1', comfy_online: true, comfy_url: 'x', active_jobs: 0, data_dir: 'd' } },
    { match: '/api/assets', body: [] },
    { match: '/api/validate', method: 'POST', body: { ok: true, issues: [], normalized: null, estimate_seconds: null, estimate_basis: null, continuity_plan: null } },
  ])
  renderWithProviders(<App />)

  const nav = await screen.findByRole('navigation', { name: 'Secciones' })
  expect(within(nav).getAllByRole('button').map((button) => button.textContent)).toEqual(['Crear', 'Escenario', 'Refs', 'Galería'])
  expect(within(nav).getByRole('button', { name: 'Crear' })).toHaveAttribute('aria-current', 'page')
  // Recipes are the first step, so on a phone they sit above the composer.
  expect(screen.getByRole('button', { name: 'Receta: Character Swap · HD Turbo8 ✓. Cambiar receta' })).toBeInTheDocument()
  expect(screen.getByRole('radiogroup', { name: 'Tarea' })).toBeInTheDocument()
  expect(screen.getByRole('region', { name: 'Compositor' })).toBeInTheDocument()

  await user.click(within(nav).getByRole('button', { name: 'Galería' }))
  const gallery = await screen.findByRole('region', { name: 'Galería' })
  expect(within(gallery).getByRole('button', { name: 'Ver Faro en el escenario' })).toBeInTheDocument()

  await user.click(within(gallery).getByRole('button', { name: 'Reutilizar esta toma' }))
  expect(await screen.findByText('Receta y semilla cargadas')).toBeInTheDocument()
  expect(useComposer.getState()).toMatchObject({ prompt: 'A lighthouse at dusk.', title: 'Faro', seed: 42 })
  expect(within(nav).getByRole('button', { name: 'Crear' })).toHaveAttribute('aria-current', 'page')
  // Reuse loads a recipe; it never starts a render.
  expect(calls.some((call) => call.method === 'POST' && call.url.endsWith('/api/jobs'))).toBe(false)
})
