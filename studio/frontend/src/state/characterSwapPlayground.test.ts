import {beforeEach,expect,it} from 'vitest'
import {useComposer,toGenerationRequest} from './composer'
import {makePreset,makeAsset,makeVideoAsset} from '../test/factories'
const p=()=>makePreset({id:'character-swap-playground',suggests_mode:'ref2va',patch:{width:576,height:1024,length:124,steps:8,method:'baseline',sampler_name:'euler',scheduler:'simple',prompt:'body_swap: Replace the adult in <Video 1> with <Picture 1>.',title:'',lora_chain:[{name:'latest_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors',strength:1},{name:'minimax_h3_character_swap_v1.1_ref2va_fro.safetensors',strength:1}]}})
beforeEach(()=>useComposer.getState().reset())
it('loads experiment from a strict recipe and converts existing guide to normal motion reference',()=>{
 const s=useComposer.getState();s.setMode('ref2va');s.addAsset(makeAsset());s.addAsset(makeVideoAsset());const uid=useComposer.getState().references[1].uid;s.setRole(uid,'aligned_guide');s.setPrompt('Old the reference character couch');s.applyPreset(p());const req=toGenerationRequest(useComposer.getState());expect(req.references[1].role).toBe('motion');expect(req.references[1].include_audio).toBe(false);expect(req.prompt).toContain('<Video 1>');expect(req.prompt).not.toContain('the reference character');expect(req.lora_chain).toEqual(p().patch.lora_chain);expect(useComposer.getState().auto_ratio).toBe(true)
})
it('keeps new uploads as normal references and all settings editable',()=>{
 useComposer.getState().applyPreset(p());useComposer.getState().addAsset(makeAsset());useComposer.getState().addAsset(makeVideoAsset());expect(toGenerationRequest(useComposer.getState()).references[1].role).toBe('motion');useComposer.getState().setPrompt('body_swap: Experiment with <Picture 1> and <Video 1>.');expect(toGenerationRequest(useComposer.getState()).prompt).toContain('Experiment with')
})
