import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { renderWithProviders, resetStores, stubFetch } from '../../test/utils'
import { ModelsButton } from './ModelsDialog'

const OPENAPI = {
  paths: {
    '/api/models/catalog': {},
    '/api/models/status': {},
    '/api/models/{model_id}/install': {},
    '/api/models/{model_id}/cancel': {},
  },
}

const catalog = {
  manifest_sha256: 'f'.repeat(64),
  license_documents: ['licenses/MINIMAX-H3-LICENSE.txt', 'licenses/BFS-CHARACTER-SWAP-LICENSE.md'],
  models: [
    {
      id: '0',
      target: 'diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors',
      size: 20_970_379_616,
      sha256: 'a'.repeat(64),
      included: false,
      installed: true,
      verified: true,
      reused: true,
      revision: 'e5eb578a89295337b8ff433a035929ce0279e0b6',
      repo: 'Comfy-Org/MiniMax-H3',
    },
    {
      id: '5',
      target: 'loras/minimax_h3_character_swap_v1.1_ref2va_fro.safetensors',
      size: 80_673_112,
      sha256: 'b'.repeat(64),
      included: true,
      installed: false,
      verified: false,
      reused: false,
      revision: '37d7d8b302ec4168ff30467c900c588db253cad9',
      repo: 'Alissonerdx/Minimax-H3-ComfyUI',
    },
  ],
}

beforeEach(() => resetStores())
afterEach(() => vi.unstubAllGlobals())

it('does not offer a Models button when this backend has no model manager', async () => {
  const { calls } = stubFetch([{ match: '/api/openapi.json', body: { paths: { '/api/health': {} } } }])
  renderWithProviders(<ModelsButton />)
  await waitFor(() => expect(calls.some((call) => call.url.includes('openapi'))).toBe(true))
  expect(screen.queryByRole('button', { name: /Modelos/ })).not.toBeInTheDocument()
})

it('hashes only on request, asks for license consent, and reports a 409 in Spanish', async () => {
  const user = userEvent.setup()
  const { calls } = stubFetch([
    { match: '/api/openapi.json', body: OPENAPI },
    { match: '/api/models/catalog', body: catalog },
    { match: '/api/models/status', body: { downloads: [], restart_comfy_after_install: true } },
    { match: '/api/models/5/install', method: 'POST', status: 409, body: { detail: 'Espacio insuficiente: modelo pendiente mas 1 GiB de margen' } },
  ])
  renderWithProviders(<ModelsButton />)

  await user.click(await screen.findByRole('button', { name: /Modelos/ }))
  expect(screen.getByRole('button', { name: 'Comprobar ahora' })).toBeInTheDocument()
  expect(calls.some((call) => call.url.includes('/api/models/catalog'))).toBe(false)

  await user.click(screen.getByRole('button', { name: 'Comprobar ahora' }))
  expect(await screen.findByText('1 de 2 verificados')).toBeInTheDocument()
  expect(screen.getByText('Reutilizado (verificado)')).toBeInTheDocument()
  expect(screen.getByText('Falta')).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: /Instalar/ }))
  const consent = screen.getByRole('group', { name: /Licencia y descarga de BFS Character Swap v1.1/ })
  expect(within(consent).getByText('licenses/BFS-CHARACTER-SWAP-LICENSE.md')).toBeInTheDocument()
  const download = within(consent).getByRole('button', { name: /Descargar 77 MB/ })
  expect(download).toBeDisabled()
  expect(calls.some((call) => call.method === 'POST')).toBe(false)

  await user.click(within(consent).getByRole('checkbox', { name: /acepto/ }))
  await user.click(download)
  expect(await screen.findByText('Espacio insuficiente: modelo pendiente mas 1 GiB de margen')).toBeInTheDocument()
  expect(calls.find((call) => call.method === 'POST')).toMatchObject({
    url: '/api/models/5/install',
    body: { license_acknowledged: true },
  })
})

it('shows real progress, lets the creator cancel, and warns to restart Comfy after an install', async () => {
  const user = userEvent.setup()
  const { calls } = stubFetch([
    { match: '/api/openapi.json', body: OPENAPI },
    { match: '/api/models/catalog', body: catalog },
    {
      match: '/api/models/status',
      body: {
        downloads: [
          { id: '5', status: 'downloading', bytes: 40_000_000, total: 80_673_112, error: null },
          { id: '9', status: 'installed', bytes: 1, total: 1, error: null },
        ],
        restart_comfy_after_install: true,
      },
    },
    { match: '/api/models/5/cancel', method: 'POST', body: { id: '5', cancel_requested: true } },
  ])
  renderWithProviders(<ModelsButton />)
  await user.click(await screen.findByRole('button', { name: /Modelos/ }))
  expect(await screen.findByText(/Reinicia Comfy con DETENER\/INICIAR/)).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Comprobar ahora' }))

  expect(await screen.findByRole('progressbar', { name: 'Descarga de BFS Character Swap v1.1' })).toBeInTheDocument()
  expect(screen.getByText('38 MB de 77 MB')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Cancelar descarga' }))
  expect(await screen.findByText('Cancelación solicitada')).toBeInTheDocument()
  expect(screen.getByText(/puede tardar hasta 30 s/)).toBeInTheDocument()
  expect(calls.some((call) => call.method === 'POST' && call.url === '/api/models/5/cancel')).toBe(true)
})
