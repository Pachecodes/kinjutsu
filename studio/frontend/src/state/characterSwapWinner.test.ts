import { beforeEach, expect, it } from 'vitest'
import { useComposer, toGenerationRequest } from './composer'
import { makePreset, makeVideoAsset, makeAsset } from '../test/factories'

const prompt = 'body_swap: Replace the single adult guide person with <Picture 1>. Preserve guide clothing, scene and motion.'
const winner = () => makePreset({id:'character-swap-hd-turbo8',suggests_mode:'ref2va',patch:{width:736,height:1280,length:124,steps:8,method:'baseline',weights:'int8',encoder:'standard',sampler_name:'euler',scheduler:'simple',ref_image_size:'match',prompt,continuity:{auto_split:false,window:'auto',pin_frames:'22'},lora_chain:[{name:'latest_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors',strength:1},{name:'minimax_h3_character_swap_v1.1_ref2va_fro.safetensors',strength:1}]}})
beforeEach(() => useComposer.getState().reset())
it('loads winner prompt replacing stale the reference character scene, and maps existing references to identity and aligned guide', () => {
  const s = useComposer.getState()
  s.setMode('ref2va')
  s.addAsset(makeAsset({id:'new-identity'}))
  s.addAsset(makeVideoAsset({id:'new-guide'}))
  s.setPrompt('the reference character wears sunglasses on a couch')
  s.setTitle('Old the reference character take')
  s.applyPreset({...winner(),patch:{...winner().patch,title:''}})
  const req=toGenerationRequest(useComposer.getState())
  expect(req.title ?? '').toBe('')
  expect(req.prompt).toBe(prompt)
  expect(req.references.map(r => r.role)).toEqual(['identity','aligned_guide'])
  expect(req.references[1].include_audio).toBe(false)
  expect([req.width,req.height,req.length,req.steps]).toEqual([736,1280,124,8])
  expect(req.lora_chain).toEqual(winner().patch.lora_chain)
  expect(useComposer.getState().auto_ratio).toBe(false)
})
it('keeps HD canvas and marks newly attached video as aligned guide after applying winner', () => {
  useComposer.getState().applyPreset(winner())
  useComposer.getState().addAsset(makeAsset({width:800,height:800}))
  useComposer.getState().addAsset(makeVideoAsset())
  expect(useComposer.getState().references[0].role).toBe('identity')
  expect(useComposer.getState().references[1].role).toBe('aligned_guide')
  expect([useComposer.getState().width,useComposer.getState().height]).toEqual([736,1280])
  useComposer.getState().setPrompt('body_swap: My edited direction with <Picture 1>.')
  expect(toGenerationRequest(useComposer.getState()).prompt).toContain('My edited direction')
})
