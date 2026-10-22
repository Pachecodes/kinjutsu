import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { PromptComposer } from './PromptComposer'
import { useComposer } from '../../state/composer'
import { renderWithProviders, resetStores, stubFetch } from '../../test/utils'

describe('AI Director prompt preview', () => {
  beforeEach(() => resetStores())
  afterEach(() => vi.unstubAllGlobals())

  it('previews without mutating, applies explicitly, and can undo', async () => {
    const user = userEvent.setup()
    useComposer.setState({ prompt: 'Una astronauta camina por la luna', mode: 'text', length: 124 })
    const { calls } = stubFetch([
      {
        match: '/api/director/enhance',
        method: 'POST',
        body: {
          original_prompt: 'Una astronauta camina por la luna',
          enhanced_prompt: '[SCENE]\nAn astronaut crosses the moon.',
          analyses: [],
          cached_analyses: 0,
          model: 'local-test-model',
        },
      },
    ])

    renderWithProviders(<PromptComposer />)
    await user.click(screen.getByRole('button', { name: /ai director/i }))

    expect(useComposer.getState().prompt).toBe('Una astronauta camina por la luna')
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Enhanced prompt' })).toHaveTextContent(
      '[SCENE] An astronaut crosses the moon.',
    )
    expect(calls.find((call) => call.url.includes('/api/director/enhance'))).toMatchObject({
      method: 'POST',
      body: { mode: 'text', prompt: 'Una astronauta camina por la luna', length: 124, references: [] },
    })

    await user.click(screen.getByRole('button', { name: /apply enhanced prompt/i }))
    expect(useComposer.getState().prompt).toBe('[SCENE]\nAn astronaut crosses the moon.')

    await user.click(screen.getByRole('button', { name: /undo ai director/i }))
    expect(useComposer.getState().prompt).toBe('Una astronauta camina por la luna')
  })

  it('shows a local error beside the action', async () => {
    const user = userEvent.setup()
    useComposer.setState({ prompt: 'A scene' })
    stubFetch([
      {
        match: '/api/director/enhance',
        method: 'POST',
        status: 409,
        body: { detail: 'AI Director waits until the active H3 render finishes.' },
      },
    ])

    renderWithProviders(<PromptComposer />)
    await user.click(screen.getByRole('button', { name: /ai director/i }))

    expect(await screen.findByText(/waits until the active h3 render finishes/i)).toBeInTheDocument()
    expect(useComposer.getState().prompt).toBe('A scene')
  })

  it('chats with GPU Gemma and applies its response to the composer', async () => {
    const user = userEvent.setup()
    useComposer.setState({
      prompt: 'A simple beach shot',
      mode: 'ref2va',
      length: 124,
      references: [
        {
          uid: 'slot-1',
          role: 'identity',
          include_audio: false,
          asset: {
            id: 'asset-1',
            kind: 'image',
            original_name: 'subject.png',
            stored_name: 'safe.png',
            mime: 'image/png',
            size_bytes: 100,
            width: 512,
            height: 512,
            duration_seconds: null,
            has_audio: null,
            created_at: '2026-09-06T00:00:00Z',
            url: '/api/assets/asset-1/file',
          },
        },
      ],
    })
    const { calls } = stubFetch([
      {
        match: '/api/director/chat',
        method: 'POST',
        body: {
          message: '[SCENE]\nA production-ready beach shot.',
          model: 'gemma4-e2b-h3-prompts-gpu',
          visual_references: 1,
        },
      },
    ])

    renderWithProviders(<PromptComposer />)
    await user.click(screen.getByRole('button', { name: /gpu prompt chat/i }))
    expect(screen.getByText(/released automatically before h3 renders/i)).toBeInTheDocument()
    expect(screen.getByText(/gemma sees 1 attached image/i)).toBeInTheDocument()
    await user.type(screen.getByLabelText('Message'), 'Write the final prompt')
    await user.click(screen.getByRole('button', { name: /send message to gemma/i }))

    expect(await screen.findByText(/production-ready beach shot/i)).toBeInTheDocument()
    expect(calls.find((call) => call.url.includes('/api/director/chat'))?.body).toMatchObject({
      references: [{ asset_id: 'asset-1', kind: 'image', role: 'identity' }],
    })
    await user.click(screen.getByRole('button', { name: /use as h3 prompt/i }))
    expect(useComposer.getState().prompt).toBe('[SCENE]\nA production-ready beach shot.')

    await user.click(screen.getByRole('button', { name: /gpu prompt chat/i }))
    expect(within(screen.getByRole('dialog')).queryByText(/production-ready beach shot/i)).not.toBeInTheDocument()
    expect(screen.getByText(/gemma sees 1 attached image/i)).toBeInTheDocument()
  })
})
