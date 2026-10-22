import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { makeJob } from '../../test/factories'
import { renderWithProviders, resetStores, stubFetch } from '../../test/utils'
import { OutputStage } from './OutputStage'

const { cancelTake } = vi.hoisted(() => ({ cancelTake: vi.fn() }))
vi.mock('../../hooks/useTakeActions', () => ({
  useTakeActions: () => ({
    cancelTake,
    reuseTake: vi.fn(),
    copyPrompt: vi.fn(),
    download: vi.fn(),
    toggleHidden: vi.fn(),
    deleteTake: vi.fn(),
    pending: { cancel: false, reuse: false, hidden: false, remove: false },
  }),
}))

beforeEach(() => {
  resetStores()
  cancelTake.mockReset()
  cancelTake.mockResolvedValue(undefined)
})
afterEach(() => vi.unstubAllGlobals())

const running = () =>
  makeJob({
    id: 'job-run',
    status: 'running',
    stage: 'Understanding references',
    progress: 0.42,
    started_at: new Date(Date.now() - 65_000).toISOString(),
    finished_at: null,
    duration_seconds: null,
    estimate_seconds: 80,
    outputs: [],
  })

it('shows the stage, its own percentage and total time separately, with an honest estimate', async () => {
  stubFetch([{ match: '/api/preview', status: 204 }])
  renderWithProviders(<OutputStage job={running()} loading={false} hasAnyTake />)

  expect(screen.getByText('Preparando referencias')).toBeInTheDocument()
  expect(screen.getByText('42% de esta etapa')).toBeInTheDocument()
  expect(screen.getByRole('progressbar', { name: /Progreso de la etapa: Preparando referencias/ })).toBeInTheDocument()
  expect(screen.getByText(/Tiempo total 1:0\d · referencia ≈ 1m 20s, no es un compromiso/)).toBeInTheDocument()
  const steps = screen.getByRole('list', { name: 'Etapas del render' })
  expect(within(steps).getByText('Preparando').closest('li')).toHaveAttribute('aria-current', 'step')
})

it('confirms before cancelling and only cancels on explicit consent', async () => {
  const user = userEvent.setup()
  stubFetch([{ match: '/api/preview', status: 204 }])
  const job = running()
  renderWithProviders(<OutputStage job={job} loading={false} hasAnyTake />)

  await user.click(screen.getByRole('button', { name: 'Cancelar toma' }))
  let dialog = await screen.findByRole('alertdialog', { name: '¿Cancelar esta toma?' })
  expect(within(dialog).getByText(/se detiene al terminar el paso en curso/i)).toBeInTheDocument()
  await user.click(within(dialog).getByRole('button', { name: 'Seguir generando' }))
  expect(cancelTake).not.toHaveBeenCalled()

  await user.click(screen.getByRole('button', { name: 'Cancelar toma' }))
  dialog = await screen.findByRole('alertdialog')
  await user.click(within(dialog).getByRole('button', { name: 'Cancelar toma' }))
  expect(cancelTake).toHaveBeenCalledWith(job)
})

it('says whether a canceled take was interrupted or never computed', async () => {
  stubFetch([
    {
      match: '/api/jobs/job-cx/events',
      body: { events: [{ id: 1, job_id: 'job-cx', level: 'info', message: 'Interrupted the running render.', created_at: '2026-10-21T10:00:00' }] },
    },
  ])
  renderWithProviders(
    <OutputStage job={makeJob({ id: 'job-cx', status: 'canceled', outputs: [] })} loading={false} hasAnyTake />,
  )
  expect(await screen.findByText(/Se pidió a ComfyUI que interrumpa el render/)).toBeInTheDocument()
  expect(screen.getByText('Toma cancelada')).toBeInTheDocument()
})
