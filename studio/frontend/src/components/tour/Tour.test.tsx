import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { useUi } from '../../state/ui'
import { renderWithProviders, resetStores, stubFetch } from '../../test/utils'
import { TOUR_STEPS } from './steps'
import { Tour, TourOffer } from './Tour'

beforeEach(() => {
  resetStores()
  window.localStorage.clear()
})
afterEach(() => vi.unstubAllGlobals())

it('is offered once, walks forward and back, and Esc leaves it for good without touching the API', async () => {
  const user = userEvent.setup()
  const { calls } = stubFetch([])
  renderWithProviders(
    <>
      <TourOffer />
      <Tour />
    </>,
  )

  await user.click(screen.getByRole('button', { name: 'Empezar' }))
  expect(screen.getByRole('dialog', { name: TOUR_STEPS[0].title })).toHaveFocus()
  expect(screen.getByText(`Guía · paso 1 de ${TOUR_STEPS.length}`)).toBeInTheDocument()
  expect(screen.getByText(/no se sube, genera ni descarga nada/i)).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Siguiente' }))
  expect(screen.getByRole('dialog', { name: '1 · Elige una receta' })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /Anterior/ }))
  expect(screen.getByRole('dialog', { name: TOUR_STEPS[0].title })).toBeInTheDocument()

  await user.keyboard('{Escape}')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(window.localStorage.getItem('h3studio.tour.v1.done')).toBe('1')
  expect(screen.queryByRole('button', { name: 'Empezar' })).not.toBeInTheDocument()
  expect(calls).toEqual([])
})

it('can be repeated, keeps keyboard focus inside the card, and finishes on the last step', async () => {
  const user = userEvent.setup()
  useUi.setState({ tourDone: true })
  renderWithProviders(<Tour />)
  useUi.getState().openTour(TOUR_STEPS.length - 1)

  const dialog = await screen.findByRole('dialog', { name: TOUR_STEPS[TOUR_STEPS.length - 1].title })
  await user.tab()
  await user.tab()
  await user.tab()
  await user.tab()
  expect(dialog).toContainElement(document.activeElement as HTMLElement)

  await user.click(screen.getByRole('button', { name: 'Terminar' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(useUi.getState().tourStep).toBeNull()
})

it('exits from any step with the labelled close button', async () => {
  const user = userEvent.setup()
  renderWithProviders(<Tour />)
  useUi.getState().openTour(3)
  await user.click(await screen.findByRole('button', { name: 'Salir del recorrido' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(useUi.getState().tourDone).toBe(true)
})
