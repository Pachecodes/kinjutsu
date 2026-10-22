from copy import deepcopy
from app.presets import PRESETS
from app.schemas import GenerationRequest, RefKind
from app.workflow.validation import ResolvedAsset, validate_request
from app.workflow.builder import build_workflow

SWAP='minimax_h3_character_swap_v1.1_ref2va_fro.safetensors'
TURBO='latest_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors'

def assets():
    return {'identity':ResolvedAsset(id='identity',kind=RefKind.image,comfy_name='portrait.jpg'), 'motion':ResolvedAsset(id='motion',kind=RefKind.video,comfy_name='raw-video.mp4',duration_seconds=9.229,width=1126,height=642)}

def request(preset_id='character-swap-playground', role='motion'):
    return GenerationRequest.model_validate(dict(mode='ref2va',preset_id=preset_id,prompt='body_swap: Replace the person in <Video 1> with <Picture 1>.',width=576,height=1024,length=124,steps=8,method='baseline',weights='int8',sampler_name='euler',scheduler='simple',lora_chain=[{'name':TURBO,'strength':1},{'name':SWAP,'strength':1}],references=[{'asset_id':'identity','kind':'image','role':'identity'},{'asset_id':'motion','kind':'video','role':role}]))

def test_playground_uses_normal_video_refs_without_requiring_aligned_metadata():
    req,issues=validate_request(request(),assets(),aligned_guides_available=False)
    assert not [i for i in issues if i.severity.value=='error'], issues
    assert 'character_swap_playground' in [i.code for i in issues]
    graph=build_workflow(req,assets(),seed=1,filename_prefix='no-submit').prompt
    assert not any(n['class_type']=='MiniMaxH3AddGuide' for n in graph.values())
    assert any(k.startswith('ref_videos.') for n in graph.values() if n['class_type']=='MiniMaxH3ReferenceToVideo' for k in n['inputs'])
    assert [n['inputs']['lora_name'] for n in graph.values() if n['class_type']=='LoraLoaderModelOnly']==[TURBO,SWAP]

def test_strict_recipe_still_requires_verified_aligned_video():
    _,issues=validate_request(request('character-swap-hd-turbo8'),assets(),aligned_guides_available=True)
    assert 'character_swap_guide_required' in [i.code for i in issues]
    _,issues=validate_request(request(role='aligned_guide'),assets(),aligned_guides_available=True)
    assert 'guide_metadata_missing' in [i.code for i in issues]

def test_playground_is_an_explicit_lora_and_prompt_template():
    p=next((p for p in PRESETS if p['id']=='character-swap-playground'),None)
    assert p is not None, 'Publish a separate experimental template'
    assert [l['name'] for l in p['patch']['lora_chain']]==[TURBO,SWAP]
    assert '<Video 1>' in p['patch']['prompt'] and '<Picture 1>' in p['patch']['prompt']
    assert 'the reference character' not in p['patch']['prompt']
    assert any('experimental' in x.lower() for x in p['caveats'])
