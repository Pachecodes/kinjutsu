import { beforeEach, expect, it } from 'vitest'
import { useComposer, toGenerationRequest } from './composer'
import { makePreset, makeVideoAsset, makeAsset } from '../test/factories'

beforeEach(() => useComposer.getState().reset())
it('keeps preset canvas fixed when media is attached afterward', () => {
  useComposer.getState().applyPreset(makePreset({id:'character-swap-v11',suggests_mode:'ref2va',patch:{width:576,height:1024,length:124,steps:20}}))
  useComposer.getState().addAsset(makeAsset({width:1000,height:1000}))
  useComposer.getState().addAsset(makeVideoAsset())
  expect(useComposer.getState().width).toBe(576)
  expect(useComposer.getState().height).toBe(1024)
  expect(useComposer.getState().references[1].role).toBe('aligned_guide')
})

it('loads author guide preset, inserts trigger and preserves guide role through Reuse', () => {
  useComposer.getState().setMode('ref2va')
  const portrait=makeAsset({id:'portrait'})
  const guide=makeVideoAsset({id:'guide'})
  useComposer.getState().addAsset(portrait)
  useComposer.getState().addAsset(guide)
  useComposer.getState().setPrompt('Replace the main subject with <Picture 1>.')
  useComposer.getState().applyPreset(makePreset({id:'character-swap-v11',suggests_mode:'ref2va',patch:{width:576,height:1024,length:124,steps:20,method:'baseline',continuity:{auto_split:false,window:'auto',pin_frames:'22'},lora_chain:[{name:'minimax_h3_character_swap_v1.1_ref2va_fro.safetensors',strength:1}]}}))
  const request=toGenerationRequest(useComposer.getState())
  expect(request.prompt).toBe('body_swap: Replace the main subject with <Picture 1>.')
  expect(request.references[1].role).toBe('aligned_guide')
  expect(request.references[1].include_audio).toBe(false)
  useComposer.getState().reset()
  useComposer.getState().loadRequest(request,new Map([['portrait',portrait],['guide',guide]]))
  expect(toGenerationRequest(useComposer.getState())).toEqual(request)
})
