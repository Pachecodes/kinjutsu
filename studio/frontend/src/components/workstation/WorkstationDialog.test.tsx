import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { BINDING_COPY, STATE_COPY, generatesHere, isLocalContext } from '../../lib/workstation'
import type { WorkstationStatus } from '../../lib/types'
import { makeConfig } from '../../test/factories'
import { renderWithProviders, resetStores, stubFetch, type RouteStub } from '../../test/utils'
import { WorkstationButton, WorkstationPanel } from './WorkstationDialog'

const status = (overrides: Partial<WorkstationStatus> = {}): WorkstationStatus => ({
  state: 'stopped',
  selected_id: 'comfy_abc',
  label: 'Kinjutsu ComfyUI',
  url: 'http://127.0.0.1:8218',
  capabilities: { start: true, open_comfy: false, select: true, folders: { models: true, loras: true, outputs: false } },
  automatic_downloads: false,
  stop_supported: false,
  generation_binding: 'matches',
  ...overrides,
})

const OPENAPI_PATHS = {
  '/api/workstation/status': {},
  '/api/workstation/discover': {},
  '/api/workstation/select': {},
  '/api/workstation/roots/select': {},
  '/api/workstation/comfy/start': {},
  '/api/workstation/comfy/open': {},
  '/api/workstation/folders/{kind}/open': {},
}

function routes(extra: RouteStub[] = []): RouteStub[] {
  return [
    ...extra,
    { match: '/api/openapi.json', body: { paths: OPENAPI_PATHS } },
    { match: '/api/config', body: makeConfig() },
    { match: '/api/workstation/status', body: status() },
  ]
}

const posts = (calls: { method: string; url: string }[]) => calls.filter((call) => call.method === 'POST')

beforeEach(() => resetStores())
afterEach(() => vi.unstubAllGlobals())

describe('workstation copy', () => {
  it('only treats loopback hosts as local', () => {
    expect(isLocalContext('localhost')).toBe(true)
    expect(isLocalContext('127.0.0.1')).toBe(true)
    expect(isLocalContext('studio.example.ts.net')).toBe(false)
  })

  it('never offers a kill or restart for blocked states', () => {
    for (const state of ['port_conflict', 'configuration_changed', 'launch_unverified', 'unhealthy'] as const) {
      expect(STATE_COPY[state].next).not.toMatch(/reinicia el motor|mata|kill/i)
    }
    expect(STATE_COPY.port_conflict.next).toMatch(/No se arranca, adopta ni detiene nada/)
    expect(BINDING_COPY.different.text).toMatch(/no redirige/)
  })

  it('claims Studio generates here only when binding matches and the engine is up', () => {
    expect(generatesHere(status({ state: 'online' }), true)).toBe(true)
    expect(generatesHere(status({ state: 'online' }), false)).toBe(false)
    expect(generatesHere(status({ state: 'online', generation_binding: 'different' }), true)).toBe(false)
    expect(generatesHere(status({ state: 'stopped' }), true)).toBe(false)
  })
})

describe('workstation panel', () => {
  it('hides the entry point when the backend has no workstation routes', async () => {
    const { calls } = stubFetch([{ match: '/api/openapi.json', body: { paths: {} } }])
    renderWithProviders(<WorkstationButton />)
    await waitFor(() => expect(calls.some((call) => call.url.includes('openapi'))).toBe(true))
    expect(screen.queryByRole('button', { name: /Instalación/ })).not.toBeInTheDocument()
  })

  it('reads status on open, separates Start from Open, and never POSTs by itself', async () => {
    const { calls } = stubFetch(routes())
    renderWithProviders(<WorkstationButton />)
    await userEvent.setup().click(await screen.findByRole('button', { name: /Instalación/ }))

    expect(await screen.findByText('Motor detenido')).toBeInTheDocument()
    expect(screen.getByText(/configurado para generar con esta misma instalación/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Iniciar motor' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Abrir ComfyUI' })).toBeDisabled()
    expect(screen.getByText(/No arranca el motor: debe estar en línea/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Modelos' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Resultados' })).toBeDisabled()
    expect(screen.queryByRole('button', { name: /Detener|Reiniciar/ })).not.toBeInTheDocument()
    // Discovery is explicit, and nothing is ever POSTed on load.
    expect(calls.some((call) => call.url.includes('/discover'))).toBe(false)
    expect(posts(calls)).toEqual([])
  })

  it('reports a requested start as starting, not ready, and polls status (GET) until online', async () => {
    const user = userEvent.setup()
    let current = status()
    const { calls } = stubFetch([
      { match: '/api/workstation/comfy/start', method: 'POST', body: { state: 'starting', reused: false, log: 'runtime/logs/workstation-comfy.log' } },
      { match: '/api/openapi.json', body: { paths: OPENAPI_PATHS } },
      { match: '/api/config', body: makeConfig() },
    ])
    // Status follows the backend: starting after the request, then online.
    const fetchImpl = vi.mocked(globalThis.fetch)
    const original = fetchImpl.getMockImplementation()!
    fetchImpl.mockImplementation(async (input, init) => {
      if (String(input).includes('/api/workstation/status')) {
        calls.push({ url: String(input), method: 'GET', body: null })
        return new Response(JSON.stringify(current), { status: 200 })
      }
      return original(input, init)
    })
    renderWithProviders(<WorkstationPanel />)

    const startButton = await screen.findByRole('button', { name: 'Iniciar motor' })
    current = status({ state: 'starting', capabilities: { ...status().capabilities, start: false } })
    await user.click(startButton)
    expect(await screen.findByText(/Arrancado aún no es listo/)).toBeInTheDocument()
    expect(await screen.findByText('Motor arrancando')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Iniciar motor' })).toBeDisabled()

    current = status({ state: 'online', capabilities: { ...status().capabilities, start: false, open_comfy: true } })
    expect(await screen.findByText('Motor en línea', {}, { timeout: 4000 })).toBeInTheDocument()
    expect(posts(calls).map((call) => call.url)).toEqual(['/api/workstation/comfy/start'])
  })

  it('explains a foreign port without offering any recovery action', async () => {
    stubFetch(routes([{ match: '/api/workstation/status', body: status({ state: 'port_conflict', capabilities: { start: false, open_comfy: false, select: true, folders: { models: false, loras: false, outputs: false } } }) }]))
    renderWithProviders(<WorkstationPanel />)
    expect(await screen.findByText('Puerto ocupado por otro programa')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Iniciar motor' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Abrir ComfyUI' })).toBeDisabled()
  })

  it('discovers on request, keeps detected apart from approved, and selects only with consent', async () => {
    const user = userEvent.setup()
    const { calls } = stubFetch(
      routes([
        {
          match: '/api/workstation/discover',
          body: {
            runtimes: [
              { id: 'comfy_abc', label: 'Kinjutsu ComfyUI', location: 'C:/K/runtime/ComfyUI', online: true, approved: true, configuration_required: false },
              { id: 'comfy_new', label: 'Shared ComfyUI', location: 'D:/Shared/ComfyUI', online: false, approved: true, configuration_required: false },
              { id: 'comfy_foreign', label: 'ComfyUI', location: 'E:/Otros/ComfyUI', online: true, approved: false, configuration_required: true },
            ],
            roots: [],
            limits: { max_roots: 64, max_depth: 0, max_results: 128, budget_seconds: 2 },
            automatic_downloads: false,
          },
        },
        { match: '/api/workstation/select', method: 'POST', body: { selected_id: 'comfy_new', selected: true, generation_routing_changed: false } },
      ]),
    )
    renderWithProviders(<WorkstationPanel />)
    await user.click(await screen.findByRole('button', { name: 'Buscar instalaciones' }))
    const list = await screen.findByRole('list', { name: 'Instalaciones encontradas' })

    const foreign = within(list).getByText('E:/Otros/ComfyUI').closest('li')!
    expect(within(foreign).getByText('Solo detectada')).toBeInTheDocument()
    expect(within(foreign).queryByRole('button', { name: /Usar esta instalación/ })).not.toBeInTheDocument()
    expect(within(list).getByText('Kinjutsu ComfyUI').closest('li')!).toHaveTextContent('Elegida')

    const shared = within(list).getByText('Shared ComfyUI').closest('li')!
    await user.click(within(shared).getByRole('button', { name: 'Usar esta instalación…' }))
    const consent = within(shared).getByRole('group', { name: 'Usar Shared ComfyUI' })
    expect(within(consent).getByText(/no copia ni mueve modelos/)).toBeInTheDocument()
    const confirm = within(consent).getByRole('button', { name: 'Usar esta instalación' })
    expect(confirm).toBeDisabled()
    expect(posts(calls)).toEqual([])
    await user.click(within(consent).getByRole('checkbox'))
    await user.click(confirm)
    expect(await within(shared).findByText(/La generación no se ha redirigido/)).toBeInTheDocument()
    expect(posts(calls)[0]).toMatchObject({ url: '/api/workstation/select', body: { candidate_id: 'comfy_new', acknowledge: true } })
  })

  it('verifies a shared model root with consent, blocks double submit and reports reuse without copying', async () => {
    const user = userEvent.setup()
    let release: (value: Response) => void = () => {}
    const { calls } = stubFetch(
      routes([
        {
          match: '/api/workstation/discover',
          body: {
            runtimes: [],
            roots: [
              { id: 'root_shared', label: 'models', location: 'D:/Shared/models', approved: true, runtime_id: 'comfy_abc' },
              { id: 'root_auth', label: 'vae', location: 'X:/vae', approved: true, runtime_id: null },
            ],
            limits: { max_roots: 64, max_depth: 0, max_results: 128, budget_seconds: 2 },
            automatic_downloads: false,
          },
        },
      ]),
    )
    const fetchImpl = vi.mocked(globalThis.fetch)
    const original = fetchImpl.getMockImplementation()!
    fetchImpl.mockImplementation(async (input, init) => {
      if (String(input).includes('/roots/select')) {
        calls.push({ url: String(input), method: 'POST', body: JSON.parse(String(init?.body)) })
        return new Promise<Response>((resolve) => {
          release = resolve
        })
      }
      return original(input, init)
    })
    renderWithProviders(<WorkstationPanel />)
    await user.click(await screen.findByRole('button', { name: 'Buscar instalaciones' }))
    const roots = await screen.findByRole('list', { name: 'Carpetas de modelos encontradas' })
    expect(within(roots).getByText('Ya autorizada para Modelos')).toBeInTheDocument()

    const shared = within(roots).getByText('D:/Shared/models').closest('li')!
    await user.click(within(shared).getByRole('button', { name: /Verificar y reutilizar/ }))
    await user.click(within(shared).getByRole('checkbox'))
    await user.click(within(shared).getByRole('button', { name: 'Verificar y reutilizar' }))
    expect(await within(shared).findByText(/Verificando SHA256… puede tardar varios minutos/)).toBeInTheDocument()
    expect(within(shared).getByRole('button', { name: /Verificar y reutilizar/ })).toBeDisabled()

    release(new Response(JSON.stringify({ root_id: 'root_shared', verified_models: 4, reused: true, external_comfy_mapping_changed: false, restart_required: true }), { status: 200 }))
    expect(await within(shared).findByText(/4 modelos verificados por SHA256 y reutilizados sin copiar/)).toBeInTheDocument()
    expect(within(shared).getByText(/Reinicia Comfy/)).toBeInTheDocument()
    expect(posts(calls).filter((call) => call.url.includes('/roots/select'))).toHaveLength(1)
  })

  it('opens folders only via the allowlisted kinds and says where they open', async () => {
    const user = userEvent.setup()
    const { calls } = stubFetch(routes([{ match: '/api/workstation/folders/loras/open', method: 'POST', body: { kind: 'loras', requested: true } }]))
    renderWithProviders(<WorkstationPanel />)
    await user.click(await screen.findByRole('button', { name: 'LoRAs' }))
    expect(await screen.findByText('Se abre en el Explorador del equipo servidor.')).toBeInTheDocument()
    expect(posts(calls)).toEqual([{ url: '/api/workstation/folders/loras/open', method: 'POST', body: {} }])
  })

  it('explains, without calling any workstation route, when opened remotely', async () => {
    const { calls } = stubFetch(routes())
    renderWithProviders(<WorkstationPanel local={false} />)
    expect(screen.getByText('Solo desde el propio equipo')).toBeInTheDocument()
    expect(screen.getByText(/en el Windows del servidor/)).toBeInTheDocument()
    expect(calls.some((call) => call.url.includes('/api/workstation'))).toBe(false)
  })

  it('treats a 403 from the backend as a non-local context', async () => {
    stubFetch(routes([{ match: '/api/workstation/status', status: 403, body: { detail: 'Non-local Host rejected' } }]))
    renderWithProviders(<WorkstationPanel />)
    expect(await screen.findByText('Solo desde el propio equipo')).toBeInTheDocument()
  })
})
