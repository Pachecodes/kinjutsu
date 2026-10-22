import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it } from 'vitest'

import { useComposer } from '../../state/composer'
import { makeAsset, makeVideoAsset } from '../../test/factories'
import { renderWithProviders, resetStores } from '../../test/utils'
import { GuideSync } from './GuideSync'

const guide = makeVideoAsset({
  id: 'guide-124',
  original_name: 'guia-736x1280-124f-pad.mp4',
  width: 736,
  height: 1280,
  duration_seconds: 124 / 24,
  has_audio: false,
  guide_provenance: { source_asset_id: 'src', fit: 'pad', start_seconds: 0, source_duration_seconds: 12 },
})

beforeEach(() => {
  resetStores()
  useComposer.setState({
    mode: 'ref2va',
    presetId: 'character-swap-hd-turbo8',
    width: 736,
    height: 1280,
    length: 243,
    references: [
      { uid: 'id', asset: makeAsset({ id: 'face' }), role: 'identity', include_audio: false },
      { uid: 'guide', asset: guide, role: 'aligned_guide', include_audio: false },
    ],
  })
})

it('explains a 243/124 mismatch and resolves it by following the guide', async () => {
  const user = userEvent.setup()
  renderWithProviders(<GuideSync />)

  expect(screen.getByText('La guía no coincide con la salida')).toBeInTheDocument()
  expect(screen.getByText('La salida pide 243 frames (10,13 s) pero la guía tiene 124 (5,17 s).')).toBeInTheDocument()
  expect(screen.getByText(/es un fragmento/)).toBeInTheDocument()
  // The other honest way out: a new guide at the requested length, from the original.
  expect(screen.getByRole('button', { name: 'Preparar guía de 10,13 s' })).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: /Ajustar salida a la guía · 124 f/ }))
  expect(useComposer.getState()).toMatchObject({ length: 124, width: 736, height: 1280 })
  expect(screen.getByText('Guía alineada con la salida')).toBeInTheDocument()
  // Identity and the rest of the take are untouched.
  expect(useComposer.getState().references.map((slot) => slot.asset.id)).toEqual(['face', 'guide-124'])
})

it('warns when the stored original cannot cover the requested duration', () => {
  useComposer.setState({ length: 413 })
  renderWithProviders(<GuideSync />)
  expect(screen.getByText(/El original no alcanza 17,21 s/)).toBeInTheDocument()
  expect(screen.getByText(/fuera de la ventana entrenada/)).toBeInTheDocument()
})

it('renders nothing without an aligned guide', () => {
  useComposer.setState({ references: [] })
  renderWithProviders(<GuideSync />)
  expect(screen.queryByRole('region', { name: 'Guía alineada' })).not.toBeInTheDocument()
})
