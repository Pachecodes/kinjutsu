import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { Segmented } from './segmented'
import { renderWithProviders } from '../../test/utils'


describe('Segmented selected state', () => {
  it('renders an explicit high-contrast selected option independent of Radix data-state', () => {
    renderWithProviders(
      <Segmented
        label="Weights"
        value="erosmax_beta5"
        onValueChange={vi.fn()}
        options={[
          { value: 'int8', label: 'Default / OG' },
          { value: 'gguf', label: 'GGUF' },
          { value: 'erosmax_beta5', label: 'ErosMax Beta 5' },
        ]}
      />,
    )

    const selected = screen.getByRole('radio', { name: /erosmax beta 5/i })
    expect(selected).toHaveAttribute('aria-checked', 'true')
    expect(selected).toHaveAttribute('data-selected', 'true')
    expect(selected).toHaveClass('bg-accent', 'text-accent-ink')
    expect(selected.querySelector('[data-selection-check="true"]')).not.toBeNull()

    const unselected = screen.getByRole('radio', { name: /default \/ og/i })
    expect(unselected).toHaveAttribute('data-selected', 'false')
    expect(unselected).not.toHaveClass('bg-accent')
  })
})
