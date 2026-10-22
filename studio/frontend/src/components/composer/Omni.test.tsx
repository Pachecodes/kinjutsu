import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi, afterEach } from 'vitest'
import { RecipeList } from '../rail/RecipeRail'
import { SettingsPanel } from '../settings/SettingsPanel'
import { MethodPicker } from './MethodPicker'
import { ReferenceTray } from './ReferenceTray'
import { makeCapabilities, makePreset } from '../../test/factories'
import { renderWithProviders, resetStores, stubFetch } from '../../test/utils'
import { useComposer } from '../../state/composer'

const preset = makePreset({ id: 'fasth3-omni-scenes', label: 'FastH3 Omni · Escenas', suggests_mode: 'ref2va', available: false, unavailable_reason: 'Omni engine offline.', patch: { width: 512, height: 640, length: 124, steps: 8, method: 'fast_h3_omni_8step' } })
beforeEach(() => { resetStores(); stubFetch([]) })
afterEach(() => vi.unstubAllGlobals())
it('keeps a missing Omni recipe honestly unavailable even when the other engine is offline, with an explicit setup route', async () => {
  renderWithProviders(<RecipeList presets={[preset]} comfyOnline={false} />)
  expect(screen.getByRole('button', { name: /^FastH3 Omni · Escenas/ })).toBeDisabled()
  expect(screen.getByText(/No disponible: Omni engine offline/)).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: /Instalar o configurar Omni/ }))
  const dialog = await screen.findByRole('dialog')
  expect(within(dialog).getByText('fasth3-omni')).toBeVisible()
  expect(within(dialog).getByText(/22,2 GB/)).toBeVisible()
})
it('shows honest scene measurements and no mandatory video-guide slot', () => {
  useComposer.getState().setMethod('fast_h3_omni_8step')
  renderWithProviders(<ReferenceTray />)
  expect(screen.queryByRole('button', { name: /Subir vídeo guía/ })).not.toBeInTheDocument()
  expect(screen.getByText(/86–123 s/)).toBeVisible()
  expect(screen.getByText(/no es voz clonada/)).toBeVisible()
})
it('locks the Omni core in advanced controls and names its own checkpoint', async () => {
  useComposer.getState().setMethod('fast_h3_omni_8step')
  renderWithProviders(<SettingsPanel capabilities={makeCapabilities()} />)
  expect(screen.getByText(/Checkpoint elegido: FastH3 Omni INT8/)).toBeVisible()
  expect(screen.getByRole('slider')).toHaveAttribute('data-disabled')
  expect(screen.getByRole('textbox', { name: 'Sigmas manuales' })).toBeDisabled()
  expect(screen.getByRole('radio', { name: 'Heretic' })).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: /^Continuidad$/ }))
  expect(screen.getByRole('switch', { name: 'Continuidad automática' })).toBeDisabled()
})
it('does not infer Omni availability from the primary engine offline state', () => {
  const method = { ...makeCapabilities().methods[0], id: 'fast_h3_omni_8step' as const, label: 'Omni', available: false }
  useComposer.getState().setMode('ref2va')
  renderWithProviders(<MethodPicker methods={[method]} comfyOnline={false} />)
  expect(screen.getByRole('radio', { name: /Omni/ })).toBeDisabled()
})
