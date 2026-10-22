import { expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ReferenceCard } from './ReferenceCard'
import { makeVideoAsset } from '../../test/factories'
import { PromptComposer } from '../composer/PromptComposer'
import { useComposer } from '../../state/composer'
import { renderWithProviders } from '../../test/utils'

it('keeps guide prompts manual rather than inventing Video tokens in AI tools', () => {
  useComposer.getState().reset()
  useComposer.setState({mode:'ref2va',prompt:'body_swap: <Picture 1>',references:[{uid:'guide',asset:makeVideoAsset(),role:'aligned_guide',include_audio:false}]})
  renderWithProviders(<PromptComposer />)
  expect(screen.getByRole('button',{name:'AI Director'})).toBeDisabled()
  expect(screen.getByRole('button',{name:'GPU Prompt Chat'})).toBeDisabled()
})

it('renders a guide as frame-zero latent conditioning without a soundtrack control', () => {
  renderWithProviders(<ReferenceCard alignedGuides slot={{uid:'guide',asset:makeVideoAsset(),role:'aligned_guide',include_audio:false}} index={0} total={1} dragging={false} mode="ref2va" tag={null} onDragStart={()=>{}} onDragEnd={()=>{}} onDragOver={()=>{}} />)
  expect(screen.getByText(/Guía desde el frame 0 · sin token de vídeo · sin sonido/)).toBeInTheDocument()
  expect(screen.queryByRole('switch')).not.toBeInTheDocument()
})

it('disables the guide role until a live supported node is registered', async () => {
  renderWithProviders(<ReferenceCard alignedGuides={false} slot={{uid:'guide',asset:makeVideoAsset(),role:'aligned_guide',include_audio:false}} index={0} total={1} dragging={false} mode="ref2va" tag={null} onDragStart={()=>{}} onDragEnd={()=>{}} onDragOver={()=>{}} />)
  screen.getByRole('combobox').focus()
  await userEvent.keyboard('{Enter}')
  expect(screen.getByRole('option',{name:/Guía alineada/})).toHaveAttribute('data-disabled')
})
