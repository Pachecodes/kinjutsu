import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { RecipeList } from '../components/rail/RecipeRail'
import { ModelsButton } from '../components/models/ModelsDialog'
import { SettingsPanel } from '../components/settings/SettingsPanel'
import { ReferenceTray } from '../components/composer/ReferenceTray'
import { WorkstationButton } from '../components/workstation/WorkstationDialog'
import type { WorkstationStatus } from '../lib/types'
import { useComposer } from '../state/composer'
import { makeCapabilities, makeConfig, makePreset } from '../test/factories'
import { renderWithProviders, resetStores, stubFetch } from '../test/utils'
import { useLocale, type Locale } from './index'

/**
 * The same screens in both languages. Spanish copy is covered in depth by each
 * component's own spec; these check that every area switches, and that
 * identifiers, model names and backend messages pass through untouched.
 */

interface Copy {
  omniSetup: RegExp
  unavailable: RegExp
  omniAudio: RegExp
  checkpoint: RegExp
  sigmas: string
  continuity: RegExp
  autoContinuity: string
  installation: RegExp
  stopped: string
  start: string
  open: string
  models: RegExp
  checkNow: string
  verified: string
  missing: string
  install: RegExp
  consent: RegExp
  download: RegExp
  accept: RegExp
}

const COPY: Record<Locale, Copy> = {
  es: {
    omniSetup: /Instalar o configurar Omni/,
    unavailable: /No disponible: Omni engine offline/,
    omniAudio: /no es voz clonada/,
    checkpoint: /Checkpoint elegido: FastH3 Omni INT8/,
    sigmas: 'Sigmas manuales',
    continuity: /^Continuidad$/,
    autoContinuity: 'Continuidad automática',
    installation: /Instalación/,
    stopped: 'Motor detenido',
    start: 'Iniciar motor',
    open: 'Abrir ComfyUI',
    models: /Modelos/,
    checkNow: 'Comprobar ahora',
    verified: '1 de 2 verificados',
    missing: 'Falta',
    install: /Instalar/,
    consent: /Licencia y descarga de BFS Character Swap v1.1/,
    download: /Descargar 77 MB/,
    accept: /acepto/,
  },
  en: {
    omniSetup: /Install or set up Omni/,
    unavailable: /Unavailable: Omni engine offline/,
    omniAudio: /isn't a cloned voice/,
    checkpoint: /Selected checkpoint: FastH3 Omni INT8/,
    sigmas: 'Manual sigmas',
    continuity: /^Continuity$/,
    autoContinuity: 'Automatic continuity',
    installation: /Installation/,
    stopped: 'Engine stopped',
    start: 'Start engine',
    open: 'Open ComfyUI',
    models: /Models/,
    checkNow: 'Check now',
    verified: '1 of 2 verified',
    missing: 'Missing',
    install: /Install/,
    consent: /License and download for BFS Character Swap v1.1/,
    download: /Download 77 MB/,
    accept: /accept/,
  },
}

const LOCALES: Locale[] = ['es', 'en']

beforeEach(() => resetStores())
afterEach(() => {
  vi.unstubAllGlobals()
  useLocale.setState({ locale: 'es' })
})

describe.each(LOCALES)('Omni controls in %s', (locale) => {
  const copy = COPY[locale]
  beforeEach(() => {
    useLocale.setState({ locale })
    stubFetch([])
  })

  it('keeps the recipe label and backend reason verbatim and offers setup', async () => {
    const preset = makePreset({
      id: 'fasth3-omni-scenes',
      label: 'FastH3 Omni · Escenas',
      suggests_mode: 'ref2va',
      available: false,
      unavailable_reason: 'Omni engine offline.',
      patch: { width: 512, height: 640, length: 124, steps: 8, method: 'fast_h3_omni_8step' },
    })
    renderWithProviders(<RecipeList presets={[preset]} comfyOnline={false} />)
    expect(screen.getByRole('button', { name: /^FastH3 Omni · Escenas/ })).toBeDisabled()
    expect(screen.getByText(copy.unavailable)).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: copy.omniSetup }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('fasth3-omni')).toBeVisible()
    expect(within(dialog).getByText(locale === 'es' ? /22,2 GB/ : /22\.2 GB/)).toBeVisible()
  })

  it('explains Omni audio in the reference tray', () => {
    useComposer.getState().setMethod('fast_h3_omni_8step')
    renderWithProviders(<ReferenceTray />)
    expect(screen.getByText(copy.omniAudio)).toBeVisible()
  })

  it('locks the Omni core in the advanced settings', async () => {
    useComposer.getState().setMethod('fast_h3_omni_8step')
    renderWithProviders(<SettingsPanel capabilities={makeCapabilities()} />)
    expect(screen.getByText(copy.checkpoint)).toBeVisible()
    expect(screen.getByRole('textbox', { name: copy.sigmas })).toBeDisabled()
    expect(screen.getByRole('radio', { name: 'Heretic' })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: copy.continuity }))
    expect(screen.getByRole('switch', { name: copy.autoContinuity })).toBeDisabled()
  })
})

const workstation: WorkstationStatus = {
  state: 'stopped',
  selected_id: 'comfy_abc',
  label: 'Kinjutsu ComfyUI',
  url: 'http://127.0.0.1:8218',
  capabilities: { start: true, open_comfy: false, select: true, folders: { models: true, loras: true, outputs: false } },
  automatic_downloads: false,
  stop_supported: false,
  generation_binding: 'matches',
}

describe.each(LOCALES)('installation in %s', (locale) => {
  const copy = COPY[locale]

  it('reads the engine state without POSTing and keeps the installation label', async () => {
    useLocale.setState({ locale })
    const { calls } = stubFetch([
      {
        match: '/api/openapi.json',
        body: {
          paths: {
            '/api/workstation/status': {},
            '/api/workstation/discover': {},
            '/api/workstation/select': {},
            '/api/workstation/roots/select': {},
            '/api/workstation/comfy/start': {},
            '/api/workstation/comfy/open': {},
            '/api/workstation/folders/{kind}/open': {},
          },
        },
      },
      { match: '/api/config', body: makeConfig() },
      { match: '/api/workstation/status', body: workstation },
    ])
    renderWithProviders(<WorkstationButton />)
    await userEvent.click(await screen.findByRole('button', { name: copy.installation }))
    expect(await screen.findByText(copy.stopped)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: copy.start })).toBeEnabled()
    expect(screen.getByRole('button', { name: copy.open })).toBeDisabled()
    expect(screen.getAllByText(/Kinjutsu ComfyUI/).length).toBeGreaterThan(0)
    expect(calls.filter((call) => call.method === 'POST')).toEqual([])
  })
})

describe.each(LOCALES)('model manager in %s', (locale) => {
  const copy = COPY[locale]

  it('checks on request, asks for consent and shows the backend error verbatim', async () => {
    useLocale.setState({ locale })
    const user = userEvent.setup()
    const backendError = 'Espacio insuficiente: modelo pendiente mas 1 GiB de margen'
    const { calls } = stubFetch([
      {
        match: '/api/openapi.json',
        body: {
          paths: {
            '/api/models/catalog': {},
            '/api/models/status': {},
            '/api/models/{model_id}/install': {},
            '/api/models/{model_id}/cancel': {},
          },
        },
      },
      {
        match: '/api/models/catalog',
        body: {
          manifest_sha256: 'f'.repeat(64),
          license_documents: ['licenses/BFS-CHARACTER-SWAP-LICENSE.md'],
          models: [
            {
              id: '0',
              target: 'diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors',
              size: 20_970_379_616,
              sha256: 'a'.repeat(64),
              included: false,
              installed: true,
              verified: true,
              reused: false,
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
        },
      },
      { match: '/api/models/status', body: { downloads: [], restart_comfy_after_install: false } },
      { match: '/api/models/5/install', method: 'POST', status: 409, body: { detail: backendError } },
    ])
    renderWithProviders(<ModelsButton />)

    await user.click(await screen.findByRole('button', { name: copy.models }))
    await user.click(screen.getByRole('button', { name: copy.checkNow }))
    expect(await screen.findByText(copy.verified)).toBeInTheDocument()
    expect(screen.getByText(copy.missing)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: copy.install }))
    const consent = screen.getByRole('group', { name: copy.consent })
    expect(within(consent).getByText('licenses/BFS-CHARACTER-SWAP-LICENSE.md')).toBeInTheDocument()
    await user.click(within(consent).getByRole('checkbox', { name: copy.accept }))
    await user.click(within(consent).getByRole('button', { name: copy.download }))
    // Backend messages are shown as sent, never re-translated.
    expect(await screen.findByText(backendError)).toBeInTheDocument()
    expect(calls.find((call) => call.method === 'POST')).toMatchObject({ url: '/api/models/5/install' })
  })
})
