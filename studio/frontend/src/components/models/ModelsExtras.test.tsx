import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { fitsOnDisk, partialInfo } from '../../lib/models'
import type { ManagedModel } from '../../lib/types'
import { renderWithProviders, resetStores, stubFetch } from '../../test/utils'
import { ModelsButton } from './ModelsDialog'

const GIB = 1024 ** 3

const row = (overrides: Partial<ManagedModel>): ManagedModel => ({
  id: '0',
  target: 'loras/minimax_h3_character_swap_v1.1_ref2va_fro.safetensors',
  size: 2 * GIB,
  sha256: 'a'.repeat(64),
  included: false,
  installed: false,
  verified: false,
  reused: false,
  revision: 'b'.repeat(40),
  repo: 'Alissonerdx/Minimax-H3-ComfyUI',
  label: 'BFS Character Swap v1.1',
  role: 'task_lora',
  required_by: ['character-swap-hd-turbo8'],
  partial_bytes: 0,
  partial_valid_size: true,
  ...overrides,
})

const OPENAPI = {
  paths: {
    '/api/models/catalog': {},
    '/api/models/status': {},
    '/api/models/{model_id}/install': {},
    '/api/models/{model_id}/cancel': {},
    '/api/models/licenses/{name}': {},
  },
}

function render(models: ManagedModel[], freeBytes: number) {
  const stub = stubFetch([
    { match: '/api/openapi.json', body: OPENAPI },
    {
      match: '/api/models/catalog',
      body: { manifest_sha256: 'x', models, free_bytes: freeBytes, license_documents: ['licenses/BFS-CHARACTER-SWAP-LICENSE.md'] },
    },
    { match: '/api/models/status', body: { downloads: [], restart_comfy_after_install: true } },
  ])
  renderWithProviders(<ModelsButton />)
  return stub
}

beforeEach(() => resetStores())
afterEach(() => vi.unstubAllGlobals())

it('computes disk fit and partials from the catalog extras', () => {
  expect(fitsOnDisk(row({}), 10 * GIB)).toBe(true)
  expect(fitsOnDisk(row({}), 2.5 * GIB)).toBe(false)
  // A valid partial only needs the remainder plus the margin.
  expect(fitsOnDisk(row({ partial_bytes: 1.8 * GIB }), 1.3 * GIB)).toBe(true)
  expect(fitsOnDisk(row({}), undefined)).toBeNull()
  expect(partialInfo(row({ partial_bytes: GIB }))).toEqual({ bytes: GIB, valid: true })
  expect(partialInfo(row({ partial_bytes: 3 * GIB, partial_valid_size: false }))).toEqual({ bytes: 3 * GIB, valid: false })
  expect(partialInfo(row({ verified: true, partial_bytes: GIB }))).toBeNull()
})

it('shows free disk (not VRAM), the backend label and the recipes that need a model', async () => {
  const user = userEvent.setup()
  render([row({})], 50 * GIB)
  await user.click(await screen.findByRole('button', { name: /Modelos/ }))
  await user.click(screen.getByRole('button', { name: 'Comprobar ahora' }))
  expect(await screen.findByText(/libres en disco \(no VRAM\)/)).toBeInTheDocument()
  expect(screen.getByText('BFS Character Swap v1.1')).toBeInTheDocument()
  expect(screen.getByText('Lo usa:').parentElement).toHaveTextContent('character-swap-hd-turbo8')
})

it('blocks a download that would not fit on disk, and offers to resume a valid partial', async () => {
  const user = userEvent.setup()
  render(
    [
      row({ id: '0', label: 'Too big', size: 40 * GIB }),
      row({ id: '1', label: 'Half done', target: 'vae/x.safetensors', partial_bytes: GIB }),
      row({ id: '2', label: 'Bad partial', target: 'vae/y.safetensors', partial_bytes: 5 * GIB, partial_valid_size: false }),
    ],
    4 * GIB,
  )
  await user.click(await screen.findByRole('button', { name: /Modelos/ }))
  await user.click(screen.getByRole('button', { name: 'Comprobar ahora' }))

  const big = (await screen.findByText('Too big')).closest('li')!
  expect(within(big).getByText(/No cabe en el disco/)).toBeInTheDocument()
  expect(within(big).queryByRole('button', { name: /Instalar|Reanudar/ })).not.toBeInTheDocument()

  const half = screen.getByText('Half done').closest('li')!
  expect(within(half).getByText(/Hay una descarga parcial guardada: 1,00 GB de 2,00 GB/)).toBeInTheDocument()
  expect(within(half).getByRole('button', { name: 'Reanudar…' })).toBeInTheDocument()

  const bad = screen.getByText('Bad partial').closest('li')!
  expect(within(bad).getByText(/mayor que el tamaño fijado/)).toBeInTheDocument()
  expect(within(bad).queryByRole('button', { name: /Instalar|Reanudar/ })).not.toBeInTheDocument()
})

it('reads a license as escaped plain text before consenting', async () => {
  const user = userEvent.setup()
  const { calls } = render([row({})], 50 * GIB)
  const fetchImpl = vi.mocked(globalThis.fetch)
  const original = fetchImpl.getMockImplementation()!
  fetchImpl.mockImplementation(async (input, init) => {
    if (String(input).includes('/api/models/licenses/')) {
      calls.push({ url: String(input), method: 'GET', body: null })
      return new Response('BFS terms <script>alert(1)</script>\nNo hosted service.', { status: 200, headers: { 'Content-Type': 'text/plain' } })
    }
    return original(input, init)
  })
  await user.click(await screen.findByRole('button', { name: /Modelos/ }))
  await user.click(screen.getByRole('button', { name: 'Comprobar ahora' }))
  await user.click(await screen.findByRole('button', { name: 'Instalar…' }))
  await user.click(screen.getByRole('button', { name: 'Leer BFS-CHARACTER-SWAP-LICENSE.md' }))

  const text = await screen.findByLabelText('Texto de BFS-CHARACTER-SWAP-LICENSE.md')
  expect(text.textContent).toContain('<script>alert(1)</script>')
  expect(text.querySelector('script')).toBeNull()
  expect(calls.find((call) => call.url.includes('/licenses/'))?.url).toBe('/api/models/licenses/BFS-CHARACTER-SWAP-LICENSE.md')
  expect(calls.some((call) => call.method === 'POST')).toBe(false)
})
