import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useComposer } from '../../state/composer'
import { makePreset } from '../../test/factories'
import { renderWithProviders, resetStores, stubFetch } from '../../test/utils'
import { RecipeList } from './RecipeRail'

const swap = makePreset({
  id: 'character-swap-hd-turbo8',
  label: 'Character Swap · HD Turbo8 ✓',
  suggests_mode: 'ref2va',
  patch: {
    width: 736,
    height: 1280,
    length: 124,
    steps: 8,
    method: 'baseline',
    sampler_name: 'euler',
    scheduler: 'simple',
    title: '',
    prompt: 'body_swap: Replace the person in the aligned guide with <Picture 1>.',
  },
})
const preview = makePreset()
const playground = makePreset({ id: 'character-swap-playground', label: 'Character Swap · Experimentar' })

describe('curated recipes', () => {
  beforeEach(() => {
    resetStores()
    window.localStorage.clear()
  })
  afterEach(() => vi.unstubAllGlobals())

  it('keeps experiments behind a remembered opt-in', async () => {
    const user = userEvent.setup()
    renderWithProviders(<RecipeList presets={[swap, preview, playground]} comfyOnline />)

    expect(screen.getByRole('heading', { name: 'Recomendadas' })).toBeInTheDocument()
    expect(screen.getByText('Character Swap · HD Turbo8 ✓')).toBeInTheDocument()
    expect(screen.queryByText('Character Swap · Experimentar')).not.toBeInTheDocument()

    await user.click(screen.getByRole('switch', { name: /recetas experimentales/i }))
    expect(screen.getByText('Character Swap · Experimentar')).toBeInTheDocument()
    expect(window.localStorage.getItem('h3studio.recipes.showExperimental')).toBe('1')
  })

  it('asks before replacing a written prompt, never generates, and drops the old title', async () => {
    const user = userEvent.setup()
    const { calls } = stubFetch([])
    useComposer.setState({ prompt: 'Old couch scene from a previous take', title: 'Previous take 3' })
    renderWithProviders(<RecipeList presets={[swap, preview]} comfyOnline />)

    await user.click(screen.getByRole('button', { name: /^Character Swap · HD Turbo8/ }))
    const dialog = await screen.findByRole('alertdialog')
    expect(within(dialog).getByText(/sustituirá el que escribiste/)).toBeInTheDocument()

    await user.click(within(dialog).getByRole('button', { name: 'Mantener mi prompt' }))
    expect(useComposer.getState().prompt).toBe('Old couch scene from a previous take')
    expect(useComposer.getState().presetId).toBeNull()

    await user.click(screen.getByRole('button', { name: /^Character Swap · HD Turbo8/ }))
    await user.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Cargar receta' }))
    const state = useComposer.getState()
    expect(state.prompt).toBe(swap.patch.prompt)
    expect(state.title).toBe('')
    expect(state.presetId).toBe('character-swap-hd-turbo8')
    expect(state.mode).toBe('ref2va')
    expect(await screen.findByText(/No se ha generado nada/)).toBeInTheDocument()
    expect(calls.filter((call) => call.method === 'POST')).toEqual([])
  })

  it('loads a recipe without a prompt straight away', async () => {
    const user = userEvent.setup()
    useComposer.setState({ prompt: 'my lighthouse' })
    renderWithProviders(<RecipeList presets={[swap, preview]} comfyOnline />)

    await user.click(screen.getByRole('button', { name: /^Fast Preview 5s/ }))
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(useComposer.getState()).toMatchObject({ prompt: 'my lighthouse', method: 'easycache', presetId: 'fast-preview-5s' })
  })

  it('blocks a recipe the live runtime cannot run, but not while availability is unknown', () => {
    const missing = { ...preview, available: false, unavailable_reason: 'Missing LoRA.' }
    const { unmount } = renderWithProviders(<RecipeList presets={[missing]} comfyOnline />)
    expect(screen.getByRole('button', { name: /^Fast Preview 5s/ })).toBeDisabled()
    expect(screen.getByText(/No disponible: Missing LoRA/)).toBeInTheDocument()
    unmount()

    renderWithProviders(<RecipeList presets={[missing]} comfyOnline={false} />)
    expect(screen.getByRole('button', { name: /^Fast Preview 5s/ })).toBeEnabled()
  })
})
