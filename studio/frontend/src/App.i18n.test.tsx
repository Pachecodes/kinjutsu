import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import { useLocale } from './i18n'
import { BRAND } from './lib/brand'
import { useComposer } from './state/composer'
import { makeConfig, makePreset } from './test/factories'
import { renderWithProviders, resetStores, stubFetch } from './test/utils'

const RECIPE = 'Character Swap · HD Turbo8 ✓'
const PROMPT = 'body_swap: Replace the main guide subject with <Picture 1>. Mantén la cámara.'

function stubStudio() {
  return stubFetch([
    {
      match: '/api/config',
      body: makeConfig({ presets: [makePreset(), makePreset({ id: 'character-swap-hd-turbo8', label: RECIPE })] }),
    },
    { match: '/api/jobs', body: { jobs: [], total: 0 } },
    { match: '/api/health', body: { status: 'ok', version: '1', comfy_online: true, comfy_url: 'x', active_jobs: 0, data_dir: 'd' } },
    { match: '/api/assets', body: [] },
    {
      match: '/api/validate',
      method: 'POST',
      body: { ok: true, issues: [], normalized: null, estimate_seconds: null, estimate_basis: null, continuity_plan: null },
    },
  ])
}

beforeEach(() => {
  resetStores()
  window.localStorage.clear()
})
afterEach(() => {
  vi.unstubAllGlobals()
  useLocale.setState({ locale: 'es' })
})

describe('EN/ES switch', () => {
  it('starts in Spanish and switches the whole interface to English, persistently', async () => {
    const user = userEvent.setup()
    const { calls } = stubStudio()
    renderWithProviders(<App />)

    const nav = await screen.findByRole('navigation', { name: 'Secciones' })
    const switcher = screen.getByRole('group', { name: 'Idioma de la interfaz' })
    expect(within(switcher).getByRole('button', { name: 'Español' })).toHaveAttribute('aria-pressed', 'true')
    expect(within(nav).getAllByRole('button').map((button) => button.textContent)).toEqual(['Crear', 'Escenario', 'Refs', 'Galería'])
    expect(screen.getByRole('radiogroup', { name: 'Tarea' })).toBeInTheDocument()

    useComposer.getState().setPrompt(PROMPT)
    await user.click(within(switcher).getByRole('button', { name: 'English' }))

    const navEn = screen.getByRole('navigation', { name: 'Sections' })
    expect(within(navEn).getAllByRole('button').map((button) => button.textContent)).toEqual(['Create', 'Stage', 'Refs', 'Gallery'])
    expect(screen.getByRole('group', { name: 'Interface language' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'English' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Open the interactive guide' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Advanced' })).toBeInTheDocument()
    expect(screen.queryByText('Avanzado')).not.toBeInTheDocument()
    expect(window.localStorage.getItem('h3studio.locale')).toBe('en')
    expect(document.documentElement.lang).toBe('en')

    // Creator content and identifiers are never translated.
    expect(useComposer.getState().prompt).toBe(PROMPT)
    expect(screen.getByDisplayValue(PROMPT)).toBeInTheDocument()
    expect(screen.getAllByText(RECIPE, { exact: false }).length).toBeGreaterThan(0)
    expect(useComposer.getState().presetId).toBe('character-swap-hd-turbo8')

    await user.click(screen.getByRole('button', { name: 'Español' }))
    expect(screen.getByRole('navigation', { name: 'Secciones' })).toBeInTheDocument()
    expect(window.localStorage.getItem('h3studio.locale')).toBe('es')
    // Switching language is local UI: it never reaches the API.
    expect(calls.filter((call) => call.method !== 'GET' && !call.url.includes('/api/validate'))).toEqual([])
  })

  it('opens directly in the stored language', async () => {
    useLocale.getState().setLocale('en')
    stubStudio()
    renderWithProviders(<App />)
    expect(await screen.findByRole('navigation', { name: 'Sections' })).toBeInTheDocument()
    expect(screen.getByRole('radiogroup', { name: 'Task' })).toBeInTheDocument()
  })

  it('runs the guided tour in English', async () => {
    const user = userEvent.setup()
    useLocale.getState().setLocale('en')
    stubStudio()
    renderWithProviders(<App />)
    await user.click(await screen.findByRole('button', { name: 'Open the interactive guide' }))
    const tour = await screen.findByRole('dialog')
    expect(within(tour).getByText(`Welcome to ${BRAND.product}`)).toBeInTheDocument()
    expect(within(tour).getByText(/Nothing is uploaded, generated or downloaded during the tour/)).toBeInTheDocument()
  })

  it.each([
    ['es', `${BRAND.product} no encuentra su backend`, 'Reintentar'],
    ['en', `${BRAND.product} can't find its backend`, 'Retry'],
  ] as const)('explains a missing backend in %s', async (locale, title, retry) => {
    useLocale.setState({ locale })
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    renderWithProviders(<App />)
    // useConfig retries once before giving up.
    expect(await screen.findByText(title, undefined, { timeout: 4000 })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: new RegExp(retry) })).toBeInTheDocument()
  })
})
