import { screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'

import type { JobOut } from '../../lib/types'
import { renderWithProviders } from '../../test/utils'
import { OutputStage } from './OutputStage'

vi.mock('../../hooks/useTakeActions', () => ({
  useTakeActions: () => ({ cancelTake: vi.fn(), pending: { cancel: false } }),
}))

const runningJob = {
  id: 'job-1',
  status: 'running',
  mode: 'text',
  method: 'baseline',
  title: 'Preview take',
  prompt: 'x',
  width: 352,
  height: 640,
  length: 124,
  seed: 7,
  steps: 20,
  progress: 0.2,
  stage: 'Rendering',
  queue_position: 0,
  error: null,
  hidden: false,
  created_at: new Date().toISOString(),
  started_at: new Date().toISOString(),
  finished_at: null,
  duration_seconds: null,
  estimate_seconds: 100,
  comfy_prompt_id: 'p1',
  outputs: [],
  request: {} as JobOut['request'],
} as JobOut

test('shows the latest live tiny-VAE preview while a take is running', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ data_url: 'data:image/jpeg;base64,YWJj', width: 352, height: 640, step: 3, total: 20 }),
  }))
  renderWithProviders(<OutputStage job={runningJob} loading={false} hasAnyTake />)
  const image = await screen.findByRole('img', { name: /vista previa en vivo/i })
  expect(image).toHaveAttribute('src', 'data:image/jpeg;base64,YWJj')
  expect(screen.getByRole('region', { name: /escenario/i }).firstElementChild).toHaveClass(
    'h-[clamp(15rem,44dvh,34rem)]',
  )
  await waitFor(() => expect(screen.getByText(/Paso 3 \/ 20/)).toBeInTheDocument())
  vi.unstubAllGlobals()
})
