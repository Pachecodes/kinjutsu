import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it } from 'vitest'
import { SettingsPanel } from './SettingsPanel'
import { makeCapabilities } from '../../test/factories'
import { renderWithProviders, resetStores } from '../../test/utils'
import { useComposer } from '../../state/composer'
beforeEach(() => resetStores())
it('shows 10Eros identity and editable manual sigmas', async () => {
  const user = userEvent.setup()
  const caps = makeCapabilities()
  caps.weights.erosmax_beta5 = true
  renderWithProviders(<SettingsPanel capabilities={caps} />)
  expect(screen.getByRole('radio', {name: /10eros-max/i})).toBeEnabled()
  const field = screen.getByRole('textbox', {name: /sigmas manuales/i})
  await user.type(field, '1, 0.94, 0.83, 0.72, 0.55, 0.30, 0.10, 0')
  await user.tab()
  expect(useComposer.getState().custom_sigmas).toEqual([1,.94,.83,.72,.55,.30,.10,0])
})
it('reports offline checkpoint discovery rather than missing weights', () => {
  const caps = makeCapabilities()
  caps.comfy_online = false
  caps.weights.erosmax_beta5 = false
  renderWithProviders(<SettingsPanel capabilities={caps} />)
  expect(screen.getByText(/disponibilidad de checkpoints desconocida.*desconectado/i)).toBeVisible()
})
