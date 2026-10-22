import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useComposer } from '../../state/composer'
import { makeCapabilities, makeConfig, makeJob, makeValidation } from '../../test/factories'
import { renderWithProviders, resetStores, stubFetch } from '../../test/utils'
import { Composer } from './Composer'

const config = makeConfig()
const capabilities = makeCapabilities()

function renderComposer() {
  return renderWithProviders(<Composer config={config} capabilities={capabilities} />)
}

describe('Generate', () => {
  beforeEach(() => resetStores())
  afterEach(() => vi.unstubAllGlobals())

  it('says why it is blocked, right beside the action', () => {
    stubFetch([])
    renderComposer()
    expect(screen.getByRole('button', { name: /Generar toma/ })).toBeDisabled()
    expect(screen.getByText('Escribe un prompt primero.')).toBeInTheDocument()
  })

  it('blocks on a validation error with a plain sentence and offers the one-click fix', async () => {
    const user = userEvent.setup()
    stubFetch([
      {
        match: '/api/validate',
        method: 'POST',
        body: makeValidation({
          ok: false,
          issues: [
            {
              code: 'guide_continuity',
              message: 'Disable auto continuity for an aligned full-clip guide.',
              severity: 'error',
              field: 'continuity',
            },
          ],
        }),
      },
    ])
    useComposer.setState({ prompt: 'A lighthouse at dusk.' })
    renderComposer()

    const fix = await screen.findByRole('button', { name: /Apagar continuidad/ }, { timeout: 3000 })
    // Headline in plain words, backend message kept verbatim underneath.
    expect(screen.getAllByText('Una guía alineada necesita la continuidad automática apagada.').length).toBeGreaterThan(0)
    expect(screen.getByText('Disable auto continuity for an aligned full-clip guide.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Generar toma/ })).toBeDisabled()

    await user.click(fix)
    expect(useComposer.getState().continuity.auto_split).toBe(false)
  })

  it('shows busy, then queues exactly the composed request and confirms', async () => {
    const user = userEvent.setup()
    let release: (value: Response) => void = () => {}
    const posts: unknown[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url.includes('/api/validate')) {
          return new Response(JSON.stringify(makeValidation({ estimate_seconds: 62.3 })), { status: 200 })
        }
        if (url.endsWith('/api/jobs') && init?.method === 'POST') {
          posts.push(JSON.parse(String(init.body)))
          return new Promise<Response>((resolve) => {
            release = resolve
          })
        }
        return new Response(JSON.stringify({ detail: 'not stubbed' }), { status: 404 })
      }),
    )
    useComposer.setState({ prompt: 'A lighthouse at dusk.', title: 'Faro' })
    renderComposer()

    const generate = await screen.findByRole('button', { name: /Generar toma, unos 1m 2s estimados/ }, { timeout: 3000 })
    await user.click(generate)
    expect(await screen.findByRole('button', { name: 'Enviando la toma' })).toBeDisabled()
    expect(posts).toHaveLength(1)
    expect(posts[0]).toMatchObject({ prompt: 'A lighthouse at dusk.', title: 'Faro', mode: 'text' })

    release(new Response(JSON.stringify({ job: makeJob({ status: 'queued', title: 'Faro' }) }), { status: 201 }))
    expect(await screen.findByText('Toma en cola')).toBeInTheDocument()
  })

  it('keeps the take and explains when the backend refuses it', async () => {
    const user = userEvent.setup()
    stubFetch([
      { match: '/api/validate', method: 'POST', body: makeValidation() },
      { match: '/api/jobs', method: 'POST', status: 409, body: { detail: 'Another H3 render owns the GPU.' } },
    ])
    useComposer.setState({ prompt: 'A lighthouse at dusk.' })
    renderComposer()

    await waitFor(() => expect(screen.getByRole('button', { name: /Generar toma/ })).toBeEnabled(), { timeout: 3000 })
    await user.click(screen.getByRole('button', { name: /Generar toma/ }))
    expect(await screen.findByText('No se pudo poner en cola')).toBeInTheDocument()
    expect(screen.getAllByText('Another H3 render owns the GPU.').length).toBeGreaterThan(0)
    expect(useComposer.getState().prompt).toBe('A lighthouse at dusk.')
  })
})
