import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../lib/api'

import { useComposer } from '../../state/composer'
import { makeAsset, makeVideoAsset, makeConfig } from '../../test/factories'
import { renderWithProviders, resetStores, stubFetch } from '../../test/utils'
import { ReferencesPanel } from './ReferencesPanel'

beforeEach(() => { vi.restoreAllMocks(); resetStores() })

function setup() {
  const identity = makeAsset({ id: 'identity' })
  const source = makeVideoAsset({ id: 'source', duration_seconds: 9.229 })
  const other = makeVideoAsset({ id: 'other' })
  useComposer.setState({ mode: 'ref2va', auto_ratio: false, width: 736, height: 1280, length: 124, presetId: 'keep-me', prompt: 'keep prompt', steps: 8 })
  for (const asset of [identity, source, other]) useComposer.getState().addAsset(asset)
  return { identity, source, other }
}

describe('Preparar guía integration', () => {
  it('rounds custom seconds upward and intentionally updates length only on success using original provenance', async () => {
    setup()
    const state = useComposer.getState()
    useComposer.setState({ references: state.references.map((s, i) => i === 1 ? { ...s, asset: makeVideoAsset({ id: 'derived', duration_seconds: 124/24, guide_provenance: { source_asset_id: 'original', source_duration_seconds: 16.667, fit: 'crop', start_seconds: 0 } }) } : s) })
    const prepared = makeVideoAsset({ id: 'long-guide' })
    const prepare = vi.spyOn(api, 'prepareGuide').mockResolvedValue({ asset: prepared, source_asset_id: 'derived', fit: 'crop', start_seconds: 0, verified: { width: 736, height: 1280, frame_count: 243, fps: 24 } })
    stubFetch([{ match: '/api/assets', body: [] }])
    renderWithProviders(<ReferencesPanel config={makeConfig({ capabilities: { ...makeConfig().capabilities, aligned_guides: true } })} />)
    fireEvent.click(screen.getAllByRole('button', { name: 'Preparar guía' })[0])
    fireEvent.change(screen.getByLabelText('Duración deseada (segundos)'), { target: { value: '10' } })
    expect(screen.getByText(/Solicitada:/)).toHaveTextContent('10 s')
    expect(screen.getByText(/736 × 1280/)).toHaveTextContent('243 fotogramas · 10.125 s')
    expect(useComposer.getState().length).toBe(124)
    expect(screen.getByRole('button', { name: 'Crear guía 24 FPS' })).toBeEnabled()
    fireEvent.click(screen.getByRole('button', { name: 'Crear guía 24 FPS' }))
    await waitFor(() => expect(useComposer.getState().length).toBe(243))
    expect(prepare).toHaveBeenCalledWith('derived', expect.objectContaining({ length: 243, fit: 'crop' }))
    expect(useComposer.getState().references[1].asset.id).toBe('long-guide')
  })

  it.each([
    ['0.001', 5, '0.208'],
    ['5.166666666666667', 124, '5.167'],
    ['10', 243, '10.125'],
    ['10.125', 243, '10.125'],
    ['10.126', 260, '10.833'],
    ['149.66666666666666', 3592, '149.667'],
  ])('previews seconds %s as %i exact grid frames without silently shortening', (value, frames, actual) => {
    setup()
    stubFetch([{ match: '/api/assets', body: [] }])
    renderWithProviders(<ReferencesPanel config={makeConfig({ capabilities: { ...makeConfig().capabilities, aligned_guides: true } })} />)
    fireEvent.click(screen.getAllByRole('button', { name: 'Preparar guía' })[0])
    fireEvent.change(screen.getByLabelText('Duración deseada (segundos)'), { target: { value } })
    expect(screen.getByText(/736 × 1280/)).toHaveTextContent(`${frames} fotogramas · ${actual} s`)
    expect(useComposer.getState().length).toBe(124)
  })

  it.each(['', '0', '-1', '150', '99999'])('rejects invalid or above-grid-max seconds %s without clamping', value => {
    setup()
    const prepare = vi.spyOn(api, 'prepareGuide')
    stubFetch([{ match: '/api/assets', body: [] }])
    renderWithProviders(<ReferencesPanel config={makeConfig({ capabilities: { ...makeConfig().capabilities, aligned_guides: true } })} />)
    fireEvent.click(screen.getAllByRole('button', { name: 'Preparar guía' })[0])
    fireEvent.change(screen.getByLabelText('Duración deseada (segundos)'), { target: { value } })
    expect(screen.getByRole('alert')).toHaveTextContent('duración positiva')
    expect(screen.getByRole('button', { name: 'Crear guía 24 FPS' })).toBeDisabled()
    expect(useComposer.getState().length).toBe(124)
    expect(prepare).not.toHaveBeenCalled()
  })

  it('rejects rounded coverage beyond the original and shows explicit legacy guidance', () => {
    setup()
    stubFetch([{ match: '/api/assets', body: [] }])
    renderWithProviders(<ReferencesPanel config={makeConfig({ capabilities: { ...makeConfig().capabilities, aligned_guides: true } })} />)
    fireEvent.click(screen.getAllByRole('button', { name: 'Preparar guía' })[0])
    fireEvent.change(screen.getByLabelText('Duración deseada (segundos)'), { target: { value: '9.2' } })
    expect(screen.getByText(/736 × 1280/)).toHaveTextContent('226 fotogramas · 9.417 s')
    expect(screen.getByRole('alert')).toHaveTextContent('Vídeo demasiado corto')
    expect(screen.getByText(/Sin procedencia guardada/)).toHaveTextContent('selecciona el vídeo original desde Library')
    expect(screen.getByRole('button', { name: 'Crear guía 24 FPS' })).toBeDisabled()
  })

  it.each(['failure', 'mismatch', 'length', 'mode', 'removed'] as const)('never changes composer length or identity on custom-duration %s', async outcome => {
    setup()
    const before = useComposer.getState()
    let resolve!: (value: Awaited<ReturnType<typeof api.prepareGuide>>) => void
    let reject!: (reason: Error) => void
    vi.spyOn(api, 'prepareGuide').mockReturnValue(new Promise((done, fail) => { resolve = done; reject = fail }))
    stubFetch([{ match: '/api/assets', body: [] }])
    renderWithProviders(<ReferencesPanel config={makeConfig({ capabilities: { ...makeConfig().capabilities, aligned_guides: true } })} />)
    fireEvent.click(screen.getAllByRole('button', { name: 'Preparar guía' })[0])
    fireEvent.change(screen.getByLabelText('Duración deseada (segundos)'), { target: { value: '6' } })
    fireEvent.click(screen.getByRole('button', { name: 'Crear guía 24 FPS' }))
    act(() => {
      if (outcome === 'length') useComposer.setState({ length: 243 })
      if (outcome === 'mode') useComposer.setState({ mode: 'text' })
      if (outcome === 'removed') useComposer.setState({ references: before.references.filter(s => s.asset.id !== 'source') })
    })
    const expected = useComposer.getState()
    await act(async () => {
      if (outcome === 'failure') reject(new Error('Conversion failed'))
      else resolve({ asset: makeVideoAsset({ id: 'new' }), source_asset_id: 'source', fit: 'pad', start_seconds: 0, verified: { width: 736, height: 1280, frame_count: outcome === 'mismatch' ? 124 : 158, fps: 24 } })
    })
    expect(useComposer.getState().references).toEqual(expected.references)
    expect(useComposer.getState().length).toBe(expected.length)
    expect(useComposer.getState().presetId).toBe('keep-me')
    expect(useComposer.getState().prompt).toBe('keep prompt')
  })

  it('previews pad policy and creates a new asset in only the clicked slot without rendering', async () => {
    const { source } = setup()
    const before = useComposer.getState()
    const prepared = makeVideoAsset({ id: 'new-guide', has_audio: false })
    const { calls } = stubFetch([
      { match: '/prepare-guide', method: 'POST', status: 201, body: { asset: prepared, source_asset_id: source.id, verified: { width: 736, height: 1280, frame_count: 124, fps: 24 }, fit: 'pad', start_seconds: 0 } },
      { match: '/api/assets', body: [source, prepared] },
    ])
    renderWithProviders(<ReferencesPanel config={makeConfig({ capabilities: { ...makeConfig().capabilities, aligned_guides: true } })} />)
    fireEvent.click(screen.getAllByRole('button', { name: 'Preparar guía' })[0])
    expect(screen.getByText(/736 × 1280/)).toHaveTextContent('124 fotogramas · 5.167 s · 24 FPS')
    expect(screen.getByLabelText('Encuadre')).toHaveValue('pad')
    expect(screen.getByText(/El original se conserva/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Crear guía 24 FPS' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Guía preparada'))
    const after = useComposer.getState()
    expect(after.references[0]).toEqual(before.references[0])
    expect(after.references[2]).toEqual(before.references[2])
    expect(after.references[1]).toEqual({ ...before.references[1], asset: prepared, role: 'aligned_guide', include_audio: false })
    expect([after.width, after.height, after.length, after.presetId, after.prompt, after.steps]).toEqual([736, 1280, 124, 'keep-me', 'keep prompt', 8])
    expect(calls.filter(c => c.method === 'POST')).toEqual([{ url: '/api/assets/source/prepare-guide', method: 'POST', body: { width: 736, height: 1280, length: 124, fit: 'pad', start_seconds: 0 } }])
  })

  it('shows actionable short-source errors and prevents requests', () => {
    setup()
    useComposer.setState({ length: 362 })
    const { calls } = stubFetch([{ match: '/api/assets', body: [] }])
    renderWithProviders(<ReferencesPanel config={makeConfig({ capabilities: { ...makeConfig().capabilities, aligned_guides: true } })} />)
    fireEvent.click(screen.getAllByRole('button', { name: 'Preparar guía' })[0])
    expect(screen.getByRole('alert')).toHaveTextContent('Vídeo demasiado corto')
    expect(screen.getByRole('alert')).toHaveTextContent('No se congela ni se repite el final')
    expect(screen.getByRole('button', { name: 'Crear guía 24 FPS' })).toBeDisabled()
    expect(calls.some(c => c.method === 'POST')).toBe(false)
  })

  it('sends explicit crop and offset, showing API errors without replacing source', async () => {
    setup()
    const before = useComposer.getState().references
    const { calls } = stubFetch([
      { match: '/prepare-guide', method: 'POST', status: 400, body: { detail: { code: 'guide_source_too_short', message: 'Origen corto: reduce la duración.' } } },
      { match: '/api/assets', body: [] },
    ])
    renderWithProviders(<ReferencesPanel config={makeConfig({ capabilities: { ...makeConfig().capabilities, aligned_guides: true } })} />)
    fireEvent.click(screen.getAllByRole('button', { name: 'Preparar guía' })[0])
    fireEvent.change(screen.getByLabelText('Encuadre'), { target: { value: 'crop' } })
    fireEvent.change(screen.getByLabelText('Inicio (segundos)'), { target: { value: '1.25' } })
    expect(screen.getByText(/Recorte centrado/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Crear guía 24 FPS' }))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Origen corto: reduce la duración.'))
    expect(useComposer.getState().references).toEqual(before)
    expect(calls.find(c => c.method === 'POST')?.body).toMatchObject({ fit: 'crop', start_seconds: 1.25 })
    expect(screen.getByRole('button', { name: 'Crear guía 24 FPS' })).toBeEnabled()
  })

  it.each(['target', 'slot'] as const)('does not overwrite a changed %s on a late result; loading prevents duplicate clicks', async change => {
    const { source } = setup()
    const before = useComposer.getState().references
    stubFetch([{ match: '/api/assets', body: [] }])
    let resolve!: (value: Awaited<ReturnType<typeof api.prepareGuide>>) => void
    const pending = new Promise<Awaited<ReturnType<typeof api.prepareGuide>>>(done => { resolve = done })
    const prepare = vi.spyOn(api, 'prepareGuide').mockReturnValue(pending)
    renderWithProviders(<ReferencesPanel config={makeConfig({ capabilities: { ...makeConfig().capabilities, aligned_guides: true } })} />)
    fireEvent.click(screen.getAllByRole('button', { name: 'Preparar guía' })[0])
    fireEvent.click(screen.getByRole('button', { name: 'Crear guía 24 FPS' }))
    expect(screen.getByRole('button', { name: 'Preparando guía…' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Preparando guía…' }))
    expect(prepare).toHaveBeenCalledTimes(1)
    act(() => {
      if (change === 'target') useComposer.setState({ width: 768 })
      else useComposer.setState({ references: before.map((slot, i) => i === 1 ? { ...slot, asset: makeVideoAsset({ id: 'replacement' }) } : slot) })
    })
    const expected = useComposer.getState().references
    await act(async () => resolve({ asset: makeVideoAsset({ id: 'late-guide' }), source_asset_id: source.id, fit: 'pad', start_seconds: 0, verified: { width: 736, height: 1280, frame_count: 124, fps: 24 } }))
    expect(useComposer.getState().references).toEqual(expected)
    expect(screen.getByRole('status')).toHaveTextContent('no se sustituyó ninguna referencia')
  })

  it('only offers normalization for videos in a mode with aligned support', () => {
    setup()
    stubFetch([{ match: '/api/assets', body: [] }])
    renderWithProviders(<ReferencesPanel config={makeConfig()} />)
    expect(screen.queryByRole('button', { name: 'Preparar guía' })).not.toBeInTheDocument()
  })
})
