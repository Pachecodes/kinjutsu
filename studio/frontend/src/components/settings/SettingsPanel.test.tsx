import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import { SettingsPanel } from './SettingsPanel'
import { makeCapabilities } from '../../test/factories'
import { renderWithProviders, resetStores } from '../../test/utils'
import { useComposer } from '../../state/composer'


describe('automatic continuity controls', () => {
  beforeEach(() => resetStores())

  it('is enabled by default and lets the creator force a window size', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SettingsPanel capabilities={makeCapabilities()} />)

    // Continuity lives in a collapsed Advanced section.
    await user.click(screen.getByRole('button', { name: /^continuidad$/i }))
    const toggle = screen.getByRole('switch', { name: /continuidad automática/i })
    expect(toggle).toBeChecked()
    expect(screen.getByRole('combobox', { name: /ventana de continuidad/i })).toBeEnabled()
    await user.click(toggle)
    expect(useComposer.getState().continuity.auto_split).toBe(false)
    expect(screen.getByRole('combobox', { name: /ventana de continuidad/i })).toBeDisabled()
  })
})


describe('checkpoint controls', () => {
  beforeEach(() => resetStores())

  it('shows installed hybrid ErosMax Beta 5 in reference mode', async () => {
    const user = userEvent.setup()
    useComposer.getState().setMode('ref2va')
    const capabilities = makeCapabilities()
    capabilities.weights.erosmax_beta5 = true
    renderWithProviders(<SettingsPanel capabilities={capabilities} />)

    // The base-model section is open by default: it is the first thing Advanced explains.
    expect(screen.getByRole('button', { name: /^modelo base \(checkpoint\)$/i })).toHaveAttribute('aria-expanded', 'true')
    const beta5 = screen.getByRole('radio', { name: /erosmax beta 5/i })
    expect(beta5).toBeEnabled()
    await user.click(beta5)
    expect(screen.getByText(/checkpoint elegido: erosmax beta 5/i)).toBeVisible()
  })

  it('enables installed hybrid ErosMax Beta 5 in frame mode', () => {
    const capabilities = makeCapabilities()
    capabilities.weights.erosmax_beta5 = true
    renderWithProviders(<SettingsPanel capabilities={capabilities} />)

    expect(screen.getByRole('radio', { name: /erosmax beta 5/i })).toBeEnabled()
  })
})

describe('LoRA chain', () => {
  beforeEach(() => resetStores())

  it('keeps the chain order editable, since LoRAs apply in order', async () => {
    const user = userEvent.setup()
    const capabilities = makeCapabilities()
    capabilities.loras = [
      { name: 'turbo.safetensors', label: 'Turbo 8', recommended_strength: 1, checkpoint: 'any', note: null },
      { name: 'swap.safetensors', label: 'Character Swap', recommended_strength: 1, checkpoint: 'any', note: null },
    ]
    useComposer.setState({
      lora_chain: [
        { name: 'turbo.safetensors', strength: 1 },
        { name: 'swap.safetensors', strength: 0.8 },
      ],
    })
    renderWithProviders(<SettingsPanel capabilities={capabilities} />)

    expect(screen.getByRole('button', { name: 'Subir Turbo 8 en la cadena' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Bajar Turbo 8 en la cadena' }))
    expect(useComposer.getState().lora_chain).toEqual([
      { name: 'swap.safetensors', strength: 0.8 },
      { name: 'turbo.safetensors', strength: 1 },
    ])
  })
})
