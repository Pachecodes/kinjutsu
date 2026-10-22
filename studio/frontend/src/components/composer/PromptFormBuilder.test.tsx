import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { useComposer } from '../../state/composer'
import { makeAsset, makeVideoAsset } from '../../test/factories'
// Snapshot of the packaged backend catalog, not an invented/reduced response shape.
import promptCatalog from '../../test/fixtures/promptCatalog.json'
import { renderWithProviders, resetStores, stubFetch } from '../../test/utils'
import { PromptBuilder } from './PromptBuilder'

const routes = (build: { status?: number; body: unknown }) => [
  { match: '/api/openapi.json', body: { paths: { '/api/prompting/catalog': {}, '/api/prompting/build': {} } } },
  {
    match: '/api/prompting/catalog',
    body: promptCatalog,
  },
  { match: '/api/prompting/build', method: 'POST', ...build },
]

beforeEach(() => {
  resetStores()
  useComposer.setState({
    mode: 'ref2va',
    presetId: 'character-swap-hd-turbo8',
    length: 124,
    prompt: 'body_swap: my current prompt <Picture 1>',
    references: [
      { uid: 'face', asset: makeAsset({ original_name: 'face.png' }), role: 'identity', include_audio: false },
      { uid: 'guide', asset: makeVideoAsset({ original_name: 'guide.mp4' }), role: 'aligned_guide', include_audio: false },
    ],
  })
})
afterEach(() => vi.unstubAllGlobals())

async function openAndFill(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('button', { name: 'Plantilla' }))
  const dialog = await screen.findByRole('dialog', { name: 'Plantilla H3 sin agente' })
  expect(await within(dialog).findByRole('radio', { name: /Character Swap · guía alineada/ })).toHaveAttribute('aria-checked', 'true')
  expect(within(dialog).getAllByRole('radio')).toHaveLength(6)
  expect(within(dialog).getByText('5,167 s')).toBeInTheDocument()
  await user.type(within(dialog).getByLabelText('<Picture 1> · identity'), 'Portrait of the performer')
  await user.type(within(dialog).getByLabelText('Guía alineada (sin token)'), 'Existing guide in a living room')
  return dialog
}

it('uses the backend form when served: preview, then an explicit Apply that only replaces the prompt', async () => {
  const user = userEvent.setup()
  const { calls } = stubFetch(routes({ body: { template: 'character-swap-aligned', prompt: 'body_swap: Rendered prompt.', requires_agent: false, submits_render: false } }))
  renderWithProviders(<PromptBuilder />)
  const dialog = await openAndFill(user)

  await user.click(within(dialog).getByRole('button', { name: 'Vista previa' }))
  expect(await within(dialog).findByText('body_swap: Rendered prompt.')).toBeInTheDocument()
  expect(useComposer.getState().prompt).toBe('body_swap: my current prompt <Picture 1>')

  const build = calls.find((call) => call.url.includes('/api/prompting/build'))
  expect(build?.body).toMatchObject({
    template: 'character-swap-aligned',
    input: {
      duration_seconds: 5.167,
      assets: [
        { kind: 'image', role: 'identity', token: '<Picture 1>', description: 'Portrait of the performer' },
        { kind: 'aligned_guide', role: 'aligned_guide', description: 'Existing guide in a living room' },
      ],
      audio: { music: 'N/A' },
      dialogue: [],
    },
  })
  expect((build?.body as { input: { assets: object[] } }).input.assets[1]).not.toHaveProperty('token')

  // Editing after the preview makes it stale until it is rebuilt.
  await user.type(within(dialog).getByLabelText('Identidad'), 'x')
  expect(within(dialog).getByRole('button', { name: 'Usar como prompt' })).toBeDisabled()
  await user.click(within(dialog).getByRole('button', { name: 'Vista previa' }))
  await user.click(await within(dialog).findByRole('button', { name: 'Usar como prompt' }))
  expect(useComposer.getState()).toMatchObject({ prompt: 'body_swap: Rendered prompt.', presetId: 'character-swap-hd-turbo8' })
  expect(calls.some((call) => call.url.includes('/api/jobs'))).toBe(false)
})

it('shows a readable 422 and leaves the prompt alone', async () => {
  const user = userEvent.setup()
  stubFetch(routes({ status: 422, body: { detail: 'identity: nonempty text required; describe it explicitly, do not infer from media' } }))
  renderWithProviders(<PromptBuilder />)
  const dialog = await openAndFill(user)
  await user.click(within(dialog).getByRole('button', { name: 'Vista previa' }))
  expect(await within(dialog).findByText(/identity: nonempty text required/)).toBeInTheDocument()
  expect(within(dialog).getByText(/Tu prompt actual no ha cambiado/)).toBeInTheDocument()
  expect(useComposer.getState().prompt).toBe('body_swap: my current prompt <Picture 1>')
})

it('explains, without calling the backend, when the attachments do not fit the template', async () => {
  const user = userEvent.setup()
  const { calls } = stubFetch(routes({ body: {} }))
  useComposer.setState({ references: [useComposer.getState().references[0]] })
  renderWithProviders(<PromptBuilder />)
  await user.click(await screen.findByRole('button', { name: 'Plantilla' }))
  const dialog = await screen.findByRole('dialog')
  expect(await within(dialog).findByText(/Necesita exactamente el retrato de identidad/, { selector: '[role=alert]' })).toBeInTheDocument()
  expect(within(dialog).getByRole('button', { name: 'Vista previa' })).toBeDisabled()
  expect(calls.some((call) => call.url.includes('/api/prompting/build'))).toBe(false)
})

it('falls back to the local template when the backend does not serve prompting', async () => {
  const user = userEvent.setup()
  stubFetch([{ match: '/api/openapi.json', body: { paths: {} } }])
  renderWithProviders(<PromptBuilder />)
  await user.click(await screen.findByRole('button', { name: 'Plantilla' }))
  expect(await screen.findByRole('dialog', { name: 'Plantilla de prompt' })).toBeInTheDocument()
})
