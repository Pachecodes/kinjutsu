from copy import deepcopy
from app.presets import PRESETS
from app.schemas import GenerationRequest
from app.capabilities import build_capabilities
from app.api import _presets_with_availability
from tests.conftest import CONTRACT

SWAP = 'minimax_h3_character_swap_v1.1_ref2va_fro.safetensors'
TURBO = 'latest_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors'

def test_approved_hd_turbo8_preset_loads_generic_prompt_and_exact_recipe():
    preset = next((p for p in PRESETS if p['id'] == 'character-swap-hd-turbo8'), None)
    assert preset is not None, 'Approved HD Turbo8 recipe must be selectable'
    patch = preset['patch']
    assert preset['suggests_mode'] == 'ref2va'
    assert (patch['width'], patch['height'], patch['length'], patch['steps']) == (736,1280,124,8)
    assert (patch['method'],patch['weights'],patch['encoder']) == ('baseline','int8','standard')
    assert (patch['sampler_name'],patch['scheduler'],patch['ref_image_size']) == ('euler','simple','match')
    assert patch['lora_chain'] == [{'name':TURBO,'strength':1.0},{'name':SWAP,'strength':1.0}]
    assert patch['continuity']['auto_split'] is False
    assert patch['prompt'].startswith('body_swap:') and '<Picture 1>' in patch['prompt']
    assert '<Video' not in patch['prompt'] and 'the reference character' not in patch['prompt']
    assert all(word in patch['prompt'].lower() for word in ['both hands','arms','neck','clothing','lighting'])
    GenerationRequest.model_validate({'mode':'ref2va', **patch})


def test_winning_preset_requires_both_adapters_and_aligned_guide_contract():
    info=deepcopy(CONTRACT)
    names=info['LoraLoaderModelOnly']['input']['required']['lora_name'][0]
    names[:] = [name for name in names if name not in {SWAP, TURBO}]
    names.append(SWAP)
    info['MiniMaxH3AddGuide']={'input':{'required':{'positive':['CONDITIONING'],'latent':['LATENT'],'frame_idx':['INT']},'optional':{'vae':['VAE'],'image':['IMAGE']}}}
    def preset():
        caps=build_capabilities(info,comfy_url='test',comfy_online=True,source='live')
        return next((p for p in _presets_with_availability(caps) if p['id']=='character-swap-hd-turbo8'), None)
    p=preset()
    assert p is not None, 'Approved HD Turbo8 recipe must be published'
    assert not p['available']
    names.append(TURBO)
    assert preset()['available']
    del info['MiniMaxH3AddGuide']
    assert not preset()['available']
